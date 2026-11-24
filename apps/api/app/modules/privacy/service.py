import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, delete, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ForbiddenError
from app.core.security import verify_password
from app.modules.auth.models import EmailToken, RefreshToken
from app.modules.chat.models import ChatMessage, SenderRole
from app.modules.draws import crypto
from app.modules.draws.models import Draw, DrawAssignment
from app.modules.groups.models import Group
from app.modules.notifications.models import PushSubscription
from app.modules.participants.models import Participant, ParticipantRole
from app.modules.privacy.schemas import DeleteAccountIn
from app.modules.rules.repository import RulesRepository
from app.modules.users.models import User
from app.modules.wishlist.models import ParticipantPreferences, WishlistItem

logger = logging.getLogger(__name__)

REMOVED_NAME = "Participante removido"


class PrivacyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Exportação ---

    async def export(self, user: User) -> dict[str, Any]:
        participants = (
            await self.session.scalars(
                select(Participant)
                .where(Participant.user_id == user.id)
                .order_by(Participant.joined_at)
            )
        ).all()
        groups_out = []
        for p in participants:
            group = await self.session.get(Group, p.group_id)
            items = (
                await self.session.scalars(
                    select(WishlistItem).where(WishlistItem.participant_id == p.id)
                )
            ).all()
            prefs = await self.session.get(ParticipantPreferences, p.id)
            groups_out.append(
                {
                    "group": group.title if group else None,
                    "role": p.role,
                    "joined_at": p.joined_at,
                    "left_at": p.left_at,
                    "wishlist": [
                        {
                            "title": i.title,
                            "url": i.url,
                            "price_hint_cents": i.price_hint_cents,
                            "priority": i.priority,
                            "notes": i.notes,
                        }
                        for i in items
                    ],
                    "preferences": {
                        "dislikes": prefs.dislikes if prefs else None,
                        "notes": prefs.notes if prefs else None,
                    },
                    "messages_sent": await self._my_messages(p),
                }
            )
        push_count = await self.session.scalar(
            select(func.count()).where(PushSubscription.user_id == user.id)
        )
        return {
            "exported_at": datetime.now(UTC),
            "profile": {
                "name": user.name,
                "email": user.email,
                "email_verified_at": user.email_verified_at,
                "created_at": user.created_at,
                "avatar_url": user.avatar_url,
                "shirt_size": user.shirt_size,
                "shoe_size": user.shoe_size,
                "phone": user.phone,
                "whatsapp_opt_in": user.whatsapp_opt_in,
                "email_reminders": user.email_reminders,
                "login_with_google": user.google_sub is not None,
            },
            "groups": groups_out,
            "push_devices": int(push_count or 0),
        }

    async def _my_messages(self, participant: Participant) -> list[dict[str, Any]]:
        conditions = await self._my_message_conditions(participant)
        if not conditions:
            return []
        rows = (
            await self.session.scalars(
                select(ChatMessage).where(or_(*conditions)).order_by(ChatMessage.id)
            )
        ).all()
        return [{"sent_at": m.created_at, "body": m.body} for m in rows]

    async def _my_message_conditions(self, participant: Participant) -> list[Any]:
        """Mensagens que o participante enviou, nos dois papéis (quem dá e quem recebe)."""
        conditions = []
        draws = (
            await self.session.scalars(select(Draw).where(Draw.group_id == participant.group_id))
        ).all()
        for draw in draws:
            as_giver = select(DrawAssignment.id).where(
                DrawAssignment.draw_id == draw.id,
                DrawAssignment.giver_participant_id == participant.id,
            )
            lookup = crypto.receiver_lookup_hash(draw.id, participant.id)
            as_receiver = select(DrawAssignment.id).where(
                DrawAssignment.draw_id == draw.id, DrawAssignment.receiver_lookup_hash == lookup
            )
            conditions.append(
                and_(
                    ChatMessage.assignment_id.in_(as_giver),
                    ChatMessage.sender_role == SenderRole.GIVER,
                )
            )
            conditions.append(
                and_(
                    ChatMessage.assignment_id.in_(as_receiver),
                    ChatMessage.sender_role == SenderRole.RECEIVER,
                )
            )
        return conditions

    # --- Exclusão ---

    async def delete_account(self, user: User, data: DeleteAccountIn) -> str:
        if user.password_hash:
            if not data.password or not verify_password(data.password, user.password_hash):
                raise ForbiddenError("Senha incorreta.", code="invalid_password")
        elif (data.confirm or "").strip().upper() != "EXCLUIR":
            raise ForbiddenError('Digite "EXCLUIR" para confirmar.', code="confirmation_required")

        participants = (
            await self.session.scalars(select(Participant).where(Participant.user_id == user.id))
        ).all()
        await self._handover_owned_groups(user, participants)

        in_draw = bool(
            await self.session.scalar(
                select(
                    exists().where(
                        Participant.user_id == user.id,
                        Draw.group_id == Participant.group_id,
                    )
                )
            )
        )
        rules = RulesRepository(self.session)
        for p in participants:
            await self._erase_participant_content(p)
            if not in_draw:
                await rules.remove_participant(p.id)
        if in_draw:
            await self._anonymize(user)
            mode = "anonymized"
        else:
            await self.session.execute(delete(Participant).where(Participant.user_id == user.id))
            await self.session.execute(delete(User).where(User.id == user.id))
            mode = "deleted"
        await self.session.commit()
        logger.info("account_deleted", extra={"mode": mode})
        return mode

    async def _handover_owned_groups(self, user: User, participants: Any) -> None:
        """Grupos que a pessoa criou passam para um coorganizador (ou o membro mais antigo).

        Grupos sem mais ninguém são apagados.
        """
        owned = (await self.session.scalars(select(Group).where(Group.owner_id == user.id))).all()
        for group in owned:
            others = (
                await self.session.scalars(
                    select(Participant)
                    .where(
                        Participant.group_id == group.id,
                        Participant.user_id != user.id,
                        Participant.left_at.is_(None),
                    )
                    .order_by(
                        (Participant.role == ParticipantRole.CO_OWNER).desc(),
                        Participant.joined_at,
                    )
                )
            ).all()
            if not others:
                await self.session.delete(group)
                continue
            heir = others[0]
            heir.role = ParticipantRole.OWNER
            group.owner_id = heir.user_id
            mine = next((p for p in participants if p.group_id == group.id), None)
            if mine is not None:
                mine.role = ParticipantRole.MEMBER
        await self.session.flush()

    async def _erase_participant_content(self, participant: Participant) -> None:
        await self.session.execute(
            delete(WishlistItem).where(WishlistItem.participant_id == participant.id)
        )
        await self.session.execute(
            delete(ParticipantPreferences).where(
                ParticipantPreferences.participant_id == participant.id
            )
        )
        conditions = await self._my_message_conditions(participant)
        if conditions:
            await self.session.execute(delete(ChatMessage).where(or_(*conditions)))

    async def _anonymize(self, user: User) -> None:
        now = datetime.now(UTC)
        user.name = REMOVED_NAME
        user.email = f"removido+{uuid.uuid4().hex}@invalid.tireivoce"
        user.password_hash = None
        user.google_sub = None
        user.email_verified_at = None
        user.avatar_url = None
        user.shirt_size = None
        user.shoe_size = None
        user.phone = None
        user.whatsapp_opt_in = False
        user.email_reminders = False
        user.is_admin = False
        user.is_active = False
        user.deleted_at = now
        await self.session.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
        await self.session.execute(delete(EmailToken).where(EmailToken.user_id == user.id))
        await self.session.execute(
            delete(PushSubscription).where(PushSubscription.user_id == user.id)
        )

    # --- Retenção (job diário) ---

    async def purge(self, now: datetime) -> dict[str, int]:
        settings = get_settings()
        cutoff = now - timedelta(days=30 * settings.retention_months)
        stale_groups = select(Group.id).where(
            Group.updated_at < cutoff, or_(Group.event_at.is_(None), Group.event_at < cutoff)
        )
        groups = await self._delete(delete(Group).where(Group.id.in_(stale_groups)))

        # Contas nunca confirmadas e sem participação em grupos.
        unverified_cutoff = now - timedelta(days=settings.unverified_account_days)
        lonely = ~exists().where(Participant.user_id == User.id)
        no_owned = ~exists().where(Group.owner_id == User.id)
        unverified = await self._delete(
            delete(User).where(
                User.email_verified_at.is_(None),
                User.deleted_at.is_(None),
                User.created_at < unverified_cutoff,
                lonely,
                no_owned,
            )
        )
        # Contas anonimizadas que não estão mais em nenhum grupo.
        anonymized = await self._delete(
            delete(User).where(User.deleted_at.is_not(None), lonely, no_owned)
        )
        token_cutoff = now - timedelta(days=30)
        tokens = await self._delete(
            delete(RefreshToken).where(
                or_(RefreshToken.expires_at < token_cutoff, RefreshToken.revoked_at < token_cutoff)
            )
        )
        tokens += await self._delete(delete(EmailToken).where(EmailToken.expires_at < token_cutoff))
        await self.session.commit()
        result = {
            "groups": groups,
            "unverified_users": unverified,
            "anonymized_users": anonymized,
            "tokens": tokens,
        }
        logger.info("retention_purge", extra=result)
        return result

    async def _delete(self, stmt: Any) -> int:
        result = await self.session.execute(stmt.execution_options(synchronize_session=False))
        return int(getattr(result, "rowcount", 0) or 0)

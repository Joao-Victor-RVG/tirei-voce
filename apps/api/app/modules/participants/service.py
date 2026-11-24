import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.modules.groups.models import GroupStatus
from app.modules.groups.schemas import UserBrief
from app.modules.groups.service import GroupAccess, ensure_not_frozen
from app.modules.participants.models import Participant, ParticipantRole
from app.modules.participants.repository import ParticipantRepository
from app.modules.participants.schemas import ParticipantOut
from app.modules.rules.repository import RulesRepository
from app.modules.users.models import User

logger = logging.getLogger(__name__)


class ParticipantService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.access = GroupAccess(session)
        self.participants = ParticipantRepository(session)

    async def list(self, group_id: uuid.UUID, user: User) -> list[ParticipantOut]:
        membership = await self.access.member(group_id, user)
        participants = await self.participants.list_active(group_id)
        return [self._to_out(p, me=membership.participant) for p in participants]

    async def remove(self, group_id: uuid.UUID, participant_id: uuid.UUID, user: User) -> None:
        membership = await self.access.organizer(group_id, user, for_update=True)
        ensure_not_frozen(membership.group)
        target = await self.participants.get_active(group_id, participant_id)
        if target is None:
            raise NotFoundError("Participante não encontrado.", code="participant_not_found")
        if target.is_owner:
            raise ConflictError(
                "Quem criou o grupo não pode ser removido.", code="cannot_remove_owner"
            )
        if target.is_organizer and not membership.participant.is_owner:
            raise ForbiddenError(
                "Só quem criou o grupo pode remover coorganizadores.", code="owner_only"
            )
        await self._deactivate(target)
        logger.info("participant_removed", extra={"group_id": str(group_id)})

    async def leave(self, group_id: uuid.UUID, user: User) -> None:
        membership = await self.access.member(group_id, user, for_update=True)
        ensure_not_frozen(membership.group)
        if membership.participant.is_owner:
            raise ConflictError("Quem criou o grupo não pode sair dele.", code="owner_cannot_leave")
        await self._deactivate(membership.participant)

    async def set_role(
        self, group_id: uuid.UUID, participant_id: uuid.UUID, user: User, role: ParticipantRole
    ) -> ParticipantOut:
        """Promove a coorganizador ou volta a participante. Só o dono do grupo."""
        membership = await self.access.owner(group_id, user, for_update=True)
        if membership.group.status is GroupStatus.FINISHED:
            raise ConflictError("O grupo foi encerrado.", code="group_finished")
        target = await self.participants.get_active(group_id, participant_id)
        if target is None:
            raise NotFoundError("Participante não encontrado.", code="participant_not_found")
        if target.is_owner:
            raise ConflictError(
                "Quem criou o grupo já é o organizador.", code="cannot_change_owner"
            )
        target.role = role
        await self.session.commit()
        logger.info("participant_role_changed", extra={"group_id": str(group_id), "role": role})
        return self._to_out(target, me=membership.participant)

    async def _deactivate(self, participant: Participant) -> None:
        participant.left_at = datetime.now(UTC)
        await RulesRepository(self.session).remove_participant(participant.id)
        await self.session.commit()

    @staticmethod
    def _to_out(p: Participant, *, me: Participant) -> ParticipantOut:
        return ParticipantOut(
            id=p.id,
            user=UserBrief(id=p.user.id, name=p.user.name, avatar_url=p.user.avatar_url),
            role=p.role,
            joined_at=p.joined_at,
            is_me=p.id == me.id,
        )

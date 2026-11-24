import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.modules.groups.models import Group
from app.modules.notifications import templates
from app.modules.notifications.email import EmailSender
from app.modules.notifications.push import PushMessage, send_to_users
from app.modules.notifications.whatsapp import TEMPLATE_REMINDER, WhatsAppMessage, WhatsAppSender
from app.modules.participants.models import Participant
from app.modules.reminders.models import ReminderKind, SentReminder
from app.modules.reminders.schedule import (
    ACTIVE_STATUSES,
    ONE_DAY,
    REVEAL_WINDOW,
    DueReminder,
    due_reminders,
)
from app.modules.users.models import User
from app.modules.wishlist.models import WishlistItem

logger = logging.getLogger(__name__)

# Brasília não tem horário de verão desde 2019.
BRT = timezone(timedelta(hours=-3))


def format_br(value: datetime) -> str:
    local = value.astimezone(BRT)
    return f"{local:%d/%m} às {local:%H:%M}"


@dataclass(frozen=True)
class ReminderContent:
    subject: str
    headline: str
    body: str
    push_title: str


def content_for(group: Group, reminder: DueReminder) -> ReminderContent:
    name = f"“{group.title}”"
    when = format_br(reminder.target_at)
    place = f" em {group.event_location}" if group.event_location else ""
    if reminder.kind is ReminderKind.WISHLIST_DEADLINE:
        return ReminderContent(
            subject=f"Sua lista de desejos está vazia — {group.title}",
            headline="Monte sua lista de desejos 📝",
            body=f"O prazo para montar a lista de {name} termina {when}. "
            "Dê umas dicas para o seu amigo secreto não errar!",
            push_title="📝 Sua lista de desejos está vazia",
        )
    if reminder.kind is ReminderKind.REVEAL:
        return ReminderContent(
            subject=f"Hora da revelação! {group.title} 🎉",
            headline="Quem será que te tirou? 🎉",
            body=f"Chegou a hora de {name}! Abra o app e descubra quem foi seu amigo secreto.",
            push_title="🎉 Hora da revelação!",
        )
    if reminder.kind is ReminderKind.EVENT_1D:
        return ReminderContent(
            subject=f"É amanhã! {group.title} 🎁",
            headline="Falta só 1 dia! 🎁",
            body=f"{name} é amanhã, {when}{place}. Já está com o presente em mãos?",
            push_title="🎁 Falta 1 dia!",
        )
    return ReminderContent(
        subject=f"Faltam 2 horas! {group.title} ⏰",
        headline="Faltam 2 horas! ⏰",
        body=f"{name} começa {when}{place}. Não esquece o presente!",
        push_title="⏰ Faltam 2 horas!",
    )


class ReminderService:
    def __init__(
        self,
        session: AsyncSession,
        email_sender: EmailSender,
        whatsapp_sender: WhatsAppSender | None = None,
    ) -> None:
        self.session = session
        self.email_sender = email_sender
        self.whatsapp_sender = whatsapp_sender

    async def send_due(self, now: datetime) -> int:
        """Envia os lembretes vencidos. Retorna quantos lembretes (não pessoas) saíram."""
        horizon = now + ONE_DAY
        stmt = (
            select(Group)
            .options(selectinload(Group.theme))
            .where(
                Group.status.in_(ACTIVE_STATUSES),
                or_(
                    Group.event_at.between(now - REVEAL_WINDOW, horizon),
                    Group.wishlist_deadline_at.between(now, horizon),
                ),
            )
        )
        sent = 0
        for group in (await self.session.scalars(stmt)).all():
            for reminder in due_reminders(
                status=group.status,
                event_at=group.event_at,
                wishlist_deadline_at=group.wishlist_deadline_at,
                now=now,
            ):
                if await self._claim(group.id, reminder):
                    await self._deliver(group, reminder)
                    sent += 1
        return sent

    async def _claim(self, group_id: uuid.UUID, reminder: DueReminder) -> bool:
        """INSERT … ON CONFLICT DO NOTHING: só um worker ganha o direito de enviar."""
        stmt = (
            insert(SentReminder)
            .values(
                id=uuid.uuid4(), group_id=group_id, kind=reminder.kind, target_at=reminder.target_at
            )
            .on_conflict_do_nothing(constraint="uq_sent_reminders_group_kind_target")
            .returning(SentReminder.id)
        )
        claimed = await self.session.scalar(stmt)
        await self.session.commit()
        return claimed is not None

    async def _recipients(self, group: Group, reminder: DueReminder) -> list[User]:
        stmt = (
            select(User)
            .join(Participant, Participant.user_id == User.id)
            .where(
                Participant.group_id == group.id,
                Participant.left_at.is_(None),
                User.is_active.is_(True),
            )
        )
        if reminder.kind is ReminderKind.WISHLIST_DEADLINE:
            items = (
                select(func.count())
                .where(WishlistItem.participant_id == Participant.id)
                .correlate(Participant)
                .scalar_subquery()
            )
            stmt = stmt.where(items == 0)
        return list((await self.session.scalars(stmt)).all())

    async def _deliver(self, group: Group, reminder: DueReminder) -> None:
        users = await self._recipients(group, reminder)
        content = content_for(group, reminder)
        url = f"{get_settings().frontend_url}/groups/{group.id}"
        for user in users:
            if not (user.email_reminders and user.is_email_verified):
                continue
            try:
                await self.email_sender.send(
                    templates.reminder(
                        user.email, user.name, content.subject, content.headline, content.body, url
                    )
                )
            except Exception:
                logger.warning(
                    "reminder_email_failed", extra={"group_id": str(group.id)}, exc_info=True
                )
        if self.whatsapp_sender is not None:
            for user in users:
                if not (user.whatsapp_opt_in and user.phone):
                    continue
                try:
                    await self.whatsapp_sender.send(
                        WhatsAppMessage(
                            to=user.phone,
                            template=TEMPLATE_REMINDER,
                            params=(user.name, content.body, url),
                        )
                    )
                except Exception:
                    logger.warning(
                        "reminder_whatsapp_failed", extra={"group_id": str(group.id)}, exc_info=True
                    )
        await send_to_users(
            self.session,
            [u.id for u in users],
            PushMessage(
                title=content.push_title,
                body=content.body,
                url=f"/groups/{group.id}",
                tag=f"{reminder.kind}-{group.id}",
            ),
        )
        await self.session.execute(
            update(SentReminder)
            .where(
                SentReminder.group_id == group.id,
                SentReminder.kind == reminder.kind,
                SentReminder.target_at == reminder.target_at,
            )
            .values(recipients=len(users))
        )
        await self.session.commit()
        logger.info(
            "reminder_sent",
            extra={"group_id": str(group.id), "kind": reminder.kind, "recipients": len(users)},
        )

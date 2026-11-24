import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.modules.draws.service import DrawService
from app.modules.groups.models import Group, GroupStatus
from app.modules.notifications import templates
from app.modules.notifications.email import EmailSender
from app.modules.notifications.push import PushMessage, send_to_users
from app.modules.participants.models import Participant, ParticipantRole
from app.modules.users.models import User

logger = logging.getLogger(__name__)


async def run_scheduled_draws(email_sender: EmailSender, now: datetime) -> int:
    """Executa os sorteios agendados vencidos. Cada grupo em sua própria transação."""
    async with get_sessionmaker()() as session:
        due = (
            await session.scalars(
                select(Group.id).where(
                    Group.draw_scheduled_at <= now,
                    Group.status.in_((GroupStatus.OPEN, GroupStatus.CLOSED)),
                )
            )
        ).all()
    done = 0
    for group_id in due:
        async with get_sessionmaker()() as session:
            result = await DrawService(session).execute_scheduled(group_id, now)
            if result.done:
                done += 1
                logger.info("scheduled_draw_done", extra={"group_id": str(group_id)})
            elif result.error:
                logger.warning("scheduled_draw_failed", extra={"group_id": str(group_id)})
                await _notify_failure(session, email_sender, group_id, result.error)
    return done


async def _notify_failure(
    session: AsyncSession, email_sender: EmailSender, group_id: uuid.UUID, error: str
) -> None:
    group = await session.get(Group, group_id)
    if group is None:
        return
    organizers = (
        await session.scalars(
            select(User)
            .join(Participant, Participant.user_id == User.id)
            .where(
                Participant.group_id == group.id,
                Participant.left_at.is_(None),
                Participant.role.in_((ParticipantRole.OWNER, ParticipantRole.CO_OWNER)),
                User.is_active.is_(True),
            )
        )
    ).all()
    body = f"O sorteio automático de “{group.title}” não pôde ser feito: {error}"
    url = f"{get_settings().frontend_url}/groups/{group.id}?tab=rules"
    for user in organizers:
        if user.is_email_verified:
            await email_sender.send(
                templates.reminder(
                    user.email,
                    user.name,
                    f"Sorteio automático não realizado — {group.title}",
                    "O sorteio automático não rolou 😕",
                    body + " Ajuste as regras e sorteie manualmente.",
                    url,
                )
            )
    await send_to_users(
        session,
        [u.id for u in organizers],
        PushMessage(
            title="😕 O sorteio automático não rolou",
            body=body,
            url=f"/groups/{group.id}?tab=rules",
            tag=f"scheduled-draw-{group.id}",
        ),
    )

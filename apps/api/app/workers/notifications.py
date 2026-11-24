import uuid
from typing import Any

from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.modules.draws import crypto
from app.modules.draws.models import Draw, DrawAssignment
from app.modules.groups.models import Group
from app.modules.notifications.push import PushMessage, send_to_users
from app.modules.participants.models import Participant


async def push_draw_done(ctx: dict[str, Any], group_id: str) -> int:
    async with get_sessionmaker()() as session:
        group = await session.get(Group, uuid.UUID(group_id))
        if group is None:
            return 0
        user_ids = (
            await session.scalars(
                select(Participant.user_id).where(
                    Participant.group_id == group.id, Participant.left_at.is_(None)
                )
            )
        ).all()
        message = PushMessage(
            title="🎁 O sorteio saiu!",
            body=f"Toque para descobrir quem você tirou em “{group.title}”.",
            url=f"/groups/{group.id}?tab=draw",
            tag=f"draw-{group.id}",
        )
        return await send_to_users(session, user_ids, message)


async def push_chat_message(ctx: dict[str, Any], assignment_id: str, recipient_role: str) -> int:
    async with get_sessionmaker()() as session:
        assignment = await session.get(DrawAssignment, uuid.UUID(assignment_id))
        if assignment is None:
            return 0
        draw = await session.get(Draw, assignment.draw_id)
        if draw is None:
            return 0
        if recipient_role == "receiver":
            participant_id = crypto.decrypt_receiver(assignment.receiver_encrypted)
            title, thread = "🤫 Seu amigo secreto mandou uma mensagem", "santa"
        else:
            participant_id = assignment.giver_participant_id
            title, thread = "💬 Quem você tirou respondeu", "match"
        participant = await session.get(Participant, participant_id)
        if participant is None:
            return 0
        message = PushMessage(
            title=title,
            body="Toque para abrir o chat.",  # nunca o conteúdo: aparece na tela bloqueada
            url=f"/groups/{draw.group_id}?tab=chat",
            tag=f"chat-{assignment.id}-{thread}",
        )
        return await send_to_users(session, [participant.user_id], message)

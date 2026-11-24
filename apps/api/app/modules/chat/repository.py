import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chat.models import ChatMessage, SenderRole
from app.modules.draws.models import DrawAssignment


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def assignment_by_lookup(self, draw_id: uuid.UUID, lookup: str) -> DrawAssignment | None:
        stmt = select(DrawAssignment).where(
            DrawAssignment.draw_id == draw_id, DrawAssignment.receiver_lookup_hash == lookup
        )
        return await self.session.scalar(stmt)

    async def add(self, message: ChatMessage) -> ChatMessage:
        self.session.add(message)
        await self.session.flush()
        return message

    async def list(
        self,
        assignment_id: uuid.UUID,
        *,
        before: uuid.UUID | None,
        after: uuid.UUID | None,
        limit: int,
    ) -> list[ChatMessage]:
        stmt = select(ChatMessage).where(ChatMessage.assignment_id == assignment_id)
        if after is not None:
            # Polling: mensagens novas, em ordem cronológica.
            stmt = stmt.where(ChatMessage.id > after).order_by(ChatMessage.id).limit(limit)
            return list((await self.session.scalars(stmt)).all())
        if before is not None:
            stmt = stmt.where(ChatMessage.id < before)
        stmt = stmt.order_by(ChatMessage.id.desc()).limit(limit)
        return list(reversed((await self.session.scalars(stmt)).all()))

    async def last(self, assignment_id: uuid.UUID) -> ChatMessage | None:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.assignment_id == assignment_id)
            .order_by(ChatMessage.id.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def unread(self, assignment_id: uuid.UUID, from_role: SenderRole) -> int:
        stmt = select(func.count()).where(
            ChatMessage.assignment_id == assignment_id,
            ChatMessage.sender_role == from_role,
            ChatMessage.read_at.is_(None),
        )
        return int(await self.session.scalar(stmt) or 0)

    async def mark_read(
        self, assignment_id: uuid.UUID, from_role: SenderRole, now: datetime
    ) -> None:
        await self.session.execute(
            update(ChatMessage)
            .where(
                ChatMessage.assignment_id == assignment_id,
                ChatMessage.sender_role == from_role,
                ChatMessage.read_at.is_(None),
            )
            .values(read_at=now)
        )

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.participants.models import Participant


class ParticipantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, participant: Participant) -> Participant:
        self.session.add(participant)
        await self.session.flush()
        return participant

    async def get_by_user(self, group_id: uuid.UUID, user_id: uuid.UUID) -> Participant | None:
        stmt = select(Participant).where(
            Participant.group_id == group_id, Participant.user_id == user_id
        )
        return await self.session.scalar(stmt)

    async def get_by_id(self, participant_id: uuid.UUID) -> Participant | None:
        stmt = (
            select(Participant)
            .options(selectinload(Participant.user))
            .where(Participant.id == participant_id)
        )
        return await self.session.scalar(stmt)

    async def get_active(
        self, group_id: uuid.UUID, participant_id: uuid.UUID
    ) -> Participant | None:
        stmt = (
            select(Participant)
            .options(selectinload(Participant.user))
            .where(
                Participant.id == participant_id,
                Participant.group_id == group_id,
                Participant.left_at.is_(None),
            )
        )
        return await self.session.scalar(stmt)

    async def list_active(self, group_id: uuid.UUID) -> list[Participant]:
        stmt = (
            select(Participant)
            .options(selectinload(Participant.user))
            .where(Participant.group_id == group_id, Participant.left_at.is_(None))
            .order_by(Participant.joined_at, Participant.id)
        )
        return list((await self.session.scalars(stmt)).all())

    async def user_ids_by_participant(self, group_id: uuid.UUID) -> dict[uuid.UUID, uuid.UUID]:
        """Todos os participantes do grupo (inclusive quem saiu): participante → usuário."""
        stmt = select(Participant.id, Participant.user_id).where(Participant.group_id == group_id)
        return {pid: uid for pid, uid in (await self.session.execute(stmt)).all()}

    async def count_active(self, group_id: uuid.UUID) -> int:
        stmt = select(func.count()).where(
            Participant.group_id == group_id, Participant.left_at.is_(None)
        )
        return int(await self.session.scalar(stmt) or 0)

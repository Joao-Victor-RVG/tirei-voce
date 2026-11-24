import uuid

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.rules.models import BlockedPair, ExclusionCircle, ExclusionCircleMember


class RulesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_circles(self, group_id: uuid.UUID) -> list[ExclusionCircle]:
        stmt = (
            select(ExclusionCircle)
            .options(selectinload(ExclusionCircle.members))
            .where(ExclusionCircle.group_id == group_id)
            .order_by(ExclusionCircle.id)
        )
        return list((await self.session.scalars(stmt)).all())

    async def get_circle(self, group_id: uuid.UUID, circle_id: uuid.UUID) -> ExclusionCircle | None:
        stmt = (
            select(ExclusionCircle)
            .options(selectinload(ExclusionCircle.members))
            .where(ExclusionCircle.id == circle_id, ExclusionCircle.group_id == group_id)
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def add(self, obj: ExclusionCircle | BlockedPair) -> None:
        self.session.add(obj)
        await self.session.flush()

    async def delete(self, obj: ExclusionCircle | BlockedPair) -> None:
        await self.session.delete(obj)
        await self.session.flush()

    async def list_pairs(self, group_id: uuid.UUID) -> list[BlockedPair]:
        stmt = select(BlockedPair).where(BlockedPair.group_id == group_id).order_by(BlockedPair.id)
        return list((await self.session.scalars(stmt)).all())

    async def get_pair(self, group_id: uuid.UUID, pair_id: uuid.UUID) -> BlockedPair | None:
        stmt = select(BlockedPair).where(
            BlockedPair.id == pair_id, BlockedPair.group_id == group_id
        )
        return await self.session.scalar(stmt)

    async def find_pair(
        self, group_id: uuid.UUID, giver_id: uuid.UUID, receiver_id: uuid.UUID
    ) -> BlockedPair | None:
        stmt = select(BlockedPair).where(
            BlockedPair.group_id == group_id,
            BlockedPair.giver_participant_id == giver_id,
            BlockedPair.receiver_participant_id == receiver_id,
        )
        return await self.session.scalar(stmt)

    async def remove_participant(self, participant_id: uuid.UUID) -> None:
        """Quem sai do grupo deixa de aparecer em círculos e pares bloqueados."""
        await self.session.execute(
            delete(ExclusionCircleMember).where(
                ExclusionCircleMember.participant_id == participant_id
            )
        )
        await self.session.execute(
            delete(BlockedPair).where(
                or_(
                    BlockedPair.giver_participant_id == participant_id,
                    BlockedPair.receiver_participant_id == participant_id,
                )
            )
        )

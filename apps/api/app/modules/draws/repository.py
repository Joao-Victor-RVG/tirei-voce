import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.draws.models import Draw, DrawAssignment


class DrawRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def latest(self, group_id: uuid.UUID) -> Draw | None:
        stmt = select(Draw).where(Draw.group_id == group_id).order_by(Draw.version.desc()).limit(1)
        return await self.session.scalar(stmt)

    async def next_version(self, group_id: uuid.UUID) -> int:
        stmt = select(func.coalesce(func.max(Draw.version), 0)).where(Draw.group_id == group_id)
        return int(await self.session.scalar(stmt) or 0) + 1

    async def add(self, draw: Draw, assignments: list[DrawAssignment]) -> None:
        self.session.add(draw)
        await self.session.flush()
        self.session.add_all(assignments)
        await self.session.flush()

    async def gift_progress(self, draw_id: uuid.UUID) -> tuple[int, int]:
        stmt = select(
            func.count(DrawAssignment.gift_purchased_at), func.count(DrawAssignment.id)
        ).where(DrawAssignment.draw_id == draw_id)
        purchased, total = (await self.session.execute(stmt)).one()
        return int(purchased), int(total)

    async def assignment_by_lookup(self, draw_id: uuid.UUID, lookup: str) -> DrawAssignment | None:
        stmt = select(DrawAssignment).where(
            DrawAssignment.draw_id == draw_id, DrawAssignment.receiver_lookup_hash == lookup
        )
        return await self.session.scalar(stmt)

    async def count_assignments(self, draw_id: uuid.UUID) -> int:
        stmt = select(func.count()).where(DrawAssignment.draw_id == draw_id)
        return int(await self.session.scalar(stmt) or 0)

    async def assignments(self, draw_id: uuid.UUID) -> list[DrawAssignment]:
        stmt = select(DrawAssignment).where(DrawAssignment.draw_id == draw_id)
        return list((await self.session.scalars(stmt)).all())

    async def assignment_for_giver(
        self, draw_id: uuid.UUID, giver_participant_id: uuid.UUID
    ) -> DrawAssignment | None:
        stmt = select(DrawAssignment).where(
            DrawAssignment.draw_id == draw_id,
            DrawAssignment.giver_participant_id == giver_participant_id,
        )
        return await self.session.scalar(stmt)

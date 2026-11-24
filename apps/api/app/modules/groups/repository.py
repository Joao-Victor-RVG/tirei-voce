import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.groups.models import Group, GroupTheme
from app.modules.participants.models import Participant, ParticipantRole


def _active_count_subquery() -> object:
    return (
        select(func.count())
        .where(Participant.group_id == Group.id, Participant.left_at.is_(None))
        .correlate(Group)
        .scalar_subquery()
    )


class GroupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_themes(self) -> list[GroupTheme]:
        return list(
            (await self.session.scalars(select(GroupTheme).order_by(GroupTheme.slug))).all()
        )

    async def get_theme_by_slug(self, slug: str) -> GroupTheme | None:
        return await self.session.scalar(select(GroupTheme).where(GroupTheme.slug == slug))

    async def add(self, group: Group) -> Group:
        self.session.add(group)
        await self.session.flush()
        return group

    async def get(self, group_id: uuid.UUID, *, for_update: bool = False) -> Group | None:
        stmt = select(Group).where(Group.id == group_id)
        if for_update:
            # Trava só a linha do grupo (não as tabelas carregadas via selectinload).
            stmt = stmt.with_for_update(of=Group)
        stmt = stmt.options(selectinload(Group.theme), selectinload(Group.owner))
        return await self.session.scalar(stmt.execution_options(populate_existing=True))

    async def get_by_invite_code(self, code: str, *, for_update: bool = False) -> Group | None:
        stmt = select(Group).where(Group.invite_code == code)
        if for_update:
            stmt = stmt.with_for_update(of=Group)
        stmt = stmt.options(selectinload(Group.theme), selectinload(Group.owner))
        return await self.session.scalar(stmt.execution_options(populate_existing=True))

    async def invite_code_exists(self, code: str) -> bool:
        return bool(await self.session.scalar(select(Group.id).where(Group.invite_code == code)))

    async def list_for_user(
        self, user_id: uuid.UUID, *, cursor: uuid.UUID | None, limit: int
    ) -> list[tuple[Group, ParticipantRole, int]]:
        count = _active_count_subquery()
        stmt = (
            select(Group, Participant.role, count)  # type: ignore[call-overload]
            .join(Participant, Participant.group_id == Group.id)
            .options(selectinload(Group.theme))
            .where(Participant.user_id == user_id, Participant.left_at.is_(None))
            .order_by(Group.id.desc())
            .limit(limit)
        )
        if cursor is not None:
            stmt = stmt.where(Group.id < cursor)
        result = await self.session.execute(stmt)
        return [(group, role, int(count)) for group, role, count in result.all()]

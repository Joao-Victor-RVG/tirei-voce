import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.pagination import PageParams
from app.modules.admin.schemas import AdminMetrics, AdminUserOut, AdminUserPage, CountWithRecent
from app.modules.auth.repository import RefreshTokenRepository
from app.modules.chat.models import ChatMessage
from app.modules.draws.models import Draw, DrawAssignment
from app.modules.groups.models import Group, GroupStatus
from app.modules.notifications.models import PushSubscription
from app.modules.participants.models import Participant
from app.modules.users.models import User

logger = logging.getLogger(__name__)


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _count(self, *where: object, model: type, since: datetime | None = None) -> int:
        stmt = select(func.count()).select_from(model)
        for clause in where:
            stmt = stmt.where(clause)  # type: ignore[arg-type]
        if since is not None:
            stmt = stmt.where(model.created_at >= since)  # type: ignore[attr-defined]
        return int(await self.session.scalar(stmt) or 0)

    async def metrics(self) -> AdminMetrics:
        now = datetime.now(UTC)
        week = now - timedelta(days=7)
        by_status_rows = (
            await self.session.execute(select(Group.status, func.count()).group_by(Group.status))
        ).all()
        by_status = {status: 0 for status in GroupStatus} | {s: int(n) for s, n in by_status_rows}
        groups_total = sum(by_status.values())
        active_participants = await self._count(Participant.left_at.is_(None), model=Participant)
        return AdminMetrics(
            users=CountWithRecent(
                total=await self._count(model=User),
                last_7d=await self._count(model=User, since=week),
            ),
            users_verified=await self._count(User.email_verified_at.is_not(None), model=User),
            groups=CountWithRecent(
                total=groups_total, last_7d=await self._count(model=Group, since=week)
            ),
            groups_by_status=by_status,
            draws=CountWithRecent(
                total=await self._count(model=Draw),
                last_7d=await self._count(model=Draw, since=week),
            ),
            participants=active_participants,
            avg_group_size=round(active_participants / groups_total, 1) if groups_total else 0.0,
            gifts_purchased=await self._count(
                DrawAssignment.gift_purchased_at.is_not(None), model=DrawAssignment
            ),
            gifts_total=await self._count(model=DrawAssignment),
            chat_messages_7d=await self._count(model=ChatMessage, since=week),
            push_subscriptions=await self._count(model=PushSubscription),
            scheduled_draws_pending=await self._count(
                Group.draw_scheduled_at.is_not(None),
                Group.status.in_((GroupStatus.OPEN, GroupStatus.CLOSED)),
                model=Group,
            ),
            generated_at=now,
        )

    async def users(self, query: str | None, page: PageParams) -> AdminUserPage:
        groups = (
            select(func.count())
            .where(Participant.user_id == User.id, Participant.left_at.is_(None))
            .correlate(User)
            .scalar_subquery()
        )
        stmt = select(User, groups).order_by(User.id.desc()).limit(page.limit + 1)
        if query:
            like = f"%{query.strip().lower()}%"
            stmt = stmt.where(
                or_(func.lower(User.email).like(like), func.lower(User.name).like(like))
            )
        if page.cursor:
            stmt = stmt.where(User.id < page.cursor)
        rows = (await self.session.execute(stmt)).all()
        items = [
            AdminUserOut(
                id=u.id,
                name=u.name,
                email=u.email,
                email_verified=u.is_email_verified,
                is_active=u.is_active,
                is_admin=u.is_admin,
                groups=int(n),
                created_at=u.created_at,
            )
            for u, n in rows[: page.limit]
        ]
        return AdminUserPage(
            items=items, next_cursor=str(items[-1].id) if len(rows) > page.limit else None
        )

    async def set_active(self, admin: User, user_id: uuid.UUID, active: bool) -> AdminUserOut:
        if user_id == admin.id:
            raise ConflictError(
                "Você não pode desativar a própria conta.", code="cannot_change_self"
            )
        user = await self.session.get(User, user_id)
        if user is None:
            raise NotFoundError("Usuário não encontrado.", code="user_not_found")
        user.is_active = active
        if not active:
            await RefreshTokenRepository(self.session).revoke_all_for_user(
                user.id, datetime.now(UTC)
            )
        await self.session.commit()
        logger.info(
            "admin_user_active_changed",
            extra={"admin_id": str(admin.id), "user_id": str(user.id), "active": active},
        )
        page = await self.users(user.email, PageParams(limit=1))
        return page.items[0]

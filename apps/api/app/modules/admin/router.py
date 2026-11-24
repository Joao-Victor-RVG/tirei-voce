import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import NotFoundError
from app.core.pagination import PageParams, page_params
from app.modules.admin.schemas import AdminMetrics, AdminUserOut, AdminUserPage
from app.modules.admin.service import AdminService
from app.modules.auth.dependencies import CurrentUser
from app.modules.users.models import User


async def require_admin(user: CurrentUser) -> User:
    # 404 em vez de 403: não revela que a área existe.
    if not user.is_admin:
        raise NotFoundError()
    return user


AdminUser = Annotated[User, Depends(require_admin)]

router = APIRouter(prefix="/admin", tags=["admin"])


def get_admin_service(session: Annotated[AsyncSession, Depends(get_session)]) -> AdminService:
    return AdminService(session)


Service = Annotated[AdminService, Depends(get_admin_service)]


@router.get("/metrics", response_model=AdminMetrics)
async def metrics(_: AdminUser, service: Service) -> AdminMetrics:
    return await service.metrics()


@router.get("/users", response_model=AdminUserPage)
async def list_users(
    _: AdminUser,
    service: Service,
    page: Annotated[PageParams, Depends(page_params)],
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> AdminUserPage:
    return await service.users(q, page)


@router.post("/users/{user_id}/deactivate", response_model=AdminUserOut)
async def deactivate_user(user_id: uuid.UUID, admin: AdminUser, service: Service) -> AdminUserOut:
    return await service.set_active(admin, user_id, False)


@router.post("/users/{user_id}/activate", response_model=AdminUserOut)
async def activate_user(user_id: uuid.UUID, admin: AdminUser, service: Service) -> AdminUserOut:
    return await service.set_active(admin, user_id, True)

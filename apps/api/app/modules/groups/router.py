import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.db import get_session
from app.core.pagination import Page, PageParams, page_params
from app.modules.auth.dependencies import Client, CurrentUser, VerifiedUser
from app.modules.groups.models import GroupStatus
from app.modules.groups.schemas import (
    GroupCreate,
    GroupOut,
    GroupSummaryOut,
    GroupUpdate,
    InvitePreviewOut,
    JoinOut,
    ThemeOut,
)
from app.modules.groups.service import GroupService

router = APIRouter(tags=["groups"])

InviteCode = Annotated[str, Path(min_length=10, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")]


def get_group_service(session: Annotated[AsyncSession, Depends(get_session)]) -> GroupService:
    return GroupService(session)


Service = Annotated[GroupService, Depends(get_group_service)]


@router.get("/themes", response_model=list[ThemeOut])
async def list_themes(service: Service) -> list[ThemeOut]:
    return await service.list_themes()


@router.post("/groups", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
async def create_group(data: GroupCreate, user: VerifiedUser, service: Service) -> GroupOut:
    return await service.create(data, user)


@router.get("/groups", response_model=Page[GroupSummaryOut])
async def list_my_groups(
    user: CurrentUser, service: Service, page: Annotated[PageParams, Depends(page_params)]
) -> Page[GroupSummaryOut]:
    return await service.list_mine(user, page)


@router.get("/groups/{group_id}", response_model=GroupOut)
async def get_group(group_id: uuid.UUID, user: CurrentUser, service: Service) -> GroupOut:
    return await service.get(group_id, user)


@router.patch("/groups/{group_id}", response_model=GroupOut)
async def update_group(
    group_id: uuid.UUID, data: GroupUpdate, user: CurrentUser, service: Service
) -> GroupOut:
    return await service.update(group_id, user, data)


@router.post("/groups/{group_id}/open", response_model=GroupOut)
async def open_group(group_id: uuid.UUID, user: CurrentUser, service: Service) -> GroupOut:
    return await service.change_status(group_id, user, GroupStatus.OPEN)


@router.post("/groups/{group_id}/close", response_model=GroupOut)
async def close_group(group_id: uuid.UUID, user: CurrentUser, service: Service) -> GroupOut:
    return await service.change_status(group_id, user, GroupStatus.CLOSED)


@router.post("/groups/{group_id}/finish", response_model=GroupOut)
async def finish_group(group_id: uuid.UUID, user: CurrentUser, service: Service) -> GroupOut:
    return await service.change_status(group_id, user, GroupStatus.FINISHED)


@router.post("/groups/{group_id}/invite-code/regenerate", response_model=GroupOut)
async def regenerate_invite_code(
    group_id: uuid.UUID, user: CurrentUser, service: Service
) -> GroupOut:
    return await service.regenerate_invite_code(group_id, user)


@router.get("/invites/{code}", response_model=InvitePreviewOut, tags=["invites"])
async def invite_preview(code: InviteCode, service: Service, client: Client) -> InvitePreviewOut:
    await rate_limit.hit("invite_preview:ip", client.ip or "-", limit=60, window_seconds=60)
    return await service.invite_preview(code)


@router.post("/invites/{code}/join", response_model=JoinOut, tags=["invites"])
async def join_group(
    code: InviteCode, user: VerifiedUser, service: Service, client: Client
) -> JoinOut:
    await rate_limit.hit("invite_join:ip", client.ip or "-", limit=30, window_seconds=300)
    await rate_limit.hit("invite_join:user", str(user.id), limit=20, window_seconds=300)
    return await service.join(code, user)

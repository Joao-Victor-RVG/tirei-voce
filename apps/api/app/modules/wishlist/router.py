import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.auth.dependencies import CurrentUser
from app.modules.wishlist.schemas import (
    PreferencesIn,
    PreferencesOut,
    WishlistItemCreate,
    WishlistItemOut,
    WishlistItemUpdate,
)
from app.modules.wishlist.service import WishlistService

router = APIRouter(prefix="/groups/{group_id}/me", tags=["wishlist"])


def get_wishlist_service(session: Annotated[AsyncSession, Depends(get_session)]) -> WishlistService:
    return WishlistService(session)


Service = Annotated[WishlistService, Depends(get_wishlist_service)]


@router.get("/wishlist", response_model=list[WishlistItemOut])
async def list_items(
    group_id: uuid.UUID, user: CurrentUser, service: Service
) -> list[WishlistItemOut]:
    return await service.list_items(group_id, user)


@router.post("/wishlist", response_model=WishlistItemOut, status_code=status.HTTP_201_CREATED)
async def add_item(
    group_id: uuid.UUID, data: WishlistItemCreate, user: CurrentUser, service: Service
) -> WishlistItemOut:
    return await service.add_item(group_id, user, data)


@router.patch("/wishlist/{item_id}", response_model=WishlistItemOut)
async def update_item(
    group_id: uuid.UUID,
    item_id: uuid.UUID,
    data: WishlistItemUpdate,
    user: CurrentUser,
    service: Service,
) -> WishlistItemOut:
    return await service.update_item(group_id, item_id, user, data)


@router.delete("/wishlist/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    group_id: uuid.UUID, item_id: uuid.UUID, user: CurrentUser, service: Service
) -> None:
    await service.delete_item(group_id, item_id, user)


@router.get("/preferences", response_model=PreferencesOut)
async def get_preferences(
    group_id: uuid.UUID, user: CurrentUser, service: Service
) -> PreferencesOut:
    return await service.get_preferences(group_id, user)


@router.put("/preferences", response_model=PreferencesOut)
async def put_preferences(
    group_id: uuid.UUID, data: PreferencesIn, user: CurrentUser, service: Service
) -> PreferencesOut:
    return await service.put_preferences(group_id, user, data)

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.auth.dependencies import CurrentUser
from app.modules.rules.schemas import (
    BlockedPairCreate,
    BlockedPairOut,
    BlockedPairUpdate,
    CircleCreate,
    CircleMemberIn,
    CircleOut,
    CircleUpdate,
)
from app.modules.rules.service import RulesService

router = APIRouter(prefix="/groups/{group_id}", tags=["rules"])


def get_rules_service(session: Annotated[AsyncSession, Depends(get_session)]) -> RulesService:
    return RulesService(session)


Service = Annotated[RulesService, Depends(get_rules_service)]


@router.get("/exclusion-circles", response_model=list[CircleOut])
async def list_circles(group_id: uuid.UUID, user: CurrentUser, service: Service) -> list[CircleOut]:
    return await service.list_circles(group_id, user)


@router.post("/exclusion-circles", response_model=CircleOut, status_code=status.HTTP_201_CREATED)
async def create_circle(
    group_id: uuid.UUID, data: CircleCreate, user: CurrentUser, service: Service
) -> CircleOut:
    return await service.create_circle(group_id, user, data)


@router.patch("/exclusion-circles/{circle_id}", response_model=CircleOut)
async def update_circle(
    group_id: uuid.UUID,
    circle_id: uuid.UUID,
    data: CircleUpdate,
    user: CurrentUser,
    service: Service,
) -> CircleOut:
    return await service.update_circle(group_id, circle_id, user, data)


@router.delete("/exclusion-circles/{circle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_circle(
    group_id: uuid.UUID, circle_id: uuid.UUID, user: CurrentUser, service: Service
) -> None:
    await service.delete_circle(group_id, circle_id, user)


@router.post("/exclusion-circles/{circle_id}/members", response_model=CircleOut)
async def add_circle_member(
    group_id: uuid.UUID,
    circle_id: uuid.UUID,
    data: CircleMemberIn,
    user: CurrentUser,
    service: Service,
) -> CircleOut:
    return await service.add_circle_member(group_id, circle_id, data.participant_id, user)


@router.delete("/exclusion-circles/{circle_id}/members/{participant_id}", response_model=CircleOut)
async def remove_circle_member(
    group_id: uuid.UUID,
    circle_id: uuid.UUID,
    participant_id: uuid.UUID,
    user: CurrentUser,
    service: Service,
) -> CircleOut:
    return await service.remove_circle_member(group_id, circle_id, participant_id, user)


@router.get("/blocked-pairs", response_model=list[BlockedPairOut])
async def list_pairs(
    group_id: uuid.UUID, user: CurrentUser, service: Service
) -> list[BlockedPairOut]:
    return await service.list_pairs(group_id, user)


@router.post("/blocked-pairs", response_model=BlockedPairOut, status_code=status.HTTP_201_CREATED)
async def create_pair(
    group_id: uuid.UUID, data: BlockedPairCreate, user: CurrentUser, service: Service
) -> BlockedPairOut:
    return await service.create_pair(group_id, user, data)


@router.patch("/blocked-pairs/{pair_id}", response_model=BlockedPairOut)
async def update_pair(
    group_id: uuid.UUID,
    pair_id: uuid.UUID,
    data: BlockedPairUpdate,
    user: CurrentUser,
    service: Service,
) -> BlockedPairOut:
    return await service.update_pair(group_id, pair_id, user, data)


@router.delete("/blocked-pairs/{pair_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pair(
    group_id: uuid.UUID, pair_id: uuid.UUID, user: CurrentUser, service: Service
) -> None:
    await service.delete_pair(group_id, pair_id, user)

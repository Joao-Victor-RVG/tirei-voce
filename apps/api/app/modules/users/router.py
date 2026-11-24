from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.auth.dependencies import CurrentUser
from app.modules.users.schemas import MeOut, MeUpdate
from app.modules.users.service import UserService

router = APIRouter(tags=["users"])


def get_user_service(session: Annotated[AsyncSession, Depends(get_session)]) -> UserService:
    return UserService(session)


@router.get("/me", response_model=MeOut)
async def get_me(user: CurrentUser) -> MeOut:
    return MeOut.from_user(user)


@router.patch("/me", response_model=MeOut)
async def update_me(
    data: MeUpdate,
    user: CurrentUser,
    service: Annotated[UserService, Depends(get_user_service)],
) -> MeOut:
    return MeOut.from_user(await service.update_me(user, data))

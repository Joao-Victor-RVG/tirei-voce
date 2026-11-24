from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.auth.dependencies import CurrentUser
from app.modules.notifications.schemas import PushConfigOut, PushSubscriptionIn
from app.modules.notifications.subscriptions import PushSubscriptionService

router = APIRouter(prefix="/push", tags=["notifications"])


def get_push_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PushSubscriptionService:
    return PushSubscriptionService(session)


Service = Annotated[PushSubscriptionService, Depends(get_push_service)]
Endpoint = Annotated[str, Query(max_length=2048)]


@router.get("/config", response_model=PushConfigOut)
async def push_config(
    user: CurrentUser, service: Service, endpoint: Endpoint | None = None
) -> PushConfigOut:
    return await service.config(user, endpoint)


@router.post("/subscriptions", status_code=status.HTTP_204_NO_CONTENT)
async def subscribe(
    data: PushSubscriptionIn, request: Request, user: CurrentUser, service: Service
) -> None:
    await service.subscribe(user, data, request.headers.get("user-agent"))


@router.delete("/subscriptions", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(endpoint: Endpoint, user: CurrentUser, service: Service) -> None:
    await service.unsubscribe(user, endpoint)

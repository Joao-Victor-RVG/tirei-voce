import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.auth.dependencies import CurrentUser
from app.modules.chat.schemas import (
    ChatMessageIn,
    ChatMessageOut,
    ChatMessagePage,
    ChatThreadSummary,
    Thread,
)
from app.modules.chat.service import ChatService

router = APIRouter(prefix="/groups/{group_id}/chats", tags=["chat"])


def get_chat_service(session: Annotated[AsyncSession, Depends(get_session)]) -> ChatService:
    return ChatService(session)


Service = Annotated[ChatService, Depends(get_chat_service)]


@router.get("", response_model=list[ChatThreadSummary])
async def list_threads(
    group_id: uuid.UUID, user: CurrentUser, service: Service
) -> list[ChatThreadSummary]:
    """As duas conversas do usuário: com quem ele tirou e com quem o tirou (anônima)."""
    return await service.threads(group_id, user)


@router.get("/{thread}/messages", response_model=ChatMessagePage)
async def list_messages(
    group_id: uuid.UUID,
    thread: Thread,
    user: CurrentUser,
    service: Service,
    before: Annotated[uuid.UUID | None, Query(description="Página anterior (mais antigas)")] = None,
    after: Annotated[uuid.UUID | None, Query(description="Polling: só as mais novas")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> ChatMessagePage:
    return await service.messages(group_id, user, thread, before=before, after=after, limit=limit)


@router.post(
    "/{thread}/messages", response_model=ChatMessageOut, status_code=status.HTTP_201_CREATED
)
async def send_message(
    group_id: uuid.UUID, thread: Thread, data: ChatMessageIn, user: CurrentUser, service: Service
) -> ChatMessageOut:
    return await service.send(group_id, user, thread, data.body)


@router.post("/{thread}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    group_id: uuid.UUID, thread: Thread, user: CurrentUser, service: Service
) -> None:
    await service.mark_read(group_id, user, thread)

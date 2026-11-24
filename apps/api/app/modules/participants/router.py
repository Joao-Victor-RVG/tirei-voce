import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.auth.dependencies import CurrentUser
from app.modules.participants.schemas import ParticipantOut
from app.modules.participants.service import ParticipantService

router = APIRouter(prefix="/groups/{group_id}", tags=["participants"])


def get_participant_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ParticipantService:
    return ParticipantService(session)


Service = Annotated[ParticipantService, Depends(get_participant_service)]


@router.get("/participants", response_model=list[ParticipantOut])
async def list_participants(
    group_id: uuid.UUID, user: CurrentUser, service: Service
) -> list[ParticipantOut]:
    """Lista completa (limitada por max_participants, até 200), em ordem de entrada."""
    return await service.list(group_id, user)


@router.delete("/participants/{participant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_participant(
    group_id: uuid.UUID, participant_id: uuid.UUID, user: CurrentUser, service: Service
) -> None:
    await service.remove(group_id, participant_id, user)


@router.post("/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_group(group_id: uuid.UUID, user: CurrentUser, service: Service) -> None:
    await service.leave(group_id, user)

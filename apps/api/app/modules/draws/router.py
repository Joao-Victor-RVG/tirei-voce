import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.auth.dependencies import CurrentUser
from app.modules.draws.schemas import (
    DrawOut,
    DrawValidationOut,
    GiftProgressOut,
    GiftStatusIn,
    GiftStatusOut,
    MyMatchOut,
    MySantaOut,
)
from app.modules.draws.service import DrawService

router = APIRouter(prefix="/groups/{group_id}", tags=["draws"])


def get_draw_service(session: Annotated[AsyncSession, Depends(get_session)]) -> DrawService:
    return DrawService(session)


Service = Annotated[DrawService, Depends(get_draw_service)]


@router.post("/draw/validate", response_model=DrawValidationOut)
async def validate_draw(
    group_id: uuid.UUID, user: CurrentUser, service: Service
) -> DrawValidationOut:
    return await service.validate(group_id, user)


@router.post("/draw", response_model=DrawOut)
async def execute_draw(
    group_id: uuid.UUID,
    user: CurrentUser,
    service: Service,
    idempotency_key: Annotated[str | None, Header(max_length=128)] = None,
) -> DrawOut:
    return await service.execute(group_id, user, idempotency_key)


@router.get("/my-match", response_model=MyMatchOut)
async def my_match(group_id: uuid.UUID, user: CurrentUser, service: Service) -> MyMatchOut:
    """O único endpoint que revela um par: o amigo secreto de quem está logado."""
    return await service.my_match(group_id, user)


@router.put("/my-match/gift", response_model=GiftStatusOut)
async def set_gift_status(
    group_id: uuid.UUID, data: GiftStatusIn, user: CurrentUser, service: Service
) -> GiftStatusOut:
    return await service.set_gift_purchased(group_id, user, data.purchased)


@router.get("/gift-progress", response_model=GiftProgressOut)
async def gift_progress(
    group_id: uuid.UUID, user: CurrentUser, service: Service
) -> GiftProgressOut:
    """Para a organização: quantos já compraram, sem dizer quem."""
    return await service.gift_progress(group_id, user)


@router.get("/my-santa", response_model=MySantaOut)
async def my_santa(group_id: uuid.UUID, user: CurrentUser, service: Service) -> MySantaOut:
    """Revelação: a partir do horário do evento, mostra quem tirou o usuário (só isso)."""
    return await service.my_santa(group_id, user, datetime.now(UTC))

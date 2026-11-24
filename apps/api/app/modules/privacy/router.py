from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.db import get_session
from app.modules.auth.cookies import clear_auth_cookies
from app.modules.auth.dependencies import CurrentUser
from app.modules.privacy.schemas import DeleteAccountIn, DeleteAccountOut
from app.modules.privacy.service import PrivacyService

router = APIRouter(prefix="/me", tags=["privacy"])


def get_privacy_service(session: Annotated[AsyncSession, Depends(get_session)]) -> PrivacyService:
    return PrivacyService(session)


Service = Annotated[PrivacyService, Depends(get_privacy_service)]


@router.get("/export", response_model=dict[str, Any])
async def export_my_data(user: CurrentUser, service: Service) -> JSONResponse:
    """Todos os dados pessoais do usuário (LGPD, art. 18), em JSON para download."""
    await rate_limit.hit("export:user", str(user.id), limit=5, window_seconds=3600)
    data = jsonable_encoder(await service.export(user))
    return JSONResponse(
        data, headers={"Content-Disposition": 'attachment; filename="tirei-voce-meus-dados.json"'}
    )


@router.post("/delete", response_model=DeleteAccountOut)
async def delete_my_account(
    data: DeleteAccountIn, user: CurrentUser, service: Service, response: Response
) -> DeleteAccountOut:
    await rate_limit.hit("delete:user", str(user.id), limit=5, window_seconds=900)
    mode = await service.delete_account(user, data)
    clear_auth_cookies(response)
    return DeleteAccountOut(mode=mode)

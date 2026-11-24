from fastapi import APIRouter, Request, Response, status

from app.core import rate_limit
from app.modules.auth.cookies import (
    CSRF_COOKIE,
    REFRESH_COOKIE,
    clear_auth_cookies,
    set_auth_cookies,
    set_csrf_cookie,
)
from app.modules.auth.dependencies import AuthServiceDep, Client
from app.modules.auth.schemas import CsrfOut, LoginIn, RegisterIn
from app.modules.auth.service import InvalidRefreshTokenError
from app.modules.users.schemas import MeOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/csrf", response_model=CsrfOut)
async def csrf(request: Request, response: Response) -> CsrfOut:
    token = set_csrf_cookie(response, request.cookies.get(CSRF_COOKIE))
    return CsrfOut(csrf_token=token)


@router.post("/register", response_model=MeOut, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterIn, response: Response, service: AuthServiceDep, client: Client
) -> MeOut:
    await rate_limit.hit("register:ip", client.ip or "-", limit=10, window_seconds=3600)
    user, tokens = await service.register(data, client)
    set_auth_cookies(response, tokens)
    return MeOut.from_user(user)


@router.post("/login", response_model=MeOut)
async def login(
    data: LoginIn, response: Response, service: AuthServiceDep, client: Client
) -> MeOut:
    await rate_limit.hit("login:ip", client.ip or "-", limit=30, window_seconds=300)
    await rate_limit.hit("login:email", data.email, limit=10, window_seconds=900)
    user, tokens = await service.login(data, client)
    set_auth_cookies(response, tokens)
    return MeOut.from_user(user)


@router.post("/refresh", response_model=MeOut)
async def refresh(
    request: Request, response: Response, service: AuthServiceDep, client: Client
) -> MeOut:
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise InvalidRefreshTokenError()
    user, tokens = await service.refresh(raw, client)
    set_auth_cookies(response, tokens)
    return MeOut.from_user(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, service: AuthServiceDep) -> None:
    await service.logout(request.cookies.get(REFRESH_COOKIE))
    clear_auth_cookies(response)

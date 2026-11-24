from fastapi import APIRouter, Request, Response, status

from app.core import rate_limit
from app.modules.auth.cookies import (
    CSRF_COOKIE,
    REFRESH_COOKIE,
    clear_auth_cookies,
    set_auth_cookies,
    set_csrf_cookie,
)
from app.modules.auth.dependencies import AuthServiceDep, Client, CurrentUser
from app.modules.auth.schemas import (
    CsrfOut,
    ForgotPasswordIn,
    LoginIn,
    MessageOut,
    RegisterIn,
    ResetPasswordIn,
    TokenIn,
)
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


@router.post("/verify-email", response_model=MeOut)
async def verify_email(data: TokenIn, service: AuthServiceDep, client: Client) -> MeOut:
    await rate_limit.hit("verify:ip", client.ip or "-", limit=30, window_seconds=900)
    return MeOut.from_user(await service.verify_email(data.token))


@router.post("/resend-verification", response_model=MessageOut, status_code=202)
async def resend_verification(user: CurrentUser, service: AuthServiceDep) -> MessageOut:
    await rate_limit.hit("resend:user", str(user.id), limit=3, window_seconds=900)
    await service.resend_verification(user)
    return MessageOut(message="Se o seu e-mail ainda não foi confirmado, enviamos um novo link.")


@router.post("/forgot-password", response_model=MessageOut, status_code=202)
async def forgot_password(
    data: ForgotPasswordIn, service: AuthServiceDep, client: Client
) -> MessageOut:
    await rate_limit.hit("forgot:ip", client.ip or "-", limit=10, window_seconds=900)
    await rate_limit.hit("forgot:email", data.email, limit=3, window_seconds=900)
    await service.forgot_password(data.email)
    return MessageOut(message="Se o e-mail existir, enviaremos um link para redefinir a senha.")


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    data: ResetPasswordIn, response: Response, service: AuthServiceDep, client: Client
) -> None:
    await rate_limit.hit("reset:ip", client.ip or "-", limit=20, window_seconds=900)
    await service.reset_password(data.token, data.password)
    clear_auth_cookies(response)

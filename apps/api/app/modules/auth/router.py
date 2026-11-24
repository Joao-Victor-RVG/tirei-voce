from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from app.core import rate_limit
from app.core.config import get_settings
from app.core.errors import AppError
from app.modules.auth.cookies import (
    CSRF_COOKIE,
    REFRESH_COOKIE,
    clear_auth_cookies,
    set_auth_cookies,
    set_csrf_cookie,
)
from app.modules.auth.dependencies import AuthServiceDep, Client, CurrentUser
from app.modules.auth.google import (
    STATE_TTL_SECONDS,
    GoogleAuthError,
    GoogleOAuthClient,
    OAuthStateStore,
    new_pending_login,
    safe_next_path,
)
from app.modules.auth.schemas import (
    AuthConfigOut,
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

OAUTH_COOKIE = "tv_oauth"
OAUTH_COOKIE_PATH = "/api/v1/auth/google"


def get_google_client() -> GoogleOAuthClient | None:
    settings = get_settings()
    return GoogleOAuthClient(settings) if settings.google_enabled else None


@router.get("/config", response_model=AuthConfigOut)
async def auth_config() -> AuthConfigOut:
    return AuthConfigOut(google_enabled=get_settings().google_enabled)


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


def _frontend_redirect(path: str) -> RedirectResponse:
    return RedirectResponse(f"{get_settings().frontend_url}{path}", status_code=302)


def _login_error_redirect(code: str) -> RedirectResponse:
    return _frontend_redirect(f"/login?{urlencode({'error': code})}")


@router.get("/google/start", response_class=RedirectResponse, status_code=302)
async def google_start(
    client: Client, next: Annotated[str | None, Query(max_length=512)] = None
) -> RedirectResponse:
    google = get_google_client()
    if google is None:
        return _login_error_redirect("google_disabled")
    await rate_limit.hit("google:ip", client.ip or "-", limit=30, window_seconds=300)
    state, pending = new_pending_login(safe_next_path(next))
    await OAuthStateStore().save(state, pending)
    response = RedirectResponse(
        google.authorization_url(state, pending.code_verifier, pending.nonce), status_code=302
    )
    # Amarra o state a este navegador (evita login CSRF).
    settings = get_settings()
    response.set_cookie(
        OAUTH_COOKIE,
        state,
        max_age=STATE_TTL_SECONDS,
        path=OAUTH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain,
    )
    return response


@router.get("/google/callback", response_class=RedirectResponse, status_code=302)
async def google_callback(
    request: Request,
    service: AuthServiceDep,
    client: Client,
    google: Annotated[GoogleOAuthClient | None, Depends(get_google_client)],
    code: Annotated[str | None, Query(max_length=2048)] = None,
    state: Annotated[str | None, Query(max_length=256)] = None,
) -> RedirectResponse:
    cookie_state = request.cookies.get(OAUTH_COOKIE)
    pending = await OAuthStateStore().pop(state) if state else None
    try:
        if google is None:
            raise GoogleAuthError(code="google_disabled")
        if not code or not state or not cookie_state or cookie_state != state or not pending:
            raise GoogleAuthError()
        id_token = await google.exchange_code(code, pending.code_verifier)
        identity = await google.verify_id_token(id_token, pending.nonce)
        _, tokens = await service.login_with_google(identity, client)
    except AppError as exc:
        response = _login_error_redirect(exc.code)
    else:
        response = _frontend_redirect(pending.next_path)
        set_auth_cookies(response, tokens)
    response.delete_cookie(
        OAUTH_COOKIE, path=OAUTH_COOKIE_PATH, domain=get_settings().cookie_domain
    )
    return response

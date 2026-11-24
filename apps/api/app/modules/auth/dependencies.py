from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token, tokens_match
from app.modules.auth.cookies import ACCESS_COOKIE, CSRF_COOKIE, CSRF_HEADER
from app.modules.auth.service import AuthService, ClientInfo
from app.modules.notifications.service import EmailOutbox, get_email_outbox
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


async def verify_csrf(request: Request) -> None:
    if request.method in _SAFE_METHODS:
        return
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get(CSRF_HEADER)
    if not cookie or not header or not tokens_match(cookie, header):
        raise ForbiddenError(
            "Sessão de segurança inválida. Recarregue a página e tente novamente.",
            code="csrf_failed",
        )


async def get_current_user(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> User:
    token = request.cookies.get(ACCESS_COOKIE)
    user_id = decode_access_token(token) if token else None
    if user_id is None:
        raise UnauthorizedError()
    user = await UserRepository(session).get(user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_verified_user(user: CurrentUser) -> User:
    if not user.is_email_verified:
        raise ForbiddenError(
            "Confirme seu e-mail para continuar. Enviamos um link para a sua caixa de entrada.",
            code="email_not_verified",
        )
    return user


VerifiedUser = Annotated[User, Depends(get_verified_user)]


def get_client_info(request: Request) -> ClientInfo:
    return ClientInfo(
        user_agent=request.headers.get("user-agent"),
        ip=request.client.host if request.client else None,
    )


def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    outbox: Annotated[EmailOutbox, Depends(get_email_outbox)],
) -> AuthService:
    return AuthService(session, outbox)


Client = Annotated[ClientInfo, Depends(get_client_info)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]

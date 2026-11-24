import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    generate_token,
    hash_password,
    hash_token,
    password_needs_rehash,
    verify_password,
)
from app.modules.auth.models import RefreshToken
from app.modules.auth.passwords import validate_password
from app.modules.auth.repository import RefreshTokenRepository
from app.modules.auth.schemas import LoginIn, RegisterIn
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClientInfo:
    user_agent: str | None
    ip: str | None


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    refresh_expires_at: datetime


class InvalidCredentialsError(UnauthorizedError):
    code = "invalid_credentials"
    message = "E-mail ou senha incorretos."


class InvalidRefreshTokenError(UnauthorizedError):
    code = "invalid_refresh_token"
    message = "Sua sessão expirou. Faça login novamente."


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)

    async def register(self, data: RegisterIn, client: ClientInfo) -> tuple[User, TokenPair]:
        email = data.email.strip().lower()
        validate_password(data.password, email=email)
        if await self.users.get_by_email(email):
            raise ConflictError("Este e-mail já está cadastrado.", code="email_taken")
        user = User(name=data.name, email=email, password_hash=hash_password(data.password))
        try:
            await self.users.add(user)
        except IntegrityError as exc:  # corrida entre dois cadastros com o mesmo e-mail
            await self.session.rollback()
            raise ConflictError("Este e-mail já está cadastrado.", code="email_taken") from exc
        tokens = await self._issue_tokens(user, client)
        await self.session.commit()
        logger.info("user_registered", extra={"user_id": str(user.id)})
        return user, tokens

    async def login(self, data: LoginIn, client: ClientInfo) -> tuple[User, TokenPair]:
        user = await self.users.get_by_email(data.email)
        password_hash = user.password_hash if user else None
        if not verify_password(data.password, password_hash) or user is None:
            raise InvalidCredentialsError()
        if not user.is_active:
            raise UnauthorizedError("Esta conta está desativada.", code="account_disabled")
        if password_hash and password_needs_rehash(password_hash):
            user.password_hash = hash_password(data.password)
        tokens = await self._issue_tokens(user, client)
        await self.session.commit()
        return user, tokens

    async def login_user(self, user: User, client: ClientInfo) -> TokenPair:
        """Cria uma sessão para um usuário já autenticado por outro meio (ex.: Google)."""
        tokens = await self._issue_tokens(user, client)
        await self.session.commit()
        return tokens

    async def refresh(self, raw_token: str, client: ClientInfo) -> tuple[User, TokenPair]:
        now = datetime.now(UTC)
        stored = await self.refresh_tokens.get_by_hash_for_update(hash_token(raw_token))
        if stored is None:
            raise InvalidRefreshTokenError()
        if stored.revoked_at is not None:
            # Token já usado: provável roubo. Derruba todas as sessões do usuário.
            await self.refresh_tokens.revoke_all_for_user(stored.user_id, now)
            await self.session.commit()
            logger.warning("refresh_token_reuse_detected", extra={"user_id": str(stored.user_id)})
            raise InvalidRefreshTokenError()
        if stored.expires_at <= now:
            raise InvalidRefreshTokenError()
        user = await self.users.get(stored.user_id)
        if user is None or not user.is_active:
            raise InvalidRefreshTokenError()
        stored.revoked_at = now
        tokens = await self._issue_tokens(user, client)
        await self.session.commit()
        return user, tokens

    async def logout(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        stored = await self.refresh_tokens.get_by_hash_for_update(hash_token(raw_token))
        if stored is not None and stored.revoked_at is None:
            stored.revoked_at = datetime.now(UTC)
            await self.session.commit()

    async def _issue_tokens(self, user: User, client: ClientInfo) -> TokenPair:
        settings = get_settings()
        raw_refresh = generate_token()
        expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days)
        await self.refresh_tokens.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_token(raw_refresh),
                expires_at=expires_at,
                user_agent=(client.user_agent or "")[:512] or None,
                ip=client.ip,
            )
        )
        return TokenPair(create_access_token(user.id), raw_refresh, expires_at)

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    generate_token,
    hash_password,
    hash_token,
    password_needs_rehash,
    verify_password,
)
from app.modules.auth.google import GoogleIdentity
from app.modules.auth.models import EmailToken, EmailTokenPurpose, RefreshToken
from app.modules.auth.passwords import validate_password
from app.modules.auth.repository import EmailTokenRepository, RefreshTokenRepository
from app.modules.auth.schemas import LoginIn, RegisterIn
from app.modules.notifications import templates
from app.modules.notifications.service import EmailOutbox
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


class InvalidEmailTokenError(AppError):
    code = "invalid_token"
    message = "Este link é inválido ou expirou. Peça um novo."


class AuthService:
    def __init__(self, session: AsyncSession, outbox: EmailOutbox) -> None:
        self.session = session
        self.outbox = outbox
        self.users = UserRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)
        self.email_tokens = EmailTokenRepository(session)

    async def register(self, data: RegisterIn, client: ClientInfo) -> tuple[User, TokenPair]:
        email = data.email.strip().lower()
        validate_password(data.password, email=email)
        if await self.users.get_by_email(email):
            raise ConflictError("Este e-mail já está cadastrado.", code="email_taken")
        user = User(name=data.name, email=email, password_hash=hash_password(data.password))
        if get_settings().auto_verify_emails:  # modo teste: dispensa a confirmação
            user.email_verified_at = datetime.now(UTC)
        try:
            await self.users.add(user)
        except IntegrityError as exc:  # corrida entre dois cadastros com o mesmo e-mail
            await self.session.rollback()
            raise ConflictError("Este e-mail já está cadastrado.", code="email_taken") from exc
        tokens = await self._issue_tokens(user, client)
        if user.is_email_verified:
            await self.session.commit()
        else:
            raw_verify = await self._create_email_token(user, EmailTokenPurpose.VERIFY_EMAIL)
            await self.session.commit()
            await self._send_verification(user, raw_verify)
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

    async def login_with_google(
        self, identity: GoogleIdentity, client: ClientInfo
    ) -> tuple[User, TokenPair]:
        now = datetime.now(UTC)
        user = await self.users.get_by_google_sub(identity.sub)
        if user is None:
            user = await self.users.get_by_email(identity.email)
            if user is not None:
                if user.google_sub is not None:  # e-mail já vinculado a outra conta Google
                    raise UnauthorizedError(
                        "Este e-mail já está vinculado a outra conta Google.",
                        code="google_account_conflict",
                    )
                if not user.is_email_verified:
                    # Conta com senha nunca verificada: quem criou pode não ser o dono do e-mail.
                    # O Google provou a posse, então removemos a senha e as sessões existentes.
                    user.password_hash = None
                    await self.refresh_tokens.revoke_all_for_user(user.id, now)
                user.google_sub = identity.sub
                user.email_verified_at = user.email_verified_at or now
                user.avatar_url = user.avatar_url or identity.picture
                logger.info("google_account_linked", extra={"user_id": str(user.id)})
            else:
                user = await self.users.add(
                    User(
                        name=identity.name,
                        email=identity.email,
                        google_sub=identity.sub,
                        email_verified_at=now,
                        avatar_url=identity.picture,
                    )
                )
                logger.info("user_registered", extra={"user_id": str(user.id), "via": "google"})
        if not user.is_active:
            raise UnauthorizedError("Esta conta está desativada.", code="account_disabled")
        tokens = await self._issue_tokens(user, client)
        await self.session.commit()
        return user, tokens

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

    # --- Verificação de e-mail ---

    async def resend_verification(self, user: User) -> None:
        if user.is_email_verified:
            return
        raw = await self._create_email_token(user, EmailTokenPurpose.VERIFY_EMAIL)
        await self.session.commit()
        await self._send_verification(user, raw)

    async def verify_email(self, raw_token: str) -> User:
        token = await self._consume_email_token(raw_token, EmailTokenPurpose.VERIFY_EMAIL)
        user = await self.users.get(token.user_id)
        if user is None:
            raise InvalidEmailTokenError()
        if user.email_verified_at is None:
            user.email_verified_at = datetime.now(UTC)
        await self.session.commit()
        return user

    # --- Reset de senha ---

    async def forgot_password(self, email: str) -> None:
        """Sempre "funciona" para quem chama: não revela se o e-mail existe."""
        user = await self.users.get_by_email(email)
        if user is None or not user.is_active:
            return
        raw = await self._create_email_token(user, EmailTokenPurpose.RESET_PASSWORD)
        await self.session.commit()
        url = f"{get_settings().frontend_url}/reset-password?token={raw}"
        await self.outbox.send(templates.reset_password(user.email, user.name, url))

    async def reset_password(self, raw_token: str, new_password: str) -> None:
        token = await self._consume_email_token(raw_token, EmailTokenPurpose.RESET_PASSWORD)
        user = await self.users.get(token.user_id)
        if user is None or not user.is_active:
            raise InvalidEmailTokenError()
        validate_password(new_password, email=user.email)
        now = datetime.now(UTC)
        user.password_hash = hash_password(new_password)
        # Quem recebeu o link no e-mail provou que é dono dele.
        user.email_verified_at = user.email_verified_at or now
        await self.refresh_tokens.revoke_all_for_user(user.id, now)
        await self.session.commit()
        logger.info("password_reset", extra={"user_id": str(user.id)})

    # --- Internos ---

    async def _create_email_token(self, user: User, purpose: EmailTokenPurpose) -> str:
        settings = get_settings()
        now = datetime.now(UTC)
        ttl = (
            timedelta(hours=settings.verify_email_ttl_hours)
            if purpose is EmailTokenPurpose.VERIFY_EMAIL
            else timedelta(minutes=settings.reset_password_ttl_minutes)
        )
        await self.email_tokens.invalidate_pending(user.id, purpose, now)
        raw = generate_token()
        await self.email_tokens.add(
            EmailToken(
                user_id=user.id, purpose=purpose, token_hash=hash_token(raw), expires_at=now + ttl
            )
        )
        return raw

    async def _consume_email_token(self, raw_token: str, purpose: EmailTokenPurpose) -> EmailToken:
        now = datetime.now(UTC)
        token = await self.email_tokens.get_by_hash_for_update(hash_token(raw_token), purpose)
        if token is None or token.used_at is not None or token.expires_at <= now:
            raise InvalidEmailTokenError()
        token.used_at = now
        return token

    async def _send_verification(self, user: User, raw_token: str) -> None:
        url = f"{get_settings().frontend_url}/verify-email?token={raw_token}"
        await self.outbox.send(templates.verify_email(user.email, user.name, url))

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

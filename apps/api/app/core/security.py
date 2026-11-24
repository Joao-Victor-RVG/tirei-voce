import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

# argon2-cffi usa Argon2id com os parâmetros recomendados pela RFC 9106 por padrão.
_hasher = PasswordHasher()
# Hash usado para gastar o mesmo tempo quando o usuário não existe (evita enumeração por tempo).
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))

_JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError, ValueError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def create_access_token(user_id: uuid.UUID, *, now: datetime | None = None) -> str:
    settings = get_settings()
    issued_at = now or datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=settings.access_token_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[_JWT_ALGORITHM],
            options={"require": ["sub", "exp", "iat"]},
        )
        if payload.get("type") != "access":
            return None
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError):
        return None


def generate_token() -> str:
    """Token opaco de alta entropia (refresh, verificação de e-mail, reset de senha)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def tokens_match(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())

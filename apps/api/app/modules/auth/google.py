import base64
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

from app.core.config import Settings
from app.core.errors import AppError
from app.core.redis import get_redis
from app.core.security import generate_token

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")

STATE_TTL_SECONDS = 600
_JWKS_TTL_SECONDS = 3600


class GoogleAuthError(AppError):
    code = "google_auth_failed"
    message = "Não foi possível entrar com o Google. Tente novamente."


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    name: str
    picture: str | None


@dataclass(frozen=True)
class PendingLogin:
    code_verifier: str
    nonce: str
    next_path: str


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


class OAuthStateStore:
    """Guarda verifier/nonce no Redis (e não na memória): qualquer réplica atende o callback."""

    PREFIX = "oauth:google:"

    async def save(self, state: str, pending: PendingLogin) -> None:
        payload = json.dumps(pending.__dict__)
        await get_redis().set(self.PREFIX + state, payload, ex=STATE_TTL_SECONDS)

    async def pop(self, state: str) -> PendingLogin | None:
        raw = await get_redis().getdel(self.PREFIX + state)
        return PendingLogin(**json.loads(raw)) if raw else None


class GoogleOAuthClient:
    _jwks_cache: tuple[float, dict[str, Any]] | None = None

    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None) -> None:
        if not settings.google_client_id or not settings.google_client_secret:
            raise GoogleAuthError("Login com Google não está configurado.", code="google_disabled")
        self.client_id = settings.google_client_id
        self.client_secret = settings.google_client_secret
        self.redirect_uri = settings.google_redirect_uri
        self.http = http or httpx.AsyncClient(timeout=10)

    def authorization_url(self, state: str, code_verifier: str, nonce: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "code_challenge": pkce_challenge(code_verifier),
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, code_verifier: str) -> str:
        response = await self.http.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
            },
        )
        if response.status_code != 200:
            raise GoogleAuthError()
        id_token = response.json().get("id_token")
        if not isinstance(id_token, str):
            raise GoogleAuthError()
        return id_token

    async def verify_id_token(self, id_token: str, nonce: str) -> GoogleIdentity:
        try:
            kid = jwt.get_unverified_header(id_token).get("kid")
            key = await self._signing_key(kid)
            claims = jwt.decode(
                id_token,
                key,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=ISSUERS,
                options={"require": ["sub", "email", "exp", "iat", "aud", "iss"]},
            )
        except jwt.PyJWTError as exc:
            raise GoogleAuthError() from exc
        if claims.get("nonce") != nonce:
            raise GoogleAuthError()
        if claims.get("email_verified") is not True:
            raise GoogleAuthError(
                "Seu e-mail no Google não está verificado.", code="google_email_unverified"
            )
        email = str(claims["email"]).lower()
        return GoogleIdentity(
            sub=str(claims["sub"]),
            email=email,
            name=str(claims.get("name") or email.split("@")[0])[:100],
            picture=claims.get("picture"),
        )

    async def _signing_key(self, kid: str | None) -> Any:
        for force_refresh in (False, True):
            jwks = await self._jwks(force_refresh)
            for jwk in jwks.get("keys", []):
                if jwk.get("kid") == kid:
                    return jwt.PyJWK(jwk).key
        raise GoogleAuthError()

    async def _jwks(self, force_refresh: bool) -> dict[str, Any]:
        cached = GoogleOAuthClient._jwks_cache
        if cached and not force_refresh and time.monotonic() - cached[0] < _JWKS_TTL_SECONDS:
            return cached[1]
        response = await self.http.get(JWKS_URL)
        if response.status_code != 200:
            raise GoogleAuthError()
        data: dict[str, Any] = response.json()
        GoogleOAuthClient._jwks_cache = (time.monotonic(), data)
        return data


def new_pending_login(next_path: str) -> tuple[str, PendingLogin]:
    return generate_token(), PendingLogin(
        generate_token() + generate_token(), generate_token(), next_path
    )


def safe_next_path(value: str | None) -> str:
    """Só aceita caminhos relativos do próprio front (evita open redirect)."""
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value:
        return "/groups"
    return value[:512]

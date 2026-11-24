import json
import time
from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.main import app
from app.modules.auth.google import GoogleOAuthClient, pkce_challenge, safe_next_path
from app.modules.auth.router import get_google_client
from app.modules.users.models import User
from tests.helpers import DEFAULT_PASSWORD, mark_verified, register

CLIENT_ID = "test-client.apps.googleusercontent.com"
_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_JWK = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(_KEY.public_key()))
_JWK.update({"kid": "k1", "alg": "RS256", "use": "sig"})


class FakeGoogle:
    def __init__(self) -> None:
        self.claims: dict[str, Any] = {}
        self.token_status = 200
        self.received: dict[str, list[str]] = {}

    def id_token(self, nonce: str) -> str:
        now = int(time.time())
        claims = {
            "iss": "https://accounts.google.com",
            "aud": CLIENT_ID,
            "sub": "google-sub-1",
            "email": "ana@example.com",
            "email_verified": True,
            "name": "Ana Google",
            "picture": "https://lh3.googleusercontent.com/a/ana",
            "iat": now,
            "exp": now + 300,
            "nonce": nonce,
        } | self.claims
        return jwt.encode(claims, _KEY, algorithm="RS256", headers={"kid": "k1"})

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/certs"):
            return httpx.Response(200, json={"keys": [_JWK]})
        self.received = parse_qs(request.content.decode())
        return httpx.Response(self.token_status, json={"id_token": self.id_token(self.nonce)})

    nonce = ""


@pytest.fixture
def google(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeGoogle]:
    settings = get_settings()
    monkeypatch.setattr(settings, "google_client_id", CLIENT_ID)
    monkeypatch.setattr(settings, "google_client_secret", "secret")
    monkeypatch.setattr(GoogleOAuthClient, "_jwks_cache", None)
    fake = FakeGoogle()
    client = GoogleOAuthClient(
        settings, httpx.AsyncClient(transport=httpx.MockTransport(fake.handler))
    )
    app.dependency_overrides[get_google_client] = lambda: client
    yield fake
    app.dependency_overrides.pop(get_google_client, None)


async def _start(client: httpx.AsyncClient, fake: FakeGoogle, next_path: str = "/i/abc") -> str:
    response = await client.get("/api/v1/auth/google/start", params={"next": next_path})
    assert response.status_code == 302
    params = parse_qs(urlsplit(response.headers["location"]).query)
    assert params["code_challenge_method"] == ["S256"]
    assert params["client_id"] == [CLIENT_ID]
    fake.nonce = params["nonce"][0]
    return params["state"][0]


async def _callback(client: httpx.AsyncClient, state: str) -> httpx.Response:
    return await client.get("/api/v1/auth/google/callback", params={"code": "c0de", "state": state})


async def test_google_creates_new_verified_account(
    client: httpx.AsyncClient, google: FakeGoogle
) -> None:
    state = await _start(client, google)
    response = await _callback(client, state)
    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:5173/i/abc"
    assert google.received["code_verifier"][0]  # PKCE enviado na troca

    me = (await client.get("/api/v1/me")).json()
    assert me["email_verified"] is True
    assert me["has_google"] is True
    assert me["has_password"] is False
    assert me["name"] == "Ana Google"


async def test_google_links_verified_password_account(
    client: httpx.AsyncClient, google: FakeGoogle
) -> None:
    await register(client, verified=True)
    await client.post("/api/v1/auth/logout")
    response = await _callback(client, await _start(client, google))
    assert response.status_code == 302

    me = (await client.get("/api/v1/me")).json()
    assert me["has_google"] is True and me["has_password"] is True
    login = await client.post(
        "/api/v1/auth/login", json={"email": "ana@example.com", "password": DEFAULT_PASSWORD}
    )
    assert login.status_code == 200


async def test_google_linking_unverified_account_drops_password(
    client: httpx.AsyncClient, google: FakeGoogle
) -> None:
    await register(client)  # alguém cadastrou o e-mail mas nunca confirmou
    squatter_refresh = client.cookies.get("tv_refresh")
    await _callback(client, await _start(client, google))

    me = (await client.get("/api/v1/me")).json()
    assert me["has_password"] is False and me["email_verified"] is True
    login = await client.post(
        "/api/v1/auth/login", json={"email": "ana@example.com", "password": DEFAULT_PASSWORD}
    )
    assert login.status_code == 401
    client.cookies.set("tv_refresh", squatter_refresh or "", path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_google_second_login_uses_sub(client: httpx.AsyncClient, google: FakeGoogle) -> None:
    await _callback(client, await _start(client, google))
    google.claims = {"email": "novo-email@example.com"}
    await _callback(client, await _start(client, google))
    async with get_sessionmaker()() as session:
        users = (await session.scalars(select(User))).all()
    assert len(users) == 1


@pytest.mark.parametrize(
    "claims, code",
    [
        ({"email_verified": False}, "google_email_unverified"),
        ({"aud": "outro-client"}, "google_auth_failed"),
        ({"iss": "https://evil.example"}, "google_auth_failed"),
        ({"nonce": "outro"}, "google_auth_failed"),
        ({"exp": int(time.time()) - 10}, "google_auth_failed"),
    ],
)
async def test_google_rejects_invalid_id_token(
    client: httpx.AsyncClient, google: FakeGoogle, claims: dict[str, Any], code: str
) -> None:
    state = await _start(client, google)
    google.claims = claims
    response = await _callback(client, state)
    assert response.headers["location"] == f"http://localhost:5173/login?error={code}"
    assert (await client.get("/api/v1/me")).status_code == 401


async def test_google_state_must_match_cookie_and_be_single_use(
    client: httpx.AsyncClient, google: FakeGoogle
) -> None:
    state = await _start(client, google)
    client.cookies.delete("tv_oauth", path="/api/v1/auth/google")
    response = await _callback(client, state)
    assert "error=google_auth_failed" in response.headers["location"]

    state = await _start(client, google)
    assert "error=" not in (await _callback(client, state)).headers["location"]
    client.cookies.set("tv_oauth", state, path="/api/v1/auth/google")
    assert "error=" in (await _callback(client, state)).headers["location"]


async def test_google_token_exchange_failure(client: httpx.AsyncClient, google: FakeGoogle) -> None:
    state = await _start(client, google)
    google.token_status = 400
    assert "error=google_auth_failed" in (await _callback(client, state)).headers["location"]


async def test_google_conflicting_account(client: httpx.AsyncClient, google: FakeGoogle) -> None:
    await _callback(client, await _start(client, google))
    google.claims = {"sub": "outro-sub"}
    response = await _callback(client, await _start(client, google))
    assert "error=google_account_conflict" in response.headers["location"]


async def test_google_disabled(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/v1/auth/config")).json()["google_enabled"] is False
    response = await client.get("/api/v1/auth/google/start")
    assert response.headers["location"].endswith("/login?error=google_disabled")
    response = await client.get("/api/v1/auth/google/callback", params={"code": "x", "state": "y"})
    assert response.headers["location"].endswith("/login?error=google_disabled")


async def test_google_disabled_account(client: httpx.AsyncClient, google: FakeGoogle) -> None:
    await register(client)
    await mark_verified("ana@example.com")
    async with get_sessionmaker()() as session:
        user = await session.scalar(select(User))
        assert user is not None
        user.is_active = False
        await session.commit()
    response = await _callback(client, await _start(client, google))
    assert "error=account_disabled" in response.headers["location"]


@pytest.mark.parametrize(
    "value, expected",
    [
        ("/groups/1", "/groups/1"),
        (None, "/groups"),
        ("https://evil.com", "/groups"),
        ("//evil.com", "/groups"),
        ("/\\evil.com", "/groups"),
    ],
)
def test_safe_next_path(value: str | None, expected: str) -> None:
    assert safe_next_path(value) == expected


def test_pkce_challenge_matches_rfc7636_example() -> None:
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    assert pkce_challenge(verifier) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"

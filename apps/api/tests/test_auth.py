import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.core.security import create_access_token, hash_password, verify_password
from app.modules.auth.models import RefreshToken
from app.modules.users.models import User
from tests.conftest import make_client
from tests.helpers import DEFAULT_PASSWORD, register


async def test_register_logs_in_and_sets_cookies(client: httpx.AsyncClient) -> None:
    data = await register(client, "Ana@Example.com")
    assert data["email"] == "ana@example.com"
    assert data["email_verified"] is False
    assert data["has_password"] is True
    assert {"tv_access", "tv_refresh", "tv_csrf"} <= set(client.cookies.keys())

    me = await client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["name"] == "Ana"


async def test_cookies_are_httponly_and_lax(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"name": "Ana", "email": "ana@example.com", "password": DEFAULT_PASSWORD},
    )
    set_cookies = response.headers.get_list("set-cookie")
    access = next(c for c in set_cookies if c.startswith("tv_access="))
    refresh = next(c for c in set_cookies if c.startswith("tv_refresh="))
    csrf = next(c for c in set_cookies if c.startswith("tv_csrf="))
    for cookie in (access, refresh):
        assert "HttpOnly" in cookie
        assert "SameSite=lax" in cookie
    assert "Path=/api/v1/auth" in refresh
    assert "HttpOnly" not in csrf


async def test_password_is_stored_with_argon2id(client: httpx.AsyncClient) -> None:
    await register(client)
    async with get_sessionmaker()() as session:
        user = await session.scalar(select(User))
    assert user is not None and user.password_hash is not None
    assert user.password_hash.startswith("$argon2id$")
    assert DEFAULT_PASSWORD not in user.password_hash


async def test_register_duplicate_email_case_insensitive(client: httpx.AsyncClient) -> None:
    await register(client, "ana@example.com")
    response = await client.post(
        "/api/v1/auth/register",
        json={"name": "Outra", "email": "ANA@example.com", "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


@pytest.mark.parametrize("password", ["curta", "senha123", "12345678", "aaaaaaaaaa"])
async def test_register_rejects_weak_passwords(client: httpx.AsyncClient, password: str) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"name": "Ana", "email": "ana@example.com", "password": password},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "weak_password"


async def test_register_rejects_invalid_email(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"name": "Ana", "email": "nao-e-email", "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_login_success_and_failure(client: httpx.AsyncClient) -> None:
    await register(client)
    await client.post("/api/v1/auth/logout")
    client.cookies.delete("tv_access", path="/api")

    wrong = await client.post(
        "/api/v1/auth/login", json={"email": "ana@example.com", "password": "errada-123"}
    )
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "invalid_credentials"

    unknown = await client.post(
        "/api/v1/auth/login", json={"email": "ninguem@example.com", "password": "errada-123"}
    )
    assert unknown.status_code == 401
    assert unknown.json()["error"] == wrong.json()["error"]

    ok = await client.post(
        "/api/v1/auth/login", json={"email": "ANA@example.com", "password": DEFAULT_PASSWORD}
    )
    assert ok.status_code == 200
    assert (await client.get("/api/v1/me")).status_code == 200


async def test_login_inactive_account(client: httpx.AsyncClient) -> None:
    await register(client)
    async with get_sessionmaker()() as session:
        user = await session.scalar(select(User))
        assert user is not None
        user.is_active = False
        await session.commit()
    response = await client.post(
        "/api/v1/auth/login", json={"email": "ana@example.com", "password": DEFAULT_PASSWORD}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "account_disabled"


async def test_me_requires_auth(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_expired_or_forged_access_token_is_rejected(client: httpx.AsyncClient) -> None:
    data = await register(client)

    expired = create_access_token(uuid.UUID(data["id"]), now=datetime.now(UTC) - timedelta(hours=1))
    client.cookies.set("tv_access", expired, path="/api")
    assert (await client.get("/api/v1/me")).status_code == 401

    client.cookies.set("tv_access", expired[:-4] + "abcd", path="/api")
    assert (await client.get("/api/v1/me")).status_code == 401


async def test_csrf_required_for_mutations() -> None:
    async with make_client() as c:
        response = await c.post(
            "/api/v1/auth/register",
            json={"name": "Ana", "email": "ana@example.com", "password": DEFAULT_PASSWORD},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "csrf_failed"

        await c.get("/api/v1/auth/csrf")
        bad = await c.post(
            "/api/v1/auth/login",
            json={"email": "ana@example.com", "password": "x"},
            headers={"X-CSRF-Token": "outro-valor"},
        )
        assert bad.status_code == 403


async def test_refresh_rotates_token(client: httpx.AsyncClient) -> None:
    await register(client)
    old_refresh = client.cookies.get("tv_refresh")
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    new_refresh = client.cookies.get("tv_refresh")
    assert new_refresh and new_refresh != old_refresh
    assert (await client.get("/api/v1/me")).status_code == 200


async def test_refresh_reuse_revokes_all_sessions(client: httpx.AsyncClient) -> None:
    await register(client)
    stolen = client.cookies.get("tv_refresh")
    assert stolen
    assert (await client.post("/api/v1/auth/refresh")).status_code == 200

    async with make_client() as attacker:
        await attacker.get("/api/v1/auth/csrf")
        attacker.cookies.set("tv_refresh", stolen, path="/api/v1/auth")
        reuse = await attacker.post("/api/v1/auth/refresh")
        assert reuse.status_code == 401
        assert reuse.json()["error"]["code"] == "invalid_refresh_token"

    # A sessão legítima (já rotacionada) também foi derrubada.
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401
    async with get_sessionmaker()() as session:
        tokens = (await session.scalars(select(RefreshToken))).all()
    assert tokens and all(t.revoked_at is not None for t in tokens)


async def test_refresh_without_cookie_or_expired(client: httpx.AsyncClient) -> None:
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401

    await register(client)
    async with get_sessionmaker()() as session:
        token = await session.scalar(select(RefreshToken))
        assert token is not None
        token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_logout_revokes_refresh_token(client: httpx.AsyncClient) -> None:
    await register(client)
    refresh = client.cookies.get("tv_refresh")
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 204
    assert "tv_access" not in client.cookies

    client.cookies.set("tv_refresh", refresh or "", path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_login_rate_limited_per_email(client: httpx.AsyncClient) -> None:
    payload = {"email": "alvo@example.com", "password": "errada-123"}
    statuses = [
        (await client.post("/api/v1/auth/login", json=payload)).status_code for _ in range(11)
    ]
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429
    last = await client.post("/api/v1/auth/login", json=payload)
    assert last.json()["error"]["details"]["retry_after_seconds"] > 0


async def test_update_me(client: httpx.AsyncClient) -> None:
    await register(client)
    response = await client.patch(
        "/api/v1/me",
        json={"name": "  Ana Maria ", "shirt_size": "M", "shoe_size": "37"},
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["name"], body["shirt_size"], body["shoe_size"]) == ("Ana Maria", "M", "37")

    assert (await client.patch("/api/v1/me", json={"name": None})).status_code == 422
    assert (await client.patch("/api/v1/me", json={"email": "x@y.com"})).status_code == 422


def test_verify_password_handles_missing_hash() -> None:
    assert verify_password("qualquer", None) is False
    assert verify_password("certa-123", hash_password("certa-123")) is True
    assert verify_password("errada", "não-é-hash") is False


async def test_auto_verify_emails_for_testing(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, outbox: object
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "auto_verify_emails", True)
    data = await register(client)
    assert data["email_verified"] is True
    assert outbox.messages == []  # type: ignore[attr-defined]


def test_auto_verify_emails_forbidden_in_production() -> None:
    from app.core.config import Settings

    with pytest.raises(ValueError, match="AUTO_VERIFY_EMAILS"):
        Settings(
            environment="production",
            cookie_secure=True,
            jwt_secret="x" * 40,
            draw_encryption_key="YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXphYmNkZWY=",
            draw_hmac_key="y" * 40,
            auto_verify_emails=True,
        )

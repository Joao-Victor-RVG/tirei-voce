import itertools
import uuid

import httpx
import pytest
from fastapi import APIRouter

from app.core.errors import ConflictError
from app.core.ids import uuid7
from app.main import app

_probe = APIRouter(prefix="/__probe")


@_probe.get("/conflict")
async def _conflict() -> None:
    raise ConflictError("Grupo já sorteado.", code="group_already_drawn")


@_probe.get("/boom")
async def _boom() -> None:
    raise RuntimeError("segredo interno")


@_probe.get("/validate")
async def _validate(n: int) -> int:
    return n


app.include_router(_probe)


async def test_health_checks_db_and_redis(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok", "redis": "ok"}}


async def test_health_reports_failure(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing() -> str:
        return "error"

    monkeypatch.setattr("app.core.health._check_redis", failing)
    response = await client.get("/health")
    assert response.status_code == 503
    assert response.json()["checks"]["redis"] == "error"


async def test_app_error_format(client: httpx.AsyncClient) -> None:
    response = await client.get("/__probe/conflict")
    assert response.status_code == 409
    assert response.json() == {
        "error": {"code": "group_already_drawn", "message": "Grupo já sorteado."}
    }


async def test_validation_error_format(client: httpx.AsyncClient) -> None:
    response = await client.get("/__probe/validate", params={"n": "abc"})
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert body["details"][0]["field"] == "n"


async def test_not_found_format(client: httpx.AsyncClient) -> None:
    response = await client.get("/nao-existe")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_unexpected_error_hides_details() -> None:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        response = await c.get("/__probe/boom")
    assert response.status_code == 500
    assert "segredo" not in response.text
    assert response.json()["error"]["code"] == "internal_error"


async def test_request_id_and_security_headers(client: httpx.AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert response.headers["X-Request-ID"] == "abc-123"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"

    generated = await client.get("/health", headers={"X-Request-ID": "bad id with spaces"})
    assert generated.headers["X-Request-ID"] != "bad id with spaces"


async def test_cors_allows_only_frontend(client: httpx.AsyncClient) -> None:
    preflight = {"Access-Control-Request-Method": "POST"}
    ok = await client.options("/health", headers={"Origin": "http://localhost:5173", **preflight})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = await client.options("/health", headers={"Origin": "https://evil.example", **preflight})
    assert "access-control-allow-origin" not in bad.headers


def test_uuid7_is_version_7_and_time_ordered() -> None:
    ids = [uuid7() for _ in range(100)]
    assert all(
        isinstance(i, uuid.UUID) and i.version == 7 and i.variant == uuid.RFC_4122 for i in ids
    )
    assert [i.bytes[:6] for i in ids] == sorted(i.bytes[:6] for i in ids)
    assert len(set(ids)) == 100


def test_uuid7_is_strictly_monotonic_within_the_same_millisecond() -> None:
    # Milhares de ids caem no mesmo milissegundo: ainda assim saem sempre em ordem.
    ids = [uuid7() for _ in range(20_000)]
    assert all(a < b for a, b in itertools.pairwise(ids))


def test_uuid7_keeps_order_if_clock_goes_back(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    first = uuid7()
    monkeypatch.setattr(time, "time_ns", lambda: 0)  # relógio "voltou" para 1970
    second = uuid7()
    assert second > first

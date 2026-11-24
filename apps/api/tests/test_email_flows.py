from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select, update

from app.core.db import get_sessionmaker
from app.modules.auth.models import EmailToken
from app.modules.notifications.email import (
    ConsoleEmailSender,
    EmailMessage,
    ResendEmailSender,
    build_email_sender,
)
from app.modules.notifications.service import QueuedEmailOutbox
from app.workers.main import send_email
from tests.conftest import MemoryOutbox
from tests.helpers import DEFAULT_PASSWORD, register, token_from

NEW_PASSWORD = "Outra-senha-forte-99"


async def test_register_sends_verification_email(
    client: httpx.AsyncClient, outbox: MemoryOutbox
) -> None:
    await register(client, name="Ana <script>")
    message = outbox.last_to("ana@example.com")
    assert "Confirme seu e-mail" in message.subject
    assert "http://localhost:5173/verify-email?token=" in message.text
    assert "<script>" not in message.html  # nome é escapado no HTML


async def test_verify_email_is_single_use(client: httpx.AsyncClient, outbox: MemoryOutbox) -> None:
    await register(client)
    token = token_from(outbox.last_to("ana@example.com").text)

    response = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert response.status_code == 200
    assert response.json()["email_verified"] is True

    again = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "invalid_token"


async def test_verify_email_expired(client: httpx.AsyncClient, outbox: MemoryOutbox) -> None:
    await register(client)
    token = token_from(outbox.last_to("ana@example.com").text)
    async with get_sessionmaker()() as session:
        await session.execute(
            update(EmailToken).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()
    response = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert response.status_code == 400


async def test_resend_verification_invalidates_previous_link(
    client: httpx.AsyncClient, outbox: MemoryOutbox
) -> None:
    await register(client)
    first = token_from(outbox.last_to("ana@example.com").text)
    response = await client.post("/api/v1/auth/resend-verification")
    assert response.status_code == 202
    second = token_from(outbox.last_to("ana@example.com").text)
    assert first != second

    assert (
        await client.post("/api/v1/auth/verify-email", json={"token": first})
    ).status_code == 400
    assert (
        await client.post("/api/v1/auth/verify-email", json={"token": second})
    ).status_code == 200

    # Já verificado: não manda mais nada.
    count = len(outbox.messages)
    await client.post("/api/v1/auth/resend-verification")
    assert len(outbox.messages) == count


async def test_resend_verification_rate_limited(client: httpx.AsyncClient) -> None:
    await register(client)
    codes = [(await client.post("/api/v1/auth/resend-verification")).status_code for _ in range(4)]
    assert codes == [202, 202, 202, 429]


async def test_forgot_password_is_generic(client: httpx.AsyncClient, outbox: MemoryOutbox) -> None:
    await register(client)
    sent_before = len(outbox.messages)

    unknown = await client.post("/api/v1/auth/forgot-password", json={"email": "x@example.com"})
    known = await client.post("/api/v1/auth/forgot-password", json={"email": "ANA@example.com"})
    assert unknown.status_code == known.status_code == 202
    assert unknown.json() == known.json()
    assert len(outbox.messages) == sent_before + 1
    assert "/reset-password?token=" in outbox.messages[-1].text


async def test_reset_password_flow(client: httpx.AsyncClient, outbox: MemoryOutbox) -> None:
    await register(client)
    old_refresh = client.cookies.get("tv_refresh")
    await client.post("/api/v1/auth/forgot-password", json={"email": "ana@example.com"})
    token = token_from(outbox.last_to("ana@example.com").text)

    weak = await client.post(
        "/api/v1/auth/reset-password", json={"token": token, "password": "senha123"}
    )
    assert weak.status_code == 422

    ok = await client.post(
        "/api/v1/auth/reset-password", json={"token": token, "password": NEW_PASSWORD}
    )
    assert ok.status_code == 204

    reused = await client.post(
        "/api/v1/auth/reset-password", json={"token": token, "password": NEW_PASSWORD}
    )
    assert reused.status_code == 400

    # Sessões antigas foram revogadas.
    client.cookies.set("tv_refresh", old_refresh or "", path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401

    old_login = {"email": "ana@example.com", "password": DEFAULT_PASSWORD}
    assert (await client.post("/api/v1/auth/login", json=old_login)).status_code == 401
    new_login = await client.post(
        "/api/v1/auth/login", json={"email": "ana@example.com", "password": NEW_PASSWORD}
    )
    assert new_login.status_code == 200
    assert new_login.json()["email_verified"] is True


async def test_reset_token_cannot_verify_email(
    client: httpx.AsyncClient, outbox: MemoryOutbox
) -> None:
    await register(client)
    await client.post("/api/v1/auth/forgot-password", json={"email": "ana@example.com"})
    reset_token = token_from(outbox.last_to("ana@example.com").text)
    response = await client.post("/api/v1/auth/verify-email", json={"token": reset_token})
    assert response.status_code == 400


async def test_tokens_are_stored_hashed(client: httpx.AsyncClient, outbox: MemoryOutbox) -> None:
    await register(client)
    raw = token_from(outbox.last_to("ana@example.com").text)
    async with get_sessionmaker()() as session:
        hashes = (await session.scalars(select(EmailToken.token_hash))).all()
    assert raw not in hashes


# --- EmailSender / worker ---

MESSAGE = EmailMessage(to="a@b.com", subject="Oi", html="<p>Oi</p>", text="Oi")


async def test_resend_sender_calls_api() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers["authorization"]
        captured["body"] = request.content
        return httpx.Response(200, json={"id": "1"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await ResendEmailSender("re_key", "Tirei <x@y.com>", client).send(MESSAGE)
    assert captured["auth"] == "Bearer re_key"
    assert b'"to":["a@b.com"]' in captured["body"]


async def test_resend_sender_raises_on_error() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(500)))
    with pytest.raises(httpx.HTTPStatusError):
        await ResendEmailSender("k", "x@y.com", client).send(MESSAGE)


async def test_worker_job_uses_sender(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    await send_email({"email_sender": ConsoleEmailSender()}, MESSAGE.to_dict())
    assert any(r.getMessage() == "email_sent_to_console" for r in caplog.records)


async def test_queued_outbox_enqueues_job() -> None:
    from app.core import queue

    await QueuedEmailOutbox().send(MESSAGE)
    jobs = await (await queue.get_queue()).queued_jobs()
    assert [j.function for j in jobs] == ["send_email"]
    await queue.close_queue()


def test_build_email_sender() -> None:
    from app.core.config import Settings

    assert isinstance(build_email_sender(Settings(email_provider="console")), ConsoleEmailSender)
    sender = build_email_sender(Settings(email_provider="resend", resend_api_key="k"))
    assert isinstance(sender, ResendEmailSender)

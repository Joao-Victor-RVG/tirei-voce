import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select, update

from app.core.db import get_sessionmaker
from app.modules.groups.models import Group
from app.modules.notifications.email import EmailMessage
from app.modules.reminders.models import SentReminder
from app.modules.reminders.service import ReminderService, format_br
from tests.conftest import UserClientFactory
from tests.helpers import future, group_with_members


class CaptureSender:
    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.messages.append(message)


async def _group(
    user_client: UserClientFactory, **overrides: object
) -> tuple[dict[str, object], dict[str, httpx.AsyncClient]]:
    clients = {n: await user_client(n) for n in ["Ana", "Bia", "Caio"]}
    group, _ = await group_with_members(
        clients["Ana"], [clients["Bia"], clients["Caio"]], **overrides
    )
    return group, clients


async def _set(group_id: object, **values: object) -> None:
    async with get_sessionmaker()() as session:
        await session.execute(
            update(Group).where(Group.id == uuid.UUID(str(group_id))).values(**values)
        )
        await session.commit()


async def _run(now: datetime) -> CaptureSender:
    sender = CaptureSender()
    async with get_sessionmaker()() as session:
        await ReminderService(session, sender).send_due(now)
    return sender


async def test_event_reminder_sent_once_to_everyone(user_client: UserClientFactory) -> None:
    group, _ = await _group(user_client)
    now = datetime.now(UTC)
    event_at = now + timedelta(hours=20)
    await _set(group["id"], event_at=event_at, event_location="Casa da vó")

    first = await _run(now)
    assert sorted(m.to for m in first.messages) == [
        "ana@example.com",
        "bia@example.com",
        "caio@example.com",
    ]
    message = first.messages[0]
    assert "Falta só 1 dia" in message.html and "Casa da vó" in message.text
    assert format_br(event_at) in message.text
    assert f"/groups/{group['id']}" in message.text

    assert (await _run(now + timedelta(minutes=5))).messages == []  # não duplica

    async with get_sessionmaker()() as session:
        rows = (await session.scalars(select(SentReminder))).all()
    assert [(r.kind, r.recipients) for r in rows] == [("event_1d", 3)]


async def test_two_hours_reminder_and_rescheduled_event(user_client: UserClientFactory) -> None:
    group, _ = await _group(user_client)
    now = datetime.now(UTC)
    await _set(group["id"], event_at=now + timedelta(hours=1))
    assert "Faltam 2 horas" in (await _run(now)).messages[0].subject

    # O organizador muda o horário: o lembrete vale de novo para a data nova.
    await _set(group["id"], event_at=now + timedelta(hours=1, minutes=30))
    assert len((await _run(now)).messages) == 3


async def test_wishlist_reminder_only_for_empty_lists(user_client: UserClientFactory) -> None:
    group, clients = await _group(user_client)
    base = f"/api/v1/groups/{group['id']}"
    await clients["Bia"].post(f"{base}/me/wishlist", json={"title": "Livro"})
    now = datetime.now(UTC)
    await _set(group["id"], wishlist_deadline_at=now + timedelta(hours=10))

    sent = await _run(now)
    assert sorted(m.to for m in sent.messages) == ["ana@example.com", "caio@example.com"]
    assert "lista de desejos" in sent.messages[0].subject.lower()


async def test_opt_out_and_inactive_groups(user_client: UserClientFactory) -> None:
    group, clients = await _group(user_client)
    assert (await clients["Bia"].patch("/api/v1/me", json={"email_reminders": False})).json()[
        "email_reminders"
    ] is False
    now = datetime.now(UTC)
    await _set(group["id"], event_at=now + timedelta(hours=10))
    assert sorted(m.to for m in (await _run(now)).messages) == [
        "ana@example.com",
        "caio@example.com",
    ]

    other, _ = await _group_named(user_client)
    await _set(other["id"], event_at=now + timedelta(hours=10), status="FINISHED")
    assert (await _run(now)).messages == []


async def _group_named(user_client: UserClientFactory) -> tuple[dict[str, object], None]:
    eva = await user_client("Eva")
    group, _ = await group_with_members(eva, [])
    return group, None


async def test_wishlist_deadline_validation(user_client: UserClientFactory) -> None:
    ana = await user_client("Ana")
    ok = await ana.post(
        "/api/v1/groups",
        json={
            "theme_slug": "amigo-secreto",
            "title": "Natal",
            "event_at": future(30),
            "wishlist_deadline_at": future(20),
        },
    )
    assert ok.status_code == 201 and ok.json()["wishlist_deadline_at"]
    after_event = await ana.patch(
        f"/api/v1/groups/{ok.json()['id']}", json={"wishlist_deadline_at": future(40)}
    )
    assert after_event.status_code == 422
    past = await ana.patch(
        f"/api/v1/groups/{ok.json()['id']}", json={"wishlist_deadline_at": "2020-01-01T00:00:00Z"}
    )
    assert past.status_code == 422

import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import update

from app.core.db import get_sessionmaker
from app.modules.groups.models import Group
from app.modules.reminders.service import ReminderService
from tests.conftest import UserClientFactory
from tests.helpers import group_with_members
from tests.test_reminders import CaptureSender

NAMES = ["Ana", "Bia", "Caio", "Duda"]


async def _drawn(
    user_client: UserClientFactory,
) -> tuple[str, dict[str, httpx.AsyncClient], dict[str, str]]:
    clients = {n: await user_client(n) for n in NAMES}
    group, _ = await group_with_members(clients["Ana"], [clients[n] for n in NAMES[1:]])
    base = f"/api/v1/groups/{group['id']}"
    await clients["Ana"].post(f"{base}/draw")
    matches = {n: (await clients[n].get(f"{base}/my-match")).json()["name"] for n in NAMES}
    return base, clients, matches


async def _event_at(base: str, when: datetime) -> None:
    async with get_sessionmaker()() as session:
        await session.execute(
            update(Group)
            .where(Group.id == uuid.UUID(base.rsplit("/", 1)[-1]))
            .values(event_at=when)
        )
        await session.commit()


async def test_reveal_only_after_event_and_only_own_santa(user_client: UserClientFactory) -> None:
    base, clients, matches = await _drawn(user_client)
    early = await clients["Bia"].get(f"{base}/my-santa")
    assert early.status_code == 409 and early.json()["error"]["code"] == "reveal_not_available"

    await _event_at(base, datetime.now(UTC) - timedelta(minutes=1))
    for name, client in clients.items():
        santa = (await client.get(f"{base}/my-santa")).json()
        expected = next(giver for giver, receiver in matches.items() if receiver == name)
        assert santa["name"] == expected
        assert set(santa) == {"participant_id", "name", "avatar_url"}  # nada de outros pares


async def test_no_event_date_means_no_reveal(user_client: UserClientFactory) -> None:
    base, clients, _ = await _drawn(user_client)
    await _event_at(base, None)  # type: ignore[arg-type]
    assert (await clients["Ana"].get(f"{base}/my-santa")).status_code == 409


async def test_chat_shows_real_name_after_reveal(user_client: UserClientFactory) -> None:
    base, clients, matches = await _drawn(user_client)
    santa_of_bia = next(giver for giver, receiver in matches.items() if receiver == "Bia")
    threads = {t["thread"]: t for t in (await clients["Bia"].get(f"{base}/chats")).json()}
    assert threads["santa"]["title"] == "Seu amigo secreto"
    await _event_at(base, datetime.now(UTC) - timedelta(minutes=1))
    threads = {t["thread"]: t for t in (await clients["Bia"].get(f"{base}/chats")).json()}
    assert threads["santa"]["title"] == santa_of_bia


async def test_reveal_reminder_at_event_time(user_client: UserClientFactory) -> None:
    base, _, _ = await _drawn(user_client)
    now = datetime.now(UTC)
    await _event_at(base, now - timedelta(minutes=3))
    sender = CaptureSender()
    async with get_sessionmaker()() as session:
        await ReminderService(session, sender).send_due(now)
    assert len(sender.messages) == 4
    assert "Hora da revelação" in sender.messages[0].subject

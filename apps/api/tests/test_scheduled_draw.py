import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select, update

from app.core.db import get_sessionmaker
from app.modules.draws.models import Draw
from app.modules.draws.scheduled import run_scheduled_draws
from app.modules.groups.models import Group
from app.modules.notifications.email import EmailMessage
from tests.conftest import UserClientFactory
from tests.helpers import future, group_with_members


class CaptureSender:
    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.messages.append(message)


async def _group(
    user_client: UserClientFactory,
) -> tuple[str, dict[str, str], dict[str, httpx.AsyncClient]]:
    clients = {n: await user_client(n) for n in ["Ana", "Bia", "Caio", "Duda"]}
    group, ids = await group_with_members(
        clients["Ana"], [clients[n] for n in ["Bia", "Caio", "Duda"]]
    )
    return str(group["id"]), ids, clients


async def _due_now(group_id: str) -> None:
    async with get_sessionmaker()() as session:
        await session.execute(
            update(Group)
            .where(Group.id == uuid.UUID(group_id))
            .values(draw_scheduled_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()


async def test_schedule_validation(user_client: UserClientFactory) -> None:
    gid, _, c = await _group(user_client)
    base = f"/api/v1/groups/{gid}"
    ok = await c["Ana"].patch(base, json={"draw_scheduled_at": future(10)})
    assert ok.status_code == 200 and ok.json()["draw_scheduled_at"]
    past = await c["Ana"].patch(base, json={"draw_scheduled_at": "2020-01-01T00:00:00Z"})
    assert past.status_code == 422
    after_event = await c["Ana"].patch(base, json={"draw_scheduled_at": future(60)})
    assert after_event.status_code == 422  # evento do helper é em 30 dias
    assert (await c["Bia"].patch(base, json={"draw_scheduled_at": future(5)})).status_code == 403
    cleared = await c["Ana"].patch(base, json={"draw_scheduled_at": None})
    assert cleared.json()["draw_scheduled_at"] is None


async def test_scheduled_draw_runs_as_owner(user_client: UserClientFactory) -> None:
    gid, _, c = await _group(user_client)
    await c["Ana"].patch(f"/api/v1/groups/{gid}", json={"draw_scheduled_at": future(1)})
    sender = CaptureSender()

    assert await run_scheduled_draws(sender, datetime.now(UTC)) == 0  # ainda não venceu
    await _due_now(gid)
    assert await run_scheduled_draws(sender, datetime.now(UTC)) == 1

    group = (await c["Ana"].get(f"/api/v1/groups/{gid}")).json()
    assert group["status"] == "DRAWN" and group["draw_scheduled_at"] is None
    names = {(await c[n].get(f"/api/v1/groups/{gid}/my-match")).json()["name"] for n in c}
    assert names == set(c)
    async with get_sessionmaker()() as session:
        draw = await session.scalar(select(Draw))
    ana_id = (await c["Ana"].get("/api/v1/me")).json()["id"]
    assert draw is not None and str(draw.executed_by) == ana_id
    assert await run_scheduled_draws(sender, datetime.now(UTC)) == 0  # não repete


async def test_concurrent_workers_draw_once(user_client: UserClientFactory) -> None:
    gid, _, _ = await _group(user_client)
    await _due_now(gid)
    sender = CaptureSender()
    results = await asyncio.gather(
        *(run_scheduled_draws(sender, datetime.now(UTC)) for _ in range(3))
    )
    assert sum(results) == 1
    async with get_sessionmaker()() as session:
        assert len((await session.scalars(select(Draw))).all()) == 1


async def test_impossible_scheduled_draw_warns_organizers(user_client: UserClientFactory) -> None:
    gid, ids, c = await _group(user_client)
    base = f"/api/v1/groups/{gid}"
    await c["Ana"].put(f"{base}/participants/{ids['Bia']}/co-organizer")
    await c["Ana"].post(
        f"{base}/exclusion-circles",
        json={"name": "Família", "participant_ids": [ids["Ana"], ids["Bia"], ids["Caio"]]},
    )
    await _due_now(gid)
    sender = CaptureSender()
    assert await run_scheduled_draws(sender, datetime.now(UTC)) == 0

    group = (await c["Ana"].get(base)).json()
    assert group["status"] == "OPEN" and group["draw_scheduled_at"] is None  # não fica tentando
    assert sorted(m.to for m in sender.messages) == ["ana@example.com", "bia@example.com"]
    assert "não existe sorteio possível" in sender.messages[0].text


async def test_manual_draw_clears_schedule(user_client: UserClientFactory) -> None:
    gid, _, c = await _group(user_client)
    await c["Ana"].patch(f"/api/v1/groups/{gid}", json={"draw_scheduled_at": future(5)})
    await c["Ana"].post(f"/api/v1/groups/{gid}/draw")
    await _due_now(gid)
    assert await run_scheduled_draws(CaptureSender(), datetime.now(UTC)) == 0

import json
import uuid
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from pywebpush import WebPushException
from sqlalchemy import select

from app.core import queue
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.keys import vapid_keys
from app.modules.notifications import push
from app.modules.notifications.models import PushSubscription
from app.workers.notifications import push_chat_message, push_draw_done
from tests.conftest import UserClientFactory
from tests.helpers import group_with_members

FCM = "https://fcm.googleapis.com/fcm/send/"
KEYS = {
    "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u"
    "-Ts1XbjhazAkj7I99e8QcYP7DkM",
    "auth": "tBHItJI5svbpez7KI4CCXg",
}


class FakePush:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.fail_with: dict[str, int] = {}

    def __call__(self, subscription_info: dict[str, Any], data: str, **kwargs: Any) -> None:
        endpoint = subscription_info["endpoint"]
        if endpoint in self.fail_with:
            raise WebPushException(
                "fail", response=SimpleNamespace(status_code=self.fail_with[endpoint])
            )
        assert kwargs["vapid_claims"]["sub"].startswith("mailto:")
        self.sent.append({"endpoint": endpoint, "data": json.loads(data)})


@pytest.fixture
def fake_push(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakePush]:
    public, private = vapid_keys()
    settings = get_settings()
    monkeypatch.setattr(settings, "vapid_public_key", public)
    monkeypatch.setattr(settings, "vapid_private_key", private)
    push._vapid.cache_clear()
    fake = FakePush()
    monkeypatch.setattr(push, "webpush", fake)
    yield fake
    push._vapid.cache_clear()


async def _subscribe(client: httpx.AsyncClient, token: str) -> httpx.Response:
    return await client.post(
        "/api/v1/push/subscriptions",
        json={"endpoint": FCM + token, "keys": KEYS, "expirationTime": None},
    )


@pytest.mark.parametrize(
    "endpoint, allowed",
    [
        ("https://fcm.googleapis.com/fcm/send/abc", True),
        ("https://updates.push.services.mozilla.com/wpush/v2/abc", True),
        ("https://web.push.apple.com/abc", True),
        ("https://wns2-bl2p.notify.windows.com/w/?token=abc", True),
        ("http://fcm.googleapis.com/fcm/send/abc", False),
        ("https://evil.com/fcm.googleapis.com", False),
        ("https://fcm.googleapis.com.evil.com/x", False),
        ("https://169.254.169.254/latest", False),
    ],
)
def test_endpoint_allow_list(endpoint: str, allowed: bool) -> None:
    assert push.is_allowed_endpoint(endpoint) is allowed


async def test_push_config_and_subscribe(
    user_client: UserClientFactory, fake_push: FakePush
) -> None:
    ana = await user_client("Ana")
    config = (await ana.get("/api/v1/push/config", params={"endpoint": FCM + "a1"})).json()
    assert config["enabled"] is True and config["public_key"] and config["subscribed"] is False

    assert (await _subscribe(ana, "a1")).status_code == 204
    assert (await _subscribe(ana, "a1")).status_code == 204  # idempotente
    config = (await ana.get("/api/v1/push/config", params={"endpoint": FCM + "a1"})).json()
    assert config["subscribed"] is True

    bad = await ana.post(
        "/api/v1/push/subscriptions", json={"endpoint": "https://evil.com/x", "keys": KEYS}
    )
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "push_endpoint_not_allowed"

    assert (
        await ana.request("DELETE", "/api/v1/push/subscriptions", params={"endpoint": FCM + "a1"})
    ).status_code == 204
    async with get_sessionmaker()() as session:
        assert (await session.scalars(select(PushSubscription))).all() == []


async def test_push_disabled_without_vapid(
    client: httpx.AsyncClient, user_client: UserClientFactory
) -> None:
    ana = await user_client("Ana")
    assert (await ana.get("/api/v1/push/config")).json() == {
        "enabled": False,
        "public_key": None,
        "subscribed": False,
    }


async def test_same_browser_moves_to_new_user(
    user_client: UserClientFactory, fake_push: FakePush
) -> None:
    ana, bia = await user_client("Ana"), await user_client("Bia")
    await _subscribe(ana, "shared")
    await _subscribe(bia, "shared")
    async with get_sessionmaker()() as session:
        subs = (await session.scalars(select(PushSubscription))).all()
    assert len(subs) == 1
    bia_id = (await bia.get("/api/v1/me")).json()["id"]
    assert str(subs[0].user_id) == bia_id


async def _drawn_group(
    user_client: UserClientFactory,
) -> tuple[dict[str, Any], dict[str, httpx.AsyncClient], dict[str, str]]:
    names = ["Ana", "Bia", "Caio"]
    clients = {n: await user_client(n) for n in names}
    for n in names:
        await _subscribe(clients[n], n.lower())
    group, _ = await group_with_members(clients["Ana"], [clients["Bia"], clients["Caio"]])
    await clients["Ana"].post(f"/api/v1/groups/{group['id']}/draw")
    matches = {
        n: (await clients[n].get(f"/api/v1/groups/{group['id']}/my-match")).json()["name"]
        for n in names
    }
    return group, clients, matches


async def test_draw_enqueues_neutral_job_and_notifies_everyone(
    user_client: UserClientFactory, fake_push: FakePush
) -> None:
    group, _, _ = await _drawn_group(user_client)
    jobs = await (await queue.get_queue()).queued_jobs()
    draw_jobs = [j for j in jobs if j.function == "push_draw_done"]
    assert [j.args for j in draw_jobs] == [(group["id"],)]

    sent = await push_draw_done({}, group["id"])
    assert sent == 3
    assert {m["endpoint"] for m in fake_push.sent} == {FCM + "ana", FCM + "bia", FCM + "caio"}
    assert fake_push.sent[0]["data"]["url"] == f"/groups/{group['id']}?tab=draw"


async def test_chat_push_goes_to_the_other_side_without_revealing(
    user_client: UserClientFactory, fake_push: FakePush
) -> None:
    group, clients, matches = await _drawn_group(user_client)
    base = f"/api/v1/groups/{group['id']}"
    await (await queue.get_queue()).flushdb()

    await clients["Ana"].post(f"{base}/chats/match/messages", json={"body": "texto secreto"})
    jobs = [
        j
        for j in await (await queue.get_queue()).queued_jobs()
        if j.function == "push_chat_message"
    ]
    assert len(jobs) == 1
    assignment_id, role = jobs[0].args
    uuid.UUID(assignment_id)
    assert role == "receiver"
    job_dump = repr(jobs[0].args)
    for name in matches:
        assert name not in job_dump

    await push_chat_message({}, assignment_id, role)
    receiver = matches["Ana"]
    assert [m["endpoint"] for m in fake_push.sent] == [FCM + receiver.lower()]
    payload = fake_push.sent[0]["data"]
    assert "texto secreto" not in json.dumps(payload)
    assert "Ana" not in json.dumps(payload)
    assert payload["url"].endswith("?tab=chat")

    fake_push.sent.clear()
    await push_chat_message({}, assignment_id, "giver")
    assert [m["endpoint"] for m in fake_push.sent] == [FCM + "ana"]


async def test_expired_subscriptions_are_removed(
    user_client: UserClientFactory, fake_push: FakePush
) -> None:
    group, _, _ = await _drawn_group(user_client)
    fake_push.fail_with = {FCM + "bia": 410, FCM + "caio": 500}
    sent = await push_draw_done({}, group["id"])
    assert sent == 1
    async with get_sessionmaker()() as session:
        endpoints = {s.endpoint for s in (await session.scalars(select(PushSubscription))).all()}
    assert endpoints == {FCM + "ana", FCM + "caio"}  # 410 sai; 500 é temporário e fica


async def test_jobs_ignore_missing_records(fake_push: FakePush) -> None:
    missing = str(uuid.uuid4())
    assert await push_draw_done({}, missing) == 0
    assert await push_chat_message({}, missing, "giver") == 0

import httpx
import pytest
from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.modules.chat.models import ChatMessage
from tests.conftest import UserClientFactory
from tests.helpers import create_group, group_with_members

NAMES = ["Ana", "Bia", "Caio", "Duda"]


async def _drawn(
    user_client: UserClientFactory,
) -> tuple[str, dict[str, str], dict[str, httpx.AsyncClient], dict[str, str]]:
    clients = {n: await user_client(n) for n in NAMES}
    group, ids = await group_with_members(clients["Ana"], [clients[n] for n in NAMES[1:]])
    base = f"/api/v1/groups/{group['id']}"
    assert (await clients["Ana"].post(f"{base}/draw")).status_code == 200
    matches = {n: (await clients[n].get(f"{base}/my-match")).json()["name"] for n in NAMES}
    return base, ids, clients, matches


def _santa_of(matches: dict[str, str], name: str) -> str:
    return next(giver for giver, receiver in matches.items() if receiver == name)


async def test_giver_and_receiver_talk_anonymously(user_client: UserClientFactory) -> None:
    base, _, c, matches = await _drawn(user_client)
    receiver = matches["Ana"]

    sent = await c["Ana"].post(
        f"{base}/chats/match/messages", json={"body": "  Oi! Tamanho P ou M?  "}
    )
    assert sent.status_code == 201
    assert sent.json()["from_me"] is True and sent.json()["body"] == "Oi! Tamanho P ou M?"

    # Quem recebe vê a mensagem na conversa "santa", sem saber de quem é.
    threads = {t["thread"]: t for t in (await c[receiver].get(f"{base}/chats")).json()}
    assert threads["santa"]["title"] == "Seu amigo secreto"
    assert threads["santa"]["unread"] == 1
    page = (await c[receiver].get(f"{base}/chats/santa/messages")).json()
    assert [m["body"] for m in page["items"]] == ["Oi! Tamanho P ou M?"]
    assert page["items"][0]["from_me"] is False
    body = (await c[receiver].get(f"{base}/chats/santa/messages")).text
    assert "Ana" not in body and "giver" not in body and "participant" not in body

    reply = await c[receiver].post(f"{base}/chats/santa/messages", json={"body": "M, obrigada!"})
    assert reply.status_code == 201
    ana_view = (await c["Ana"].get(f"{base}/chats/match/messages")).json()["items"]
    assert [(m["body"], m["from_me"]) for m in ana_view] == [
        ("Oi! Tamanho P ou M?", True),
        ("M, obrigada!", False),
    ]
    ana_threads = {t["thread"]: t for t in (await c["Ana"].get(f"{base}/chats")).json()}
    assert ana_threads["match"]["title"] == receiver
    assert ana_threads["match"]["unread"] == 1
    assert ana_threads["match"]["last_message"]["body"] == "M, obrigada!"


async def test_mark_read(user_client: UserClientFactory) -> None:
    base, _, c, matches = await _drawn(user_client)
    receiver = matches["Ana"]
    await c["Ana"].post(f"{base}/chats/match/messages", json={"body": "Oi"})
    assert (await c[receiver].post(f"{base}/chats/santa/read")).status_code == 204
    threads = {t["thread"]: t for t in (await c[receiver].get(f"{base}/chats")).json()}
    assert threads["santa"]["unread"] == 0
    # As próprias mensagens não contam como não lidas para quem enviou.
    ana_threads = {t["thread"]: t for t in (await c["Ana"].get(f"{base}/chats")).json()}
    assert ana_threads["match"]["unread"] == 0


async def test_conversations_are_isolated_per_pair(user_client: UserClientFactory) -> None:
    base, _, c, matches = await _drawn(user_client)
    await c["Ana"].post(f"{base}/chats/match/messages", json={"body": "segredo da Ana"})
    receiver = matches["Ana"]
    for name in NAMES:
        if name in ("Ana", receiver):
            continue
        for thread in ("match", "santa"):
            text = (await c[name].get(f"{base}/chats/{thread}/messages")).text
            assert "segredo da Ana" not in text, (name, thread)


async def test_organizer_cannot_read_other_chats(user_client: UserClientFactory) -> None:
    base, _, c, matches = await _drawn(user_client)
    santa_of_ana = _santa_of(matches, "Ana")
    others = [n for n in NAMES if n != "Ana"]
    for name in others:
        await c[name].post(f"{base}/chats/match/messages", json={"body": f"msg de {name}"})
    visible = ""
    for thread in ("match", "santa"):
        visible += (await c["Ana"].get(f"{base}/chats/{thread}/messages")).text
    visible += (await c["Ana"].get(f"{base}/chats")).text
    for name in others:
        if name != santa_of_ana:
            assert f"msg de {name}" not in visible
    async with get_sessionmaker()():
        columns = set(ChatMessage.__table__.columns.keys())
    assert "participant_id" not in columns and "user_id" not in columns


async def test_pagination_and_polling(user_client: UserClientFactory) -> None:
    base, _, c, matches = await _drawn(user_client)
    for i in range(5):
        await c["Ana"].post(f"{base}/chats/match/messages", json={"body": f"m{i}"})
    first = (await c["Ana"].get(f"{base}/chats/match/messages", params={"limit": 2})).json()
    assert [m["body"] for m in first["items"]] == ["m3", "m4"]
    older = (
        await c["Ana"].get(
            f"{base}/chats/match/messages", params={"limit": 2, "before": first["next_cursor"]}
        )
    ).json()
    assert [m["body"] for m in older["items"]] == ["m1", "m2"]

    last_id = first["items"][-1]["id"]
    assert (await c["Ana"].get(f"{base}/chats/match/messages", params={"after": last_id})).json()[
        "items"
    ] == []
    await c[matches["Ana"]].post(f"{base}/chats/santa/messages", json={"body": "novidade"})
    new = (await c["Ana"].get(f"{base}/chats/match/messages", params={"after": last_id})).json()
    assert [m["body"] for m in new["items"]] == ["novidade"]


async def test_chat_rules(user_client: UserClientFactory) -> None:
    eva = await user_client("Eva")
    early = await create_group(eva, open_=True)
    response = await eva.get(f"/api/v1/groups/{early['id']}/chats")
    assert response.status_code == 409 and response.json()["error"]["code"] == "draw_not_done"

    base, _, c, _ = await _drawn(user_client)
    assert (
        await c["Ana"].post(f"{base}/chats/match/messages", json={"body": " "})
    ).status_code == 422
    too_long = await c["Ana"].post(f"{base}/chats/match/messages", json={"body": "x" * 1001})
    assert too_long.status_code == 422
    assert (await c["Ana"].get(f"{base}/chats/outro/messages")).status_code == 422
    outsider = await user_client("Zé")
    assert (await outsider.get(f"{base}/chats")).status_code == 404

    await c["Ana"].post(f"{base}/finish")
    closed = await c["Ana"].post(f"{base}/chats/match/messages", json={"body": "oi"})
    assert closed.status_code == 409
    assert (await c["Ana"].get(f"{base}/chats/match/messages")).status_code == 200


async def test_chat_rate_limit(user_client: UserClientFactory) -> None:
    base, _, c, _ = await _drawn(user_client)
    codes = [
        (await c["Ana"].post(f"{base}/chats/match/messages", json={"body": f"{i}"})).status_code
        for i in range(31)
    ]
    assert codes[:30] == [201] * 30 and codes[30] == 429


async def test_messages_never_logged(
    user_client: UserClientFactory, caplog: pytest.LogCaptureFixture
) -> None:
    base, _, c, _ = await _drawn(user_client)
    caplog.set_level("DEBUG")
    await c["Ana"].post(f"{base}/chats/match/messages", json={"body": "conteudo-privado-123"})
    assert not any(
        "conteudo-privado-123" in f"{r.getMessage()} {r.__dict__}" for r in caplog.records
    )
    async with get_sessionmaker()() as session:
        assert (await session.scalar(select(ChatMessage.body))) == "conteudo-privado-123"

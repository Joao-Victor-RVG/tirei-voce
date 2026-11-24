import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select, update

from app.core.db import get_sessionmaker
from app.modules.chat.models import ChatMessage
from app.modules.groups.models import Group
from app.modules.privacy.service import PrivacyService
from app.modules.users.models import User
from app.modules.wishlist.models import WishlistItem
from tests.conftest import UserClientFactory
from tests.helpers import DEFAULT_PASSWORD, create_group, group_with_members

NAMES = ["Ana", "Bia", "Caio", "Duda"]


async def _drawn(
    user_client: UserClientFactory,
) -> tuple[str, dict[str, httpx.AsyncClient], dict[str, str]]:
    clients = {n: await user_client(n) for n in NAMES}
    group, _ = await group_with_members(clients["Ana"], [clients[n] for n in NAMES[1:]])
    base = f"/api/v1/groups/{group['id']}"
    for name in NAMES:
        await clients[name].post(f"{base}/me/wishlist", json={"title": f"Presente da {name}"})
    await clients["Ana"].post(f"{base}/draw")
    matches = {n: (await clients[n].get(f"{base}/my-match")).json()["name"] for n in NAMES}
    return base, clients, matches


async def _count(model: type, *where: object) -> int:
    async with get_sessionmaker()() as session:
        stmt = select(func.count()).select_from(model)
        for w in where:
            stmt = stmt.where(w)  # type: ignore[arg-type]
        return int(await session.scalar(stmt) or 0)


async def test_export_contains_my_data_only(user_client: UserClientFactory) -> None:
    base, clients, matches = await _drawn(user_client)
    await clients["Bia"].post(f"{base}/chats/match/messages", json={"body": "msg da Bia"})
    receiver = matches["Bia"]
    await clients[receiver].post(f"{base}/chats/santa/messages", json={"body": "resposta"})

    response = await clients["Bia"].get("/api/v1/me/export")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    data = response.json()
    assert data["profile"]["email"] == "bia@example.com"
    group = data["groups"][0]
    assert [i["title"] for i in group["wishlist"]] == ["Presente da Bia"]
    assert [m["body"] for m in group["messages_sent"]] == ["msg da Bia"]
    assert "resposta" not in response.text  # mensagem dos outros não é dado dela


async def test_delete_requires_confirmation(user_client: UserClientFactory) -> None:
    ana = await user_client("Ana")
    wrong = await ana.post("/api/v1/me/delete", json={"password": "errada"})
    assert wrong.status_code == 403 and wrong.json()["error"]["code"] == "invalid_password"
    assert (await ana.get("/api/v1/me")).status_code == 200


async def test_delete_without_draws_removes_everything(user_client: UserClientFactory) -> None:
    ana = await user_client("Ana")
    bia = await user_client("Bia")
    group, _ = await group_with_members(ana, [bia])
    solo = await create_group(ana)
    await bia.post(f"/api/v1/groups/{group['id']}/me/wishlist", json={"title": "x"})

    response = await ana.post("/api/v1/me/delete", json={"password": DEFAULT_PASSWORD})
    assert response.json() == {"mode": "deleted"}
    assert await _count(User, User.email == "ana@example.com") == 0
    # Grupo com mais gente passou para a Bia; grupo só da Ana sumiu.
    detail = (await bia.get(f"/api/v1/groups/{group['id']}")).json()
    assert detail["my_role"] == "owner" and detail["owner"]["name"] == "Bia"
    assert await _count(Group, Group.id == uuid.UUID(solo["id"])) == 0
    assert (await ana.get("/api/v1/me")).status_code == 401


async def test_delete_after_draw_anonymizes_and_keeps_others_working(
    user_client: UserClientFactory,
) -> None:
    base, clients, matches = await _drawn(user_client)
    santa_of_caio = next(g for g, r in matches.items() if r == "Caio")
    await clients["Caio"].post(f"{base}/chats/match/messages", json={"body": "oi do Caio"})

    response = await clients["Caio"].post("/api/v1/me/delete", json={"password": DEFAULT_PASSWORD})
    assert response.json() == {"mode": "anonymized"}

    async with get_sessionmaker()() as session:
        caio = await session.scalar(select(User).where(User.name == "Participante removido"))
        assert caio is not None and caio.deleted_at is not None
        assert caio.email.endswith("@invalid.tireivoce") and caio.password_hash is None
        assert caio.is_active is False
    assert await _count(ChatMessage, ChatMessage.body == "oi do Caio") == 0
    assert await _count(WishlistItem, WishlistItem.title == "Presente da Caio") == 0

    # Quem tirou o Caio continua vendo o amigo secreto, agora anonimizado.
    match = (await clients[santa_of_caio].get(f"{base}/my-match")).json()
    assert match["name"] == "Participante removido" and match["wishlist"] == []
    # Login antigo não funciona mais.
    login = await clients["Caio"].post(
        "/api/v1/auth/login", json={"email": "caio@example.com", "password": DEFAULT_PASSWORD}
    )
    assert login.status_code == 401


async def test_owner_deletion_hands_group_to_co_organizer(user_client: UserClientFactory) -> None:
    base, clients, _ = await _drawn(user_client)
    people = {
        p["user"]["name"]: p["id"]
        for p in (await clients["Ana"].get(f"{base}/participants")).json()
    }
    await clients["Ana"].put(f"{base}/participants/{people['Duda']}/co-organizer")
    await clients["Ana"].post("/api/v1/me/delete", json={"password": DEFAULT_PASSWORD})
    detail = (await clients["Duda"].get(base)).json()
    assert detail["my_role"] == "owner"


async def test_retention_purges_old_data(user_client: UserClientFactory) -> None:
    base, clients, _ = await _drawn(user_client)
    gid = uuid.UUID(base.rsplit("/", 1)[-1])
    recent = await create_group(clients["Ana"], title="Recente")
    old = datetime.now(UTC) - timedelta(days=400)
    async with get_sessionmaker()() as session:
        await session.execute(
            update(Group).where(Group.id == gid).values(updated_at=old, event_at=old)
        )
        await session.execute(
            update(User).where(User.email == "bia@example.com").values(created_at=old)
        )
        await session.commit()
    lonely = await user_client("Zé", verified=False)
    async with get_sessionmaker()() as session:
        await session.execute(
            update(User).where(User.email == "zé@example.com").values(created_at=old)
        )
        await session.commit()
    assert lonely is not None

    async with get_sessionmaker()() as session:
        result = await PrivacyService(session).purge(datetime.now(UTC))
    assert result["groups"] == 1 and result["unverified_users"] == 1
    assert await _count(Group, Group.id == gid) == 0
    assert await _count(Group, Group.id == uuid.UUID(recent["id"])) == 1
    assert await _count(User, User.email == "bia@example.com") == 1  # verificada: fica

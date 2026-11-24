import httpx
from sqlalchemy import update

from app.core.db import get_sessionmaker
from app.modules.users.models import User
from tests.conftest import UserClientFactory
from tests.helpers import group_with_members


async def _make_admin(email: str) -> None:
    async with get_sessionmaker()() as session:
        await session.execute(update(User).where(User.email == email).values(is_admin=True))
        await session.commit()


async def _admin(user_client: UserClientFactory) -> httpx.AsyncClient:
    client = await user_client("Root")
    await _make_admin("root@example.com")
    return client


async def test_admin_area_is_hidden_from_regular_users(user_client: UserClientFactory) -> None:
    ana = await user_client("Ana")
    assert (await ana.get("/api/v1/admin/metrics")).status_code == 404
    assert (await ana.get("/api/v1/admin/users")).status_code == 404
    assert (await ana.get("/api/v1/me")).json()["is_admin"] is False
    promote = await ana.patch("/api/v1/me", json={"is_admin": True})
    assert promote.status_code == 422  # não dá para se promover pela API


async def test_metrics_are_aggregate(user_client: UserClientFactory) -> None:
    root = await _admin(user_client)
    clients = {n: await user_client(n) for n in ["Ana", "Bia", "Caio"]}
    group, _ = await group_with_members(clients["Ana"], [clients["Bia"], clients["Caio"]])
    base = f"/api/v1/groups/{group['id']}"
    await clients["Ana"].post(f"{base}/draw")
    await clients["Bia"].put(f"{base}/my-match/gift", json={"purchased": True})
    await clients["Ana"].post(f"{base}/chats/match/messages", json={"body": "segredo-admin"})

    response = await root.get("/api/v1/admin/metrics")
    assert response.status_code == 200
    m = response.json()
    assert m["users"] == {"total": 4, "last_7d": 4}
    assert m["groups"]["total"] == 1 and m["groups_by_status"]["DRAWN"] == 1
    assert m["groups_by_status"]["OPEN"] == 0
    assert m["draws"]["total"] == 1
    assert (m["gifts_purchased"], m["gifts_total"]) == (1, 3)
    assert m["chat_messages_7d"] == 1
    assert m["avg_group_size"] == 3.0
    assert "segredo-admin" not in response.text and "Bia" not in response.text


async def test_user_search_and_deactivation(user_client: UserClientFactory) -> None:
    root = await _admin(user_client)
    ana = await user_client("Ana")
    await user_client("Bia")

    found = (await root.get("/api/v1/admin/users", params={"q": "ANA@"})).json()
    assert [u["email"] for u in found["items"]] == ["ana@example.com"]
    all_users = (await root.get("/api/v1/admin/users", params={"limit": 2})).json()
    assert len(all_users["items"]) == 2 and all_users["next_cursor"]

    ana_id = found["items"][0]["id"]
    off = await root.post(f"/api/v1/admin/users/{ana_id}/deactivate")
    assert off.json()["is_active"] is False
    assert (await ana.get("/api/v1/me")).status_code == 401
    assert (await ana.post("/api/v1/auth/refresh")).status_code == 401  # sessões revogadas

    on = await root.post(f"/api/v1/admin/users/{ana_id}/activate")
    assert on.json()["is_active"] is True

    me = (await root.get("/api/v1/me")).json()
    assert me["is_admin"] is True
    self_off = await root.post(f"/api/v1/admin/users/{me['id']}/deactivate")
    assert self_off.status_code == 409
    missing = await root.post("/api/v1/admin/users/00000000-0000-7000-8000-000000000000/activate")
    assert missing.status_code == 404


async def test_admin_cannot_read_pairs_or_chats(user_client: UserClientFactory) -> None:
    root = await _admin(user_client)
    clients = {n: await user_client(n) for n in ["Ana", "Bia", "Caio"]}
    group, _ = await group_with_members(clients["Ana"], [clients["Bia"], clients["Caio"]])
    await clients["Ana"].post(f"/api/v1/groups/{group['id']}/draw")
    # Admin não é membro: as rotas do grupo continuam 404 para ele.
    for path in ["", "/participants", "/my-match", "/chats", "/gift-progress"]:
        assert (await root.get(f"/api/v1/groups/{group['id']}{path}")).status_code == 404

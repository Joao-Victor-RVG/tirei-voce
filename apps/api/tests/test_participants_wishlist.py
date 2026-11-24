import uuid

import httpx
import pytest
from sqlalchemy import update

from app.core.db import get_sessionmaker
from app.modules.groups.models import Group, GroupStatus
from tests.conftest import UserClientFactory
from tests.helpers import create_group, join


async def _group_with(
    user_client: UserClientFactory, *names: str
) -> tuple[dict[str, object], list[httpx.AsyncClient]]:
    owner = await user_client("Ana")
    group = await create_group(owner, open_=True)
    clients = [owner]
    for name in names:
        c = await user_client(name)
        assert (await join(c, str(group["invite_code"]))).status_code == 200
        clients.append(c)
    return group, clients


async def _force_status(group_id: object, status: GroupStatus) -> None:
    async with get_sessionmaker()() as session:
        await session.execute(
            update(Group).where(Group.id == uuid.UUID(str(group_id))).values(status=status)
        )
        await session.commit()


async def test_list_participants(user_client: UserClientFactory) -> None:
    group, (_ana, bia) = await _group_with(user_client, "Bia")
    response = await bia.get(f"/api/v1/groups/{group['id']}/participants")
    assert response.status_code == 200
    people = response.json()
    assert [(p["user"]["name"], p["role"], p["is_me"]) for p in people] == [
        ("Ana", "owner", False),
        ("Bia", "member", True),
    ]
    assert "email" not in people[0]["user"]  # e-mail dos outros não vaza


async def test_participants_hidden_from_outsiders(user_client: UserClientFactory) -> None:
    group, _ = await _group_with(user_client)
    outsider = await user_client("Zé")
    assert (await outsider.get(f"/api/v1/groups/{group['id']}/participants")).status_code == 404


async def test_organizer_removes_participant(user_client: UserClientFactory) -> None:
    group, (ana, bia, caio) = await _group_with(user_client, "Bia", "Caio")
    people = (await ana.get(f"/api/v1/groups/{group['id']}/participants")).json()
    bia_id = next(p["id"] for p in people if p["user"]["name"] == "Bia")
    owner_id = next(p["id"] for p in people if p["role"] == "owner")

    assert (
        await caio.delete(f"/api/v1/groups/{group['id']}/participants/{bia_id}")
    ).status_code == 403
    owner_removal = await ana.delete(f"/api/v1/groups/{group['id']}/participants/{owner_id}")
    assert owner_removal.status_code == 409

    assert (
        await ana.delete(f"/api/v1/groups/{group['id']}/participants/{bia_id}")
    ).status_code == 204
    assert (await bia.get(f"/api/v1/groups/{group['id']}")).status_code == 404
    again = await ana.delete(f"/api/v1/groups/{group['id']}/participants/{bia_id}")
    assert again.status_code == 404

    # Pode voltar pelo convite enquanto estiver aberto.
    assert (await join(bia, str(group["invite_code"]))).json()["already_member"] is False
    assert (await bia.get(f"/api/v1/groups/{group['id']}")).status_code == 200


async def test_leave_group(user_client: UserClientFactory) -> None:
    group, (ana, bia) = await _group_with(user_client, "Bia")
    assert (await ana.post(f"/api/v1/groups/{group['id']}/leave")).status_code == 409
    assert (await bia.post(f"/api/v1/groups/{group['id']}/leave")).status_code == 204
    assert (await bia.get("/api/v1/groups")).json()["items"] == []


@pytest.mark.parametrize("status", [GroupStatus.DRAWN, GroupStatus.FINISHED])
async def test_participants_frozen_after_draw(
    user_client: UserClientFactory, status: GroupStatus
) -> None:
    group, (ana, bia) = await _group_with(user_client, "Bia")
    people = (await ana.get(f"/api/v1/groups/{group['id']}/participants")).json()
    bia_id = next(p["id"] for p in people if p["user"]["name"] == "Bia")
    await _force_status(group["id"], status)

    removal = await ana.delete(f"/api/v1/groups/{group['id']}/participants/{bia_id}")
    assert removal.status_code == 409 and removal.json()["error"]["code"] == "group_frozen"
    assert (await bia.post(f"/api/v1/groups/{group['id']}/leave")).status_code == 409


async def test_wishlist_crud(user_client: UserClientFactory) -> None:
    group, (ana,) = await _group_with(user_client)
    base = f"/api/v1/groups/{group['id']}/me/wishlist"

    created = await ana.post(
        base,
        json={
            "title": "Livro de receitas",
            "url": "https://loja.example/livro",
            "price_hint_cents": 7990,
            "priority": 1,
        },
    )
    assert created.status_code == 201, created.text
    item = created.json()
    await ana.post(base, json={"title": "Meias coloridas", "priority": 3})

    listed = (await ana.get(base)).json()
    assert [i["title"] for i in listed] == ["Livro de receitas", "Meias coloridas"]

    patched = await ana.patch(f"{base}/{item['id']}", json={"priority": 2, "url": None})
    assert patched.status_code == 200
    assert patched.json()["priority"] == 2 and patched.json()["url"] is None
    assert (await ana.patch(f"{base}/{item['id']}", json={"title": None})).status_code == 422

    assert (await ana.delete(f"{base}/{item['id']}")).status_code == 204
    assert (await ana.delete(f"{base}/{item['id']}")).status_code == 404
    assert len((await ana.get(base)).json()) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"title": ""},
        {"title": "X", "priority": 4},
        {"title": "X", "url": "javascript:alert(1)"},
        {"title": "X", "price_hint_cents": -1},
    ],
)
async def test_wishlist_validation(
    user_client: UserClientFactory, payload: dict[str, object]
) -> None:
    group, (ana,) = await _group_with(user_client)
    response = await ana.post(f"/api/v1/groups/{group['id']}/me/wishlist", json=payload)
    assert response.status_code == 422


async def test_wishlist_is_private(user_client: UserClientFactory) -> None:
    group, (ana, bia) = await _group_with(user_client, "Bia")
    base = f"/api/v1/groups/{group['id']}/me/wishlist"
    item = (await ana.post(base, json={"title": "Segredo da Ana"})).json()

    assert (await bia.get(base)).json() == []
    assert (await bia.patch(f"{base}/{item['id']}", json={"title": "x"})).status_code == 404
    assert (await bia.delete(f"{base}/{item['id']}")).status_code == 404


async def test_wishlist_limit(user_client: UserClientFactory) -> None:
    group, (ana,) = await _group_with(user_client)
    base = f"/api/v1/groups/{group['id']}/me/wishlist"
    for i in range(30):
        assert (await ana.post(base, json={"title": f"Item {i}"})).status_code == 201
    full = await ana.post(base, json={"title": "Mais um"})
    assert full.status_code == 409 and full.json()["error"]["code"] == "wishlist_full"


async def test_wishlist_editable_after_draw_but_not_after_finish(
    user_client: UserClientFactory,
) -> None:
    group, (ana,) = await _group_with(user_client)
    base = f"/api/v1/groups/{group['id']}/me/wishlist"
    await _force_status(group["id"], GroupStatus.DRAWN)
    assert (await ana.post(base, json={"title": "Ainda dá"})).status_code == 201
    await _force_status(group["id"], GroupStatus.FINISHED)
    assert (await ana.post(base, json={"title": "Não dá"})).status_code == 409
    assert (await ana.get(base)).status_code == 200


async def test_preferences(user_client: UserClientFactory) -> None:
    group, (ana, bia) = await _group_with(user_client, "Bia")
    url = f"/api/v1/groups/{group['id']}/me/preferences"
    assert (await ana.get(url)).json() == {"dislikes": None, "notes": None}

    saved = await ana.put(url, json={"dislikes": "Perfume, chocolate amargo", "notes": "Calço 37"})
    assert saved.status_code == 200
    assert (await ana.get(url)).json()["dislikes"] == "Perfume, chocolate amargo"

    cleared = await ana.put(url, json={"dislikes": "  "})
    assert cleared.json() == {"dislikes": None, "notes": None}
    assert (await bia.get(url)).json() == {"dislikes": None, "notes": None}

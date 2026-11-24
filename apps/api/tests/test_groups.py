import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import update

from app.core.db import get_sessionmaker
from app.modules.groups.models import Group, GroupStatus
from app.modules.groups.service import ALLOWED_TRANSITIONS
from tests.conftest import UserClientFactory
from tests.helpers import create_group, future, join


async def test_list_themes(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/themes")
    assert response.status_code == 200
    slugs = {t["slug"] for t in response.json()}
    assert slugs == {"amigo-secreto", "amigo-da-onca", "amigo-calcinha"}


async def test_create_group(user_client: UserClientFactory) -> None:
    owner = await user_client("Ana")
    group = await create_group(owner, theme_slug="amigo-da-onca", custom_name="Onça do Escritório")
    assert group["status"] == "DRAFT"
    assert group["my_role"] == "owner"
    assert group["participant_count"] == 1
    assert group["display_name"] == "Onça do Escritório"
    assert group["theme"]["emoji"] == "🐆"
    assert len(group["invite_code"]) >= 10
    assert group["prefer_single_cycle"] is True and group["max_participants"] == 100


async def test_create_group_requires_verified_email(user_client: UserClientFactory) -> None:
    unverified = await user_client("Bia", verified=False)
    response = await unverified.post(
        "/api/v1/groups", json={"theme_slug": "amigo-secreto", "title": "Teste"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "email_not_verified"


@pytest.mark.parametrize(
    "overrides, code",
    [
        ({"theme_slug": "nao-existe"}, "invalid_theme"),
        ({"min_value_cents": 5000, "max_value_cents": 100}, "validation_error"),
        ({"event_at": "2020-01-01T10:00:00Z"}, "invalid_date"),
        ({"event_at": "2030-01-01T10:00:00"}, "validation_error"),  # sem fuso
        ({"event_at": future(5), "join_deadline_at": future(10)}, "validation_error"),
        ({"max_participants": 2}, "validation_error"),
        ({"title": " "}, "validation_error"),
    ],
)
async def test_create_group_validation(
    user_client: UserClientFactory, overrides: dict[str, object], code: str
) -> None:
    owner = await user_client("Ana")
    payload = {"theme_slug": "amigo-secreto", "title": "Natal"} | overrides
    response = await owner.post("/api/v1/groups", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code


async def test_list_my_groups_paginated(user_client: UserClientFactory) -> None:
    ana = await user_client("Ana")
    bia = await user_client("Bia")
    ids = [(await create_group(ana, title=f"Grupo {i}"))["id"] for i in range(3)]
    await create_group(bia, title="Grupo da Bia")

    first = (await ana.get("/api/v1/groups", params={"limit": 2})).json()
    assert [g["id"] for g in first["items"]] == [ids[2], ids[1]]
    assert first["next_cursor"] == ids[1]
    second = (
        await ana.get("/api/v1/groups", params={"limit": 2, "cursor": first["next_cursor"]})
    ).json()
    assert [g["id"] for g in second["items"]] == [ids[0]]
    assert second["next_cursor"] is None
    assert second["items"][0]["participant_count"] == 1


async def test_non_member_gets_404(user_client: UserClientFactory) -> None:
    ana = await user_client("Ana")
    intruso = await user_client("Intruso")
    group = await create_group(ana)
    for method, path in [
        ("GET", ""),
        ("PATCH", ""),
        ("POST", "/open"),
        ("POST", "/invite-code/regenerate"),
    ]:
        response = await intruso.request(method, f"/api/v1/groups/{group['id']}{path}", json={})
        assert response.status_code == 404, (method, path)
        assert response.json()["error"]["code"] == "group_not_found"
    assert (await intruso.get(f"/api/v1/groups/{uuid.uuid4()}")).status_code == 404


async def test_member_cannot_do_organizer_actions(user_client: UserClientFactory) -> None:
    ana = await user_client("Ana")
    bia = await user_client("Bia")
    group = await create_group(ana, open_=True)
    assert (await join(bia, group["invite_code"])).status_code == 200

    detail = await bia.get(f"/api/v1/groups/{group['id']}")
    assert detail.status_code == 200 and detail.json()["my_role"] == "member"
    for path in ["/close", "/finish", "/invite-code/regenerate"]:
        response = await bia.post(f"/api/v1/groups/{group['id']}{path}")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "organizer_only"
    patch = await bia.patch(f"/api/v1/groups/{group['id']}", json={"title": "Hack"})
    assert patch.status_code == 403


async def test_update_group(user_client: UserClientFactory) -> None:
    ana = await user_client("Ana")
    group = await create_group(ana)
    response = await ana.patch(
        f"/api/v1/groups/{group['id']}",
        json={
            "title": "Natal 2026",
            "theme_slug": "amigo-calcinha",
            "event_maps_url": "https://maps.google.com/?q=casa",
            "custom_name": None,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["title"] == "Natal 2026"
    assert body["theme"]["slug"] == "amigo-calcinha"
    assert body["display_name"] == "Amigo Calcinha"
    assert body["event_maps_url"] == "https://maps.google.com/?q=casa"

    # Validação combinando com valores já salvos.
    bad = await ana.patch(f"/api/v1/groups/{group['id']}", json={"max_value_cents": 1000})
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "invalid_values"
    assert (
        await ana.patch(f"/api/v1/groups/{group['id']}", json={"title": None})
    ).status_code == 422


async def test_state_machine_happy_path(user_client: UserClientFactory) -> None:
    ana = await user_client("Ana")
    gid = (await create_group(ana))["id"]
    assert (await ana.post(f"/api/v1/groups/{gid}/open")).json()["status"] == "OPEN"
    assert (await ana.post(f"/api/v1/groups/{gid}/close")).json()["status"] == "CLOSED"
    assert (await ana.post(f"/api/v1/groups/{gid}/open")).json()["status"] == "OPEN"


@pytest.mark.parametrize(
    "status, action",
    [
        ("DRAFT", "close"),
        ("DRAFT", "finish"),
        ("OPEN", "open"),
        ("OPEN", "finish"),
        ("CLOSED", "close"),
        ("DRAWN", "open"),
        ("DRAWN", "close"),
        ("FINISHED", "open"),
        ("FINISHED", "finish"),
    ],
)
async def test_invalid_transitions_return_409(
    user_client: UserClientFactory, status: str, action: str
) -> None:
    ana = await user_client("Ana")
    gid = (await create_group(ana))["id"]
    await _force_status(gid, GroupStatus(status))
    response = await ana.post(f"/api/v1/groups/{gid}/{action}")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_status_transition"


async def test_drawn_to_finished(user_client: UserClientFactory) -> None:
    ana = await user_client("Ana")
    gid = (await create_group(ana))["id"]
    await _force_status(gid, GroupStatus.DRAWN)
    frozen = await ana.patch(f"/api/v1/groups/{gid}", json={"max_participants": 10})
    assert frozen.status_code == 409 and frozen.json()["error"]["code"] == "group_frozen"
    assert (
        await ana.patch(f"/api/v1/groups/{gid}", json={"event_location": "Praia"})
    ).status_code == 200

    assert (await ana.post(f"/api/v1/groups/{gid}/finish")).json()["status"] == "FINISHED"
    readonly = await ana.patch(f"/api/v1/groups/{gid}", json={"event_location": "Outro"})
    assert readonly.status_code == 409
    assert (await ana.post(f"/api/v1/groups/{gid}/invite-code/regenerate")).status_code == 409


def test_transition_table_never_reaches_draft() -> None:
    assert all(GroupStatus.DRAFT not in targets for targets in ALLOWED_TRANSITIONS.values())
    assert ALLOWED_TRANSITIONS[GroupStatus.FINISHED] == frozenset()


# --- Convites ---


async def test_invite_preview_is_public_and_minimal(
    user_client: UserClientFactory, client: httpx.AsyncClient
) -> None:
    ana = await user_client("Ana")
    group = await create_group(ana, open_=True)
    response = await client.get(f"/api/v1/invites/{group['invite_code']}")
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Natal da Família"
    assert body["organizer_name"] == "Ana"
    assert body["can_join"] is True
    assert "id" not in body and "invite_code" not in body and "owner" not in body

    assert (await client.get("/api/v1/invites/codigo-inexistente")).status_code == 404


async def test_join_flow(user_client: UserClientFactory) -> None:
    ana = await user_client("Ana")
    bia = await user_client("Bia")
    group = await create_group(ana, open_=True)

    first = await join(bia, group["invite_code"])
    assert first.status_code == 200
    assert first.json() == {"group_id": group["id"], "already_member": False}
    again = await join(bia, group["invite_code"])
    assert again.json()["already_member"] is True

    detail = (await ana.get(f"/api/v1/groups/{group['id']}")).json()
    assert detail["participant_count"] == 2
    listed = (await bia.get("/api/v1/groups")).json()["items"]
    assert [g["id"] for g in listed] == [group["id"]]


async def test_join_requires_verified_email(user_client: UserClientFactory) -> None:
    ana = await user_client("Ana")
    group = await create_group(ana, open_=True)
    unverified = await user_client("Bia", verified=False)
    response = await join(unverified, group["invite_code"])
    assert response.status_code == 403


@pytest.mark.parametrize("status", ["DRAFT", "CLOSED", "DRAWN", "FINISHED"])
async def test_join_only_when_open(user_client: UserClientFactory, status: str) -> None:
    ana = await user_client("Ana")
    bia = await user_client("Bia")
    group = await create_group(ana)
    await _force_status(group["id"], GroupStatus(status))
    response = await join(bia, group["invite_code"])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "join_not_allowed"
    preview = (await bia.get(f"/api/v1/invites/{group['invite_code']}")).json()
    assert preview["can_join"] is False and preview["reason"]


async def test_join_after_deadline(user_client: UserClientFactory) -> None:
    ana = await user_client("Ana")
    bia = await user_client("Bia")
    group = await create_group(ana, open_=True, join_deadline_at=future(1))
    async with get_sessionmaker()() as session:
        await session.execute(
            update(Group)
            .where(Group.id == uuid.UUID(group["id"]))
            .values(join_deadline_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await session.commit()
    response = await join(bia, group["invite_code"])
    assert response.status_code == 409
    assert "prazo" in response.json()["error"]["message"]


async def test_join_respects_max_participants_concurrently(
    user_client: UserClientFactory,
) -> None:
    ana = await user_client("Ana")
    group = await create_group(ana, open_=True, max_participants=3)
    others = [await user_client(f"Pessoa {i}") for i in range(4)]
    responses = await asyncio.gather(*(join(c, group["invite_code"]) for c in others))
    assert sorted(r.status_code for r in responses) == [200, 200, 409, 409]
    detail = (await ana.get(f"/api/v1/groups/{group['id']}")).json()
    assert detail["participant_count"] == 3

    too_low = await ana.patch(f"/api/v1/groups/{group['id']}", json={"max_participants": 3})
    assert too_low.status_code == 200


async def test_regenerate_invite_code(user_client: UserClientFactory) -> None:
    ana = await user_client("Ana")
    bia = await user_client("Bia")
    group = await create_group(ana, open_=True)
    response = await ana.post(f"/api/v1/groups/{group['id']}/invite-code/regenerate")
    new_code = response.json()["invite_code"]
    assert new_code != group["invite_code"]
    assert (await join(bia, group["invite_code"])).status_code == 404
    assert (await join(bia, new_code)).status_code == 200


async def test_join_rate_limited(user_client: UserClientFactory) -> None:
    bia = await user_client("Bia")
    codes = [(await join(bia, "codigo-invalido-x")).status_code for _ in range(21)]
    assert codes[:20] == [404] * 20 and codes[20] == 429


async def _force_status(group_id: str, status: GroupStatus) -> None:
    async with get_sessionmaker()() as session:
        await session.execute(
            update(Group).where(Group.id == uuid.UUID(group_id)).values(status=status)
        )
        await session.commit()

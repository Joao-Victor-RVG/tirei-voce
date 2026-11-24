import asyncio
import json
import re
import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.main import app
from app.modules.draws import crypto
from app.modules.draws.models import Draw, DrawAssignment
from tests.conftest import UserClientFactory
from tests.helpers import create_group, group_with_members, join

NAMES = ["Bia", "Caio", "Duda"]


async def _drawn_group(
    user_client: UserClientFactory, *, couple: bool = True
) -> tuple[str, dict[str, str], dict[str, httpx.AsyncClient]]:
    ana = await user_client("Ana")
    others = {n: await user_client(n) for n in NAMES}
    group, ids = await group_with_members(ana, list(others.values()))
    base = f"/api/v1/groups/{group['id']}"
    if couple:
        response = await ana.post(
            f"{base}/exclusion-circles",
            json={"name": "Casal Ana e Bia", "participant_ids": [ids["Ana"], ids["Bia"]]},
        )
        assert response.status_code == 201
    response = await ana.post(f"{base}/draw")
    assert response.status_code == 200, response.text
    return base, ids, {"Ana": ana, **others}


async def test_validate_reports_possible_and_impossible(user_client: UserClientFactory) -> None:
    ana = await user_client("Ana")
    others = [await user_client(n) for n in NAMES]
    group, ids = await group_with_members(ana, others)
    base = f"/api/v1/groups/{group['id']}"

    ok = (await ana.post(f"{base}/draw/validate")).json()
    assert ok["possible"] is True and ok["participant_count"] == 4

    # Ana, Bia e Caio na mesma família: impossível com 4 pessoas.
    await ana.post(
        f"{base}/exclusion-circles",
        json={"name": "Família", "participant_ids": [ids["Ana"], ids["Bia"], ids["Caio"]]},
    )
    bad = (await ana.post(f"{base}/draw/validate")).json()
    assert bad["possible"] is False
    assert "não existe sorteio possível" in bad["message"]
    assert {c["name"] for c in bad["most_constrained"]} == {"Ana", "Bia", "Caio"}

    draw = await ana.post(f"{base}/draw")
    assert draw.status_code == 422
    assert draw.json()["error"]["code"] == "draw_impossible"
    assert draw.json()["error"]["details"]["most_constrained"][0]["options"] == 1
    assert (await ana.get(f"/api/v1/groups/{group['id']}")).json()["status"] == "OPEN"


async def test_validate_and_draw_need_three_people(user_client: UserClientFactory) -> None:
    ana = await user_client("Ana")
    bia = await user_client("Bia")
    group, _ = await group_with_members(ana, [bia])
    base = f"/api/v1/groups/{group['id']}"
    validation = (await ana.post(f"{base}/draw/validate")).json()
    assert validation["possible"] is False and "pelo menos 3" in validation["message"]
    response = await ana.post(f"{base}/draw")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "not_enough_participants"


async def test_draw_happy_path_and_my_match(user_client: UserClientFactory) -> None:
    base, _ids, clients = await _drawn_group(user_client)
    group = (await clients["Ana"].get(base)).json()
    assert group["status"] == "DRAWN"

    await clients["Bia"].post(f"{base}/me/wishlist", json={"title": "Fone de ouvido"})
    await clients["Bia"].put(f"{base}/me/preferences", json={"dislikes": "Perfume"})

    matches: dict[str, str] = {}
    for name, client in clients.items():
        response = await client.get(f"{base}/my-match")
        assert response.status_code == 200
        match = response.json()
        matches[name] = match["name"]
        if match["name"] == "Bia":
            assert [i["title"] for i in match["wishlist"]] == ["Fone de ouvido"]
            assert match["preferences"]["dislikes"] == "Perfume"

    assert sorted(matches.values()) == sorted(matches.keys())  # permutação
    assert all(giver != receiver for giver, receiver in matches.items())
    assert matches["Ana"] != "Bia" and matches["Bia"] != "Ana"  # casal respeitado


async def test_draw_rejected_before_open_and_after_drawn(user_client: UserClientFactory) -> None:
    eva = await user_client("Eva")
    draft = await create_group(eva)
    response = await eva.post(f"/api/v1/groups/{draft['id']}/draw")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_status_transition"

    base, _, clients = await _drawn_group(user_client, couple=False)
    again = await clients["Ana"].post(f"{base}/draw")
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_drawn"


async def test_draw_freezes_rules_and_participants(user_client: UserClientFactory) -> None:
    base, ids, clients = await _drawn_group(user_client)
    ana = clients["Ana"]
    assert (await ana.get(f"{base}/exclusion-circles")).status_code == 200
    response = await ana.post(
        f"{base}/blocked-pairs",
        json={"giver_participant_id": ids["Caio"], "receiver_participant_id": ids["Duda"]},
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "group_frozen"
    assert (await ana.delete(f"{base}/participants/{ids['Caio']}")).status_code == 409
    assert (await clients["Caio"].post(f"{base}/leave")).status_code == 409


async def test_my_match_before_draw(user_client: UserClientFactory) -> None:
    ana = await user_client("Ana")
    group = await create_group(ana, open_=True)
    response = await ana.get(f"/api/v1/groups/{group['id']}/my-match")
    assert response.status_code == 409 and response.json()["error"]["code"] == "draw_not_done"


async def test_draw_only_by_organizer(user_client: UserClientFactory) -> None:
    ana = await user_client("Ana")
    others = [await user_client(n) for n in NAMES]
    group, _ = await group_with_members(ana, others)
    base = f"/api/v1/groups/{group['id']}"
    assert (await others[0].post(f"{base}/draw")).status_code == 403
    assert (await others[0].post(f"{base}/draw/validate")).status_code == 403
    outsider = await user_client("Zé")
    assert (await outsider.post(f"{base}/draw")).status_code == 404
    assert (await outsider.get(f"{base}/my-match")).status_code == 404


async def test_concurrent_draws_produce_a_single_draw(user_client: UserClientFactory) -> None:
    ana = await user_client("Ana")
    others = [await user_client(n) for n in NAMES]
    group, _ = await group_with_members(ana, others)
    base = f"/api/v1/groups/{group['id']}"
    responses = await asyncio.gather(*(ana.post(f"{base}/draw") for _ in range(5)))
    assert sorted(r.status_code for r in responses) == [200, 409, 409, 409, 409]
    async with get_sessionmaker()() as session:
        draws = (await session.scalars(select(Draw))).all()
    assert len(draws) == 1 and draws[0].version == 1


async def test_idempotency_key_returns_same_result(user_client: UserClientFactory) -> None:
    ana = await user_client("Ana")
    others = [await user_client(n) for n in NAMES]
    group, _ = await group_with_members(ana, others)
    base = f"/api/v1/groups/{group['id']}"
    headers = {"Idempotency-Key": "clique-123"}
    first, second = await asyncio.gather(
        ana.post(f"{base}/draw", headers=headers), ana.post(f"{base}/draw", headers=headers)
    )
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    third = await ana.post(f"{base}/draw", headers=headers)
    assert third.json() == first.json()
    other_key = await ana.post(f"{base}/draw", headers={"Idempotency-Key": "outro"})
    assert other_key.status_code == 409


async def test_join_blocked_after_draw(user_client: UserClientFactory) -> None:
    base, _, clients = await _drawn_group(user_client)
    group = (await clients["Ana"].get(base)).json()
    late = await user_client("Atrasado")
    assert (await join(late, group["invite_code"])).status_code == 409


# --- Sigilo ---


async def test_assignments_are_encrypted_at_rest(user_client: UserClientFactory) -> None:
    _base, ids, _ = await _drawn_group(user_client)
    async with get_sessionmaker()() as session:
        draw = await session.scalar(select(Draw))
        rows = (await session.scalars(select(DrawAssignment))).all()
    assert draw is not None and len(rows) == 4
    participant_ids = {uuid.UUID(v) for v in ids.values()}
    receivers = set()
    for row in rows:
        blob = bytes(row.receiver_encrypted)
        for pid in participant_ids:
            assert pid.bytes not in blob and str(pid).encode() not in blob
            assert str(pid) not in row.receiver_lookup_hash
        receiver = crypto.decrypt_receiver(blob)
        assert row.receiver_lookup_hash == crypto.receiver_lookup_hash(draw.id, receiver)
        receivers.add(receiver)
    assert receivers == participant_ids
    mapping = {r.giver_participant_id: crypto.decrypt_receiver(r.receiver_encrypted) for r in rows}
    assert draw.seed_hash == crypto.assignment_digest(draw.id, mapping)


def _fill_path(path: str, values: dict[str, str]) -> str:
    return re.sub(r"{(\w+)}", lambda m: values.get(m.group(1), str(uuid.uuid4())), path)


async def test_organizer_cannot_see_pairs_through_any_get_endpoint(
    user_client: UserClientFactory,
) -> None:
    """Varre todas as rotas GET da API como organizador e procura qualquer par alheio."""
    base, ids, clients = await _drawn_group(user_client)
    ana = clients["Ana"]
    group_id = base.rsplit("/", 1)[-1]
    my_receiver = (await ana.get(f"{base}/my-match")).json()["participant_id"]
    others_pairs = []
    for name, client in clients.items():
        if name != "Ana":
            receiver = (await client.get(f"{base}/my-match")).json()["participant_id"]
            others_pairs.append((ids[name], receiver))

    values = {"group_id": group_id, "participant_id": ids["Bia"], "code": "x" * 12}
    checked = 0
    get_paths = [p for p, ops in app.openapi()["paths"].items() if "get" in ops]
    for path in get_paths:
        if not path.startswith("/api/v1"):
            continue
        response = await ana.get(_fill_path(path, values))
        body = response.text
        checked += 1
        assert "receiver_encrypted" not in body and "lookup_hash" not in body, path
        for giver, receiver in others_pairs:
            if path.endswith("/my-match"):
                # O único par visível é o da própria Ana.
                assert json.loads(body)["participant_id"] == my_receiver
                continue
            data = _json_or_none(body)
            assert not _contains_pair(data, giver, receiver), path
    assert checked >= 10


async def test_draw_response_and_logs_have_no_pairs(
    user_client: UserClientFactory, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("DEBUG")
    ana = await user_client("Ana")
    others = [await user_client(n) for n in NAMES]
    group, ids = await group_with_members(ana, others)
    response = await ana.post(f"/api/v1/groups/{group['id']}/draw")
    assert set(response.json()) == {"draw_id", "version", "executed_at", "participant_count"}

    logged = "\n".join(
        f"{r.getMessage()} {r.__dict__}" for r in caplog.records if r.name.startswith("app")
    )
    non_owner_ids = [ids[n] for n in NAMES]
    for pid in non_owner_ids:
        assert pid not in logged


async def test_my_match_only_shows_own_receiver(user_client: UserClientFactory) -> None:
    base, ids, clients = await _drawn_group(user_client)
    seen = set()
    for client in clients.values():
        match = (await client.get(f"{base}/my-match")).json()
        assert set(match) == {
            "participant_id",
            "name",
            "avatar_url",
            "shirt_size",
            "shoe_size",
            "wishlist",
            "preferences",
            "gift_purchased",
        }
        seen.add(match["participant_id"])
    assert seen == set(ids.values())


def _json_or_none(body: str) -> Any:
    try:
        return json.loads(body)
    except ValueError:
        return None


def _contains_pair(data: Any, giver: str, receiver: str) -> bool:
    """True se algum objeto JSON associa o giver ao receiver."""
    if isinstance(data, dict):
        values = {str(v) for v in data.values() if not isinstance(v, (dict, list))}
        if giver in values and receiver in values:
            return True
        return any(_contains_pair(v, giver, receiver) for v in data.values())
    if isinstance(data, list):
        return any(_contains_pair(v, giver, receiver) for v in data)
    return False


# --- Presente comprado ---


async def test_gift_purchased_and_aggregate_progress(user_client: UserClientFactory) -> None:
    base, _ids, clients = await _drawn_group(user_client)
    ana = clients["Ana"]
    assert (await ana.get(f"{base}/gift-progress")).json() == {"purchased": 0, "total": 4}

    bia = clients["Bia"]
    assert (await bia.get(f"{base}/my-match")).json()["gift_purchased"] is False
    marked = await bia.put(f"{base}/my-match/gift", json={"purchased": True})
    assert marked.json() == {"purchased": True}
    assert (await bia.get(f"{base}/my-match")).json()["gift_purchased"] is True
    await clients["Caio"].put(f"{base}/my-match/gift", json={"purchased": True})

    progress = (await ana.get(f"{base}/gift-progress")).json()
    assert progress == {"purchased": 2, "total": 4}  # só números, sem nomes

    await bia.put(f"{base}/my-match/gift", json={"purchased": False})
    assert (await ana.get(f"{base}/gift-progress")).json()["purchased"] == 1


async def test_gift_progress_is_organizer_only_and_after_draw(
    user_client: UserClientFactory,
) -> None:
    base, _ids, clients = await _drawn_group(user_client)
    assert (await clients["Bia"].get(f"{base}/gift-progress")).status_code == 403

    eva = await user_client("Eva")
    fresh = await create_group(eva, open_=True)
    early = await eva.get(f"/api/v1/groups/{fresh['id']}/gift-progress")
    assert early.status_code == 409
    early_gift = await eva.put(
        f"/api/v1/groups/{fresh['id']}/my-match/gift", json={"purchased": True}
    )
    assert early_gift.status_code == 409


async def test_gift_status_read_only_after_finish(user_client: UserClientFactory) -> None:
    base, _ids, clients = await _drawn_group(user_client)
    await clients["Ana"].post(f"{base}/finish")
    response = await clients["Bia"].put(f"{base}/my-match/gift", json={"purchased": True})
    assert response.status_code == 409

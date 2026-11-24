import httpx

from tests.conftest import UserClientFactory
from tests.helpers import group_with_members


async def _setup(
    user_client: UserClientFactory, *names: str
) -> tuple[str, dict[str, str], httpx.AsyncClient, list[httpx.AsyncClient]]:
    ana = await user_client("Ana")
    others = [await user_client(n) for n in names]
    group, ids = await group_with_members(ana, others)
    return f"/api/v1/groups/{group['id']}", ids, ana, others


async def test_circle_crud(user_client: UserClientFactory) -> None:
    base, ids, ana, _ = await _setup(user_client, "Bia", "Caio", "Duda")
    created = await ana.post(
        f"{base}/exclusion-circles",
        json={"name": "Casal Ana e Bia", "participant_ids": [ids["Ana"], ids["Bia"], ids["Ana"]]},
    )
    assert created.status_code == 201, created.text
    circle = created.json()
    assert sorted(m["name"] for m in circle["members"]) == ["Ana", "Bia"]

    added = await ana.post(
        f"{base}/exclusion-circles/{circle['id']}/members", json={"participant_id": ids["Caio"]}
    )
    assert len(added.json()["members"]) == 3
    removed = await ana.delete(f"{base}/exclusion-circles/{circle['id']}/members/{ids['Caio']}")
    assert len(removed.json()["members"]) == 2
    too_small = await ana.delete(f"{base}/exclusion-circles/{circle['id']}/members/{ids['Bia']}")
    assert too_small.status_code == 422

    renamed = await ana.patch(
        f"{base}/exclusion-circles/{circle['id']}",
        json={"name": "Família", "participant_ids": [ids["Caio"], ids["Duda"]]},
    )
    assert renamed.json()["name"] == "Família"
    assert sorted(m["name"] for m in renamed.json()["members"]) == ["Caio", "Duda"]

    assert len((await ana.get(f"{base}/exclusion-circles")).json()) == 1
    assert (await ana.delete(f"{base}/exclusion-circles/{circle['id']}")).status_code == 204
    assert (await ana.get(f"{base}/exclusion-circles")).json() == []


async def test_circle_validation(user_client: UserClientFactory) -> None:
    base, ids, ana, _ = await _setup(user_client, "Bia")
    one = await ana.post(
        f"{base}/exclusion-circles", json={"name": "Só eu", "participant_ids": [ids["Ana"]]}
    )
    assert one.status_code == 422
    dup = await ana.post(
        f"{base}/exclusion-circles",
        json={"name": "Dup", "participant_ids": [ids["Ana"], ids["Ana"]]},
    )
    assert dup.status_code == 422 and dup.json()["error"]["code"] == "circle_too_small"

    stranger = await user_client("Zé")
    _, zé_ids = await _setup_other(user_client, stranger)
    foreign = await ana.post(
        f"{base}/exclusion-circles",
        json={"name": "X", "participant_ids": [ids["Ana"], zé_ids["Zé"]]},
    )
    assert foreign.status_code == 422
    assert foreign.json()["error"]["code"] == "invalid_participant"


async def _setup_other(
    user_client: UserClientFactory, owner: httpx.AsyncClient
) -> tuple[dict[str, object], dict[str, str]]:
    return await group_with_members(owner, [])


async def test_blocked_pairs_crud(user_client: UserClientFactory) -> None:
    base, ids, ana, _ = await _setup(user_client, "Bia", "Caio")
    created = await ana.post(
        f"{base}/blocked-pairs",
        json={"giver_participant_id": ids["Bia"], "receiver_participant_id": ids["Caio"]},
    )
    assert created.status_code == 201
    pair = created.json()
    assert (pair["giver"]["name"], pair["receiver"]["name"], pair["bidirectional"]) == (
        "Bia",
        "Caio",
        False,
    )

    duplicate = await ana.post(
        f"{base}/blocked-pairs",
        json={"giver_participant_id": ids["Bia"], "receiver_participant_id": ids["Caio"]},
    )
    assert duplicate.status_code == 409
    same = await ana.post(
        f"{base}/blocked-pairs",
        json={"giver_participant_id": ids["Bia"], "receiver_participant_id": ids["Bia"]},
    )
    assert same.status_code == 422

    updated = await ana.patch(f"{base}/blocked-pairs/{pair['id']}", json={"bidirectional": True})
    assert updated.json()["bidirectional"] is True
    assert len((await ana.get(f"{base}/blocked-pairs")).json()) == 1
    assert (await ana.delete(f"{base}/blocked-pairs/{pair['id']}")).status_code == 204
    assert (await ana.delete(f"{base}/blocked-pairs/{pair['id']}")).status_code == 404


async def test_rules_are_organizer_only(user_client: UserClientFactory) -> None:
    base, ids, _, (bia,) = await _setup(user_client, "Bia")
    assert (await bia.get(f"{base}/exclusion-circles")).status_code == 403
    assert (await bia.get(f"{base}/blocked-pairs")).status_code == 403
    response = await bia.post(
        f"{base}/exclusion-circles",
        json={"name": "X", "participant_ids": [ids["Ana"], ids["Bia"]]},
    )
    assert response.status_code == 403
    outsider = await user_client("Zé")
    assert (await outsider.get(f"{base}/blocked-pairs")).status_code == 404


async def test_removed_participant_leaves_rules(user_client: UserClientFactory) -> None:
    base, ids, ana, _ = await _setup(user_client, "Bia", "Caio")
    circle = (
        await ana.post(
            f"{base}/exclusion-circles",
            json={"name": "Trio", "participant_ids": [ids["Ana"], ids["Bia"], ids["Caio"]]},
        )
    ).json()
    await ana.post(
        f"{base}/blocked-pairs",
        json={"giver_participant_id": ids["Caio"], "receiver_participant_id": ids["Ana"]},
    )
    assert (await ana.delete(f"{base}/participants/{ids['Caio']}")).status_code == 204

    circles = (await ana.get(f"{base}/exclusion-circles")).json()
    assert [m["name"] for m in circles[0]["members"]] == ["Ana", "Bia"]
    assert circles[0]["id"] == circle["id"]
    assert (await ana.get(f"{base}/blocked-pairs")).json() == []

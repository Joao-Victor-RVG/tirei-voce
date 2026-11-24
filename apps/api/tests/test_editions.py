import httpx

from tests.conftest import UserClientFactory
from tests.helpers import future, group_with_members, join


async def _edition(
    user_client: UserClientFactory, names: list[str]
) -> tuple[dict[str, object], dict[str, httpx.AsyncClient], dict[str, str]]:
    clients = {n: await user_client(n) for n in names}
    group, _ = await group_with_members(
        clients[names[0]], [clients[n] for n in names[1:]], description="Sem meias!"
    )
    base = f"/api/v1/groups/{group['id']}"
    assert (await clients[names[0]].post(f"{base}/draw")).status_code == 200
    matches = {n: (await clients[n].get(f"{base}/my-match")).json()["name"] for n in names}
    return group, clients, matches


async def _next_edition(
    clients: dict[str, httpx.AsyncClient], previous_id: object, *, avoid: bool = True
) -> tuple[str, dict[str, str]]:
    owner = next(iter(clients.values()))
    response = await owner.post(
        f"/api/v1/groups/{previous_id}/duplicate",
        json={"title": "Natal 2027", "event_at": future(300), "avoid_previous_pairs": avoid},
    )
    assert response.status_code == 201, response.text
    new = response.json()
    await owner.post(f"/api/v1/groups/{new['id']}/open")
    for client in list(clients.values())[1:]:
        assert (await join(client, new["invite_code"])).status_code == 200
    base = f"/api/v1/groups/{new['id']}"
    assert (await owner.post(f"{base}/draw")).status_code == 200
    return str(new["id"]), {
        n: (await c.get(f"{base}/my-match")).json()["name"] for n, c in clients.items()
    }


async def test_duplicate_copies_settings_not_people(user_client: UserClientFactory) -> None:
    group, clients, _ = await _edition(user_client, ["Ana", "Bia", "Caio"])
    response = await clients["Ana"].post(f"/api/v1/groups/{group['id']}/duplicate", json={})
    new = response.json()
    assert response.status_code == 201
    assert new["status"] == "DRAFT" and new["participant_count"] == 1
    assert new["title"] == group["title"] and new["description"] == "Sem meias!"
    assert new["min_value_cents"] == group["min_value_cents"]
    assert new["previous_group_id"] == group["id"] and new["avoid_previous_pairs"] is True
    assert new["invite_code"] != group["invite_code"]
    assert new["event_at"] is None


async def test_three_people_get_the_other_cycle(user_client: UserClientFactory) -> None:
    """Com 3 pessoas só existem dois ciclos: sem repetir, a nova edição é o ciclo inverso."""
    group, clients, first = await _edition(user_client, ["Ana", "Bia", "Caio"])
    _, second = await _next_edition(clients, group["id"])
    assert all(second[n] != first[n] for n in first)
    assert {first[second[n]] for n in second} == set(first)  # é mesmo o inverso


async def test_no_repeated_pairs_with_more_people(user_client: UserClientFactory) -> None:
    group, clients, first = await _edition(user_client, ["Ana", "Bia", "Caio", "Duda", "Edu"])
    _, second = await _next_edition(clients, group["id"])
    assert all(second[n] != first[n] for n in first)


async def test_option_off_allows_repeats_and_validation_sees_constraint(
    user_client: UserClientFactory,
) -> None:
    group, clients, first = await _edition(user_client, ["Ana", "Bia", "Caio"])
    owner = clients["Ana"]
    new = (await owner.post(f"/api/v1/groups/{group['id']}/duplicate", json={})).json()
    base = f"/api/v1/groups/{new['id']}"
    await owner.post(f"{base}/open")
    for n in ["Bia", "Caio"]:
        await join(clients[n], new["invite_code"])
    people = {p["user"]["name"]: p["id"] for p in (await owner.get(f"{base}/participants")).json()}
    # Sem repetir, sobra só o ciclo inverso, em que Ana tira quem a tirou antes. Bloqueando isso:
    santa_of_ana = next(n for n, r in first.items() if r == "Ana")
    await owner.post(
        f"{base}/blocked-pairs",
        json={
            "giver_participant_id": people["Ana"],
            "receiver_participant_id": people[santa_of_ana],
        },
    )
    assert (await owner.post(f"{base}/draw/validate")).json()["possible"] is False
    assert (await owner.patch(base, json={"avoid_previous_pairs": False})).status_code == 200
    assert (await owner.post(f"{base}/draw/validate")).json()["possible"] is True


async def test_duplicate_requires_organizer(user_client: UserClientFactory) -> None:
    group, clients, _ = await _edition(user_client, ["Ana", "Bia", "Caio"])
    response = await clients["Bia"].post(f"/api/v1/groups/{group['id']}/duplicate", json={})
    assert response.status_code == 403
    outsider = await user_client("Zé")
    assert (
        await outsider.post(f"/api/v1/groups/{group['id']}/duplicate", json={})
    ).status_code == 404
    past = await clients["Ana"].post(
        f"/api/v1/groups/{group['id']}/duplicate", json={"event_at": "2020-01-01T00:00:00Z"}
    )
    assert past.status_code == 422


async def test_previous_pairs_never_exposed(user_client: UserClientFactory) -> None:
    group, clients, _ = await _edition(user_client, ["Ana", "Bia", "Caio", "Duda"])
    new_id, _ = await _next_edition(clients, group["id"])
    owner = clients["Ana"]
    # As restrições da edição anterior não viram pares bloqueados visíveis.
    assert (await owner.get(f"/api/v1/groups/{new_id}/blocked-pairs")).json() == []
    validation = (await owner.post(f"/api/v1/groups/{new_id}/draw/validate")).json()
    assert set(validation) == {
        "possible",
        "participant_count",
        "min_participants",
        "message",
        "most_constrained",
    }

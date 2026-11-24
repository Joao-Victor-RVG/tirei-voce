import httpx

from tests.conftest import UserClientFactory
from tests.helpers import group_with_members

NAMES = ["Bia", "Caio", "Duda"]


async def _setup(
    user_client: UserClientFactory,
) -> tuple[str, dict[str, str], dict[str, httpx.AsyncClient]]:
    ana = await user_client("Ana")
    others = {n: await user_client(n) for n in NAMES}
    group, ids = await group_with_members(ana, list(others.values()))
    return f"/api/v1/groups/{group['id']}", ids, {"Ana": ana, **others}


async def test_owner_promotes_and_demotes(user_client: UserClientFactory) -> None:
    base, ids, c = await _setup(user_client)
    promoted = await c["Ana"].put(f"{base}/participants/{ids['Bia']}/co-organizer")
    assert promoted.status_code == 200 and promoted.json()["role"] == "co_owner"
    assert (await c["Bia"].get(base)).json()["my_role"] == "co_owner"

    demoted = await c["Ana"].delete(f"{base}/participants/{ids['Bia']}/co-organizer")
    assert demoted.json()["role"] == "member"
    assert (await c["Bia"].get(f"{base}/exclusion-circles")).status_code == 403


async def test_co_organizer_has_organizer_powers(user_client: UserClientFactory) -> None:
    base, ids, c = await _setup(user_client)
    await c["Ana"].put(f"{base}/participants/{ids['Bia']}/co-organizer")
    bia = c["Bia"]

    assert (await bia.patch(base, json={"event_location": "Praia"})).status_code == 200
    circle = await bia.post(
        f"{base}/exclusion-circles",
        json={"name": "Casal", "participant_ids": [ids["Caio"], ids["Duda"]]},
    )
    assert circle.status_code == 201
    assert (await bia.post(f"{base}/invite-code/regenerate")).status_code == 200
    assert (await bia.delete(f"{base}/participants/{ids['Duda']}")).status_code == 204
    assert (await bia.post(f"{base}/close")).status_code == 200
    assert (await bia.post(f"{base}/draw/validate")).json()["possible"] is True
    assert (await bia.post(f"{base}/draw")).status_code == 200


async def test_only_owner_manages_co_organizers(user_client: UserClientFactory) -> None:
    base, ids, c = await _setup(user_client)
    await c["Ana"].put(f"{base}/participants/{ids['Bia']}/co-organizer")
    bia = c["Bia"]

    promote = await bia.put(f"{base}/participants/{ids['Caio']}/co-organizer")
    assert promote.status_code == 403 and promote.json()["error"]["code"] == "owner_only"
    assert (
        await c["Caio"].put(f"{base}/participants/{ids['Duda']}/co-organizer")
    ).status_code == 403

    # Ninguém mexe no dono.
    owner = await c["Ana"].put(f"{base}/participants/{ids['Ana']}/co-organizer")
    assert owner.status_code == 409
    assert (await bia.delete(f"{base}/participants/{ids['Ana']}")).status_code == 409


async def test_co_organizer_cannot_remove_other_co_organizer(
    user_client: UserClientFactory,
) -> None:
    base, ids, c = await _setup(user_client)
    await c["Ana"].put(f"{base}/participants/{ids['Bia']}/co-organizer")
    await c["Ana"].put(f"{base}/participants/{ids['Caio']}/co-organizer")

    blocked = await c["Bia"].delete(f"{base}/participants/{ids['Caio']}")
    assert blocked.status_code == 403
    assert (await c["Ana"].delete(f"{base}/participants/{ids['Caio']}")).status_code == 204


async def test_co_organizer_can_leave_but_owner_cannot(user_client: UserClientFactory) -> None:
    base, ids, c = await _setup(user_client)
    await c["Ana"].put(f"{base}/participants/{ids['Bia']}/co-organizer")
    assert (await c["Bia"].post(f"{base}/leave")).status_code == 204
    assert (await c["Ana"].post(f"{base}/leave")).status_code == 409


async def test_co_organizer_cannot_see_pairs(user_client: UserClientFactory) -> None:
    base, ids, c = await _setup(user_client)
    await c["Ana"].put(f"{base}/participants/{ids['Bia']}/co-organizer")
    assert (await c["Bia"].post(f"{base}/draw")).status_code == 200
    match = (await c["Bia"].get(f"{base}/my-match")).json()
    assert set(match) >= {"participant_id", "name"}
    # Ela só enxerga o próprio par, como qualquer participante.
    receivers = {(await c[n].get(f"{base}/my-match")).json()["participant_id"] for n in c}
    assert len(receivers) == 4


async def test_role_changes_rejected_for_unknown_or_finished(
    user_client: UserClientFactory,
) -> None:
    base, ids, c = await _setup(user_client)
    missing = await c["Ana"].put(
        f"{base}/participants/00000000-0000-7000-8000-000000000000/co-organizer"
    )
    assert missing.status_code == 404
    await c["Ana"].post(f"{base}/draw")
    await c["Ana"].post(f"{base}/finish")
    finished = await c["Ana"].put(f"{base}/participants/{ids['Bia']}/co-organizer")
    assert finished.status_code == 409

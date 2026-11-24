import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import update

from app.core.db import get_sessionmaker
from app.modules.users.models import User

DEFAULT_PASSWORD = "Pa$$word-forte-42"


async def register(
    client: httpx.AsyncClient,
    email: str = "ana@example.com",
    *,
    name: str = "Ana",
    password: str = DEFAULT_PASSWORD,
    verified: bool = False,
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/auth/register", json={"name": name, "email": email, "password": password}
    )
    assert response.status_code == 201, response.text
    if verified:
        await mark_verified(email)
    data: dict[str, Any] = response.json()
    return data


async def mark_verified(email: str) -> None:
    async with get_sessionmaker()() as session:
        await session.execute(
            update(User)
            .where(User.email == email.lower())
            .values(email_verified_at=datetime.now(UTC))
        )
        await session.commit()


def token_from(message_text: str) -> str:
    match = re.search(r"token=([A-Za-z0-9_-]+)", message_text)
    assert match, message_text
    return match.group(1)


def future(days: int = 30) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


async def create_group(
    client: httpx.AsyncClient, *, open_: bool = False, **overrides: Any
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "theme_slug": "amigo-secreto",
        "title": "Natal da Família",
        "min_value_cents": 5000,
        "max_value_cents": 10000,
        "event_at": future(30),
        "event_location": "Casa da vó",
    } | overrides
    response = await client.post("/api/v1/groups", json=payload)
    assert response.status_code == 201, response.text
    group: dict[str, Any] = response.json()
    if open_:
        opened = await client.post(f"/api/v1/groups/{group['id']}/open")
        assert opened.status_code == 200, opened.text
        group = opened.json()
    return group


async def join(client: httpx.AsyncClient, invite_code: str) -> httpx.Response:
    return await client.post(f"/api/v1/invites/{invite_code}/join")


async def group_with_members(
    owner: httpx.AsyncClient, members: list[httpx.AsyncClient], **overrides: Any
) -> tuple[dict[str, Any], dict[str, str]]:
    """Cria um grupo aberto com os membros e devolve (grupo, {nome: participant_id})."""
    group = await create_group(owner, open_=True, **overrides)
    for member in members:
        response = await join(member, group["invite_code"])
        assert response.status_code == 200, response.text
    people = (await owner.get(f"/api/v1/groups/{group['id']}/participants")).json()
    return group, {p["user"]["name"]: p["id"] for p in people}

import re
from datetime import UTC, datetime
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

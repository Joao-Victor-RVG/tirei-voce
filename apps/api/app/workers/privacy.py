from datetime import UTC, datetime
from typing import Any

from app.core.db import get_sessionmaker
from app.modules.privacy.service import PrivacyService


async def retention_purge(ctx: dict[str, Any]) -> dict[str, int]:
    async with get_sessionmaker()() as session:
        return await PrivacyService(session).purge(datetime.now(UTC))

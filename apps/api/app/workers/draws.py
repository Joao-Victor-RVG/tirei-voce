from datetime import UTC, datetime
from typing import Any

from app.modules.draws.scheduled import run_scheduled_draws


async def scheduled_draws(ctx: dict[str, Any]) -> int:
    return await run_scheduled_draws(ctx["email_sender"], datetime.now(UTC))

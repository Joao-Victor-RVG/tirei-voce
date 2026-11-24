from datetime import UTC, datetime
from typing import Any

from app.core.db import get_sessionmaker
from app.modules.reminders.service import ReminderService


async def send_due_reminders(ctx: dict[str, Any]) -> int:
    async with get_sessionmaker()() as session:
        return await ReminderService(session, ctx["email_sender"]).send_due(datetime.now(UTC))

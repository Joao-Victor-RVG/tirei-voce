from datetime import UTC, datetime
from typing import Any

from app.core.db import get_sessionmaker
from app.modules.reminders.service import ReminderService


async def send_due_reminders(ctx: dict[str, Any]) -> int:
    async with get_sessionmaker()() as session:
        service = ReminderService(session, ctx["email_sender"], ctx.get("whatsapp_sender"))
        return await service.send_due(datetime.now(UTC))

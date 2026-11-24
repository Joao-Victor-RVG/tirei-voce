import logging
from typing import Any, ClassVar

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.queue import redis_settings
from app.core.sentry import init_sentry
from app.modules.notifications.email import EmailMessage, build_email_sender

logger = logging.getLogger(__name__)


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    init_sentry(settings)
    ctx["email_sender"] = build_email_sender(settings)


async def send_email(ctx: dict[str, Any], payload: dict[str, Any]) -> None:
    message = EmailMessage.from_dict(payload)
    await ctx["email_sender"].send(message)
    logger.info("email_delivered", extra={"subject": message.subject})


class WorkerSettings:
    functions: ClassVar[list[Any]] = [send_email]
    on_startup = startup
    redis_settings = redis_settings()
    max_tries = 5
    job_timeout = 30

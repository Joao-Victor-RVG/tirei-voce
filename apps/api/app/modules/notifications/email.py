import logging
from dataclasses import asdict, dataclass
from typing import Any, Protocol

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    html: str
    text: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EmailMessage":
        return cls(**{k: str(data[k]) for k in ("to", "subject", "html", "text")})


class EmailSender(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailSender:
    """Dev: só imprime o e-mail no log (o link de verificação aparece aqui)."""

    async def send(self, message: EmailMessage) -> None:
        logger.info(
            "email_sent_to_console",
            extra={"to": message.to, "subject": message.subject, "body": message.text},
        )


class ResendEmailSender:
    API_URL = "https://api.resend.com/emails"

    def __init__(self, api_key: str, sender: str, client: httpx.AsyncClient | None = None) -> None:
        self.api_key = api_key
        self.sender = sender
        self.client = client or httpx.AsyncClient(timeout=10)

    async def send(self, message: EmailMessage) -> None:
        response = await self.client.post(
            self.API_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "from": self.sender,
                "to": [message.to],
                "subject": message.subject,
                "html": message.html,
                "text": message.text,
            },
        )
        response.raise_for_status()


def build_email_sender(settings: Settings) -> EmailSender:
    if settings.email_provider == "resend":
        assert settings.resend_api_key, "RESEND_API_KEY ausente"  # noqa: S101
        return ResendEmailSender(settings.resend_api_key, settings.email_from)
    return ConsoleEmailSender()

from typing import Protocol

from app.core import queue
from app.modules.notifications.email import EmailMessage


class EmailOutbox(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class QueuedEmailOutbox:
    """Enfileira o e-mail para o worker (arq): a requisição não espera o provedor."""

    async def send(self, message: EmailMessage) -> None:
        await queue.enqueue("send_email", message.to_dict())


def get_email_outbox() -> EmailOutbox:
    return QueuedEmailOutbox()

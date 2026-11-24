"""Eventos que geram notificações. Os jobs carregam só ids neutros: o worker descobre
quem notificar, para nenhum par do sorteio ficar gravado na fila."""

import logging
import uuid

from app.core import queue

logger = logging.getLogger(__name__)


async def _enqueue(function: str, *args: str) -> None:
    try:
        await queue.enqueue(function, *args)
    except Exception:  # notificação nunca deve derrubar a ação principal
        logger.warning("notification_enqueue_failed", extra={"job": function}, exc_info=True)


async def draw_done(group_id: uuid.UUID) -> None:
    await _enqueue("push_draw_done", str(group_id))


async def chat_message(assignment_id: uuid.UUID, recipient_role: str) -> None:
    await _enqueue("push_chat_message", str(assignment_id), recipient_role)

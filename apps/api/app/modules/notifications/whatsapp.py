"""Interface de envio por WhatsApp. Nenhum provedor real ainda (decisão da Fase 3).

Para plugar a WhatsApp Cloud API (Meta) ou a Twilio: implemente WhatsAppSender.send com
httpx, usando os templates aprovados (nome + parâmetros), e devolva-o em
build_whatsapp_sender quando WHATSAPP_PROVIDER apontar para ele.
"""

import logging
import re
from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings

logger = logging.getLogger(__name__)

# Templates precisam ser aprovados pela Meta antes do uso; os nomes ficam centralizados aqui.
TEMPLATE_REMINDER = "lembrete_evento"
TEMPLATE_DRAW_DONE = "sorteio_realizado"


@dataclass(frozen=True)
class WhatsAppMessage:
    to: str  # E.164, ex.: +5511987654321
    template: str
    params: tuple[str, ...]


class WhatsAppSender(Protocol):
    async def send(self, message: WhatsAppMessage) -> None: ...


class ConsoleWhatsAppSender:
    """Dev: só registra no log que a mensagem sairia (sem o número completo)."""

    async def send(self, message: WhatsAppMessage) -> None:
        logger.info(
            "whatsapp_sent_to_console",
            extra={
                "to": mask_phone(message.to),
                "template": message.template,
                "params": message.params,
            },
        )


def build_whatsapp_sender(settings: Settings) -> WhatsAppSender | None:
    if settings.whatsapp_provider == "console":
        return ConsoleWhatsAppSender()
    return None


_DIGITS = re.compile(r"\D+")


def normalize_br_phone(raw: str) -> str | None:
    """Aceita "(11) 98765-4321", "11987654321" ou "+55 11 98765-4321" → "+5511987654321"."""
    digits = _DIGITS.sub("", raw)
    if digits.startswith("55") and len(digits) in (12, 13):
        digits = digits[2:]
    if len(digits) not in (10, 11) or digits[0] == "0":
        return None
    if len(digits) == 11 and digits[2] != "9":  # celular com 9 dígitos começa com 9
        return None
    return "+55" + digits


def mask_phone(phone: str) -> str:
    return phone[:5] + "*" * max(len(phone) - 7, 0) + phone[-2:]

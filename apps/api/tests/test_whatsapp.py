from datetime import UTC, datetime, timedelta

import pytest

from app.core.db import get_sessionmaker
from app.modules.notifications.whatsapp import (
    ConsoleWhatsAppSender,
    WhatsAppMessage,
    build_whatsapp_sender,
    mask_phone,
    normalize_br_phone,
)
from app.modules.reminders.service import ReminderService
from tests.conftest import UserClientFactory
from tests.helpers import group_with_members
from tests.test_reminders import CaptureSender, _set


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("(11) 98765-4321", "+5511987654321"),
        ("+55 11 98765-4321", "+5511987654321"),
        ("1132654321", "+551132654321"),
        ("98765-4321", None),
        ("(11) 88765-4321", None),
        ("abc", None),
    ],
)
def test_normalize_br_phone(raw: str, expected: str | None) -> None:
    assert normalize_br_phone(raw) == expected


def test_mask_phone_and_builder() -> None:
    assert mask_phone("+5511987654321") == "+5511*******21"
    from app.core.config import Settings

    assert build_whatsapp_sender(Settings()) is None
    assert isinstance(
        build_whatsapp_sender(Settings(whatsapp_provider="console")), ConsoleWhatsAppSender
    )


async def test_phone_and_opt_in_on_profile(user_client: UserClientFactory) -> None:
    ana = await user_client("Ana")
    needs_phone = await ana.patch("/api/v1/me", json={"whatsapp_opt_in": True})
    assert (
        needs_phone.status_code == 422 and needs_phone.json()["error"]["code"] == "phone_required"
    )
    bad = await ana.patch("/api/v1/me", json={"phone": "123"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_phone"

    ok = await ana.patch("/api/v1/me", json={"phone": "(11) 98765-4321", "whatsapp_opt_in": True})
    assert (ok.json()["phone"], ok.json()["whatsapp_opt_in"]) == ("+5511987654321", True)
    cleared = await ana.patch("/api/v1/me", json={"phone": ""})
    assert (cleared.json()["phone"], cleared.json()["whatsapp_opt_in"]) == (None, False)


async def test_config_exposes_whatsapp_flag(user_client: UserClientFactory) -> None:
    ana = await user_client("Ana")
    assert (await ana.get("/api/v1/auth/config")).json()["whatsapp_enabled"] is False


class CaptureWhatsApp:
    def __init__(self) -> None:
        self.messages: list[WhatsAppMessage] = []

    async def send(self, message: WhatsAppMessage) -> None:
        self.messages.append(message)


async def test_reminders_go_to_opted_in_phones_only(user_client: UserClientFactory) -> None:
    clients = {n: await user_client(n) for n in ["Ana", "Bia", "Caio"]}
    await clients["Bia"].patch("/api/v1/me", json={"phone": "11987654321", "whatsapp_opt_in": True})
    await clients["Caio"].patch("/api/v1/me", json={"phone": "11912345678"})  # sem opt-in
    group, _ = await group_with_members(clients["Ana"], [clients["Bia"], clients["Caio"]])
    now = datetime.now(UTC)
    await _set(group["id"], event_at=now + timedelta(hours=10))

    whatsapp = CaptureWhatsApp()
    async with get_sessionmaker()() as session:
        await ReminderService(session, CaptureSender(), whatsapp).send_due(now)
    assert [m.to for m in whatsapp.messages] == ["+5511987654321"]
    assert whatsapp.messages[0].template == "lembrete_evento"

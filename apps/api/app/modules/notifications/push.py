"""Envio de Web Push. Roda no worker; a API só enfileira jobs sem dados sensíveis."""

import asyncio
import json
import logging
import uuid
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from functools import lru_cache
from urllib.parse import urlsplit

from py_vapid import Vapid
from pywebpush import WebPushException, webpush
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.notifications.models import PushSubscription

logger = logging.getLogger(__name__)

# Só serviços de push conhecidos: o worker faz POST para essas URLs (evita SSRF).
ALLOWED_PUSH_HOSTS = (
    "fcm.googleapis.com",
    "android.googleapis.com",
    "updates.push.services.mozilla.com",
    "push.services.mozilla.com",
    "web.push.apple.com",
    ".push.apple.com",
    ".notify.windows.com",
)

PUSH_TTL_SECONDS = 24 * 3600


def is_allowed_endpoint(endpoint: str) -> bool:
    parts = urlsplit(endpoint)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host:
        return False
    return any(host == h or (h.startswith(".") and host.endswith(h)) for h in ALLOWED_PUSH_HOSTS)


@dataclass(frozen=True)
class PushMessage:
    title: str
    body: str
    url: str
    tag: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


@lru_cache
def _vapid() -> Vapid:
    key = get_settings().vapid_private_key
    assert key, "VAPID_PRIVATE_KEY ausente"  # noqa: S101
    return Vapid.from_raw(key.encode())


def _send_one(sub: PushSubscription, payload: str) -> int | None:
    """Envia para uma inscrição. Retorna o status HTTP em caso de erro do serviço de push."""
    try:
        webpush(
            subscription_info={
                "endpoint": sub.endpoint,
                "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
            },
            data=payload,
            vapid_private_key=_vapid(),
            vapid_claims={"sub": get_settings().vapid_subject},
            ttl=PUSH_TTL_SECONDS,
            timeout=10,
        )
    except WebPushException as exc:
        return exc.response.status_code if exc.response is not None else 0
    return None


async def send_to_users(
    session: AsyncSession, user_ids: Iterable[uuid.UUID], message: PushMessage
) -> int:
    """Envia para todos os aparelhos dos usuários; remove inscrições expiradas (404/410)."""
    if not get_settings().push_enabled:
        return 0
    ids = list(set(user_ids))
    if not ids:
        return 0
    subs = (
        await session.scalars(select(PushSubscription).where(PushSubscription.user_id.in_(ids)))
    ).all()
    payload = message.to_json()
    sent, expired = 0, []
    for sub in subs:
        if not is_allowed_endpoint(sub.endpoint):
            expired.append(sub.id)
            continue
        status = await asyncio.to_thread(_send_one, sub, payload)
        if status in (404, 410):
            expired.append(sub.id)
        elif status is None:
            sub.last_sent_at = datetime.now(UTC)
            sent += 1
        else:
            logger.warning("push_failed", extra={"status": status, "tag": message.tag})
    if expired:
        await session.execute(delete(PushSubscription).where(PushSubscription.id.in_(expired)))
    await session.commit()
    return sent

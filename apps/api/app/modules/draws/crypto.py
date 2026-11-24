import hashlib
import hmac
import uuid
from collections.abc import Mapping
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    return Fernet(get_settings().draw_encryption_key.encode())


def _hmac(message: str) -> str:
    key = get_settings().draw_hmac_key.encode()
    return hmac.new(key, message.encode(), hashlib.sha256).hexdigest()


def encrypt_receiver(receiver_id: uuid.UUID) -> bytes:
    return _fernet().encrypt(receiver_id.bytes)


def decrypt_receiver(token: bytes) -> uuid.UUID:
    try:
        return uuid.UUID(bytes=_fernet().decrypt(token))
    except (InvalidToken, ValueError) as exc:
        raise RuntimeError("draw assignment could not be decrypted") from exc


def receiver_lookup_hash(draw_id: uuid.UUID, receiver_id: uuid.UUID) -> str:
    """Permite achar "quem me tirou" (chat anônimo, Fase 2) sem guardar o par em claro."""
    return _hmac(f"lookup:{draw_id}:{receiver_id}")


def assignment_digest(draw_id: uuid.UUID, assignment: Mapping[uuid.UUID, uuid.UUID]) -> str:
    canonical = ",".join(f"{g}>{r}" for g, r in sorted(assignment.items()))
    return _hmac(f"draw:{draw_id}:{canonical}")

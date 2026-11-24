import secrets
import time
import uuid


def uuid7() -> uuid.UUID:
    """UUID versão 7 (RFC 9562): 48 bits de timestamp em ms + 74 bits aleatórios.

    Ordenável por tempo, o que mantém os índices B-tree compactos.
    """
    timestamp_ms = time.time_ns() // 1_000_000
    raw = bytearray(timestamp_ms.to_bytes(6, "big") + secrets.token_bytes(10))
    raw[6] = (raw[6] & 0x0F) | 0x70  # versão 7
    raw[8] = (raw[8] & 0x3F) | 0x80  # variante RFC
    return uuid.UUID(bytes=bytes(raw))

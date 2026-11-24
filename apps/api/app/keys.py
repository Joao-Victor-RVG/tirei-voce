"""Gera segredos para o .env. Uso: python -m app.keys (ou make keys)."""

import base64
import secrets

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def vapid_keys() -> tuple[str, str]:
    """(público, privado) em base64url: o público vai para o navegador (applicationServerKey)."""
    key = ec.generate_private_key(ec.SECP256R1())
    private_raw = key.private_numbers().private_value.to_bytes(32, "big")
    public_raw = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return _b64url(public_raw), _b64url(private_raw)


def main() -> None:
    public, private = vapid_keys()
    lines = [
        f"JWT_SECRET={secrets.token_urlsafe(48)}",
        f"DRAW_ENCRYPTION_KEY={Fernet.generate_key().decode()}",
        f"DRAW_HMAC_KEY={secrets.token_urlsafe(48)}",
        f"VAPID_PUBLIC_KEY={public}",
        f"VAPID_PRIVATE_KEY={private}",
    ]
    print("\n".join(lines))


if __name__ == "__main__":
    main()

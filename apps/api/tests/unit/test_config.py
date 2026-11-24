from typing import Any

import pytest

from app.core.config import Settings


def prod(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": "production",
        "cookie_secure": True,  # o conftest define COOKIE_SECURE=false no ambiente
        "jwt_secret": "x" * 40,
        "draw_encryption_key": "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXphYmNkZWY=",
        "draw_hmac_key": "y" * 40,
    } | overrides
    return Settings(**values)


@pytest.mark.parametrize(
    "url",
    [
        "postgres://u:p@h:5432/db",
        "postgresql://u:p@h:5432/db",
        "postgresql+asyncpg://u:p@h:5432/db",
    ],
)
def test_database_url_is_normalized_to_asyncpg(url: str) -> None:
    assert Settings(database_url=url).database_url == "postgresql+asyncpg://u:p@h:5432/db"


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"jwt_secret": "dev-insecure-jwt-secret-change-me-0123456789"}, "JWT_SECRET"),
        ({"jwt_secret": "curto"}, "JWT_SECRET"),
        (
            {"draw_encryption_key": "ZGV2LWluc2VjdXJlLWRyYXcta2V5LTAxMjM0NTY3ODk="},
            "DRAW_ENCRYPTION_KEY",
        ),
        ({"draw_hmac_key": "curto"}, "DRAW_HMAC_KEY"),
        ({"cookie_secure": False}, "COOKIE_SECURE"),
        ({"email_provider": "resend"}, "RESEND_API_KEY"),
    ],
)
def test_production_rejects_unsafe_config(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        prod(**overrides)


def test_production_accepts_real_secrets() -> None:
    assert prod().is_production

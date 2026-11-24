import asyncio
import os
from collections.abc import AsyncIterator
from urllib.parse import urlsplit, urlunsplit

# Precisa vir antes de qualquer import do app: as settings são lidas uma vez.
_BASE_DB = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://tirei:tirei@localhost:5432/tirei_voce_test"
)
os.environ["DATABASE_URL"] = _BASE_DB
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ["ENVIRONMENT"] = "test"

import asyncpg
import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.core.db import get_engine
from app.core.redis import get_redis
from app.main import app
from app.models import Base


async def _ensure_database(url: str) -> None:
    parts = urlsplit(url.replace("+asyncpg", ""))
    db_name = parts.path.lstrip("/")
    admin_url = urlunsplit(parts._replace(path="/postgres"))
    conn = await asyncpg.connect(admin_url)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await conn.close()


def _run_migrations(url: str) -> None:
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.attributes["database_url"] = url
    cfg.attributes["configure_logger"] = False
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session", autouse=True)
async def _database() -> AsyncIterator[None]:
    await _ensure_database(_BASE_DB)
    await asyncio.to_thread(_run_migrations, _BASE_DB)
    yield
    await get_engine().dispose()
    await get_redis().aclose()


@pytest.fixture(autouse=True)
async def _clean_state() -> AsyncIterator[None]:
    yield
    tables = [t.name for t in reversed(Base.metadata.sorted_tables)]
    if tables:
        async with get_engine().begin() as conn:
            await conn.execute(text(f"TRUNCATE {', '.join(tables)} CASCADE"))
    await get_redis().flushdb()


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c

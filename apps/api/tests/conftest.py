import asyncio
import os
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import AsyncExitStack
from urllib.parse import urlsplit, urlunsplit

# Precisa vir antes de qualquer import do app: as settings são lidas uma vez.
_BASE_DB = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://tirei:tirei@localhost:5432/tirei_voce_test"
)
os.environ["DATABASE_URL"] = _BASE_DB
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ["ENVIRONMENT"] = "test"
os.environ["COOKIE_SECURE"] = "false"  # o cliente de teste usa http

import asyncpg
import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.core.db import get_engine, get_sessionmaker
from app.core.redis import get_redis
from app.main import app
from app.models import Base
from app.modules.notifications.email import EmailMessage
from app.modules.notifications.service import get_email_outbox
from app.seed import seed_themes

# Dados de referência: semeados uma vez e preservados entre os testes.
_PRESERVED_TABLES = {"group_themes"}


class MemoryOutbox:
    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.messages.append(message)

    def last_to(self, to: str) -> EmailMessage:
        return next(m for m in reversed(self.messages) if m.to == to)


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
    async with get_sessionmaker()() as session:
        await seed_themes(session)
    yield
    await get_engine().dispose()
    await get_redis().aclose()


@pytest.fixture(autouse=True)
def outbox() -> Iterator[MemoryOutbox]:
    box = MemoryOutbox()
    app.dependency_overrides[get_email_outbox] = lambda: box
    yield box
    app.dependency_overrides.pop(get_email_outbox, None)


@pytest.fixture(autouse=True)
async def _clean_state() -> AsyncIterator[None]:
    yield
    tables = [
        t.name for t in reversed(Base.metadata.sorted_tables) if t.name not in _PRESERVED_TABLES
    ]
    if tables:
        async with get_engine().begin() as conn:
            await conn.execute(text(f"TRUNCATE {', '.join(tables)} CASCADE"))
    await get_redis().flushdb()


def make_client() -> httpx.AsyncClient:
    """Cliente que, como o frontend, reenvia o cookie CSRF no header X-CSRF-Token."""

    async def add_csrf(request: httpx.Request) -> None:
        token = http.cookies.get("tv_csrf")
        if token and "X-CSRF-Token" not in request.headers:
            request.headers["X-CSRF-Token"] = token

    http = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        event_hooks={"request": [add_csrf]},
    )
    return http


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async with make_client() as c:
        await c.get("/api/v1/auth/csrf")
        yield c


UserClientFactory = Callable[..., Awaitable[httpx.AsyncClient]]


@pytest.fixture
async def user_client() -> AsyncIterator[UserClientFactory]:
    """Cria clientes já logados (e verificados), cada um com seu próprio usuário."""
    from tests.helpers import register

    async with AsyncExitStack() as stack:

        async def factory(name: str = "Ana", *, verified: bool = True) -> httpx.AsyncClient:
            c = await stack.enter_async_context(make_client())
            await c.get("/api/v1/auth/csrf")
            email = f"{name.lower().replace(' ', '.')}@example.com"
            await register(c, email, name=name, verified=verified)
            return c

        yield factory

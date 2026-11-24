from typing import Any

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings

from app.core.config import get_settings

_pool: ArqRedis | None = None


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_settings().redis_url)


async def get_queue() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(redis_settings())
    return _pool


async def enqueue(function: str, *args: Any) -> None:
    await (await get_queue()).enqueue_job(function, *args)


async def close_queue() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None

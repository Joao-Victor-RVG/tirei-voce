from app.core.errors import TooManyRequestsError
from app.core.redis import get_redis


async def hit(bucket: str, identifier: str, *, limit: int, window_seconds: int) -> None:
    """Janela fixa no Redis: INCR + EXPIRE. Compartilhado entre réplicas da API."""
    key = f"rl:{bucket}:{identifier.lower()}"
    redis = get_redis()
    async with redis.pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, window_seconds, nx=True)
        count, _ = await pipe.execute()
    if int(count) > limit:
        ttl = await redis.ttl(key)
        raise TooManyRequestsError(details={"retry_after_seconds": max(int(ttl), 1)})

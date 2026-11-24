import logging
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.core.db import get_engine
from app.core.redis import get_redis

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])

CheckStatus = Literal["ok", "error"]


class HealthResponse(BaseModel):
    status: CheckStatus
    checks: dict[str, CheckStatus]


async def _check_database() -> CheckStatus:
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        logger.warning("health_check_failed", extra={"check": "database"}, exc_info=True)
        return "error"
    return "ok"


async def _check_redis() -> CheckStatus:
    try:
        await get_redis().ping()
    except Exception:
        logger.warning("health_check_failed", extra={"check": "redis"}, exc_info=True)
        return "error"
    return "ok"


@router.get("/health", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
async def health() -> JSONResponse:
    checks = {"database": await _check_database(), "redis": await _check_redis()}
    ok = all(v == "ok" for v in checks.values())
    body = HealthResponse(status="ok" if ok else "error", checks=checks)
    return JSONResponse(body.model_dump(), status_code=200 if ok else 503)

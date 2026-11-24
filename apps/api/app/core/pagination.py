import uuid
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None


class PageParams(BaseModel):
    cursor: uuid.UUID | None = None
    limit: int = DEFAULT_LIMIT


def page_params(
    cursor: Annotated[uuid.UUID | None, Query(description="Cursor da página anterior")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> PageParams:
    """Paginação por cursor usando o id (UUIDv7, ordenado por tempo)."""
    return PageParams(cursor=cursor, limit=limit)

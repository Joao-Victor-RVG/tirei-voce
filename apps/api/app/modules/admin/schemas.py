import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.groups.models import GroupStatus


class CountWithRecent(BaseModel):
    total: int
    last_7d: int


class AdminMetrics(BaseModel):
    """Só números agregados: nada de pares, conversas ou listas."""

    users: CountWithRecent
    users_verified: int
    groups: CountWithRecent
    groups_by_status: dict[GroupStatus, int]
    draws: CountWithRecent
    participants: int
    avg_group_size: float
    gifts_purchased: int
    gifts_total: int
    chat_messages_7d: int
    push_subscriptions: int
    scheduled_draws_pending: int
    generated_at: datetime


class AdminUserOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    email_verified: bool
    is_active: bool
    is_admin: bool
    groups: int
    created_at: datetime


class AdminUserPage(BaseModel):
    items: list[AdminUserOut]
    next_cursor: str | None

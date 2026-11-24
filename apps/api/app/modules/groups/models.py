import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, Timestamps, UUIDPrimaryKey
from app.core.enums import str_enum

if TYPE_CHECKING:
    from app.modules.users.models import User


class GroupTheme(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "group_themes"

    slug: Mapped[str] = mapped_column(String(50), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    emoji: Mapped[str] = mapped_column(String(16))
    description: Mapped[str] = mapped_column(Text)


class GroupStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    DRAWN = "DRAWN"
    FINISHED = "FINISHED"


class Group(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "groups"

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    theme_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("group_themes.id"), index=True)
    custom_name: Mapped[str | None] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    min_value_cents: Mapped[int | None]
    max_value_cents: Mapped[int | None]
    event_at: Mapped[datetime | None]
    event_location: Mapped[str | None] = mapped_column(String(200))
    event_maps_url: Mapped[str | None] = mapped_column(String(2048))
    join_deadline_at: Mapped[datetime | None]
    wishlist_deadline_at: Mapped[datetime | None]
    draw_scheduled_at: Mapped[datetime | None] = mapped_column(index=True)
    status: Mapped[GroupStatus] = mapped_column(
        str_enum(GroupStatus, "group_status"), default=GroupStatus.DRAFT, index=True
    )
    invite_code: Mapped[str] = mapped_column(String(32), unique=True)
    max_participants: Mapped[int] = mapped_column(default=100, server_default="100")
    prefer_single_cycle: Mapped[bool] = mapped_column(default=True, server_default=true())

    theme: Mapped[GroupTheme] = relationship(lazy="raise")
    owner: Mapped["User"] = relationship(lazy="raise")

    __table_args__ = (
        CheckConstraint(
            "min_value_cents IS NULL OR min_value_cents >= 0", name="min_value_positive"
        ),
        CheckConstraint(
            "max_value_cents IS NULL OR min_value_cents IS NULL"
            " OR max_value_cents >= min_value_cents",
            name="max_value_gte_min",
        ),
        CheckConstraint("max_participants BETWEEN 3 AND 200", name="max_participants_range"),
    )

    @property
    def display_name(self) -> str:
        return self.custom_name or self.theme.display_name

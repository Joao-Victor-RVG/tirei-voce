import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPrimaryKey


class WishlistItem(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "wishlist_items"

    participant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(120))
    url: Mapped[str | None] = mapped_column(String(2048))
    price_hint_cents: Mapped[int | None]
    priority: Mapped[int] = mapped_column(default=2, server_default="2")
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("priority BETWEEN 1 AND 3", name="priority_range"),
        CheckConstraint("price_hint_cents IS NULL OR price_hint_cents >= 0", name="price_positive"),
    )


class ParticipantPreferences(Timestamps, Base):
    __tablename__ = "participant_preferences"

    participant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"), primary_key=True
    )
    dislikes: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

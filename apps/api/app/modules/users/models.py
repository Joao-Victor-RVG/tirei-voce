from datetime import datetime

from sqlalchemy import Index, String, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPrimaryKey


class User(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(320))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True)
    email_verified_at: Mapped[datetime | None]
    avatar_url: Mapped[str | None] = mapped_column(String(2048))
    shirt_size: Mapped[str | None] = mapped_column(String(10))
    shoe_size: Mapped[str | None] = mapped_column(String(10))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    email_reminders: Mapped[bool] = mapped_column(default=True, server_default=true())

    __table_args__ = (Index("uq_users_email_lower", func.lower(email), unique=True),)

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None

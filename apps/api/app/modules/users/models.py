from datetime import datetime

from sqlalchemy import Index, String, false, func, true
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
    phone: Mapped[str | None] = mapped_column(String(20))  # E.164, só com opt-in de WhatsApp
    whatsapp_opt_in: Mapped[bool] = mapped_column(default=False, server_default=false())
    # Só por comando (python -m app.admin grant <email>); nunca pela API.
    is_admin: Mapped[bool] = mapped_column(default=False, server_default=false())
    # Conta excluída e anonimizada (mantida só para não quebrar sorteios de outras pessoas).
    deleted_at: Mapped[datetime | None]

    __table_args__ = (Index("uq_users_email_lower", func.lower(email), unique=True),)

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None

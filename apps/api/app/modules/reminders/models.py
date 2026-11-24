import enum
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPrimaryKey
from app.core.enums import str_enum


class ReminderKind(enum.StrEnum):
    WISHLIST_DEADLINE = "wishlist_deadline"  # 1 dia antes do prazo da lista
    EVENT_1D = "event_1d"  # 1 dia antes do evento
    EVENT_2H = "event_2h"  # 2 horas antes do evento


class SentReminder(UUIDPrimaryKey, Timestamps, Base):
    """Garante um envio por (grupo, tipo, data-alvo), mesmo com vários workers.

    A data-alvo entra na chave: se o evento mudar de data, o lembrete volta a valer.
    """

    __tablename__ = "sent_reminders"

    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    kind: Mapped[ReminderKind] = mapped_column(str_enum(ReminderKind, "reminder_kind"))
    target_at: Mapped[datetime]
    recipients: Mapped[int] = mapped_column(default=0)

    __table_args__ = (
        UniqueConstraint(
            "group_id", "kind", "target_at", name="uq_sent_reminders_group_kind_target"
        ),
    )

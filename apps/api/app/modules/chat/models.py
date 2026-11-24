import enum
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPrimaryKey
from app.core.enums import str_enum


class SenderRole(enum.StrEnum):
    GIVER = "giver"  # quem tirou (anônimo para o outro lado)
    RECEIVER = "receiver"  # quem foi tirado


class ChatMessage(UUIDPrimaryKey, Timestamps, Base):
    """Mensagem de uma dupla do sorteio. Guarda só o papel de quem enviou, nunca o id da pessoa."""

    __tablename__ = "chat_messages"

    assignment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("draw_assignments.id", ondelete="CASCADE")
    )
    sender_role: Mapped[SenderRole] = mapped_column(str_enum(SenderRole, "chat_sender_role"))
    body: Mapped[str] = mapped_column(Text)
    read_at: Mapped[datetime | None]

    __table_args__ = (Index("ix_chat_messages_assignment_id_id", "assignment_id", "id"),)

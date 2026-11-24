import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, Timestamps, UUIDPrimaryKey
from app.core.enums import str_enum

if TYPE_CHECKING:
    from app.modules.users.models import User


class ParticipantRole(enum.StrEnum):
    OWNER = "owner"
    CO_OWNER = "co_owner"  # reservado para a Fase 2 (coorganizadores)
    MEMBER = "member"


class Participant(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "participants"

    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[ParticipantRole] = mapped_column(
        str_enum(ParticipantRole, "participant_role"), default=ParticipantRole.MEMBER
    )
    joined_at: Mapped[datetime] = mapped_column(server_default=func.now())
    left_at: Mapped[datetime | None]

    user: Mapped["User"] = relationship(lazy="raise")

    # O índice único (group_id, user_id) também atende as buscas por group_id.
    __table_args__ = (UniqueConstraint("group_id", "user_id"),)

    @property
    def is_active(self) -> bool:
        return self.left_at is None

    @property
    def is_organizer(self) -> bool:
        return self.role is ParticipantRole.OWNER

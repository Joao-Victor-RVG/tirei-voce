import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, Timestamps, UUIDPrimaryKey


class ExclusionCircle(UUIDPrimaryKey, Timestamps, Base):
    """Ninguém de um mesmo círculo tira outro membro dele (ex.: casal, família)."""

    __tablename__ = "exclusion_circles"

    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))

    members: Mapped[list["ExclusionCircleMember"]] = relationship(
        lazy="raise", cascade="all, delete-orphan", passive_deletes=True
    )


class ExclusionCircleMember(Timestamps, Base):
    __tablename__ = "exclusion_circle_members"

    circle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exclusion_circles.id", ondelete="CASCADE"), primary_key=True
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class BlockedPair(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "blocked_pairs"

    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), index=True
    )
    giver_participant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"), index=True
    )
    receiver_participant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"), index=True
    )
    bidirectional: Mapped[bool] = mapped_column(default=False, server_default=false())

    __table_args__ = (
        UniqueConstraint(
            "group_id",
            "giver_participant_id",
            "receiver_participant_id",
            name="uq_blocked_pairs_group_giver_receiver",
        ),
        CheckConstraint("giver_participant_id <> receiver_participant_id", name="distinct_people"),
    )

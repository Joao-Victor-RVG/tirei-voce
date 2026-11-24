import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Timestamps, UUIDPrimaryKey


class Draw(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "draws"

    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    version: Mapped[int]
    # Fica nulo se a conta de quem sorteou for apagada (LGPD).
    executed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    executed_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # HMAC do resultado completo: detecta adulteração das atribuições sem revelá-las.
    seed_hash: Mapped[str] = mapped_column(String(64))
    # SHA-256 de (usuário, Idempotency-Key): repetir o clique devolve este mesmo sorteio.
    idempotency_key_hash: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (UniqueConstraint("group_id", "version"),)


class DrawAssignment(UUIDPrimaryKey, Timestamps, Base):
    """Quem dá fica em claro; quem recebe fica cifrado (Fernet) + hash de busca (HMAC)."""

    __tablename__ = "draw_assignments"

    draw_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("draws.id", ondelete="CASCADE"))
    giver_participant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"), index=True
    )
    receiver_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    receiver_lookup_hash: Mapped[str] = mapped_column(String(64))
    # Marcado por quem dá o presente; a organização só vê o total agregado.
    gift_purchased_at: Mapped[datetime | None]

    __table_args__ = (
        UniqueConstraint("draw_id", "giver_participant_id"),
        UniqueConstraint("draw_id", "receiver_lookup_hash"),
    )

"""reminder kind reveal

Revision ID: a7c3e5f1b2d4
Revises: 935432411eda
Create Date: 2026-11-24 18:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a7c3e5f1b2d4"
down_revision: str | None = "935432411eda"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = ("wishlist_deadline", "event_1d", "event_2h")
NEW = (*OLD, "reveal")


def _check(values: tuple[str, ...]) -> str:
    return "kind IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f("ck_sent_reminders_reminder_kind"), "sent_reminders", type_="check")
    op.create_check_constraint("reminder_kind", "sent_reminders", _check(NEW))


def downgrade() -> None:
    op.execute("DELETE FROM sent_reminders WHERE kind = 'reveal'")
    op.drop_constraint(op.f("ck_sent_reminders_reminder_kind"), "sent_reminders", type_="check")
    op.create_check_constraint("reminder_kind", "sent_reminders", _check(OLD))

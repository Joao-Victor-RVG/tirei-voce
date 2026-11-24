"""Regra pura de quais lembretes estão vencidos (sem I/O)."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.modules.groups.models import GroupStatus
from app.modules.reminders.models import ReminderKind

ACTIVE_STATUSES = (GroupStatus.OPEN, GroupStatus.CLOSED, GroupStatus.DRAWN)

ONE_DAY = timedelta(days=1)
TWO_HOURS = timedelta(hours=2)


@dataclass(frozen=True)
class DueReminder:
    kind: ReminderKind
    target_at: datetime


def due_reminders(
    *,
    status: GroupStatus,
    event_at: datetime | None,
    wishlist_deadline_at: datetime | None,
    now: datetime,
) -> list[DueReminder]:
    """Cada lembrete vale numa janela: do horário de disparo até o momento-alvo.

    O de 1 dia não é enviado se já estivermos dentro das 2 horas finais (aí vai o de 2 h).
    """
    if status not in ACTIVE_STATUSES:
        return []
    due: list[DueReminder] = []
    if wishlist_deadline_at and wishlist_deadline_at - ONE_DAY <= now < wishlist_deadline_at:
        due.append(DueReminder(ReminderKind.WISHLIST_DEADLINE, wishlist_deadline_at))
    if event_at:
        if event_at - ONE_DAY <= now < event_at - TWO_HOURS:
            due.append(DueReminder(ReminderKind.EVENT_1D, event_at))
        elif event_at - TWO_HOURS <= now < event_at:
            due.append(DueReminder(ReminderKind.EVENT_2H, event_at))
    return due

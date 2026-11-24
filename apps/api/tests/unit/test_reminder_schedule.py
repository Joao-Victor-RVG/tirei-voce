from datetime import UTC, datetime, timedelta

import pytest

from app.modules.groups.models import GroupStatus
from app.modules.reminders.models import ReminderKind
from app.modules.reminders.schedule import due_reminders

EVENT = datetime(2026, 12, 24, 23, 0, tzinfo=UTC)


def kinds(
    now: datetime, status: GroupStatus = GroupStatus.DRAWN, deadline: datetime | None = None
) -> list[ReminderKind]:
    return [
        r.kind
        for r in due_reminders(
            status=status, event_at=EVENT, wishlist_deadline_at=deadline, now=now
        )
    ]


@pytest.mark.parametrize(
    "before_event, expected",
    [
        (timedelta(days=2), []),
        (timedelta(hours=24), [ReminderKind.EVENT_1D]),
        (timedelta(hours=3), [ReminderKind.EVENT_1D]),
        (timedelta(hours=2), [ReminderKind.EVENT_2H]),
        (timedelta(minutes=5), [ReminderKind.EVENT_2H]),
        (timedelta(0), []),
        (-timedelta(hours=1), []),
    ],
)
def test_event_windows(before_event: timedelta, expected: list[ReminderKind]) -> None:
    assert kinds(EVENT - before_event) == expected


@pytest.mark.parametrize("status", [GroupStatus.DRAFT, GroupStatus.FINISHED])
def test_inactive_groups_get_nothing(status: GroupStatus) -> None:
    assert kinds(EVENT - timedelta(hours=1), status=status) == []


def test_wishlist_deadline_window() -> None:
    deadline = EVENT - timedelta(days=5)
    assert kinds(deadline - timedelta(hours=25), deadline=deadline) == []
    assert kinds(deadline - timedelta(hours=10), deadline=deadline) == [
        ReminderKind.WISHLIST_DEADLINE
    ]
    assert kinds(deadline, deadline=deadline) == []


def test_target_is_the_reference_moment() -> None:
    due = due_reminders(
        status=GroupStatus.OPEN,
        event_at=EVENT,
        wishlist_deadline_at=None,
        now=EVENT - timedelta(hours=1),
    )
    assert due[0].target_at == EVENT

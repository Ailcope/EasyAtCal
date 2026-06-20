from __future__ import annotations

from datetime import date, datetime

from easyatcal.backends.base import Changes
from easyatcal.models import Shift
from easyatcal.state import State


def compute_changes(
    remote_shifts: list[Shift],
    state: State,
    known_updated_at: dict[str, str],
    *,
    from_date: date,
    to_date: date,
    known_start: dict[str, str],
) -> Changes:
    """Diff remote shifts against the last-known state.

    known_updated_at maps shift_id -> ISO updated_at recorded at last sync.
    known_start maps shift_id -> ISO start datetime recorded at last sync.

    A tracked shift absent from ``remote_shifts`` is only deleted when its
    recorded start falls inside the fetched window ``[from_date, to_date]`` —
    i.e. the API was actually asked about it and reported it gone. Shifts that
    merely aged out of the window (or whose start we never recorded) are left
    untouched, so past shifts are never deleted by a later sync.
    """
    remote_by_id = {s.id: s for s in remote_shifts}
    adds: list[Shift] = []
    updates: list[tuple[Shift, str]] = []
    deletes: list[str] = []

    for shift in remote_shifts:
        event_uid = state.shift_to_event.get(shift.id)
        if event_uid is None:
            adds.append(shift)
            continue
        last_updated = known_updated_at.get(shift.id)
        if last_updated != shift.updated_at.isoformat():
            updates.append((shift, event_uid))

    for shift_id, event_uid in state.shift_to_event.items():
        if shift_id in remote_by_id:
            continue
        if _start_in_window(known_start.get(shift_id), from_date, to_date):
            deletes.append(event_uid)

    return Changes(adds=adds, updates=updates, deletes=deletes)


def _start_in_window(
    start_iso: str | None, from_date: date, to_date: date
) -> bool:
    """True only when we know the shift's start and it lies in the window.

    Unknown or unparseable starts return False so the shift is preserved.
    """
    if not start_iso:
        return False
    try:
        start = datetime.fromisoformat(start_iso).date()
    except ValueError:
        return False
    return from_date <= start <= to_date

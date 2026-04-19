from __future__ import annotations

from easyatcal.backends.base import Changes
from easyatcal.models import Shift
from easyatcal.state import State


def compute_changes(
    remote_shifts: list[Shift],
    state: State,
    known_updated_at: dict[str, str],
) -> Changes:
    """Diff remote shifts against the last-known state.

    known_updated_at maps shift_id -> ISO-formatted updated_at recorded at last sync.
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
        if shift_id not in remote_by_id:
            deletes.append(event_uid)

    return Changes(adds=adds, updates=updates, deletes=deletes)

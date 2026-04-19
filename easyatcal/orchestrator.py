from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

from easyatcal.backends.base import CalendarBackend
from easyatcal.models import Shift
from easyatcal.state import State, load_state, save_state
from easyatcal.sync import compute_changes


class ShiftFetcher(Protocol):
    def fetch_shifts(self, from_date, to_date) -> list[Shift]: ...


def run_sync(
    api: ShiftFetcher,
    backend: CalendarBackend,
    state_path: Path,
    lookback_days: int,
    lookahead_days: int,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now(timezone.utc)
    from_date = (now - timedelta(days=lookback_days)).date()
    to_date = (now + timedelta(days=lookahead_days)).date()

    remote_shifts = api.fetch_shifts(from_date=from_date, to_date=to_date)
    state = load_state(state_path)
    changes = compute_changes(
        remote_shifts, state, known_updated_at=state.shift_updated_at
    )
    mapping = backend.apply(changes)

    new_shift_to_event = dict(state.shift_to_event)
    new_updated_at = dict(state.shift_updated_at)
    for shift_id, event_uid in mapping.items():
        new_shift_to_event[shift_id] = event_uid
    for shift in remote_shifts:
        new_updated_at[shift.id] = shift.updated_at.isoformat()

    remote_ids = {s.id for s in remote_shifts}
    new_shift_to_event = {
        sid: evt for sid, evt in new_shift_to_event.items() if sid in remote_ids
    }
    new_updated_at = {
        sid: ts for sid, ts in new_updated_at.items() if sid in remote_ids
    }

    save_state(
        state_path,
        State(
            shift_to_event=new_shift_to_event,
            shift_updated_at=new_updated_at,
            last_sync=now.isoformat(),
        ),
    )

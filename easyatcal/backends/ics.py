from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from icalendar import Calendar, Event

from easyatcal.backends.base import ApplyResult, Changes
from easyatcal.models import Shift

UID_PREFIX = "easyatcal-"
# Holds the unformatted title so a custom event_title_format is not re-applied
# to an already-formatted summary when an old event is reloaded from the file.
RAW_TITLE_PROP = "X-EASYATCAL-TITLE"


def _uid_for(shift_id: str) -> str:
    return f"{UID_PREFIX}{shift_id}"


def _shift_from_event(comp: Any) -> Shift | None:
    """Reconstruct a Shift from a VEVENT we previously wrote. Returns None for
    events we cannot faithfully rebuild (e.g. all-day or naive datetimes)."""
    uid = str(comp.get("uid", ""))
    if not uid.startswith(UID_PREFIX):
        return None
    try:
        start = comp.decoded("dtstart")
        end = comp.decoded("dtend")
    except (KeyError, ValueError):
        return None
    if not isinstance(start, datetime) or not isinstance(end, datetime):
        return None
    raw_title = comp.get(RAW_TITLE_PROP) or comp.get("summary")
    location = comp.get("location")
    notes = comp.get("description")
    try:
        return Shift(
            id=uid[len(UID_PREFIX):],
            start=start,
            end=end,
            title=str(raw_title) if raw_title else "Shift",
            location=str(location) if location else None,
            notes=str(notes) if notes else None,
            updated_at=datetime.now(UTC),
        )
    except ValueError:
        return None


def _to_event(
    shift: Shift,
    uid: str,
    event_title_format: str = "{title}",
    alarm_minutes_before: int | None = None,
) -> Any:
    from datetime import UTC, datetime, timedelta

    from icalendar import Alarm
    ev = Event()  # type: ignore[no-untyped-call]
    ev.add("uid", uid)
    
    # Format the title
    title = event_title_format.format(
        title=shift.title,
        location=shift.location or "",
        notes=shift.notes or "",
    ).strip()
    
    ev.add("summary", title)
    ev.add(RAW_TITLE_PROP, shift.title)
    ev.add("dtstart", shift.start)
    ev.add("dtend", shift.end)
    # Always use current time for dtstamp to indicate when the file was generated
    now = datetime.now(UTC)
    ev.add("dtstamp", now)
    # Force an update by bumping the sequence (or using the timestamp) and updating last-modified
    ev.add("last-modified", now)
    ev.add("sequence", int(now.timestamp()))
    ev.add("status", "CONFIRMED")
    ev.add("transp", "OPAQUE")  # Standard: Show as busy
    ev.add("X-MICROSOFT-CDO-BUSYSTATUS", "BUSY")  # Outlook specific
    if shift.location:
        ev.add("location", shift.location)
    if shift.notes:
        ev.add("description", shift.notes)
        
    if alarm_minutes_before is not None:
        alarm = Alarm()  # type: ignore[no-untyped-call]
        alarm.add("action", "DISPLAY")
        alarm.add("description", "Shift Reminder")
        alarm.add("trigger", timedelta(minutes=-alarm_minutes_before))
        ev.add_component(alarm)
        
    return ev


class IcsBackend:
    """File-based calendar backend that regenerates the .ics on each apply.

    `known_shifts` is the previous set of shifts the caller knows about — used
    so we can rewrite the file without losing events unrelated to the current
    change set.
    """

    def __init__(
        self,
        output_path: Path,
        known_shifts: list[Shift],
        event_title_format: str = "{title}",
        alarm_minutes_before: int | None = None,
    ) -> None:
        self.output_path = Path(output_path).expanduser()
        self.event_title_format = event_title_format
        self.alarm_minutes_before = alarm_minutes_before
        # Seed from any existing file so events outside the current fetch window
        # survive regeneration, then overlay caller-provided known shifts.
        self._current: dict[str, Shift] = self._load_existing()
        for s in known_shifts:
            self._current[s.id] = s

    def _load_existing(self) -> dict[str, Shift]:
        if not self.output_path.exists():
            return {}
        try:
            cal = Calendar.from_ical(self.output_path.read_bytes())
        except (ValueError, KeyError):
            return {}
        out: dict[str, Shift] = {}
        for comp in cal.walk("VEVENT"):
            shift = _shift_from_event(comp)
            if shift is not None:
                out[shift.id] = shift
        return out

    def set_all_shifts(self, shifts: list[Shift]) -> None:
        # Merge: refresh window shifts without dropping previously-known ones.
        for s in shifts:
            self._current[s.id] = s

    def apply(self, changes: Changes) -> ApplyResult:
        mapping: dict[str, str] = {}

        for shift in changes.adds:
            self._current[shift.id] = shift
            mapping[shift.id] = _uid_for(shift.id)

        for shift, _event_uid in changes.updates:
            self._current[shift.id] = shift
            mapping[shift.id] = _uid_for(shift.id)

        delete_uids = set(changes.deletes)
        to_drop = [
            sid for sid in self._current
            if _uid_for(sid) in delete_uids
        ]
        confirmed_deletes: list[str] = []
        for sid in to_drop:
            self._current.pop(sid, None)
            confirmed_deletes.append(_uid_for(sid))
        # Any requested delete for a uid we never knew about is treated as
        # "already gone" — surface it so the orchestrator prunes state.
        for uid in delete_uids - set(confirmed_deletes):
            confirmed_deletes.append(uid)

        self._write()
        return ApplyResult(mapping=mapping, deleted_uids=confirmed_deletes)

    def _write(self) -> None:
        cal = Calendar()  # type: ignore[no-untyped-call]
        cal.add("prodid", "-//EasyAtCal//EN")
        cal.add("version", "2.0")
        cal.add("calscale", "GREGORIAN")
        cal.add("method", "PUBLISH")  # Crucial for Outlook
        cal.add("x-wr-calname", "easy@work")  # Apple Calendar display name
        cal.add("x-wr-caldesc", "Work shifts imported from easy@work")
        for shift in self._current.values():
            cal.add_component(_to_event(
                shift,
                _uid_for(shift.id),
                self.event_title_format,
                self.alarm_minutes_before,
            ))

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.output_path.with_suffix(self.output_path.suffix + ".tmp")
        tmp.write_bytes(cal.to_ical())
        tmp.replace(self.output_path)

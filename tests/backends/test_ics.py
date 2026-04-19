from datetime import UTC, datetime
from pathlib import Path

from easyatcal.backends.base import Changes
from easyatcal.backends.ics import IcsBackend
from easyatcal.models import Shift


def _shift(id_: str) -> Shift:
    return Shift(
        id=id_,
        start=datetime(2026, 4, 20, 9, tzinfo=UTC),
        end=datetime(2026, 4, 20, 17, tzinfo=UTC),
        title=f"Shift {id_}",
        location="Oslo",
        notes=None,
        updated_at=datetime(2026, 4, 18, tzinfo=UTC),
    )


def test_adds_produce_events_in_file(tmp_path: Path):
    out = tmp_path / "shifts.ics"
    backend = IcsBackend(output_path=out, known_shifts=[])
    changes = Changes(adds=[_shift("s1"), _shift("s2")])

    result = backend.apply(changes)

    body = out.read_text()
    assert "BEGIN:VCALENDAR" in body
    assert "SUMMARY:Shift s1" in body
    assert "SUMMARY:Shift s2" in body
    assert result.mapping["s1"].startswith("easyatcal-s1")
    assert result.mapping["s2"].startswith("easyatcal-s2")


def test_deletes_remove_events(tmp_path: Path):
    out = tmp_path / "shifts.ics"
    backend1 = IcsBackend(output_path=out, known_shifts=[])
    backend1.apply(Changes(adds=[_shift("s1"), _shift("s2")]))

    backend2 = IcsBackend(
        output_path=out,
        known_shifts=[_shift("s1"), _shift("s2")],
    )
    uid_s2 = "easyatcal-s2"
    backend2.apply(Changes(deletes=[uid_s2]))

    body = out.read_text()
    assert "SUMMARY:Shift s1" in body
    assert "SUMMARY:Shift s2" not in body


def test_updates_replace_event(tmp_path: Path):
    out = tmp_path / "shifts.ics"
    s = _shift("s1")
    IcsBackend(output_path=out, known_shifts=[]).apply(Changes(adds=[s]))

    s_new = Shift(
        id=s.id, start=s.start, end=s.end, title="New Title",
        location=s.location, notes=s.notes, updated_at=s.updated_at,
    )
    backend = IcsBackend(output_path=out, known_shifts=[s])
    backend.apply(Changes(updates=[(s_new, "easyatcal-s1")]))

    body = out.read_text()
    assert "SUMMARY:New Title" in body
    assert "SUMMARY:Shift s1" not in body

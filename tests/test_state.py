import json
from pathlib import Path

from easyatcal.state import State, load_state, save_state


def test_save_then_load_roundtrip(tmp_path: Path):
    path = tmp_path / "state.json"
    s = State(shift_to_event={"shift-1": "evt-1", "shift-2": "evt-2"},
              last_sync="2026-04-19T12:00:00+00:00")
    save_state(path, s)

    loaded = load_state(path)
    assert loaded.shift_to_event == s.shift_to_event
    assert loaded.last_sync == s.last_sync


def test_load_missing_returns_empty(tmp_path: Path):
    s = load_state(tmp_path / "missing.json")
    assert s.shift_to_event == {}
    assert s.last_sync is None


def test_load_corrupt_backs_up_and_returns_empty(tmp_path: Path):
    path = tmp_path / "state.json"
    path.write_text("not valid json{{{")

    s = load_state(path)

    assert s.shift_to_event == {}
    assert (tmp_path / "state.json.bak").exists()


def test_save_is_atomic(tmp_path: Path):
    path = tmp_path / "state.json"
    save_state(path, State(shift_to_event={"a": "b"}, last_sync=None))
    assert not any(p.name.endswith(".tmp") for p in tmp_path.iterdir())
    assert json.loads(path.read_text())["shift_to_event"] == {"a": "b"}


def test_state_roundtrip_with_updated_at(tmp_path):
    path = tmp_path / "state.json"
    s = State(
        shift_to_event={"s1": "e1"},
        shift_updated_at={"s1": "2026-04-18T10:00:00+00:00"},
        last_sync="2026-04-19T12:00:00+00:00",
    )
    save_state(path, s)
    loaded = load_state(path)
    assert loaded.shift_updated_at == {"s1": "2026-04-18T10:00:00+00:00"}

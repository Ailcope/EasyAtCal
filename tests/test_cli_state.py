from unittest.mock import patch

from typer.testing import CliRunner

from easyatcal.cli import app
from easyatcal.state import State, save_state

runner = CliRunner()


@patch("easyatcal.cli.state_path")
def test_state_show_reports_summary(mock_sp, tmp_path):
    sp = tmp_path / "state.json"
    save_state(sp, State(
        shift_to_event={"s1": "evt-1", "s2": "evt-2"},
        shift_updated_at={
            "s1": "2026-04-18T00:00:00+00:00",
            "s2": "2026-04-18T00:00:00+00:00",
        },
        last_sync="2026-04-19T12:00:00+00:00",
    ))
    mock_sp.return_value = sp

    result = runner.invoke(app, ["state", "show"])
    assert result.exit_code == 0, result.stdout
    assert "2" in result.stdout  # shift count
    assert "2026-04-19" in result.stdout
    assert str(sp) in result.stdout


@patch("easyatcal.cli.state_path")
def test_state_show_handles_missing(mock_sp, tmp_path):
    mock_sp.return_value = tmp_path / "nope.json"
    result = runner.invoke(app, ["state", "show"])
    assert result.exit_code == 0
    assert "0" in result.stdout or "empty" in result.stdout.lower()


@patch("easyatcal.cli.state_path")
def test_state_clear_requires_confirmation_and_deletes(mock_sp, tmp_path):
    sp = tmp_path / "state.json"
    save_state(sp, State(shift_to_event={"s1": "e1"}))
    mock_sp.return_value = sp

    # Without --yes: refuses.
    result = runner.invoke(app, ["state", "clear"])
    assert result.exit_code != 0
    assert sp.exists()

    # With --yes: deletes.
    result = runner.invoke(app, ["state", "clear", "--yes"])
    assert result.exit_code == 0, result.stdout
    assert not sp.exists()


@patch("easyatcal.cli.state_path")
def test_state_clear_missing_is_noop(mock_sp, tmp_path):
    mock_sp.return_value = tmp_path / "nope.json"
    result = runner.invoke(app, ["state", "clear", "--yes"])
    assert result.exit_code == 0

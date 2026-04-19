from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from easyatcal.cli import app

runner = CliRunner()


@patch("easyatcal.cli.run_sync")
@patch("easyatcal.cli._build_backend")
@patch("easyatcal.cli._build_api_client")
@patch("easyatcal.cli.configure_logging")
@patch("easyatcal.cli.load_config")
def test_sync_once_invokes_run_sync(
    mock_cfg, mock_log, mock_api, mock_back, mock_run, tmp_path
):
    mock_cfg.return_value = MagicMock(
        sync=MagicMock(lookback_days=7, lookahead_days=90),
        logging=MagicMock(level="INFO"),
    )
    result = runner.invoke(app, ["sync"])

    assert result.exit_code == 0, result.stdout
    mock_run.assert_called_once()


@patch("easyatcal.cli.time.sleep", side_effect=KeyboardInterrupt)
@patch("easyatcal.cli.run_sync")
@patch("easyatcal.cli._build_backend")
@patch("easyatcal.cli._build_api_client")
@patch("easyatcal.cli.configure_logging")
@patch("easyatcal.cli.load_config")
def test_watch_loops_until_interrupt(
    mock_cfg, mock_log, mock_api, mock_back, mock_run, mock_sleep
):
    mock_cfg.return_value = MagicMock(
        sync=MagicMock(lookback_days=7, lookahead_days=90),
        logging=MagicMock(level="INFO"),
    )
    result = runner.invoke(app, ["watch", "--interval-seconds", "60"])

    assert mock_run.call_count == 1
    assert result.exit_code == 0


@patch("easyatcal.cli._build_backend")
@patch("easyatcal.cli._build_api_client")
@patch("easyatcal.cli.configure_logging")
@patch("easyatcal.cli.load_config")
def test_sync_dry_run_skips_backend_and_state(
    mock_cfg, mock_log, mock_api_build, mock_back, tmp_path
):
    from datetime import datetime, timezone
    from easyatcal.models import Shift

    mock_cfg.return_value = MagicMock(
        sync=MagicMock(lookback_days=7, lookahead_days=90),
        logging=MagicMock(level="INFO"),
    )
    api = MagicMock()
    api.fetch_shifts.return_value = [
        Shift(
            id="s1",
            start=datetime(2026, 5, 1, 9, tzinfo=timezone.utc),
            end=datetime(2026, 5, 1, 17, tzinfo=timezone.utc),
            title="Shift s1",
            location=None,
            notes=None,
            updated_at=datetime(2026, 4, 29, tzinfo=timezone.utc),
        )
    ]
    mock_api_build.return_value = api
    backend = MagicMock()
    mock_back.return_value = backend

    result = runner.invoke(app, ["sync", "--dry-run"])

    assert result.exit_code == 0, result.stdout
    backend.apply.assert_not_called()
    assert "dry run" in result.stdout.lower()
    assert "add" in result.stdout.lower()

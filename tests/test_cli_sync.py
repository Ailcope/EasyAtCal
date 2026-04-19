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

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from easyatcal.cli import app

runner = CliRunner()


@patch("easyatcal.cli._build_backend")
@patch("easyatcal.cli._build_api_client")
@patch("easyatcal.cli.configure_logging")
@patch("easyatcal.cli.load_config")
@patch("easyatcal.cli.config_path")
def test_doctor_all_green(mock_cpath, mock_cfg, mock_log, mock_api, mock_backend, tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("stub: true\n")
    mock_cpath.return_value = cfg_file
    mock_cfg.return_value = MagicMock(
        logging=MagicMock(level="INFO"), backend="ics"
    )
    api = MagicMock()
    api.authenticate.return_value = "tok"
    mock_api.return_value = api
    mock_backend.return_value = MagicMock()

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.stdout
    assert "config" in result.stdout.lower()
    assert "auth" in result.stdout.lower()
    assert "backend" in result.stdout.lower()


@patch("easyatcal.cli.config_path")
def test_doctor_reports_missing_config(mock_cpath, tmp_path):
    mock_cpath.return_value = tmp_path / "nope.yaml"
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code != 0
    assert "config" in result.stdout.lower()


@patch("easyatcal.cli._build_api_client")
@patch("easyatcal.cli.configure_logging")
@patch("easyatcal.cli.load_config")
@patch("easyatcal.cli.config_path")
def test_doctor_reports_auth_failure(mock_cpath, mock_cfg, mock_log, mock_api, tmp_path):
    from easyatcal.api import AuthError

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("stub: true\n")
    mock_cpath.return_value = cfg_file
    mock_cfg.return_value = MagicMock(
        logging=MagicMock(level="INFO"), backend="ics"
    )
    api = MagicMock()
    api.authenticate.side_effect = AuthError("401 bad creds")
    mock_api.return_value = api

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code != 0
    assert "401" in result.stdout or "bad creds" in result.stdout

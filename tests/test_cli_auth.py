from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from easyatcal.cli import app

runner = CliRunner()


@patch("easyatcal.cli._build_api_client")
@patch("easyatcal.cli.configure_logging")
@patch("easyatcal.cli.load_config")
def test_auth_test_success(mock_cfg, mock_log, mock_build):
    api = MagicMock()
    api.authenticate.return_value = "tok"
    mock_build.return_value = api
    mock_cfg.return_value = MagicMock(logging=MagicMock(level="INFO"))

    result = runner.invoke(app, ["auth", "test"])
    assert result.exit_code == 0, result.stdout
    assert "OK" in result.stdout


@patch("easyatcal.cli._build_api_client")
@patch("easyatcal.cli.configure_logging")
@patch("easyatcal.cli.load_config")
def test_auth_test_failure(mock_cfg, mock_log, mock_build):
    from easyatcal.api import AuthError
    api = MagicMock()
    api.authenticate.side_effect = AuthError("bad creds")
    mock_build.return_value = api
    mock_cfg.return_value = MagicMock(logging=MagicMock(level="INFO"))

    result = runner.invoke(app, ["auth", "test"])
    assert result.exit_code == 2
    assert "bad creds" in result.stdout

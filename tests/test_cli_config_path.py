"""Global --config-path flag overrides the default config location."""
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from easyatcal.cli import app

runner = CliRunner()


@patch("easyatcal.cli.load_config")
def test_config_show_respects_config_path_flag(mock_load, tmp_path: Path):
    cfg_file = tmp_path / "custom.yaml"
    cfg_file.write_text("stub: true\n")

    mock_load.return_value = MagicMock(
        model_dump=lambda: {"easyatwork": {"client_secret": "x"}}
    )

    result = runner.invoke(
        app, ["--config-path", str(cfg_file), "config", "show"]
    )
    assert result.exit_code == 0, result.stdout
    mock_load.assert_called_once_with(cfg_file)


@patch("easyatcal.cli.config_path")
def test_default_config_path_used_when_flag_absent(mock_default, tmp_path: Path):
    mock_default.return_value = tmp_path / "nope.yaml"
    result = runner.invoke(app, ["doctor"])
    # Should call the default resolver because no flag given.
    mock_default.assert_called()
    assert result.exit_code != 0


def test_version_flag_prints_version_and_exits():
    from easyatcal import __version__

    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout

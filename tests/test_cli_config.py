from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from easyatcal.cli import app

runner = CliRunner()


def test_config_init_creates_file(tmp_path: Path):
    target = tmp_path / "config.yaml"
    with patch("easyatcal.cli.config_path", return_value=target):
        result = runner.invoke(app, ["config", "init"])

    assert result.exit_code == 0, result.stdout
    assert target.exists()
    assert "easyatwork:" in target.read_text()


def test_config_init_does_not_overwrite(tmp_path: Path):
    target = tmp_path / "config.yaml"
    target.write_text("existing: yes\n")
    with patch("easyatcal.cli.config_path", return_value=target):
        result = runner.invoke(app, ["config", "init"])

    assert result.exit_code != 0


def test_config_show_redacts_secret(tmp_path: Path):
    target = tmp_path / "config.yaml"
    target.write_text(
        "easyatwork:\n"
        "  auth_mode: client\n"
        "  client_id: cid\n"
        "  client_secret: supersecret\n"
        "  base_url: https://api.easyatwork.com\n"
        "backend: ics\n"
    )
    with patch("easyatcal.cli.config_path", return_value=target):
        result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0, result.stdout
    assert "supersecret" not in result.stdout
    assert "***" in result.stdout

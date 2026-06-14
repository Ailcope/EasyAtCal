from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from easyatcal.cli import app

runner = CliRunner()


def test_config_init_creates_file(tmp_path: Path):
    target = tmp_path / "config.yaml"
    with patch("easyatcal.cli.config_path", return_value=target):
        result = runner.invoke(app, ["config", "init", "--no-interactive"])

    assert result.exit_code == 0, result.stdout
    assert target.exists()
    assert "easyatwork:" in target.read_text()


def test_config_init_interactive_english_eventkit(tmp_path: Path):
    target = tmp_path / "config.yaml"
    answers = "user@example.com\nWork {title}\ny\n30\neventkit\n"

    with (
        patch("easyatcal.cli.config_path", return_value=target),
        patch("easyatcal.cli._is_french", return_value=False),
        patch("sys.platform", "darwin"),
    ):
        result = runner.invoke(app, ["config", "init"], input=answers)

    assert result.exit_code == 0, result.stdout
    body = target.read_text()
    assert 'email: "user@example.com"' in body
    assert 'event_title_format: "Work {title}"' in body
    assert "alarm_minutes_before: 30" in body
    assert "backend: eventkit" in body
    assert "Next steps:" in result.stdout


def test_config_init_interactive_french_ics(tmp_path: Path):
    target = tmp_path / "config.yaml"
    answers = "utilisateur@example.com\n{title}\nn\n"

    with (
        patch("easyatcal.cli.config_path", return_value=target),
        patch("easyatcal.cli._is_french", return_value=True),
        patch("sys.platform", "linux"),
    ):
        result = runner.invoke(app, ["config", "init"], input=answers)

    assert result.exit_code == 0, result.stdout
    body = target.read_text()
    assert 'email: "utilisateur@example.com"' in body
    assert "backend: ics" in body
    assert "Configuration générée avec succès" in result.stdout
    assert "Prochaines étapes" in result.stdout


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

from pathlib import Path

import pytest
from typer.testing import CliRunner

from easyatcal.cli import app

runner = CliRunner()


def _write_user_config(tmp_path: Path) -> Path:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        """
easyatwork:
  auth_mode: user
  email: me@example.com
  login_url: https://app.easyatwork.com/
  app_url: https://app.easyatwork.com
  shifts_endpoint: ""
backend: ics
backends:
  ics:
    output_path: %s
"""
        % (tmp_path / "out.ics")
    )
    return cfg


def _write_client_config(tmp_path: Path) -> Path:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        """
easyatwork:
  auth_mode: client
  client_id: cid
  client_secret: csec
  base_url: https://api.easyatwork.com
backend: ics
backends:
  ics:
    output_path: %s
"""
        % (tmp_path / "out.ics")
    )
    return cfg


def test_login_invokes_do_login(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _write_user_config(tmp_path)
    monkeypatch.setenv("EAW_PASSWORD", "s3cret")

    called: dict[str, object] = {}

    def fake_do_login(*, cfg, password, storage_path, extra_wait_selector=None):  # type: ignore[no-untyped-def]
        called["email"] = cfg.email
        called["password"] = password
        called["storage_path"] = storage_path
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        storage_path.write_text('{"cookies":[]}')

    monkeypatch.setattr("easyatcal.auth_user.do_login", fake_do_login)
    monkeypatch.setattr(
        "easyatcal.cli.session_state_path",
        lambda: tmp_path / "session.json",
    )

    result = runner.invoke(app, ["--config-path", str(cfg), "login"])
    assert result.exit_code == 0, result.output
    assert called["email"] == "me@example.com"
    assert called["password"] == "s3cret"
    assert (tmp_path / "session.json").exists()


def test_login_rejects_client_mode(tmp_path: Path) -> None:
    cfg = _write_client_config(tmp_path)
    result = runner.invoke(app, ["--config-path", str(cfg), "login"])
    assert result.exit_code == 1
    assert "auth_mode is not 'user'" in result.output


def test_login_empty_password_exits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = _write_user_config(tmp_path)
    monkeypatch.setenv("EAW_PASSWORD", "")
    # Input "" for the prompt fallback (getenv returns empty string, not None)
    # We expect CLI to treat empty as aborting.
    result = runner.invoke(app, ["--config-path", str(cfg), "login"])
    assert result.exit_code == 1
    assert "Empty password" in result.output


def test_login_playwright_missing_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from easyatcal.auth_user import PlaywrightMissingError

    cfg = _write_user_config(tmp_path)
    monkeypatch.setenv("EAW_PASSWORD", "pw")

    def boom(**_kw: object) -> None:
        raise PlaywrightMissingError("install playwright")

    monkeypatch.setattr("easyatcal.auth_user.do_login", boom)
    monkeypatch.setattr(
        "easyatcal.cli.session_state_path",
        lambda: tmp_path / "session.json",
    )
    result = runner.invoke(app, ["--config-path", str(cfg), "login"])
    assert result.exit_code == 1
    assert "install playwright" in result.output


def test_login_failure_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from easyatcal.auth_user import LoginError

    cfg = _write_user_config(tmp_path)
    monkeypatch.setenv("EAW_PASSWORD", "pw")

    def boom(**_kw: object) -> None:
        raise LoginError("bad creds")

    monkeypatch.setattr("easyatcal.auth_user.do_login", boom)
    monkeypatch.setattr(
        "easyatcal.cli.session_state_path",
        lambda: tmp_path / "session.json",
    )
    result = runner.invoke(app, ["--config-path", str(cfg), "login"])
    assert result.exit_code == 2
    assert "Login failed" in result.output


def test_logout_clears_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = tmp_path / "session.json"
    storage.write_text('{"cookies":[]}')
    monkeypatch.setattr("easyatcal.cli.session_state_path", lambda: storage)
    result = runner.invoke(app, ["logout"])
    assert result.exit_code == 0
    assert not storage.exists()

from __future__ import annotations

import shutil
import time
from datetime import UTC
from pathlib import Path
from typing import Any

import typer
import yaml

from easyatcal.api import EawClient
from easyatcal.api_session import SessionEawClient
from easyatcal.backends.base import CalendarBackend
from easyatcal.backends.ics import IcsBackend
from easyatcal.config import Config, load_config
from easyatcal.logging_setup import configure_logging
from easyatcal.orchestrator import ShiftFetcher, run_sync
from easyatcal.paths import (
    config_path,
    log_path,
    session_state_path,
    state_path,
    token_cache_path,
)
from easyatcal.session import SessionStore

app = typer.Typer(help="EasyAtCal — sync easy@work shifts to Apple Calendar.")
config_app = typer.Typer(help="Manage the config file.")
auth_app = typer.Typer(help="Credential checks.")
state_app = typer.Typer(help="Inspect local sync state.")
app.add_typer(config_app, name="config")
app.add_typer(auth_app, name="auth")
app.add_typer(state_app, name="state")

EXAMPLE_CONFIG = Path(__file__).parent.parent / "config.example.yaml"

# Override set by the root callback when --config-path is given.
_CONFIG_OVERRIDE: Path | None = None
_LOG_LEVEL_OVERRIDE: str | None = None


def _cfg_path() -> Path:
    return _CONFIG_OVERRIDE if _CONFIG_OVERRIDE is not None else config_path()


def _get_log_level(cfg_level: str) -> str:
    return _LOG_LEVEL_OVERRIDE if _LOG_LEVEL_OVERRIDE is not None else cfg_level


def _version_callback(value: bool) -> None:
    if value:
        from easyatcal import __version__

        typer.echo(f"easyatcal {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    config_path_override: Path | None = typer.Option(  # noqa: B008
        None,
        "--config-path",
        help="Override the default config file location.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Set log level to DEBUG.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Set log level to WARNING.",
    ),
    _version: bool = typer.Option(  # noqa: B008
        False,
        "--version",
        help="Print version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    global _CONFIG_OVERRIDE
    global _LOG_LEVEL_OVERRIDE
    _CONFIG_OVERRIDE = config_path_override
    if verbose:
        _LOG_LEVEL_OVERRIDE = "DEBUG"
    elif quiet:
        _LOG_LEVEL_OVERRIDE = "WARNING"


# ---------- helpers ----------

def _build_api_client(cfg: Config) -> ShiftFetcher:
    if cfg.easyatwork.auth_mode == "client":
        # OAuth public-API mode (kept for forward-compat).
        assert cfg.easyatwork.client_id and cfg.easyatwork.client_secret
        return EawClient(
            client_id=cfg.easyatwork.client_id,
            client_secret=cfg.easyatwork.client_secret,
            base_url=cfg.easyatwork.base_url,
            token_cache=token_cache_path(),
        )
    # auth_mode == "user" — JWT Bearer mode (token from localStorage)
    return SessionEawClient(
        shifts_url=cfg.easyatwork.shifts_url(),
        session_store=SessionStore(session_state_path()),
        origin=cfg.easyatwork.app_url,
        ui_version=cfg.easyatwork.ui_version,
    )


def _build_backend(cfg: Config) -> CalendarBackend:
    if cfg.backend == "ics":
        return IcsBackend(
            output_path=Path(cfg.backends.ics.output_path).expanduser(),
            known_shifts=[],
        )
    if cfg.backend == "eventkit":
        from easyatcal.backends.eventkit import EventKitBackend
        return EventKitBackend(
            calendar_name=cfg.backends.eventkit.calendar_name,
            calendar_source=cfg.backends.eventkit.calendar_source,
        )
    raise RuntimeError(f"Unknown backend: {cfg.backend}")


# ---------- config ----------

@config_app.command("init")
def config_init() -> None:
    """Scaffold a config file at the user config dir."""
    target = _cfg_path()
    if target.exists():
        typer.echo(f"Config already exists at {target}", err=True)
        raise typer.Exit(code=1)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(EXAMPLE_CONFIG, target)
    typer.echo(f"Wrote {target}. Edit it before running `eaw-sync sync`.")


@config_app.command("show")
def config_show() -> None:
    """Print the effective config with secrets redacted."""
    cfg = load_config(_cfg_path())
    dumped = cfg.model_dump()
    if dumped["easyatwork"].get("client_secret"):
        dumped["easyatwork"]["client_secret"] = "***"
    typer.echo(yaml.safe_dump(dumped, sort_keys=False))


# ---------- login (session auth) ----------

@app.command("login")
def login_cmd(
    password_env: str = typer.Option(
        "EAW_PASSWORD",
        "--password-env",
        help="Env var holding the password. If unset, prompt interactively.",
    ),
    headful: bool = typer.Option(
        False,
        "--headful",
        help="Run browser visibly (debug failing login).",
    ),
) -> None:
    """Open a headless browser, log in to easy@work, persist the session.

    Requires ``auth_mode: user`` and ``email`` in config, plus the
    ``playwright`` optional extra installed.
    """
    import os

    from easyatcal.auth_user import LoginError, PlaywrightMissingError, do_login

    cfg = load_config(_cfg_path())
    configure_logging(
        level=_get_log_level(cfg.logging.level),
        log_file=log_path(),
        fmt=cfg.logging.format,
    )

    if cfg.easyatwork.auth_mode != "user":
        typer.echo("auth_mode is not 'user' — nothing to log in to.", err=True)
        raise typer.Exit(code=1)

    password = os.environ.get(password_env)
    if password is None:
        password = typer.prompt("Password", hide_input=True)
    if not password:
        typer.echo("Empty password — aborting.", err=True)
        raise typer.Exit(code=1)

    auth = cfg.easyatwork.model_copy(update={"headless": not headful})
    storage = session_state_path()

    try:
        do_login(cfg=auth, password=password, storage_path=storage)
    except PlaywrightMissingError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1) from e
    except LoginError as e:
        typer.echo(f"Login failed: {e}", err=True)
        raise typer.Exit(code=2) from e
    typer.echo(f"Logged in. Session stored at {storage}")


@app.command("logout")
def logout_cmd() -> None:
    """Delete the persisted session cookies."""
    path = session_state_path()
    store = SessionStore(path)
    store.clear()
    typer.echo(f"Cleared {path}")


# ---------- sync / watch ----------

@app.command("sync")
def sync_cmd(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Compute changes without touching calendar or state."
    ),
) -> None:
    """Run one sync pass and exit."""
    cfg = load_config(_cfg_path())
    configure_logging(level=_get_log_level(cfg.logging.level), log_file=log_path(), fmt=cfg.logging.format)
    api = _build_api_client(cfg)
    backend = _build_backend(cfg)
    if dry_run:
        from datetime import datetime, timedelta

        from easyatcal.state import load_state
        from easyatcal.sync import compute_changes

        now = datetime.now(UTC)
        from_date = (now - timedelta(days=cfg.sync.lookback_days)).date()
        to_date = (now + timedelta(days=cfg.sync.lookahead_days)).date()
        remote = api.fetch_shifts(
            from_date=from_date, to_date=to_date, user_id=cfg.sync.user_id
        )
        state = load_state(state_path())
        changes = compute_changes(
            remote, state, known_updated_at=state.shift_updated_at
        )
        typer.echo(
            f"Dry run: {len(changes.adds)} add, "
            f"{len(changes.updates)} update, "
            f"{len(changes.deletes)} delete."
        )
        return
    from easyatcal.backends.base import BackendError

    try:
        summary = run_sync(
            api=api,
            backend=backend,
            state_path=state_path(),
            lookback_days=cfg.sync.lookback_days,
            lookahead_days=cfg.sync.lookahead_days,
            user_id=cfg.sync.user_id,
        )
    except BackendError as e:
        typer.echo(f"Sync partial failure: {e}")
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.echo(f"Sync failed: {e}")
        raise typer.Exit(code=2) from e
    typer.echo(
        f"Sync complete: {summary.adds} added, "
        f"{summary.updates} updated, {summary.deletes} deleted."
    )


@app.command("watch")
def watch_cmd(
    interval_seconds: int = typer.Option(
        900, "--interval-seconds", help="Seconds between sync passes."
    ),
) -> None:
    """Run sync on a loop until Ctrl-C or SIGTERM."""
    import signal

    from easyatcal.backends.base import BackendError

    cfg = load_config(_cfg_path())
    configure_logging(level=_get_log_level(cfg.logging.level), log_file=log_path(), fmt=cfg.logging.format)
    api = _build_api_client(cfg)
    backend = _build_backend(cfg)

    stop = False

    def _handler(signum: int, _frame: Any) -> None:  # noqa: ARG001
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, _handler)

    consecutive_errors = 0
    max_backoff = 3600

    try:
        while not stop:
            try:
                run_sync(
                    api=api,
                    backend=backend,
                    state_path=state_path(),
                    lookback_days=cfg.sync.lookback_days,
                    lookahead_days=cfg.sync.lookahead_days,
                    user_id=cfg.sync.user_id,
                )
                consecutive_errors = 0
                sleep_time = interval_seconds
            except BackendError as e:
                typer.echo(f"Sync partial failure: {e}", err=True)
                consecutive_errors = 0
                sleep_time = interval_seconds
            except Exception as e:
                consecutive_errors += 1
                sleep_time = min(interval_seconds * (2 ** (consecutive_errors - 1)), max_backoff)
                typer.echo(f"Sync failed: {e}. Backing off for {sleep_time}s.", err=True)

            if stop:
                break
            typer.echo(f"Sleeping {sleep_time}s...")
            # Sleep in 1s slices so SIGTERM exits promptly.
            for _ in range(sleep_time):
                if stop:
                    break
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    typer.echo("\nStopped.")


@app.command("install-completion")
def install_completion_cmd() -> None:
    """Install shell auto-completions for eaw-sync."""
    import os
    import subprocess


    # Run typer's underlying completion installation
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        subprocess.run(["eaw-sync", "--install-completion", "zsh"], check=False)
    elif "bash" in shell:
        subprocess.run(["eaw-sync", "--install-completion", "bash"], check=False)
    elif "fish" in shell:
        subprocess.run(["eaw-sync", "--install-completion", "fish"], check=False)
    else:
        typer.echo(f"Unsupported shell: {shell}. Try running: eaw-sync --install-completion [bash|zsh|fish]", err=True)
        raise typer.Exit(code=1)
    typer.echo("Restart your shell to apply completions.")

# ---------- state ----------

@state_app.command("show")
def state_show() -> None:
    """Print a summary of the local sync state."""
    from easyatcal.state import load_state

    sp = state_path()
    state = load_state(sp)
    typer.echo(f"Path: {sp}")
    typer.echo(f"Tracked shifts: {len(state.shift_to_event)}")
    typer.echo(f"Last sync: {state.last_sync or 'never'}")


@state_app.command("clear")
def state_clear(
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Confirm deletion without prompting."
    ),
) -> None:
    """Delete the local state file. Next sync rebuilds from scratch."""
    sp = state_path()
    if not yes:
        typer.echo(
            f"Refusing to delete {sp} without --yes. "
            "A full resync will re-create every event."
        )
        raise typer.Exit(code=1)
    if sp.exists():
        sp.unlink()
        typer.echo(f"Deleted {sp}.")
    else:
        typer.echo(f"No state at {sp}; nothing to do.")


# ---------- doctor ----------

@app.command("doctor")
def doctor_cmd() -> None:
    """Check config, credentials, and backend wiring."""
    from easyatcal.api import AuthError

    failures = 0
    cfg_file = _cfg_path()

    # 1. Config
    if not cfg_file.exists():
        typer.echo(f"[FAIL] config: not found at {cfg_file}")
        typer.echo("       Run `eaw-sync config init`.")
        raise typer.Exit(code=1)
    try:
        cfg = load_config(cfg_file)
        typer.echo(f"[ OK ] config: loaded from {cfg_file}")
    except Exception as e:
        typer.echo(f"[FAIL] config: {e}")
        raise typer.Exit(code=1) from e

    configure_logging(level=cfg.logging.level, log_file=log_path(), fmt=cfg.logging.format)

    # 2. Auth
    mode = cfg.easyatwork.auth_mode
    try:
        api = _build_api_client(cfg)
        api.authenticate()
        if mode == "client":
            typer.echo("[ OK ] auth: OAuth token obtained")
        else:
            typer.echo("[ OK ] auth: session cookies loaded")
    except AuthError as e:
        typer.echo(f"[FAIL] auth ({mode}): {e}")
        if mode == "user":
            typer.echo("       Run `eaw-sync login` to create a session.")
        failures += 1
    except Exception as e:
        typer.echo(f"[FAIL] auth ({mode}): {e}")
        failures += 1

    # 3. Backend
    try:
        _build_backend(cfg)
        typer.echo(f"[ OK ] backend: {cfg.backend} reachable")
    except Exception as e:
        typer.echo(f"[FAIL] backend ({cfg.backend}): {e}")
        failures += 1

    # 4. State directory writable
    sp = state_path()
    try:
        sp.parent.mkdir(parents=True, exist_ok=True)
        probe = sp.parent / ".eaw-sync-doctor-probe"
        probe.write_text("ok")
        probe.unlink()
        typer.echo(f"[ OK ] state: {sp.parent} writable")
    except OSError as e:
        typer.echo(f"[FAIL] state: cannot write to {sp.parent}: {e}")
        failures += 1

    if failures:
        raise typer.Exit(code=1)
    typer.echo("All checks passed.")


# ---------- auth ----------

@auth_app.command("test")
def auth_test() -> None:
    """Verify that the configured credentials can obtain a token."""
    from easyatcal.api import AuthError

    cfg = load_config(_cfg_path())
    configure_logging(level=_get_log_level(cfg.logging.level), log_file=log_path(), fmt=cfg.logging.format)
    api = _build_api_client(cfg)
    try:
        api.authenticate()
    except AuthError as e:
        typer.echo(f"Auth failed: {e}")
        raise typer.Exit(code=2) from e
    typer.echo("OK -- credentials work.")

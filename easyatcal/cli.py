from __future__ import annotations

import shutil
import time
from pathlib import Path

import typer
import yaml

from easyatcal.api import EawClient
from easyatcal.backends.ics import IcsBackend
from easyatcal.config import load_config
from easyatcal.logging_setup import configure_logging
from easyatcal.orchestrator import run_sync
from easyatcal.paths import (
    config_path,
    log_path,
    state_path,
    token_cache_path,
)

app = typer.Typer(help="EasyAtCal — sync easy@work shifts to Apple Calendar.")
config_app = typer.Typer(help="Manage the config file.")
auth_app = typer.Typer(help="Credential checks.")
app.add_typer(config_app, name="config")
app.add_typer(auth_app, name="auth")

EXAMPLE_CONFIG = Path(__file__).parent.parent / "config.example.yaml"


# ---------- helpers ----------

def _build_api_client(cfg):
    return EawClient(
        client_id=cfg.easyatwork.client_id,
        client_secret=cfg.easyatwork.client_secret,
        base_url=cfg.easyatwork.base_url,
        token_cache=token_cache_path(),
    )


def _build_backend(cfg):
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
    target = config_path()
    if target.exists():
        typer.echo(f"Config already exists at {target}", err=True)
        raise typer.Exit(code=1)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(EXAMPLE_CONFIG, target)
    typer.echo(f"Wrote {target}. Edit it before running `eaw-sync sync`.")


@config_app.command("show")
def config_show() -> None:
    """Print the effective config with secrets redacted."""
    cfg = load_config(config_path())
    dumped = cfg.model_dump()
    dumped["easyatwork"]["client_secret"] = "***"
    typer.echo(yaml.safe_dump(dumped, sort_keys=False))


# ---------- sync / watch ----------

@app.command("sync")
def sync_cmd() -> None:
    """Run one sync pass and exit."""
    cfg = load_config(config_path())
    configure_logging(level=cfg.logging.level, log_file=log_path())
    api = _build_api_client(cfg)
    backend = _build_backend(cfg)
    run_sync(
        api=api,
        backend=backend,
        state_path=state_path(),
        lookback_days=cfg.sync.lookback_days,
        lookahead_days=cfg.sync.lookahead_days,
    )
    typer.echo("Sync complete.")


@app.command("watch")
def watch_cmd(
    interval_seconds: int = typer.Option(
        900, "--interval-seconds", help="Seconds between sync passes."
    ),
) -> None:
    """Run sync on a loop until Ctrl-C."""
    cfg = load_config(config_path())
    configure_logging(level=cfg.logging.level, log_file=log_path())
    api = _build_api_client(cfg)
    backend = _build_backend(cfg)
    try:
        while True:
            run_sync(
                api=api,
                backend=backend,
                state_path=state_path(),
                lookback_days=cfg.sync.lookback_days,
                lookahead_days=cfg.sync.lookahead_days,
            )
            typer.echo(f"Sleeping {interval_seconds}s...")
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        typer.echo("\nStopped.")


# ---------- doctor ----------

@app.command("doctor")
def doctor_cmd() -> None:
    """Check config, credentials, and backend wiring."""
    from easyatcal.api import AuthError

    failures = 0
    cfg_file = config_path()

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
        raise typer.Exit(code=1)

    configure_logging(level=cfg.logging.level, log_file=log_path())

    # 2. Auth
    try:
        api = _build_api_client(cfg)
        api.authenticate()
        typer.echo("[ OK ] auth: token obtained")
    except AuthError as e:
        typer.echo(f"[FAIL] auth: {e}")
        failures += 1
    except Exception as e:
        typer.echo(f"[FAIL] auth: {e}")
        failures += 1

    # 3. Backend
    try:
        _build_backend(cfg)
        typer.echo(f"[ OK ] backend: {cfg.backend} reachable")
    except Exception as e:
        typer.echo(f"[FAIL] backend ({cfg.backend}): {e}")
        failures += 1

    if failures:
        raise typer.Exit(code=1)
    typer.echo("All checks passed.")


# ---------- auth ----------

@auth_app.command("test")
def auth_test() -> None:
    """Verify that the configured credentials can obtain a token."""
    from easyatcal.api import AuthError

    cfg = load_config(config_path())
    configure_logging(level=cfg.logging.level, log_file=log_path())
    api = _build_api_client(cfg)
    try:
        api.authenticate()
    except AuthError as e:
        typer.echo(f"Auth failed: {e}")
        raise typer.Exit(code=2)
    typer.echo("OK -- credentials work.")

# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[SemVer](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] — 2026-04-20

### Changed
- Backends now return `ApplyResult(mapping, deleted_uids)` and raise
  `BackendError(message, partial)` on failure. The orchestrator catches the
  error, persists partial progress, then re-raises — so a crash mid-apply no
  longer leaves `state.json` out of sync with the calendar.

### Added
- `eaw-sync doctor` preflight command: checks config, auth, backend wiring.
- `eaw-sync state show`: prints local state path, tracked-shift count, last sync.
- `eaw-sync sync --dry-run`: computes adds/updates/deletes without touching
  the calendar or state.
- Global `--config-path` override and `--version` flag.
- Defined `sync` exit codes: 0 clean, 1 partial failure (`BackendError`),
  2 fatal (config/auth/network).
- Post-sync summary line (`Sync complete: X added, Y updated, Z deleted.`);
  `run_sync` now returns a `SyncSummary`.
- `logging.format: text|json` config option; JSON formatter suitable for log
  aggregators.
- `watch` handles `SIGTERM` gracefully (launchctl unload / systemd stop),
  sleeps in 1-second slices for quick exit.
- API backoff honors `Retry-After` header on 429/5xx responses.
- `examples/launchd/com.easyatcal.watch.plist`: sample launchd agent for
  auto-running `sync` every 15 minutes.
- Ruff config + `.pre-commit-config.yaml`; CI now lints and enforces 85%
  coverage.
- `py.typed` marker so downstream projects see EasyAtCal's type hints.
- `CHANGELOG.md`, expanded `README.md`, `LICENSE` (MIT).
- GitHub Actions workflow to publish to PyPI on `v*` tags via trusted
  publisher.

## [0.1.0] — 2026-04-19

### Added
- Initial release.
- `Shift` model, pydantic-v2 config loader with env overrides, atomic JSON
  state with corrupt-file recovery.
- easy@work OAuth2 client-credentials auth with token cache, paginated
  `fetch_shifts`, exponential backoff on 429/5xx.
- Pluggable `CalendarBackend` protocol, diff engine (`compute_changes`).
- ICS file backend and macOS EventKit backend (pyobjc).
- Typer CLI: `config init/show`, `auth test`, `sync`, `watch`.
- GitHub Actions matrix CI (Linux + macOS × Python 3.11/3.12) with
  end-to-end ICS test.

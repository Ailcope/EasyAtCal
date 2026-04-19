# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[SemVer](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `eaw-sync doctor` preflight command: checks config, auth, backend wiring.
- `eaw-sync sync --dry-run`: computes adds/updates/deletes without touching
  the calendar or state.
- `examples/launchd/com.easyatcal.watch.plist`: sample launchd agent for
  auto-running `sync` every 15 minutes.
- `CHANGELOG.md`, expanded `README.md`, `LICENSE` (MIT).
- GitHub Actions workflow to publish to PyPI on `v*` tags via trusted
  publisher.

### Changed
- Backends now return `ApplyResult(mapping, deleted_uids)` and raise
  `BackendError(message, partial)` on failure. The orchestrator catches the
  error, persists partial progress, then re-raises — so a crash mid-apply no
  longer leaves `state.json` out of sync with the calendar.

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

# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[SemVer](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Session-cookie auth via headless browser.** New `auth_mode: user`
  (now the default) drives a headless Chromium through the easy@work
  web login, persists cookies to `~/.cache/easyatcal/session.json`, and
  replays them on every HTTP call. `eaw-sync login` / `eaw-sync logout`
  commands. Password never stored on disk — passes via `EAW_PASSWORD`
  env or interactive prompt.
- `SessionEawClient` with flexible payload shape detection
  (`data` / `results` / `items` / `shifts` / bare list) and heuristic
  field mapping (`id`/`uuid`/`shiftId`, `start`/`starts_at`/`from`, …).
  Returns `AuthError` on HTTP 401 with a "run login" hint.
- `easyatcal.session.SessionStore` atomic 0600 cookie-jar persistence.
- `easyatcal.auth_user.do_login` Playwright driver with configurable
  selectors (`email_selector`, `password_selector`, `submit_selector`)
  and `headless` toggle.
- Optional `playwright` extra. `mypy.overrides` for `playwright.*`.
- 18 new tests (session store, session-mode fetch, CLI login/logout).

### Changed
- `doctor` and `auth test` now report session / OAuth status distinctly.
- `ShiftFetcher` protocol gains `authenticate() -> object`.
- `shifts_endpoint` is blank by default; sync raises a clear
  "inspect HAR" error until set.

### Added
- Structured log events in `run_sync` with `event_id` extra (`sync.fetch.ok`,
  `sync.fetch.error`, `sync.compute_changes.ok`, `sync.apply.ok`,
  `sync.apply.partial`, `sync.complete`). JSON formatter propagates `event_id`.
- `--verbose` / `--quiet` global flags override config `logging.level`.
- `user_id` parameter plumbed through `EawClient.fetch_shifts` and
  `run_sync`, so the configured `sync.user_id` narrows the API query.
- `EAW_BASE_URL` env override for `easyatwork.base_url`.
- Defensive API payload parsing: unexpected response shape now raises
  `ApiError` with the observed top-level keys.
- Exponential backoff in `watch` on consecutive fatal errors (capped 1 h).
- `mypy` strict wired into Makefile (`make types`, `make check`) and CI.
- mkdocs-material site (`docs/pages/`, `mkdocs.yml`, `.github/workflows/docs.yml`)
  auto-published to GitHub Pages from README/CONTRIBUTING/CHANGELOG.
- Dockerfile + `.dockerignore` for container deployments.
- README "Known limitations" section documenting that the easy@work API
  shape assumed by `api.py` is unverified against the reference
  `php-eaw-client` (which could not be located).

### Fixed
- Pagination: passing `params={}` to httpx on the second request was
  stripping the `cursor=…` query from the server-provided `next` URL,
  causing an infinite loop. Now reset to `None`.

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

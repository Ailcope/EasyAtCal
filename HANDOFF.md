# HANDOFF — EasyAtCal project context

Full list of files to hand to another AI so it has every bit of context from this session. The AI should use **only** the files in this list; no external lookups required to understand what was built and why.

## 1. Session transcript (MOST IMPORTANT)

Contains the entire conversation: user messages, assistant reasoning, tool calls, tool results, and the final TodoWrite list. JSONL format, one event per line.

- `/Users/ailcope/.claude/projects/-Users-ailcope-ClaudeCode-EasyAtWork/83e5cde7-97ff-4b9f-b116-8c05c6540380.jsonl`

Claude Code stores the todo list inline in the transcript as TodoWrite tool calls — no separate todo file to hand over.

## 2. Design spec & plan

- `/Users/ailcope/ClaudeCode/EasyAtWork/docs/superpowers/specs/2026-04-19-easyatcal-design.md`
- `/Users/ailcope/ClaudeCode/EasyAtWork/docs/superpowers/plans/2026-04-19-easyatcal-implementation.md`

## 3. Project root / packaging / ops

- `/Users/ailcope/ClaudeCode/EasyAtWork/pyproject.toml`
- `/Users/ailcope/ClaudeCode/EasyAtWork/.gitignore`
- `/Users/ailcope/ClaudeCode/EasyAtWork/README.md`
- `/Users/ailcope/ClaudeCode/EasyAtWork/CHANGELOG.md`
- `/Users/ailcope/ClaudeCode/EasyAtWork/LICENSE`
- `/Users/ailcope/ClaudeCode/EasyAtWork/config.example.yaml`
- `/Users/ailcope/ClaudeCode/EasyAtWork/.pre-commit-config.yaml`
- `/Users/ailcope/ClaudeCode/EasyAtWork/.github/workflows/ci.yml`
- `/Users/ailcope/ClaudeCode/EasyAtWork/.github/workflows/publish.yml`
- `/Users/ailcope/ClaudeCode/EasyAtWork/examples/launchd/com.easyatcal.watch.plist`

## 4. Source — `easyatcal/`

- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/__init__.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/models.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/config.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/state.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/api.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/sync.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/orchestrator.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/cli.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/paths.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/api_session.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/session.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/auth_user.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/logging_setup.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/backends/__init__.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/backends/base.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/backends/ics.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/backends/eventkit.py`

## 5. Tests — `tests/`

- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/__init__.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/conftest.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/fixtures/config_valid.yaml`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/test_models.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/test_config.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/test_state.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/test_api_auth.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/test_api_fetch.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/test_sync.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/test_orchestrator.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/test_cli_config.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/test_cli_config_path.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/test_cli_sync.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/test_cli_auth.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/test_cli_login.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/test_api_session.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/test_session.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/test_cli_doctor.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/test_cli_state.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/test_logging_setup.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/test_e2e_ics.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/backends/__init__.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/backends/test_base.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/backends/test_ics.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/backends/test_eventkit.py`

## Deliberately excluded

- `.venv/` — regenerate with `python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev]'`
- `.git/` — repo is mirrored at `git@github.com:Ailcope/EasyAtCal.git` (tag `v0.1.0`; `main` at `HEAD`)
- `config.yaml`, `state.json`, `token.json`, `*.ics` — never committed; user data / secrets
- `.pytest_cache/`, `__pycache__/`, `*.pyc` — build artifacts

## Status at handoff

- 53 tests passing locally (Python 3.12 on macOS). EventKit tests skipped on Linux in CI.
- Coverage gate: CI fails under 85% (see `.github/workflows/ci.yml`).
- Ruff clean; `.pre-commit-config.yaml` wires ruff + ruff-format + whitespace hooks.
- Remaining wiring work for a real user: run `eaw-sync config init`, fill in real easy@work parameters (`customer_id`, `employee_id`), run `eaw-sync login` to generate the session JWT via headless Playwright, pick `ics` or `eventkit` backend, then `eaw-sync sync` (or `eaw-sync doctor` first).

## Auth Narrative Pivot

**Critical context:** We pivoted away from pure OAuth `client_credentials`.
Authentication is now handled via **JWT Bearer** token extracted from Playwright's `localStorage` after a headless UI login. The token is replayed against `<region>.api.easyatwork.com/customers/{cid}/employees/{eid}/shifts`.
- *Commit Ref:* `48cb8b0` (JWT pivot) and `323f338` (session-cookie pivot intermediate).
- No refresh flow is implemented: JWT expires in ~1y; users must rerun `eaw-sync login` when a 401 occurs.
- `auth_user.py` uses Playwright to capture this token. It needs a live Playwright run for smoke verification before claiming absolute production-readiness.

## What was added beyond the original 19-task plan

- `LICENSE` (MIT), `CHANGELOG.md`, expanded `README.md`.
- Atomic state sync: `ApplyResult` + `BackendError(partial)`; orchestrator persists partial progress then re-raises.
- CLI: `eaw-sync doctor`, `eaw-sync state show`, `eaw-sync sync --dry-run`, global `--config-path` override, `--install-completion`.
- Sync exit codes (0 clean / 1 partial / 2 fatal) and post-sync summary line.
- `logging.format: text|json` (JSON formatter for log aggregators).
- `watch` handles `SIGTERM` gracefully with 1-second sleep slices.
- API backoff honors `Retry-After` header on 429/5xx.
- Ruff lint + pre-commit hooks + CI lint stage + 85% coverage gate.
- PyPI publish workflow on `v*` tags (trusted publisher; configure on pypi.org).
- launchd agent template at `examples/launchd/com.easyatcal.watch.plist`.

## Unverified assumptions

Flagged in spec "Open questions": exact easy@work API endpoint paths and pagination shape. The PHP client at `https://github.com/easyatworkas/php-eaw-client` is the reference — inspect it if the default paths in `api.py` are wrong.

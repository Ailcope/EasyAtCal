# HANDOFF — EasyAtCal project context

Full list of files to hand to another AI so it has every bit of context from this session. The AI should use **only** the files in this list; no external lookups required to understand what was built and why.

## 1. Session transcript (MOST IMPORTANT)

Contains the entire conversation: user messages, assistant reasoning, tool calls, tool results, and the final TodoWrite list. JSONL format, one event per line.

- `/Users/ailcope/.claude/projects/-Users-ailcope-ClaudeCode-EasyAtWork/83e5cde7-97ff-4b9f-b116-8c05c6540380.jsonl`

Claude Code stores the todo list inline in the transcript as TodoWrite tool calls — no separate todo file to hand over.

## 2. Design spec

- `/Users/ailcope/ClaudeCode/EasyAtWork/docs/superpowers/specs/2026-04-19-easyatcal-design.md`

## 3. Implementation plan

- `/Users/ailcope/ClaudeCode/EasyAtWork/docs/superpowers/plans/2026-04-19-easyatcal-implementation.md`

## 4. Project root / packaging

- `/Users/ailcope/ClaudeCode/EasyAtWork/pyproject.toml`
- `/Users/ailcope/ClaudeCode/EasyAtWork/.gitignore`
- `/Users/ailcope/ClaudeCode/EasyAtWork/README.md`
- `/Users/ailcope/ClaudeCode/EasyAtWork/config.example.yaml`
- `/Users/ailcope/ClaudeCode/EasyAtWork/.github/workflows/ci.yml`

## 5. Source — `easyatcal/`

- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/__init__.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/models.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/config.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/state.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/api.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/sync.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/orchestrator.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/cli.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/paths.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/logging_setup.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/backends/__init__.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/backends/base.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/backends/ics.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/easyatcal/backends/eventkit.py`

## 6. Tests — `tests/`

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
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/test_cli_sync.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/test_cli_auth.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/test_logging_setup.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/test_e2e_ics.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/backends/__init__.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/backends/test_base.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/backends/test_ics.py`
- `/Users/ailcope/ClaudeCode/EasyAtWork/tests/backends/test_eventkit.py`

## Deliberately excluded

- `.venv/` — regenerate with `python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev]'`
- `.git/` — repo is mirrored at `git@github.com:Ailcope/EasyAtCal.git` (tag `v0.1.0`)
- `config.yaml`, `state.json`, `token.json`, `*.ics` — never committed; user data / secrets
- `.pytest_cache/`, `__pycache__/`, `*.pyc` — build artifacts

## Status at handoff

- 39 tests passing locally (Python 3.12 on macOS). EventKit tests skipped on Linux in CI.
- Branch: `main` at commit `e3ec355`. Tag `v0.1.0` pushed.
- Remaining wiring work for a real user: run `eaw-sync config init`, fill in real easy@work OAuth credentials, pick `ics` or `eventkit` backend, then `eaw-sync sync`.
- Unverified assumptions (flagged in spec "Open questions"): exact easy@work API endpoint paths and pagination shape. The PHP client at `https://github.com/easyatworkas/php-eaw-client` is the reference — inspect it if the default paths in `api.py` are wrong.

# Contributing to EasyAtCal

Thanks for your interest. This project is a small, focused tool; contributions
that fit the scope are welcome.

## Scope

EasyAtCal is a **one-way** sync of easy@work shifts to Apple Calendar. Things
that belong here:

- Correctness / safety fixes (idempotency, atomic state, backoff).
- Additional read-only sources from easy@work (e.g. extra shift fields).
- Additional calendar backends that mirror the existing `CalendarBackend`
  protocol.
- Docs, tests, CI hygiene.

Things that **don't** belong here:

- Two-way sync, write-back to easy@work.
- Non-easy@work data sources.
- GUI wrappers.

If you're unsure, open an issue first.

## Dev setup

```bash
git clone git@github.com:Ailcope/EasyAtCal.git
cd EasyAtCal
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

Optional (macOS EventKit backend):

```bash
.venv/bin/pip install -e '.[eventkit]'
```

## Workflow

1. Branch off `main`.
2. TDD: write the failing test first, make it pass, keep diffs small.
3. Keep commits focused; rebase before opening the PR.
4. Run `make check` (or the commands below) before pushing.

## Quality gates

```bash
.venv/bin/ruff check easyatcal tests       # lint
.venv/bin/ruff format easyatcal tests      # format
.venv/bin/pytest --cov=easyatcal --cov-fail-under=85
```

CI runs the same three on Linux + macOS × Python 3.11/3.12. PRs below 85%
coverage will fail.

Pre-commit hooks are available — `pre-commit install` once and they run on
every `git commit`.

## Commit style

- Imperative subject, concise. `feat(cli): add --dry-run flag to sync`.
- Prefixes we use: `feat`, `fix`, `chore`, `docs`, `ci`, `refactor`, `release`.
- Don't add `Co-Authored-By` trailers.

## Reporting bugs / security

- Functional bugs: open a GitHub issue with `eaw-sync doctor` output and log
  excerpt.
- Security: see [`SECURITY.md`](./SECURITY.md); don't file a public issue.

## License

Contributions are licensed under the MIT License (see [`LICENSE`](./LICENSE)).

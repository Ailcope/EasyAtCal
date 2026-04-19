# Security Policy

## Supported versions

Only the latest minor version gets security fixes. Pin to `easyatcal>=0.2` in
production.

## Reporting a vulnerability

**Do not file a public GitHub issue.**

Email the maintainer with the subject `[SECURITY] EasyAtCal`. Include:

- Affected version (`eaw-sync --version`).
- Reproduction steps or proof-of-concept.
- Your assessment of impact.

You'll get an acknowledgement within 7 days. A fix — or a concrete plan —
within 30 days. Coordinated disclosure once a release is available.

## Threat model

EasyAtCal is a local CLI that:

- Reads easy@work OAuth2 credentials from `config.yaml`.
- Writes an OAuth token cache to `~/Library/Caches/easyatcal/token.json`
  (or the XDG equivalent) with `0600` permissions.
- Writes to Apple Calendar via EventKit or to a local `.ics` file.
- Writes a local `state.json` with shift-id → event-uid mapping.

It does not:

- Accept network input on any listening port.
- Execute anything from the remote API beyond the JSON it receives.
- Upload anything beyond OAuth requests to the configured `base_url`.

Likely classes of issue worth reporting:

- Secrets or tokens leaking into logs / stdout / `state.json`.
- State-file path traversal or TOCTOU races.
- Calendar-event or `.ics` content derived from remote data without proper
  escaping causing local client problems.
- Dependency CVEs we haven't bumped past.

## Responsible research

Please do not run destructive tests against third-party easy@work tenants. A
local mock (see `tests/test_api_*.py` for `respx` examples) is the right way
to reproduce most issues.

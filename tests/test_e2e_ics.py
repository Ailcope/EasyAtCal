"""End-to-end test using the ICS backend and a mocked easy@work API."""
from pathlib import Path

import httpx
import respx

from easyatcal.api import EawClient
from easyatcal.backends.ics import IcsBackend
from easyatcal.orchestrator import run_sync


@respx.mock
def test_end_to_end_ics(tmp_path: Path):
    token_cache = tmp_path / "token.json"
    token_cache.write_text(
        '{"access_token":"tok","expires_at":"2099-01-01T00:00:00+00:00"}'
    )
    respx.get("https://api.easyatwork.com/v1/shifts").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "s1",
                        "start": "2026-04-20T09:00:00+00:00",
                        "end": "2026-04-20T17:00:00+00:00",
                        "title": "Morning", "location": "Oslo", "notes": None,
                        "updated_at": "2026-04-18T10:00:00+00:00",
                    }
                ],
                "next": None,
            },
        )
    )
    api = EawClient(
        client_id="cid", client_secret="csecret",
        base_url="https://api.easyatwork.com", token_cache=token_cache,
    )
    ics_out = tmp_path / "shifts.ics"
    backend = IcsBackend(output_path=ics_out, known_shifts=[])

    run_sync(
        api=api,
        backend=backend,
        state_path=tmp_path / "state.json",
        lookback_days=1,
        lookahead_days=7,
    )

    body = ics_out.read_text()
    assert "SUMMARY:Morning" in body
    assert "LOCATION:Oslo" in body
    assert (tmp_path / "state.json").exists()

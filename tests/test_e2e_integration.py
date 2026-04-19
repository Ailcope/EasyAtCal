import json
from pathlib import Path

import httpx
import respx

from easyatcal.api import EawClient
from easyatcal.backends.ics import IcsBackend
from easyatcal.orchestrator import run_sync


@respx.mock
def test_real_fixture_sync(tmp_path: Path):
    fixture_path = Path(__file__).parent / "fixtures" / "easyatwork_shifts.json"
    fixture_data = json.loads(fixture_path.read_text())

    token_cache = tmp_path / "token.json"
    token_cache.write_text(
        '{"access_token":"tok","expires_at":"2099-01-01T00:00:00+00:00"}'
    )
    
    # Mock the API response with our real recorded fixture
    respx.get("https://api.easyatwork.com/v1/shifts").mock(
        return_value=httpx.Response(200, json=fixture_data)
    )
    
    api = EawClient(
        client_id="cid", client_secret="csecret",
        base_url="https://api.easyatwork.com", token_cache=token_cache,
    )
    
    ics_out = tmp_path / "shifts.ics"
    backend = IcsBackend(output_path=ics_out, known_shifts=[])

    # 1. First sync - should add 2 shifts
    summary = run_sync(
        api=api,
        backend=backend,
        state_path=tmp_path / "state.json",
        lookback_days=1,
        lookahead_days=7,
    )
    
    assert summary.adds == 2
    assert summary.updates == 0
    assert summary.deletes == 0

    ics_content = ics_out.read_text()
    assert "SUMMARY:Barista Shift" in ics_content
    assert "LOCATION:Downtown Cafe" in ics_content
    assert "DESCRIPTION:Opening shift\\, don't forget keys" in ics_content
    assert "SUMMARY:Closing Shift" in ics_content
    
    # 2. Second sync with same data - should do nothing
    summary2 = run_sync(
        api=api,
        backend=backend,
        state_path=tmp_path / "state.json",
        lookback_days=1,
        lookahead_days=7,
    )
    assert summary2.adds == 0
    assert summary2.updates == 0
    assert summary2.deletes == 0

    # 3. Third sync with deleted shift and updated shift
    fixture_data["data"].pop()  # Remove "Closing Shift"
    fixture_data["data"][0]["title"] = "Barista Shift - Updated"
    fixture_data["data"][0]["updated_at"] = "2026-05-02T12:00:00+00:00"
    respx.get("https://api.easyatwork.com/v1/shifts").mock(
        return_value=httpx.Response(200, json=fixture_data)
    )

    summary3 = run_sync(
        api=api,
        backend=backend,
        state_path=tmp_path / "state.json",
        lookback_days=1,
        lookahead_days=7,
    )
    assert summary3.adds == 0
    assert summary3.updates == 1
    assert summary3.deletes == 1
    
    ics_content3 = ics_out.read_text()
    assert "SUMMARY:Barista Shift - Updated" in ics_content3
    assert "SUMMARY:Closing Shift" not in ics_content3

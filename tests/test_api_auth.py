import json
from pathlib import Path

import httpx
import pytest
import respx

from easyatcal.api import AuthError, EawClient


@respx.mock
def test_client_credentials_fetch_token(tmp_path: Path):
    respx.post("https://api.easyatwork.com/oauth/token").mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "tok-123", "expires_in": 3600,
                  "token_type": "Bearer"},
        )
    )
    client = EawClient(
        client_id="cid",
        client_secret="csecret",
        base_url="https://api.easyatwork.com",
        token_cache=tmp_path / "token.json",
    )

    token = client.authenticate()

    assert token == "tok-123"
    cached = json.loads((tmp_path / "token.json").read_text())
    assert cached["access_token"] == "tok-123"


@respx.mock
def test_cached_token_reused(tmp_path: Path):
    cache = tmp_path / "token.json"
    cache.write_text(json.dumps({
        "access_token": "cached-tok",
        "expires_at": "2099-01-01T00:00:00+00:00",
    }))
    route = respx.post("https://api.easyatwork.com/oauth/token")

    client = EawClient(
        client_id="cid",
        client_secret="csecret",
        base_url="https://api.easyatwork.com",
        token_cache=cache,
    )
    token = client.authenticate()

    assert token == "cached-tok"
    assert route.call_count == 0


@respx.mock
def test_auth_failure_raises(tmp_path: Path):
    respx.post("https://api.easyatwork.com/oauth/token").mock(
        return_value=httpx.Response(401, json={"error": "invalid_client"})
    )
    client = EawClient(
        client_id="bad",
        client_secret="bad",
        base_url="https://api.easyatwork.com",
        token_cache=tmp_path / "token.json",
    )
    with pytest.raises(AuthError):
        client.authenticate()

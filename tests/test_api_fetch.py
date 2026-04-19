from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from easyatcal.api import ApiError, EawClient
from easyatcal.models import Shift


def _fresh_client(tmp_path: Path) -> EawClient:
    cache = tmp_path / "token.json"
    cache.write_text(
        '{"access_token":"tok","expires_at":"2099-01-01T00:00:00+00:00"}'
    )
    return EawClient(
        client_id="cid",
        client_secret="csecret",
        base_url="https://api.easyatwork.com",
        token_cache=cache,
    )


@respx.mock
def test_fetch_shifts_single_page(tmp_path: Path):
    respx.get("https://api.easyatwork.com/v1/shifts").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "s1",
                        "start": "2026-04-20T09:00:00+00:00",
                        "end": "2026-04-20T17:00:00+00:00",
                        "title": "Morning",
                        "location": "Oslo",
                        "notes": None,
                        "updated_at": "2026-04-18T10:00:00+00:00",
                    }
                ],
                "next": None,
            },
        )
    )
    client = _fresh_client(tmp_path)

    shifts = client.fetch_shifts(
        from_date=date(2026, 4, 19), to_date=date(2026, 4, 21)
    )

    assert len(shifts) == 1
    s = shifts[0]
    assert isinstance(s, Shift)
    assert s.id == "s1"
    assert s.location == "Oslo"


@respx.mock
def test_fetch_shifts_follows_pagination(tmp_path: Path):
    page1 = {
        "data": [{
            "id": "s1",
            "start": "2026-04-20T09:00:00+00:00",
            "end": "2026-04-20T17:00:00+00:00",
            "title": "A", "location": None, "notes": None,
            "updated_at": "2026-04-18T10:00:00+00:00",
        }],
        "next": "https://api.easyatwork.com/v1/shifts?cursor=abc",
    }
    page2 = {
        "data": [{
            "id": "s2",
            "start": "2026-04-21T09:00:00+00:00",
            "end": "2026-04-21T17:00:00+00:00",
            "title": "B", "location": None, "notes": None,
            "updated_at": "2026-04-18T10:00:00+00:00",
        }],
        "next": None,
    }

    def _handler(request: httpx.Request) -> httpx.Response:
        if "cursor=abc" in str(request.url):
            return httpx.Response(200, json=page2)
        return httpx.Response(200, json=page1)

    respx.get(url__regex=r"https://api\.easyatwork\.com/v1/shifts.*").mock(
        side_effect=_handler
    )
    client = _fresh_client(tmp_path)

    shifts = client.fetch_shifts(
        from_date=date(2026, 4, 19), to_date=date(2026, 4, 22)
    )
    ids = [s.id for s in shifts]
    assert ids == ["s1", "s2"]


@respx.mock
def test_fetch_shifts_retries_on_429(tmp_path: Path, monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("easyatcal.api.time.sleep", lambda s: sleeps.append(s))

    responses_iter = iter([
        httpx.Response(429),
        httpx.Response(200, json={"data": [], "next": None}),
    ])
    respx.get("https://api.easyatwork.com/v1/shifts").mock(
        side_effect=lambda req: next(responses_iter)
    )
    client = _fresh_client(tmp_path)

    shifts = client.fetch_shifts(
        from_date=date(2026, 4, 19), to_date=date(2026, 4, 22)
    )

    assert shifts == []
    assert len(sleeps) == 1
    assert sleeps[0] >= 1


@respx.mock
def test_fetch_shifts_gives_up_after_retries(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("easyatcal.api.time.sleep", lambda s: None)
    respx.get("https://api.easyatwork.com/v1/shifts").mock(
        return_value=httpx.Response(429)
    )
    client = _fresh_client(tmp_path)

    with pytest.raises(ApiError, match="rate limit"):
        client.fetch_shifts(
            from_date=date(2026, 4, 19), to_date=date(2026, 4, 22)
        )

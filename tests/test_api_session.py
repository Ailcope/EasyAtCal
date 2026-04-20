from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from easyatcal.api import AuthError
from easyatcal.api_session import SessionEawClient, _iter_rows, _parse_shift
from easyatcal.session import SessionStore

# Fake JWT: three dot-separated segments starting with "ey".
FAKE_JWT = "eyhdr." + ("x" * 40) + ".sig"
SHIFTS_URL = "https://eu-west-3.api.easyatwork.com/customers/1/employees/2/shifts"


def _seeded_store(tmp_path: Path, token: str = FAKE_JWT) -> SessionStore:
    store = SessionStore(tmp_path / "session.json")
    store.save(
        {
            "cookies": [],
            "origins": [
                {
                    "origin": "https://app.easyatwork.com",
                    "localStorage": [
                        {"name": "access_token", "value": token},
                    ],
                }
            ],
        }
    )
    return store


from unittest.mock import patch

def test_no_token_raises_authenticate(tmp_path: Path) -> None:
    with patch("keyring.get_password", return_value=None):
        client = SessionEawClient(
            shifts_url=SHIFTS_URL,
            session_store=SessionStore(tmp_path / "missing.json"),
        )
        with pytest.raises(AuthError, match="No access token"):
            client.authenticate()


@respx.mock
def test_fetch_shifts_happy_path(tmp_path: Path) -> None:
    respx.get(SHIFTS_URL).mock(
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
                        "updated_at": "2026-04-18T10:00:00+00:00",
                    }
                ],
                "next_page_url": None,
            },
        )
    )
    client = SessionEawClient(
        shifts_url=SHIFTS_URL,
        session_store=_seeded_store(tmp_path),
    )
    shifts = client.fetch_shifts(
        from_date=date(2026, 4, 20), to_date=date(2026, 4, 27)
    )
    assert len(shifts) == 1
    assert shifts[0].id == "s1"
    assert shifts[0].location == "Oslo"


@respx.mock
def test_fetch_shifts_sends_bearer_and_laravel_params(tmp_path: Path) -> None:
    route = respx.get(SHIFTS_URL).mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    with patch("keyring.get_password", return_value=FAKE_JWT):
        client = SessionEawClient(
            shifts_url=SHIFTS_URL,
            session_store=_seeded_store(tmp_path),
        )
        client.fetch_shifts(
            from_date=date(2026, 4, 20), to_date=date(2026, 4, 27)
        )
        req = route.calls.last.request
        assert req.headers["Authorization"] == f"Bearer {FAKE_JWT}"
    assert req.headers["X-Ui-Version"] == "2.313.0"
    # Space-separated Laravel datetime (url-encoded as %20 or +)
    qs = req.url.query.decode()
    assert "from=2026-04-20" in qs and "00%3A00%3A00" in qs
    assert "to=2026-04-27" in qs and "23%3A59%3A59" in qs
    assert "order_by=from" in qs
    assert "direction=asc" in qs
    assert "with%5B%5D=schedule.customer" in qs


@respx.mock
def test_fetch_shifts_401_raises_auth_error(tmp_path: Path) -> None:
    respx.get(SHIFTS_URL).mock(return_value=httpx.Response(401))
    client = SessionEawClient(
        shifts_url=SHIFTS_URL,
        session_store=_seeded_store(tmp_path),
    )
    with pytest.raises(AuthError, match="Token probably expired"):
        client.fetch_shifts(
            from_date=date(2026, 4, 20), to_date=date(2026, 4, 27)
        )


@respx.mock
def test_fetch_shifts_accepts_bare_list_and_flexible_keys(tmp_path: Path) -> None:
    respx.get(SHIFTS_URL).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "uuid": "sh-9",
                    "starts_at": "2026-04-21 09:00:00",
                    "ends_at": "2026-04-21 17:00:00",
                    "name": "Evening",
                    "place": "Bergen",
                    "updatedAt": "2026-04-19T10:00:00+00:00",
                }
            ],
        )
    )
    client = SessionEawClient(
        shifts_url=SHIFTS_URL,
        session_store=_seeded_store(tmp_path),
    )
    shifts = client.fetch_shifts(
        from_date=date(2026, 4, 20), to_date=date(2026, 4, 27)
    )
    assert shifts[0].id == "sh-9"
    assert shifts[0].title == "Evening"
    assert shifts[0].location == "Bergen"


@respx.mock
def test_parse_shift_prefers_schedule_customer_name(tmp_path: Path) -> None:
    respx.get(SHIFTS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": 42,
                        "start": "2026-04-22T09:00:00+00:00",
                        "end": "2026-04-22T17:00:00+00:00",
                        "schedule": {"customer": {"name": "Acme Corp"}},
                    }
                ]
            },
        )
    )
    client = SessionEawClient(
        shifts_url=SHIFTS_URL,
        session_store=_seeded_store(tmp_path),
    )
    shifts = client.fetch_shifts(
        from_date=date(2026, 4, 20), to_date=date(2026, 4, 27)
    )
    assert shifts[0].title == "Acme Corp"


def test_iter_rows_shapes() -> None:
    assert _iter_rows([{"a": 1}]) == [{"a": 1}]
    assert _iter_rows({"data": [{"a": 1}]}) == [{"a": 1}]
    assert _iter_rows({"results": [{"a": 1}]}) == [{"a": 1}]
    assert _iter_rows({"items": [{"a": 1}]}) == [{"a": 1}]
    assert _iter_rows({"shifts": [{"a": 1}]}) == [{"a": 1}]
    assert _iter_rows({"nope": 1}) == []
    assert _iter_rows("string") == []


def test_parse_shift_missing_fields_raises() -> None:
    with pytest.raises(ValueError, match="missing id/start/end"):
        _parse_shift({"title": "x"})

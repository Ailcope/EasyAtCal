from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from easyatcal.api import ApiError, AuthError
from easyatcal.api_session import SessionEawClient, _iter_rows, _parse_shift
from easyatcal.session import SessionStore


def _seeded_store(tmp_path: Path) -> SessionStore:
    store = SessionStore(tmp_path / "session.json")
    store.save(
        {
            "cookies": [
                {
                    "name": "SESSION",
                    "value": "abc",
                    "domain": "app.easyatwork.com",
                    "path": "/",
                }
            ]
        }
    )
    return store


def test_missing_endpoint_raises(tmp_path: Path) -> None:
    client = SessionEawClient(
        app_url="https://app.easyatwork.com",
        shifts_endpoint="",
        session_store=_seeded_store(tmp_path),
    )
    with pytest.raises(ApiError, match="shifts_endpoint"):
        client.fetch_shifts(
            from_date=date(2026, 4, 20), to_date=date(2026, 4, 27)
        )


def test_no_session_cookies_raises_authenticate(tmp_path: Path) -> None:
    client = SessionEawClient(
        app_url="https://app.easyatwork.com",
        shifts_endpoint="/api/shifts",
        session_store=SessionStore(tmp_path / "missing.json"),
    )
    with pytest.raises(AuthError, match="No session cookies"):
        client.authenticate()


@respx.mock
def test_fetch_shifts_happy_path(tmp_path: Path) -> None:
    respx.get("https://app.easyatwork.com/api/shifts").mock(
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
                "next": None,
            },
        )
    )
    client = SessionEawClient(
        app_url="https://app.easyatwork.com",
        shifts_endpoint="/api/shifts",
        session_store=_seeded_store(tmp_path),
    )
    shifts = client.fetch_shifts(
        from_date=date(2026, 4, 20), to_date=date(2026, 4, 27)
    )
    assert len(shifts) == 1
    assert shifts[0].id == "s1"
    assert shifts[0].location == "Oslo"


@respx.mock
def test_fetch_shifts_401_raises_auth_error(tmp_path: Path) -> None:
    respx.get("https://app.easyatwork.com/api/shifts").mock(
        return_value=httpx.Response(401)
    )
    client = SessionEawClient(
        app_url="https://app.easyatwork.com",
        shifts_endpoint="/api/shifts",
        session_store=_seeded_store(tmp_path),
    )
    with pytest.raises(AuthError, match="cookies rejected"):
        client.fetch_shifts(
            from_date=date(2026, 4, 20), to_date=date(2026, 4, 27)
        )


@respx.mock
def test_fetch_shifts_accepts_bare_list_and_flexible_keys(tmp_path: Path) -> None:
    respx.get("https://app.easyatwork.com/api/v2/schedules").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "uuid": "sh-9",
                    "starts_at": "2026-04-21T09:00:00+00:00",
                    "ends_at": "2026-04-21T17:00:00+00:00",
                    "name": "Evening",
                    "place": "Bergen",
                    "updatedAt": "2026-04-19T10:00:00+00:00",
                }
            ],
        )
    )
    client = SessionEawClient(
        app_url="https://app.easyatwork.com",
        shifts_endpoint="/api/v2/schedules",
        session_store=_seeded_store(tmp_path),
    )
    shifts = client.fetch_shifts(
        from_date=date(2026, 4, 20), to_date=date(2026, 4, 27)
    )
    assert shifts[0].id == "sh-9"
    assert shifts[0].title == "Evening"
    assert shifts[0].location == "Bergen"


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

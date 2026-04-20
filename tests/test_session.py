from pathlib import Path

from easyatcal.session import SessionStore


def test_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "session.json"
    store = SessionStore(path)
    state = {
        "cookies": [
            {
                "name": "SESSION",
                "value": "abc123",
                "domain": "app.easyatwork.com",
                "path": "/",
            }
        ],
        "origins": [],
    }
    store.save(state)

    assert path.exists()
    assert path.stat().st_mode & 0o777 == 0o600

    loaded = store.load()
    assert loaded == state


def test_load_missing_returns_none(tmp_path: Path) -> None:
    assert SessionStore(tmp_path / "nope.json").load() is None


def test_load_corrupt_returns_none(tmp_path: Path) -> None:
    p = tmp_path / "session.json"
    p.write_text("not json")
    assert SessionStore(p).load() is None


def test_cookies_for_httpx(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "session.json")
    store.save(
        {
            "cookies": [
                {
                    "name": "A",
                    "value": "1",
                    "domain": "app.easyatwork.com",
                    "path": "/",
                },
                {
                    "name": "B",
                    "value": "2",
                    "domain": "app.easyatwork.com",
                    "path": "/",
                },
                {"name": "", "value": "skip", "domain": "x", "path": "/"},
            ],
        }
    )
    jar = store.cookies()
    assert jar is not None
    assert jar.get("A", domain="app.easyatwork.com") == "1"
    assert jar.get("B", domain="app.easyatwork.com") == "2"


def test_clear(tmp_path: Path) -> None:
    p = tmp_path / "session.json"
    store = SessionStore(p)
    store.save({"cookies": []})
    assert p.exists()
    store.clear()
    assert not p.exists()
    # clear on missing is noop
    store.clear()

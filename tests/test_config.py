from pathlib import Path

import pytest

from easyatcal.config import Config, load_config


FIXTURE = Path(__file__).parent / "fixtures" / "config_valid.yaml"


def test_load_config_from_file():
    cfg = load_config(FIXTURE)
    assert isinstance(cfg, Config)
    assert cfg.easyatwork.client_id == "cid"
    assert cfg.backend == "ics"
    assert cfg.sync.lookback_days == 7


def test_env_override_for_secret(monkeypatch):
    monkeypatch.setenv("EAW_CLIENT_SECRET", "from-env")
    cfg = load_config(FIXTURE)
    assert cfg.easyatwork.client_secret == "from-env"


def test_invalid_backend_rejected(tmp_path):
    bad = tmp_path / "c.yaml"
    bad.write_text(FIXTURE.read_text().replace("backend: ics", "backend: nonsense"))
    with pytest.raises(Exception):
        load_config(bad)


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "missing.yaml")

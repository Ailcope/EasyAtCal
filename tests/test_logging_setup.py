import logging
from pathlib import Path

from easyatcal.logging_setup import configure_logging


def test_configure_logging_writes_to_file(tmp_path: Path):
    log_file = tmp_path / "eaw-sync.log"
    configure_logging(level="INFO", log_file=log_file)

    logging.getLogger("easyatcal").info("hello world")

    for h in logging.getLogger().handlers:
        h.flush()

    assert log_file.exists()
    assert "hello world" in log_file.read_text()


def test_configure_logging_json_format(tmp_path: Path):
    import json

    log_file = tmp_path / "eaw-sync.log"
    configure_logging(level="INFO", log_file=log_file, fmt="json")
    logging.getLogger("easyatcal").info("payload-ok")
    for h in logging.getLogger().handlers:
        h.flush()
    line = log_file.read_text().strip().splitlines()[-1]
    record = json.loads(line)
    assert record["msg"] == "payload-ok"
    assert record["level"] == "INFO"
    assert "ts" in record

"""Tests for the pivault access log functions."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from pivault.vault.log import log_event, make_log_record


def read_log(path: Path) -> list[dict[str, str | bool]]:
    """Read every record in a log file, one JSON object per line."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_make_log_record_with_entry() -> None:
    """Test that a record about an entry has every field, with the time in UTC."""
    record = make_log_record("view", "macbook", True, ("netflix", "Denzel"))
    assert set(record) == {"time", "laptop", "event", "success", "website", "username"}
    assert record["website"] == "netflix"
    assert record["username"] == "Denzel"
    assert record["success"] is True
    assert datetime.fromisoformat(str(record["time"])).utcoffset() == timedelta(0)


def test_make_log_record_without_entry() -> None:
    """Test that a record not about an entry, like a wrong 2FA code, has no entry fields."""
    record = make_log_record("twofa", "macbook", False)
    assert set(record) == {"time", "laptop", "event", "success"}
    assert record["success"] is False


def test_log_event_adds_lines(tmp_path: Path) -> None:
    """Test that each event adds one line and earlier lines are left unchanged."""
    path = tmp_path / "access.log"
    log_event(path, "view", "macbook", True, ("netflix", "Denzel"))
    first = path.read_text(encoding="utf-8")
    log_event(path, "quit", "macbook", True)
    assert path.read_text(encoding="utf-8").startswith(first)
    records = read_log(path)
    assert [record["event"] for record in records] == ["view", "quit"]


def test_log_event_line_break_stays_on_one_line(tmp_path: Path) -> None:
    """Test that a line break inside a value can't split one record into two lines."""
    path = tmp_path / "access.log"
    log_event(path, "add", "bad\nlaptop", True, ("site", "user\nname"))
    records = read_log(path)
    assert len(records) == 1
    assert records[0]["laptop"] == "bad\nlaptop"
    assert records[0]["username"] == "user\nname"


def test_bad_event_writes_nothing(tmp_path: Path) -> None:
    """Test that a typo in an event name raises ValueError and nothing is written."""
    path = tmp_path / "access.log"
    with pytest.raises(ValueError):
        log_event(path, "veiw", "macbook", True)
    assert not path.exists()

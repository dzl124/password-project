"""Access log functions for the pivault application: one JSON line per event.

Never log secrets: no passwords, master keys, 2FA codes (right or wrong),
recovery codes or the 2FA secret, and never the text typed into search.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from pivault.vault.files import append_line


# One log record: text values, except success, which is True or False.
LogRecord = dict[str, str | bool]

# Every event the vault can log. A name not in here raises ValueError.
LOG_EVENTS = frozenset({
    "connect",
    "twofa",
    "master_key",
    "lockout",
    "search",
    "view",
    "add",
    "overwrite",
    "edit",
    "delete",
    "timeout",
    "quit",
    "storage_error",
    "error",
})


def make_log_record(
    event: str,
    laptop: str,
    success: bool,
    entry: tuple[str, str] | None = None,
) -> LogRecord:
    """Build one log record, stamped with the time in UTC, without writing it.

    Args:
        event (str): What happened, one of LOG_EVENTS.
        laptop (str): Which laptop was connected, or the Pi admin account.
        success (bool): Whether it worked (for search: whether anything was found).
        entry (tuple[str, str] | None): The entry's (website, username), if
            the event is about one entry. Defaults to None.

    Returns:
        LogRecord: time, laptop, event and success, plus website and
        username when an entry is given.

    Raises:
        ValueError: If the event isn't in LOG_EVENTS.
    """
    if event not in LOG_EVENTS:
        raise ValueError(f"Invalid log event: {event!r}")
    record: LogRecord = {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "laptop": laptop,
        "event": event,
        "success": success,
    }
    if entry is not None:
        website, username = entry
        record["website"] = website
        record["username"] = username
    return record


def append_log(path: Path, record: LogRecord) -> None:
    """Add one record to the access log as one JSON line.

    json.dumps turns any line break inside a value into \\n, so one record
    can never be split into two or fake an extra line.

    Args:
        path (Path): The access log, normally settings.ACCESS_LOG_FILE.
        record (LogRecord): The record from make_log_record.

    Raises:
        OSError: If the log can't be written. The action being logged
        should not go ahead.
    """
    append_line(path, json.dumps(record))


def log_event(
    path: Path,
    event: str,
    laptop: str,
    success: bool,
    entry: tuple[str, str] | None = None,
) -> None:
    """Build a record and add it to the access log in one call.

    This is the one the app calls, for example
    log_event(settings.ACCESS_LOG_FILE, "view", laptop, True, ("netflix", "Denzel")).

    Args:
        path (Path): The access log, normally settings.ACCESS_LOG_FILE.
        event (str): What happened, one of LOG_EVENTS.
        laptop (str): Which laptop was connected, or the Pi admin account.
        success (bool): Whether it worked.
        entry (tuple[str, str] | None): The entry's (website, username), if any.

    Raises:
        ValueError: If the event isn't in LOG_EVENTS. Nothing is written.
        OSError: If the log can't be written.
    """
    append_log(path, make_log_record(event, laptop, success, entry))

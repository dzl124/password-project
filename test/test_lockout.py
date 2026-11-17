"""Tests for the pivault lockout functions."""

from pathlib import Path

import pytest

from pivault import settings
from pivault.vault.lockout import (
    LOCKOUT_FIELDS,
    is_locked,
    load_lockout,
    new_lockout_state,
    record_failure,
    record_success,
    save_lockout,
    seconds_left,
)
from pivault.vault.storage import StorageError

# A made-up "now", in whole seconds, so tests never depend on the real clock.
NOW = 1000


def test_new_state_save_and_load(tmp_path: Path) -> None:
    """Test that a fresh state is all zeros and survives a save and load."""
    state = new_lockout_state()
    assert set(state) == LOCKOUT_FIELDS
    assert all(value == 0 for value in state.values())
    path = tmp_path / "lockout.json"
    save_lockout(path, state)
    assert load_lockout(path) == state
    assert path.stat().st_mode & 0o777 == 0o600


def test_load_lockout_fails_closed(tmp_path: Path) -> None:
    """Test that a missing or damaged file raises StorageError instead of meaning no lockout."""
    path = tmp_path / "lockout.json"
    with pytest.raises(StorageError):
        load_lockout(path)
    damaged = [
        "not json",
        "[]",
        '{"twofa_failures": 0, "master_key_failures": 0}',
        '{"twofa_failures": -1, "master_key_failures": 0, "locked_until": 0}',
        '{"twofa_failures": true, "master_key_failures": 0, "locked_until": 0}',
    ]
    for text in damaged:
        path.write_text(text, encoding="utf-8")
        with pytest.raises(StorageError):
            load_lockout(path)


def test_third_failure_locks_for_ten_minutes() -> None:
    """Test that two wrong tries don't lock, and the third locks for LOCKOUT_SECONDS."""
    state = new_lockout_state()
    assert not record_failure(state, "twofa_failures", NOW)
    assert not record_failure(state, "twofa_failures", NOW)
    assert record_failure(state, "twofa_failures", NOW)
    assert state["locked_until"] == NOW + settings.LOCKOUT_SECONDS
    assert state["twofa_failures"] == 0
    assert seconds_left(state, NOW) == settings.LOCKOUT_SECONDS
    assert is_locked(state, NOW + settings.LOCKOUT_SECONDS - 1)
    assert not is_locked(state, NOW + settings.LOCKOUT_SECONDS)
    assert seconds_left(state, NOW + 2 * settings.LOCKOUT_SECONDS) == 0


def test_success_resets_only_its_own_counter() -> None:
    """Test that a right 2FA code resets the 2FA counter and leaves the rest alone."""
    state = new_lockout_state()
    record_failure(state, "twofa_failures", NOW)
    record_failure(state, "twofa_failures", NOW)
    record_failure(state, "master_key_failures", NOW)
    record_success(state, "twofa_failures")
    assert state == {"twofa_failures": 0, "master_key_failures": 1, "locked_until": 0}
    assert not record_failure(state, "twofa_failures", NOW)


def test_bad_counter_name_changes_nothing() -> None:
    """Test that a typo in a counter name raises ValueError and leaves the state alone."""
    state = new_lockout_state()
    with pytest.raises(ValueError):
        record_failure(state, "twofa_fail", NOW)
    with pytest.raises(ValueError):
        record_success(state, "twofa_fail")
    assert state == new_lockout_state()

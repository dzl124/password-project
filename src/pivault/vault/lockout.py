"""Lockout functions for the pivault application: wrong-attempt counters and the lockout timer."""

import json
from pathlib import Path

from pivault import settings
from pivault.vault.files import save_file_safely
from pivault.vault.storage import StorageError


# The lockout file's contents: the two counters and locked_until, all whole numbers.
LockoutState = dict[str, int]

# Each counter's name and how many wrong tries it allows before a lockout.
COUNTER_LIMITS = {
    "twofa_failures": settings.MAX_WRONG_2FA_ATTEMPTS,
    "master_key_failures": settings.MAX_WRONG_MASTER_KEY_ATTEMPTS,
}

# The exact keys lockout.json must have: both counters plus the lockout end time.
LOCKOUT_FIELDS = frozenset({*COUNTER_LIMITS, "locked_until"})


def new_lockout_state() -> LockoutState:
    """Make a fresh lockout state: no wrong tries and no lockout.

    vault-setup saves this as the first lockout.json.

    Returns:
        LockoutState: Both counters and locked_until set to 0.
    """
    return {key: 0 for key in LOCKOUT_FIELDS}


def save_lockout(path: Path, state: LockoutState) -> None:
    """Save the lockout state, crash-safe and owner-only.

    Args:
        path (Path): The lockout file, normally settings.LOCKOUT_FILE.
        state (LockoutState): The state to save.

    Raises:
        OSError: Passed on from save_file_safely if the folder is missing
        or the disk is full.
    """
    save_file_safely(path, json.dumps(state) + "\n")


def load_lockout(path: Path) -> LockoutState:
    """Read the lockout state and check that it has the right shape.

    A damaged or missing file fails closed, so breaking it can never
    erase a lockout.

    Args:
        path (Path): The lockout file, normally settings.LOCKOUT_FILE.

    Returns:
        LockoutState: Both counters and locked_until.

    Raises:
        StorageError: If the file can't be read, isn't valid JSON, isn't a
        dict with exactly LOCKOUT_FIELDS, or has a value that isn't a
        whole number of 0 or more.
    """
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise StorageError(f"Cannot read the lockout file {path}.") from error
    if not isinstance(data, dict):
        raise StorageError(f"The lockout file {path} must hold a dict.")
    if set(data) != LOCKOUT_FIELDS:
        raise StorageError(f"The lockout file {path} has missing or extra fields.")
    for value in data.values():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise StorageError(f"The lockout file {path} has a value that isn't a whole number.")

    state: LockoutState = data
    return state


def seconds_left(state: LockoutState, now: int) -> int:
    """Seconds until the lockout ends, or 0 if there is none.

    Args:
        state (LockoutState): The lockout state.
        now (int): The current time in whole seconds, like int(time.time()).

    Returns:
        int: Seconds left, never below 0.
    """
    return max(0, state["locked_until"] - now)


def is_locked(state: LockoutState, now: int) -> bool:
    """Whether the vault is locked out right now.

    Args:
        state (LockoutState): The lockout state.
        now (int): The current time in whole seconds, like int(time.time()).

    Returns:
        bool: True while a lockout is running.
    """
    return seconds_left(state, now) > 0


def record_failure(state: LockoutState, counter: str, now: int) -> bool:
    """Count one wrong try, and start a lockout on the last allowed one.

    Changes state in place; the caller saves it with save_lockout. When a
    lockout starts, that counter goes back to 0 so there are fresh tries
    after it ends.

    Args:
        state (LockoutState): The lockout state.
        counter (str): Which counter, a key of COUNTER_LIMITS.
        now (int): The current time in whole seconds, like int(time.time()).

    Returns:
        bool: True if this failure started a lockout.

    Raises:
        ValueError: If the counter isn't in COUNTER_LIMITS. Nothing is changed.
    """
    if counter not in COUNTER_LIMITS:
        raise ValueError(f"Invalid counter: {counter!r}")
    state[counter] += 1
    if state[counter] >= COUNTER_LIMITS[counter]:
        state["locked_until"] = now + settings.LOCKOUT_SECONDS
        state[counter] = 0
        return True
    return False


def record_success(state: LockoutState, counter: str) -> None:
    """Reset one counter after its step succeeds.

    Each counter resets only on its own success, so a right 2FA code
    leaves the master-key counter alone. locked_until is not touched.
    Changes state in place; the caller saves it with save_lockout.

    Args:
        state (LockoutState): The lockout state.
        counter (str): Which counter, a key of COUNTER_LIMITS.

    Raises:
        ValueError: If the counter isn't in COUNTER_LIMITS. Nothing is changed.
    """
    if counter not in COUNTER_LIMITS:
        raise ValueError(f"Invalid counter: {counter!r}")
    state[counter] = 0

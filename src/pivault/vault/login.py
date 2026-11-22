"""Login for the vault app: the lockout check, the 2FA code, then the master key."""

import time
from collections.abc import Callable

from pivault import settings
from pivault.vault.lockbox import load_lockbox, open_lockbox
from pivault.vault.lockout import (
    LockoutState,
    is_locked,
    load_lockout,
    record_failure,
    record_success,
    save_lockout,
    seconds_left,
)
from pivault.vault.log import log_event
from pivault.vault.prompts import ask_master_key, ask_twofa_code
from pivault.vault.session import Session
from pivault.vault.twofa import check_twofa_code, load_twofa_secret


class LockedOut(Exception):
    """Raised when the vault is locked out; app.py shows the time left and disconnects."""

    def __init__(self, seconds: int) -> None:
        super().__init__(f"Locked out for {seconds} more seconds.")
        self.seconds = seconds


def wall_clock() -> int:
    """Return the real date and time as whole seconds, which survives a reboot or disconnect."""
    return int(time.time())


def check_not_locked(session: Session, now: Callable[[], int] = wall_clock) -> None:
    """Refuse the session if a lockout is still running.

    Args:
        session (Session): The current session.
        now (Callable[[], int]): Gives the real time in seconds; tests pass a fake one.

    Raises:
        LockedOut: If the lockout hasn't ended.
        StorageError: If lockout.json is missing or damaged (fails closed).
    """
    state = load_lockout(session.lockout_path)
    current = now()
    if is_locked(state, current):
        log_event(session.log_path, "lockout", session.laptop, False)
        raise LockedOut(seconds_left(state, current))


def _count_failure(
    session: Session, state: LockoutState, counter: str, event: str, current: int
) -> None:
    """Count one wrong try, save it straight away, and lock out at the limit.

    Args:
        session (Session): The current session.
        state (LockoutState): The lockout state, changed in place.
        counter (str): "twofa_failures" or "master_key_failures".
        event (str): The log event, "twofa" or "master_key".
        current (int): The real time now, in seconds.

    Raises:
        LockedOut: If this try reached the limit.
    """
    locked = record_failure(state, counter, current)
    save_lockout(session.lockout_path, state)
    log_event(session.log_path, event, session.laptop, False)
    if locked:
        log_event(session.log_path, "lockout", session.laptop, False)
        raise LockedOut(seconds_left(state, current))


def ask_twofa(session: Session, now: Callable[[], int] = wall_clock) -> None:
    """Ask for 2FA codes until one is right or the lockout starts.

    Args:
        session (Session): The current session.
        now (Callable[[], int]): Gives the real time in seconds; tests pass a fake one.

    Raises:
        LockedOut: After too many wrong codes.
    """
    state = load_lockout(session.lockout_path)
    secret = load_twofa_secret(session.twofa_secret_path)
    while True:
        code = ask_twofa_code(session, settings.LIMIT_PER_SCREEN_SECONDS)
        if check_twofa_code(secret, code):
            record_success(state, "twofa_failures")
            save_lockout(session.lockout_path, state)
            log_event(session.log_path, "twofa", session.laptop, True)
            return
        _count_failure(session, state, "twofa_failures", "twofa", now())
        session.write("Wrong code.\r\n")


def unlock_vault(session: Session, now: Callable[[], int] = wall_clock) -> None:
    """Ask for the master key until it opens the lockbox or the lockout starts.

    On success the vault key is held in session.vault_key.

    Args:
        session (Session): The current session.
        now (Callable[[], int]): Gives the real time in seconds; tests pass a fake one.

    Raises:
        LockedOut: After too many wrong master keys.
    """
    state = load_lockout(session.lockout_path)
    lockbox = load_lockbox(session.lockbox_path)
    while True:
        master_key = ask_master_key(session, settings.LIMIT_PER_SCREEN_SECONDS)
        vault_key = open_lockbox(lockbox, master_key)
        if vault_key is not None:
            session.vault_key = vault_key
            record_success(state, "master_key_failures")
            save_lockout(session.lockout_path, state)
            log_event(session.log_path, "master_key", session.laptop, True)
            return
        _count_failure(session, state, "master_key_failures", "master_key", now())
        session.write("Wrong password.\r\n")

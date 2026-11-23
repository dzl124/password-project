"""Tests for the login steps: the lockout check, the 2FA code and the master key."""

import json
import time
from pathlib import Path

import pyotp
import pytest

from pivault import settings
from pivault.vault.crypto import make_vault_key
from pivault.vault.lockbox import make_lockbox, save_lockbox
from pivault.vault.lockout import LockoutState, load_lockout, new_lockout_state, save_lockout
from pivault.vault.login import LockedOut, ask_twofa, check_not_locked, unlock_vault, wall_clock
from pivault.vault.screen import CTRL_D, QuitRequested, ReadKey
from pivault.vault.session import Session
from pivault.vault.storage import StorageError
from pivault.vault.twofa import make_twofa_secret, save_twofa_secret

# A made-up "now", in whole seconds, so tests never depend on the real clock.
NOW = 1000

# Made once for the whole file, because making a lockbox runs the slow scrypt step.
MASTER_KEY = "Purple-Kettle-Orbit-42!"
VAULT_KEY = make_vault_key()
LOCKBOX = make_lockbox(VAULT_KEY, MASTER_KEY)
TWOFA_SECRET = make_twofa_secret()


def fake_now() -> int:
    """Return the made-up time, in place of the real wall clock."""
    return NOW


def fake_keyboard(keys: list[str]) -> ReadKey:
    """Return a read_key that hands out these keys in order, then None (nothing pressed)."""
    remaining = list(keys)

    def read_key(_seconds: float) -> str | None:
        return remaining.pop(0) if remaining else None

    return read_key


def fake_clock() -> float:
    """Return a screen clock that never moves, so the 3-minute limit never runs out."""
    return 0.0


def make_session(folder: Path, *lines: str, quit_after: bool = False) -> tuple[Session, list[str]]:
    """Set up a vault in folder and return a Session that types these lines, plus what was shown.

    Each line ends in Enter. With quit_after, Ctrl+D is pressed after the last line.
    """
    save_lockout(folder / "lockout.json", new_lockout_state())
    save_lockbox(folder / "lockbox.json", LOCKBOX)
    save_twofa_secret(folder / "twofa.txt", TWOFA_SECRET)
    keys = [key for line in lines for key in line + "\r"]
    if quit_after:
        keys.append(CTRL_D)
    shown: list[str] = []
    session = Session(
        "macbook",
        fake_keyboard(keys),
        shown.append,
        log_path=folder / "access.log",
        lockout_path=folder / "lockout.json",
        lockbox_path=folder / "lockbox.json",
        twofa_secret_path=folder / "twofa.txt",
        clock=fake_clock,
    )
    return session, shown


def set_lockout(session: Session, state: LockoutState) -> None:
    """Replace the session's lockout file with this state."""
    save_lockout(session.lockout_path, state)


def read_log(session: Session) -> list[tuple[str, bool]]:
    """Return each log line as (event, success), or [] if nothing was logged."""
    if not session.log_path.exists():
        return []
    lines = session.log_path.read_text(encoding="utf-8").splitlines()
    return [(record["event"], record["success"]) for record in map(json.loads, lines)]


def right_code() -> str:
    """Return the 2FA code an authenticator app would show right now."""
    return pyotp.TOTP(TWOFA_SECRET).now()


def wrong_code() -> str:
    """Return a 6-digit code that isn't the right one."""
    return f"{(int(right_code()) + 500000) % 1000000:06d}"


# LockedOut and wall_clock

def test_locked_out_carries_seconds() -> None:
    """Test that LockedOut keeps the seconds left, for app.py to show."""
    error = LockedOut(600)
    assert error.seconds == 600
    assert "600" in str(error)


def test_wall_clock_is_real_time() -> None:
    """Test that wall_clock gives the real time in whole seconds."""
    before = int(time.time())
    assert before <= wall_clock() <= before + 1


# check_not_locked

def test_check_not_locked_fresh(tmp_path: Path) -> None:
    """Test that a fresh lockout file lets you through and logs nothing."""
    session, _ = make_session(tmp_path)
    check_not_locked(session, fake_now)
    assert not read_log(session)


def test_check_not_locked_refuses(tmp_path: Path) -> None:
    """Test that a running lockout raises LockedOut with the seconds left."""
    session, _ = make_session(tmp_path)
    set_lockout(session, {**new_lockout_state(), "locked_until": NOW + 600})
    with pytest.raises(LockedOut) as caught:
        check_not_locked(session, fake_now)
    assert caught.value.seconds == 600


def test_check_not_locked_logs(tmp_path: Path) -> None:
    """Test that a refused session is logged as a failed lockout."""
    session, _ = make_session(tmp_path)
    set_lockout(session, {**new_lockout_state(), "locked_until": NOW + 60})
    with pytest.raises(LockedOut):
        check_not_locked(session, fake_now)
    assert read_log(session) == [("lockout", False)]


def test_check_not_locked_ends_on_time(tmp_path: Path) -> None:
    """Test that you're let back in at exactly the second the lockout ends."""
    session, _ = make_session(tmp_path)
    set_lockout(session, {**new_lockout_state(), "locked_until": NOW})
    check_not_locked(session, fake_now)


def test_check_not_locked_missing_file(tmp_path: Path) -> None:
    """Test that a missing lockout file fails closed with StorageError."""
    session, _ = make_session(tmp_path)
    session.lockout_path.unlink()
    with pytest.raises(StorageError):
        check_not_locked(session, fake_now)


# ask_twofa

def test_ask_twofa_right_code(tmp_path: Path) -> None:
    """Test that the right code lets you through and is logged as a success."""
    session, _ = make_session(tmp_path, right_code())
    ask_twofa(session, fake_now)
    assert read_log(session) == [("twofa", True)]


def test_ask_twofa_wrong_then_right(tmp_path: Path) -> None:
    """Test that a wrong code says so, asks again, and the counter resets on success."""
    session, shown = make_session(tmp_path, wrong_code(), right_code())
    ask_twofa(session, fake_now)
    assert "Wrong code." in "".join(shown)
    assert load_lockout(session.lockout_path)["twofa_failures"] == 0
    assert read_log(session) == [("twofa", False), ("twofa", True)]


def test_ask_twofa_three_wrong_locks(tmp_path: Path) -> None:
    """Test that 3 wrong codes start a 10-minute lockout and reset the counter."""
    session, _ = make_session(tmp_path, wrong_code(), wrong_code(), wrong_code())
    with pytest.raises(LockedOut) as caught:
        ask_twofa(session, fake_now)
    state = load_lockout(session.lockout_path)
    assert caught.value.seconds == settings.LOCKOUT_SECONDS
    assert state["locked_until"] == NOW + settings.LOCKOUT_SECONDS
    assert state["twofa_failures"] == 0
    assert read_log(session)[-1] == ("lockout", False)


def test_ask_twofa_failure_saved_straight_away(tmp_path: Path) -> None:
    """Test that wrong codes are saved before you can quit, so reconnecting can't dodge them."""
    session, _ = make_session(tmp_path, wrong_code(), wrong_code(), quit_after=True)
    with pytest.raises(QuitRequested):
        ask_twofa(session, fake_now)
    assert load_lockout(session.lockout_path)["twofa_failures"] == 2


def test_ask_twofa_leaves_master_key_counter(tmp_path: Path) -> None:
    """Test that a right 2FA code doesn't reset the master-key counter."""
    session, _ = make_session(tmp_path, right_code())
    set_lockout(session, {**new_lockout_state(), "master_key_failures": 2})
    ask_twofa(session, fake_now)
    assert load_lockout(session.lockout_path)["master_key_failures"] == 2


# unlock_vault

def test_unlock_vault_right_key(tmp_path: Path) -> None:
    """Test that the right master key puts the vault key in the session and is logged."""
    session, _ = make_session(tmp_path, MASTER_KEY)
    unlock_vault(session, fake_now)
    assert session.vault_key == VAULT_KEY
    assert read_log(session) == [("master_key", True)]


def test_unlock_vault_wrong_then_right(tmp_path: Path) -> None:
    """Test that a wrong master key says "Wrong password.", and the counter resets on success."""
    session, shown = make_session(tmp_path, "wrong-key", MASTER_KEY)
    unlock_vault(session, fake_now)
    assert "Wrong password." in "".join(shown)
    assert session.vault_key == VAULT_KEY
    assert load_lockout(session.lockout_path)["master_key_failures"] == 0


def test_unlock_vault_three_wrong_locks(tmp_path: Path) -> None:
    """Test that 3 wrong master keys lock you out and leave the vault locked."""
    session, shown = make_session(tmp_path, "wrong-1", "wrong-2", "wrong-3")
    with pytest.raises(LockedOut):
        unlock_vault(session, fake_now)
    assert session.vault_key is None
    assert load_lockout(session.lockout_path)["locked_until"] == NOW + settings.LOCKOUT_SECONDS
    assert "".join(shown).count("Wrong password.") == 2


def test_unlock_vault_failure_saved_straight_away(tmp_path: Path) -> None:
    """Test that a wrong master key is saved before you can quit."""
    session, _ = make_session(tmp_path, "wrong-key", quit_after=True)
    with pytest.raises(QuitRequested):
        unlock_vault(session, fake_now)
    assert load_lockout(session.lockout_path)["master_key_failures"] == 1


def test_unlock_vault_empty_enter_not_counted(tmp_path: Path) -> None:
    """Test that pressing Enter with nothing typed isn't a wrong try."""
    session, _ = make_session(tmp_path, "", MASTER_KEY)
    unlock_vault(session, fake_now)
    assert read_log(session) == [("master_key", True)]

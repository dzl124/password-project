"""Tests for the Session object: its defaults, locking the vault, and locking passwords."""

import pytest

from pivault import settings
from pivault.vault.crypto import make_vault_key
from pivault.vault.session import Session

PASSWORD = "Movie!!night42"


def make_session(vault_key: bytes | None = None) -> Session:
    """Return a Session with no keyboard or screen, holding this vault key."""
    session = Session("macbook", lambda _seconds: None, lambda _text: None)
    session.vault_key = vault_key
    return session


# defaults and lock_vault

def test_session_defaults() -> None:
    """Test that a new Session uses the real files and starts locked."""
    session = make_session()
    assert session.entries_path == settings.ENTRIES_FILE
    assert session.lockout_path == settings.LOCKOUT_FILE
    assert session.vault_key is None


def test_lock_vault_forgets_key() -> None:
    """Test that lock_vault wipes the key, so passwords can't be unlocked any more."""
    session = make_session(make_vault_key())
    token = session.lock_password(PASSWORD)
    session.lock_vault()
    assert session.vault_key is None
    with pytest.raises(RuntimeError):
        session.unlock_password(token)


# lock_password

def test_lock_password_is_a_token() -> None:
    """Test that a locked password is Fernet token text, ready for entries.json."""
    token = make_session(make_vault_key()).lock_password(PASSWORD)
    assert isinstance(token, str)
    assert token.startswith("gAAAAA")


def test_lock_password_hides_password() -> None:
    """Test that the password can't be read in the locked text."""
    token = make_session(make_vault_key()).lock_password(PASSWORD)
    assert PASSWORD not in token


def test_lock_password_differs_each_time() -> None:
    """Test that one password locks to different text each time (why Edit keeps the old token)."""
    session = make_session(make_vault_key())
    assert session.lock_password(PASSWORD) != session.lock_password(PASSWORD)


def test_lock_password_refuses_when_locked() -> None:
    """Test that locking a password with no vault key raises RuntimeError."""
    with pytest.raises(RuntimeError):
        make_session().lock_password(PASSWORD)


def test_lock_password_accents_and_emoji() -> None:
    """Test that accents, ß and emoji survive locking and unlocking."""
    session = make_session(make_vault_key())
    password = "Café-straße-\N{SLIGHTLY SMILING FACE}"
    assert session.unlock_password(session.lock_password(password)) == password


# unlock_password

def test_unlock_password_round_trip() -> None:
    """Test that a locked password unlocks back to the same password."""
    session = make_session(make_vault_key())
    assert session.unlock_password(session.lock_password(PASSWORD)) == PASSWORD


def test_unlock_password_wrong_vault_key() -> None:
    """Test that a password locked with a different vault key gives None."""
    token = make_session(make_vault_key()).lock_password(PASSWORD)
    assert make_session(make_vault_key()).unlock_password(token) is None


def test_unlock_password_changed_token() -> None:
    """Test that a token with one character changed gives None."""
    session = make_session(make_vault_key())
    token = session.lock_password(PASSWORD)
    changed = token[:-5] + ("A" if token[-5] != "A" else "B") + token[-4:]
    assert session.unlock_password(changed) is None


def test_unlock_password_damaged_text() -> None:
    """Test that junk and non-ASCII text give None instead of crashing."""
    session = make_session(make_vault_key())
    assert session.unlock_password("not a token") is None
    assert session.unlock_password("gAAAAAé") is None


def test_unlock_password_refuses_when_locked() -> None:
    """Test that unlocking a password with no vault key raises RuntimeError."""
    with pytest.raises(RuntimeError):
        make_session().unlock_password("gAAAAAanything")

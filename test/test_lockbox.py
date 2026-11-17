"""Tests for the pivault lockbox functions."""

import base64
import json
from pathlib import Path

import pytest

from pivault import settings
from pivault.vault.crypto import make_vault_key
from pivault.vault.lockbox import (
    LOCKBOX_FIELDS,
    load_lockbox,
    make_lockbox,
    open_lockbox,
    save_lockbox,
)
from pivault.vault.storage import StorageError

# A sample master key, 16+ characters like a real one.
MASTER_KEY = "Purple-Kettle-Orbit-42!"
# A sample recovery code in the real shape, using only allowed characters.
RECOVERY_CODE = "ABCD-EFGH-JKMN-PQRS-TUVW"
# A well-shaped lockbox built by hand, so the load tests don't need scrypt.
FAKE_SALT = base64.b64encode(b"x" * settings.SALT_LENGTH).decode("ascii")
FAKE_LOCKBOX = {"salt": FAKE_SALT, "locked_vault_key": "gAAAAAfake-token"}


def write_lockbox_file(folder: Path, content: object) -> Path:
    """Write content as JSON (or as-is if it's text) to lockbox.json and return its path."""
    path = folder / "lockbox.json"
    text = content if isinstance(content, str) else json.dumps(content)
    path.write_text(text, encoding="utf-8")
    return path


# make_lockbox

def test_make_lockbox_shape() -> None:
    """Test that a lockbox has exactly the two fields, both as text."""
    key = make_vault_key()
    lockbox = make_lockbox(key, MASTER_KEY)
    assert set(lockbox) == LOCKBOX_FIELDS
    assert all(isinstance(value, str) for value in lockbox.values())


def test_make_lockbox_salt() -> None:
    """Test that the salt is SALT_LENGTH bytes and the lockbox opens to the same key."""
    key = make_vault_key()
    lockbox = make_lockbox(key, MASTER_KEY)
    salt = base64.b64decode(lockbox["salt"])
    assert len(salt) == settings.SALT_LENGTH
    opens = open_lockbox(lockbox, MASTER_KEY)
    assert opens == key


def test_make_lockbox_new_salt() -> None:
    """Test that the same key and secret give a new salt and token every time."""
    key = make_vault_key()
    l1 = make_lockbox(key, MASTER_KEY)
    l2 = make_lockbox(key, MASTER_KEY)
    assert l1["salt"] != l2["salt"]
    assert l1["locked_vault_key"] != l2["locked_vault_key"]


def test_make_lockbox_key_invisible() -> None:
    """Test that the vault key doesn't appear in the lockbox, so it really is locked."""
    key = make_vault_key()
    lockbox = make_lockbox(key, MASTER_KEY)
    decode = key.decode("ascii")
    assert decode not in lockbox["locked_vault_key"]


# save_lockbox

def test_save_lockbox_roundtrip(tmp_path: Path) -> None:
    """Test that a saved lockbox loads back the same and still opens."""
    key = make_vault_key()
    lockbox = make_lockbox(key, MASTER_KEY)
    path = tmp_path / "lockbox.json"
    save_lockbox(path, lockbox)
    loaded = load_lockbox(path)
    assert loaded == lockbox
    assert open_lockbox(loaded, MASTER_KEY) == key


def test_save_lockbox_owner_only(tmp_path: Path) -> None:
    """Test that a lockbox file can only be read and written by its owner."""
    path = tmp_path / "lockbox.json"
    save_lockbox(path, FAKE_LOCKBOX)
    assert path.stat().st_mode & 0o777 == 0o600


def test_save_lockbox_overwrite(tmp_path: Path) -> None:
    """Test that saving a new lockbox, as a master key change does, replaces the old one."""
    path = tmp_path / "lockbox.json"
    save_lockbox(path, FAKE_LOCKBOX)
    new = {**FAKE_LOCKBOX, "locked_vault_key": "gAAAAAnew-token"}
    save_lockbox(path, new)
    assert load_lockbox(path) == new


# load_lockbox

def test_load_lockbox_good(tmp_path: Path) -> None:
    """Test that a well-shaped lockbox loads back exactly."""
    assert load_lockbox(write_lockbox_file(tmp_path, FAKE_LOCKBOX)) == FAKE_LOCKBOX


def test_load_lockbox_missing(tmp_path: Path) -> None:
    """Test that a missing lockbox file raises StorageError."""
    with pytest.raises(StorageError):
        load_lockbox(tmp_path / "lockbox.json")


def test_load_lockbox_not_json(tmp_path: Path) -> None:
    """Test that a file that isn't JSON raises StorageError."""
    with pytest.raises(StorageError):
        load_lockbox(write_lockbox_file(tmp_path, "not json"))


def test_load_lockbox_not_dict(tmp_path: Path) -> None:
    """Test that valid JSON that isn't a dict raises StorageError."""
    with pytest.raises(StorageError):
        load_lockbox(write_lockbox_file(tmp_path, []))


def test_load_lockbox_wrong_fields(tmp_path: Path) -> None:
    """Test that a missing or an extra field raises StorageError."""
    with pytest.raises(StorageError):
        load_lockbox(write_lockbox_file(tmp_path, {"salt": FAKE_SALT}))
    with pytest.raises(StorageError):
        load_lockbox(write_lockbox_file(tmp_path, {**FAKE_LOCKBOX, "extra": "x"}))


def test_load_lockbox_not_text(tmp_path: Path) -> None:
    """Test that a value that isn't text raises StorageError."""
    with pytest.raises(StorageError):
        load_lockbox(write_lockbox_file(tmp_path, {**FAKE_LOCKBOX, "salt": 5}))


def test_load_lockbox_salt_not_base64(tmp_path: Path) -> None:
    """Test that a stray non-base64 character raises StorageError instead of being skipped."""
    sneaky = FAKE_SALT[:4] + "!" + FAKE_SALT[4:]
    with pytest.raises(StorageError):
        load_lockbox(write_lockbox_file(tmp_path, {**FAKE_LOCKBOX, "salt": sneaky}))


def test_load_lockbox_salt_wrong_length(tmp_path: Path) -> None:
    """Test that a valid base64 salt one byte too short raises StorageError."""
    short = base64.b64encode(b"x" * (settings.SALT_LENGTH - 1)).decode("ascii")
    with pytest.raises(StorageError):
        load_lockbox(write_lockbox_file(tmp_path, {**FAKE_LOCKBOX, "salt": short}))


# open_lockbox

def test_open_lockbox_wrong_secret() -> None:
    """Test that a wrong secret gives None."""
    lockbox = make_lockbox(make_vault_key(), MASTER_KEY)
    assert open_lockbox(lockbox, "Wrong-Secret-Entirely-1") is None


def test_open_lockbox_one_character_off() -> None:
    """Test that the secret with its last character changed gives None."""
    lockbox = make_lockbox(make_vault_key(), MASTER_KEY)
    assert open_lockbox(lockbox, MASTER_KEY[:-1] + "?") is None


def test_open_lockbox_accented_letter() -> None:
    """Test that both ways of writing an accented letter open the same lockbox."""
    key = make_vault_key()
    lockbox = make_lockbox(key, "Purple-caf\u00e9-Orbit-42!")
    assert open_lockbox(lockbox, "Purple-cafe\u0301-Orbit-42!") == key


def test_open_lockbox_two_lockboxes_same_key() -> None:
    """Test that the master-key and recovery lockboxes open to the same vault key."""
    key = make_vault_key()
    master = make_lockbox(key, MASTER_KEY)
    recovery = make_lockbox(key, RECOVERY_CODE)
    assert open_lockbox(master, MASTER_KEY) == key
    assert open_lockbox(recovery, RECOVERY_CODE) == key


def test_open_lockbox_secrets_not_interchangeable() -> None:
    """Test that the recovery code doesn't open the master-key lockbox."""
    master = make_lockbox(make_vault_key(), MASTER_KEY)
    assert open_lockbox(master, RECOVERY_CODE) is None

"""Lockbox functions for the pivault application: the vault key, locked by a secret."""

import base64
import json
from pathlib import Path

from pivault import settings
from pivault.vault.crypto import lock, make_key_from_secret, make_salt, unlock
from pivault.vault.files import save_file_safely
from pivault.vault.storage import StorageError


# One lockbox file's contents: the salt (base64) and the locked vault key (a Fernet token).
Lockbox = dict[str, str]

# The exact keys every lockbox file must have.
LOCKBOX_FIELDS = frozenset({"salt", "locked_vault_key"})


def make_lockbox(vault_key: bytes, secret: str) -> Lockbox:
    """Lock the vault key with a secret (the master key or the recovery code).

    Uses a new random salt every time, so two lockboxes never share one.

    Args:
        vault_key (bytes): The vault key from make_vault_key.
        secret (str): The master key or recovery code that will open it.

    Returns:
        Lockbox: The salt as base64 text and the locked vault key as text.
    """
    salt = make_salt()
    key = make_key_from_secret(secret, salt)
    locked = lock(vault_key, key)
    return {
        "salt": base64.b64encode(salt).decode("ascii"),
        "locked_vault_key": locked.decode("ascii"),
    }


def save_lockbox(path: Path, lockbox: Lockbox) -> None:
    """Save a lockbox, crash-safe and owner-only.

    Args:
        path (Path): The lockbox file, like settings.MASTER_KEY_LOCKBOX_FILE.
        lockbox (Lockbox): The lockbox from make_lockbox.

    Raises:
        OSError: Passed on from save_file_safely if the folder is missing
        or the disk is full.
    """
    save_file_safely(path, json.dumps(lockbox) + "\n")


def load_lockbox(path: Path) -> Lockbox:
    """Read a lockbox file and check that it has the right shape.

    A damaged lockbox raises StorageError here, with a clear message,
    instead of failing later at login looking like a wrong master key.

    Args:
        path (Path): The lockbox file, like settings.MASTER_KEY_LOCKBOX_FILE.

    Returns:
        Lockbox: The salt (base64 text) and the locked vault key.

    Raises:
        StorageError: If the file can't be read, isn't valid JSON, isn't a
        dict with exactly LOCKBOX_FIELDS as text, or its salt isn't valid
        base64 of SALT_LENGTH bytes.
    """
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise StorageError(f"Cannot read the lockbox file {path}.") from error
    if not isinstance(data, dict):
        raise StorageError(f"The lockbox file {path} must hold a dict.")
    if set(data) != LOCKBOX_FIELDS:
        raise StorageError(f"The lockbox file {path} has missing or extra fields.")
    if not all(isinstance(value, str) for value in data.values()):
        raise StorageError(f"The lockbox file {path} has a value that isn't text.")

    try:
        salt = base64.b64decode(data["salt"], validate=True)
    except ValueError as error:
        raise StorageError(f"The lockbox file {path} has a salt that isn't base64.") from error
    if len(salt) != settings.SALT_LENGTH:
        raise StorageError(f"The lockbox file {path} has a salt of the wrong length.")

    lockbox: Lockbox = data
    return lockbox


def open_lockbox(lockbox: Lockbox, secret: str) -> bytes | None:
    """Open a lockbox with a secret and get the vault key back.

    Slow on purpose (scrypt, about 0.4 seconds on the Pi), so guessing
    secrets takes a long time.

    Args:
        lockbox (Lockbox): The lockbox from load_lockbox.
        secret (str): The master key or recovery code, as typed.

    Returns:
        bytes | None: The vault key, or None if the secret is wrong.
    """
    salt = base64.b64decode(lockbox["salt"])
    key = make_key_from_secret(secret, salt)
    return unlock(lockbox["locked_vault_key"].encode("ascii"), key)

"""Tests for the pivault cryptographic functions."""

import pytest

from pivault import settings
from pivault.vault.crypto import (
    lock,
    make_key_from_secret,
    make_recovery_code,
    make_salt,
    make_vault_key,
    unlock,
)

# Fernet keys are 32 bytes written as base64, which is 44 characters.
FERNET_KEY_LENGTH = 44


# make_vault_key

def test_make_vault_key() -> None:
    """Test that make_vault_key returns a valid Fernet key."""
    key = make_vault_key()
    assert isinstance(key, bytes)
    assert len(key) == FERNET_KEY_LENGTH


def test_make_vault_key_unique() -> None:
    """Test that make_vault_key returns a different key each time."""
    key1 = make_vault_key()
    key2 = make_vault_key()
    assert key1 != key2


# make_salt

def test_make_salt() -> None:
    """Test that make_salt returns bytes of the right length."""
    salt = make_salt()
    assert isinstance(salt, bytes)
    assert len(salt) == settings.SALT_LENGTH


def test_make_salt_unique() -> None:
    """Test that make_salt returns a different salt each time."""
    salt1 = make_salt()
    salt2 = make_salt()
    assert salt1 != salt2


# lock and unlock

def test_lock_changes_data() -> None:
    """Test that lock actually changes the data."""
    data = b"test"
    key = make_vault_key()
    locked = lock(data, key)
    assert locked != data


def test_lock_twice_different_results() -> None:
    """Test that locking the same data twice gives different results."""
    data = b"test"
    key = make_vault_key()
    locked1 = lock(data, key)
    locked2 = lock(data, key)
    assert locked1 != locked2


def test_lock_different_keys_different_results() -> None:
    """Test that locking the same data with different keys gives different results."""
    data = b"test"
    key1 = make_vault_key()
    key2 = make_vault_key()
    locked1 = lock(data, key1)
    locked2 = lock(data, key2)
    assert locked1 != locked2


def test_unlock_right_key() -> None:
    """Test that unlock with the right key gives the original data back."""
    data = b"test"
    key = make_vault_key()
    locked = lock(data, key)
    assert unlock(locked, key) == data


def test_unlock_wrong_key() -> None:
    """Test that unlock with the wrong key gives None."""
    data = b"test"
    key = make_vault_key()
    locked = lock(data, key)
    wrong_key = make_vault_key()
    assert unlock(locked, key) == data
    assert unlock(locked, wrong_key) is None


def test_unlock_changed_data() -> None:
    """Test that unlock gives None when the locked data has been changed."""
    data = b"test"
    key = make_vault_key()
    locked = lock(data, key)
    changed = locked + b"extra"
    assert unlock(changed, key) is None


# make_key_from_secret

def test_make_key_from_secret() -> None:
    """Test that make_key_from_secret returns a valid Fernet key."""
    salt = make_salt()
    key = make_key_from_secret("test", salt)
    assert isinstance(key, bytes)
    assert len(key) == FERNET_KEY_LENGTH


def test_same_secret_same_key() -> None:
    """Test that the same secret and salt give the same key."""
    salt = make_salt()
    secret = "test"
    key1 = make_key_from_secret(secret, salt)
    key2 = make_key_from_secret(secret, salt)
    assert key1 == key2


def test_different_salts_different_keys() -> None:
    """Test that the same secret with different salts gives different keys."""
    salt1 = make_salt()
    salt2 = make_salt()
    secret = "test"
    key1 = make_key_from_secret(secret, salt1)
    key2 = make_key_from_secret(secret, salt2)
    assert key1 != key2


def test_different_secrets_different_keys() -> None:
    """Test that secrets one character apart give different keys."""
    salt = make_salt()
    secret1 = "test1"
    secret2 = "test2"
    key1 = make_key_from_secret(secret1, salt)
    key2 = make_key_from_secret(secret2, salt)
    assert key1 != key2


def test_accented_letter_same_key() -> None:
    """Test that both ways of writing é give the same key."""
    salt = make_salt()
    one_char = "café"
    two_chars = "café"
    key1 = make_key_from_secret(one_char, salt)
    key2 = make_key_from_secret(two_chars, salt)
    assert key1 == key2


def test_salt_far_too_short() -> None:
    """Test that a salt far shorter than SALT_LENGTH raises ValueError."""
    with pytest.raises(ValueError):
        make_key_from_secret("test", b"short")


def test_salt_one_byte_short() -> None:
    """Test that a salt one byte too short raises ValueError."""
    short_salt = make_salt()[:-1]
    with pytest.raises(ValueError):
        make_key_from_secret("test", short_salt)


def test_salt_one_byte_long() -> None:
    """Test that a salt one byte too long raises ValueError."""
    long_salt = make_salt() + b"x"
    with pytest.raises(ValueError):
        make_key_from_secret("test", long_salt)


def test_secret_key_locks() -> None:
    """Test that a key made from a secret can lock data."""
    salt = make_salt()
    key = make_key_from_secret("test", salt)
    data = b"test"
    locked = lock(data, key)
    assert locked != data


def test_secret_key_unlocks_right_key() -> None:
    """Test that a key made from a secret can lock and unlock data."""
    salt = make_salt()
    key = make_key_from_secret("test", salt)
    data = b"test"
    locked = lock(data, key)
    assert unlock(locked, key) == data


def test_secret_key_unlocks_wrong_key() -> None:
    """Test that data locked with a secret's key cannot be unlocked with another key."""
    salt = make_salt()
    key = make_key_from_secret("test", salt)
    wrong_key = make_vault_key()
    data = b"test"
    locked = lock(data, key)
    assert unlock(locked, wrong_key) is None


# make_recovery_code

def test_recovery_code_shape() -> None:
    """Test that the recovery code has the right number of groups, each the right length."""
    code = make_recovery_code()
    groups = code.split("-")
    assert len(groups) == settings.RECOVERY_CODE_GROUP_TOTAL
    for group in groups:
        assert len(group) == settings.RECOVERY_CODE_GROUP_SIZE


def test_recovery_code_allowed_chars() -> None:
    """Test that recovery codes only use allowed characters (no look-alikes)."""
    for _ in range(50):
        code = make_recovery_code()
        for char in code.replace("-", ""):
            assert char in settings.RECOVERY_CODE_CHARS


def test_recovery_code_unique() -> None:
    """Test that make_recovery_code returns a different code each time."""
    code1 = make_recovery_code()
    code2 = make_recovery_code()
    assert code1 != code2

"""Cryptographic functions for the pivault application."""

import base64
import secrets
import unicodedata

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from pivault import settings


def make_vault_key() -> bytes:
    """Generate a new Fernet vault key.

    Returns:
        bytes: The generated Fernet key.
    """
    return Fernet.generate_key()


def make_salt() -> bytes:
    """Generate a new random salt.

    Returns:
        bytes: The generated salt.
    """
    return secrets.token_bytes(settings.SALT_LENGTH)


def lock(data: bytes, key: bytes) -> bytes:
    """Lock (encrypt) data with the given Fernet key.

    Args:
        data (bytes): The data to lock, such as a password or the vault key.
        key (bytes): The Fernet key to lock it with.

    Returns:
        bytes: The locked data.
    """
    f = Fernet(key)
    return f.encrypt(data)


def unlock(encrypted_data: bytes, key: bytes) -> bytes | None:
    """Unlock (decrypt) data with the given Fernet key.

    Args:
        encrypted_data (bytes): The locked data, as returned by the lock function.
        key (bytes): The Fernet key it was locked with.

    Returns:
        bytes | None: The unlocked data, or None if the key is wrong
        or the data was changed.
    """
    f = Fernet(key)
    try:
        return f.decrypt(encrypted_data)
    except InvalidToken:
        return None


def make_key_from_secret(secret: str, salt: bytes) -> bytes:
    """Derive a Fernet key from a secret and a salt using scrypt.

    Used for both the master key and the recovery code.

    Args:
        secret (str): The secret to derive the key from.
        salt (bytes): The salt to use for the key derivation.

    Returns:
        bytes: The derived Fernet key.

    Raises:
        ValueError: If the salt is not SALT_LENGTH bytes, for example
        when a lockbox file is damaged.
    """
    if len(salt) != settings.SALT_LENGTH:
        raise ValueError(
            f"Salt must be {settings.SALT_LENGTH} bytes, got {len(salt)}."
        )
    secret = unicodedata.normalize("NFC", secret)
    kdf = Scrypt(
        salt=salt,
        length=32,
        n=settings.SCRYPT_N,
        r=settings.SCRYPT_R,
        p=settings.SCRYPT_P,
    )
    raw_key = kdf.derive(secret.encode("utf-8"))
    return base64.urlsafe_b64encode(raw_key)


def make_recovery_code() -> str:
    """Generate a new recovery code.

    Shown once at setup and written down on paper.

    Returns:
        str: The generated recovery code, like ABCD-EFGH-JKMN-PQRS-TUVW.
    """
    code = "".join(secrets.choice(settings.RECOVERY_CODE_CHARS)
                   for _ in range(settings.RECOVERY_CODE_LENGTH))
    groups = [code[i:i + settings.RECOVERY_CODE_GROUP_SIZE]
              for i in range(0, settings.RECOVERY_CODE_LENGTH, settings.RECOVERY_CODE_GROUP_SIZE)]
    return "-".join(groups)

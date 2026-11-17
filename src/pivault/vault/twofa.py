"""2FA functions for the pivault application: the secret, codes and the setup QR code."""

import io
import string
from pathlib import Path

import pyotp
import qrcode

from pivault import settings
from pivault.vault.files import save_file_safely
from pivault.vault.storage import StorageError


# The 32 characters a base32 secret can use: A-Z and 2-7.
BASE32_CHARS = string.ascii_uppercase + "234567"


def make_twofa_secret() -> str:
    """Make a new random 2FA secret, at setup and at each 2FA reset.

    Returns:
        str: 32 base32 characters (A-Z and 2-7), 160 bits of randomness.
    """
    return pyotp.random_base32()


def save_twofa_secret(path: Path, secret: str) -> None:
    """Save the 2FA secret, crash-safe and owner-only.

    Args:
        path (Path): The secret file, normally settings.TWOFA_SECRET_FILE.
        secret (str): The secret from make_twofa_secret.
    """
    save_file_safely(path, secret + "\n")


def load_twofa_secret(path: Path) -> str:
    """Read the 2FA secret and check that it is valid base32.

    A damaged secret would make every code fail, so it fails loudly here instead.

    Args:
        path (Path): The secret file, normally settings.TWOFA_SECRET_FILE.

    Returns:
        str: The secret, without its trailing newline.

    Raises:
        StorageError: If the file can't be read, is empty, or has a character
        that isn't in BASE32_CHARS.
    """
    try:
        secret = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as error:
        raise StorageError("Cannot read the 2FA secret file.") from error
    if not secret or not all(char in BASE32_CHARS for char in secret):
        raise StorageError("2FA secret is empty or contains invalid characters.")
    return secret


def check_twofa_code(secret: str, code: str) -> bool:
    """Check a 6-digit code typed from the authenticator app.

    Spaces are ignored, so "123 456" works. Codes from one 30-second step
    either side of now are accepted, for clock drift. Counting wrong
    attempts is the lockout module's job.

    Args:
        secret (str): The 2FA secret from load_twofa_secret.
        code (str): The code as typed.

    Returns:
        bool: True if the code is right, False if it is wrong or not 6 digits.
    """
    cleaned = code.strip().replace(" ", "")
    if len(cleaned) != 6 or not all(char in string.digits for char in cleaned):
        return False
    return pyotp.TOTP(secret).verify(cleaned, valid_window=settings.TWOFA_VALID_WINDOW)


def twofa_setup_uri(secret: str) -> str:
    """Build the otpauth:// link that the setup QR code holds.

    An authenticator app reads the name, label and secret out of it.

    Args:
        secret (str): The 2FA secret from make_twofa_secret.

    Returns:
        str: The link, like otpauth://totp/PiVault:vault?secret=...&issuer=PiVault.
    """
    return pyotp.TOTP(secret).provisioning_uri(
        name=settings.TWOFA_ACCOUNT,
        issuer_name=settings.TWOFA_ISSUER,
    )


def twofa_qr_text(uri: str) -> str:
    """Draw the setup link as a QR code made of text, for the terminal.

    Returns text rather than printing it, so the screen code decides when
    to show it and when to clear it.

    Args:
        uri (str): The link from twofa_setup_uri.

    Returns:
        str: The QR code as lines of block characters, light on dark.
    """
    qr = qrcode.QRCode()
    qr.add_data(uri)
    qr.make(fit=True)
    buffer = io.StringIO()
    qr.print_ascii(out=buffer, invert=True)
    return buffer.getvalue()


def format_setup_key(secret: str) -> str:
    """Split the secret into groups of 4 for typing by hand.

    The setup key fallback for when the QR code won't scan. Authenticator
    apps ignore the spaces.

    Args:
        secret (str): The 2FA secret from make_twofa_secret.

    Returns:
        str: The secret in groups, like JBSW Y3DP EHPK 3PXP.
    """
    size = settings.TWOFA_KEY_GROUP_SIZE
    groups = [secret[i:i + size] for i in range(0, len(secret), size)]
    return " ".join(groups)

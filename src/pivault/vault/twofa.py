"""2FA functions for the pivault application: the secret, codes and the setup QR code."""

import io
from pathlib import Path

import pyotp
import qrcode

from pivault import settings
from pivault.vault.files import save_file_safely
from pivault.vault.storage import StorageError

"""Settings for the pivault application."""

import string
from pathlib import Path

# Lockout settings
# Wrong 2FA code attempts allowed before lockout
MAX_WRONG_2FA_ATTEMPTS = 3
# Wrong master key attempts allowed before lockout
MAX_WRONG_MASTER_KEY_ATTEMPTS = 3
# Lockout duration
LOCKOUT_SECONDS = 10 * 60

# Time limits
# Limit per screen
LIMIT_PER_SCREEN_SECONDS = 3 * 60
# How long a password is visible
PASSWORD_VISIBLE_SECONDS = 30
# How long messages stay up
MESSAGE_VISIBLE_SECONDS = 7
# Delay after an incorrect search
INCORRECT_SEARCH_DELAY_SECONDS = 3

# Other settings
# How long deleted entries are kept
DELETED_ENTRIES_KEPT_SECONDS = 14 * 24 * 60 * 60  # 14 days
# Minimum master key length
MIN_MASTER_KEY_LENGTH = 16

# Encryption
# Salt length in bytes, one salt per lockbox
SALT_LENGTH = 16
# scrypt cost settings (OWASP: N=2^17, r=8, p=1), about 0.4 seconds and 128 MB on the Pi
SCRYPT_N = 2**17
SCRYPT_R = 8
SCRYPT_P = 1

# Recovery code
# Capital letters and digits, minus look-alikes (O/0, I/1/L), 31 characters
RECOVERY_CODE_ALL_CHARS = string.ascii_uppercase + string.digits
RECOVERY_CODE_BANNED_CHARS = "O", "L", "I", "0", "1"
RECOVERY_CODE_CHARS = "".join(
    char for char in RECOVERY_CODE_ALL_CHARS if char not in RECOVERY_CODE_BANNED_CHARS
)
# 20 characters in groups of 4, like ABCD-EFGH-JKMN-PQRS-TUVW
RECOVERY_CODE_LENGTH = 20
RECOVERY_CODE_GROUP_SIZE = 4
# Number of groups; LENGTH must divide evenly by GROUP_SIZE
RECOVERY_CODE_GROUP_TOTAL = RECOVERY_CODE_LENGTH // RECOVERY_CODE_GROUP_SIZE

# 2FA
# Name shown in the authenticator app
TWOFA_ISSUER = "PiVault"
# Label shown under the name in the authenticator app
TWOFA_ACCOUNT = "vault"
# 30-second steps accepted either side of now, to allow for clock drift
TWOFA_VALID_WINDOW = 1
# Setup key shown in groups of 4, like JBSW Y3DP EHPK 3PXP
TWOFA_KEY_GROUP_SIZE = 4

# Folders and files
# Vault paths
VAULT_FOLDER = Path("/var/lib/pivault")
ENTRIES_FILE = VAULT_FOLDER / "entries.json"
MASTER_KEY_LOCKBOX_FILE = VAULT_FOLDER / "master_key_lockbox.json"
RECOVERY_LOCKBOX_FILE = VAULT_FOLDER / "recovery_lockbox.json"
TWOFA_SECRET_FILE = VAULT_FOLDER / "twofa_secret.txt"
LOCKOUT_FILE = VAULT_FOLDER / "lockout.json"

# Admin paths
ADMIN_FOLDER = Path("/var/lib/pivault-admin")
DELETED_ENTRIES_FILE = ADMIN_FOLDER / "deleted_entries.jsonl"
ACCESS_LOG_FILE = ADMIN_FOLDER / "access.log"

# Entries
# Longest website name allowed
MAX_WEBSITE_LENGTH = 64
# Longest username allowed, long enough for most email addresses
MAX_USERNAME_LENGTH = 48
# Lowercase letters, digits, - and _ (no dots, spaces or accents)
WEBSITE_ALLOWED_CHARS = string.ascii_lowercase + string.digits + "-_"

"""Settings for the pivault application."""

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

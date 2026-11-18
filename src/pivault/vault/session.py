"""The Session object: everything a vault screen needs, carried in one place."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pivault import settings
from pivault.vault.screen import ReadKey, Write


@dataclass
class Session:
    """One connected laptop's session with the vault.

    Every screen takes a Session instead of six or more separate arguments.
    The paths default to the real files in settings; tests pass temporary
    ones. vault_key starts as None and holds the unlocked vault key only
    between a correct master key and the end of the action.

    Attributes:
        laptop (str): Which laptop connected, from --laptop.
        read_key (ReadKey): Where keys come from.
        write (Write): Where text is shown.
        entries_path (Path): entries.json.
        deleted_path (Path): The deleted-entries file.
        log_path (Path): The access log.
        lockout_path (Path): lockout.json.
        lockbox_path (Path): The master-key lockbox.
        twofa_secret_path (Path): The 2FA secret.
        vault_key (bytes | None): The unlocked vault key, or None when locked.
        clock (Callable[[], float]): Gives the current time in seconds;
            tests pass a fake one.
    """

    laptop: str
    read_key: ReadKey
    write: Write
    entries_path: Path = settings.ENTRIES_FILE
    deleted_path: Path = settings.DELETED_ENTRIES_FILE
    log_path: Path = settings.ACCESS_LOG_FILE
    lockout_path: Path = settings.LOCKOUT_FILE
    lockbox_path: Path = settings.MASTER_KEY_LOCKBOX_FILE
    twofa_secret_path: Path = settings.TWOFA_SECRET_FILE
    vault_key: bytes | None = None
    clock: Callable[[], float] = time.monotonic

    def lock_vault(self) -> None:
        """Forget the vault key, so nothing can be unlocked until the master key is typed again."""
        self.vault_key = None

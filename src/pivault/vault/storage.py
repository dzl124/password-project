"""Storage functions for the pivault application: entries and deleted entries."""

import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from pivault import settings
from pivault.vault.files import append_line, save_file_safely


# One saved entry: website, username and the locked password, all as text.
Entry = dict[str, str]

# The exact keys every entry in entries.json must have.
ENTRY_FIELDS = frozenset({"website", "username", "password"})

# Why an entry went to the deleted-entries file.
DELETE_REASONS = frozenset({"deleted", "overwritten"})


class StorageError(Exception):
    """Raised when the entries file is missing or damaged."""


def clean_website(website: str) -> str:
    """Clean and check a website name before it is saved.

    Trims spaces from both ends and lowercases it.

    Args:
        website (str): The website name as typed, like "  Netflix ".

    Returns:
        str: The cleaned website name, like "netflix".

    Raises:
        ValueError: If the website is empty, longer than MAX_WEBSITE_LENGTH,
        or has a character that isn't in WEBSITE_ALLOWED_CHARS.
    """
    cleaned = website.strip().lower()
    if not cleaned:
        raise ValueError("Website cannot be empty.")
    if len(cleaned) > settings.MAX_WEBSITE_LENGTH:
        raise ValueError(f"Website cannot exceed {settings.MAX_WEBSITE_LENGTH} characters.")
    for char in cleaned:
        if char not in settings.WEBSITE_ALLOWED_CHARS:
            raise ValueError(f"Website contains invalid character: {char!r}")
    return cleaned


def clean_username(username: str) -> str:
    """Clean and check a username before it is saved.

    Trims spaces from both ends and normalizes it to NFC so both ways of
    writing é match. Capitals are kept.

    Args:
        username (str): The username as typed, like "  John Doe ".

    Returns:
        str: The cleaned username, like "John Doe".

    Raises:
        ValueError: If the username is empty, longer than MAX_USERNAME_LENGTH,
        or has a character that isn't printable.
    """
    cleaned = unicodedata.normalize("NFC", username.strip())
    if not cleaned:
        raise ValueError("Username cannot be empty.")
    if len(cleaned) > settings.MAX_USERNAME_LENGTH:
        raise ValueError(f"Username cannot exceed {settings.MAX_USERNAME_LENGTH} characters.")
    for char in cleaned:
        if not char.isprintable():
            raise ValueError(f"Username contains invalid character: {char!r}")
    return cleaned


def compare_form(text: str) -> str:
    """Convert text to a form suitable for comparison.

    Used so search and duplicate checks ignore capitals (Denzel and denzel match)
    and both ways of writing é match. Only used for comparing, never saved.

    Args:
        text (str): The text to be compared.

    Returns:
        str: The text in a case-insensitive form for comparison.
    """
    # Split letters into base + accent (NFD) before and after casefold,
    # because casefold alone doesn't merge the two ways of writing é.
    split = unicodedata.normalize("NFD", text)
    return unicodedata.normalize("NFD", split.casefold())


def find_entry(entries: list[Entry], website: str, username: str) -> Entry | None:
    """Find an entry in the list that matches the given website and username.

    Capitals are ignored. The website and username should already be cleaned
    with clean_website and clean_username.

    Args:
        entries (list[Entry]): The list of entries to search through.
        website (str): The website to match.
        username (str): The username to match.

    Returns:
        Entry | None: The matching entry, or None if no match is found.
    """
    for entry in entries:
        if (compare_form(entry["website"]) == compare_form(website)
                and compare_form(entry["username"]) == compare_form(username)):
            return entry
    return None


def search(entries: list[Entry], query: str) -> list[Entry]:
    """Search for entries that match the given query in either the website or username.

    The match is exact and ignores capitals: "NETFLIX" finds "netflix", "net" finds nothing.
    The query is only trimmed, not cleaned, because it could be a website or a username.

    Args:
        entries (list[Entry]): The list of entries to search through.
        query (str): The query to match against.

    Returns:
        list[Entry]: A list of entries that match the query, sorted by website and username.
    """
    cleaned = compare_form(query.strip())
    if not cleaned:
        return []
    matches: list[Entry] = []
    for entry in entries:
        if (cleaned == compare_form(entry["website"])
                or cleaned == compare_form(entry["username"])):
            matches.append(entry)
    return sorted(
        matches,
        key=lambda item: (compare_form(item["website"]), compare_form(item["username"])),
    )


def load_entries(path: Path) -> list[Entry]:
    """Read entries.json and check that it has the right shape.

    Any problem fails the whole load, so a damaged file is never
    half-loaded and then saved back with entries missing.

    Args:
        path (Path): The entries file, normally settings.ENTRIES_FILE.

    Returns:
        list[Entry]: Every saved entry, in the order they are in the file.

    Raises:
        StorageError: If the file is missing or can't be read, isn't valid JSON,
        isn't a list, has an entry without exactly website, username and password,
        has a value that isn't text, or has two entries with the same website
        and username.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise StorageError(f"Cannot read the entries file {path}.") from error

    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise StorageError(f"Entries file {path} is not valid JSON.") from error

    if not isinstance(data, list):
        raise StorageError("The entries file must hold a list.")

    seen: set[tuple[str, str]] = set()
    for number, item in enumerate(data, start=1):
        if not isinstance(item, dict) or set(item) != ENTRY_FIELDS:
            raise StorageError(f"Entry {number} must have exactly website, username and password.")
        if not all(isinstance(value, str) for value in item.values()):
            raise StorageError(f"Entry {number} has a value that isn't text.")

        identity = (compare_form(item["website"]), compare_form(item["username"]))
        if identity in seen:
            raise StorageError(f"Entry {number} has the same website and username as another.")
        seen.add(identity)

    entries: list[Entry] = data
    return entries


def save_entries(path: Path, entries: list[Entry]) -> None:
    """Save every entry to entries.json, safely.

    Uses save_file_safely, so a power cut never leaves the file half-written.

    Args:
        path (Path): The entries file, normally settings.ENTRIES_FILE.
        entries (list[Entry]): Every entry to save, replacing what was there.

    Raises:
        OSError: Passed on from save_file_safely if the folder is missing
        or the disk is full.
    """
    save_file_safely(path, json.dumps(entries, indent=2) + "\n")


def append_deleted(path: Path, entry: Entry, laptop: str, reason: str) -> None:
    """Add one record to the deleted-entries file.

    Appends one JSON line and never rewrites the file, because on the Pi
    the file is append-only. The password stays locked.

    Args:
        path (Path): The deleted-entries file, normally settings.DELETED_ENTRIES_FILE.
        entry (Entry): The entry being deleted or overwritten.
        laptop (str): Which laptop was connected.
        reason (str): "deleted" or "overwritten".

    Raises:
        ValueError: If the reason isn't in DELETE_REASONS.
        OSError: If the file can't be written.
    """
    if reason not in DELETE_REASONS:
        raise ValueError(f"Invalid delete reason: {reason!r}.")
    deleted_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = {**entry, "laptop": laptop, "deleted_at": deleted_at, "reason": reason}
    append_line(path, json.dumps(record))


def move_to_deleted(
    entries: list[Entry],
    deleted_path: Path,
    entry: Entry,
    laptop: str,
    reason: str,
) -> None:
    """Record an entry in the deleted-entries file, then remove it from the list.

    The deleted file is written first, so a power cut can't lose the entry.
    This only changes the list in memory: the caller still has to save it.

    Args:
        entries (list[Entry]): The entries list, changed in place.
        deleted_path (Path): The deleted-entries file.
        entry (Entry): The entry to move, which must be in entries.
        laptop (str): Which laptop was connected.
        reason (str): "deleted" or "overwritten".

    Raises:
        ValueError: If the reason isn't in DELETE_REASONS. The list is left unchanged.
        OSError: If the deleted file can't be written. The list is left unchanged.
    """
    append_deleted(deleted_path, entry, laptop, reason)
    entries.remove(entry)


def add_entry(entries_path: Path, deleted_path: Path, laptop: str, new_entry: Entry) -> None:
    """Save a new entry, overwriting any entry with the same website and username.

    Capitals are ignored when matching. An overwritten entry goes to the
    deleted-entries file first, so it can be restored. The app asks the
    y/n overwrite question before calling this.

    Args:
        entries_path (Path): The entries file, normally settings.ENTRIES_FILE.
        deleted_path (Path): The deleted-entries file, normally settings.DELETED_ENTRIES_FILE.
        laptop (str): Which laptop was connected.
        new_entry (Entry): The entry to save, already cleaned, with its password locked.

    Raises:
        StorageError: If entries.json is missing or damaged.
        OSError: If a file can't be written.
    """
    entries = load_entries(entries_path)
    existing = find_entry(entries, new_entry["website"], new_entry["username"])
    if existing is not None:
        move_to_deleted(entries, deleted_path, existing, laptop, "overwritten")
    entries.append(new_entry)
    save_entries(entries_path, entries)


def delete_entry(
    entries_path: Path,
    deleted_path: Path,
    laptop: str,
    website: str,
    username: str,
) -> None:
    """Delete an entry from the entries file and move it to the deleted-entries file.

    Capitals are ignored. The deleted file is written first.

    Args:
        entries_path (Path): The entries file, normally settings.ENTRIES_FILE.
        deleted_path (Path): The deleted-entries file, normally settings.DELETED_ENTRIES_FILE.
        laptop (str): Which laptop was connected.
        website (str): The website of the entry to delete.
        username (str): The username of the entry to delete.

    Raises:
        ValueError: If no entry matches the website and username. Nothing is changed.
        StorageError: If entries.json is missing or damaged.
        OSError: If a file can't be written.
    """
    entries = load_entries(entries_path)
    entry = find_entry(entries, website, username)
    if entry is None:
        raise ValueError("Entry not found.")
    move_to_deleted(entries, deleted_path, entry, laptop, "deleted")
    save_entries(entries_path, entries)


def edit_entry(
    entries_path: Path,
    deleted_path: Path,
    laptop: str,
    original: Entry,
    new_entry: Entry,
) -> bool:
    """Save changes to one entry, returning whether anything was saved.

    An entry never clashes with itself, so a capitals-only change is fine.
    A clash with a different entry sends that entry to the deleted-entries
    file first. The old version of the edited entry is not kept.

    Args:
        entries_path (Path): The entries file, normally settings.ENTRIES_FILE.
        deleted_path (Path): The deleted-entries file, normally settings.DELETED_ENTRIES_FILE.
        laptop (str): Which laptop was connected.
        original (Entry): The entry as it was when picked from the search results.
        new_entry (Entry): The entry after editing, already cleaned, with its password locked.

    Returns:
        bool: True if the changes were saved, False if nothing changed.

    Raises:
        ValueError: If the original entry isn't found. Nothing is changed.
        StorageError: If entries.json is missing or damaged.
        OSError: If a file can't be written.
    """
    entries = load_entries(entries_path)
    current = find_entry(entries, original["website"], original["username"])
    if current is None:
        raise ValueError("Entry not found.")
    if new_entry == current:
        return False

    clash = find_entry(entries, new_entry["website"], new_entry["username"])
    if clash is not None and clash is not current:
        move_to_deleted(entries, deleted_path, clash, laptop, "overwritten")

    current["website"] = new_entry["website"]
    current["username"] = new_entry["username"]
    current["password"] = new_entry["password"]
    save_entries(entries_path, entries)
    return True

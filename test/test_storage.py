"""Tests for the pivault storage functions."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from pivault import settings
from pivault.vault.storage import (
    Entry,
    StorageError,
    add_entry,
    append_deleted,
    clean_username,
    clean_website,
    compare_form,
    delete_entry,
    edit_entry,
    find_entry,
    load_entries,
    move_to_deleted,
    save_entries,
    search,
)


# clean_website

def test_clean_website() -> None:
    """Test that clean_website trims spaces and lowercases."""
    assert clean_website("  Netflix ") == "netflix"
    assert clean_website("  google ") == "google"
    assert clean_website("  Example ") == "example"


def test_clean_website_valid() -> None:
    """Test that clean_website keeps - and _."""
    assert clean_website("  valid-website ") == "valid-website"
    assert clean_website("  valid_website ") == "valid_website"


def test_clean_website_digits() -> None:
    """Test that clean_website allows digits."""
    assert clean_website("7eleven") == "7eleven"


def test_clean_website_tab_at_ends() -> None:
    """Test that clean_website trims tabs and newlines at the ends, not just spaces."""
    assert clean_website("\tnetflix\n") == "netflix"


def test_clean_website_max_length() -> None:
    """Test that a website of exactly MAX_WEBSITE_LENGTH characters is allowed."""
    website = "a" * settings.MAX_WEBSITE_LENGTH
    assert clean_website(website) == website


def test_clean_website_one_too_long() -> None:
    """Test that a website one character over MAX_WEBSITE_LENGTH raises ValueError."""
    with pytest.raises(ValueError):
        clean_website("a" * (settings.MAX_WEBSITE_LENGTH + 1))


def test_clean_website_far_too_long() -> None:
    """Test that a website far over MAX_WEBSITE_LENGTH raises ValueError."""
    with pytest.raises(ValueError):
        clean_website("a" * 100)


def test_clean_website_length_after_trim() -> None:
    """Test that spaces at the ends don't count toward the length limit."""
    website = "a" * settings.MAX_WEBSITE_LENGTH
    assert clean_website("  " + website + "  ") == website


def test_clean_website_blank() -> None:
    """Test that an empty or only-spaces website raises ValueError."""
    with pytest.raises(ValueError):
        clean_website("  ")
    with pytest.raises(ValueError):
        clean_website("")


def test_clean_website_invalid() -> None:
    """Test that @, dots and spaces inside a website raise ValueError."""
    with pytest.raises(ValueError):
        clean_website("invalid@website")
    with pytest.raises(ValueError):
        clean_website("invalid.website")
    with pytest.raises(ValueError):
        clean_website("invalid website")


def test_clean_website_other_symbols() -> None:
    """Test that commas, slashes and emoji raise ValueError."""
    with pytest.raises(ValueError):
        clean_website("a,b")
    with pytest.raises(ValueError):
        clean_website("a/b")
    with pytest.raises(ValueError):
        clean_website("netflix😀")


def test_clean_website_accents() -> None:
    """Test that accented and foreign letters raise ValueError."""
    with pytest.raises(ValueError):
        clean_website("café")
    with pytest.raises(ValueError):
        clean_website("Straße")


def test_clean_website_error_names_char() -> None:
    """Test that the error message shows the bad character in quotes."""
    with pytest.raises(ValueError, match="' '"):
        clean_website("invalid website")


# clean_username

def test_clean_username_valid() -> None:
    """Test that clean_username trims spaces and keeps everything else."""
    assert clean_username("  valid-username ") == "valid-username"
    assert clean_username("dzl445 ") == "dzl445"
    assert clean_username("  valid.username ") == "valid.username"


def test_clean_username_keeps_capitals() -> None:
    """Test that clean_username does not lowercase."""
    assert clean_username("CH@@#ssee00") == "CH@@#ssee00"


def test_clean_username_middle_space() -> None:
    """Test that a space inside a username is kept."""
    assert clean_username("  bob smith ") == "bob smith"


def test_clean_username_email() -> None:
    """Test that a normal email address is allowed."""
    assert clean_username("denzel.example@university.edu") == "denzel.example@university.edu"


def test_clean_username_emoji() -> None:
    """Test that emoji count as printable and are allowed."""
    assert clean_username("denzel😀") == "denzel😀"


def test_clean_username_one_char() -> None:
    """Test that a one-character username is allowed (no minimum beyond not empty)."""
    assert clean_username("d") == "d"


def test_clean_username_max_length() -> None:
    """Test that a username of exactly MAX_USERNAME_LENGTH characters is allowed."""
    username = "i" * settings.MAX_USERNAME_LENGTH
    assert clean_username(username) == username


def test_clean_username_one_too_long() -> None:
    """Test that a username one character over MAX_USERNAME_LENGTH raises ValueError."""
    with pytest.raises(ValueError):
        clean_username("i" * (settings.MAX_USERNAME_LENGTH + 1))


def test_clean_username_length_after_nfc() -> None:
    """Test that the length is measured after NFC, so a 2-piece é counts as 1."""
    two_piece_e = "e\u0301"
    username = two_piece_e * settings.MAX_USERNAME_LENGTH
    assert len(username) == settings.MAX_USERNAME_LENGTH * 2
    assert len(clean_username(username)) == settings.MAX_USERNAME_LENGTH


def test_clean_username_blank() -> None:
    """Test that an empty or only-spaces username raises ValueError."""
    with pytest.raises(ValueError):
        clean_username("  ")
    with pytest.raises(ValueError):
        clean_username("")


def test_clean_username_accented_letter_same() -> None:
    """Test that both ways of writing é give the same username."""
    one_char = "caf\u00e9"
    two_chars = "cafe\u0301"
    assert clean_username(one_char) == clean_username(two_chars)


def test_clean_username_control_chars() -> None:
    """Test that tabs, newlines and terminal escape codes raise ValueError."""
    with pytest.raises(ValueError):
        clean_username("Denzel\tx")
    with pytest.raises(ValueError):
        clean_username("a\nb")
    with pytest.raises(ValueError):
        clean_username("a\rb")
    with pytest.raises(ValueError):
        clean_username("\x1b[31mred")
    with pytest.raises(ValueError):
        clean_username("a\x00b")


def test_clean_username_invisible_chars() -> None:
    """Test that invisible characters from copy-paste raise ValueError."""
    with pytest.raises(ValueError):
        clean_username("den\u200bzel")
    with pytest.raises(ValueError):
        clean_username("bob\xa0smith")
    with pytest.raises(ValueError):
        clean_username("\ufeffdenzel")


def test_clean_username_error_names_char() -> None:
    """Test that the error message spells out an invisible character."""
    with pytest.raises(ValueError, match=r"\\t"):
        clean_username("Denzel\tx")


# compare_form

def test_compare_form_ignores_capitals() -> None:
    """Test that the same name in different capitals compares equal."""
    assert compare_form("Denzel") == compare_form("denzel")
    assert compare_form("NETFLIX") == compare_form("netflix")


def test_compare_form_german_ss() -> None:
    """Test that casefold matches ß with SS, which lower() would not."""
    assert compare_form("Straße") == compare_form("STRASSE")


def test_compare_form_accented_letter_same() -> None:
    """Test that both ways of writing é compare equal, even with different capitals."""
    assert compare_form("caf\u00e9") == compare_form("cafe\u0301")
    assert compare_form("CAF\u00c9") == compare_form("cafe\u0301")


def test_compare_form_different_names() -> None:
    """Test that different names stay different."""
    assert compare_form("denzel") != compare_form("denzel2")


def test_compare_form_keeps_original() -> None:
    """Test that compare_form returns a new string and leaves the original alone."""
    name = "Denzel"
    compare_form(name)
    assert name == "Denzel"


def test_compare_form_with_cleaned_username() -> None:
    """Test that a username is stored as typed but compared ignoring capitals."""
    stored = clean_username("CH@@#ssee00")
    assert stored == "CH@@#ssee00"
    assert compare_form(stored) == "ch@@#ssee00"


# Sample entries for find_entry and search, deliberately not in website order.

def sample_entries() -> list[Entry]:
    """Return a fresh list of sample entries for each test."""
    return [
        {"website": "spotify", "username": "denzel", "password": "token1"},
        {"website": "netflix", "username": "jeffa", "password": "token2"},
        {"website": "amazon", "username": "Denzel", "password": "token3"},
        {"website": "netflix", "username": "Denzel", "password": "token4"},
        {"website": "caf\u00e9", "username": "bob", "password": "token5"},
    ]


# find_entry

def test_return_entry_valid() -> None:
    """Test that find_entry returns the correct entry when given valid parameters."""

    result = find_entry(sample_entries(), "SPOTIFY", "denzel")
    assert result == sample_entries()[0]


def test_find_entry_not_first() -> None:
    """Test that the loop keeps going past entries that don't match."""
    result = find_entry(sample_entries(), "netflix", "denzel")
    assert result is not None
    assert result["password"] == "token4"


def test_find_entry_needs_both() -> None:
    """Test that the right website with the wrong username finds nothing."""
    assert find_entry(sample_entries(), "netflix", "bob") is None


def test_find_entry_empty_list() -> None:
    """Test that an empty vault finds nothing."""
    assert find_entry([], "netflix", "Denzel") is None


def test_find_entry_accented() -> None:
    """Test that a two-piece é finds a saved one-piece é."""
    result = find_entry(sample_entries(), "cafe\u0301", "BOB")
    assert result is not None
    assert result["password"] == "token5"


# search

def passwords(results: list[Entry]) -> list[str]:
    """Return just the password tokens, to check which entries came back and in what order."""
    return [entry["password"] for entry in results]


def test_search_username_sorted() -> None:
    """Test that a username is found on every site, sorted by website."""
    assert passwords(search(sample_entries(), "denzel")) == ["token3", "token4", "token1"]


def test_search_website_capitals_and_spaces() -> None:
    """Test that capitals and spaces around the query are ignored."""
    assert passwords(search(sample_entries(), "  NETFLIX ")) == ["token4", "token2"]


def test_search_exact_only() -> None:
    """Test that part of a name finds nothing."""
    assert not search(sample_entries(), "net")


def test_search_blank_query() -> None:
    """Test that an empty or only-spaces query finds nothing."""
    assert not search(sample_entries(), "")
    assert not search(sample_entries(), "   ")


def test_search_both_fields_once() -> None:
    """Test that an entry matching on website and username appears only once."""
    entries: list[Entry] = [{"website": "denzel", "username": "denzel", "password": "x"}]
    assert len(search(entries, "denzel")) == 1


# load_entries

def write_entries_file(folder: Path, text: str) -> Path:
    """Write text to entries.json in a test folder and return its path."""
    path = folder / "entries.json"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_entries_good_file(tmp_path: Path) -> None:
    """Test that a good file loads every entry, in file order."""
    text = """[
      {"website": "netflix", "username": "Denzel", "password": "token1"},
      {"website": "amazon", "username": "jeffa", "password": "token2"}
    ]"""
    assert load_entries(write_entries_file(tmp_path, text)) == [
        {"website": "netflix", "username": "Denzel", "password": "token1"},
        {"website": "amazon", "username": "jeffa", "password": "token2"},
    ]


def test_load_entries_missing_file(tmp_path: Path) -> None:
    """Test that a missing file raises StorageError instead of giving an empty vault."""
    with pytest.raises(StorageError):
        load_entries(tmp_path / "entries.json")


def test_load_entries_not_json(tmp_path: Path) -> None:
    """Test that a file that isn't JSON raises StorageError and is left untouched."""
    path = write_entries_file(tmp_path, "not json")
    with pytest.raises(StorageError):
        load_entries(path)
    assert path.read_text(encoding="utf-8") == "not json"


def test_load_entries_missing_key(tmp_path: Path) -> None:
    """Test that an entry with no password raises StorageError naming the entry."""
    text = '[{"website": "a", "username": "b", "password": "c"}, {"website": "d", "username": "e"}]'
    with pytest.raises(StorageError, match="Entry 2"):
        load_entries(write_entries_file(tmp_path, text))


def test_load_entries_duplicate(tmp_path: Path) -> None:
    """Test that two entries differing only by capitals raise StorageError."""
    text = """[
      {"website": "netflix", "username": "Denzel", "password": "x"},
      {"website": "Netflix", "username": "denzel", "password": "y"}
    ]"""
    with pytest.raises(StorageError):
        load_entries(write_entries_file(tmp_path, text))


# save_entries

def two_entries() -> list[Entry]:
    """Return a fresh list of two sample entries."""
    return [
        {"website": "netflix", "username": "Denzel", "password": "token1"},
        {"website": "amazon", "username": "jeffa", "password": "token2"},
    ]


def test_save_entries_round_trip(tmp_path: Path) -> None:
    """Test that saving then loading gives back the same list, in the same order."""
    path = tmp_path / "entries.json"
    save_entries(path, two_entries())
    assert load_entries(path) == two_entries()


def test_save_entries_empty_vault(tmp_path: Path) -> None:
    """Test that an empty list saves and loads back as an empty vault."""
    path = tmp_path / "entries.json"
    save_entries(path, [])
    assert not load_entries(path)


def test_save_entries_overwrite(tmp_path: Path) -> None:
    """Test that saving a shorter list replaces what was there."""
    path = tmp_path / "entries.json"
    save_entries(path, two_entries())
    save_entries(path, two_entries()[:1])
    assert load_entries(path) == two_entries()[:1]


def test_save_entries_readable(tmp_path: Path) -> None:
    """Test that the file is indented and ends with a newline."""
    path = tmp_path / "entries.json"
    save_entries(path, two_entries())
    text = path.read_text(encoding="utf-8")
    assert text.startswith("[\n  {")
    assert text.endswith("\n")


def test_save_entries_owner_only(tmp_path: Path) -> None:
    """Test that the entries file is owner-only, because it goes through save_file_safely."""
    path = tmp_path / "entries.json"
    save_entries(path, two_entries())
    assert path.stat().st_mode & 0o777 == 0o600


# append_deleted

def read_deleted(path: Path) -> list[dict[str, str]]:
    """Read every record in a deleted-entries file, one JSON object per line."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def test_append_deleted_one_line(tmp_path: Path) -> None:
    """Test that one call writes one line holding the entry plus three new keys."""
    path = tmp_path / "deleted.jsonl"
    append_deleted(path, two_entries()[0], "macbook", "deleted")
    records = read_deleted(path)
    assert len(records) == 1
    assert set(records[0]) == {
        "website", "username", "password", "laptop", "deleted_at", "reason"
    }


def test_append_deleted_two_lines(tmp_path: Path) -> None:
    """Test that a second call adds a line and leaves the first unchanged."""
    path = tmp_path / "deleted.jsonl"
    append_deleted(path, two_entries()[0], "macbook", "deleted")
    first_line = path.read_text(encoding="utf-8")
    append_deleted(path, two_entries()[1], "macbook", "overwritten")
    text = path.read_text(encoding="utf-8")
    assert text.startswith(first_line)
    assert len(text.splitlines()) == 2


def test_append_deleted_record_values(tmp_path: Path) -> None:
    """Test that the record keeps the locked password and the laptop and reason given."""
    path = tmp_path / "deleted.jsonl"
    append_deleted(path, two_entries()[0], "macbook", "overwritten")
    record = read_deleted(path)[0]
    assert record["password"] == "token1"
    assert record["laptop"] == "macbook"
    assert record["reason"] == "overwritten"


def test_append_deleted_time_is_utc(tmp_path: Path) -> None:
    """Test that deleted_at is an ISO 8601 time in UTC."""
    path = tmp_path / "deleted.jsonl"
    append_deleted(path, two_entries()[0], "macbook", "deleted")
    deleted_at = datetime.fromisoformat(read_deleted(path)[0]["deleted_at"])
    assert deleted_at.utcoffset() == timedelta(0)


def test_append_deleted_bad_reason(tmp_path: Path) -> None:
    """Test that a bad reason raises before anything is written."""
    path = tmp_path / "deleted.jsonl"
    entry = two_entries()[0]
    with pytest.raises(ValueError):
        append_deleted(path, entry, "macbook", "overwriten")
    assert not path.exists()
    assert entry == two_entries()[0]


# move_to_deleted

def test_move_to_deleted_removes_entry(tmp_path: Path) -> None:
    """Test that the entry is taken out of the list."""
    entries = two_entries()
    move_to_deleted(entries, tmp_path / "deleted.jsonl", entries[0], "macbook", "deleted")
    assert entries == two_entries()[1:]


def test_move_to_deleted_records_entry(tmp_path: Path) -> None:
    """Test that the entry is written to the deleted file with the reason given."""
    path = tmp_path / "deleted.jsonl"
    entries = two_entries()
    move_to_deleted(entries, path, entries[0], "macbook", "overwritten")
    record = read_deleted(path)[0]
    assert record["website"] == "netflix"
    assert record["reason"] == "overwritten"


def test_move_to_deleted_changes_list_in_place(tmp_path: Path) -> None:
    """Test that the caller's own list is changed, not replaced with a new one."""
    entries = two_entries()
    same_list = entries
    move_to_deleted(entries, tmp_path / "deleted.jsonl", entries[1], "macbook", "deleted")
    assert same_list is entries
    assert len(same_list) == 1


def test_move_to_deleted_does_not_save(tmp_path: Path) -> None:
    """Test that only the deleted file is written; the caller still has to save."""
    move_to_deleted(two_entries(), tmp_path / "deleted.jsonl", two_entries()[0], "mac", "deleted")
    assert list(tmp_path.iterdir()) == [tmp_path / "deleted.jsonl"]


def test_move_to_deleted_bad_reason(tmp_path: Path) -> None:
    """Test that a bad reason leaves the list unchanged, because the deleted file comes first."""
    entries = two_entries()
    with pytest.raises(ValueError):
        move_to_deleted(entries, tmp_path / "deleted.jsonl", entries[0], "macbook", "oops")
    assert entries == two_entries()


# add_entry, delete_entry and edit_entry

def make_vault(folder: Path, entries: list[Entry]) -> tuple[Path, Path]:
    """Save entries to a test vault and return the entries and deleted-entries paths."""
    entries_path = folder / "entries.json"
    save_entries(entries_path, entries)
    return entries_path, folder / "deleted.jsonl"


NEW_ENTRY: Entry = {"website": "spotify", "username": "bob", "password": "token3"}


# add_entry

def test_add_entry_empty_vault(tmp_path: Path) -> None:
    """Test that adding to an empty vault saves just that entry and deletes nothing."""
    entries_path, deleted_path = make_vault(tmp_path, [])
    add_entry(entries_path, deleted_path, "macbook", dict(NEW_ENTRY))
    assert load_entries(entries_path) == [NEW_ENTRY]
    assert not deleted_path.exists()


def test_add_entry_second_entry(tmp_path: Path) -> None:
    """Test that a new entry is added after the ones already saved."""
    entries_path, deleted_path = make_vault(tmp_path, two_entries())
    add_entry(entries_path, deleted_path, "macbook", dict(NEW_ENTRY))
    assert load_entries(entries_path) == two_entries() + [NEW_ENTRY]


def test_add_entry_overwrite(tmp_path: Path) -> None:
    """Test that adding an existing entry replaces it and keeps the old one in the deleted file."""
    entries_path, deleted_path = make_vault(tmp_path, two_entries())
    new: Entry = {"website": "netflix", "username": "Denzel", "password": "newtoken"}
    add_entry(entries_path, deleted_path, "macbook", new)
    assert load_entries(entries_path) == [two_entries()[1], new]
    record = read_deleted(deleted_path)[0]
    assert record["password"] == "token1"
    assert record["reason"] == "overwritten"


def test_add_entry_overwrite_ignores_capitals(tmp_path: Path) -> None:
    """Test that a duplicate differing only by capitals still overwrites, with the new capitals."""
    entries_path, deleted_path = make_vault(tmp_path, two_entries())
    new: Entry = {"website": "netflix", "username": "denzel", "password": "newtoken"}
    add_entry(entries_path, deleted_path, "macbook", new)
    entries = load_entries(entries_path)
    assert len(entries) == 2
    assert new in entries
    assert len(read_deleted(deleted_path)) == 1


def test_add_entry_missing_file(tmp_path: Path) -> None:
    """Test that a missing entries.json raises StorageError and writes nothing."""
    deleted_path = tmp_path / "deleted.jsonl"
    with pytest.raises(StorageError):
        add_entry(tmp_path / "entries.json", deleted_path, "macbook", dict(NEW_ENTRY))
    assert not list(tmp_path.iterdir())


# delete_entry

def test_delete_entry_removes_it(tmp_path: Path) -> None:
    """Test that the entry is gone and the other one is untouched."""
    entries_path, deleted_path = make_vault(tmp_path, two_entries())
    delete_entry(entries_path, deleted_path, "macbook", "netflix", "Denzel")
    assert load_entries(entries_path) == two_entries()[1:]


def test_delete_entry_records_it(tmp_path: Path) -> None:
    """Test that the deleted entry is in the deleted file with reason deleted."""
    entries_path, deleted_path = make_vault(tmp_path, two_entries())
    delete_entry(entries_path, deleted_path, "macbook", "netflix", "Denzel")
    record = read_deleted(deleted_path)[0]
    assert record["password"] == "token1"
    assert record["reason"] == "deleted"


def test_delete_entry_ignores_capitals(tmp_path: Path) -> None:
    """Test that capitals in the website and username don't matter."""
    entries_path, deleted_path = make_vault(tmp_path, two_entries())
    delete_entry(entries_path, deleted_path, "macbook", "NETFLIX", "DENZEL")
    assert load_entries(entries_path) == two_entries()[1:]


def test_delete_entry_not_found(tmp_path: Path) -> None:
    """Test that a missing entry raises ValueError and changes neither file."""
    entries_path, deleted_path = make_vault(tmp_path, two_entries())
    before = entries_path.read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        delete_entry(entries_path, deleted_path, "macbook", "google", "bob")
    assert entries_path.read_text(encoding="utf-8") == before
    assert not deleted_path.exists()


def test_delete_entry_last_one(tmp_path: Path) -> None:
    """Test that deleting the only entry leaves an empty vault."""
    entries_path, deleted_path = make_vault(tmp_path, two_entries()[:1])
    delete_entry(entries_path, deleted_path, "macbook", "netflix", "Denzel")
    assert not load_entries(entries_path)


# edit_entry

def test_edit_entry_password(tmp_path: Path) -> None:
    """Test that changing the password saves it and sends nothing to the deleted file."""
    entries_path, deleted_path = make_vault(tmp_path, two_entries())
    original = two_entries()[0]
    new: Entry = {**original, "password": "new"}
    assert edit_entry(entries_path, deleted_path, "macbook", original, new)
    assert load_entries(entries_path)[0]["password"] == "new"
    assert not deleted_path.exists()


def test_edit_entry_capitals_only(tmp_path: Path) -> None:
    """Test that changing only capitals is saved and doesn't count as a clash with itself."""
    entries_path, deleted_path = make_vault(tmp_path, two_entries())
    original = two_entries()[0]
    new: Entry = {**original, "username": "denzel"}
    assert edit_entry(entries_path, deleted_path, "macbook", original, new)
    entries = load_entries(entries_path)
    assert entries[0]["username"] == "denzel"
    assert len(entries) == 2
    assert not deleted_path.exists()


def test_edit_entry_clash(tmp_path: Path) -> None:
    """Test that renaming onto another entry overwrites it and keeps it in the deleted file."""
    entries_path, deleted_path = make_vault(tmp_path, two_entries())
    original = two_entries()[0]
    new: Entry = {"website": "amazon", "username": "jeffa", "password": "token1"}
    assert edit_entry(entries_path, deleted_path, "macbook", original, new)
    assert load_entries(entries_path) == [new]
    record = read_deleted(deleted_path)[0]
    assert record["password"] == "token2"
    assert record["reason"] == "overwritten"


def test_edit_entry_no_change(tmp_path: Path) -> None:
    """Test that no change returns False and leaves the file exactly as it was."""
    entries_path, deleted_path = make_vault(tmp_path, two_entries())
    before = entries_path.read_text(encoding="utf-8")
    original = two_entries()[0]
    assert not edit_entry(entries_path, deleted_path, "macbook", original, dict(original))
    assert entries_path.read_text(encoding="utf-8") == before


def test_edit_entry_missing_original(tmp_path: Path) -> None:
    """Test that an original that isn't saved raises ValueError and changes nothing."""
    entries_path, deleted_path = make_vault(tmp_path, two_entries())
    before = entries_path.read_text(encoding="utf-8")
    missing: Entry = {"website": "google", "username": "bob", "password": "x"}
    with pytest.raises(ValueError):
        edit_entry(entries_path, deleted_path, "macbook", missing, dict(NEW_ENTRY))
    assert entries_path.read_text(encoding="utf-8") == before
    assert not deleted_path.exists()

"""Tests for the pivault storage functions."""

from pathlib import Path

import pytest

from pivault import settings
from pivault.vault.storage import (
    Entry,
    StorageError,
    clean_username,
    clean_website,
    compare_form,
    find_entry,
    load_entries,
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

"""Tests for the pivault storage functions."""

import pytest

from pivault import settings
from pivault.vault.storage import clean_username, clean_website, compare_form


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

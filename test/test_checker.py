"""Tests for password_checker: each rule alone, every rule at once, and the length limits."""
from pivault.checker import password_checker

def test_all_valid():
    """ test valid password"""
    assert password_checker("Lol6769$$$") == []  # pylint: disable=use-implicit-booleaness-not-comparison

def test_all_not_valid_too_short():
    """test for everything being invalid, using min length (excludes max length)"""
    assert password_checker("") == [
        "Too short: you have 0 characters, you need at least 10.",
        "Not enough special characters: you have 0, you need at least 2.",
        "Password needs at least one uppercase letter.",
        "Password needs at least one lowercase letter.",
        "Password needs at least one digit.",
    ]

def test_all_not_valid_too_long():
    """test for everything being invalid, using max length (excludes min length)"""
    assert password_checker(" " * 65) == [
        "Too long: you have 65 characters, the max is 64.",
        "Not enough special characters: you have 0, you need at least 2.",
        "Password needs at least one uppercase letter.",
        "Password needs at least one lowercase letter.",
        "Password needs at least one digit.",
    ]

def test_max_length():
    """test max length rule"""
    assert password_checker("Lol6769$$$" + "a" * 55) == [
        "Too long: you have 65 characters, the max is 64.",
    ]

def test_exactly_max_length_is_valid():
    """test a password of exactly 64 characters is allowed"""
    assert password_checker("Lol6769$$$" + "a" * 54) == []  # pylint: disable=use-implicit-booleaness-not-comparison

def test_min_length():
    """test min length rule"""
    assert password_checker("Lol67$$") == [
        "Too short: you have 7 characters, you need at least 10.",
    ]

def test_special_chars():
    """test special characters rule"""
    assert password_checker("Lol6769$abc") == [
        "Not enough special characters: you have 1, you need at least 2.",
    ]

def test_uppercase():
    """test uppercase rule"""
    assert password_checker("lol6769$$$") == [
        "Password needs at least one uppercase letter.",
    ]

def test_lowercase():
    """test lowercase rule"""
    assert password_checker("LOL6769$$$") == [
        "Password needs at least one lowercase letter.",
    ]

def test_digit():
    """test digit rule"""
    assert password_checker("Lolabcd$$$") == [
        "Password needs at least one digit.",
    ]

def test_spaces_count_toward_length():
    """test spaces are allowed and count toward length"""
    assert password_checker("Lol67$$   ") == []  # pylint: disable=use-implicit-booleaness-not-comparison

def test_spaces_are_not_special_characters():
    """test spaces do not count as special characters"""
    assert password_checker("Lol6769$  ") == [
        "Not enough special characters: you have 1, you need at least 2.",
    ]

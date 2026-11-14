"""Storage functions for the pivault application: entries and deleted entries."""

import unicodedata

from pivault import settings


class StorageError(Exception):
    """Raised when the entries file is missing or damaged."""


def clean_website(website: str) -> str:
    """Clean and check a website name before it is saved or searched.

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
    """Clean and check a username before it is saved or searched.

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

    Used so search and duplicate checks ignore capitals (Denzel and denzel match).

    Args:
        text (str): The text to be compared.

    Returns:
        str: The text in a case-insensitive form for comparison.
    """
    return text.casefold()

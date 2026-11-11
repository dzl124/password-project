"""Password rule checks and the error messages shown when a rule fails."""

import string

SPECIAL_CHARS = frozenset(string.punctuation)
MIN_LENGTH = 10
MAX_LENGTH = 64
MIN_SPECIAL = 2


def password_checker(pw: str) -> list[str]:
    """Check whether a password meets every requirement.

    Runs every rule (length, special characters, uppercase, lowercase,
    digit) and collects a message for each rule the password breaks.

    Args:
        pw: The password to check.

    Returns:
        A list of error messages, one per broken rule. An empty list
        means the password is valid.
    """

    errors: list[str] = []
    length = len(pw)
    special_count = sum(1 for c in pw if c in SPECIAL_CHARS)

    if length < MIN_LENGTH:
        errors.append(f"Too short: you have {length} characters, "
                      f"you need at least {MIN_LENGTH}.")
    elif length > MAX_LENGTH:
        errors.append(f"Too long: you have {length} characters, "
                      f"the max is {MAX_LENGTH}.")
    if special_count < MIN_SPECIAL:
        errors.append(f"Not enough special characters: you have {special_count}, "
                      f"you need at least {MIN_SPECIAL}.")
    if not any(c.isupper() for c in pw):
        errors.append("Password needs at least one uppercase letter.")
    if not any(c.islower() for c in pw):
        errors.append("Password needs at least one lowercase letter.")
    if not any(c.isdigit() for c in pw):
        errors.append("Password needs at least one digit.")
    return errors

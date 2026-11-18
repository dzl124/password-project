"""Shared prompts for the vault app and the admin commands.

yes/no, website, username, a new password (checked and typed twice), the
master key and a 2FA code. Kept here so the admin commands can reuse them
without depending on the vault app.
"""

from pivault.vault.screen import read_line
from pivault.vault.session import Session
from pivault.vault.storage import clean_username, clean_website

YES_ANSWERS = ("y", "yes")
NO_ANSWERS = ("n", "no")


def _ask(session: Session, prompt: str, hidden: bool, deadline: float) -> str:
    """Ask once with whatever time is left before the screen's deadline.

    Args:
        session (Session): Where keys come from and text goes.
        prompt (str): The text shown before the typing.
        hidden (bool): True to show nothing as keys are typed.
        deadline (float): When the screen runs out, on session.clock.

    Returns:
        str: The line typed.

    Raises:
        ScreenTimeout: If the deadline passes before Enter.
        QuitRequested: If Ctrl+D is pressed.
    """
    seconds_left = max(0.0, deadline - session.clock())
    return read_line(prompt, hidden, seconds_left, session.read_key, session.write, session.clock)


def ask_yes_no(session: Session, question: str, seconds: float) -> bool:
    """Ask a yes/no question until y, yes, n or no is typed.

    Args:
        session (Session): The current session.
        question (str): The question, like "Overwrite it? (y/n) ".
        seconds (float): The time limit for this screen.

    Returns:
        bool: True for yes, False for no.
    """
    deadline = session.clock() + seconds
    while True:
        answer = _ask(session, question, False, deadline).strip().casefold()
        if answer in YES_ANSWERS:
            return True
        if answer in NO_ANSWERS:
            return False
        session.write("Please type y or n.\r\n")


def ask_website(session: Session, seconds: float) -> str:
    """Ask for a website until it passes clean_website.

    Args:
        session (Session): The current session.
        seconds (float): The time limit for this screen.

    Returns:
        str: The cleaned website.
    """
    deadline = session.clock() + seconds
    while True:
        try:
            return clean_website(_ask(session, "Website: ", False, deadline))
        except ValueError as error:
            session.write(f"{error}\r\n")


def ask_username(session: Session, seconds: float) -> str:
    """Ask for a username until it passes clean_username.

    Args:
        session (Session): The current session.
        seconds (float): The time limit for this screen.

    Returns:
        str: The cleaned username.
    """
    deadline = session.clock() + seconds
    while True:
        try:
            return clean_username(_ask(session, "Username: ", False, deadline))
        except ValueError as error:
            session.write(f"{error}\r\n")


def ask_new_password(session: Session, seconds: float, min_length: int = 1) -> str:
    """Ask for a new password twice, hidden, until both match and it's long enough.

    Args:
        session (Session): The current session.
        seconds (float): The time limit for this screen.
        min_length (int): The fewest characters allowed. Defaults to 1.

    Returns:
        str: The new password.
    """
    deadline = session.clock() + seconds
    while True:
        password = _ask(session, "New password: ", True, deadline)
        if len(password) < min_length:
            session.write(f"Password must be at least {min_length} characters.\r\n")
            continue
        again = _ask(session, "Type it again: ", True, deadline)
        if password == again:
            return password
        session.write("Passwords didn't match. Try again.\r\n")


def ask_master_key(session: Session, seconds: float) -> str:
    """Ask for the master key once, hidden, until something is typed.

    Whether it is right is checked later by open_lockbox.

    Args:
        session (Session): The current session.
        seconds (float): The time limit for this screen.

    Returns:
        str: The master key as typed.
    """
    deadline = session.clock() + seconds
    while True:
        master_key = _ask(session, "Master key: ", True, deadline)
        if master_key:
            return master_key
        session.write("Master key cannot be empty.\r\n")


def ask_twofa_code(session: Session, seconds: float) -> str:
    """Ask for the 6-digit 2FA code until something is typed.

    The digits are checked later by check_twofa_code.

    Args:
        session (Session): The current session.
        seconds (float): The time limit for this screen.

    Returns:
        str: The code as typed.
    """
    deadline = session.clock() + seconds
    while True:
        code = _ask(session, "2FA code: ", False, deadline)
        if code.strip():
            return code
        session.write("2FA code cannot be empty.\r\n")

"""Shared prompts for the vault app and the admin commands.

yes/no, website, username, a new password (checked and typed twice), the
master key and a 2FA code. Kept here so the admin commands can reuse them
without depending on the vault app.
"""

from collections.abc import Callable

from pivault.vault.screen import read_line
from pivault.vault.session import Session
from pivault.vault.storage import clean_username, clean_website

YES_ANSWERS = ("y", "yes")
NO_ANSWERS = ("n", "no")

# A password check like password_checker: takes the password, returns one message per broken rule.
PasswordCheck = Callable[[str], list[str]]


def ask_line(session: Session, prompt: str, hidden: bool, deadline: float) -> str:
    """Ask once with whatever time is left before the screen's deadline.

    Public so get.py and app.py can read a line against one fixed deadline,
    where invalid input must not reset the time.

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
        answer = ask_line(session, question, False, deadline).strip().casefold()
        if answer in YES_ANSWERS:
            return True
        if answer in NO_ANSWERS:
            return False
        session.write("Please type y or n.\r\n")


def ask_website(session: Session, seconds: float, current: str | None = None) -> str:
    """Ask for a website until it passes clean_website.

    With current (Edit), the prompt shows it in brackets and pressing
    Enter keeps it.

    Args:
        session (Session): The current session.
        seconds (float): The time limit for this screen.
        current (str | None): The saved website to keep on Enter, or None (Add).

    Returns:
        str: The cleaned website, or current if Enter was pressed.
    """
    if current is None:
        prompt = "Website (name only, like netflix): "
    else:
        prompt = f"Website [{current}]: "
    deadline = session.clock() + seconds
    while True:
        typed = ask_line(session, prompt, False, deadline)
        if current is not None and not typed.strip():
            return current
        try:
            return clean_website(typed)
        except ValueError as error:
            session.write(f"{error}\r\n")


def ask_username(session: Session, seconds: float, current: str | None = None) -> str:
    """Ask for a username until it passes clean_username.

    With current (Edit), the prompt shows it in brackets and pressing
    Enter keeps it.

    Args:
        session (Session): The current session.
        seconds (float): The time limit for this screen.
        current (str | None): The saved username to keep on Enter, or None (Add).

    Returns:
        str: The cleaned username, or current if Enter was pressed.
    """
    prompt = "Username: " if current is None else f"Username [{current}]: "
    deadline = session.clock() + seconds
    while True:
        typed = ask_line(session, prompt, False, deadline)
        if current is not None and not typed.strip():
            return current
        try:
            return clean_username(typed)
        except ValueError as error:
            session.write(f"{error}\r\n")


def ask_new_password(
    session: Session,
    seconds: float,
    min_length: int = 1,
    checker: PasswordCheck | None = None,
) -> str:
    """Ask for a new password twice, hidden, until both match and it passes the checks.

    Args:
        session (Session): The current session.
        seconds (float): The time limit for this screen.
        min_length (int): The fewest characters allowed. Defaults to 1.
        checker (PasswordCheck | None): A password check like password_checker.
            Every message it returns is shown and the password asked again.
            None (the master-key prompts) skips it.

    Returns:
        str: The new password.
    """
    deadline = session.clock() + seconds
    while True:
        password = ask_line(session, "New password: ", True, deadline)
        if len(password) < min_length:
            session.write(f"Password must be at least {min_length} characters.\r\n")
            continue
        if checker is not None:
            problems = checker(password)
            if problems:
                for problem in problems:
                    session.write(f"{problem}\r\n")
                continue
        again = ask_line(session, "Type it again: ", True, deadline)
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
        master_key = ask_line(session, "Enter password: ", True, deadline)
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
        code = ask_line(session, "2FA code: ", False, deadline)
        if code.strip():
            return code
        session.write("2FA code cannot be empty.\r\n")

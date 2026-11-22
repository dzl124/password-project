"""Screen helpers for the pivault application: clearing, timed and hidden typing, and quitting."""

import codecs
import os
import select
import sys
import termios
import time
import tty
from collections.abc import Callable, Iterator
from contextlib import contextmanager


# Clears the scrollback, clears the screen, then moves to the top-left corner.
CLEAR_SCREEN = "\033[3J\033[2J\033[H"

# Special keys, as they arrive from the keyboard in raw mode.
CTRL_C = "\x03"
CTRL_D = "\x04"
ESCAPE = "\x1b"
ENTER_KEYS = frozenset({"\r", "\n"})
BACKSPACE_KEYS = frozenset({"\x7f", "\x08"})

# Erases the last character shown: move back, overwrite with a space, move back again.
ERASE_LAST_CHAR = "\b \b"

# Longest line read_line accepts, so a stuck key or a huge paste can't grow forever.
MAX_INPUT_LENGTH = 256

# What the decoder turns junk bytes into. read_line never types it into a line.
REPLACEMENT_CHAR = "\N{REPLACEMENT CHARACTER}"

# A function that waits up to this many seconds for one key, or returns None if none came.
ReadKey = Callable[[float], str | None]

# A function that shows text on the screen.
Write = Callable[[str], None]

# How long to wait for the rest of a key that arrives as several bytes, like é.
REST_OF_KEY_SECONDS = 0.05

# One UTF-8 decoder for the whole session, so a character split across reads
# (é is two bytes) is put back together. Junk bytes become a replacement character.
UTF8_DECODER = codecs.getincrementaldecoder("utf-8")(errors="replace")


class ScreenTimeout(Exception):
    """Raised when a screen's time runs out, which ends the session."""


class QuitRequested(Exception):
    """Raised when Ctrl+D is pressed, which ends the session from any screen."""


def clear_screen(write: Write) -> None:
    """Clear the scrollback and the screen, and move to the top.

    Args:
        write (Write): The function that shows text on the screen.
    """
    write(CLEAR_SCREEN)


def skip_escape_sequence(read_key: ReadKey) -> None:
    """Throw away the rest of a key that starts with Escape, like an arrow key.

    Up arrow arrives as Escape, "[", "A". Each part is read with a very short
    wait, because a real sequence arrives all at once and a lone Escape press
    has nothing after it.

    Args:
        read_key (ReadKey): Where keys come from.
    """
    while True:
        key = read_key(REST_OF_KEY_SECONDS)
        if key is None or key.isalpha() or key == "~":
            return


def read_line(
    prompt: str,
    hidden: bool,
    seconds: float,
    read_key: ReadKey,
    write: Write,
    clock: Callable[[], float] = time.monotonic,
) -> str:
    """Show a prompt and read one line of typing, within a time limit.

    The deadline covers the whole screen, so typing never resets it.
    Ctrl+C is ignored, arrow keys are ignored, and hidden shows nothing at
    all while typing (not even stars, which would reveal the length).

    Args:
        prompt (str): The text shown before the typing, like "Enter password: ".
        hidden (bool): True to show nothing as keys are typed.
        seconds (float): The time limit for this screen.
        read_key (ReadKey): Where keys come from.
        write (Write): Where text is shown.
        clock (Callable[[], float]): Gives the current time in seconds.
            Defaults to time.monotonic; tests pass a fake one.

    Returns:
        str: The line typed, without the Enter.

    Raises:
        ScreenTimeout: If the time limit runs out before Enter.
        QuitRequested: If Ctrl+D is pressed.
    """
    deadline = clock() + seconds
    write(prompt)
    typed: list[str] = []

    while True:
        time_left = deadline - clock()
        if time_left <= 0:
            raise ScreenTimeout
        key = read_key(time_left)
        if key is None:
            raise ScreenTimeout

        if key in ENTER_KEYS:
            write("\r\n")
            return "".join(typed)
        if key == CTRL_D:
            raise QuitRequested
        if key == CTRL_C:
            continue
        if key in BACKSPACE_KEYS:
            if typed:
                typed.pop()
                if not hidden:
                    write(ERASE_LAST_CHAR)
            continue
        if key == ESCAPE:
            skip_escape_sequence(read_key)
            continue
        if key.isprintable() and key != REPLACEMENT_CHAR and len(typed) < MAX_INPUT_LENGTH:
            typed.append(key)
            if not hidden:
                write(key)


def show_for(
    text: str,
    seconds: float,
    read_key: ReadKey,
    write: Write,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Show text for a limited time, then clear the screen.

    Ctrl+C clears it early, Ctrl+D quits, and other keys are ignored. The
    screen is always cleared, even on Ctrl+D or an error, so a shown
    password is never left behind.

    Args:
        text (str): What to show, like an entry with its password.
        seconds (float): How long to show it, normally PASSWORD_VISIBLE_SECONDS.
        read_key (ReadKey): Where keys come from.
        write (Write): Where text is shown.
        clock (Callable[[], float]): Gives the current time in seconds.
            Defaults to time.monotonic; tests pass a fake one.

    Raises:
        QuitRequested: If Ctrl+D is pressed (after the screen is cleared).
    """
    deadline = clock() + seconds
    write(text)
    try:
        while True:
            time_left = deadline - clock()
            if time_left <= 0:
                return
            key = read_key(time_left)
            if key is None or key == CTRL_C:
                return
            if key == CTRL_D:
                raise QuitRequested
    finally:
        clear_screen(write)


@contextmanager
def raw_terminal() -> Iterator[None]:
    """Switch the terminal to raw mode for a with block, and always switch it back.

    In raw mode every key arrives straight away, nothing is echoed unless
    the app writes it (which is how hidden typing works), and Ctrl+C and
    Ctrl+D arrive as ordinary keys. The old settings are put back however
    the block ends, even on a crash, so the terminal is never left stuck.
    """
    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    tty.setraw(fd)
    try:
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


def terminal_read_key(seconds: float) -> str | None:
    """Wait up to seconds for one key on the real keyboard.

    The real ReadKey, used inside raw_terminal. Bytes are put together into
    whole characters, so é arrives as one key. Half a character whose rest
    never comes is thrown away and the wait carries on, so None only ever
    means the time ran out. A closed connection (the SSH session dropping)
    is reported as Ctrl+D, so the session ends cleanly.

    Args:
        seconds (float): The longest to wait for a key.

    Returns:
        str | None: The key, or None if nothing was pressed in time.
    """
    fd = sys.stdin.fileno()
    deadline = time.monotonic() + seconds
    while True:
        time_left = max(0.0, deadline - time.monotonic())
        ready, _, _ = select.select([fd], [], [], time_left)
        if not ready:
            return None
        key = _read_character(fd)
        if key:
            return key


def _read_character(fd: int) -> str:
    """Read the bytes of one character from the keyboard.

    Args:
        fd (int): The keyboard's file number.

    Returns:
        str: The character, CTRL_D if the connection closed, or "" if only
        half a character came (it is thrown away).
    """
    while True:
        byte = os.read(fd, 1)
        if not byte:
            return CTRL_D
        key = UTF8_DECODER.decode(byte)
        if key:
            return key
        ready, _, _ = select.select([fd], [], [], REST_OF_KEY_SECONDS)
        if not ready:
            UTF8_DECODER.reset()
            return ""


def terminal_write(text: str) -> None:
    """Show text on the real screen straight away.

    The real Write, used inside raw_terminal. print() isn't used because it
    adds a plain newline (which in raw mode doesn't go back to the start of
    the line) and may hold text back before showing it.

    Args:
        text (str): What to show. Use "\\r\\n" for a new line in raw mode.
    """
    sys.stdout.write(text)
    sys.stdout.flush()

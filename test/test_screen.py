"""Tests for the pivault screen helpers, using a fake keyboard, screen and clock."""

from collections.abc import Callable

import pytest

from pivault.vault.screen import (
    BACKSPACE_KEYS,
    CLEAR_SCREEN,
    CTRL_C,
    CTRL_D,
    ERASE_LAST_CHAR,
    ESCAPE,
    MAX_INPUT_LENGTH,
    QuitRequested,
    ReadKey,
    ScreenTimeout,
    clear_screen,
    read_line,
    show_for,
    skip_escape_sequence,
)

ENTER = "\r"
BACKSPACE = sorted(BACKSPACE_KEYS)[0]
UP_ARROW = [ESCAPE, "[", "A"]
PROMPT = "P: "


def fake_keyboard(keys: list[str]) -> ReadKey:
    """Return a read_key that hands out these keys in order, then None (nothing pressed)."""
    remaining = list(keys)

    def read_key(_seconds: float) -> str | None:
        return remaining.pop(0) if remaining else None

    return read_key


def fake_clock(step: float) -> Callable[[], float]:
    """Return a clock that moves forward by step seconds every time it's asked."""
    now = [0.0]

    def clock() -> float:
        now[0] += step
        return now[0]

    return clock


def type_line(keys: list[str], hidden: bool = False) -> tuple[str, str]:
    """Run read_line on these keys and return what it gave back and what was shown."""
    shown: list[str] = []
    line = read_line(PROMPT, hidden, 180, fake_keyboard(keys), shown.append)
    return line, "".join(shown)


# clear_screen

def test_clear_screen_writes_clear_code() -> None:
    """Test that clear_screen writes exactly the code that clears the scrollback and screen."""
    shown: list[str] = []
    clear_screen(shown.append)
    assert shown == [CLEAR_SCREEN]


# skip_escape_sequence

def test_skip_escape_sequence_stops_at_letter() -> None:
    """Test that an arrow key's "[A" is thrown away and the next key is left alone."""
    read_key = fake_keyboard(["[", "A", "b"])
    skip_escape_sequence(read_key)
    assert read_key(1) == "b"


def test_skip_escape_sequence_stops_at_tilde() -> None:
    """Test that keys like Delete, which end in ~, are thrown away up to the ~."""
    read_key = fake_keyboard(["[", "3", "~", "b"])
    skip_escape_sequence(read_key)
    assert read_key(1) == "b"


def test_skip_escape_sequence_lone_escape() -> None:
    """Test that a lone Escape press, with nothing after it, returns without hanging."""
    skip_escape_sequence(fake_keyboard([]))


# read_line

def test_read_line_typed_text() -> None:
    """Test that typed keys come back as a line and are shown after the prompt."""
    line, shown = type_line(list("abc") + [ENTER])
    assert line == "abc"
    assert shown == PROMPT + "abc\r\n"


def test_read_line_hidden_shows_nothing() -> None:
    """Test that hidden typing returns the line but never shows any of it, not even stars."""
    line, shown = type_line(list("secret") + [ENTER], hidden=True)
    assert line == "secret"
    assert shown == PROMPT + "\r\n"


def test_read_line_backspace() -> None:
    """Test that Backspace removes the last character and erases it on screen."""
    line, shown = type_line(["a", "b", BACKSPACE, "c", ENTER])
    assert line == "ac"
    assert ERASE_LAST_CHAR in shown


def test_read_line_backspace_hidden_erases_nothing() -> None:
    """Test that Backspace while hidden erases nothing on screen, since nothing was shown."""
    line, shown = type_line(["a", "b", BACKSPACE, ENTER], hidden=True)
    assert line == "a"
    assert ERASE_LAST_CHAR not in shown


def test_read_line_backspace_on_empty_line() -> None:
    """Test that Backspace on an empty line does nothing and doesn't crash."""
    line, shown = type_line([BACKSPACE, BACKSPACE, "a", ENTER])
    assert line == "a"
    assert ERASE_LAST_CHAR not in shown


def test_read_line_both_backspace_keys() -> None:
    """Test that both kinds of Backspace key (Delete and Ctrl+H) work."""
    for key in BACKSPACE_KEYS:
        line, _ = type_line(["a", "b", key, ENTER])
        assert line == "a"


def test_read_line_both_enter_keys() -> None:
    """Test that Enter works whether the terminal sends \\r or \\n."""
    assert type_line(["a", "\r"])[0] == "a"
    assert type_line(["a", "\n"])[0] == "a"


def test_read_line_ctrl_c_ignored() -> None:
    """Test that Ctrl+C is ignored, so it can never crash the app."""
    line, shown = type_line(["a", CTRL_C, "b", ENTER])
    assert line == "ab"
    assert CTRL_C not in shown


def test_read_line_ctrl_d_quits() -> None:
    """Test that Ctrl+D raises QuitRequested."""
    with pytest.raises(QuitRequested):
        type_line(["a", CTRL_D])


def test_read_line_no_key_times_out() -> None:
    """Test that running out of keys before Enter raises ScreenTimeout."""
    with pytest.raises(ScreenTimeout):
        type_line(["a", "b"])


def test_read_line_deadline_covers_whole_screen() -> None:
    """Test that the time limit runs out even while keys keep coming, so typing can't extend it."""
    keys = fake_keyboard(["a"] * 100 + [ENTER])
    shown: list[str] = []
    with pytest.raises(ScreenTimeout):
        read_line(PROMPT, False, 180, keys, shown.append, fake_clock(60))


def test_read_line_arrow_keys_ignored() -> None:
    """Test that an arrow key adds nothing, so Up doesn't type [A."""
    line, shown = type_line(["a", *UP_ARROW, "b", ENTER])
    assert line == "ab"
    assert "[A" not in shown


def test_read_line_control_keys_ignored() -> None:
    """Test that other control keys, like Ctrl+A, are ignored."""
    assert type_line(["a", "\x01", "b", ENTER])[0] == "ab"


def test_read_line_max_length() -> None:
    """Test that typing stops being added at MAX_INPUT_LENGTH characters."""
    line, _ = type_line(["x"] * (MAX_INPUT_LENGTH + 50) + [ENTER])
    assert line == "x" * MAX_INPUT_LENGTH


def test_read_line_accents_and_spaces() -> None:
    """Test that accented letters and spaces in the middle are kept."""
    line, _ = type_line(["\u00e9", " ", "z", ENTER])
    assert line == "\u00e9 z"


def test_read_line_empty_line() -> None:
    """Test that pressing Enter straight away gives an empty line."""
    assert type_line([ENTER])[0] == ""


# show_for

def run_show_for(keys: list[str], clock: Callable[[], float] | None = None) -> list[str]:
    """Run show_for on these keys and return everything that was written."""
    shown: list[str] = []
    if clock is None:
        show_for("PASSWORD", 30, fake_keyboard(keys), shown.append)
    else:
        show_for("PASSWORD", 30, fake_keyboard(keys), shown.append, clock)
    return shown


def test_show_for_times_out_and_clears() -> None:
    """Test that when time runs out it returns normally and clears the screen."""
    assert run_show_for([]) == ["PASSWORD", CLEAR_SCREEN]


def test_show_for_ctrl_c_hides_early() -> None:
    """Test that Ctrl+C ends it straight away (the next key is never read) and clears the screen."""
    shown: list[str] = []
    read_key = fake_keyboard([CTRL_C, "next"])
    show_for("PASSWORD", 30, read_key, shown.append)
    assert shown == ["PASSWORD", CLEAR_SCREEN]
    assert read_key(1) == "next"


def test_show_for_other_keys_ignored() -> None:
    """Test that other keys are ignored and not shown."""
    assert run_show_for(["a", "b", ENTER]) == ["PASSWORD", CLEAR_SCREEN]


def test_show_for_ctrl_d_quits_after_clearing() -> None:
    """Test that Ctrl+D raises QuitRequested, and the password is cleared first."""
    shown: list[str] = []
    with pytest.raises(QuitRequested):
        show_for("PASSWORD", 30, fake_keyboard([CTRL_D]), shown.append)
    assert shown == ["PASSWORD", CLEAR_SCREEN]


def test_show_for_deadline_ends_it() -> None:
    """Test that the time limit ends it even while keys keep coming."""
    assert run_show_for(["a"] * 100, fake_clock(20)) == ["PASSWORD", CLEAR_SCREEN]

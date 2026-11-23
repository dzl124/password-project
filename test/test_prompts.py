"""Tests for the shared prompts, using a fake keyboard, screen and clock."""

from collections.abc import Callable

import pytest

from pivault.checker import password_checker
from pivault.vault.prompts import (
    ask_line,
    ask_master_key,
    ask_new_password,
    ask_twofa_code,
    ask_username,
    ask_website,
    ask_yes_no,
)
from pivault.vault.screen import CTRL_D, QuitRequested, ReadKey, ScreenTimeout
from pivault.vault.session import Session

SECONDS = 180


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


def make_session(*lines: str) -> tuple[Session, list[str]]:
    """Return a Session that types these lines (each ending in Enter) and the list of what was shown."""
    keys = [key for line in lines for key in line + "\r"]
    shown: list[str] = []
    session = Session("laptop", fake_keyboard(keys), shown.append, clock=fake_clock(0.01))
    return session, shown


def silent_session() -> Session:
    """Return a Session where nothing is ever typed and the clock moves 1 second per look."""
    return Session("laptop", fake_keyboard([]), lambda _text: None, clock=fake_clock(1.0))


def ctrl_d_session() -> Session:
    """Return a Session where the only key pressed is Ctrl+D."""
    return Session("laptop", fake_keyboard([CTRL_D]), lambda _text: None, clock=fake_clock(0.01))


# ask_yes_no

def test_ask_yes_no_y() -> None:
    """Test that y means yes."""
    session, _ = make_session("y")
    assert ask_yes_no(session, "Q? ", SECONDS) is True


def test_ask_yes_no_upper_no() -> None:
    """Test that NO in capitals means no."""
    session, _ = make_session("NO")
    assert ask_yes_no(session, "Q? ", SECONDS) is False


def test_ask_yes_no_spaces() -> None:
    """Test that spaces around the answer are ignored."""
    session, _ = make_session(" Yes ")
    assert ask_yes_no(session, "Q? ", SECONDS) is True


def test_ask_yes_no_reasks() -> None:
    """Test that a wrong answer shows a hint and asks again."""
    session, shown = make_session("maybe", "n")
    assert ask_yes_no(session, "Q? ", SECONDS) is False
    assert "Please type y or n." in "".join(shown)


def test_ask_yes_no_timeout() -> None:
    """Test that nothing typed before the limit raises ScreenTimeout."""
    with pytest.raises(ScreenTimeout):
        ask_yes_no(silent_session(), "Q? ", 5)


# ask_website

def test_ask_website_valid() -> None:
    """Test that a valid website comes back cleaned."""
    session, _ = make_session("  github  ")
    assert ask_website(session, SECONDS) == "github"


def test_ask_website_too_long() -> None:
    """Test that a website over 64 characters is re-asked."""
    session, shown = make_session("a" * 65, "github")
    assert ask_website(session, SECONDS) == "github"
    assert "cannot exceed" in "".join(shown)


def test_ask_website_bad_char() -> None:
    """Test that a website with a character that isn't allowed is re-asked."""
    session, shown = make_session("git hub!", "github")
    assert ask_website(session, SECONDS) == "github"
    assert "invalid character" in "".join(shown)


def test_ask_website_empty() -> None:
    """Test that an empty website is re-asked."""
    session, shown = make_session("", "github")
    assert ask_website(session, SECONDS) == "github"
    assert "cannot be empty" in "".join(shown)


def test_ask_website_ctrl_d() -> None:
    """Test that Ctrl+D raises QuitRequested."""
    with pytest.raises(QuitRequested):
        ask_website(ctrl_d_session(), SECONDS)


# ask_username

def test_ask_username_kept_as_typed() -> None:
    """Test that the username's capitals are kept."""
    session, _ = make_session("Denzel_Q")
    assert ask_username(session, SECONDS) == "Denzel_Q"


def test_ask_username_too_long() -> None:
    """Test that a username over 48 characters is re-asked."""
    session, shown = make_session("a" * 49, "me")
    assert ask_username(session, SECONDS) == "me"
    assert "cannot exceed" in "".join(shown)


def test_ask_username_empty() -> None:
    """Test that an empty username is re-asked."""
    session, shown = make_session("", "me")
    assert ask_username(session, SECONDS) == "me"
    assert "cannot be empty" in "".join(shown)


def test_ask_username_unicode() -> None:
    """Test that a username with accented letters is accepted."""
    session, _ = make_session("josé")
    assert ask_username(session, SECONDS) == "josé"


def test_ask_username_timeout() -> None:
    """Test that nothing typed before the limit raises ScreenTimeout."""
    with pytest.raises(ScreenTimeout):
        ask_username(silent_session(), 5)


# ask_new_password

def test_ask_new_password_match() -> None:
    """Test that the same password typed twice is returned."""
    session, _ = make_session("hunter22", "hunter22")
    assert ask_new_password(session, SECONDS) == "hunter22"


def test_ask_new_password_mismatch_then_match() -> None:
    """Test that a mismatch starts over and the next matching pair is returned."""
    session, shown = make_session("first1", "other1", "second", "second")
    assert ask_new_password(session, SECONDS) == "second"
    assert "didn't match" in "".join(shown)


def test_ask_new_password_too_short() -> None:
    """Test that a password under min_length is re-asked before the confirm step."""
    session, shown = make_session("short", "longenough", "longenough")
    assert ask_new_password(session, SECONDS, min_length=8) == "longenough"
    assert "at least 8 characters" in "".join(shown)


def test_ask_new_password_never_shown() -> None:
    """Test that nothing typed appears in what was written."""
    session, shown = make_session("s3cretpw", "s3cretpw")
    ask_new_password(session, SECONDS)
    assert "s3cretpw" not in "".join(shown)


def test_ask_new_password_timeout() -> None:
    """Test that nothing typed before the limit raises ScreenTimeout."""
    with pytest.raises(ScreenTimeout):
        ask_new_password(silent_session(), 5)


# ask_master_key

def test_ask_master_key_returned() -> None:
    """Test that the master key comes back exactly as typed, spaces included."""
    session, _ = make_session(" my key ")
    assert ask_master_key(session, SECONDS) == " my key "


def test_ask_master_key_empty() -> None:
    """Test that an empty master key is re-asked."""
    session, shown = make_session("", "key")
    assert ask_master_key(session, SECONDS) == "key"
    assert "cannot be empty" in "".join(shown)


def test_ask_master_key_never_shown() -> None:
    """Test that the master key never appears in what was written."""
    session, shown = make_session("topsecret")
    ask_master_key(session, SECONDS)
    assert "topsecret" not in "".join(shown)


def test_ask_master_key_ctrl_d() -> None:
    """Test that Ctrl+D raises QuitRequested."""
    with pytest.raises(QuitRequested):
        ask_master_key(ctrl_d_session(), SECONDS)


def test_ask_master_key_timeout() -> None:
    """Test that nothing typed before the limit raises ScreenTimeout."""
    with pytest.raises(ScreenTimeout):
        ask_master_key(silent_session(), 5)


# ask_twofa_code

def test_ask_twofa_code_as_typed() -> None:
    """Test that the code comes back with its space, for check_twofa_code to remove."""
    session, _ = make_session("123 456")
    assert ask_twofa_code(session, SECONDS) == "123 456"


def test_ask_twofa_code_empty() -> None:
    """Test that only spaces is re-asked."""
    session, shown = make_session("   ", "123456")
    assert ask_twofa_code(session, SECONDS) == "123456"
    assert "cannot be empty" in "".join(shown)


def test_ask_twofa_code_letters_returned() -> None:
    """Test that letters are still returned, since check_twofa_code rejects them."""
    session, _ = make_session("abcdef")
    assert ask_twofa_code(session, SECONDS) == "abcdef"


def test_ask_twofa_code_timeout() -> None:
    """Test that nothing typed before the limit raises ScreenTimeout."""
    with pytest.raises(ScreenTimeout):
        ask_twofa_code(silent_session(), 5)


def test_ask_twofa_code_ctrl_d() -> None:
    """Test that Ctrl+D raises QuitRequested."""
    with pytest.raises(QuitRequested):
        ask_twofa_code(ctrl_d_session(), SECONDS)


# ask_line

def test_ask_line_returns_typed_line() -> None:
    """Test that ask_line gives back the line typed."""
    session, shown = make_session("hello")
    assert ask_line(session, "Q: ", False, deadline=SECONDS) == "hello"
    assert "".join(shown).startswith("Q: ")


def test_ask_line_hidden() -> None:
    """Test that hidden typing is returned but never shown."""
    session, shown = make_session("secret")
    assert ask_line(session, "Q: ", True, deadline=SECONDS) == "secret"
    assert "secret" not in "".join(shown)


def test_ask_line_past_deadline() -> None:
    """Test that a deadline already gone times out straight away, even with keys waiting."""
    session, _ = make_session("too late")
    with pytest.raises(ScreenTimeout):
        ask_line(session, "Q: ", False, deadline=0.0)


# ask_website and ask_username with a current value (Edit)

def test_ask_website_enter_keeps_current() -> None:
    """Test that Enter keeps the saved website, and the prompt shows it in brackets."""
    session, shown = make_session("")
    assert ask_website(session, SECONDS, current="netflix") == "netflix"
    assert "Website [netflix]: " in "".join(shown)


def test_ask_website_spaces_keep_current() -> None:
    """Test that only spaces counts as Enter and keeps the saved website."""
    session, _ = make_session("   ")
    assert ask_website(session, SECONDS, current="netflix") == "netflix"


def test_ask_website_new_value_replaces_current() -> None:
    """Test that a typed website replaces the saved one and is cleaned."""
    session, _ = make_session("  Hulu ")
    assert ask_website(session, SECONDS, current="netflix") == "hulu"


def test_ask_website_bad_new_value_reasked() -> None:
    """Test that a bad new website is still refused in Edit, then Enter keeps the saved one."""
    session, shown = make_session("net.flix", "")
    assert ask_website(session, SECONDS, current="netflix") == "netflix"
    assert "invalid character" in "".join(shown)


def test_ask_website_add_prompt() -> None:
    """Test that Add's prompt says name only, and Enter there is still an error."""
    session, shown = make_session("", "netflix")
    assert ask_website(session, SECONDS) == "netflix"
    assert "name only" in "".join(shown)
    assert "cannot be empty" in "".join(shown)


def test_ask_username_enter_keeps_current() -> None:
    """Test that Enter keeps the saved username, and the prompt shows it in brackets."""
    session, shown = make_session("")
    assert ask_username(session, SECONDS, current="Denzel") == "Denzel"
    assert "Username [Denzel]: " in "".join(shown)


def test_ask_username_new_value_replaces_current() -> None:
    """Test that a typed username replaces the saved one, capitals kept."""
    session, _ = make_session("Jeffa")
    assert ask_username(session, SECONDS, current="Denzel") == "Jeffa"


def test_ask_username_add_enter_is_error() -> None:
    """Test that without a current value, Enter is still an error."""
    session, shown = make_session("", "Denzel")
    assert ask_username(session, SECONDS) == "Denzel"
    assert "cannot be empty" in "".join(shown)


# ask_new_password with a checker (Add and Edit)

STRONG = "Movie!!night42"


def test_ask_new_password_checker_lists_every_problem() -> None:
    """Test that a weak password shows every broken rule, then a strong one is accepted."""
    session, shown = make_session("abc", STRONG, STRONG)
    assert ask_new_password(session, SECONDS, checker=password_checker) == STRONG
    for problem in password_checker("abc"):
        assert problem in "".join(shown)


def test_ask_new_password_checker_skips_retype() -> None:
    """Test that a password failing the checker isn't asked for a second time."""
    session, shown = make_session("abc", STRONG, STRONG)
    ask_new_password(session, SECONDS, checker=password_checker)
    assert "".join(shown).count("Type it again: ") == 1


def test_ask_new_password_checker_strong_first_time() -> None:
    """Test that a strong password passes straight away with no messages."""
    session, shown = make_session(STRONG, STRONG)
    assert ask_new_password(session, SECONDS, checker=password_checker) == STRONG
    assert "".join(shown).count("New password: ") == 1


def test_ask_new_password_checker_only_sees_first_entry() -> None:
    """Test that the checker runs on the password, not on the retype."""
    checked: list[str] = []

    def record(password: str) -> list[str]:
        checked.append(password)
        return []

    session, _ = make_session("first", "first")
    ask_new_password(session, SECONDS, checker=record)
    assert checked == ["first"]


def test_ask_new_password_length_checked_before_checker() -> None:
    """Test that a too-short password gets only the length message, not the checker's."""
    session, shown = make_session("abc", STRONG, STRONG)
    ask_new_password(session, SECONDS, min_length=5, checker=password_checker)
    assert "at least 5 characters" in "".join(shown)
    assert "uppercase" not in "".join(shown)

"""Tests for the pivault 2FA functions."""

import time
from pathlib import Path

import pyotp
import pytest

from pivault.vault.storage import StorageError
from pivault.vault.twofa import (
    BASE32_CHARS,
    check_twofa_code,
    format_setup_key,
    load_twofa_secret,
    make_twofa_secret,
    save_twofa_secret,
    twofa_qr_text,
    twofa_setup_uri,
)

# Codes change every 30 seconds.
STEP_SECONDS = 30


def wait_for_fresh_step() -> None:
    """Wait if a new 30-second step is about to start, so a test can't straddle two steps."""
    seconds_into_step = time.time() % STEP_SECONDS
    if seconds_into_step > STEP_SECONDS - 5:
        time.sleep(STEP_SECONDS - seconds_into_step + 1)


# make_twofa_secret

def test_make_twofa_secret_length() -> None:
    """Test that a secret is 32 characters, 160 bits."""
    assert len(make_twofa_secret()) == 32


def test_make_twofa_secret_characters() -> None:
    """Test that a secret only uses base32 characters, A-Z and 2-7."""
    for _ in range(20):
        assert all(char in BASE32_CHARS for char in make_twofa_secret())


def test_make_twofa_secret_unique() -> None:
    """Test that two secrets are different."""
    assert make_twofa_secret() != make_twofa_secret()


def test_make_twofa_secret_no_padding() -> None:
    """Test that a secret has no = padding, which some authenticator apps reject."""
    assert "=" not in make_twofa_secret()


def test_make_twofa_secret_makes_codes() -> None:
    """Test that a secret can make 6-digit codes."""
    code = pyotp.TOTP(make_twofa_secret()).now()
    assert len(code) == 6
    assert code.isdigit()


# save_twofa_secret

def test_save_twofa_secret_text(tmp_path: Path) -> None:
    """Test that the file holds the secret and a newline."""
    path = tmp_path / "twofa_secret.txt"
    secret = make_twofa_secret()
    save_twofa_secret(path, secret)
    assert path.read_text(encoding="utf-8") == secret + "\n"


def test_save_twofa_secret_owner_only(tmp_path: Path) -> None:
    """Test that the secret file can only be read and written by its owner."""
    path = tmp_path / "twofa_secret.txt"
    save_twofa_secret(path, make_twofa_secret())
    assert path.stat().st_mode & 0o777 == 0o600


def test_save_twofa_secret_overwrite(tmp_path: Path) -> None:
    """Test that saving a new secret, as a 2FA reset does, replaces the old one."""
    path = tmp_path / "twofa_secret.txt"
    save_twofa_secret(path, make_twofa_secret())
    new_secret = make_twofa_secret()
    save_twofa_secret(path, new_secret)
    assert path.read_text(encoding="utf-8") == new_secret + "\n"


def test_save_twofa_secret_no_leftovers(tmp_path: Path) -> None:
    """Test that no .tmp file is left in the folder."""
    path = tmp_path / "twofa_secret.txt"
    save_twofa_secret(path, make_twofa_secret())
    assert list(tmp_path.iterdir()) == [path]


def test_save_twofa_secret_missing_folder(tmp_path: Path) -> None:
    """Test that saving into a folder that doesn't exist raises OSError."""
    with pytest.raises(OSError):
        save_twofa_secret(tmp_path / "nope" / "twofa_secret.txt", make_twofa_secret())


# load_twofa_secret

def test_load_twofa_secret_round_trip(tmp_path: Path) -> None:
    """Test that a saved secret loads back exactly, without its newline."""
    path = tmp_path / "twofa_secret.txt"
    secret = make_twofa_secret()
    save_twofa_secret(path, secret)
    assert load_twofa_secret(path) == secret


def test_load_twofa_secret_missing(tmp_path: Path) -> None:
    """Test that a missing file raises StorageError."""
    with pytest.raises(StorageError):
        load_twofa_secret(tmp_path / "twofa_secret.txt")


def test_load_twofa_secret_empty(tmp_path: Path) -> None:
    """Test that an empty or only-whitespace file raises StorageError."""
    path = tmp_path / "twofa_secret.txt"
    path.write_text("\n", encoding="utf-8")
    with pytest.raises(StorageError):
        load_twofa_secret(path)


def test_load_twofa_secret_lowercase(tmp_path: Path) -> None:
    """Test that a lowercase secret raises StorageError, since base32 is capitals only."""
    path = tmp_path / "twofa_secret.txt"
    path.write_text(make_twofa_secret().lower(), encoding="utf-8")
    with pytest.raises(StorageError):
        load_twofa_secret(path)


def test_load_twofa_secret_junk(tmp_path: Path) -> None:
    """Test that characters outside base32, like 0, 1 or !, raise StorageError."""
    path = tmp_path / "twofa_secret.txt"
    path.write_text("NOT BASE32 0 1 !", encoding="utf-8")
    with pytest.raises(StorageError):
        load_twofa_secret(path)


# check_twofa_code

def test_check_twofa_code_current() -> None:
    """Test that the code the app shows right now is accepted."""
    secret = make_twofa_secret()
    assert check_twofa_code(secret, pyotp.TOTP(secret).now())


def test_check_twofa_code_spaces() -> None:
    """Test that spaces in the middle or around the code are ignored."""
    secret = make_twofa_secret()
    code = pyotp.TOTP(secret).now()
    assert check_twofa_code(secret, code[:3] + " " + code[3:])
    assert check_twofa_code(secret, "  " + code + " ")


def test_check_twofa_code_wrong() -> None:
    """Test that a code with one digit changed is refused."""
    secret = make_twofa_secret()
    code = pyotp.TOTP(secret).now()
    wrong = code[:-1] + str((int(code[-1]) + 1) % 10)
    assert not check_twofa_code(secret, wrong)


def test_check_twofa_code_bad_shape() -> None:
    """Test that anything that isn't exactly 6 ASCII digits is refused."""
    secret = make_twofa_secret()
    arabic_indic_digits = chr(0x0661) * 6
    for code in ["", "12345", "1234567", "abcdef", "12 34 5", arabic_indic_digits]:
        assert not check_twofa_code(secret, code)


def test_check_twofa_code_window() -> None:
    """Test that codes one step either side are accepted, but three steps back are not."""
    wait_for_fresh_step()
    secret = make_twofa_secret()
    totp = pyotp.TOTP(secret)
    now = int(time.time())
    assert check_twofa_code(secret, totp.at(now - STEP_SECONDS))
    assert check_twofa_code(secret, totp.at(now + STEP_SECONDS))
    assert not check_twofa_code(secret, totp.at(now - 3 * STEP_SECONDS))


# twofa_setup_uri

def test_twofa_setup_uri_scheme() -> None:
    """Test that the link is a TOTP link an authenticator app understands."""
    assert twofa_setup_uri(make_twofa_secret()).startswith("otpauth://totp/")


def test_twofa_setup_uri_secret() -> None:
    """Test that the link holds the secret."""
    secret = make_twofa_secret()
    assert "secret=" + secret in twofa_setup_uri(secret)


def test_twofa_setup_uri_issuer() -> None:
    """Test that the link names PiVault as the issuer."""
    assert "issuer=PiVault" in twofa_setup_uri(make_twofa_secret())


def test_twofa_setup_uri_label() -> None:
    """Test that the label is PiVault:vault, which the app shows as the entry's name."""
    assert "/PiVault:vault?" in twofa_setup_uri(make_twofa_secret())


def test_twofa_setup_uri_parses_back() -> None:
    """Test that reading the link back gives the same codes as the secret."""
    secret = make_twofa_secret()
    parsed = pyotp.parse_uri(twofa_setup_uri(secret))
    assert isinstance(parsed, pyotp.TOTP)
    assert parsed.secret == secret


# twofa_qr_text

def test_twofa_qr_text_inverted() -> None:
    """Test that the drawing starts with a solid border, so it suits a dark terminal."""
    first_line = twofa_qr_text(twofa_setup_uri(make_twofa_secret())).splitlines()[0]
    assert first_line
    assert set(first_line) == {"\N{FULL BLOCK}"}


def test_twofa_qr_text_many_lines() -> None:
    """Test that the drawing is many lines tall, not one long line."""
    lines = twofa_qr_text(twofa_setup_uri(make_twofa_secret())).splitlines()
    assert len(lines) > 20


def test_twofa_qr_text_rectangle() -> None:
    """Test that every line is the same width, so the pattern isn't broken."""
    lines = twofa_qr_text(twofa_setup_uri(make_twofa_secret())).splitlines()
    assert len({len(line) for line in lines}) == 1


def test_twofa_qr_text_different_links() -> None:
    """Test that two different secrets give two different drawings."""
    first = twofa_qr_text(twofa_setup_uri(make_twofa_secret()))
    second = twofa_qr_text(twofa_setup_uri(make_twofa_secret()))
    assert first != second


def test_twofa_qr_text_same_link() -> None:
    """Test that the same link always gives the same drawing."""
    uri = twofa_setup_uri(make_twofa_secret())
    assert twofa_qr_text(uri) == twofa_qr_text(uri)


# format_setup_key

def test_format_setup_key_groups() -> None:
    """Test that a 32-character secret becomes 8 groups of 4."""
    groups = format_setup_key(make_twofa_secret()).split(" ")
    assert len(groups) == 8
    assert all(len(group) == 4 for group in groups)


def test_format_setup_key_same_secret() -> None:
    """Test that removing the spaces gives back the exact secret."""
    secret = make_twofa_secret()
    assert format_setup_key(secret).replace(" ", "") == secret


def test_format_setup_key_example() -> None:
    """Test a known secret, to show the exact shape."""
    assert format_setup_key("JBSWY3DPEHPK3PXP") == "JBSW Y3DP EHPK 3PXP"


def test_format_setup_key_short_last_group() -> None:
    """Test that a length that isn't a multiple of 4 leaves a short last group."""
    assert format_setup_key("ABCDEF") == "ABCD EF"


def test_format_setup_key_makes_same_codes() -> None:
    """Test that a key typed by hand makes the same codes as the scanned secret."""
    secret = make_twofa_secret()
    typed = format_setup_key(secret).replace(" ", "")
    assert pyotp.TOTP(typed).now() == pyotp.TOTP(secret).now()

"""Tests for the pivault file helpers."""

import os
from pathlib import Path

import pytest

from pivault.vault.files import save_file_safely


# save_file_safely

def test_save_file_safely_new_file(tmp_path: Path) -> None:
    """Test that saving to a new path creates it with exactly that text."""
    path = tmp_path / "file.json"
    save_file_safely(path, "hello caf\u00e9")
    assert path.read_text(encoding="utf-8") == "hello caf\u00e9"


def test_save_file_safely_overwrite(tmp_path: Path) -> None:
    """Test that saving twice leaves only the second text."""
    path = tmp_path / "file.json"
    save_file_safely(path, "first")
    save_file_safely(path, "second")
    assert path.read_text(encoding="utf-8") == "second"


def test_save_file_safely_no_leftovers(tmp_path: Path) -> None:
    """Test that no .tmp file is left in the folder after saving."""
    path = tmp_path / "file.json"
    save_file_safely(path, "first")
    save_file_safely(path, "second")
    assert list(tmp_path.iterdir()) == [path]


def test_save_file_safely_owner_only(tmp_path: Path) -> None:
    """Test that the saved file can only be read and written by its owner."""
    path = tmp_path / "file.json"
    save_file_safely(path, "secret")
    assert path.stat().st_mode & 0o777 == 0o600


def test_save_file_safely_failure_keeps_old_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that a failed swap keeps the old file, removes the temp file and raises."""
    path = tmp_path / "file.json"
    save_file_safely(path, "old")

    def failing_replace(source: str, target: Path) -> None:
        raise OSError(f"disk full while moving {source} to {target}")

    monkeypatch.setattr(os, "replace", failing_replace)
    with pytest.raises(OSError):
        save_file_safely(path, "new")
    assert path.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.iterdir()) == [path]

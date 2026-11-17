"""File helpers for the pivault application, shared by every module that saves a file."""

import os
import tempfile
from pathlib import Path


def save_file_safely(path: Path, text: str) -> None:
    """Write text to a file so a power cut never leaves it half-written.

    Writes a temp file in the same folder, forces it to disk, swaps it in
    with one rename, then forces the folder to disk. The file ends up
    owner-only.

    Args:
        path (Path): The file to write, like settings.ENTRIES_FILE.
        text (str): The file's new contents.

    Raises:
        OSError: If the folder is missing or the disk is full. The temp
        file is removed first, and the old file is left as it was.
    """
    fd, temp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_name, path)
    except BaseException:
        os.unlink(temp_name)
        raise

    folder_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(folder_fd)
    finally:
        os.close(folder_fd)

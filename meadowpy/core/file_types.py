"""Shared file type helpers."""

from __future__ import annotations

from pathlib import Path


PYTHON_FILE_SUFFIXES = {".py", ".pyw"}


def is_python_file_path(file_path: str | None) -> bool:
    """Return True when ``file_path`` can be treated as Python source."""
    if not file_path:
        return True
    return Path(file_path).suffix.lower() in PYTHON_FILE_SUFFIXES

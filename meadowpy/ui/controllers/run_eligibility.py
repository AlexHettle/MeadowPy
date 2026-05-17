"""Helpers for deciding whether the current editor can be run as Python."""

from __future__ import annotations

from pathlib import Path
from typing import Any

PYTHON_FILE_SUFFIXES = {".py", ".pyw"}


def is_python_file_path(file_path: str | None) -> bool:
    """Return True when ``file_path`` points at a runnable Python file."""
    if not file_path:
        return True
    return Path(file_path).suffix.lower() in PYTHON_FILE_SUFFIXES


def can_run_editor(editor: Any, expected_type: type | tuple[type, ...] | None = None) -> bool:
    """Return True if ``editor`` should expose Run File behavior."""
    if editor is None:
        return False
    if expected_type is not None and not isinstance(editor, expected_type):
        return False
    return is_python_file_path(getattr(editor, "file_path", None))

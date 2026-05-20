"""Helpers for deciding whether the current editor can be run as Python."""

from __future__ import annotations

from typing import Any

from meadowpy.core.file_types import PYTHON_FILE_SUFFIXES, is_python_file_path


def can_run_editor(editor: Any, expected_type: type | tuple[type, ...] | None = None) -> bool:
    """Return True if ``editor`` should expose Run File behavior."""
    if editor is None:
        return False
    if expected_type is not None and not isinstance(editor, expected_type):
        return False
    return is_python_file_path(getattr(editor, "file_path", None))

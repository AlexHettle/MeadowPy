"""Shared file type helpers."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path


PYTHON_FILE_SUFFIXES = {".py", ".pyw"}


class SyntaxLanguage(StrEnum):
    """Syntax-highlighting languages supported by the editor."""

    PYTHON = "python"
    JSON = "json"
    MARKDOWN = "markdown"
    YAML = "yaml"
    PROPERTIES = "properties"
    PLAIN = "plain"


_SYNTAX_LANGUAGE_BY_SUFFIX = {
    ".py": SyntaxLanguage.PYTHON,
    ".pyw": SyntaxLanguage.PYTHON,
    ".json": SyntaxLanguage.JSON,
    ".md": SyntaxLanguage.MARKDOWN,
    ".markdown": SyntaxLanguage.MARKDOWN,
    ".yaml": SyntaxLanguage.YAML,
    ".yml": SyntaxLanguage.YAML,
    ".ini": SyntaxLanguage.PROPERTIES,
    ".cfg": SyntaxLanguage.PROPERTIES,
    ".properties": SyntaxLanguage.PROPERTIES,
}


def syntax_language_for_path(file_path: str | None) -> SyntaxLanguage:
    """Return the editor highlighting language for ``file_path``.

    Untitled files preserve MeadowPy's existing Python-first behavior.  This
    classification is intentionally independent from whether a file can run
    or debug as Python.
    """
    if not file_path:
        return SyntaxLanguage.PYTHON
    return _SYNTAX_LANGUAGE_BY_SUFFIX.get(
        Path(file_path).suffix.lower(),
        SyntaxLanguage.PLAIN,
    )


def is_python_file_path(file_path: str | None) -> bool:
    """Return True when ``file_path`` can be treated as Python source."""
    if not file_path:
        return True
    return Path(file_path).suffix.lower() in PYTHON_FILE_SUFFIXES

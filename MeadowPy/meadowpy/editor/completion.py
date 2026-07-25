"""Auto-completion setup using QScintilla's QsciAPIs system."""

import builtins
import keyword
import sys

from PyQt6.Qsci import QsciAPIs, QsciLexerPython

_CACHED_COMPLETIONS: list[str] | None = None


def get_python_completions() -> list[str]:
    """Return a sorted list of Python keywords + builtins + stdlib module names."""
    global _CACHED_COMPLETIONS
    if _CACHED_COMPLETIONS is not None:
        return _CACHED_COMPLETIONS

    words = set()

    # Python keywords
    words.update(keyword.kwlist)

    # Builtin names (excluding dunder names)
    words.update(name for name in dir(builtins) if not name.startswith("_"))

    # Standard library module names (Python 3.10+)
    if hasattr(sys, "stdlib_module_names"):
        words.update(
            name for name in sys.stdlib_module_names if not name.startswith("_")
        )

    _CACHED_COMPLETIONS = sorted(words)
    return _CACHED_COMPLETIONS


def create_apis(lexer: QsciLexerPython) -> QsciAPIs:
    """Create and prepare a QsciAPIs object for auto-completion."""
    apis = QsciAPIs(lexer)
    for word in get_python_completions():
        apis.add(word)
    apis.prepare()
    return apis

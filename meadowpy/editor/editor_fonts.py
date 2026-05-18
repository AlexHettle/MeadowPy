"""Helpers for selecting fonts that are safe for the code editor."""

from PyQt6.QtGui import QFontDatabase


DEFAULT_EDITOR_FONT_FAMILY = "Consolas"
EDITOR_FONT_FALLBACKS = (
    "Cascadia Mono",
    DEFAULT_EDITOR_FONT_FAMILY,
    "Courier New",
    "Monospace",
    "monospace",
)


def _families() -> list[str]:
    try:
        return list(QFontDatabase.families())
    except RuntimeError:
        return []


def _known_family(family: str, families: list[str]) -> bool:
    return family in families or any(
        name.startswith(f"{family} [") for name in families
    )


def _is_smoothly_scalable(family: str) -> bool:
    return QFontDatabase.isSmoothlyScalable(family)


def is_editor_safe_font_family(family: str | None) -> bool:
    """Return True for scalable families suited to QScintilla."""
    if not family:
        return False

    families = _families()
    if not families:
        return True
    if not _known_family(family, families):
        return False

    try:
        return _is_smoothly_scalable(family)
    except RuntimeError:
        return False


def editor_font_family(preferred_family: str | None) -> str:
    """Return a safe editor font, falling back when a saved font is unsuitable."""
    if is_editor_safe_font_family(preferred_family):
        return str(preferred_family)

    for family in EDITOR_FONT_FALLBACKS:
        if is_editor_safe_font_family(family):
            return family

    families = _families()
    for family in families:
        if is_editor_safe_font_family(family):
            return family

    return DEFAULT_EDITOR_FONT_FAMILY

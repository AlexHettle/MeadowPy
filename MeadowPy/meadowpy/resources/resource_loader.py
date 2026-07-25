"""Compatibility facade for MeadowPy resource helpers."""

from meadowpy.resources.resource_icons import (
    load_themed_icon as _load_themed_icon,
    load_tinted_icon as _load_tinted_icon,
)
from meadowpy.resources.resource_paths import (
    DEFAULT_RESOURCES_DIR,
    get_font_path as _get_font_path,
    get_icon_path as _get_icon_path,
)
from meadowpy.resources.stylesheet_loader import get_stylesheet as _get_stylesheet
from meadowpy.resources.theme_colors import (
    current_accent_hex,
    darken_color,
    lighten_color,
    resolve_accent_shades as _resolve_accent_shades,
    run_button_accent_hex,
    theme_is_dark,
    theme_is_high_contrast,
)

_RESOURCES_DIR = DEFAULT_RESOURCES_DIR


def get_icon_path(name: str) -> str:
    """Return the full path to an icon file, or empty string if not found."""
    return _get_icon_path(name, _RESOURCES_DIR)


def load_themed_icon(name: str, theme_name: str = ""):
    """Return a QIcon for *name*, color-mapped if the current theme requires it."""
    return _load_themed_icon(name, theme_name, _RESOURCES_DIR)


def load_tinted_icon(name: str, color: str, size: int = 16):
    """Render a ``{{COLOR}}``-templated SVG into a QIcon at the given color."""
    return _load_tinted_icon(name, color, size, _RESOURCES_DIR)


def get_font_path(name: str) -> str:
    """Return the full path to a font file, or empty string if not found."""
    return _get_font_path(name, _RESOURCES_DIR)


def get_stylesheet(
    theme_name: str = "default_light",
    *,
    custom_base: str = "dark",
    custom_accent: str | None = None,
) -> str:
    """Load and return the QSS stylesheet for the given theme."""
    return _get_stylesheet(
        theme_name,
        custom_base=custom_base,
        custom_accent=custom_accent,
        resources_dir=_RESOURCES_DIR,
    )


__all__ = [
    "_RESOURCES_DIR",
    "_resolve_accent_shades",
    "current_accent_hex",
    "darken_color",
    "get_font_path",
    "get_icon_path",
    "get_stylesheet",
    "lighten_color",
    "load_themed_icon",
    "load_tinted_icon",
    "run_button_accent_hex",
    "theme_is_dark",
    "theme_is_high_contrast",
]

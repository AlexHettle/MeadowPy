"""Utility to resolve resource paths for icons and stylesheets."""

from pathlib import Path

_RESOURCES_DIR = Path(__file__).parent


def get_icon_path(name: str) -> str:
    """Return the full path to an icon file, or empty string if not found."""
    for ext in (".svg", ".png"):
        path = _RESOURCES_DIR / "icons" / f"{name}{ext}"
        if path.exists():
            return str(path)
    return ""


def get_font_path(name: str) -> str:
    """Return the full path to a font file, or empty string if not found."""
    path = _RESOURCES_DIR / "fonts" / name
    if path.exists():
        return str(path)
    return ""


def get_stylesheet(theme_name: str = "default_light") -> str:
    """Load and return the QSS stylesheet for the given theme."""
    if "dark" in theme_name:
        qss_path = _RESOURCES_DIR / "styles" / "meadowpy_dark.qss"
    else:
        qss_path = _RESOURCES_DIR / "styles" / "meadowpy.qss"
    if qss_path.exists():
        content = qss_path.read_text(encoding="utf-8")
        icons_dir = str(_RESOURCES_DIR / "icons").replace("\\", "/")
        return content.replace("{{ICONS_DIR}}", icons_dir)
    return ""

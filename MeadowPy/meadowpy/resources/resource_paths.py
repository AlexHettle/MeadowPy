"""Path helpers for MeadowPy bundled resources."""

from pathlib import Path

DEFAULT_RESOURCES_DIR = Path(__file__).parent


def get_icon_path(
    name: str,
    resources_dir: Path | str = DEFAULT_RESOURCES_DIR,
) -> str:
    """Return the full path to an icon file, or empty string if not found."""
    base_dir = Path(resources_dir)
    for ext in (".svg", ".png"):
        path = base_dir / "icons" / f"{name}{ext}"
        if path.exists():
            return str(path)
    return ""


def get_font_path(
    name: str,
    resources_dir: Path | str = DEFAULT_RESOURCES_DIR,
) -> str:
    """Return the full path to a font file, or empty string if not found."""
    path = Path(resources_dir) / "fonts" / name
    if path.exists():
        return str(path)
    return ""

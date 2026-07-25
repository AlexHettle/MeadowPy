"""Stylesheet loading and theme post-processing helpers."""

from pathlib import Path

from meadowpy.resources.resource_paths import DEFAULT_RESOURCES_DIR
from meadowpy.resources.theme_colors import (
    resolve_accent_shades,
    theme_is_dark,
    theme_is_high_contrast,
)

# Substitutions applied to the dark QSS template when rendering the
# high-contrast theme. Longer / more-specific keys come first so replacements
# do not rewrite something they just produced.
_HIGH_CONTRAST_SUBSTITUTIONS: list[tuple[str, str]] = [
    ("#094771", "#FFFFFF"),
    ("#2F5C88", "#FFFFFF"),
    ("#2A2D2E", "#2A2A2A"),
    ("#3A3D3A", "#2A2A2A"),
    ("#1E1E1E", "#000000"),
    ("#252526", "#000000"),
    ("#252525", "#000000"),
    ("#181818", "#000000"),
    ("#222222", "#000000"),
    ("#232323", "#000000"),
]


def _load_high_contrast_overrides(resources_dir: Path | str) -> str:
    overrides_path = Path(resources_dir) / "styles" / "high_contrast_overrides.qss"
    if not overrides_path.exists():
        return ""
    return "\n" + overrides_path.read_text(encoding="utf-8")


def get_stylesheet(
    theme_name: str = "default_light",
    *,
    custom_base: str = "dark",
    custom_accent: str | None = None,
    resources_dir: Path | str = DEFAULT_RESOURCES_DIR,
) -> str:
    """Load and return the QSS stylesheet for the given theme."""
    if theme_name == "custom":
        is_dark = (custom_base or "dark").lower() == "dark"
    else:
        is_dark = theme_is_dark(theme_name, custom_base)

    is_hc = theme_is_high_contrast(theme_name)
    base_dir = Path(resources_dir)
    qss_path = base_dir / "styles" / (
        "meadowpy_dark.qss" if is_dark else "meadowpy.qss"
    )
    if not qss_path.exists():
        return ""

    content = qss_path.read_text(encoding="utf-8")

    shades = resolve_accent_shades(theme_name, is_dark, custom_accent)
    icons_dir = str(base_dir / "icons").replace("\\", "/")

    content = content.replace("{{ICONS_DIR}}", icons_dir)
    for key in sorted(shades, key=len, reverse=True):
        content = content.replace("{{" + key + "}}", shades[key])

    if is_hc:
        for old, new in _HIGH_CONTRAST_SUBSTITUTIONS:
            content = content.replace(old, new)
            content = content.replace(old.lower(), new)
        content += _load_high_contrast_overrides(base_dir)

    return content

"""Utility to resolve resource paths for icons and stylesheets."""

import colorsys
from pathlib import Path
from typing import Optional

_RESOURCES_DIR = Path(__file__).parent

# Default "green" accents used by the built-in Light and Dark themes.
# The QSS files contain `{{ACCENT}}` / `{{ACCENT_HOVER}}` placeholders; these
# values are substituted in when rendering the Light or Dark theme so the
# themes look exactly as they did before the template refactor.
_DEFAULT_LIGHT_ACCENT = "#2E7D32"
_DEFAULT_LIGHT_HOVER = "#1B5E20"
_DEFAULT_LIGHT_TINT = "#A0D4AD"         # pale — selected-tab gradient (light)
_DEFAULT_LIGHT_BRIGHT = "#2E7D32"       # unused by light QSS, kept for parity
_DEFAULT_LIGHT_HOVER_BRIGHT = "#1B5E20" # unused by light QSS, kept for parity

_DEFAULT_DARK_ACCENT = "#2F7A44"
_DEFAULT_DARK_HOVER = "#245F35"
_DEFAULT_DARK_TINT = "#A0D4AD"          # unused by dark QSS, kept for parity
_DEFAULT_DARK_BRIGHT = "#4CAF50"        # REPL prompt, example-library highlights
_DEFAULT_DARK_HOVER_BRIGHT = "#38934F"  # example-library open button hover


def get_icon_path(name: str) -> str:
    """Return the full path to an icon file, or empty string if not found."""
    for ext in (".svg", ".png"):
        path = _RESOURCES_DIR / "icons" / f"{name}{ext}"
        if path.exists():
            return str(path)
    return ""


def load_tinted_icon(name: str, color: str, size: int = 16):
    """Render a ``{{COLOR}}``-templated SVG into a QIcon at the given color.

    Returns an empty ``QIcon`` if the named icon isn't found on disk.

    The pixmap is rendered at 2× the requested size so Qt can downscale
    smoothly when the view's icon slot is smaller, yielding crisper edges
    than a 1× render.
    """
    from PyQt6.QtCore import QByteArray, QSize, Qt
    from PyQt6.QtGui import QIcon, QPainter, QPixmap
    from PyQt6.QtSvg import QSvgRenderer

    svg_path = _RESOURCES_DIR / "icons" / f"{name}.svg"
    if not svg_path.exists():
        return QIcon()

    svg_data = svg_path.read_text(encoding="utf-8").replace("{{COLOR}}", color)
    renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))

    render_size = size * 2
    pixmap = QPixmap(QSize(render_size, render_size))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2.0)

    # Explicitly register the same pixmap for every mode so Qt doesn't
    # auto-generate a greyed-out variant (e.g. when a tree item is
    # selected or a button is hovered).
    icon = QIcon()
    for mode in (
        QIcon.Mode.Normal,
        QIcon.Mode.Active,
        QIcon.Mode.Selected,
        QIcon.Mode.Disabled,
    ):
        for state in (QIcon.State.On, QIcon.State.Off):
            icon.addPixmap(pixmap, mode, state)
    return icon


def get_font_path(name: str) -> str:
    """Return the full path to a font file, or empty string if not found."""
    path = _RESOURCES_DIR / "fonts" / name
    if path.exists():
        return str(path)
    return ""


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    """Convert '#RRGGBB' to (r, g, b) floats in [0, 1]."""
    s = hex_color.lstrip("#")
    if len(s) != 6:
        raise ValueError(f"Expected a #RRGGBB hex color, got {hex_color!r}")
    r = int(s[0:2], 16) / 255.0
    g = int(s[2:4], 16) / 255.0
    b = int(s[4:6], 16) / 255.0
    return r, g, b


def _rgb_to_hex(r: float, g: float, b: float) -> str:
    return "#{:02X}{:02X}{:02X}".format(
        int(round(_clamp(r) * 255)),
        int(round(_clamp(g) * 255)),
        int(round(_clamp(b) * 255)),
    )


def theme_is_dark(theme_name: str, custom_base: str = "dark") -> bool:
    """Return True if the given theme renders a dark chrome.

    Handles the ``"custom"`` theme by deferring to ``custom_base``.
    Used by callers (tab manager, main window, welcome widget, ...) to
    decide which icon/variant to paint without duplicating the logic.
    """
    if theme_name == "custom":
        return (custom_base or "dark").lower() == "dark"
    return "dark" in (theme_name or "")


def darken_color(hex_color: str, amount: float = 0.12) -> str:
    """Return a darker shade of `hex_color` by reducing HSL lightness.

    `amount` is in [0, 1]; 0.12 = 12% darker.
    """
    try:
        r, g, b = _hex_to_rgb(hex_color)
    except ValueError:
        return hex_color
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = _clamp(l - amount)
    r2, g2, b2 = colorsys.hls_to_rgb(h, l, s)
    return _rgb_to_hex(r2, g2, b2)


def lighten_color(
    hex_color: str, l_add: float = 0.15, s_mul: float = 1.0
) -> str:
    """Return a lighter shade by raising HSL lightness and optionally desaturating.

    ``l_add`` adds to L (0..1). ``s_mul`` multiplies S.
    """
    try:
        r, g, b = _hex_to_rgb(hex_color)
    except ValueError:
        return hex_color
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = _clamp(l + l_add)
    s = _clamp(s * s_mul)
    r2, g2, b2 = colorsys.hls_to_rgb(h, l, s)
    return _rgb_to_hex(r2, g2, b2)


def _resolve_accent_shades(
    theme_name: str,
    is_dark: bool,
    custom_accent: Optional[str],
) -> dict[str, str]:
    """Return all accent-related shades for the given theme.

    Keys in the returned dict map 1:1 to the QSS placeholders:
        ACCENT, ACCENT_HOVER, ACCENT_TINT, ACCENT_BRIGHT, ACCENT_HOVER_BRIGHT.
    """
    if theme_name == "custom" and custom_accent:
        accent = custom_accent
        return {
            "ACCENT":              accent,
            "ACCENT_HOVER":        darken_color(accent, 0.12),
            "ACCENT_TINT":         lighten_color(accent, 0.40, 0.75),
            "ACCENT_BRIGHT":       lighten_color(accent, 0.18, 1.0),
            "ACCENT_HOVER_BRIGHT": lighten_color(accent, 0.08, 1.0),
        }
    if is_dark:
        return {
            "ACCENT":              _DEFAULT_DARK_ACCENT,
            "ACCENT_HOVER":        _DEFAULT_DARK_HOVER,
            "ACCENT_TINT":         _DEFAULT_DARK_TINT,
            "ACCENT_BRIGHT":       _DEFAULT_DARK_BRIGHT,
            "ACCENT_HOVER_BRIGHT": _DEFAULT_DARK_HOVER_BRIGHT,
        }
    return {
        "ACCENT":              _DEFAULT_LIGHT_ACCENT,
        "ACCENT_HOVER":        _DEFAULT_LIGHT_HOVER,
        "ACCENT_TINT":         _DEFAULT_LIGHT_TINT,
        "ACCENT_BRIGHT":       _DEFAULT_LIGHT_BRIGHT,
        "ACCENT_HOVER_BRIGHT": _DEFAULT_LIGHT_HOVER_BRIGHT,
    }


def current_accent_hex(
    theme_name: str,
    custom_base: str = "dark",
    custom_accent: Optional[str] = None,
) -> str:
    """Return the base ``ACCENT`` hex used by the current theme."""
    if theme_name == "custom" and custom_accent:
        return custom_accent
    is_dark = theme_is_dark(theme_name, custom_base)
    return _DEFAULT_DARK_ACCENT if is_dark else _DEFAULT_LIGHT_ACCENT


def run_button_accent_hex(
    theme_name: str,
    custom_accent: Optional[str] = None,
) -> str:
    """Return the hex color used for the "run" button glow.

    Built-in Light and Dark themes keep the original bright green (#4CAF50).
    The Custom theme uses a brighter shade of the user's chosen accent so
    the glow reads as a highlight rather than a muted background color.
    """
    if theme_name == "custom" and custom_accent:
        return lighten_color(custom_accent, 0.18, 1.0)
    return "#4CAF50"


def get_stylesheet(
    theme_name: str = "default_light",
    *,
    custom_base: str = "dark",
    custom_accent: Optional[str] = None,
) -> str:
    """Load and return the QSS stylesheet for the given theme.

    Parameters
    ----------
    theme_name
        One of ``"default_light"``, ``"default_dark"``, or ``"custom"``.
    custom_base
        Only used when ``theme_name == "custom"`` — ``"light"`` or ``"dark"``
        selects which base QSS template to render.
    custom_accent
        Only used when ``theme_name == "custom"`` — a ``#RRGGBB`` accent color
        that replaces the default green across the UI.
    """
    if theme_name == "custom":
        is_dark = (custom_base or "dark").lower() == "dark"
    else:
        is_dark = "dark" in theme_name

    qss_path = _RESOURCES_DIR / "styles" / (
        "meadowpy_dark.qss" if is_dark else "meadowpy.qss"
    )
    if not qss_path.exists():
        return ""

    content = qss_path.read_text(encoding="utf-8")

    shades = _resolve_accent_shades(theme_name, is_dark, custom_accent)
    icons_dir = str(_RESOURCES_DIR / "icons").replace("\\", "/")

    content = content.replace("{{ICONS_DIR}}", icons_dir)
    # Replace the longest placeholder names first — "{{ACCENT}}" is a
    # prefix of "{{ACCENT_HOVER}}" etc., so naive replacement in the wrong
    # order would corrupt the output.
    for key in sorted(shades, key=len, reverse=True):
        content = content.replace("{{" + key + "}}", shades[key])
    return content

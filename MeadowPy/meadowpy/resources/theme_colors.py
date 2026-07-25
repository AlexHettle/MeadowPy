"""Theme and color helpers for MeadowPy resources."""

import colorsys

# Default "green" accents used by the built-in Light and Dark themes.
DEFAULT_LIGHT_ACCENT = "#2E7D32"
DEFAULT_LIGHT_HOVER = "#1B5E20"
DEFAULT_LIGHT_TINT = "#A0D4AD"
DEFAULT_LIGHT_BRIGHT = "#2E7D32"
DEFAULT_LIGHT_HOVER_BRIGHT = "#1B5E20"

DEFAULT_DARK_ACCENT = "#2F7A44"
DEFAULT_DARK_HOVER = "#245F35"
DEFAULT_DARK_TINT = "#A0D4AD"
DEFAULT_DARK_BRIGHT = "#4CAF50"
DEFAULT_DARK_HOVER_BRIGHT = "#38934F"

# High-contrast theme: pure black and white only.
DEFAULT_HC_ACCENT = "#FFFFFF"
DEFAULT_HC_HOVER = "#CCCCCC"
DEFAULT_HC_TINT = "#FFFFFF"
DEFAULT_HC_BRIGHT = "#FFFFFF"
DEFAULT_HC_HOVER_BRIGHT = "#FFFFFF"


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
    """Return True if the given theme renders a dark chrome."""
    if theme_name == "custom":
        return (custom_base or "dark").lower() == "dark"
    if theme_name == "default_high_contrast":
        return True
    return "dark" in (theme_name or "")


def theme_is_high_contrast(theme_name: str) -> bool:
    """Return True if the given theme is the high-contrast accessibility theme."""
    return theme_name == "default_high_contrast"


def darken_color(hex_color: str, amount: float = 0.12) -> str:
    """Return a darker shade of `hex_color` by reducing HSL lightness."""
    try:
        r, g, b = _hex_to_rgb(hex_color)
    except ValueError:
        return hex_color
    h, lightness, saturation = colorsys.rgb_to_hls(r, g, b)
    lightness = _clamp(lightness - amount)
    r2, g2, b2 = colorsys.hls_to_rgb(h, lightness, saturation)
    return _rgb_to_hex(r2, g2, b2)


def lighten_color(
    hex_color: str,
    l_add: float = 0.15,
    s_mul: float = 1.0,
) -> str:
    """Return a lighter shade by raising HSL lightness and tuning saturation."""
    try:
        r, g, b = _hex_to_rgb(hex_color)
    except ValueError:
        return hex_color
    h, lightness, saturation = colorsys.rgb_to_hls(r, g, b)
    lightness = _clamp(lightness + l_add)
    saturation = _clamp(saturation * s_mul)
    r2, g2, b2 = colorsys.hls_to_rgb(h, lightness, saturation)
    return _rgb_to_hex(r2, g2, b2)


def resolve_accent_shades(
    theme_name: str,
    is_dark: bool,
    custom_accent: str | None,
) -> dict[str, str]:
    """Return all accent-related shades for the given theme."""
    if theme_name == "custom" and custom_accent:
        accent = custom_accent
        return {
            "ACCENT": accent,
            "ACCENT_HOVER": darken_color(accent, 0.12),
            "ACCENT_TINT": lighten_color(accent, 0.40, 0.75),
            "ACCENT_BRIGHT": lighten_color(accent, 0.18, 1.0),
            "ACCENT_HOVER_BRIGHT": lighten_color(accent, 0.08, 1.0),
        }
    if theme_name == "default_high_contrast":
        return {
            "ACCENT": DEFAULT_HC_ACCENT,
            "ACCENT_HOVER": DEFAULT_HC_HOVER,
            "ACCENT_TINT": DEFAULT_HC_TINT,
            "ACCENT_BRIGHT": DEFAULT_HC_BRIGHT,
            "ACCENT_HOVER_BRIGHT": DEFAULT_HC_HOVER_BRIGHT,
        }
    if is_dark:
        return {
            "ACCENT": DEFAULT_DARK_ACCENT,
            "ACCENT_HOVER": DEFAULT_DARK_HOVER,
            "ACCENT_TINT": DEFAULT_DARK_TINT,
            "ACCENT_BRIGHT": DEFAULT_DARK_BRIGHT,
            "ACCENT_HOVER_BRIGHT": DEFAULT_DARK_HOVER_BRIGHT,
        }
    return {
        "ACCENT": DEFAULT_LIGHT_ACCENT,
        "ACCENT_HOVER": DEFAULT_LIGHT_HOVER,
        "ACCENT_TINT": DEFAULT_LIGHT_TINT,
        "ACCENT_BRIGHT": DEFAULT_LIGHT_BRIGHT,
        "ACCENT_HOVER_BRIGHT": DEFAULT_LIGHT_HOVER_BRIGHT,
    }


def current_accent_hex(
    theme_name: str,
    custom_base: str = "dark",
    custom_accent: str | None = None,
) -> str:
    """Return the base ``ACCENT`` hex used by the current theme."""
    if theme_name == "custom" and custom_accent:
        return custom_accent
    if theme_name == "default_high_contrast":
        return DEFAULT_HC_ACCENT
    is_dark = theme_is_dark(theme_name, custom_base)
    return DEFAULT_DARK_ACCENT if is_dark else DEFAULT_LIGHT_ACCENT


def run_button_accent_hex(
    theme_name: str,
    custom_accent: str | None = None,
) -> str:
    """Return the hex color used for the "run" button glow."""
    if theme_name == "custom" and custom_accent:
        return lighten_color(custom_accent, 0.18, 1.0)
    if theme_name == "default_high_contrast":
        return DEFAULT_HC_ACCENT
    return "#4CAF50"

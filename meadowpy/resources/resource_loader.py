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

# High-contrast theme — pure black and white only (no chroma anywhere).
# Selection / focus / primary-action affordances are signalled by inverting
# the surface (white bg, black text) instead of by introducing a third color.
_DEFAULT_HC_ACCENT = "#FFFFFF"
_DEFAULT_HC_HOVER = "#CCCCCC"
_DEFAULT_HC_TINT = "#FFFFFF"
_DEFAULT_HC_BRIGHT = "#FFFFFF"
_DEFAULT_HC_HOVER_BRIGHT = "#FFFFFF"


# Substitutions applied to the dark QSS template when rendering the
# high-contrast theme — keeps a single source of truth for layout/borders
# while remapping every color slot to a pure-black-on-white-on-yellow
# palette. Order matters: longer / more-specific keys first so we don't
# rewrite something we just produced.
_HIGH_CONTRAST_SUBSTITUTIONS: list[tuple[str, str]] = [
    # Selection / highlights — invert surface to white-on-black
    ("#094771", "#FFFFFF"),
    ("#2F5C88", "#FFFFFF"),
    # Caret-line / subtle row highlight — neutral grey, no chroma
    ("#2A2D2E", "#2A2A2A"),
    ("#3A3D3A", "#2A2A2A"),
    # Backgrounds → pure black
    ("#1E1E1E", "#000000"),
    ("#252526", "#000000"),
    ("#252525", "#000000"),
    ("#181818", "#000000"),
    ("#222222", "#000000"),
    ("#232323", "#000000"),
    # NOTE: We intentionally do *not* remap #3C3C3C, #2D2D2D, #454545, #555555,
    # etc. The same hex is used as both fills (buttons/combos/inputs) AND
    # borders/separators throughout the QSS, so a blanket swap produced
    # white-on-white widgets. The override block below explicitly restyles
    # those interactables instead.
]


# Appended verbatim to the end of the QSS in HC mode. Targets every widget
# that can't be safely color-substituted because it shares hex values with
# unrelated UI parts (buttons, inputs, combos, checkboxes, scrollbars).
# Rule of thumb: pure black background, pure white text, pure white border,
# yellow accent for selection / focus / primary actions — and on yellow
# surfaces, text flips to BLACK so it stays legible.
_HIGH_CONTRAST_OVERRIDES = """
/* === High Contrast accessibility overrides — pure black & white === */
QWidget { color: #FFFFFF; }

QPushButton {
    background: #000000;
    color: #FFFFFF;
    border: 2px solid #FFFFFF;
    border-radius: 4px;
}
QPushButton:hover { background: #FFFFFF; color: #000000; }
QPushButton:focus { border: 3px solid #FFFFFF; }
QPushButton:pressed { background: #FFFFFF; color: #000000; }
QPushButton:disabled { color: #7F7F7F; border-color: #7F7F7F; }

QDialogButtonBox QPushButton:default,
QDialogButtonBox QPushButton:default:hover {
    background: #FFFFFF;
    color: #000000;
    border: 2px solid #FFFFFF;
}

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox, QFontComboBox {
    background: #000000;
    color: #FFFFFF;
    border: 2px solid #FFFFFF;
    border-radius: 3px;
    selection-background-color: #FFFFFF;
    selection-color: #000000;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QComboBox:focus, QFontComboBox:focus {
    border: 3px solid #FFFFFF;
}

QComboBox::drop-down, QSpinBox::up-button, QSpinBox::down-button {
    background: #000000;
    border-left: 2px solid #FFFFFF;
}
QComboBox QAbstractItemView {
    background: #000000;
    color: #FFFFFF;
    border: 2px solid #FFFFFF;
    selection-background-color: #FFFFFF;
    selection-color: #000000;
}

QCheckBox, QRadioButton, QLabel { color: #FFFFFF; background: transparent; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 14px; height: 14px;
    background: #000000;
    border: 2px solid #FFFFFF;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background: #FFFFFF;
    border-color: #FFFFFF;
}

QMenu, QMenuBar { background: #000000; color: #FFFFFF; }
QMenuBar::item:selected, QMenu::item:selected {
    background: #FFFFFF; color: #000000;
}

QGroupBox { border: 2px solid #FFFFFF; border-radius: 4px; margin-top: 8px; color: #FFFFFF; }
QGroupBox::title { color: #FFFFFF; }

QToolBar { background: #000000; border: none; }
QToolBar QToolButton { color: #FFFFFF; background: #000000; border: 2px solid transparent; }
QToolBar QToolButton:hover { background: #FFFFFF; border-color: #FFFFFF; }
QToolBar QToolButton:pressed { background: #FFFFFF; }

QStatusBar { background: #000000; color: #FFFFFF; }

QScrollBar:vertical, QScrollBar:horizontal {
    background: #000000; border: 1px solid #FFFFFF;
}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: #FFFFFF; border: 1px solid #FFFFFF;
}
QScrollBar::add-line, QScrollBar::sub-line { background: #000000; }

QHeaderView::section { background: #000000; color: #FFFFFF; border: 1px solid #FFFFFF; }
QTreeView, QListView, QTableView, QTableWidget {
    background: #000000; color: #FFFFFF; alternate-background-color: #000000;
    selection-background-color: #FFFFFF; selection-color: #000000;
}
QTreeView::item:hover, QListView::item:hover, QTableView::item:hover {
    background: #2A2A2A;
}

QSplitter::handle { background: #FFFFFF; }

QDockWidget { color: #FFFFFF; }
QDockWidget::title { background: #000000; color: #FFFFFF; border: 1px solid #FFFFFF; }

/* Frames / panel containers — solid white border for clear separation */
#explorerContainer, #outputContainer, #aiChatContainer, #editorContainer,
#aiChatTitleBar, #aiChatInputContainer {
    border: 2px solid #FFFFFF;
}

/* Tab bars — selected tab inverts (white bg + black text), no chroma anywhere */
QTabBar::tab { color: #FFFFFF; background: #000000; border: 2px solid transparent; border-bottom: none; }
QTabBar::tab:selected {
    background: #FFFFFF; color: #000000;
    border: 2px solid #FFFFFF; border-bottom: none;
    border-top: 3px solid #FFFFFF;
}
QTabBar::tab:hover:!selected { background: #2A2A2A; color: #FFFFFF; }

/* Project pill badge — must override its inline stylesheet */
#explorerProjectBadge {
    background: #000000;
    color: #FFFFFF;
    border: 2px solid #FFFFFF;
}
#explorerProjectBadge:hover { background: #FFFFFF; color: #000000; }

/* AI chat extras */
#aiChatHint { color: #FFFFFF; }
#aiChatPlaceholder { color: #FFFFFF; }

/* Accent-styled buttons across the app — the underlying QSS sets these to
   `background: ACCENT; color: white;`, which collapses to white-on-white in
   HC mode. Force black text on every white-background interactable. */
/* Specificity here matches or exceeds the original QSS rules
   (e.g. `#SearchPanel #searchRunBtn`) so the cascade lands on us. */
#aiChatSendBtn,
#SearchPanel #searchRunBtn,
#OutputPanel #replRunBtn,
#exLibOpenBtn,
#findToggleBtn:checked,
#welcomeActionBtn,
#welcomeTemplateCard,
#chatBubbleUser,
QPushButton:default,
QPushButton:default:hover {
    background: #FFFFFF;
    color: #000000;
    border: 2px solid #FFFFFF;
}
#aiChatSendBtn:hover,
#SearchPanel #searchRunBtn:hover,
#OutputPanel #replRunBtn:hover,
#exLibOpenBtn:hover,
#welcomeActionBtn:hover {
    background: #CCCCCC;
    color: #000000;
}
#aiChatSendBtn:disabled,
#SearchPanel #searchRunBtn:disabled,
#OutputPanel #replRunBtn:disabled,
#aiChatStopBtn:disabled {
    background: #2A2A2A;
    color: #7F7F7F;
    border-color: #7F7F7F;
}

/* Status bar should stay black-on-white at the very bottom of the window */
QStatusBar { background: #FFFFFF; color: #000000; }
QStatusBar QLabel { background: transparent; color: #000000; border: none; }
"""


def get_icon_path(name: str) -> str:
    """Return the full path to an icon file, or empty string if not found."""
    for ext in (".svg", ".png"):
        path = _RESOURCES_DIR / "icons" / f"{name}{ext}"
        if path.exists():
            return str(path)
    return ""


# Hardcoded fills inside the colorful SVG icons (run, debug, restart, stop, ...).
# When the theme is "high contrast" we collapse every semantic color (red /
# orange / green) onto pure white so the toolbar is fully monochromatic — HC
# mode is intended for users who can't reliably distinguish colors anyway,
# and pure black/white maximises luminance contrast.
_HC_ICON_COLOR_MAP: dict[str, str] = {
    "#4CAF50": "#FFFFFF",  # run green
    "#FF9800": "#FFFFFF",  # debug / restart orange (fill)
    "#E65100": "#FFFFFF",  # debug stroke (dark orange)
    "#F57C00": "#FFFFFF",  # restart stroke
    "#E51400": "#FFFFFF",  # stop red
    "#A30000": "#FFFFFF",  # stop stroke
}


def load_themed_icon(name: str, theme_name: str = ""):
    """Return a QIcon for *name*, color-mapped if the current theme requires it.

    Falls back to a plain ``QIcon(path)`` for non-HC themes. In HC mode the
    SVG content is patched in memory so the icon's hardcoded brand colors
    become the accessibility accent (yellow).
    """
    from PyQt6.QtGui import QIcon

    path = get_icon_path(name)
    if not path:
        return QIcon()

    # Only HC needs SVG color rewriting today; everything else loads as-is.
    if theme_name != "default_high_contrast" or not path.endswith(".svg"):
        return QIcon(path)

    try:
        from PyQt6.QtCore import QByteArray
        from PyQt6.QtSvg import QSvgRenderer
        from PyQt6.QtGui import QPainter, QPixmap
        from PyQt6.QtCore import QSize, Qt

        svg_text = Path(path).read_text(encoding="utf-8")
        for old, new in _HC_ICON_COLOR_MAP.items():
            svg_text = svg_text.replace(old, new)
            svg_text = svg_text.replace(old.lower(), new)
        renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
        # Render at a generous size so the icon stays crisp when scaled down
        # in toolbars / output panels.
        size = 48
        pixmap = QPixmap(QSize(size, size))
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)
    except Exception:
        return QIcon(path)


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
    if theme_name == "default_high_contrast":
        return True
    return "dark" in (theme_name or "")


def theme_is_high_contrast(theme_name: str) -> bool:
    """Return True if the given theme is the high-contrast accessibility theme."""
    return theme_name == "default_high_contrast"


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
    if theme_name == "default_high_contrast":
        return {
            "ACCENT":              _DEFAULT_HC_ACCENT,
            "ACCENT_HOVER":        _DEFAULT_HC_HOVER,
            "ACCENT_TINT":         _DEFAULT_HC_TINT,
            "ACCENT_BRIGHT":       _DEFAULT_HC_BRIGHT,
            "ACCENT_HOVER_BRIGHT": _DEFAULT_HC_HOVER_BRIGHT,
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
    if theme_name == "default_high_contrast":
        return _DEFAULT_HC_ACCENT
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
    if theme_name == "default_high_contrast":
        return _DEFAULT_HC_ACCENT
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
        is_dark = theme_is_dark(theme_name, custom_base)

    # High-contrast theme is rendered from the dark template, then
    # post-processed to swap every neutral palette color for a
    # pure-black/white/yellow equivalent.
    is_hc = theme_is_high_contrast(theme_name)
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

    # Apply the HC palette swap *after* placeholders so accent stays accent,
    # then append HC-specific overrides for widgets that can't be safely
    # color-substituted (buttons, combos, etc. share hex values with borders).
    if is_hc:
        for old, new in _HIGH_CONTRAST_SUBSTITUTIONS:
            content = content.replace(old, new)
            content = content.replace(old.lower(), new)
        content += _HIGH_CONTRAST_OVERRIDES

    return content

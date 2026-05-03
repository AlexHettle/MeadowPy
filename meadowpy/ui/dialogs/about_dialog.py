"""About MeadowPy dialog."""

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QWidget

from meadowpy.constants import APP_NAME, VERSION
from meadowpy.core.settings import Settings
from meadowpy.resources.resource_loader import (
    current_accent_hex,
    darken_color,
    get_icon_path,
    lighten_color,
    run_button_accent_hex,
    theme_is_high_contrast,
)


def _rounded_pixmap(pixmap: QPixmap, size: int, radius: float) -> QPixmap:
    """Return ``pixmap`` scaled and clipped to a rounded square."""
    scaled = pixmap.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    rounded = QPixmap(size, size)
    rounded.fill(Qt.GlobalColor.transparent)

    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    clip_path = QPainterPath()
    clip_path.addRoundedRect(0, 0, size, size, radius, radius)
    painter.setClipPath(clip_path)
    painter.drawPixmap(0, 0, scaled)
    painter.end()

    return rounded


class _AboutHeroWidget(QWidget):
    """Paint the entire About popup body as one stable widget."""

    def __init__(self, palette: dict[str, str], high_contrast: bool, parent=None):
        super().__init__(parent)
        self._palette = palette
        self._high_contrast = high_contrast
        self._icon_size = 112 if high_contrast else 118
        self._icon_radius = 26
        self._icon = QPixmap()

        icon_path = get_icon_path("meadowpy_256") or get_icon_path("meadowpy")
        if icon_path:
            self._icon = _rounded_pixmap(
                QPixmap(icon_path),
                self._icon_size,
                self._icon_radius,
            )

        self._title_font = QFont("Segoe UI", 1)
        self._title_font.setPixelSize(34 if high_contrast else 36)
        self._title_font.setBold(True)

        self._tagline_font = QFont("Segoe UI", 1)
        self._tagline_font.setPixelSize(14 if high_contrast else 15)
        self._tagline_font.setBold(True)

        self._version_font = QFont("Segoe UI", 1)
        self._version_font.setPixelSize(14)
        self._version_font.setBold(True)

        self._built_with_font = QFont("Segoe UI", 1)
        self._built_with_font.setPixelSize(13)

        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

    def paintEvent(self, event) -> None:
        """Paint the hero background, icon, and all text."""
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        self._paint_background(painter)
        icon_rect = self._paint_icon(painter)
        content_top = int(icon_rect.bottom()) + 22
        built_with_fm = QFontMetrics(self._built_with_font)
        built_with_height = built_with_fm.height() + 6
        bottom_padding = 14 if self._high_contrast else 18
        built_with_top = self.height() - bottom_padding - built_with_height
        pill_top = built_with_top - 16 - 40
        title_bottom = self._paint_title(painter, content_top)
        tagline_top = title_bottom + 12
        max_tagline_top = pill_top - (QFontMetrics(self._tagline_font).height() + 18)
        tagline_top = max(title_bottom + 10, min(tagline_top, max_tagline_top))
        tagline_bottom = self._paint_tagline(painter, tagline_top)
        pill_top = max(tagline_bottom + 20, pill_top)
        pill_bottom = self._paint_version_pill(painter, pill_top)
        self._paint_built_with(painter, built_with_top)
        painter.end()

    def _paint_background(self, painter: QPainter) -> None:
        """Paint the dialog background and soft lower glow."""
        painter.fillRect(self.rect(), QColor(self._palette["background"]))

        gradient = QRadialGradient(
            self.width() * 0.50,
            self.height() * 0.95,
            max(self.width() * 0.66, self.height() * 0.96),
        )
        accent = QColor(self._palette["accent"])
        strong = QColor(accent)
        strong.setAlpha(28 if self._high_contrast else 40)
        soft = QColor(accent)
        soft.setAlpha(14 if self._high_contrast else 22)
        gradient.setColorAt(0.00, strong)
        gradient.setColorAt(0.30, soft)
        gradient.setColorAt(0.62, QColor(0, 0, 0, 0))
        gradient.setColorAt(1.00, QColor(self._palette["surface"]))
        painter.fillRect(self.rect(), gradient)

    def _paint_icon(self, painter: QPainter) -> QRectF:
        """Paint the centered icon and its halo."""
        icon_left = (self.width() - self._icon_size) / 2
        icon_top = 24
        icon_rect = QRectF(icon_left, icon_top, self._icon_size, self._icon_size)

        glow_color = QColor(self._palette["accent"])
        max_expand = 14 if self._high_contrast else 18
        max_alpha = 10 if self._high_contrast else 16
        glow_steps = 8 if self._high_contrast else 12
        for step in range(glow_steps, 0, -1):
            distance = step / glow_steps
            expand = 2 + (max_expand * distance)
            alpha = max(1, round(2 + (max_alpha * (1.0 - distance))))
            layer_color = QColor(glow_color)
            layer_color.setAlpha(alpha)
            layer_rect = icon_rect.adjusted(-expand, -expand, expand, expand)
            layer_radius = self._icon_radius + expand
            layer_path = QPainterPath()
            layer_path.addRoundedRect(layer_rect, layer_radius, layer_radius)
            painter.fillPath(layer_path, layer_color)

        inner_glow = QColor(glow_color)
        inner_glow.setAlpha(14 if self._high_contrast else 20)
        inner_rect = icon_rect.adjusted(-3, -3, 3, 3)
        inner_path = QPainterPath()
        inner_path.addRoundedRect(
            inner_rect,
            self._icon_radius + 3,
            self._icon_radius + 3,
        )
        painter.fillPath(inner_path, inner_glow)

        if not self._icon.isNull():
            painter.drawPixmap(
                int(icon_rect.x()),
                int(icon_rect.y()),
                self._icon,
            )
        return icon_rect

    def _paint_title(self, painter: QPainter, top: int) -> int:
        """Paint the two-tone MeadowPy title."""
        base = APP_NAME[:-2] if APP_NAME.endswith("Py") else APP_NAME
        suffix = APP_NAME[-2:] if APP_NAME.endswith("Py") else ""

        painter.setFont(self._title_font)
        fm = QFontMetrics(self._title_font)
        baseline = top + fm.ascent()
        total_width = fm.horizontalAdvance(base + suffix)
        base_width = fm.horizontalAdvance(base)
        start_x = int((self.width() - total_width) / 2)

        painter.setPen(QColor(self._palette["text"]))
        painter.drawText(start_x, baseline, base)
        painter.setPen(QColor(self._palette["accent"]))
        painter.drawText(start_x + base_width, baseline, suffix)
        return top + fm.height()

    def _paint_tagline(self, painter: QPainter, top: int) -> int:
        """Paint the centered product description."""
        painter.setFont(self._tagline_font)
        fm = QFontMetrics(self._tagline_font)
        painter.setPen(QColor(self._palette["muted"]))
        rect = QRectF(44, top, self.width() - 88, fm.height() + 8)
        painter.drawText(
            rect,
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
            "A beginner-friendly Python IDE with AI assistance.",
        )
        return int(rect.bottom())

    def _paint_version_pill(self, painter: QPainter, top: int) -> int:
        """Paint the centered version pill."""
        text = f"Version {VERSION}"
        painter.setFont(self._version_font)
        fm = QFontMetrics(self._version_font)

        pill_width = fm.horizontalAdvance(text) + 34
        pill_height = 40
        pill_left = int((self.width() - pill_width) / 2)
        pill_rect = QRectF(pill_left, top, pill_width, pill_height)

        pill_fill = QColor(self._palette["accent"])
        pill_fill.setAlpha(18 if self._high_contrast else 22)
        pill_border = QColor(self._palette["accent"])
        pill_border.setAlpha(120 if self._high_contrast else 96)

        painter.setPen(QPen(pill_border, 1))
        painter.setBrush(pill_fill)
        painter.drawRoundedRect(pill_rect, pill_height / 2, pill_height / 2)

        painter.setPen(QColor(self._palette["text"]))
        painter.drawText(
            pill_rect,
            int(Qt.AlignmentFlag.AlignCenter),
            text,
        )
        return int(pill_rect.bottom())

    def _paint_built_with(self, painter: QPainter, top: int) -> None:
        """Paint the supporting technology line."""
        painter.setFont(self._built_with_font)
        fm = QFontMetrics(self._built_with_font)
        painter.setPen(QColor(self._palette["subtle"]))
        rect = QRectF(40, top, self.width() - 80, fm.height() + 6)
        painter.drawText(
            rect,
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
            "Built with PyQt6 and QScintilla.",
        )


class AboutDialog(QDialog):
    """Branded About dialog matching MeadowPy's visual identity."""

    def __init__(self, settings: Settings | None = None, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._palette, self._is_high_contrast = self._build_palette()

        self.setWindowTitle(f"About {APP_NAME}")
        self.setFixedSize(460, 384)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(
            _AboutHeroWidget(
                self._palette,
                self._is_high_contrast,
                self,
            )
        )

    def _build_palette(self) -> tuple[dict[str, str], bool]:
        """Resolve dialog colors from the current theme settings."""
        theme_name = "default_dark"
        custom_base = "dark"
        custom_accent = None

        if self._settings is not None:
            theme_name = self._settings.get("editor.theme") or theme_name
            custom_base = (
                self._settings.get("editor.custom_theme.base") or custom_base
            )
            custom_accent = self._settings.get("editor.custom_theme.accent")

        is_high_contrast = theme_is_high_contrast(theme_name)
        if is_high_contrast:
            palette = {
                "background": "#000000",
                "surface": "#000000",
                "text": "#FFFFFF",
                "muted": "#DEDEDE",
                "subtle": "#BFBFBF",
                "accent": "#FFFFFF",
            }
            return palette, True

        base_accent = current_accent_hex(theme_name, custom_base, custom_accent)
        hero_accent = run_button_accent_hex(theme_name, custom_accent)
        bright_accent = lighten_color(hero_accent, 0.10, 1.0)
        deep_accent = darken_color(base_accent, 0.28)
        palette = {
            "background": "#040805",
            "surface": "#06110A",
            "text": "#F6FAF5",
            "muted": "#97A39A",
            "subtle": "#7C887E",
            "accent": bright_accent,
            "panel": deep_accent,
        }
        return palette, False

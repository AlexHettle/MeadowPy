"""Custom painted hero block for the MeadowPy welcome screen."""

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPixmap,
)
from PyQt6.QtWidgets import QSizePolicy, QWidget

from meadowpy.constants import APP_NAME, VERSION
from meadowpy.resources.resource_loader import (
    get_icon_path,
    run_button_accent_hex,
    theme_is_dark,
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


class _WelcomeHeroWidget(QWidget):
    """Paint the welcome-page brand block as a single stable hero widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_dark = False
        self._is_high_contrast = False
        self._palette = {
            "background": "#FFFFFF",
            "text": "#273026",
            "muted": "#7D857F",
            "accent": "#4CAF50",
        }
        self._icon_size = 92
        self._icon_radius = 22
        self._icon = QPixmap()

        icon_path = get_icon_path("meadowpy_256") or get_icon_path("meadowpy")
        if icon_path:
            self._icon = _rounded_pixmap(
                QPixmap(icon_path),
                self._icon_size,
                self._icon_radius,
            )

        self._title_font = QFont("Segoe UI", 1)
        self._title_font.setPixelSize(40)
        self._title_font.setBold(True)

        self._subtitle_font = QFont("Segoe UI", 1)
        self._subtitle_font.setPixelSize(15)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(238)

    def apply_theme(
        self,
        theme_name: str,
        custom_base: str = "dark",
        custom_accent: str | None = None,
    ) -> None:
        """Refresh the hero colors to match the active MeadowPy theme."""
        self._is_dark = theme_is_dark(theme_name, custom_base)
        self._is_high_contrast = theme_is_high_contrast(theme_name)
        accent = run_button_accent_hex(theme_name, custom_accent)

        if self._is_high_contrast:
            self._palette = {
                "background": "#000000",
                "text": "#FFFFFF",
                "muted": "#D7D7D7",
                "accent": "#FFFFFF",
            }
        elif self._is_dark:
            self._palette = {
                "background": "#1E1E1E",
                "text": "#F6FAF5",
                "muted": "#98A39B",
                "accent": accent,
            }
        else:
            self._palette = {
                "background": "#FFFFFF",
                "text": "#273026",
                "muted": "#7D857F",
                "accent": accent,
            }

        self.update()

    def paintEvent(self, event) -> None:
        """Paint the icon halo, split-color title, and subtitle."""
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        painter.fillRect(self.rect(), QColor(self._palette["background"]))
        icon_rect = self._paint_icon(painter)
        title_bottom = self._paint_title(painter, int(icon_rect.bottom()) + 30)
        self._paint_subtitle(painter, title_bottom + 12)
        painter.end()

    def _paint_icon(self, painter: QPainter) -> QRectF:
        """Paint the welcome icon with the same halo language as About."""
        icon_left = (self.width() - self._icon_size) / 2
        icon_top = 18 if self._is_high_contrast else 20
        icon_rect = QRectF(icon_left, icon_top, self._icon_size, self._icon_size)

        glow_color = QColor(self._palette["accent"])
        max_expand = 10 if self._is_high_contrast else 16
        glow_steps = 8 if self._is_high_contrast else 12
        max_alpha = 10 if self._is_high_contrast else 18

        for step in range(glow_steps, 0, -1):
            distance = step / glow_steps
            expand = 2 + (max_expand * distance)
            alpha = max(1, round(3 + (max_alpha * (1.0 - distance))))
            layer_color = QColor(glow_color)
            layer_color.setAlpha(alpha)
            layer_rect = icon_rect.adjusted(-expand, -expand, expand, expand)
            layer_radius = self._icon_radius + expand
            layer_path = QPainterPath()
            layer_path.addRoundedRect(layer_rect, layer_radius, layer_radius)
            painter.fillPath(layer_path, layer_color)

        inner_glow = QColor(glow_color)
        inner_glow.setAlpha(14 if self._is_high_contrast else 24)
        inner_rect = icon_rect.adjusted(-3, -3, 3, 3)
        inner_path = QPainterPath()
        inner_path.addRoundedRect(
            inner_rect,
            self._icon_radius + 3,
            self._icon_radius + 3,
        )
        painter.fillPath(inner_path, inner_glow)

        if not self._icon.isNull():
            painter.drawPixmap(int(icon_rect.x()), int(icon_rect.y()), self._icon)

        return icon_rect

    def _paint_title(self, painter: QPainter, top: int) -> int:
        """Paint a MeadowPy title with an accent-colored ``Py`` suffix."""
        base = APP_NAME[:-2] if APP_NAME.endswith("Py") else APP_NAME
        suffix = APP_NAME[-2:] if APP_NAME.endswith("Py") else ""

        painter.setFont(self._title_font)
        fm = QFontMetrics(self._title_font)
        total_width = fm.horizontalAdvance(base + suffix)
        base_width = fm.horizontalAdvance(base)
        baseline = top + fm.ascent()
        start_x = int((self.width() - total_width) / 2)

        painter.setPen(QColor(self._palette["text"]))
        painter.drawText(start_x, baseline, base)
        painter.setPen(QColor(self._palette["accent"]))
        painter.drawText(start_x + base_width, baseline, suffix)
        return top + fm.height()

    def _paint_subtitle(self, painter: QPainter, top: int) -> None:
        """Paint the welcome subtitle and current version."""
        painter.setFont(self._subtitle_font)
        painter.setPen(QColor(self._palette["muted"]))
        rect = QRectF(48, top, self.width() - 96, 28)
        painter.drawText(
            rect,
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
            f"A beginner-friendly Python IDE  ·  v{VERSION}",
        )

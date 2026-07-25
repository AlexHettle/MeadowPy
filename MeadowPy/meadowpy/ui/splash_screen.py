"""Custom splash screen shown while MeadowPy starts."""

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from meadowpy.resources.resource_loader import get_icon_path


class LoadingDotsWidget(QWidget):
    """Simple animated loading dots for the splash screen."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._active_index = 0
        self._timer = QTimer(self)
        self._timer.setInterval(260)
        self._timer.timeout.connect(self._advance)
        self._timer.start()
        self.setFixedSize(44, 14)

    def _advance(self) -> None:
        self._active_index = (self._active_index + 1) % 3
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        diameter = 10
        gap = 7
        total_width = (diameter * 3) + (gap * 2)
        start_x = (self.width() - total_width) / 2
        y = (self.height() - diameter) / 2

        for index in range(3):
            color = QColor("#63D468")
            if index == self._active_index:
                color.setAlpha(255)
            elif index == (self._active_index - 1) % 3:
                color.setAlpha(180)
            else:
                color.setAlpha(90)

            painter.setBrush(color)
            x = start_x + index * (diameter + gap)
            painter.drawEllipse(QRectF(x, y, diameter, diameter))


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


class SplashIconWidget(QWidget):
    """Centered app icon with the About dialog's soft green halo."""

    def __init__(self, icon_pixmap: QPixmap, parent: QWidget | None = None):
        super().__init__(parent)
        self._icon = _rounded_pixmap(icon_pixmap, 118, 26)
        self.setFixedSize(168, 150)

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        icon_rect = QRectF(
            (self.width() - self._icon.width()) / 2,
            16,
            self._icon.width(),
            self._icon.height(),
        )
        icon_path = QPainterPath()
        icon_path.addRoundedRect(icon_rect, 26, 26)
        glow_color = QColor("#63D468")
        for step in range(12, 0, -1):
            distance = step / 12
            expand = 2 + (18 * distance)
            alpha = max(1, round(2 + (16 * (1.0 - distance))))
            layer_color = QColor(glow_color)
            layer_color.setAlpha(alpha)
            layer_rect = icon_rect.adjusted(-expand, -expand, expand, expand)
            layer_path = QPainterPath()
            layer_path.addRoundedRect(
                layer_rect,
                26 + expand,
                26 + expand,
            )
            painter.fillPath(layer_path, layer_color)

        painter.fillPath(icon_path, QColor("#020604"))

        if not self._icon.isNull():
            painter.drawPixmap(
                int(icon_rect.x()),
                int(icon_rect.y()),
                self._icon,
            )
        painter.end()


class SplashFooterRow(QWidget):
    """Footer row with centered loading status and right-aligned version."""

    def __init__(
        self,
        status_label: QLabel,
        version_label: QLabel,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._status_label = status_label
        self._version_label = version_label
        self.setFixedHeight(44)

        self._loading_group = QWidget(self)
        loading_layout = QHBoxLayout(self._loading_group)
        loading_layout.setContentsMargins(0, 0, 0, 0)
        loading_layout.setSpacing(14)
        loading_layout.addWidget(LoadingDotsWidget(self._loading_group))

        self._status_label.setParent(self._loading_group)
        loading_layout.addWidget(self._status_label)
        self._version_label.setParent(self)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)

        loading_size = self._loading_group.sizeHint()
        version_size = self._version_label.sizeHint()

        version_x = self.width() - version_size.width()

        self._loading_group.setGeometry(
            0,
            (self.height() - loading_size.height()) // 2,
            loading_size.width(),
            loading_size.height(),
        )
        self._version_label.setGeometry(
            version_x,
            (self.height() - version_size.height()) // 2,
            version_size.width(),
            version_size.height(),
        )


class MeadowPySplashScreen(QWidget):
    """Frameless splash screen styled after MeadowPy's branding."""

    def __init__(
        self,
        app_icon: QIcon | None,
        version: str,
        parent: QWidget | None = None,
    ):
        flags = (
            Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        super().__init__(parent, flags)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(820, 510)
        self.setWindowTitle("MeadowPy")
        if app_icon is not None and not app_icon.isNull():
            self.setWindowIcon(app_icon)

        self._status_label = QLabel("Initializing...", self)
        self._version_label = QLabel(f"v{version}", self)
        self._build_ui(app_icon)

    def _build_ui(self, app_icon: QIcon | None) -> None:
        self.setStyleSheet(
            """
            #splashTitle {
                color: #F6FAF5;
                background: transparent;
            }
            #splashSubtitle {
                color: #97A39A;
                background: transparent;
                font-weight: 700;
            }
            #splashStatus {
                color: #97A39A;
                background: transparent;
            }
            #splashVersion {
                color: #F6FAF5;
                background-color: rgba(99, 212, 104, 22);
                border: 1px solid rgba(99, 212, 104, 96);
                border-radius: 20px;
                padding: 8px 22px;
            }
            """
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(56, 68, 56, 34)
        root_layout.setSpacing(0)

        hero = QWidget(self)
        hero.setFixedWidth(640)
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(0, 0, 0, 0)
        hero_layout.setSpacing(0)

        icon_widget = SplashIconWidget(self._icon_pixmap(app_icon), hero)
        hero_layout.addWidget(
            icon_widget,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        hero_layout.addSpacing(10)

        title_label = QLabel(
            '<span style="color:#F3F6F1;">Meadow</span>'
            '<span style="color:#63D468;">Py</span>',
            hero,
        )
        title_label.setObjectName("splashTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont("Segoe UI", 36)
        title_font.setWeight(QFont.Weight.Bold)
        title_label.setFont(title_font)
        hero_layout.addWidget(title_label)

        hero_layout.addSpacing(12)

        subtitle_label = QLabel(
            "A beginner-friendly Python IDE with AI assistance.",
            hero,
        )
        subtitle_label.setObjectName("splashSubtitle")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_font = QFont("Segoe UI", 15)
        subtitle_font.setWeight(QFont.Weight.DemiBold)
        subtitle_label.setFont(subtitle_font)
        hero_layout.addWidget(subtitle_label)

        root_layout.addWidget(
            hero,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        root_layout.addSpacing(46)

        self._version_label.setObjectName("splashVersion")
        self._version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_font = QFont("Segoe UI", 14)
        version_font.setWeight(QFont.Weight.Bold)
        self._version_label.setFont(version_font)

        self._status_label.setObjectName("splashStatus")
        status_font = QFont("Segoe UI", 13)
        self._status_label.setFont(status_font)
        self._status_label.setMinimumWidth(190)

        root_layout.addStretch(1)

        footer_row = SplashFooterRow(
            self._status_label,
            self._version_label,
            self,
        )
        root_layout.addWidget(footer_row)

    def _icon_pixmap(self, app_icon: QIcon | None) -> QPixmap:
        icon_path = get_icon_path("meadowpy_256")
        pixmap = QPixmap(icon_path) if icon_path else QPixmap()
        if pixmap.isNull() and app_icon is not None and not app_icon.isNull():
            pixmap = app_icon.pixmap(118, 118)
        if pixmap.isNull():
            return QPixmap()
        return pixmap.scaled(
            118,
            118,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def set_status_text(self, text: str) -> None:
        """Update the loading status displayed on the splash screen."""
        self._status_label.setText(text)

    def center_on_screen(self) -> None:
        """Center the splash screen on the primary screen."""
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        self.move(
            geometry.center().x() - self.width() // 2,
            geometry.center().y() - self.height() // 2,
        )

    def showEvent(self, event) -> None:  # noqa: N802
        self.center_on_screen()
        super().showEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        outer_rect = QRectF(self.rect()).adjusted(6, 6, -6, -6)
        background_path = QPainterPath()
        background_path.addRoundedRect(outer_rect, 10, 10)

        painter.fillPath(background_path, QColor("#040805"))

        painter.save()
        painter.setClipPath(background_path)

        self._paint_glow(
            painter,
            QPointF(outer_rect.center().x(), outer_rect.bottom() - 10),
            max(outer_rect.width() * 0.58, outer_rect.height() * 0.86),
            QColor(99, 212, 104, 34),
            QColor(99, 212, 104, 0),
        )
        self._paint_glow(
            painter,
            QPointF(outer_rect.center().x(), outer_rect.top() + 112),
            outer_rect.width() * 0.20,
            QColor(99, 212, 104, 22),
            QColor(99, 212, 104, 0),
        )

        painter.restore()

        border_pen = QPen(QColor(122, 176, 124, 68), 1.0)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(background_path)

    def _paint_glow(
        self,
        painter: QPainter,
        center: QPointF,
        radius: float,
        inner_color: QColor,
        outer_color: QColor,
    ) -> None:
        gradient = QRadialGradient(center, radius)
        gradient.setColorAt(0.0, inner_color)
        gradient.setColorAt(
            0.45,
            QColor(
                inner_color.red(),
                inner_color.green(),
                inner_color.blue(),
                max(inner_color.alpha() // 2, 1),
            ),
        )
        gradient.setColorAt(1.0, outer_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(center, radius, radius)

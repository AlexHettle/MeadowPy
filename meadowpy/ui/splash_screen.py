"""Custom splash screen shown while MeadowPy starts."""

from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


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
            #splashBadge {
                background-color: rgba(3, 16, 8, 228);
                border: 1px solid rgba(99, 212, 104, 35);
                border-radius: 34px;
            }
            #splashTitle {
                color: #F3F6F1;
                background: transparent;
            }
            #splashSubtitle {
                color: rgba(201, 212, 202, 168);
                background: transparent;
            }
            #splashStatus {
                color: rgba(198, 215, 201, 176);
                background: transparent;
            }
            #splashVersion {
                color: rgba(194, 205, 196, 172);
                background: transparent;
            }
            """
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(56, 42, 56, 30)
        root_layout.setSpacing(0)

        root_layout.addStretch(3)

        badge = QFrame(self)
        badge.setObjectName("splashBadge")
        badge.setFixedSize(144, 144)

        badge_layout = QVBoxLayout(badge)
        badge_layout.setContentsMargins(24, 24, 24, 24)
        badge_layout.setSpacing(0)

        icon_label = QLabel(badge)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setPixmap(self._icon_pixmap(app_icon))
        badge_layout.addWidget(icon_label)

        root_layout.addWidget(
            badge,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        root_layout.addSpacing(28)

        title_label = QLabel(
            '<span style="color:#F3F6F1;">Meadow</span>'
            '<span style="color:#63D468;">Py</span>',
            self,
        )
        title_label.setObjectName("splashTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont("Segoe UI", 34)
        title_font.setWeight(QFont.Weight.Bold)
        title_label.setFont(title_font)
        root_layout.addWidget(title_label)

        root_layout.addSpacing(10)

        subtitle_label = QLabel(
            "A beginner-friendly Python IDE with AI assistance.",
            self,
        )
        subtitle_label.setObjectName("splashSubtitle")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_font = QFont("Segoe UI", 15)
        subtitle_label.setFont(subtitle_font)
        root_layout.addWidget(subtitle_label)

        root_layout.addSpacing(42)

        loading_row = QWidget(self)
        loading_layout = QHBoxLayout(loading_row)
        loading_layout.setContentsMargins(0, 0, 0, 0)
        loading_layout.setSpacing(14)

        loading_dots = LoadingDotsWidget(loading_row)
        loading_layout.addWidget(loading_dots)

        self._status_label.setObjectName("splashStatus")
        status_font = QFont("Consolas", 13)
        self._status_label.setFont(status_font)
        loading_layout.addWidget(self._status_label)

        root_layout.addWidget(
            loading_row,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        root_layout.addStretch(4)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.addStretch()

        self._version_label.setObjectName("splashVersion")
        version_font = QFont("Segoe UI", 11)
        version_font.setWeight(QFont.Weight.DemiBold)
        self._version_label.setFont(version_font)
        footer.addWidget(self._version_label)

        root_layout.addLayout(footer)

    def _icon_pixmap(self, app_icon: QIcon | None) -> QPixmap:
        if app_icon is not None and not app_icon.isNull():
            icon_pixmap = app_icon.pixmap(96, 96)
            if not icon_pixmap.isNull():
                return icon_pixmap

        icon_path = (
            Path(__file__).resolve().parents[1]
            / "resources"
            / "icons"
            / "meadowpy_256.png"
        )
        pixmap = QPixmap(str(icon_path))
        if pixmap.isNull():
            return QPixmap()
        return pixmap.scaled(
            96,
            96,
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
        background_path.addRoundedRect(outer_rect, 26, 26)

        painter.fillPath(background_path, QColor(4, 10, 6, 242))

        painter.save()
        painter.setClipPath(background_path)

        base_gradient = QLinearGradient(
            outer_rect.topLeft(),
            outer_rect.bottomRight(),
        )
        base_gradient.setColorAt(0.0, QColor("#040806"))
        base_gradient.setColorAt(0.45, QColor("#071109"))
        base_gradient.setColorAt(1.0, QColor("#071A0B"))
        painter.fillPath(background_path, base_gradient)

        self._paint_glow(
            painter,
            QPointF(outer_rect.left() + outer_rect.width() * 0.18, outer_rect.bottom() - 36),
            outer_rect.width() * 0.46,
            QColor(20, 124, 35, 150),
            QColor(12, 72, 22, 0),
        )
        self._paint_glow(
            painter,
            QPointF(outer_rect.right() - 28, outer_rect.top() + 26),
            outer_rect.width() * 0.34,
            QColor(18, 100, 40, 88),
            QColor(18, 100, 40, 0),
        )
        self._paint_glow(
            painter,
            QPointF(outer_rect.center().x(), outer_rect.top() + outer_rect.height() * 0.34),
            outer_rect.width() * 0.18,
            QColor(87, 212, 109, 90),
            QColor(87, 212, 109, 0),
        )

        painter.restore()

        border_pen = QPen(QColor(122, 176, 124, 42), 1.0)
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
        gradient.setColorAt(0.45, QColor(inner_color.red(), inner_color.green(), inner_color.blue(), max(inner_color.alpha() // 2, 1)))
        gradient.setColorAt(1.0, outer_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(center, radius, radius)

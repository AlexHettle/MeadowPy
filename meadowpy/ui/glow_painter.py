"""Shared radial glow painter for hoverable controls."""

from PyQt6.QtCore import QEvent, QObject, QPointF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QRadialGradient
from PyQt6.QtWidgets import QApplication, QWidget


class HeaderGlowPainter(QObject):
    """Paints radial glow effects on a surface behind registered buttons."""

    HOVER_RADIUS = 12
    HOVER_ALPHA = 55
    PRESS_RADIUS = 16
    PRESS_ALPHA = 90

    def __init__(self, surface: QWidget, parent=None):
        super().__init__(parent)
        self._surface = surface
        self._entries: list[dict] = []
        surface.installEventFilter(self)

    def add_button(self, button, color: QColor) -> None:
        entry = {"btn": button, "color": QColor(color), "state": "idle"}
        self._entries.append(entry)
        button.installEventFilter(self)

    def set_button_color(self, button, color: QColor) -> None:
        """Update the glow color for an already-registered button."""
        for entry in self._entries:
            if entry["btn"] is button:
                entry["color"] = QColor(color)
                self._surface.update()
                return

    def eventFilter(self, obj, event):
        etype = event.type()

        for entry in self._entries:
            if obj is entry["btn"]:
                if etype == QEvent.Type.HoverEnter and obj.isEnabled():
                    entry["state"] = "hover"
                    self._surface.update()
                elif etype == QEvent.Type.HoverLeave:
                    entry["state"] = "idle"
                    self._surface.update()
                elif etype == QEvent.Type.MouseButtonPress and obj.isEnabled():
                    entry["state"] = "press"
                    self._surface.update()
                elif etype == QEvent.Type.MouseButtonRelease:
                    entry["state"] = (
                        "hover" if obj.underMouse() and obj.isEnabled()
                        else "idle"
                    )
                    self._surface.update()
                return False

        if obj is self._surface and etype == QEvent.Type.Paint:
            obj.removeEventFilter(self)
            QApplication.sendEvent(obj, event)
            obj.installEventFilter(self)

            painter = QPainter(obj)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            for entry in self._entries:
                if entry["state"] == "idle":
                    continue
                btn = entry["btn"]
                if not btn.isEnabled():
                    entry["state"] = "idle"
                    continue
                center = QPointF(btn.geometry().center())
                if entry["state"] == "press":
                    radius = self.PRESS_RADIUS
                    alpha = self.PRESS_ALPHA
                else:
                    radius = self.HOVER_RADIUS
                    alpha = self.HOVER_ALPHA

                base = QColor(entry["color"])
                grad = QRadialGradient(center, radius)
                c0 = QColor(base)
                c0.setAlpha(alpha)
                c1 = QColor(base)
                c1.setAlpha(int(alpha * 0.55))
                c2 = QColor(base)
                c2.setAlpha(int(alpha * 0.2))
                c3 = QColor(base)
                c3.setAlpha(0)
                grad.setColorAt(0.0, c0)
                grad.setColorAt(0.35, c1)
                grad.setColorAt(0.65, c2)
                grad.setColorAt(1.0, c3)

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(grad))
                painter.drawEllipse(center, radius, radius)
            painter.end()
            return True

        return False

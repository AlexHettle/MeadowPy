"""Toolbar construction."""

from PyQt6.QtCore import QPointF, QSize, Qt, QEvent, QObject
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFontMetrics,
    QIcon,
    QPainter,
    QPainterPath,
    QRadialGradient,
)
from PyQt6.QtWidgets import QApplication, QToolBar, QToolButton, QWidget

from meadowpy.resources.resource_loader import (
    load_themed_icon,
    theme_is_high_contrast,
)


class RunFileButton(QToolButton):
    """Fixed-size toolbar run button that elides long target names."""

    _WIDTH = 190
    _HEIGHT = 32
    _HORIZONTAL_PAD = 12
    _RIGHT_PAD = 8
    _ICON_SIZE = 12
    _ICON_GAP = 8
    _CONTENT_X_OFFSET = -2
    _ICON_Y_OFFSET = 1

    def __init__(self, action, parent=None):
        super().__init__(parent)
        self.setObjectName("runButton")
        self.setDefaultAction(action)
        self.setFixedSize(self._WIDTH, self._HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._label_font = self.font()
        self._apply_label_font()
        self._target_name = "File"
        self._accent = QColor("#2F7A44")
        action.changed.connect(self._sync_from_action)
        self._sync_from_action()

    def _apply_label_font(self) -> None:
        self._label_font = self.font()
        self._label_font.setPixelSize(13)
        self._label_font.setBold(True)

    def set_target_name(self, name: str | None) -> None:
        self._target_name = (name or "File").strip() or "File"
        self._sync_text()
        self.update()

    def set_accent_color(self, hex_color: str) -> None:
        color = QColor(hex_color)
        if color.isValid():
            self._accent = color
            self.update()

    def displayed_text(self) -> str:
        return self._elide_text(self._full_label(), self._available_text_width())

    def event(self, event) -> bool:
        result = super().event(event)
        if event.type() in {
            QEvent.Type.StyleChange,
            QEvent.Type.ApplicationFontChange,
            QEvent.Type.FontChange,
        }:
            self._apply_label_font()
            self.update()
        return result

    def _sync_from_action(self) -> None:
        action = self.defaultAction()
        if action is None:
            return
        self.setEnabled(action.isEnabled())
        self.setToolTip(action.toolTip())
        self._sync_text()
        self.update()

    def _sync_text(self) -> None:
        label = self._full_label()
        self.setText(label)
        self.setAccessibleName(label)

    def _verb(self) -> str:
        action = self.defaultAction()
        tooltip = action.toolTip() if action is not None else ""
        if tooltip.startswith("Continue"):
            return "Continue"
        return "Run"

    def _full_label(self) -> str:
        verb = self._verb()
        if verb == "Continue":
            return verb
        return f"{verb} {self._target_name}"

    def _available_text_width(self) -> int:
        return (
            self.width()
            - (self._HORIZONTAL_PAD * 2)
            - self._ICON_SIZE
            - self._ICON_GAP
        )

    def _elide_text(self, text: str, max_width: int) -> str:
        metrics = QFontMetrics(self._label_font)
        if metrics.horizontalAdvance(text) <= max_width:
            return text

        ellipsis = "..."
        if max_width <= metrics.horizontalAdvance(ellipsis):
            return ellipsis

        low, high = 0, len(text)
        while low < high:
            mid = (low + high + 1) // 2
            candidate = f"{text[:mid].rstrip()}{ellipsis}"
            if metrics.horizontalAdvance(candidate) <= max_width:
                low = mid
            else:
                high = mid - 1
        return f"{text[:low].rstrip()}{ellipsis}" if low else ellipsis

    def _foreground_for(self, background: QColor) -> QColor:
        brightness = (
            background.red() * 0.299
            + background.green() * 0.587
            + background.blue() * 0.114
        )
        return QColor("#000000") if brightness > 180 else QColor("#FFFFFF")

    def paintEvent(self, event) -> None:  # noqa: N802
        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self._label_font)

        bg = QColor(self._accent)
        if not self.isEnabled():
            bg = QColor("#555555")
            fg = QColor("#888888")
        elif self.isDown():
            bg = bg.darker(125)
            fg = self._foreground_for(bg)
        elif self.underMouse():
            bg = bg.darker(112)
            fg = self._foreground_for(bg)
        else:
            fg = self._foreground_for(bg)

        rect = self.rect()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 6, 6)

        center_y = self.rect().center().y()
        label = self.displayed_text()
        label_width = QFontMetrics(self._label_font).horizontalAdvance(label)
        content_width = self._ICON_SIZE + self._ICON_GAP + label_width
        icon_left = int((self.width() - content_width) / 2) + self._CONTENT_X_OFFSET
        icon_half = self._ICON_SIZE // 2
        icon_top = center_y - icon_half + self._ICON_Y_OFFSET
        icon_bottom = center_y + icon_half + self._ICON_Y_OFFSET
        icon_center_y = center_y + self._ICON_Y_OFFSET
        icon_tip = icon_left + self._ICON_SIZE
        triangle = QPainterPath()
        triangle.moveTo(icon_left + 2.2, icon_top + 1.0)
        triangle.cubicTo(
            icon_left + 0.8,
            icon_top + 0.1,
            icon_left,
            icon_top + 1.1,
            icon_left,
            icon_top + 2.8,
        )
        triangle.lineTo(icon_left, icon_bottom - 2.8)
        triangle.cubicTo(
            icon_left,
            icon_bottom - 1.1,
            icon_left + 0.8,
            icon_bottom - 0.1,
            icon_left + 2.2,
            icon_bottom - 1.0,
        )
        triangle.lineTo(icon_tip - 3.0, icon_center_y + 1.8)
        triangle.cubicTo(
            icon_tip - 0.5,
            icon_center_y + 0.6,
            icon_tip - 0.5,
            icon_center_y - 0.6,
            icon_tip - 3.0,
            icon_center_y - 1.8,
        )
        triangle.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fg)
        painter.drawPath(triangle)

        text_left = icon_left + self._ICON_SIZE + self._ICON_GAP
        text_rect = self.rect().adjusted(text_left, 0, -self._RIGHT_PAD, 0)
        painter.setPen(fg)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            label,
        )
        painter.end()


class ToolbarGlowPainter(QObject):
    """Paints radial glow effects on a toolbar behind registered buttons.

    The glow is drawn on the *toolbar* surface (not on the button) so it
    can radiate freely beyond the button boundaries.  Each registered
    button gets its own colour.

    Re-usable: call ``add_button(btn, color)`` for every button that
    should glow, then the filter handles hover / press tracking and
    toolbar repaint automatically.
    """

    HOVER_RADIUS = 16
    HOVER_ALPHA = 55
    PRESS_RADIUS = 20
    PRESS_ALPHA = 90

    def __init__(self, toolbar: QToolBar, parent=None):
        super().__init__(parent)
        self._toolbar = toolbar
        self._entries: list[dict] = []
        toolbar.installEventFilter(self)

    def add_button(self, button, color: QColor) -> None:
        entry = {"btn": button, "color": QColor(color), "state": "idle"}
        self._entries.append(entry)
        button.installEventFilter(self)

    def set_button_color(self, button, color: QColor) -> None:
        """Update the glow color for an already-registered button."""
        for entry in self._entries:
            if entry["btn"] is button:
                entry["color"] = QColor(color)
                self._toolbar.update()
                return

    # ── event filter ────────────────────────────────────────────
    def eventFilter(self, obj, event):
        etype = event.type()

        # --- button hover / press tracking ---
        for entry in self._entries:
            if obj is entry["btn"]:
                if etype == QEvent.Type.HoverEnter and obj.isEnabled():
                    entry["state"] = "hover"
                    self._toolbar.update()
                elif etype == QEvent.Type.HoverLeave:
                    entry["state"] = "idle"
                    self._toolbar.update()
                elif etype == QEvent.Type.MouseButtonPress and obj.isEnabled():
                    entry["state"] = "press"
                    self._toolbar.update()
                elif etype == QEvent.Type.MouseButtonRelease:
                    entry["state"] = (
                        "hover" if obj.underMouse() and obj.isEnabled()
                        else "idle"
                    )
                    self._toolbar.update()
                return False  # never consume button events

        # --- toolbar paint: draw glows after normal paint ---
        if obj is self._toolbar and etype == QEvent.Type.Paint:
            # Let the toolbar paint normally first
            obj.removeEventFilter(self)
            QApplication.sendEvent(obj, event)
            obj.installEventFilter(self)

            # Paint radial glows behind hovered / pressed buttons
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

                # Smooth exponential falloff with multiple stops
                grad = QRadialGradient(center, radius)
                c0 = QColor(base); c0.setAlpha(alpha)
                c1 = QColor(base); c1.setAlpha(int(alpha * 0.55))
                c2 = QColor(base); c2.setAlpha(int(alpha * 0.2))
                c3 = QColor(base); c3.setAlpha(0)
                grad.setColorAt(0.0, c0)
                grad.setColorAt(0.35, c1)
                grad.setColorAt(0.65, c2)
                grad.setColorAt(1.0, c3)

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(grad))
                painter.drawEllipse(center, radius, radius)
            painter.end()
            return True  # we already sent the real paint event

        return False


class ToolBarBuilder:
    """Builds the main toolbar with icon buttons."""

    def __init__(self, main_window):
        self._window = main_window

    def build(self) -> QToolBar:
        """Build and return the main toolbar."""
        toolbar = QToolBar("Main Toolbar", self._window)
        toolbar.setObjectName("MainToolBar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

        self._add(toolbar, "new", "Create a new blank file (Ctrl+N)", self._window.action_new_file)
        self._add(toolbar, "open_file", "Open an existing file (Ctrl+O)", self._window.action_open_file)
        self._add(toolbar, "save", "Save the current file (Ctrl+S)", self._window.action_save)
        toolbar.addSeparator()
        self._add(toolbar, "undo", "Undo last change (Ctrl+Z)", lambda: self._editor_call("undo"))
        self._add(toolbar, "redo", "Redo undone change (Ctrl+Y)", lambda: self._editor_call("redo"))
        toolbar.addSeparator()
        self._add(toolbar, "find", "Find text in the current file (Ctrl+F)", self._window.action_toggle_find)
        toolbar.addSeparator()

        # Run/Stop/Debug use shared QActions from main_window so enable/disable
        # stays in sync across menu and toolbar.
        run_left_margin = QWidget(toolbar)
        run_left_margin.setFixedWidth(4)
        toolbar.addWidget(run_left_margin)
        run_btn = RunFileButton(self._window._run_action, toolbar)
        toolbar.addWidget(run_btn)
        toolbar.addAction(self._window._stop_action)
        toolbar.addAction(self._window._debug_action)

        # Set object names so QSS can apply per-button colored tint
        stop_btn = toolbar.widgetForAction(self._window._stop_action)
        debug_btn = toolbar.widgetForAction(self._window._debug_action)
        stop_btn.setObjectName("stopButton")
        debug_btn.setObjectName("debugButton")

        # Debug step actions — hidden until a debug session starts
        toolbar.addSeparator()
        self._debug_separator = toolbar.actions()[-1]  # the separator we just added
        self._debug_separator.setVisible(False)

        self._window._step_over_action = toolbar.addAction(
            self._icon("step_over"), "Step Over"
        )
        self._window._step_over_action.setToolTip("Step Over (F10)")
        self._window._step_over_action.setVisible(False)

        self._window._step_into_action = toolbar.addAction(
            self._icon("step_into"), "Step Into"
        )
        self._window._step_into_action.setToolTip("Step Into (F11)")
        self._window._step_into_action.setVisible(False)

        self._window._step_out_action = toolbar.addAction(
            self._icon("step_out"), "Step Out"
        )
        self._window._step_out_action.setToolTip("Step Out (Shift+F11)")
        self._window._step_out_action.setVisible(False)

        # Glow painter — draws radial gradients behind the icon-only controls.
        # In HC mode collapse glows onto pure white so the toolbar is fully
        # monochromatic (no chroma anywhere).
        is_hc = theme_is_high_contrast(self._window._settings.get("editor.theme"))
        stop_glow = QColor("#FFFFFF") if is_hc else QColor("#E51400")
        debug_glow = QColor("#FFFFFF") if is_hc else QColor("#FF9800")
        self._glow = ToolbarGlowPainter(toolbar, toolbar)
        self._glow.add_button(stop_btn, stop_glow)
        self._glow.add_button(debug_btn, debug_glow)
        # Remember the run button so its fill can be re-tinted when the user
        # switches to a custom theme with a different accent colour.
        self._run_btn = run_btn
        self.update_run_file_label(self._window._tab_manager.current_editor())

        self._window._debug_separator = self._debug_separator
        self._window.addToolBar(toolbar)
        return toolbar

    def update_accent_color(self, hex_color: str) -> None:
        """Refresh the Run button fill color (called on theme change)."""
        if getattr(self, "_run_btn", None):
            self._run_btn.set_accent_color(hex_color)

    def update_run_file_label(self, editor=None) -> None:
        """Update the fixed Run button label from the active editor."""
        run_btn = getattr(self, "_run_btn", None)
        if run_btn is None:
            return
        display_name = getattr(editor, "display_name", None)
        run_btn.set_target_name(display_name or "File")

    def _add(self, toolbar: QToolBar, icon_name: str, tooltip: str, callback) -> None:
        action = toolbar.addAction(self._icon(icon_name), tooltip.split(" (")[0], callback)
        action.setToolTip(tooltip)

    def _icon(self, name: str) -> QIcon:
        # Route through the themed loader so colorful SVGs (run/debug/stop/
        # restart) get rewritten to the HC accent when High Contrast is on.
        theme_name = self._window._settings.get("editor.theme") or ""
        return load_themed_icon(name, theme_name)

    def _editor_call(self, method: str) -> None:
        editor = self._window._tab_manager.current_editor()
        if editor and hasattr(editor, method):
            getattr(editor, method)()

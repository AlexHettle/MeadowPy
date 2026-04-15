"""Toolbar construction."""

from PyQt6.QtCore import QSize, Qt, QEvent, QObject, QPointF
from PyQt6.QtGui import QBrush, QColor, QIcon, QPainter, QRadialGradient
from PyQt6.QtWidgets import QApplication, QToolBar

from meadowpy.resources.resource_loader import get_icon_path


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
        # stays in sync across menu, toolbar, and output panel.
        toolbar.addAction(self._window._run_action)
        toolbar.addAction(self._window._stop_action)
        toolbar.addAction(self._window._debug_action)

        # Set object names so QSS can apply per-button colored tint
        run_btn = toolbar.widgetForAction(self._window._run_action)
        stop_btn = toolbar.widgetForAction(self._window._stop_action)
        debug_btn = toolbar.widgetForAction(self._window._debug_action)
        run_btn.setObjectName("runButton")
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

        # Glow painter — draws radial gradients on the toolbar behind buttons
        self._glow = ToolbarGlowPainter(toolbar, toolbar)
        self._glow.add_button(run_btn, QColor("#4CAF50"))    # green
        self._glow.add_button(stop_btn, QColor("#E51400"))   # red
        self._glow.add_button(debug_btn, QColor("#FF9800"))  # orange
        # Remember the run button so its glow can be re-tinted when the
        # user switches to a custom theme with a different accent colour.
        self._run_btn = run_btn

        self._window._debug_separator = self._debug_separator
        self._window.addToolBar(toolbar)
        return toolbar

    def update_accent_color(self, hex_color: str) -> None:
        """Refresh the Run button's glow color (called on theme change)."""
        if getattr(self, "_run_btn", None) and getattr(self, "_glow", None):
            self._glow.set_button_color(self._run_btn, QColor(hex_color))

    def _add(self, toolbar: QToolBar, icon_name: str, tooltip: str, callback) -> None:
        action = toolbar.addAction(self._icon(icon_name), tooltip.split(" (")[0], callback)
        action.setToolTip(tooltip)

    def _icon(self, name: str) -> QIcon:
        path = get_icon_path(name)
        return QIcon(path) if path else QIcon()

    def _editor_call(self, method: str) -> None:
        editor = self._window._tab_manager.current_editor()
        if editor and hasattr(editor, method):
            getattr(editor, method)()

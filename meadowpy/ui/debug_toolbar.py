"""Debug toolbar — shown during active debug sessions."""

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QToolBar

from meadowpy.resources.resource_loader import get_icon_path


class DebugToolBar(QToolBar):
    """Toolbar with Step Over / Step Into / Step Out.

    Hidden by default, shown when a debug session is active.
    Continue is handled by the main toolbar's Run button (repurposed).
    """

    def __init__(self, main_window):
        super().__init__("Debug", main_window)
        self._window = main_window
        self.setObjectName("DebugToolBar")
        self.setMovable(False)
        self.setIconSize(QSize(20, 20))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

        self._build_actions()
        self.setVisible(False)  # hidden until debug starts

    def _build_actions(self) -> None:
        """Create all debug toolbar actions."""
        # Step Over (F10)
        self.step_over_action = QAction(
            self._icon("step_over"), "Step Over (F10)", self
        )
        self.step_over_action.setToolTip("Step Over (F10)")
        self.addAction(self.step_over_action)

        # Step Into (F11)
        self.step_into_action = QAction(
            self._icon("step_into"), "Step Into (F11)", self
        )
        self.step_into_action.setToolTip("Step Into (F11)")
        self.addAction(self.step_into_action)

        # Step Out (Shift+F11) — reuses step_into icon with visual difference
        self.step_out_action = QAction(
            self._icon("step_into"), "Step Out (Shift+F11)", self
        )
        self.step_out_action.setToolTip("Step Out (Shift+F11)")
        self.addAction(self.step_out_action)

    def set_paused(self, paused: bool) -> None:
        """Enable/disable step actions based on pause state."""
        self.step_over_action.setEnabled(paused)
        self.step_into_action.setEnabled(paused)
        self.step_out_action.setEnabled(paused)

    def _icon(self, name: str) -> QIcon:
        path = get_icon_path(name)
        return QIcon(path) if path else QIcon()

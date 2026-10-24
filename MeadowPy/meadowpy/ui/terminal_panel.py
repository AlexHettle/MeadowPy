"""Terminal panel - interactive shell dock."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from meadowpy.resources.theme_colors import theme_is_dark, theme_is_high_contrast
from meadowpy.ui.panel_title_bar import (
    configure_panel_title_bar,
    configure_panel_title_label,
)
from meadowpy.pyqtterm import Terminal

_TERMINAL_PANEL_DEFAULT_FONT_SIZE = 13
_TERMINAL_PANEL_SHELL_EXITED_MESSAGE = "[Shell exited. Press any key to start a new one.]"

# (foreground, background) of the terminal surface for each theme kind;
# these match the #terminalText colors in the theme stylesheets.
_TERMINAL_PANEL_LIGHT_COLORS = ("#1E1E1E", "#FFFFFF")
_TERMINAL_PANEL_DARK_COLORS = ("#CCCCCC", "#1E1E1E")
_TERMINAL_PANEL_HIGH_CONTRAST_COLORS = ("#FFFFFF", "#000000")


class TerminalPanel(QDockWidget):
    """Bottom dock panel for an interactive operating-system shell."""

    def __init__(self, parent=None, settings=None):
        super().__init__("Terminal", parent)
        self.setObjectName("TerminalPanel")
        self.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea
            | Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self._settings = settings
        self._working_directory = str(Path.home())
        self._stopping = False
        self._setup_ui()
        QApplication.instance().aboutToQuit.connect(self._mark_stopping)
        self.toggleViewAction().triggered.connect(self._on_toggle_triggered)

    def _setup_ui(self) -> None:
        title_bar = QFrame()
        title_bar.setObjectName("terminalTitleBar")
        title_bar.setFrameShape(QFrame.Shape.NoFrame)
        title_layout = QHBoxLayout(title_bar)
        configure_panel_title_bar(title_bar, title_layout, spacing=2)

        title_label = QLabel("Terminal")
        title_label.setObjectName("terminalTitleLabel")
        configure_panel_title_label(title_label)
        title_layout.addWidget(title_label, 0, Qt.AlignmentFlag.AlignVCenter)
        title_layout.addStretch()

        self.setTitleBarWidget(title_bar)
        self._title_bar = title_bar

        container = QFrame()
        container.setObjectName("terminalContainer")
        container.setFrameShape(QFrame.Shape.NoFrame)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._terminal_view = Terminal(
            fontsize=self._font_size_from_settings(),
            endmessage=_TERMINAL_PANEL_SHELL_EXITED_MESSAGE,
            cwd=self._working_directory,
        )
        self._terminal_view.setObjectName("terminalText")
        self._terminal_view.installEventFilter(self)
        self._terminal_view.stopped.connect(self._on_terminal_stopped)
        layout.addWidget(self._terminal_view)
        self.setWidget(container)
        self.refresh_theme()

    def _font_size_from_settings(self) -> int:
        size = None
        if self._settings is not None:
            size = self._settings.get("editor.font_size")
        return size or _TERMINAL_PANEL_DEFAULT_FONT_SIZE

    def set_working_directory(self, directory: str | None) -> None:
        """Start future shells in directory (home when empty).

        A shell that is already running keeps its own directory.
        """
        self._working_directory = directory or str(Path.home())
        self._terminal_view.setWorkingDirectory(self._working_directory)

    def update_font_size(self, size: int) -> None:
        """Apply the editor font size; the terminal's family never changes."""
        self._terminal_view.setTerminalFontSize(
            size or _TERMINAL_PANEL_DEFAULT_FONT_SIZE
        )

    def refresh_theme(self) -> None:
        """Recolor the terminal surface for the active theme."""
        theme_name = ""
        custom_base = "dark"
        if self._settings is not None:
            theme_name = self._settings.get("editor.theme") or ""
            custom_base = self._settings.get("editor.custom_theme.base") or "dark"
        if theme_is_high_contrast(theme_name):
            colors = _TERMINAL_PANEL_HIGH_CONTRAST_COLORS
        elif theme_is_dark(theme_name, custom_base):
            colors = _TERMINAL_PANEL_DARK_COLORS
        else:
            colors = _TERMINAL_PANEL_LIGHT_COLORS
        self._terminal_view.setDefaultColors(*colors)

    def focus_terminal(self) -> None:
        self._terminal_view.setFocus()

    def stop(self) -> None:
        """Kill the shell for good; called on main-window shutdown."""
        self._mark_stopping()
        self._terminal_view.stop()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        # The terminal claims every shortcut so Ctrl+letter reaches the
        # shell; let this panel's own toggle shortcut through so the
        # panel can still be hidden from the keyboard.
        if obj is self._terminal_view and event.type() == QEvent.Type.ShortcutOverride:
            if QKeySequence(event.keyCombination()) in self.toggleViewAction().shortcuts():
                return True
        return super().eventFilter(obj, event)

    def _mark_stopping(self) -> None:
        self._stopping = True

    def _on_toggle_triggered(self, checked: bool) -> None:
        if checked:
            QTimer.singleShot(0, self.focus_terminal)

    def _on_terminal_stopped(self) -> None:
        if not self._stopping:
            QTimer.singleShot(0, self._restart_shell)

    def _restart_shell(self) -> None:
        if not self._stopping:
            self._terminal_view.restart()

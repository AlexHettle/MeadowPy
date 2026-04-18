"""Tab manager for editor tabs."""

from pathlib import Path

from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QSize
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QTabWidget, QTabBar, QMessageBox, QToolButton

from meadowpy.core.settings import Settings
from meadowpy.editor.code_editor import CodeEditor
from meadowpy.resources.resource_loader import theme_is_dark
from meadowpy.ui.welcome_widget import WelcomeWidget


class _GradientTabBar(QTabBar):
    """Editor tab bar with a thin scroll indicator when tabs overflow."""

    _SCROLLBAR_H = 3  # height of the thin scrollbar

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self._settings = settings

    def minimumSizeHint(self) -> QSize:
        """Prevent the tab bar from forcing the layout wider."""
        hint = super().minimumSizeHint()
        hint.setWidth(0)
        return hint

    def paintEvent(self, event):
        super().paintEvent(event)
        self._paint_scroll_indicator()

    def _paint_scroll_indicator(self):
        """Paint a thin scrollbar at the bottom when tabs overflow."""
        if self.count() == 0:
            return

        first_rect = self.tabRect(0)
        last_rect = self.tabRect(self.count() - 1)
        total_width = last_rect.right() - first_rect.left()
        visible_width = self.width()

        if total_width <= visible_width:
            return  # all tabs fit, no scrollbar needed

        is_dark = theme_is_dark(
            self._settings.get("editor.theme") or "default_dark",
            self._settings.get("editor.custom_theme.base"),
        )

        h = self._SCROLLBAR_H
        bar_y = self.height() - h

        # Thumb proportional to visible / total
        thumb_w = max(20, int(visible_width * visible_width / total_width))

        # Position from scroll offset (first tab's left goes negative when scrolled)
        scroll_offset = -first_rect.left()
        max_scroll = total_width - visible_width
        scroll_pct = scroll_offset / max_scroll if max_scroll > 0 else 0
        thumb_x = int(scroll_pct * (visible_width - thumb_w))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        # Track
        track_color = QColor(60, 60, 60, 60) if is_dark else QColor(0, 0, 0, 30)
        painter.setBrush(track_color)
        painter.drawRoundedRect(0, bar_y, visible_width, h, 1, 1)

        # Thumb
        thumb_color = QColor(150, 150, 150, 160) if is_dark else QColor(100, 100, 100, 140)
        painter.setBrush(thumb_color)
        painter.drawRoundedRect(thumb_x, bar_y, thumb_w, h, 1, 1)

        painter.end()


class TabManager(QTabWidget):
    """Manages editor tabs. Each tab contains a CodeEditor."""

    tab_changed = pyqtSignal(object)  # emits CodeEditor or None

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._untitled_counter = 1

        # Use custom tab bar for gradient top border
        self.setTabBar(_GradientTabBar(settings, self))

        self.setTabsClosable(False)
        self.setMovable(True)
        self.setDocumentMode(True)
        self.setContentsMargins(0, 0, 0, 0)
        self.setUsesScrollButtons(True)

        self.currentChanged.connect(self._on_tab_changed)

    def new_tab(self, file_path: str | None = None, content: str = "") -> CodeEditor:
        """Create a new editor tab. Returns the editor."""
        editor = CodeEditor(self._settings, self)

        if file_path:
            editor.file_path = file_path
            editor.setText(content)
            editor.setModified(False)
            tab_title = Path(file_path).name
        else:
            editor._untitled_name = f"Untitled-{self._untitled_counter}"
            self._untitled_counter += 1
            tab_title = editor._untitled_name

        index = self.addTab(editor, tab_title)
        self._set_close_button(index, editor)
        self.setCurrentIndex(index)

        editor.modification_changed.connect(
            lambda modified, ed=editor: self._update_modified_indicator(ed, modified)
        )
        return editor

    def _close_btn_stylesheet(self, is_dark: bool) -> str:
        """QSS for the tab close button — circular hover pill."""
        idle_color = "#858585"
        hover_color = "#FFFFFF" if is_dark else "#1F1F1F"
        hover_bg = "rgba(255,255,255,0.12)" if is_dark else "rgba(0,0,0,0.08)"
        return (
            f"QToolButton {{ color: {idle_color}; font-size: 11px; font-weight: normal;"
            f" background: transparent; border: none; border-radius: 9px; padding: 0; margin: 0 4px 0 2px; }}"
            f" QToolButton:hover {{ background: {hover_bg}; color: {hover_color}; }}"
        )

    def _set_close_button(self, index: int, editor: CodeEditor) -> None:
        """Add a styled close button that tracks its editor widget."""
        is_dark = theme_is_dark(
            self._settings.get("editor.theme"),
            self._settings.get("editor.custom_theme.base"),
        )

        btn = QToolButton()
        btn.setText("\u2715")
        btn.setFixedSize(18, 18)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip("Close Tab")
        btn.setAutoRaise(True)
        btn.setStyleSheet(self._close_btn_stylesheet(is_dark))
        # Track editor, not index — index shifts when tabs are removed
        btn.clicked.connect(lambda checked=False, ed=editor: self._close_editor_tab(ed))
        self.tabBar().setTabButton(index, QTabBar.ButtonPosition.RightSide, btn)

    def _close_editor_tab(self, editor: CodeEditor) -> None:
        """Close the tab containing this editor (deferred to next event loop)."""
        def do_close():
            idx = self.indexOf(editor)
            if idx >= 0:
                self.close_tab(idx)
        QTimer.singleShot(0, do_close)

    def open_file_in_tab(self, file_path: str, content: str) -> CodeEditor:
        """Open a file. If already open, switch to its tab."""
        norm_path = str(Path(file_path).resolve())
        for i in range(self.count()):
            ed = self.widget(i)
            if isinstance(ed, CodeEditor) and ed.file_path:
                if str(Path(ed.file_path).resolve()) == norm_path:
                    self.setCurrentIndex(i)
                    return ed
        return self.new_tab(file_path, content)

    def close_tab(self, index: int) -> bool:
        """Close a tab. Prompt to save if modified. Returns True if closed."""
        editor = self.widget(index)
        if isinstance(editor, CodeEditor) and editor.is_modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                f"'{editor.display_name}' has unsaved changes.\n\nSave before closing?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return False
            if reply == QMessageBox.StandardButton.Save:
                main_window = self.parent()
                if hasattr(main_window, "action_save"):
                    main_window.action_save()
        self.removeTab(index)
        return True

    def close_all_tabs(self) -> bool:
        """Close all tabs, prompting for unsaved changes."""
        while self.count() > 0:
            if not self.close_tab(0):
                return False
        return True

    def prompt_save_all(self) -> bool:
        """Check all tabs for unsaved changes before app exit."""
        for i in range(self.count()):
            editor = self.widget(i)
            if isinstance(editor, CodeEditor) and editor.is_modified:
                self.setCurrentIndex(i)
                reply = QMessageBox.question(
                    self, "Unsaved Changes",
                    f"'{editor.display_name}' has unsaved changes.\n\nSave before closing?",
                    QMessageBox.StandardButton.Save
                    | QMessageBox.StandardButton.Discard
                    | QMessageBox.StandardButton.Cancel,
                )
                if reply == QMessageBox.StandardButton.Cancel:
                    return False
                if reply == QMessageBox.StandardButton.Save:
                    main_window = self.parent()
                    if hasattr(main_window, "action_save"):
                        main_window.action_save()
        return True

    def current_editor(self) -> CodeEditor | None:
        """Return the currently active CodeEditor, or None."""
        widget = self.currentWidget()
        return widget if isinstance(widget, CodeEditor) else None

    def get_open_file_paths(self) -> list[str]:
        """Return list of file paths for all open tabs."""
        paths = []
        for i in range(self.count()):
            ed = self.widget(i)
            if isinstance(ed, CodeEditor) and ed.file_path:
                paths.append(ed.file_path)
        return paths

    def update_tab_title(self, index: int) -> None:
        """Update the tab title from the editor's display_name."""
        editor = self.widget(index)
        if isinstance(editor, CodeEditor):
            self.setTabText(index, editor.display_name)

    def _update_modified_indicator(self, editor: CodeEditor, modified: bool) -> None:
        """Show/hide the '*' modified indicator on the tab."""
        index = self.indexOf(editor)
        if index >= 0:
            name = editor.display_name
            self.setTabText(index, f"* {name}" if modified else name)

    def update_theme(self) -> None:
        """Called when the theme changes to refresh close button colors."""
        is_dark = theme_is_dark(
            self._settings.get("editor.theme"),
            self._settings.get("editor.custom_theme.base"),
        )
        qss = self._close_btn_stylesheet(is_dark)
        bar = self.tabBar()
        for i in range(self.count()):
            btn = bar.tabButton(i, QTabBar.ButtonPosition.RightSide)
            if isinstance(btn, QToolButton):
                btn.setStyleSheet(qss)

    def _on_tab_changed(self, index: int) -> None:
        editor = self.widget(index) if index >= 0 else None
        self.tab_changed.emit(editor)

    # ── Welcome tab helpers ───────────────────────────────────────

    def show_welcome_tab(self, is_dark: bool = False) -> WelcomeWidget:
        """Insert a Welcome tab and switch to it. Returns the widget."""
        # If already showing, just switch to it
        for i in range(self.count()):
            w = self.widget(i)
            if isinstance(w, WelcomeWidget):
                self.setCurrentIndex(i)
                return w

        welcome = WelcomeWidget(is_dark=is_dark, parent=self)
        idx = self.insertTab(0, welcome, "Welcome")
        self._set_welcome_close_button(idx, welcome)
        self.setCurrentIndex(idx)
        return welcome

    def close_welcome_tab(self) -> None:
        """Remove the Welcome tab if it exists."""
        for i in range(self.count()):
            if isinstance(self.widget(i), WelcomeWidget):
                self.removeTab(i)
                return

    def _set_welcome_close_button(self, index: int, widget) -> None:
        """Add a styled close button for the welcome tab."""
        is_dark = theme_is_dark(
            self._settings.get("editor.theme"),
            self._settings.get("editor.custom_theme.base"),
        )

        btn = QToolButton()
        btn.setText("\u2715")
        btn.setFixedSize(18, 18)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip("Close Tab")
        btn.setAutoRaise(True)
        btn.setStyleSheet(self._close_btn_stylesheet(is_dark))
        btn.clicked.connect(lambda: QTimer.singleShot(0, self.close_welcome_tab))
        self.tabBar().setTabButton(index, QTabBar.ButtonPosition.RightSide, btn)

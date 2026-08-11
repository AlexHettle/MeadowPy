"""Tab manager for editor tabs."""

import re
from pathlib import Path

from PyQt6.QtCore import pyqtSignal, QEvent, Qt, QTimer, QSize, QPoint
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QTabBar,
    QTabWidget,
    QToolButton,
    QWidget,
)

from meadowpy.core.settings import Settings
from meadowpy.editor.code_editor import CodeEditor
from meadowpy.resources.resource_loader import current_accent_hex, theme_is_dark
from meadowpy.ui.save_helpers import prompt_save_before_closing, show_save_failed
from meadowpy.ui.welcome_widget import WelcomeWidget


class _ModifiedDot(QWidget):
    """Small accent-colored circle shown on modified tabs."""

    _RADIUS = 4

    def __init__(self, color_provider, parent=None):
        super().__init__(parent)
        self._color_provider = color_provider
        size = self._RADIUS * 2 + 2
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def refresh_color(self) -> None:
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._color_provider()))
        cx = self.width() // 2
        cy = self.height() // 2
        painter.drawEllipse(QPoint(cx, cy), self._RADIUS, self._RADIUS)
        painter.end()


class _TabRightWidget(QWidget):
    """Right-side tab widget: optional modified dot + close button."""

    def __init__(self, close_btn: QToolButton, dot: _ModifiedDot | None, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(4)
        self._dot = dot
        if dot is not None:
            sp = dot.sizePolicy()
            sp.setRetainSizeWhenHidden(True)
            dot.setSizePolicy(sp)
            dot.setVisible(False)
            layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self.close_btn = close_btn

    def set_modified(self, modified: bool) -> None:
        if self._dot is not None:
            self._dot.setVisible(modified)

    def refresh_dot_color(self) -> None:
        if self._dot is not None:
            self._dot.refresh_color()


class _EditorTabBar(QTabBar):
    """Accessible editor tab bar with responsive interaction states."""

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self.setExpanding(False)
        self.setUsesScrollButtons(True)
        self.setElideMode(Qt.TextElideMode.ElideMiddle)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setMouseTracking(True)
        self.setAccessibleName("Open file tabs")
        self.setAccessibleDescription(
            "Switch between open files. Use the Left and Right arrow keys."
        )
        self.setProperty("editorKeyboardFocus", False)
        self.setProperty("editorPressed", False)
        self._configure_scroll_buttons()

    def minimumSizeHint(self) -> QSize:
        """Prevent the tab bar from forcing the layout wider."""
        hint = super().minimumSizeHint()
        hint.setWidth(0)
        return hint

    def _configure_scroll_buttons(self) -> None:
        for button in self.findChildren(QToolButton):
            if button.parent() is not self:
                continue
            if button.arrowType() == Qt.ArrowType.LeftArrow:
                label = "Scroll file tabs left"
            elif button.arrowType() == Qt.ArrowType.RightArrow:
                label = "Scroll file tabs right"
            else:
                continue
            button.setAccessibleName(label)
            button.setToolTip(label)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

    def _set_visual_state(self, name: str, enabled: bool) -> None:
        if bool(self.property(name)) == enabled:
            return
        self.setProperty(name, enabled)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def focusInEvent(self, event) -> None:  # noqa: N802
        is_keyboard_focus = event.reason() in {
            Qt.FocusReason.TabFocusReason,
            Qt.FocusReason.BacktabFocusReason,
            Qt.FocusReason.ShortcutFocusReason,
        }
        self._set_visual_state("editorKeyboardFocus", is_keyboard_focus)
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:  # noqa: N802
        self._set_visual_state("editorKeyboardFocus", False)
        self._set_visual_state("editorPressed", False)
        super().focusOutEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        is_tab_press = (
            event.button() == Qt.MouseButton.LeftButton
            and self.tabAt(event.position().toPoint()) >= 0
        )
        self._set_visual_state("editorPressed", is_tab_press)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        super().mouseReleaseEvent(event)
        self._set_visual_state("editorPressed", False)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self.tabAt(event.position().toPoint()) >= 0:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._set_visual_state("editorPressed", False)
        self.unsetCursor()
        super().leaveEvent(event)

    def event(self, event) -> bool:
        if event.type() in {
            QEvent.Type.UngrabMouse,
            QEvent.Type.WindowDeactivate,
            QEvent.Type.Hide,
        }:
            self._set_visual_state("editorPressed", False)
        return super().event(event)


class TabManager(QTabWidget):
    """Manages editor tabs. Each tab contains a CodeEditor."""

    tab_changed = pyqtSignal(object)  # emits CodeEditor or None
    editor_created = pyqtSignal(object)  # emits each newly constructed CodeEditor
    editor_closed = pyqtSignal(object)  # emits after an editor leaves the tab set

    def __init__(self, settings: Settings, file_manager=None, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._file_manager = file_manager
        self._untitled_counter = 1

        self.setObjectName("editorTabs")
        self.setTabBar(_EditorTabBar(settings, self))

        self.setTabsClosable(False)
        self.setMovable(True)
        self.setDocumentMode(True)
        self.setContentsMargins(0, 0, 0, 0)
        self.setUsesScrollButtons(True)

        self.currentChanged.connect(self._on_tab_changed)

    def new_tab(
        self,
        file_path: str | None = None,
        content: str = "",
        *,
        large_file_mode: bool = False,
        untitled_name: str | None = None,
    ) -> CodeEditor:
        """Create a new editor tab. Returns the editor."""
        editor = CodeEditor(self._settings, self)
        editor.large_file_mode = large_file_mode

        if file_path:
            editor.file_path = file_path
            editor.setText(content)
            editor.setModified(False)
            tab_title = Path(file_path).name
        else:
            if untitled_name:
                editor._untitled_name = untitled_name
                match = re.fullmatch(r"Untitled-(\d+)", untitled_name)
                if match:
                    self._untitled_counter = max(
                        self._untitled_counter,
                        int(match.group(1)) + 1,
                    )
            else:
                editor._untitled_name = f"Untitled-{self._untitled_counter}"
                self._untitled_counter += 1
            if content:
                editor.setText(content)
            tab_title = editor._untitled_name

        index = self.addTab(editor, tab_title)
        self._set_close_button(index, editor)
        self._refresh_tab_metadata(index, editor)
        self.setCurrentIndex(index)

        editor.modification_changed.connect(
            lambda modified, ed=editor: self._update_modified_indicator(ed, modified)
        )
        self.editor_created.emit(editor)
        return editor

    def _close_btn_stylesheet(self, is_dark: bool, is_high_contrast: bool) -> str:
        """QSS for a stable, accessible close-tab hit target."""
        if is_high_contrast:
            idle_color = "#FFFFFF"
            hover_color = "#000000"
            hover_bg = "#FFFFFF"
            pressed_bg = "#FFFFFF"
        elif is_dark:
            idle_color = "#A0A0A0"
            hover_color = "#FFFFFF"
            hover_bg = "rgba(255,255,255,0.12)"
            pressed_bg = "rgba(255,255,255,0.20)"
        else:
            idle_color = "#60656D"
            hover_color = "#111827"
            hover_bg = "rgba(0,0,0,0.08)"
            pressed_bg = "rgba(0,0,0,0.14)"
        return (
            f"QToolButton {{ color: {idle_color}; font-family: 'Segoe UI Symbol';"
            f" font-size: 12px; font-weight: normal; background: transparent;"
            f" border: 1px solid transparent; border-radius: 12px;"
            f" padding: 0; margin: 0; }}"
            f" QToolButton:hover {{ background: {hover_bg}; color: {hover_color}; }}"
            f" QToolButton:pressed {{ background: {pressed_bg}; color: {hover_color}; }}"
        )

    def _accent_color(self) -> str:
        return current_accent_hex(
            self._settings.get("editor.theme") or "default_dark",
            self._settings.get("editor.custom_theme.base") or "dark",
            self._settings.get("editor.custom_theme.accent"),
        )

    def _refresh_tab_metadata(self, index: int, editor: CodeEditor) -> None:
        """Keep title, full-path tooltip, and trailing controls in sync."""
        if index < 0 or index >= self.count():
            return
        display_name = editor.display_name
        self.setTabText(index, display_name)
        self.setTabToolTip(index, editor.file_path or display_name)
        side = self.tabBar().tabButton(index, QTabBar.ButtonPosition.RightSide)
        if isinstance(side, _TabRightWidget):
            close_label = f"Close {display_name}"
            side.close_btn.setAccessibleName(close_label)
            side.close_btn.setToolTip(close_label)
            if side._dot is not None:
                side._dot.setAccessibleName(
                    f"{display_name} has unsaved changes"
                )

    def _set_close_button(self, index: int, editor: CodeEditor) -> None:
        """Add a styled close button (with modified dot) tied to this editor."""
        is_dark = theme_is_dark(
            self._settings.get("editor.theme"),
            self._settings.get("editor.custom_theme.base"),
        )
        is_high_contrast = (
            self._settings.get("editor.theme") == "default_high_contrast"
        )

        btn = QToolButton()
        btn.setText("\u2715")
        btn.setFixedSize(24, 24)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_label = f"Close {editor.display_name}"
        btn.setAccessibleName(close_label)
        btn.setToolTip(close_label)
        btn.setAutoRaise(True)
        btn.setStyleSheet(
            self._close_btn_stylesheet(is_dark, is_high_contrast)
        )
        btn.clicked.connect(lambda checked=False, ed=editor: self._close_editor_tab(ed))

        dot = _ModifiedDot(self._accent_color)
        dot.setAccessibleName(f"{editor.display_name} has unsaved changes")
        side = _TabRightWidget(btn, dot)
        side.set_modified(editor.is_modified)
        bar = self.tabBar()
        bar.setTabButton(index, QTabBar.ButtonPosition.RightSide, side)
        if isinstance(bar, _EditorTabBar):
            bar._configure_scroll_buttons()

    def _close_editor_tab(self, editor: CodeEditor) -> None:
        """Close the tab containing this editor (deferred to next event loop)."""
        def do_close():
            idx = self.indexOf(editor)
            if idx >= 0:
                self.close_tab(idx)
        QTimer.singleShot(0, do_close)

    def open_file_in_tab(
        self,
        file_path: str,
        content: str,
        *,
        large_file_mode: bool = False,
    ) -> CodeEditor:
        """Open a file. If already open, switch to its tab."""
        norm_path = str(Path(file_path).resolve())
        for i in range(self.count()):
            ed = self.widget(i)
            if isinstance(ed, CodeEditor) and ed.file_path:
                if str(Path(ed.file_path).resolve()) == norm_path:
                    ed.large_file_mode = large_file_mode
                    self.setCurrentIndex(i)
                    return ed
        return self.new_tab(file_path, content, large_file_mode=large_file_mode)

    def close_tab(self, index: int) -> bool:
        """Close a tab. Prompt to save if modified. Returns True if closed."""
        editor = self.widget(index)
        if isinstance(editor, CodeEditor) and editor.is_modified:
            if not self._prompt_save_editor(editor):
                return False
        self._remove_tab_and_delete(index)
        return True

    def _remove_tab_and_delete(self, index: int) -> None:
        """Remove a tab and schedule its page widget for deletion."""
        widget = self.widget(index)
        self.removeTab(index)
        if isinstance(widget, CodeEditor):
            self.editor_closed.emit(widget)
        if widget is not None:
            widget.deleteLater()

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
                if not self._prompt_save_editor(editor):
                    return False
        return True

    def _prompt_save_editor(self, editor: CodeEditor) -> bool:
        reply = prompt_save_before_closing(self, editor.display_name)
        if reply == QMessageBox.StandardButton.Cancel:
            return False
        if reply != QMessageBox.StandardButton.Save:
            return True
        return self._save_editor_for_prompt(editor)

    def _save_editor_for_prompt(self, editor: CodeEditor) -> bool:
        if not self._file_manager:
            return True
        if editor.file_path:
            if self._file_manager.save_file(editor.file_path, editor.text()):
                editor.setModified(False)
                return True
            show_save_failed(self, self._file_manager, editor.file_path)
            return False

        path = self._file_manager.save_file_as(editor.text(), parent=self)
        if path:
            editor.file_path = path
            editor.setModified(False)
            self._refresh_tab_metadata(self.indexOf(editor), editor)
            return True
        if getattr(self._file_manager, "last_save_error", None):
            show_save_failed(
                self,
                self._file_manager,
                getattr(self._file_manager, "last_save_error_path", None),
            )
        return False

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
            self._refresh_tab_metadata(index, editor)

    def _update_modified_indicator(self, editor: CodeEditor, modified: bool) -> None:
        """Show/hide the dot on this editor's tab."""
        index = self.indexOf(editor)
        if index < 0:
            return
        self._refresh_tab_metadata(index, editor)
        side = self.tabBar().tabButton(index, QTabBar.ButtonPosition.RightSide)
        if isinstance(side, _TabRightWidget):
            side.set_modified(modified)

    def update_theme(self) -> None:
        """Called when the theme changes to refresh close button colors."""
        theme_name = self._settings.get("editor.theme") or "default_dark"
        custom_base = self._settings.get("editor.custom_theme.base") or "dark"
        custom_accent = self._settings.get("editor.custom_theme.accent")
        is_dark = theme_is_dark(theme_name, custom_base)
        is_high_contrast = theme_name == "default_high_contrast"
        qss = self._close_btn_stylesheet(is_dark, is_high_contrast)
        bar = self.tabBar()
        for i in range(self.count()):
            widget = self.widget(i)
            if isinstance(widget, WelcomeWidget):
                widget.apply_theme(theme_name, custom_base, custom_accent)
            side = bar.tabButton(i, QTabBar.ButtonPosition.RightSide)
            if isinstance(side, _TabRightWidget):
                side.close_btn.setStyleSheet(qss)
                side.refresh_dot_color()
            elif isinstance(side, QToolButton):
                side.setStyleSheet(qss)

    def _on_tab_changed(self, index: int) -> None:
        editor = self.widget(index) if index >= 0 else None
        self.tab_changed.emit(editor)

    # ── Welcome tab helpers ───────────────────────────────────────

    def show_welcome_tab(
        self,
        theme_name: str,
        custom_base: str = "dark",
        custom_accent: str | None = None,
    ) -> WelcomeWidget:
        """Insert a Welcome tab and switch to it. Returns the widget."""
        # If already showing, just switch to it
        for i in range(self.count()):
            w = self.widget(i)
            if isinstance(w, WelcomeWidget):
                w.apply_theme(theme_name, custom_base, custom_accent)
                self.setCurrentIndex(i)
                return w

        welcome = WelcomeWidget(
            theme_name=theme_name,
            custom_base=custom_base,
            custom_accent=custom_accent,
            parent=self,
        )
        idx = self.insertTab(0, welcome, "Welcome")
        self._set_welcome_close_button(idx, welcome)
        self.setCurrentIndex(idx)
        return welcome

    def close_welcome_tab(self) -> None:
        """Remove the Welcome tab if it exists."""
        for i in range(self.count()):
            if isinstance(self.widget(i), WelcomeWidget):
                self._remove_tab_and_delete(i)
                return

    def _set_welcome_close_button(self, index: int, widget) -> None:
        """Add a styled close button for the welcome tab."""
        is_dark = theme_is_dark(
            self._settings.get("editor.theme"),
            self._settings.get("editor.custom_theme.base"),
        )
        is_high_contrast = (
            self._settings.get("editor.theme") == "default_high_contrast"
        )

        btn = QToolButton()
        btn.setText("\u2715")
        btn.setFixedSize(24, 24)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setAccessibleName("Close Welcome")
        btn.setToolTip("Close Welcome")
        btn.setAutoRaise(True)
        btn.setStyleSheet(
            self._close_btn_stylesheet(is_dark, is_high_contrast)
        )
        btn.clicked.connect(lambda: QTimer.singleShot(0, self.close_welcome_tab))
        side = _TabRightWidget(btn, None)
        self.tabBar().setTabButton(index, QTabBar.ButtonPosition.RightSide, side)
        self.setTabToolTip(index, "Welcome")

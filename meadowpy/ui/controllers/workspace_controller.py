from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox
from PyQt6.Qsci import QsciScintilla

from meadowpy.constants import APP_NAME
from meadowpy.editor.code_editor import CodeEditor
from meadowpy.editor.editor_config import EditorConfigurator
from meadowpy.resources.resource_loader import (
    current_accent_hex,
    get_stylesheet,
    run_button_accent_hex,
    theme_is_dark,
)
from meadowpy.ui.controllers.window_context import MainWindowController


class WorkspaceController(MainWindowController):
    """Owns a focused slice of MainWindow behavior."""

    def _initial_refresh(self) -> None:
        """Run the first outline + lint update after the window is visible."""
        editor = self._tab_manager.current_editor()
        if editor:
            self._refresh_symbol_outline(editor)
            self._do_lint()
            self._update_interpreter_label()
        self._ollama_client.start()
        # Start the interactive Python console
        if self._settings.get("repl.auto_start"):
            self._start_repl()

    # ── Welcome screen ─────────────────────────────────────────────

    def _show_welcome(self) -> None:
        """Show the Welcome tab and wire its signals."""
        from meadowpy.ui.welcome_widget import WelcomeWidget

        # Check if a welcome tab already exists — avoid double-connecting
        theme_name = self._settings.get("editor.theme") or "default_dark"
        custom_base = self._settings.get("editor.custom_theme.base") or "dark"
        custom_accent = self._settings.get("editor.custom_theme.accent")
        for i in range(self._tab_manager.count()):
            widget = self._tab_manager.widget(i)
            if isinstance(widget, WelcomeWidget):
                widget.apply_theme(theme_name, custom_base, custom_accent)
                self._tab_manager.setCurrentIndex(i)
                return

        welcome = self._tab_manager.show_welcome_tab(
            theme_name=theme_name,
            custom_base=custom_base,
            custom_accent=custom_accent,
        )
        welcome.action_new_file.connect(self._welcome_new_file)
        welcome.action_open_file.connect(self.action_open_file)
        welcome.action_open_folder.connect(self.action_open_folder)
        welcome.template_selected.connect(self._on_template_selected)

    def _welcome_new_file(self) -> None:
        """New File from welcome: close welcome tab, open blank tab."""
        self._tab_manager.close_welcome_tab()
        self._tab_manager.new_tab()

    def _on_template_selected(self, name: str, code: str) -> None:
        """Open a new untitled tab pre-filled with the template code."""
        self._tab_manager.close_welcome_tab()
        editor = self._tab_manager.new_tab()
        editor.setText(code)
        editor.setModified(False)

    def action_show_welcome(self) -> None:
        """Re-show the welcome tab (accessible from Help menu)."""
        self._show_welcome()

    # --- Action handlers ---

    def action_new_file(self) -> None:
        self._tab_manager.new_tab()

    def action_open_file(self) -> None:
        result = self._file_manager.open_file(parent=self.window)
        if result:
            path, content = result
            self._tab_manager.open_file_in_tab(path, content)

    def action_open_folder(self) -> None:
        """Show a directory picker and set it as the project folder."""
        from PyQt6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(
            self.window, "Open Folder", "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if folder:
            self._file_explorer.set_root_folder(folder)
            self._file_explorer.show()
            self._settings.set("general.project_folder", folder)
            self._search_panel.set_root_path(folder)

    def _on_explorer_file_selected(self, file_path: str) -> None:
        """Open a file from the explorer in an editor tab."""
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return
        content = self._file_manager.read_file(file_path)
        self._tab_manager.open_file_in_tab(file_path, content)
        self._recent_files.add(file_path)

    def _on_explorer_file_renamed(self, old_path: str, new_path: str) -> None:
        """Update any open tab whose file was renamed in the explorer."""
        old_resolved = str(Path(old_path).resolve())
        for i in range(self._tab_manager.count()):
            editor = self._tab_manager.widget(i)
            if not isinstance(editor, CodeEditor) or not editor.file_path:
                continue
            if str(Path(editor.file_path).resolve()) == old_resolved:
                editor.file_path = new_path
                editor._is_modified = False
                self._tab_manager.setTabText(i, Path(new_path).name)
                self._tab_manager.setTabToolTip(i, new_path)
                break

    def _on_explorer_file_deleted(self, deleted_path: str) -> None:
        """Close any open tab whose file was deleted in the explorer."""
        deleted_resolved = str(Path(deleted_path).resolve())
        # Iterate in reverse so indices stay valid after removal
        for i in range(self._tab_manager.count() - 1, -1, -1):
            editor = self._tab_manager.widget(i)
            if not isinstance(editor, CodeEditor) or not editor.file_path:
                continue
            editor_resolved = str(Path(editor.file_path).resolve())
            # Match exact file or any file inside a deleted folder
            if (editor_resolved == deleted_resolved
                    or editor_resolved.startswith(deleted_resolved + "\\")):
                self._tab_manager.removeTab(i)

    # ── Drag & Drop ──────────────────────────────────────────────────

    def action_save(self) -> None:
        editor = self._tab_manager.current_editor()
        if not editor:
            return
        if editor.file_path:
            self._file_manager.save_file(editor.file_path, editor.text())
            editor.setModified(False)
            self._tab_manager.update_tab_title(self._tab_manager.currentIndex())
        else:
            self.action_save_as()

    def action_save_as(self) -> None:
        editor = self._tab_manager.current_editor()
        if not editor:
            return
        path = self._file_manager.save_file_as(editor.text(), parent=self.window)
        if path:
            editor.file_path = path
            editor.setModified(False)
            self._tab_manager.update_tab_title(self._tab_manager.currentIndex())

    def action_close_tab(self) -> None:
        index = self._tab_manager.currentIndex()
        if index >= 0:
            self._tab_manager.close_tab(index)

    def action_toggle_find(self) -> None:
        self._find_replace_bar.toggle_find()

    def action_toggle_find_replace(self) -> None:
        self._find_replace_bar.toggle_replace()

    def action_search_in_files(self) -> None:
        """Open and focus the Search panel (Ctrl+Shift+F)."""
        self._search_panel.focus_search()

    def action_goto_line(self) -> None:
        editor = self._tab_manager.current_editor()
        if not editor:
            return
        line_count = editor.lines()
        line_num, ok = QInputDialog.getInt(
            self.window, "Go to Line", f"Line number (1-{line_count}):",
            1, 1, line_count,
        )
        if ok:
            editor.setCursorPosition(line_num - 1, 0)
            editor.setFocus()

    def action_zoom(self, direction: int) -> None:
        """Zoom in (1), out (-1), or reset (0)."""
        editor = self._tab_manager.current_editor()
        if not editor:
            return
        if direction == 0:
            editor.zoomTo(0)
        elif direction > 0:
            editor.zoomIn()
        else:
            editor.zoomOut()

    def action_toggle_word_wrap(self) -> None:
        editor = self._tab_manager.current_editor()
        if not editor:
            return
        current = editor.wrapMode() != QsciScintilla.WrapMode.WrapNone
        new_mode = (
            QsciScintilla.WrapMode.WrapNone
            if current
            else QsciScintilla.WrapMode.WrapWord
        )
        editor.setWrapMode(new_mode)
        self._settings.set("editor.word_wrap", not current)
        if hasattr(self, "_word_wrap_action"):
            self._word_wrap_action.setChecked(not current)

    def action_toggle_output_panel(self) -> None:
        """Show the output panel and raise it (used by Run actions)."""
        self._output_panel.setVisible(True)
        self._output_panel.raise_()

    # --- Run actions (Phase 3) ---

    def _on_traceback_navigate(self, file_path: str, line: int) -> None:
        """Open the file from a traceback and jump to the given line."""
        path = Path(file_path)
        if not path.exists():
            return
        content = self._file_manager.read_file(str(path))
        editor = self._tab_manager.open_file_in_tab(str(path), content)
        if editor:
            editor.setCursorPosition(line - 1, 0)
            editor.setFocus()

    def _on_search_navigate(self, file_path: str, line: int) -> None:
        """Open a file from the search panel and jump to the given line."""
        path = Path(file_path)
        if not path.exists():
            return
        content = self._file_manager.read_file(str(path))
        editor = self._tab_manager.open_file_in_tab(str(path), content)
        if editor:
            editor.setCursorPosition(line - 1, 0)
            editor.setFocus()

    def action_preferences(self) -> None:
        from meadowpy.ui.dialogs.preferences_dialog import PreferencesDialog

        dialog = PreferencesDialog(self._settings, self.window)
        dialog.exec()

    def action_example_library(self) -> None:
        from meadowpy.ui.dialogs.example_library_dialog import ExampleLibraryDialog

        dialog = ExampleLibraryDialog(self.window)
        dialog.example_selected.connect(self._on_template_selected)
        dialog.exec()

    def action_shortcut_reference(self) -> None:
        from meadowpy.ui.dialogs.shortcut_reference_dialog import ShortcutReferenceDialog

        dialog = ShortcutReferenceDialog(self.window)
        dialog.exec()

    def action_about(self) -> None:
        from meadowpy.ui.dialogs.about_dialog import AboutDialog

        dialog = AboutDialog(self._settings, self.window)
        dialog.exec()

    def open_file_in_tab(self, file_path: str, content: str) -> None:
        """Public method for opening a file in a tab (used by app.py)."""
        self._tab_manager.open_file_in_tab(file_path, content)

    def open_recent_file(self, file_path: str) -> None:
        """Open a file from the recent files list."""
        path = Path(file_path)
        if not path.exists():
            QMessageBox.warning(
                self.window, "File Not Found",
                f"The file no longer exists:\n{file_path}",
            )
            self._recent_files.remove(file_path)
            return
        content = self._file_manager.read_file(file_path)
        self._tab_manager.open_file_in_tab(file_path, content)
        self._recent_files.add(file_path)

    # --- Event handlers ---

    def _on_tab_changed(self, editor) -> None:
        """Update status bar, outline, and lint when active tab changes."""
        if isinstance(editor, CodeEditor):
            # Auto-close the Welcome tab once a real editor is active
            self._tab_manager.close_welcome_tab()

            # Update title
            title = f"{editor.display_name} - {APP_NAME}"
            self.setWindowTitle(title)

            # Connect cursor position updates
            try:
                editor.cursorPositionChanged.disconnect(self._on_cursor_moved)
            except TypeError:
                pass
            editor.cursorPositionChanged.connect(self._on_cursor_moved)

            # Update cursor position now
            line, col = editor.getCursorPosition()
            self._status_bar_manager.update_cursor_position(line, col)

            # Connect text changes for outline + lint debounce
            try:
                editor.textChanged.disconnect(self._on_editor_text_changed)
            except TypeError:
                pass
            editor.textChanged.connect(self._on_editor_text_changed)

            # Connect AI context menu actions
            try:
                editor.ai_explain_requested.disconnect(self._on_ai_explain_requested)
            except TypeError:
                pass
            editor.ai_explain_requested.connect(self._on_ai_explain_requested)

            try:
                editor.ai_improve_requested.disconnect(self._on_ai_improve_requested)
            except TypeError:
                pass
            editor.ai_improve_requested.connect(self._on_ai_improve_requested)

            try:
                editor.ai_docstring_requested.disconnect(self._on_ai_docstring_requested)
            except TypeError:
                pass
            editor.ai_docstring_requested.connect(self._on_ai_docstring_requested)

            # Update AI chat panel context with current file info
            self._update_ai_context(editor)

            # Refresh outline, lint, and interpreter label
            self._refresh_symbol_outline(editor)
            self._do_lint()
            self._update_interpreter_label()
        else:
            self.setWindowTitle(APP_NAME)
            self._symbol_outline.clear_symbols()
            self._problems_panel.clear_issues()

    def _on_cursor_moved(self, line: int, col: int) -> None:
        self._status_bar_manager.update_cursor_position(line, col)
        # Update AI context with current cursor position
        editor = self._tab_manager.current_editor()
        if isinstance(editor, CodeEditor):
            self._update_ai_context(editor, line=line)

    def _on_settings_changed(self, key: str, value) -> None:
        """Re-apply settings to all open editors when a setting changes."""
        # Swap app-wide stylesheet when theme OR any custom-theme setting changes
        theme_keys = (
            "editor.theme",
            "editor.custom_theme.base",
            "editor.custom_theme.accent",
        )
        if key in theme_keys:
            app = QApplication.instance()
            if app:
                app.setStyleSheet(get_stylesheet(
                    self._settings.get("editor.theme"),
                    custom_base=self._settings.get("editor.custom_theme.base"),
                    custom_accent=self._settings.get("editor.custom_theme.accent"),
                ))
            self._tab_manager.update_theme()
            self._apply_explorer_icon_theme()
            if hasattr(self, "_ai_chat_panel"):
                theme_name = self._settings.get("editor.theme")
                base = self._settings.get("editor.custom_theme.base")
                self._ai_chat_panel.apply_accent(
                    current_accent_hex(
                        theme_name, base,
                        self._settings.get("editor.custom_theme.accent"),
                    ),
                    theme_is_dark(theme_name, base),
                )
            # Re-tint the "Run" button glow in the toolbar & output panel to
            # match the current theme's accent (only Custom theme changes it).
            accent = run_button_accent_hex(
                self._settings.get("editor.theme"),
                self._settings.get("editor.custom_theme.accent"),
            )
            if hasattr(self, "_toolbar_builder"):
                self._toolbar_builder.update_accent_color(accent)
            if hasattr(self, "_output_panel"):
                self._output_panel.update_accent_color(accent)

            # Rebuild icons whose color depends on the theme (Run/Stop/Debug
            # are white in HC, original brand colors in dark/light/custom).
            # Without this, icons created at startup persist across theme
            # switches and you get white icons leaking into non-HC themes.
            self._refresh_themed_icons()

            # Re-render the Problems panel so its severity glyphs (✕ red /
            # ⚠ amber vs both white in HC) follow the new theme.
            if hasattr(self, "_problems_panel"):
                self._problems_panel.update_issues(
                    list(self._problems_panel._issues)
                )

            # Output panel bakes color into character formats at insert time,
            # so already-printed traceback text stays in the old theme's
            # colors until we replay the history.
            if hasattr(self, "_output_panel"):
                self._output_panel.recolor_for_theme()

            # Status bar lint counts use inline-HTML colors that don't update
            # on stylesheet change — re-render with the new theme's colors.
            if hasattr(self, "_status_bar_manager"):
                self._status_bar_manager.refresh_lint_colors()

        for i in range(self._tab_manager.count()):
            editor = self._tab_manager.widget(i)
            if isinstance(editor, CodeEditor):
                EditorConfigurator.apply(editor, self._settings)
                # Squiggle indicator colors are baked at set_lint_issues time
                # and don't follow stylesheet changes — re-apply with the
                # current theme's palette so HC switches refresh underlines.
                if key in theme_keys:
                    editor.refresh_lint_colors()
                    editor.refresh_marker_colors()

        self._status_bar_manager.update_indent_info()

        # Toggle outline/problems visibility based on settings
        if key == "editor.show_symbol_outline":
            self._symbol_outline.setVisible(value)
        if key == "editor.linting_enabled":
            if not value:
                self._problems_panel.hide()
                self._status_bar_manager.update_lint_counts(0, 0)
        if key == "explorer.show_file_explorer":
            self._file_explorer.setVisible(value)

    # --- Symbol outline ---

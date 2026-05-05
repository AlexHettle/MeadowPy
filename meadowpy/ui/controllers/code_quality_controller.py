from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QTimer

from meadowpy.core.linter import LintRunner
from meadowpy.editor.code_editor import CodeEditor
from meadowpy.ui.controllers.window_context import MainWindowController


class CodeQualityController(MainWindowController):
    """Owns a focused slice of MainWindow behavior."""

    def _create_lint_runner(self) -> None:
        """Create the lint runner and debounce timer."""
        self._lint_runner = LintRunner(self)
        self._lint_runner.lint_finished.connect(self._on_lint_finished)
        self._lint_runner.lint_error.connect(self._on_lint_error)

        self._lint_timer = QTimer(self)
        self._lint_timer.setSingleShot(True)
        self._lint_timer.setInterval(
            self._settings.get("editor.lint_delay_ms")
        )
        self._lint_timer.timeout.connect(self._do_lint)

    def _on_editor_text_changed(self) -> None:
        """Debounce both outline refresh and lint on text changes."""
        self._outline_timer.start()
        if self._settings.get("editor.linting_enabled"):
            self._lint_timer.start()

    def _on_file_saved(self, path: str) -> None:
        """Handle file saved: show message + trigger lint."""
        self._status_bar_manager.show_message(f"Saved: {Path(path).name}")
        if self._settings.get("editor.lint_on_save"):
            self._do_lint()

    def _on_outline_navigate(self, line: int) -> None:
        """Navigate editor to line when outline item is clicked."""
        editor = self._tab_manager.current_editor()
        if editor:
            editor.setCursorPosition(line, 0)
            editor.setFocus()

    def _do_refresh_outline(self) -> None:
        """Refresh the symbol outline (called after debounce)."""
        editor = self._tab_manager.current_editor()
        if editor:
            self._refresh_symbol_outline(editor)

    def _on_outline_visibility_changed(self, visible: bool) -> None:
        """Refresh the outline when the panel becomes visible."""
        if visible:
            editor = self._tab_manager.current_editor()
            if editor:
                self._symbol_outline.update_symbols(editor.text())

    def _refresh_symbol_outline(self, editor: CodeEditor) -> None:
        """Update the symbol outline from the editor's current text."""
        if self._symbol_outline.isVisible():
            self._symbol_outline.update_symbols(editor.text())

    # --- Linting ---

    def _on_problem_navigate(self, line: int, col: int) -> None:
        """Navigate editor to location when problem row is clicked."""
        editor = self._tab_manager.current_editor()
        if editor:
            editor.setCursorPosition(line, col)
            editor.setFocus()

    def _do_lint(self) -> None:
        """Actually run the linter (called after debounce or on save)."""
        editor = self._tab_manager.current_editor()
        if editor and self._settings.get("editor.linting_enabled"):
            self._lint_target_editor = editor
            self._lint_runner.run_lint(
                editor.text(),
                editor.file_path,
                self._settings.get("editor.linter"),
            )

    def _on_lint_finished(self, issues: list) -> None:
        """Receive lint results and update UI."""
        editor = getattr(self, "_lint_target_editor", None)
        if editor is None:
            editor = self._tab_manager.current_editor()
        if editor:
            editor.set_lint_issues(issues)
        self._problems_panel.update_issues(issues)

        # Update status bar with counts
        error_count = sum(1 for i in issues if i.severity == "error")
        warning_count = sum(1 for i in issues if i.severity == "warning")
        self._status_bar_manager.update_lint_counts(error_count, warning_count)

    def _on_lint_error(self, message: str) -> None:
        """Show a linter error (e.g. not installed) in the Problems panel."""
        self._problems_panel.show_linter_error(message)
        self._status_bar_manager.update_lint_counts(0, 0)

    # --- Ollama AI ---

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QTimer

from meadowpy.core.interpreter_manager import InterpreterManager
from meadowpy.core.lint_context import LintContextError, resolve_lint_context
from meadowpy.core.linter import LintRunner
from meadowpy.editor.code_editor import CodeEditor
from meadowpy.ui.controllers.run_eligibility import can_run_editor
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
        editor = self._tab_manager.current_editor()
        if self._is_large_file_editor(editor):
            self._clear_large_file_analysis_state(editor)
            return

        self._outline_timer.start()
        if not self._settings.get("editor.linting_enabled"):
            return
        if not self._settings.get("editor.lint_while_typing", True):
            self._clear_lint_state(editor)
            return
        if can_run_editor(editor, CodeEditor):
            self._lint_timer.start()
        else:
            self._clear_lint_state(editor)

    def _on_file_saved(self, path: str) -> None:
        """Handle file saved: show message + trigger lint."""
        self._status_bar_manager.show_message(f"Saved: {Path(path).name}")
        if (
            self._settings.get("editor.linting_enabled")
            and self._settings.get("editor.lint_on_save")
        ):
            self._stop_pending_lint_debounce()
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
            if self._is_large_file_editor(editor):
                self._symbol_outline.clear_symbols()
                return
            self._refresh_symbol_outline(editor)

    def _on_outline_visibility_changed(self, visible: bool) -> None:
        """Refresh the outline when the panel becomes visible."""
        if visible:
            editor = self._tab_manager.current_editor()
            if editor:
                if self._is_large_file_editor(editor):
                    self._symbol_outline.clear_symbols()
                    return
                self._symbol_outline.update_symbols(editor.text())

    def _refresh_symbol_outline(self, editor: CodeEditor) -> None:
        """Update the symbol outline from the editor's current text."""
        if self._is_large_file_editor(editor):
            self._symbol_outline.clear_symbols()
            return
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
        if self._is_large_file_editor(editor):
            self._clear_lint_state(editor)
            return
        if not self._settings.get("editor.linting_enabled"):
            return
        if not can_run_editor(editor, CodeEditor):
            self._clear_lint_state(editor)
            return
        linter = self._settings.get("editor.linter")
        explorer = getattr(self, "_file_explorer", None)
        project_root = getattr(explorer, "root_path", None)
        interpreter_manager = getattr(self, "_interpreter_manager", None)
        if interpreter_manager is None:
            interpreter_manager = InterpreterManager()
        try:
            execution_context = resolve_lint_context(
                settings=self._settings,
                interpreter_manager=interpreter_manager,
                linter=linter,
                file_path=editor.file_path,
                project_root=project_root,
            )
        except LintContextError as exc:
            self._clear_lint_state(editor)
            self._on_lint_error(str(exc))
            return
        self._last_lint_context = execution_context
        self._lint_target_editor = editor
        self._lint_runner.run_lint(
            editor.text(),
            editor.file_path,
            linter,
            self._settings.get("editor.show_lint_style_issues", True),
            execution_context=execution_context,
        )

    def action_run_linter(self) -> None:
        """Run the configured linter for the current file immediately."""
        if not self._settings.get("editor.linting_enabled"):
            return
        self._stop_pending_lint_debounce()
        self._problems_panel.setVisible(True)
        self._problems_panel.raise_()
        self._do_lint()

    def _stop_pending_lint_debounce(self) -> None:
        timer = getattr(self, "_lint_timer", None)
        stop = getattr(timer, "stop", None)
        if callable(stop):
            stop()

    def _on_lint_finished(self, issues: list) -> None:
        """Receive lint results and update UI."""
        current_editor = self._tab_manager.current_editor()
        editor = getattr(self, "_lint_target_editor", None)
        if editor is None:
            editor = current_editor
        if editor is not current_editor:
            self._lint_target_editor = None
            return
        if self._is_large_file_editor(editor):
            self._clear_lint_state(editor)
            return
        if not can_run_editor(editor, CodeEditor):
            self._clear_lint_state(editor)
            return
        editor.set_lint_issues(issues)
        self._lint_target_editor = None
        self._problems_panel.update_issues(issues)

        # Update status bar with counts
        error_count = sum(1 for i in issues if i.severity == "error")
        warning_count = sum(1 for i in issues if i.severity == "warning")
        self._status_bar_manager.update_lint_counts(error_count, warning_count)

    def _show_cached_lint_state(self, editor) -> None:
        """Show the active editor's last results without running the linter."""
        if not self._settings.get("editor.linting_enabled", True):
            self._clear_lint_state(editor)
            return
        issues = list(getattr(editor, "_lint_issues", ()))
        self._problems_panel.update_issues(issues)
        error_count = sum(1 for issue in issues if issue.severity == "error")
        warning_count = sum(
            1 for issue in issues if issue.severity == "warning"
        )
        self._status_bar_manager.update_lint_counts(error_count, warning_count)

    def _on_lint_error(self, message: str) -> None:
        """Show a linter error (e.g. not installed) in the Problems panel."""
        target = getattr(self, "_lint_target_editor", None)
        current_editor = self._tab_manager.current_editor()
        if target is not None and target is not current_editor:
            self._lint_target_editor = None
            return
        self._lint_target_editor = None
        self._problems_panel.show_linter_error(message)
        self._status_bar_manager.update_lint_counts(0, 0)

    def _clear_lint_state(self, editor=None) -> None:
        """Clear lint UI and cancel pending results for a non-lintable tab."""
        runner = getattr(self, "_lint_runner", None)
        cancel = getattr(runner, "cancel", None)
        if callable(cancel):
            cancel()
        if editor is not None:
            clear_markers = getattr(editor, "clear_lint_markers", None)
            if callable(clear_markers):
                clear_markers()
            else:
                set_issues = getattr(editor, "set_lint_issues", None)
                if callable(set_issues):
                    set_issues([])
        self._lint_target_editor = None
        self._problems_panel.clear_issues()
        self._status_bar_manager.update_lint_counts(0, 0)

    @staticmethod
    def _is_large_file_editor(editor) -> bool:
        return bool(getattr(editor, "large_file_mode", False))

    def _clear_large_file_analysis_state(self, editor=None) -> None:
        self._symbol_outline.clear_symbols()
        self._clear_lint_state(editor)

    # --- Ollama AI ---

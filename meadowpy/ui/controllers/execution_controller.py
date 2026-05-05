from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QInputDialog, QMessageBox

from meadowpy.core.process_runner import ProcessRunner
from meadowpy.core.repl_manager import ReplManager
from meadowpy.ui.controllers.window_context import MainWindowController


class ExecutionController(MainWindowController):
    """Owns a focused slice of MainWindow behavior."""

    def _create_process_runner(self) -> None:
        """Create the process runner and wire its signals."""
        self._process_runner = ProcessRunner(self)
        self._process_runner.output_received.connect(self._on_process_output)
        self._process_runner.process_started.connect(self._on_process_started)
        self._process_runner.process_finished.connect(self._on_process_finished)

    def _create_repl_manager(self) -> None:
        """Create the interactive REPL manager and wire its signals."""
        self._repl_manager = ReplManager(self)
        self._repl_manager.output_received.connect(self._on_repl_output)
        self._repl_manager.repl_started.connect(self._on_repl_started)
        self._repl_manager.repl_stopped.connect(self._on_repl_stopped)
        self._repl_manager.prompt_ready.connect(
            self._output_panel.update_repl_prompt
        )

        # Wire output panel REPL signals
        self._output_panel.repl_input_submitted.connect(self._on_repl_input)
        self._output_panel.repl_restart_requested.connect(self._on_repl_restart)
        self._output_panel.repl_history_up.connect(self._on_repl_history_up)
        self._output_panel.repl_history_down.connect(self._on_repl_history_down)

    def _resolve_working_dir(self, file_path: str | None) -> str:
        """Resolve the working directory based on settings.

        If run.working_directory is "project" and a project folder is open,
        use that. Otherwise fall back to the file's parent directory.
        """
        mode = self._settings.get("run.working_directory")
        if mode == "project":
            project = self._settings.get("general.project_folder")
            if project and Path(project).is_dir():
                return str(project)
        # Default: file's parent directory
        if file_path:
            return str(Path(file_path).parent)
        return "."

    def action_run_file(self) -> None:
        """Run the current file (F5)."""
        editor = self._tab_manager.current_editor()
        if not editor:
            return

        # Confirm if already running
        if self._process_runner.is_running():
            reply = QMessageBox.question(
                self.window,
                "Process Running",
                "A process is already running. Stop it and run again?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._process_runner.stop()

        # Save before run if configured
        if self._settings.get("run.save_before_run"):
            if editor.isModified():
                self.action_save()

        # Need a file path to run
        file_path = editor.file_path
        if not file_path:
            self.action_save_as()
            file_path = editor.file_path
            if not file_path:
                return  # user cancelled save-as

        # Resolve interpreter and working directory
        interpreter = self._interpreter_manager.get_interpreter(
            self._settings, file_path
        )
        working_dir = self._resolve_working_dir(file_path)

        # Clear output if configured
        if self._settings.get("run.clear_output_before_run"):
            self._output_panel.clear_output()

        # Show output panel if configured
        if self._settings.get("run.show_output_panel"):
            self._output_panel.show()
            self._output_panel.raise_()

        self._process_runner.run_file(file_path, interpreter, working_dir)

    def action_run_selection(self) -> None:
        """Run the selected text or current line (Shift+F5)."""
        editor = self._tab_manager.current_editor()
        if not editor:
            return

        # Confirm if already running
        if self._process_runner.is_running():
            reply = QMessageBox.question(
                self.window,
                "Process Running",
                "A process is already running. Stop it and run again?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._process_runner.stop()

        # Get selected text, or current line if no selection
        code = editor.selectedText()
        if not code.strip():
            line, _ = editor.getCursorPosition()
            code = editor.text(line)

        if not code.strip():
            return

        interpreter = self._interpreter_manager.get_interpreter(
            self._settings, editor.file_path
        )
        working_dir = self._resolve_working_dir(editor.file_path)

        if self._settings.get("run.clear_output_before_run"):
            self._output_panel.clear_output()

        if self._settings.get("run.show_output_panel"):
            self._output_panel.show()
            self._output_panel.raise_()

        self._process_runner.run_code(code, interpreter, working_dir)

    def action_stop_process(self) -> None:
        """Stop the currently running process or debug session (Ctrl+F5)."""
        if self._debug_manager.is_running():
            self._debug_manager.stop_debug()
        else:
            self._process_runner.stop()

    def action_select_interpreter(self) -> None:
        """Show a dialog to select the Python interpreter."""
        editor = self._tab_manager.current_editor()
        file_path = editor.file_path if editor else None
        interpreters = self._interpreter_manager.detect_interpreters(file_path)

        items = [f"{info.label}  ({info.path})" for info in interpreters]
        item, ok = QInputDialog.getItem(
            self.window,
            "Select Python Interpreter",
            "Choose an interpreter:",
            items,
            0,
            False,
        )
        if ok and item:
            idx = items.index(item)
            chosen = interpreters[idx]
            self._settings.set("run.python_interpreter", chosen.path)
            self._update_interpreter_label()

    def action_create_venv(self) -> None:
        """Open the virtual environment creation dialog."""
        from meadowpy.ui.dialogs.venv_dialog import VenvDialog

        editor = self._tab_manager.current_editor()
        file_path = editor.file_path if editor else None
        dialog = VenvDialog(self._interpreter_manager, file_path, self.window)
        dialog.exec()

    def _on_process_output(self, text: str, stream: str) -> None:
        self._output_panel.append_output(text, stream)
        if stream == "stderr":
            from meadowpy.core.error_explainer import explain_error
            explanation = explain_error(text)
            if explanation:
                self._output_panel.append_output(explanation, "hint")

    def _on_process_started(self, desc: str) -> None:
        self._output_panel.set_running(True)
        self._run_action.setEnabled(False)
        self._debug_action.setEnabled(False)
        self._stop_action.setEnabled(True)
        self._output_panel.append_output(f">>> {desc}\n", "system")
        self._status_bar_manager.show_message(desc)

    def _on_process_finished(self, exit_code: int, desc: str) -> None:
        self._output_panel.set_running(False)
        self._run_action.setEnabled(True)
        self._debug_action.setEnabled(True)
        self._stop_action.setEnabled(False)
        self._output_panel.append_output(f">>> {desc}\n", "system")
        self._status_bar_manager.show_message(desc)

    def _on_stdin_submitted(self, text: str) -> None:
        if self._debug_manager.is_running():
            self._debug_manager.send_stdin(text)
        else:
            self._process_runner.send_stdin(text)

    # ── REPL handlers ──────────────────────────────────────────────

    def _start_repl(self) -> None:
        """Start the interactive Python console."""
        editor = self._tab_manager.current_editor()
        file_path = editor.file_path if editor else None
        interpreter = self._interpreter_manager.get_interpreter(
            self._settings, file_path
        )
        working_dir = self._resolve_repl_working_dir()
        self._repl_manager.start(interpreter, working_dir)

    def _resolve_repl_working_dir(self) -> str:
        """Determine working directory for the REPL."""
        project = self._settings.get("general.project_folder")
        if project and Path(project).is_dir():
            return str(project)
        editor = self._tab_manager.current_editor()
        if editor and editor.file_path:
            return str(Path(editor.file_path).parent)
        return str(Path.home())

    def _on_repl_input(self, text: str) -> None:
        """Send user input to the REPL subprocess."""
        self._repl_manager.add_to_history(text)
        self._repl_manager.send_input(text)

    def _on_repl_output(self, text: str, stream: str) -> None:
        """Display REPL output in the output panel."""
        self._output_panel.append_output(text, stream)
        if stream == "stderr":
            from meadowpy.core.error_explainer import explain_error
            explanation = explain_error(text)
            if explanation:
                self._output_panel.append_output(explanation, "hint")

    def _on_repl_started(self) -> None:
        self._output_panel.append_output(
            "Python console ready.\n", "system"
        )

    def _on_repl_stopped(self) -> None:
        self._output_panel.append_output(
            "Python console stopped.\n", "system"
        )

    def _on_repl_restart(self) -> None:
        """Restart the REPL with a fresh state."""
        # Stop any running script or debug session first
        if self._debug_manager.is_running():
            self._debug_manager.stop_debug()
        elif self._process_runner.is_running():
            self._process_runner.stop()
        self._output_panel.clear_output()
        if self._repl_manager.is_running:
            self._repl_manager.stop()
        self._start_repl()

    def _on_repl_history_up(self) -> None:
        text = self._repl_manager.history_up()
        if text is not None:
            self._output_panel.set_input_text(text)

    def _on_repl_history_down(self) -> None:
        text = self._repl_manager.history_down()
        if text is not None:
            self._output_panel.set_input_text(text)

    def _update_interpreter_label(self) -> None:
        """Update the status bar interpreter label."""
        editor = self._tab_manager.current_editor()
        file_path = editor.file_path if editor else None
        interpreter = self._interpreter_manager.get_interpreter(
            self._settings, file_path
        )
        version = self._interpreter_manager._get_version(interpreter)
        self._status_bar_manager.update_interpreter(f"Python {version}")

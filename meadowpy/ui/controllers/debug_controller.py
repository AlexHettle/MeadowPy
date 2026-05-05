from __future__ import annotations

from pathlib import Path

from meadowpy.core.debug_manager import DebugManager, DebugState
from meadowpy.editor.code_editor import CodeEditor
from meadowpy.ui.controllers.window_context import MainWindowController


class DebugController(MainWindowController):
    """Owns a focused slice of MainWindow behavior."""

    def _create_debug_manager(self) -> None:
        """Create the debug manager and wire its signals."""
        self._debug_manager = DebugManager(self)
        self._debug_manager.state_changed.connect(self._on_debug_state_changed)
        self._debug_manager.paused.connect(self._on_debug_paused)
        self._debug_manager.resumed.connect(self._on_debug_resumed)
        self._debug_manager.eval_result.connect(self._on_debug_eval_result)
        self._debug_manager.debug_output.connect(self._on_process_output)
        self._debug_manager.debug_started.connect(self._on_debug_started)
        self._debug_manager.debug_finished.connect(self._on_debug_finished)

    def action_toggle_breakpoint(self) -> None:
        """Toggle a breakpoint on the current cursor line (F9)."""
        editor = self._tab_manager.current_editor()
        if editor:
            line, _ = editor.getCursorPosition()
            editor.toggle_breakpoint(line)

    # --- Debug actions (Phase 4) ---

    def action_start_debug(self) -> None:
        """Start a debug session (F6)."""
        if self._debug_manager.state != DebugState.IDLE:
            return

        editor = self._tab_manager.current_editor()
        if not editor:
            return

        # Save before debug
        if self._settings.get("run.save_before_run"):
            if editor.isModified():
                self.action_save()

        file_path = editor.file_path
        if not file_path:
            self.action_save_as()
            file_path = editor.file_path
            if not file_path:
                return

        interpreter = self._interpreter_manager.get_interpreter(
            self._settings, file_path
        )
        working_dir = self._resolve_working_dir(file_path)

        # Collect breakpoints from ALL open tabs
        breakpoints = self._collect_all_breakpoints()

        # Clear and show output panel
        if self._settings.get("run.clear_output_before_run"):
            self._output_panel.clear_output()
        if self._settings.get("run.show_output_panel"):
            self._output_panel.show()
            self._output_panel.raise_()

        self._debug_manager.start_debug(
            file_path, interpreter, working_dir, breakpoints
        )

    def action_debug_continue(self) -> None:
        """Continue execution (F5 during debug)."""
        if self._debug_manager.state == DebugState.PAUSED:
            self._debug_manager.send_continue()

    def action_debug_step_over(self) -> None:
        """Step over the current line (F10)."""
        if self._debug_manager.state == DebugState.PAUSED:
            self._debug_manager.send_step_over()

    def action_debug_step_into(self) -> None:
        """Step into the current line (F11)."""
        if self._debug_manager.state == DebugState.PAUSED:
            self._debug_manager.send_step_into()

    def action_debug_step_out(self) -> None:
        """Step out of the current function (Shift+F11)."""
        if self._debug_manager.state == DebugState.PAUSED:
            self._debug_manager.send_step_out()

    def action_stop_debug(self) -> None:
        """Stop the current debug session (Shift+F5)."""
        self._debug_manager.stop_debug()

    def action_clear_all_breakpoints(self) -> None:
        """Clear breakpoints from all open editors."""
        for i in range(self._tab_manager.count()):
            editor = self._tab_manager.widget(i)
            if isinstance(editor, CodeEditor):
                editor.clear_breakpoints()

    def _collect_all_breakpoints(self) -> dict[str, list[int]]:
        """Collect breakpoints from all tabs: {filepath: [1-based lines]}."""
        result = {}
        for i in range(self._tab_manager.count()):
            editor = self._tab_manager.widget(i)
            if isinstance(editor, CodeEditor) and editor.file_path:
                bp_lines = editor.get_breakpoints()
                if bp_lines:
                    # Convert 0-based to 1-based for the protocol
                    result[editor.file_path] = [line + 1 for line in bp_lines]
        return result

    def _set_run_as_continue(self, as_continue: bool) -> None:
        """Swap the Run button between Run and Continue modes."""
        if as_continue:
            if not getattr(self, "_run_is_continue", False):
                self._run_action.triggered.disconnect(self.action_run_file)
                self._run_action.triggered.connect(self.action_debug_continue)
                self._run_action.setToolTip("Continue (F5)")
                self._run_is_continue = True
        else:
            if getattr(self, "_run_is_continue", False):
                self._run_action.triggered.disconnect(self.action_debug_continue)
                self._run_action.triggered.connect(self.action_run_file)
                self._run_action.setToolTip("Run File (F5)")
                self._run_is_continue = False

    def _on_debug_state_changed(self, state: DebugState) -> None:
        """Update UI state based on debug lifecycle changes."""
        is_debugging = state not in (DebugState.IDLE,)
        is_paused = state == DebugState.PAUSED

        # Show/hide inline debug step actions
        self._debug_separator.setVisible(is_debugging)
        self._step_over_action.setVisible(is_debugging)
        self._step_into_action.setVisible(is_debugging)
        self._step_out_action.setVisible(is_debugging)
        self._step_over_action.setEnabled(is_paused)
        self._step_into_action.setEnabled(is_paused)
        self._step_out_action.setEnabled(is_paused)

        # Repurpose Run button as Continue when debug is paused,
        # disable it when running (not paused), restore when idle.
        if is_paused:
            self._set_run_as_continue(True)
            self._run_action.setEnabled(True)
        elif is_debugging:
            self._run_action.setEnabled(False)
        else:
            self._set_run_as_continue(False)
            self._run_action.setEnabled(True)

        self._debug_action.setEnabled(not is_debugging)

        # Enable/disable debug menu actions
        # (these are created by MenuBarBuilder and stored on self)
        if hasattr(self, "_debug_continue_action"):
            self._debug_continue_action.setEnabled(is_paused)
            self._debug_step_over_action.setEnabled(is_paused)
            self._debug_step_into_action.setEnabled(is_paused)
            self._debug_step_out_action.setEnabled(is_paused)
            self._debug_stop_action.setEnabled(is_debugging)

        # Show debug panels when paused
        if is_paused:
            self._variable_inspector.show()
            self._variable_inspector.raise_()

        # Update status bar
        self._status_bar_manager.update_debug_state(state)

    def _on_debug_started(self, desc: str) -> None:
        """Handle debug session starting."""
        self._output_panel.set_running(True)
        self._stop_action.setEnabled(True)
        self._output_panel.append_output(f">>> {desc}\n", "system")
        self._status_bar_manager.show_message(desc)

    def _on_debug_paused(
        self, file_path: str, line: int, variables: dict, call_stack: list
    ) -> None:
        """Handle debugger pausing at a line."""
        # Open file and show current-line marker
        path = Path(file_path)
        if path.exists():
            # Check if file is already open
            editor = None
            for i in range(self._tab_manager.count()):
                e = self._tab_manager.widget(i)
                if isinstance(e, CodeEditor) and e.file_path == str(path):
                    editor = e
                    self._tab_manager.setCurrentWidget(editor)
                    break

            if editor is None:
                # Open the file in a new tab
                content = self._file_manager.read_file(str(path))
                editor = self._tab_manager.open_file_in_tab(str(path), content)

            if editor:
                self._clear_debug_markers()
                editor.set_current_line(line)
                editor.setFocus()

        # Update debug panels
        self._variable_inspector.update_variables(variables)
        self._call_stack_panel.update_call_stack(call_stack)

        # Show debug panels
        self._variable_inspector.show()
        self._call_stack_panel.show()
        self._watch_panel.show()
        self._variable_inspector.raise_()

        # Re-evaluate watch expressions
        self._watch_panel.request_all_evaluations()

    def _on_debug_resumed(self) -> None:
        """Handle debugger resuming execution."""
        self._clear_debug_markers()

    def _on_debug_eval_result(
        self, expression: str, result: str, error: str
    ) -> None:
        """Handle evaluation result from the debug helper."""
        self._watch_panel.update_value(expression, result, error)

    def _on_debug_finished(self, exit_code: int, desc: str) -> None:
        """Handle debug session ending."""
        self._output_panel.set_running(False)
        self._set_run_as_continue(False)
        self._run_action.setEnabled(True)
        self._debug_action.setEnabled(True)
        self._stop_action.setEnabled(False)
        self._output_panel.append_output(f">>> {desc}\n", "system")
        self._status_bar_manager.show_message(desc)

        # Clear all debug UI
        self._clear_debug_markers()
        self._variable_inspector.clear_variables()
        self._call_stack_panel.clear_stack()
        self._watch_panel.clear_values()

        # Hide debug step actions
        self._debug_separator.setVisible(False)
        self._step_over_action.setVisible(False)
        self._step_into_action.setVisible(False)
        self._step_out_action.setVisible(False)
        self._variable_inspector.hide()
        self._call_stack_panel.hide()
        self._watch_panel.hide()

    def _clear_debug_markers(self) -> None:
        """Clear the current-line marker from all editors."""
        for i in range(self._tab_manager.count()):
            editor = self._tab_manager.widget(i)
            if isinstance(editor, CodeEditor):
                editor.clear_current_line()

from __future__ import annotations

import os
import weakref
from pathlib import Path

from PyQt6.QtCore import QTimer

from meadowpy.core.debug_manager import DebugManager, DebugState
from meadowpy.core.shortcuts import get_default_shortcut
from meadowpy.editor.code_editor import CodeEditor
from meadowpy.ui.controllers.run_eligibility import can_run_editor
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
        acknowledgement = getattr(
            self._debug_manager,
            "breakpoint_update_acknowledged",
            None,
        )
        if acknowledgement is None:
            # Keep the controller compatible with early implementations that
            # exposed the helper event name directly as the Qt signal name.
            acknowledgement = getattr(
                self._debug_manager,
                "breakpoints_updated",
                None,
            )
        connect = getattr(acknowledgement, "connect", None)
        if callable(connect):
            connect(self._on_breakpoint_update_acknowledged)

    def action_toggle_breakpoint(self) -> None:
        """Toggle a breakpoint on the current cursor line (F9)."""
        editor = self._tab_manager.current_editor()
        if can_run_editor(editor, CodeEditor):
            line, _ = editor.getCursorPosition()
            editor.toggle_breakpoint(line)
            # Normal editors emit ``breakpoints_changed`` from the toggle.
            # Retain a fallback for lightweight/legacy editor implementations
            # that do not expose the signal, without double-sending for the
            # wired path.
            if not self._editor_breakpoints_are_wired(editor):
                self._update_active_debug_breakpoints()

    # --- Debug actions (Phase 4) ---

    def action_start_debug(self) -> None:
        """Start a debug session (F6)."""
        if self._debug_manager.state != DebugState.IDLE:
            return

        editor = self._tab_manager.current_editor()
        if not can_run_editor(editor, CodeEditor):
            return

        file_path = self._prepare_editor_file_for_execution(editor, CodeEditor)
        if not file_path:
            return

        interpreter = self._interpreter_manager.get_interpreter(
            self._settings, file_path
        )
        working_dir = self._resolve_working_dir(file_path)

        # Collect breakpoints from ALL open tabs
        breakpoints = self._collect_all_breakpoints()
        self._mark_breakpoints_pending()

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
        self._breakpoint_sync_suspended = (
            self.__dict__.get("_breakpoint_sync_suspended", 0) + 1
        )
        try:
            for i in range(self._tab_manager.count()):
                editor = self._tab_manager.widget(i)
                if isinstance(editor, CodeEditor):
                    editor.clear_breakpoints()
        finally:
            self._breakpoint_sync_suspended -= 1
        self._update_active_debug_breakpoints()

    def _wire_editor_breakpoints(self, editor) -> None:
        """Connect one editor's breakpoint changes to the live debugger once."""
        if not isinstance(editor, CodeEditor):
            return

        signal = getattr(editor, "breakpoints_changed", None)
        connect = getattr(signal, "connect", None)
        if not callable(connect) or self._editor_breakpoints_are_wired(editor):
            return

        editor_ref = weakref.ref(editor)

        def forward_change(*_args) -> None:
            current_editor = editor_ref()
            if current_editor is not None:
                self._on_editor_breakpoints_changed(current_editor)

        connect(forward_change)
        self._wired_breakpoint_editors().add(editor)

    def _wired_breakpoint_editors(self):
        """Return the weak set used to prevent duplicate editor connections."""
        wired = self.__dict__.get("_breakpoint_wired_editors")
        if wired is None:
            wired = weakref.WeakSet()
            self._breakpoint_wired_editors = wired
        return wired

    def _editor_breakpoints_are_wired(self, editor) -> bool:
        try:
            return editor in self._wired_breakpoint_editors()
        except TypeError:
            # A custom editor proxy may not support weak references. Such an
            # object cannot be registered in the normal Qt editor lifecycle,
            # so the action-level compatibility send remains appropriate.
            return False

    def _on_editor_breakpoints_changed(self, editor) -> None:
        """Propagate gutter, keyboard, and edit-relocated breakpoints live."""
        if self.__dict__.get("_breakpoint_sync_suspended", 0):
            return
        self._update_active_debug_breakpoints()

    def _on_editor_closed(self, _editor=None) -> None:
        """Coalesce tab removals into one live breakpoint synchronization."""
        manager = getattr(self, "_debug_manager", None)
        if manager is None or manager.state == DebugState.IDLE:
            return
        if self.__dict__.get("_breakpoint_close_sync_pending", False):
            return
        self._breakpoint_close_sync_pending = True
        QTimer.singleShot(0, self._flush_closed_editor_breakpoint_sync)

    def _flush_closed_editor_breakpoint_sync(self) -> None:
        self._breakpoint_close_sync_pending = False
        self._update_active_debug_breakpoints()

    def _collect_all_breakpoints(self) -> dict[str, list[int]]:
        """Collect breakpoints from all tabs: {filepath: [1-based lines]}."""
        result = {}
        for i in range(self._tab_manager.count()):
            editor = self._tab_manager.widget(i)
            if can_run_editor(editor, CodeEditor) and editor.file_path:
                bp_lines = editor.get_breakpoints()
                if bp_lines:
                    # Convert 0-based to 1-based for the protocol
                    result[editor.file_path] = [
                        line + 1 for line in sorted(bp_lines)
                    ]
        return result

    def _update_active_debug_breakpoints(self) -> None:
        """Send all current breakpoints to a live debug session."""
        manager = getattr(self, "_debug_manager", None)
        if manager is None or manager.state == DebugState.IDLE:
            return
        self._mark_breakpoints_pending()
        manager.update_breakpoints(self._collect_all_breakpoints())

    def _mark_breakpoints_pending(self) -> None:
        """Show current breakpoint markers as pending until helper ack."""
        for i in range(self._tab_manager.count()):
            editor = self._tab_manager.widget(i)
            if not can_run_editor(editor, CodeEditor):
                continue
            mark_pending = getattr(editor, "mark_breakpoints_pending", None)
            if callable(mark_pending):
                mark_pending(editor.get_breakpoints())

    def _reset_breakpoint_verification(self) -> None:
        """Restore ordinary breakpoint markers when no debug session is live."""
        for i in range(self._tab_manager.count()):
            editor = self._tab_manager.widget(i)
            if not can_run_editor(editor, CodeEditor):
                continue
            set_verification = getattr(
                editor,
                "set_breakpoint_verification",
                None,
            )
            if callable(set_verification):
                set_verification(editor.get_breakpoints(), {})

    @staticmethod
    def _normalized_debug_path(file_path) -> str:
        """Return a stable path key for matching helper acknowledgements."""
        try:
            resolved = str(Path(file_path).resolve())
        except (OSError, TypeError, ValueError):
            resolved = str(file_path)
        return os.path.normcase(resolved)

    @staticmethod
    def _protocol_lines_to_editor_lines(lines) -> set[int]:
        """Convert a helper iterable of 1-based lines to valid 0-based lines."""
        converted = set()
        for line in lines or ():
            try:
                line_number = int(line)
            except (TypeError, ValueError):
                continue
            if line_number > 0:
                converted.add(line_number - 1)
        return converted

    def _on_breakpoint_update_acknowledged(
        self,
        accepted: dict,
        rejected: dict,
    ) -> None:
        """Apply debugger accepted/rejected state to each matching editor."""
        accepted_by_path = {
            self._normalized_debug_path(path): lines
            for path, lines in (accepted or {}).items()
        }
        rejected_by_path = {
            self._normalized_debug_path(path): lines
            for path, lines in (rejected or {}).items()
        }

        for i in range(self._tab_manager.count()):
            editor = self._tab_manager.widget(i)
            if not isinstance(editor, CodeEditor) or not editor.file_path:
                continue

            path_key = self._normalized_debug_path(editor.file_path)
            if (
                path_key not in accepted_by_path
                and path_key not in rejected_by_path
            ):
                # An omitted file may belong to a newer in-flight update; its
                # markers must remain pending rather than accepting stale data.
                continue

            accepted_lines = self._protocol_lines_to_editor_lines(
                accepted_by_path.get(path_key, ())
            )
            rejected_payload = rejected_by_path.get(path_key, {})
            if hasattr(rejected_payload, "items"):
                rejected_lines = {}
                for line, reason in rejected_payload.items():
                    converted = self._protocol_lines_to_editor_lines((line,))
                    if converted:
                        rejected_lines[converted.pop()] = str(reason)
            else:
                rejected_lines = self._protocol_lines_to_editor_lines(
                    rejected_payload
                )

            set_verification = getattr(
                editor,
                "set_breakpoint_verification",
                None,
            )
            if callable(set_verification):
                set_verification(accepted_lines, rejected_lines)

    def _set_run_as_continue(self, as_continue: bool) -> None:
        """Swap the Run button between Run and Continue modes."""
        if as_continue:
            if not getattr(self, "_run_is_continue", False):
                self._run_action.triggered.disconnect(self.action_run_file)
                self._run_action.triggered.connect(self.action_debug_continue)
                self._run_action.setToolTip(
                    f"Continue{self._run_shortcut_suffix()}"
                )
                self._run_is_continue = True
        else:
            if getattr(self, "_run_is_continue", False):
                self._run_action.triggered.disconnect(self.action_debug_continue)
                self._run_action.triggered.connect(self.action_run_file)
                self._run_action.setToolTip(
                    f"Run File{self._run_shortcut_suffix()}"
                )
                self._run_is_continue = False

    def _refresh_debug_shortcut_tooltips(self) -> None:
        """Refresh debug-mode tooltip text after shortcut customization."""
        if getattr(self, "_run_is_continue", False):
            self._run_action.setToolTip(
                f"Continue{self._run_shortcut_suffix()}"
            )

    def _run_shortcut_suffix(self) -> str:
        shortcut_suffix = getattr(self.window, "_shortcut_suffix", None)
        if callable(shortcut_suffix):
            return shortcut_suffix("run.file")
        shortcut = get_default_shortcut("run.file")
        return f" ({shortcut})" if shortcut else ""

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

        if hasattr(self, "_run_selection_action"):
            self._run_selection_action.setEnabled(not is_debugging)

        if is_debugging:
            self._debug_action.setEnabled(False)
        else:
            self._debug_action.setEnabled(True)
            self._refresh_run_action_enabled()

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
                reader = getattr(self.window, "_read_editor_file", None)
                large_file_mode = False
                if callable(reader):
                    read_result = reader(str(path))
                    if read_result is None:
                        return
                    if (
                        isinstance(read_result, tuple)
                        and len(read_result) == 2
                    ):
                        content, large_file_mode = read_result
                    elif isinstance(read_result, str):
                        # Compatibility with early/custom window readers that
                        # returned only the decoded text.
                        content = read_result
                    else:
                        return
                else:
                    try:
                        content = self._file_manager.read_file(str(path))
                    except OSError:
                        return
                # This method is invoked from a Qt signal.  Never pass an
                # unexpected reader payload into QScintilla: an uncaught slot
                # exception makes PyQt abort the whole process.
                if not isinstance(content, str):
                    return
                if large_file_mode:
                    editor = self._tab_manager.open_file_in_tab(
                        str(path),
                        content,
                        large_file_mode=True,
                    )
                else:
                    editor = self._tab_manager.open_file_in_tab(
                        str(path),
                        content,
                    )

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
        if hasattr(self, "_run_selection_action"):
            self._run_selection_action.setEnabled(True)
        self._debug_action.setEnabled(True)
        self._stop_action.setEnabled(False)
        self._refresh_run_action_enabled()
        self._output_panel.append_output(f">>> {desc}\n", "system")
        self._status_bar_manager.show_message(desc)

        # Clear all debug UI
        self._clear_debug_markers()
        self._reset_breakpoint_verification()
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

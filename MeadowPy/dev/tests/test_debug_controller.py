from types import SimpleNamespace

import meadowpy.ui.controllers.debug_controller as debug_module
from meadowpy.core.debug_manager import DebugState
from meadowpy.ui.controllers.debug_controller import DebugController
from meadowpy.ui.controllers.window_context import MainWindowContext
from helpers import DummySignal


class FakeEditor:
    def __init__(self, file_path, breakpoints):
        self.file_path = file_path
        self._breakpoints = breakpoints
        self.cleared = False

    def get_breakpoints(self):
        return self._breakpoints

    def clear_current_line(self):
        self.cleared = True


class FakeTabManager:
    def __init__(self, widgets):
        self.widgets = widgets

    def current_editor(self):
        return self.widgets[0] if self.widgets else None

    def count(self):
        return len(self.widgets)

    def widget(self, index):
        return self.widgets[index]


def test_collect_all_breakpoints_converts_to_protocol_lines(monkeypatch):
    monkeypatch.setattr(debug_module, "CodeEditor", FakeEditor)
    tabs = FakeTabManager([
        FakeEditor("a.py", {0, 2}),
        FakeEditor("b.py", set()),
        FakeEditor("requirements.txt", {1}),
    ])
    window = SimpleNamespace(_tab_manager=tabs)
    controller = DebugController(MainWindowContext(window, None, None, None))

    assert controller._collect_all_breakpoints() == {"a.py": [1, 3]}


def test_clear_debug_markers_clears_every_editor(monkeypatch):
    monkeypatch.setattr(debug_module, "CodeEditor", FakeEditor)
    editors = [FakeEditor("a.py", set()), FakeEditor("b.py", set())]
    window = SimpleNamespace(_tab_manager=FakeTabManager(editors))
    controller = DebugController(MainWindowContext(window, None, None, None))

    controller._clear_debug_markers()

    assert [editor.cleared for editor in editors] == [True, True]


class FakeAction:
    def __init__(self):
        self.enabled = None
        self.visible = None
        self.tooltip = ""
        self.triggered = DummySignal()

    def setEnabled(self, value):
        self.enabled = value

    def setVisible(self, value):
        self.visible = value

    def setToolTip(self, value):
        self.tooltip = value


class StartDebugEditor:
    def __init__(self, file_path, breakpoints=None, modified=False):
        self.file_path = file_path
        self._breakpoints = breakpoints or set()
        self.modified = modified
        self.current_lines = []
        self.focused = False
        self.pending = []
        self.verifications = []

    def isModified(self):
        return self.modified

    def get_breakpoints(self):
        return self._breakpoints

    def mark_breakpoints_pending(self, lines=None):
        self.pending.append(set(lines or ()))

    def set_breakpoint_verification(self, accepted, rejected=()):
        self.verifications.append((set(accepted), rejected))

    def set_current_line(self, line):
        self.current_lines.append(line)

    def clear_current_line(self):
        self.current_lines.clear()

    def setFocus(self):
        self.focused = True


class FakeOutputPanel:
    def __init__(self):
        self.cleared = 0
        self.shown = 0
        self.raised = 0
        self.running = None
        self.outputs = []

    def clear_output(self):
        self.cleared += 1

    def show(self):
        self.shown += 1

    def raise_(self):
        self.raised += 1

    def set_running(self, value):
        self.running = value

    def append_output(self, text, stream):
        self.outputs.append((text, stream))


def test_start_debug_saves_file_collects_breakpoints_and_shows_output(monkeypatch, tmp_path):
    monkeypatch.setattr(debug_module, "CodeEditor", StartDebugEditor)
    script = tmp_path / "debug_me.py"
    script.write_text("x = 1", encoding="utf-8")
    editor = StartDebugEditor(str(script), {0, 3}, modified=True)
    debug_calls = []
    output = FakeOutputPanel()
    calls = []
    settings = SimpleNamespace(
        get=lambda key, default=None: {
            "run.save_before_run": True,
            "run.clear_output_before_run": True,
            "run.show_output_panel": True,
        }.get(key, default)
    )
    tabs = FakeTabManager([editor])
    window = SimpleNamespace(
        _settings=settings,
        _debug_manager=SimpleNamespace(
            state=DebugState.IDLE,
            start_debug=lambda *args: debug_calls.append(args),
        ),
        _tab_manager=tabs,
        _interpreter_manager=SimpleNamespace(
            get_interpreter=lambda settings, file_path: "python.exe"
        ),
        _output_panel=output,
        action_save=lambda: calls.append("save") or True,
        _resolve_working_dir=lambda file_path: str(tmp_path),
    )
    controller = DebugController(
        MainWindowContext(window=window, settings=settings, file_manager=None, recent_files=None)
    )

    controller.action_start_debug()

    assert calls == ["save"]
    assert output.cleared == 1
    assert output.shown == 1
    assert output.raised == 1
    assert debug_calls == [
        (str(script), "python.exe", str(tmp_path), {str(script): [1, 4]})
    ]
    assert editor.pending == [{0, 3}]


def test_start_debug_aborts_when_save_before_debug_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(debug_module, "CodeEditor", StartDebugEditor)
    script = tmp_path / "debug_me.py"
    script.write_text("x = 1", encoding="utf-8")
    editor = StartDebugEditor(str(script), {0}, modified=True)
    debug_calls = []
    output = FakeOutputPanel()
    calls = []
    settings = SimpleNamespace(
        get=lambda key, default=None: {
            "run.save_before_run": True,
            "run.clear_output_before_run": True,
            "run.show_output_panel": True,
        }.get(key, default)
    )
    window = SimpleNamespace(
        _settings=settings,
        _debug_manager=SimpleNamespace(
            state=DebugState.IDLE,
            start_debug=lambda *args: debug_calls.append(args),
        ),
        _tab_manager=FakeTabManager([editor]),
        _output_panel=output,
        action_save=lambda: calls.append("save") or False,
    )
    controller = DebugController(
        MainWindowContext(window=window, settings=settings, file_manager=None, recent_files=None)
    )

    controller.action_start_debug()

    assert calls == ["save"]
    assert output.cleared == 0
    assert output.shown == 0
    assert debug_calls == []


def test_start_debug_ignores_saved_non_python_file(monkeypatch, tmp_path):
    monkeypatch.setattr(debug_module, "CodeEditor", StartDebugEditor)
    notes = tmp_path / "notes.txt"
    notes.write_text("not python", encoding="utf-8")
    editor = StartDebugEditor(str(notes), modified=True)
    debug_calls = []
    output = FakeOutputPanel()
    calls = []
    settings = SimpleNamespace(
        get=lambda key, default=None: {
            "run.save_before_run": True,
            "run.clear_output_before_run": True,
            "run.show_output_panel": True,
        }.get(key, default)
    )
    window = SimpleNamespace(
        _settings=settings,
        _debug_manager=SimpleNamespace(
            state=DebugState.IDLE,
            start_debug=lambda *args: debug_calls.append(args),
        ),
        _tab_manager=FakeTabManager([editor]),
        _output_panel=output,
        action_save=lambda: calls.append("save"),
    )
    controller = DebugController(
        MainWindowContext(window=window, settings=settings, file_manager=None, recent_files=None)
    )

    controller.action_start_debug()

    assert calls == []
    assert output.cleared == 0
    assert output.shown == 0
    assert debug_calls == []


def test_start_debug_rechecks_save_as_file_type(monkeypatch, tmp_path):
    monkeypatch.setattr(debug_module, "CodeEditor", StartDebugEditor)
    editor = StartDebugEditor(None)
    debug_calls = []
    output = FakeOutputPanel()
    calls = []
    settings = SimpleNamespace(
        get=lambda key, default=None: {
            "run.save_before_run": False,
            "run.clear_output_before_run": True,
            "run.show_output_panel": True,
        }.get(key, default)
    )
    window = SimpleNamespace(
        _settings=settings,
        _debug_manager=SimpleNamespace(
            state=DebugState.IDLE,
            start_debug=lambda *args: debug_calls.append(args),
        ),
        _tab_manager=FakeTabManager([editor]),
        _output_panel=output,
        action_save_as=lambda: calls.append("save_as"),
    )
    controller = DebugController(
        MainWindowContext(window=window, settings=settings, file_manager=None, recent_files=None)
    )
    controller.action_save_as = lambda: (
        calls.append("save_as"),
        setattr(editor, "file_path", str(tmp_path / "notes.txt")),
    )

    controller.action_start_debug()

    assert calls == ["save_as"]
    assert output.cleared == 0
    assert output.shown == 0
    assert debug_calls == []


def test_start_debug_ignores_non_code_tab_object():
    debug_calls = []
    settings = SimpleNamespace(get=lambda key, default=None: False)
    window = SimpleNamespace(
        _settings=settings,
        _debug_manager=SimpleNamespace(
            state=DebugState.IDLE,
            start_debug=lambda *args: debug_calls.append(args),
        ),
        _tab_manager=FakeTabManager([object()]),
    )
    controller = DebugController(
        MainWindowContext(window=window, settings=settings, file_manager=None, recent_files=None)
    )

    controller.action_start_debug()

    assert debug_calls == []


def test_debug_state_changes_swap_run_button_and_menu_state():
    run_file = lambda: None
    run_action = FakeAction()
    run_action.triggered.connect(run_file)
    calls = []
    window = SimpleNamespace(
        action_run_file=run_file,
        _run_action=run_action,
        _run_selection_action=FakeAction(),
        _debug_action=FakeAction(),
        _debug_separator=FakeAction(),
        _step_over_action=FakeAction(),
        _step_into_action=FakeAction(),
        _step_out_action=FakeAction(),
        _debug_continue_action=FakeAction(),
        _debug_step_over_action=FakeAction(),
        _debug_step_into_action=FakeAction(),
        _debug_step_out_action=FakeAction(),
        _debug_stop_action=FakeAction(),
        _variable_inspector=SimpleNamespace(
            shown=0,
            raised=0,
            show=lambda: calls.append("variables_show"),
            raise_=lambda: calls.append("variables_raise"),
        ),
        _status_bar_manager=SimpleNamespace(
            update_debug_state=lambda state: calls.append(("state", state))
        ),
    )
    controller = DebugController(MainWindowContext(window, None, None, None))

    controller._on_debug_state_changed(DebugState.PAUSED)

    assert run_action.enabled is True
    assert window._run_selection_action.enabled is False
    assert run_action.tooltip == "Continue (F5)"
    assert window._step_over_action.enabled is True
    assert window._debug_stop_action.enabled is True
    assert calls[-3:] == [
        "variables_show",
        "variables_raise",
        ("state", DebugState.PAUSED),
    ]

    controller._on_debug_state_changed(DebugState.IDLE)

    assert run_action.enabled is True
    assert window._run_selection_action.enabled is True
    assert run_action.tooltip == "Run File (F5)"
    assert window._debug_action.enabled is True
    assert calls[-1] == ("state", DebugState.IDLE)


def test_debug_idle_refresh_preserves_non_python_disabled_state():
    calls = []
    run_action = FakeAction()
    run_selection_action = FakeAction()
    debug_action = FakeAction()
    window = SimpleNamespace(
        action_run_file=lambda: None,
        _run_action=run_action,
        _run_selection_action=run_selection_action,
        _debug_action=debug_action,
        _debug_separator=FakeAction(),
        _step_over_action=FakeAction(),
        _step_into_action=FakeAction(),
        _step_out_action=FakeAction(),
        _status_bar_manager=SimpleNamespace(
            update_debug_state=lambda state: calls.append(("state", state))
        ),
    )
    window._update_run_action_enabled = lambda: (
        calls.append("refresh"),
        run_action.setEnabled(False),
        run_selection_action.setEnabled(False),
        debug_action.setEnabled(False),
    )
    controller = DebugController(MainWindowContext(window, None, None, None))

    controller._on_debug_state_changed(DebugState.IDLE)

    assert run_action.enabled is False
    assert run_selection_action.enabled is False
    assert debug_action.enabled is False
    assert calls == ["refresh", ("state", DebugState.IDLE)]


def test_debug_pause_updates_editor_panels_and_watch_expressions(monkeypatch, tmp_path):
    monkeypatch.setattr(debug_module, "CodeEditor", StartDebugEditor)
    script = tmp_path / "paused.py"
    script.write_text("value = 1", encoding="utf-8")
    editor = StartDebugEditor(str(script))
    calls = []
    tabs = FakeTabManager([editor])
    tabs.setCurrentWidget = lambda widget: calls.append(("current", widget.file_path))
    window = SimpleNamespace(
        _tab_manager=tabs,
        _file_manager=SimpleNamespace(read_file=lambda path: "value = 1"),
        _variable_inspector=SimpleNamespace(
            update_variables=lambda variables: calls.append(("vars", variables)),
            show=lambda: calls.append("vars_show"),
            raise_=lambda: calls.append("vars_raise"),
        ),
        _call_stack_panel=SimpleNamespace(
            update_call_stack=lambda stack: calls.append(("stack", stack)),
            show=lambda: calls.append("stack_show"),
        ),
        _watch_panel=SimpleNamespace(
            show=lambda: calls.append("watch_show"),
            request_all_evaluations=lambda: calls.append("watch_eval"),
        ),
    )
    controller = DebugController(MainWindowContext(window, None, None, None))
    variables = {"locals": {"value": "1"}}
    stack = [{"function": "<module>", "file": str(script), "line": 1}]

    controller._on_debug_paused(str(script), 0, variables, stack)

    assert editor.current_lines == [0]
    assert editor.focused is True
    assert ("vars", variables) in calls
    assert ("stack", stack) in calls
    assert "watch_eval" in calls


def test_create_debug_manager_wires_every_signal(monkeypatch):
    class FakeDebugManager:
        def __init__(self, parent):
            self.parent = parent
            self.state_changed = DummySignal()
            self.paused = DummySignal()
            self.resumed = DummySignal()
            self.eval_result = DummySignal()
            self.debug_output = DummySignal()
            self.debug_started = DummySignal()
            self.debug_finished = DummySignal()
            self.breakpoint_update_acknowledged = DummySignal()

    monkeypatch.setattr(debug_module, "DebugManager", FakeDebugManager)
    forwarded_output = []
    window = SimpleNamespace(
        _on_process_output=lambda text, stream: forwarded_output.append((text, stream))
    )
    controller = DebugController(MainWindowContext(window, None, None, None))

    controller._create_debug_manager()
    manager = controller._debug_manager
    manager.debug_output.emit("hello", "stdout")

    assert manager.parent is controller
    assert manager.state_changed._callbacks == [controller._on_debug_state_changed]
    assert manager.paused._callbacks == [controller._on_debug_paused]
    assert manager.resumed._callbacks == [controller._on_debug_resumed]
    assert manager.eval_result._callbacks == [controller._on_debug_eval_result]
    assert manager.debug_started._callbacks == [controller._on_debug_started]
    assert manager.debug_finished._callbacks == [controller._on_debug_finished]
    assert manager.breakpoint_update_acknowledged._callbacks == [
        controller._on_breakpoint_update_acknowledged
    ]
    assert forwarded_output == [("hello", "stdout")]


class CursorBreakpointEditor:
    def __init__(self, file_path="cursor.py"):
        self.file_path = file_path
        self.toggled = []
        self._breakpoints = set()
        self.cleared = 0
        self.breakpoints_changed = DummySignal()
        self.pending = []
        self.verifications = []

    def getCursorPosition(self):
        return 12, 4

    def toggle_breakpoint(self, line):
        self.toggled.append(line)
        if line in self._breakpoints:
            self._breakpoints.discard(line)
        else:
            self._breakpoints.add(line)
        self.breakpoints_changed.emit(self._breakpoints.copy())

    def get_breakpoints(self):
        return self._breakpoints

    def clear_breakpoints(self):
        changed = bool(self._breakpoints)
        self._breakpoints.clear()
        self.cleared += 1
        if changed:
            self.breakpoints_changed.emit(set())

    def mark_breakpoints_pending(self, lines=None):
        self.pending.append(set(lines or ()))

    def set_breakpoint_verification(self, accepted, rejected=()):
        self.verifications.append((set(accepted), rejected))


def test_breakpoint_actions_use_current_editor_and_all_open_tabs(monkeypatch):
    monkeypatch.setattr(debug_module, "CodeEditor", CursorBreakpointEditor)
    editor = CursorBreakpointEditor()
    other_editor = CursorBreakpointEditor()
    tabs = FakeTabManager([editor, object(), other_editor])
    controller = DebugController(
        MainWindowContext(SimpleNamespace(_tab_manager=tabs), None, None, None)
    )

    controller.action_toggle_breakpoint()
    controller.action_clear_all_breakpoints()

    assert editor.toggled == [12]
    assert editor.cleared == 1
    assert other_editor.cleared == 1


def test_toggle_breakpoint_ignores_non_python_current_editor(monkeypatch):
    monkeypatch.setattr(debug_module, "CodeEditor", CursorBreakpointEditor)
    editor = CursorBreakpointEditor("requirements.txt")
    tabs = FakeTabManager([editor])
    controller = DebugController(
        MainWindowContext(SimpleNamespace(_tab_manager=tabs), None, None, None)
    )

    controller.action_toggle_breakpoint()

    assert editor.toggled == []


def test_breakpoint_actions_update_active_debug_session(monkeypatch):
    monkeypatch.setattr(debug_module, "CodeEditor", CursorBreakpointEditor)
    editor = CursorBreakpointEditor("live.py")
    tabs = FakeTabManager([editor])
    updates = []
    manager = SimpleNamespace(
        state=DebugState.RUNNING,
        update_breakpoints=lambda breakpoints: updates.append(breakpoints),
    )
    controller = DebugController(
        MainWindowContext(
            SimpleNamespace(_tab_manager=tabs, _debug_manager=manager),
            None,
            None,
            None,
        )
    )
    controller._wire_editor_breakpoints(editor)

    controller.action_toggle_breakpoint()
    controller.action_clear_all_breakpoints()

    assert updates == [{"live.py": [13]}, {}]
    assert editor.pending == [{12}, set()]


def test_editor_breakpoint_signal_is_wired_once_for_gutter_and_edit_updates(
    monkeypatch,
):
    monkeypatch.setattr(debug_module, "CodeEditor", CursorBreakpointEditor)
    editor = CursorBreakpointEditor("live.py")
    tabs = FakeTabManager([editor])
    updates = []
    manager = SimpleNamespace(
        state=DebugState.RUNNING,
        update_breakpoints=lambda breakpoints: updates.append(breakpoints),
    )
    controller = DebugController(
        MainWindowContext(
            SimpleNamespace(_tab_manager=tabs, _debug_manager=manager),
            None,
            None,
            None,
        )
    )

    controller._wire_editor_breakpoints(editor)
    controller._wire_editor_breakpoints(editor)
    editor._breakpoints = {2}
    editor.breakpoints_changed.emit({2})
    editor._breakpoints = {4}
    editor.breakpoints_changed.emit({4})

    assert updates == [{"live.py": [3]}, {"live.py": [5]}]
    assert editor.pending == [{2}, {4}]
    assert len(editor.breakpoints_changed._callbacks) == 1


def test_breakpoint_acknowledgement_updates_matching_editor_state(monkeypatch, tmp_path):
    monkeypatch.setattr(debug_module, "CodeEditor", CursorBreakpointEditor)
    script = tmp_path / "ack.py"
    editor = CursorBreakpointEditor(str(script))
    editor._breakpoints = {0, 4, 7}
    other = CursorBreakpointEditor(str(tmp_path / "other.py"))
    tabs = FakeTabManager([editor, other])
    controller = DebugController(
        MainWindowContext(SimpleNamespace(_tab_manager=tabs), None, None, None)
    )

    controller._on_breakpoint_update_acknowledged(
        {str(script): [1, 5]},
        {str(script): {8: "No executable code on this line"}},
    )

    assert editor.verifications == [
        ({0, 4}, {7: "No executable code on this line"})
    ]
    assert other.verifications == []


def test_breakpoint_changes_do_not_sync_while_debugger_is_idle(monkeypatch):
    monkeypatch.setattr(debug_module, "CodeEditor", CursorBreakpointEditor)
    editor = CursorBreakpointEditor("idle.py")
    updates = []
    manager = SimpleNamespace(
        state=DebugState.IDLE,
        update_breakpoints=lambda breakpoints: updates.append(breakpoints),
    )
    controller = DebugController(
        MainWindowContext(
            SimpleNamespace(
                _tab_manager=FakeTabManager([editor]),
                _debug_manager=manager,
            ),
            None,
            None,
            None,
        )
    )
    controller._wire_editor_breakpoints(editor)

    editor.toggle_breakpoint(3)

    assert updates == []
    assert editor.pending == []


def test_closed_editor_breakpoint_updates_are_coalesced(monkeypatch):
    monkeypatch.setattr(debug_module, "CodeEditor", CursorBreakpointEditor)
    editor = CursorBreakpointEditor("closing.py")
    editor._breakpoints = {0}
    tabs = FakeTabManager([editor])
    updates = []
    scheduled = []
    manager = SimpleNamespace(
        state=DebugState.RUNNING,
        update_breakpoints=lambda breakpoints: updates.append(breakpoints),
    )
    controller = DebugController(
        MainWindowContext(
            SimpleNamespace(_tab_manager=tabs, _debug_manager=manager),
            None,
            None,
            None,
        )
    )
    monkeypatch.setattr(
        debug_module.QTimer,
        "singleShot",
        lambda delay, callback: scheduled.append((delay, callback)),
    )

    controller._on_editor_closed(editor)
    controller._on_editor_closed(editor)
    tabs.widgets.clear()

    assert len(scheduled) == 1
    assert updates == []

    scheduled[0][1]()

    assert updates == [{}]


class RecordingDebugManager:
    def __init__(self, state):
        self.state = state
        self.calls = []

    def send_continue(self):
        self.calls.append("continue")

    def send_step_over(self):
        self.calls.append("step_over")

    def send_step_into(self):
        self.calls.append("step_into")

    def send_step_out(self):
        self.calls.append("step_out")

    def stop_debug(self):
        self.calls.append("stop")


def test_debug_control_actions_only_step_when_paused():
    manager = RecordingDebugManager(DebugState.RUNNING)
    controller = DebugController(
        MainWindowContext(SimpleNamespace(_debug_manager=manager), None, None, None)
    )

    controller.action_debug_continue()
    controller.action_debug_step_over()
    controller.action_debug_step_into()
    controller.action_debug_step_out()
    controller.action_stop_debug()
    assert manager.calls == ["stop"]

    manager.state = DebugState.PAUSED
    controller.action_debug_continue()
    controller.action_debug_step_over()
    controller.action_debug_step_into()
    controller.action_debug_step_out()

    assert manager.calls == ["stop", "continue", "step_over", "step_into", "step_out"]


def test_start_debug_returns_for_busy_missing_editor_and_cancelled_save_as(monkeypatch, tmp_path):
    monkeypatch.setattr(debug_module, "CodeEditor", StartDebugEditor)
    calls = []
    settings = SimpleNamespace(get=lambda key, default=None: True)
    window = SimpleNamespace(
        _settings=settings,
        _debug_manager=SimpleNamespace(
            state=DebugState.RUNNING,
            start_debug=lambda *args: calls.append(args),
        ),
        _tab_manager=FakeTabManager([StartDebugEditor(str(tmp_path / "busy.py"))]),
    )
    controller = DebugController(MainWindowContext(window, settings, None, None))
    controller.action_start_debug()
    assert calls == []

    window._debug_manager.state = DebugState.IDLE
    window._tab_manager = FakeTabManager([])
    controller.action_start_debug()
    assert calls == []

    unsaved = StartDebugEditor(None)
    window._tab_manager = FakeTabManager([unsaved])
    window.action_save_as = lambda: calls.append("save_as")
    controller.action_start_debug()

    assert calls == ["save_as"]


def test_debug_state_running_disables_run_without_showing_paused_panels():
    calls = []
    run_action = FakeAction()
    window = SimpleNamespace(
        action_run_file=lambda: None,
        _run_action=run_action,
        _run_selection_action=FakeAction(),
        _debug_action=FakeAction(),
        _debug_separator=FakeAction(),
        _step_over_action=FakeAction(),
        _step_into_action=FakeAction(),
        _step_out_action=FakeAction(),
        _status_bar_manager=SimpleNamespace(
            update_debug_state=lambda state: calls.append(("state", state))
        ),
    )
    controller = DebugController(MainWindowContext(window, None, None, None))

    controller._on_debug_state_changed(DebugState.RUNNING)

    assert run_action.enabled is False
    assert window._run_selection_action.enabled is False
    assert window._debug_action.enabled is False
    assert window._debug_separator.visible is True
    assert window._step_over_action.enabled is False
    assert calls == [("state", DebugState.RUNNING)]


def test_debug_pause_opens_missing_file_in_new_tab(monkeypatch, tmp_path):
    monkeypatch.setattr(debug_module, "CodeEditor", StartDebugEditor)
    script = tmp_path / "new_tab.py"
    script.write_text("answer = 42\n", encoding="utf-8")
    calls = []

    class OpeningTabs(FakeTabManager):
        def __init__(self):
            super().__init__([])

        def open_file_in_tab(
            self,
            path,
            content,
            *,
            large_file_mode=False,
        ):
            calls.append(("open", path, content, large_file_mode))
            editor = StartDebugEditor(path)
            self.widgets.append(editor)
            return editor

    tabs = OpeningTabs()
    window = SimpleNamespace(
        _tab_manager=tabs,
        _read_editor_file=lambda path: ("answer = 42\n", True),
        _file_manager=SimpleNamespace(read_file=lambda path: "answer = 42\n"),
        _variable_inspector=SimpleNamespace(
            update_variables=lambda variables: calls.append(("vars", variables)),
            show=lambda: calls.append("vars_show"),
            raise_=lambda: calls.append("vars_raise"),
        ),
        _call_stack_panel=SimpleNamespace(
            update_call_stack=lambda stack: calls.append(("stack", stack)),
            show=lambda: calls.append("stack_show"),
        ),
        _watch_panel=SimpleNamespace(
            show=lambda: calls.append("watch_show"),
            request_all_evaluations=lambda: calls.append("watch_eval"),
        ),
    )
    controller = DebugController(MainWindowContext(window, None, None, None))

    controller._on_debug_paused(str(script), 1, {}, [])

    opened_editor = tabs.widgets[0]
    assert calls[0] == ("open", str(script), "answer = 42\n", True)
    assert opened_editor.current_lines == [1]
    assert opened_editor.focused is True


def test_debug_pause_ignores_non_text_workspace_reader_payload(tmp_path):
    script = tmp_path / "invalid_reader_payload.py"
    script.write_text("answer = 42\n", encoding="utf-8")
    opened = []

    tabs = FakeTabManager([])
    tabs.open_file_in_tab = lambda *args, **kwargs: opened.append(
        (args, kwargs)
    )
    window = SimpleNamespace(
        _tab_manager=tabs,
        _read_editor_file=lambda path: (b"not decoded text", False),
    )
    controller = DebugController(MainWindowContext(window, None, None, None))

    controller._on_debug_paused(str(script), 0, {}, [])

    assert opened == []


def test_debug_started_resumed_eval_and_finished_reset_ui(monkeypatch, tmp_path):
    monkeypatch.setattr(debug_module, "CodeEditor", StartDebugEditor)
    editor = StartDebugEditor(str(tmp_path / "done.py"))
    output = FakeOutputPanel()
    calls = []
    run_file = lambda: calls.append("run_file")
    run_action = FakeAction()
    controller_window = SimpleNamespace(
        action_run_file=run_file,
        _run_action=run_action,
        _run_selection_action=FakeAction(),
        _debug_action=FakeAction(),
        _stop_action=FakeAction(),
        _debug_separator=FakeAction(),
        _step_over_action=FakeAction(),
        _step_into_action=FakeAction(),
        _step_out_action=FakeAction(),
        _output_panel=output,
        _tab_manager=FakeTabManager([editor]),
        _status_bar_manager=SimpleNamespace(
            show_message=lambda message: calls.append(("message", message))
        ),
        _variable_inspector=SimpleNamespace(
            clear_variables=lambda: calls.append("clear_vars"),
            hide=lambda: calls.append("hide_vars"),
        ),
        _call_stack_panel=SimpleNamespace(
            clear_stack=lambda: calls.append("clear_stack"),
            hide=lambda: calls.append("hide_stack"),
        ),
        _watch_panel=SimpleNamespace(
            update_value=lambda expr, result, error: calls.append((expr, result, error)),
            clear_values=lambda: calls.append("clear_watches"),
            hide=lambda: calls.append("hide_watches"),
        ),
    )
    controller = DebugController(MainWindowContext(controller_window, None, None, None))
    run_action.triggered.connect(controller.action_debug_continue)
    controller._run_is_continue = True

    controller._on_debug_started("Debugging done.py")
    controller._on_debug_eval_result("answer", "42", "")
    editor.current_lines = [3]
    controller._on_debug_resumed()
    controller._on_debug_finished(0, "Debug finished")

    assert output.running is False
    assert output.outputs == [
        (">>> Debugging done.py\n", "system"),
        (">>> Debug finished\n", "system"),
    ]
    assert controller_window._stop_action.enabled is False
    assert controller_window._run_selection_action.enabled is True
    assert run_action.tooltip == "Run File (F5)"
    assert editor.current_lines == []
    assert editor.verifications == [(set(), {})]
    assert ("answer", "42", "") in calls
    assert "clear_vars" in calls
    assert "hide_watches" in calls


def test_create_debug_manager_supports_legacy_or_missing_ack_signal(monkeypatch):
    class LegacyManager:
        def __init__(self, parent):
            self.state_changed = DummySignal()
            self.paused = DummySignal()
            self.resumed = DummySignal()
            self.eval_result = DummySignal()
            self.debug_output = DummySignal()
            self.debug_started = DummySignal()
            self.debug_finished = DummySignal()
            self.breakpoints_updated = DummySignal()

    monkeypatch.setattr(debug_module, "DebugManager", LegacyManager)
    controller = DebugController(
        MainWindowContext(SimpleNamespace(_on_process_output=lambda *args: None), None, None, None)
    )
    controller._create_debug_manager()
    assert controller._debug_manager.breakpoints_updated._callbacks == [
        controller._on_breakpoint_update_acknowledged
    ]

    controller._debug_manager.breakpoint_update_acknowledged = object()
    controller._debug_manager.breakpoints_updated = object()
    monkeypatch.setattr(debug_module, "DebugManager", lambda parent: controller._debug_manager)
    controller._create_debug_manager()


def test_breakpoint_helpers_ignore_non_editors_and_malformed_protocol_lines(monkeypatch):
    monkeypatch.setattr(debug_module, "CodeEditor", CursorBreakpointEditor)
    editor = CursorBreakpointEditor("valid.py")
    editor.mark_breakpoints_pending = None
    editor.set_breakpoint_verification = None
    tabs = FakeTabManager([object(), editor])
    controller = DebugController(
        MainWindowContext(SimpleNamespace(_tab_manager=tabs), None, None, None)
    )

    controller._wire_editor_breakpoints(object())
    controller._mark_breakpoints_pending()
    controller._reset_breakpoint_verification()
    assert controller._protocol_lines_to_editor_lines([None, "bad", 0, -2, "3"]) == {2}

    monkeypatch.setattr(
        debug_module.Path,
        "resolve",
        lambda self: (_ for _ in ()).throw(OSError("bad path")),
    )
    assert controller._normalized_debug_path("valid.py").endswith("valid.py")


def test_breakpoint_ack_handles_iterable_rejections_and_missing_editor_api(monkeypatch):
    monkeypatch.setattr(debug_module, "CodeEditor", CursorBreakpointEditor)
    editor = CursorBreakpointEditor("ack.py")
    editor.set_breakpoint_verification = None
    tabs = FakeTabManager([object(), editor])
    controller = DebugController(
        MainWindowContext(SimpleNamespace(_tab_manager=tabs), None, None, None)
    )

    controller._on_breakpoint_update_acknowledged(
        {"ack.py": [1]},
        {"ack.py": ["bad", 2]},
    )


def test_editor_closed_ignores_idle_or_missing_debug_manager():
    controller = DebugController(MainWindowContext(SimpleNamespace(), None, None, None))
    controller._on_editor_closed()
    controller.window._debug_manager = SimpleNamespace(state=DebugState.IDLE)
    controller._on_editor_closed()


def test_debug_state_without_optional_run_selection_action():
    window = SimpleNamespace(
        action_run_file=lambda: None,
        _run_action=FakeAction(),
        _debug_action=FakeAction(),
        _debug_separator=FakeAction(),
        _step_over_action=FakeAction(),
        _step_into_action=FakeAction(),
        _step_out_action=FakeAction(),
        _status_bar_manager=SimpleNamespace(update_debug_state=lambda state: None),
    )
    controller = DebugController(MainWindowContext(window, None, None, None))
    controller._on_debug_state_changed(DebugState.RUNNING)
    assert window._run_action.enabled is False


def test_debug_pause_uses_string_reader_and_file_manager_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(debug_module, "CodeEditor", StartDebugEditor)
    script = tmp_path / "fallback.py"
    script.write_text("answer = 42\n", encoding="utf-8")
    calls = []

    class OpeningTabs(FakeTabManager):
        def open_file_in_tab(self, path, content, **kwargs):
            calls.append((path, content, kwargs))
            return StartDebugEditor(path)

    panels = dict(
        _variable_inspector=SimpleNamespace(
            update_variables=lambda value: None,
            show=lambda: None,
            raise_=lambda: None,
        ),
        _call_stack_panel=SimpleNamespace(
            update_call_stack=lambda value: None,
            show=lambda: None,
        ),
        _watch_panel=SimpleNamespace(show=lambda: None, request_all_evaluations=lambda: None),
    )
    tabs = OpeningTabs([])
    window = SimpleNamespace(
        _tab_manager=tabs,
        _read_editor_file=lambda path: "answer = 42\n",
        **panels,
    )
    controller = DebugController(MainWindowContext(window, None, None, None))
    controller._clear_debug_markers = lambda: None
    controller._on_debug_paused(str(script), 0, {}, [])
    assert calls == [(str(script), "answer = 42\n", {})]

    del window._read_editor_file
    window._file_manager = SimpleNamespace(read_file=lambda path: "fallback text")
    controller._on_debug_paused(str(script), 0, {}, [])
    assert calls[-1] == (str(script), "fallback text", {})

    window._file_manager.read_file = lambda path: (_ for _ in ()).throw(OSError("no read"))
    before = len(calls)
    controller._on_debug_paused(str(script), 0, {}, [])
    assert len(calls) == before

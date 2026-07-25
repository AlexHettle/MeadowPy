from types import SimpleNamespace

import meadowpy.ui.controllers.execution_controller as execution_module
from meadowpy.ui.controllers.execution_controller import ExecutionController
from meadowpy.ui.controllers.window_context import MainWindowContext
from helpers import DummySignal


class FakeSettings:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


class FakeProcessRunner:
    def __init__(self):
        self.calls = []
        self.file_calls = []
        self.stopped = 0
        self.stdin = []
        self.running = False

    def is_running(self):
        return self.running

    def run_code(self, code, interpreter, working_dir):
        self.calls.append((code, interpreter, working_dir))

    def run_file(self, file_path, interpreter, working_dir):
        self.file_calls.append((file_path, interpreter, working_dir))

    def stop(self):
        self.stopped += 1
        self.running = False

    def send_stdin(self, text):
        self.stdin.append(text)


class FakeEditor:
    def __init__(self, file_path="work/demo.py", modified=False, selected="print('selected')"):
        self.file_path = file_path
        self.modified = modified
        self.selected = selected
        self.cursor = (0, 0)
        self.lines = ["print('line')\n"]
        self.saved = False

    def selectedText(self):
        return self.selected

    def getCursorPosition(self):
        return self.cursor

    def text(self, line=None):
        if line is None:
            return "".join(self.lines)
        return self.lines[line]

    def isModified(self):
        return self.modified


def make_controller(settings):
    runner = FakeProcessRunner()
    editor = FakeEditor()
    window = SimpleNamespace(
        _settings=settings,
        _process_runner=runner,
        _tab_manager=SimpleNamespace(current_editor=lambda: editor),
        _interpreter_manager=SimpleNamespace(get_interpreter=lambda settings, file_path: "python.exe"),
        _output_panel=SimpleNamespace(clear_output=lambda: None, show=lambda: None, raise_=lambda: None),
    )
    ctx = MainWindowContext(window=window, settings=settings, file_manager=None, recent_files=None)
    return ExecutionController(ctx), window, runner


def test_resolve_working_dir_prefers_project_when_configured(tmp_path):
    settings = FakeSettings({"run.working_directory": "project", "general.project_folder": str(tmp_path)})
    controller, _, _ = make_controller(settings)

    assert controller._resolve_working_dir("C:/work/demo.py") == str(tmp_path)


def test_run_selection_uses_selected_code_and_interpreter():
    settings = FakeSettings({
        "run.working_directory": "file",
        "run.clear_output_before_run": True,
        "run.show_output_panel": True,
    })
    controller, _, runner = make_controller(settings)

    controller.action_run_selection()

    assert runner.calls == [("print('selected')", "python.exe", "work")]


def test_run_selection_ignores_saved_non_python_file(tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_text("not python", encoding="utf-8")
    settings = FakeSettings({
        "run.working_directory": "file",
        "run.clear_output_before_run": True,
        "run.show_output_panel": True,
    })
    runner = FakeProcessRunner()
    editor = FakeEditor(str(notes), selected="plain text")
    output = FakeOutputPanel()
    window = SimpleNamespace(
        _settings=settings,
        _process_runner=runner,
        _tab_manager=SimpleNamespace(current_editor=lambda: editor),
        _output_panel=output,
    )
    controller = ExecutionController(
        MainWindowContext(window=window, settings=settings, file_manager=None, recent_files=None)
    )

    controller.action_run_selection()

    assert runner.calls == []
    assert output.cleared == 0
    assert output.shown == 0


class FakeAction:
    def __init__(self):
        self.enabled = None

    def setEnabled(self, value):
        self.enabled = value


class FakeOutputPanel:
    def __init__(self):
        self.cleared = 0
        self.shown = 0
        self.raised = 0
        self.outputs = []
        self.running = None
        self.input_texts = []

    def clear_output(self):
        self.cleared += 1

    def show(self):
        self.shown += 1

    def raise_(self):
        self.raised += 1

    def append_output(self, text, stream):
        self.outputs.append((text, stream))

    def set_running(self, running):
        self.running = running

    def update_repl_prompt(self, *args):
        pass

    def set_input_text(self, text):
        self.input_texts.append(text)


def test_run_file_saves_modified_editor_and_uses_project_working_dir(tmp_path):
    script = tmp_path / "demo.py"
    script.write_text("print('run')", encoding="utf-8")
    settings = FakeSettings({
        "run.working_directory": "project",
        "general.project_folder": str(tmp_path),
        "run.save_before_run": True,
        "run.clear_output_before_run": True,
        "run.show_output_panel": True,
    })
    runner = FakeProcessRunner()
    editor = FakeEditor(str(script), modified=True)
    output = FakeOutputPanel()
    calls = []
    window = SimpleNamespace(
        _settings=settings,
        _process_runner=runner,
        _tab_manager=SimpleNamespace(current_editor=lambda: editor),
        _interpreter_manager=SimpleNamespace(
            get_interpreter=lambda settings, file_path: "python.exe"
        ),
        _output_panel=output,
        action_save=lambda: calls.append("save") or True,
    )
    controller = ExecutionController(
        MainWindowContext(window=window, settings=settings, file_manager=None, recent_files=None)
    )

    controller.action_run_file()

    assert calls == ["save"]
    assert output.cleared == 1
    assert output.shown == 1
    assert output.raised == 1
    assert runner.file_calls == [(str(script), "python.exe", str(tmp_path))]


def test_run_file_aborts_when_save_before_run_fails(tmp_path):
    script = tmp_path / "demo.py"
    script.write_text("print('old')", encoding="utf-8")
    settings = FakeSettings({
        "run.working_directory": "project",
        "general.project_folder": str(tmp_path),
        "run.save_before_run": True,
        "run.clear_output_before_run": True,
        "run.show_output_panel": True,
    })
    runner = FakeProcessRunner()
    editor = FakeEditor(str(script), modified=True)
    output = FakeOutputPanel()
    calls = []
    window = SimpleNamespace(
        _settings=settings,
        _process_runner=runner,
        _tab_manager=SimpleNamespace(current_editor=lambda: editor),
        _output_panel=output,
        action_save=lambda: calls.append("save") or False,
    )
    controller = ExecutionController(
        MainWindowContext(window=window, settings=settings, file_manager=None, recent_files=None)
    )

    controller.action_run_file()

    assert calls == ["save"]
    assert output.cleared == 0
    assert output.shown == 0
    assert runner.file_calls == []


def test_run_file_saves_untitled_editor_before_running(tmp_path):
    script = tmp_path / "new_script.py"
    settings = FakeSettings({
        "run.working_directory": "file",
        "run.save_before_run": False,
        "run.clear_output_before_run": True,
        "run.show_output_panel": True,
    })
    runner = FakeProcessRunner()
    editor = FakeEditor(None)
    output = FakeOutputPanel()
    save_as_calls = []
    window = SimpleNamespace(
        _settings=settings,
        _process_runner=runner,
        _tab_manager=SimpleNamespace(current_editor=lambda: editor),
        _interpreter_manager=SimpleNamespace(
            get_interpreter=lambda settings, file_path: "python.exe"
        ),
        _output_panel=output,
    )
    controller = ExecutionController(
        MainWindowContext(window=window, settings=settings, file_manager=None, recent_files=None)
    )

    def save_as():
        save_as_calls.append("save_as")
        editor.file_path = str(script)
        return True

    controller.action_save_as = save_as

    controller.action_run_file()

    assert save_as_calls == ["save_as"]
    assert output.cleared == 1
    assert output.shown == 1
    assert output.raised == 1
    assert runner.file_calls == [(str(script), "python.exe", str(tmp_path))]


def test_run_file_ignores_saved_non_python_file(tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_text("not python", encoding="utf-8")
    settings = FakeSettings({
        "run.working_directory": "file",
        "run.save_before_run": False,
        "run.clear_output_before_run": True,
        "run.show_output_panel": True,
    })
    runner = FakeProcessRunner()
    editor = FakeEditor(str(notes))
    output = FakeOutputPanel()
    window = SimpleNamespace(
        _settings=settings,
        _process_runner=runner,
        _tab_manager=SimpleNamespace(current_editor=lambda: editor),
        _output_panel=output,
    )
    controller = ExecutionController(
        MainWindowContext(window=window, settings=settings, file_manager=None, recent_files=None)
    )

    controller.action_run_file()

    assert runner.file_calls == []
    assert output.cleared == 0
    assert output.shown == 0


def test_run_selection_falls_back_to_current_line_when_selection_is_empty():
    settings = FakeSettings({
        "run.working_directory": "file",
        "run.clear_output_before_run": False,
        "run.show_output_panel": False,
    })
    controller, window, runner = make_controller(settings)
    window._tab_manager.current_editor().selected = ""

    controller.action_run_selection()

    assert runner.calls == [("print('line')\n", "python.exe", "work")]


def test_process_lifecycle_updates_controls_and_routes_stdin():
    output = FakeOutputPanel()
    debug_running = {"value": False}
    debug_stdin = []
    debug_manager = SimpleNamespace(
        is_running=lambda: debug_running["value"],
        send_stdin=lambda text: debug_stdin.append(text),
    )
    runner = FakeProcessRunner()
    status = SimpleNamespace(messages=[], show_message=lambda msg: status.messages.append(msg))
    window = SimpleNamespace(
        _output_panel=output,
        _run_action=FakeAction(),
        _run_selection_action=FakeAction(),
        _debug_action=FakeAction(),
        _stop_action=FakeAction(),
        _status_bar_manager=status,
        _debug_manager=debug_manager,
        _process_runner=runner,
    )
    refreshes = []
    window._update_run_action_enabled = lambda: refreshes.append("refresh")
    controller = ExecutionController(
        MainWindowContext(window=window, settings=None, file_manager=None, recent_files=None)
    )

    controller._on_process_started("Running: demo.py")
    assert output.running is True
    assert window._run_action.enabled is False
    assert window._run_selection_action.enabled is False
    assert window._debug_action.enabled is False
    assert window._stop_action.enabled is True
    controller._on_process_finished(0, "Process finished successfully")
    controller._on_stdin_submitted("hello\n")
    debug_running["value"] = True
    controller._on_stdin_submitted("debug input\n")

    assert output.outputs == [
        (">>> Running: demo.py\n", "system"),
        (">>> Process finished successfully\n", "system"),
    ]
    assert output.running is False
    assert window._run_action.enabled is True
    assert window._run_selection_action.enabled is True
    assert window._debug_action.enabled is True
    assert window._stop_action.enabled is False
    assert refreshes == ["refresh"]
    assert status.messages == ["Running: demo.py", "Process finished successfully"]
    assert runner.stdin == ["hello\n"]
    assert debug_stdin == ["debug input\n"]


def test_process_stderr_output_appends_beginner_hint():
    output = FakeOutputPanel()
    window = SimpleNamespace(_output_panel=output)
    controller = ExecutionController(
        MainWindowContext(window=window, settings=None, file_manager=None, recent_files=None)
    )

    controller._on_process_output(
        "NameError: name 'total' is not defined\n",
        "stderr",
    )

    assert output.outputs[0] == (
        "NameError: name 'total' is not defined\n",
        "stderr",
    )
    assert output.outputs[1][1] == "hint"
    assert "Python doesn't recognize 'total'." in output.outputs[1][0]


def test_stop_process_prefers_active_debug_session():
    calls = []
    runner = FakeProcessRunner()
    debug_running = {"value": True}
    debug_manager = SimpleNamespace(
        is_running=lambda: debug_running["value"],
        stop_debug=lambda: calls.append("debug_stop"),
    )
    window = SimpleNamespace(
        _debug_manager=debug_manager,
        _process_runner=runner,
    )
    controller = ExecutionController(
        MainWindowContext(window=window, settings=None, file_manager=None, recent_files=None)
    )

    controller.action_stop_process()
    debug_running["value"] = False
    controller.action_stop_process()

    assert calls == ["debug_stop"]
    assert runner.stopped == 1


def test_repl_restart_stops_running_work_and_preserves_history_navigation():
    calls = []
    output = FakeOutputPanel()
    repl = SimpleNamespace(
        is_running=True,
        stop=lambda: calls.append("repl_stop"),
        add_to_history=lambda text: calls.append(("history", text)),
        send_input=lambda text: calls.append(("send", text)),
        history_up=lambda: "previous",
        history_down=lambda: "",
    )
    window = SimpleNamespace(
        _debug_manager=SimpleNamespace(is_running=lambda: False, stop_debug=lambda: calls.append("debug_stop")),
        _process_runner=SimpleNamespace(is_running=lambda: True, stop=lambda: calls.append("process_stop")),
        _output_panel=output,
        _repl_manager=repl,
        _start_repl=lambda: calls.append("start_repl"),
    )
    controller = ExecutionController(
        MainWindowContext(window=window, settings=None, file_manager=None, recent_files=None)
    )
    controller._start_repl = lambda: calls.append("start_repl")

    controller._on_repl_input("x = 1")
    controller._on_repl_restart()
    controller._on_repl_history_up()
    controller._on_repl_history_down()

    assert calls == [
        ("history", "x = 1"),
        ("send", "x = 1"),
        "process_stop",
        "repl_stop",
        "start_repl",
    ]
    assert output.cleared == 1
    assert output.input_texts == ["previous", ""]


class FakeProcessFactory(FakeProcessRunner):
    def __init__(self, parent=None):
        super().__init__()
        self.output_received = DummySignal()
        self.process_started = DummySignal()
        self.process_finished = DummySignal()


class FakeReplFactory:
    def __init__(self, parent=None):
        self.output_received = DummySignal()
        self.repl_started = DummySignal()
        self.repl_stopped = DummySignal()
        self.prompt_ready = DummySignal()
        self.started = []

    def start(self, interpreter, working_dir):
        self.started.append((interpreter, working_dir))


class SignalOutputPanel(FakeOutputPanel):
    def __init__(self):
        super().__init__()
        self.repl_input_submitted = DummySignal()
        self.repl_restart_requested = DummySignal()
        self.repl_history_up = DummySignal()
        self.repl_history_down = DummySignal()


def test_create_process_and_repl_managers_wire_expected_signals(monkeypatch):
    monkeypatch.setattr(execution_module, "ProcessRunner", FakeProcessFactory)
    monkeypatch.setattr(execution_module, "ReplManager", FakeReplFactory)
    output = SignalOutputPanel()
    window = SimpleNamespace(_output_panel=output)
    controller = ExecutionController(
        MainWindowContext(window=window, settings=None, file_manager=None, recent_files=None)
    )

    controller._create_process_runner()
    controller._create_repl_manager()

    assert controller._on_process_output in controller._process_runner.output_received._callbacks
    assert controller._on_process_started in controller._process_runner.process_started._callbacks
    assert controller._on_process_finished in controller._process_runner.process_finished._callbacks
    assert controller._on_repl_output in controller._repl_manager.output_received._callbacks
    assert output.update_repl_prompt in controller._repl_manager.prompt_ready._callbacks
    assert controller._on_repl_input in output.repl_input_submitted._callbacks


def test_run_file_handles_running_process_prompt_save_as_and_cancel(monkeypatch, tmp_path):
    prompts = []
    monkeypatch.setattr(
        execution_module.QMessageBox,
        "question",
        lambda *args, **kwargs: prompts.append(args[2]) or execution_module.QMessageBox.StandardButton.No,
    )
    settings = FakeSettings({
        "run.working_directory": "file",
        "run.save_before_run": False,
        "run.clear_output_before_run": False,
        "run.show_output_panel": False,
    })
    runner = FakeProcessRunner()
    runner.running = True
    editor = FakeEditor(str(tmp_path / "demo.py"))
    window = SimpleNamespace(
        _settings=settings,
        _process_runner=runner,
        _tab_manager=SimpleNamespace(current_editor=lambda: editor),
    )
    controller = ExecutionController(
        MainWindowContext(window=window, settings=settings, file_manager=None, recent_files=None)
    )

    controller.action_run_file()
    assert prompts == ["A process is already running. Stop it and run again?"]
    assert runner.file_calls == []
    assert runner.stopped == 0

    monkeypatch.setattr(
        execution_module.QMessageBox,
        "question",
        lambda *args, **kwargs: execution_module.QMessageBox.StandardButton.Yes,
    )
    runner.running = True
    editor.file_path = None
    save_as_calls = []
    controller.action_save_as = lambda: save_as_calls.append("save_as") or False
    controller.action_run_file()
    assert runner.stopped == 1
    assert save_as_calls == ["save_as"]
    assert runner.file_calls == []


def test_run_selection_ignores_empty_code_and_running_process_decline(monkeypatch):
    settings = FakeSettings({
        "run.working_directory": "file",
        "run.clear_output_before_run": False,
        "run.show_output_panel": False,
    })
    controller, window, runner = make_controller(settings)
    runner.running = True
    monkeypatch.setattr(
        execution_module.QMessageBox,
        "question",
        lambda *args, **kwargs: execution_module.QMessageBox.StandardButton.No,
    )

    controller.action_run_selection()
    assert runner.calls == []

    runner.running = False
    editor = window._tab_manager.current_editor()
    editor.selected = ""
    editor.lines = ["   \n"]
    controller.action_run_selection()
    assert runner.calls == []


def test_select_interpreter_and_create_venv_dialog(monkeypatch):
    selected = []
    dialogs = []
    interpreters = [
        SimpleNamespace(label="Python A", path="a.exe"),
        SimpleNamespace(label="Python B", path="b.exe"),
    ]
    settings = FakeSettings({})
    window = SimpleNamespace(
        _settings=settings,
        _tab_manager=SimpleNamespace(current_editor=lambda: FakeEditor("demo.py")),
        _interpreter_manager=SimpleNamespace(detect_interpreters=lambda file_path: interpreters),
        _update_interpreter_label=lambda: selected.append("updated"),
    )
    controller = ExecutionController(
        MainWindowContext(window=window, settings=settings, file_manager=None, recent_files=None)
    )
    controller._update_interpreter_label = lambda: selected.append("updated")
    monkeypatch.setattr(
        execution_module.QInputDialog,
        "getItem",
        lambda *args, **kwargs: ("Python B  (b.exe)", True),
    )

    controller.action_select_interpreter()

    assert settings.values["run.python_interpreter"] == "b.exe"
    assert selected == ["updated"]

    from meadowpy.ui.dialogs import venv_dialog

    class FakeVenvDialog:
        def __init__(self, manager, file_path, parent=None):
            dialogs.append((manager, file_path, parent))

        def exec(self):
            dialogs.append("exec")

    monkeypatch.setattr(venv_dialog, "VenvDialog", FakeVenvDialog)
    controller.action_create_venv()
    assert dialogs[-2][1] == "demo.py"
    assert dialogs[-1] == "exec"


def test_select_interpreter_cancel_keeps_existing_choice(monkeypatch):
    selected = []
    detected_paths = []
    dialog_items = []
    interpreters = [
        SimpleNamespace(label="Python A", path="a.exe"),
        SimpleNamespace(label="Python B", path="b.exe"),
    ]
    settings = FakeSettings({"run.python_interpreter": "existing.exe"})
    window = SimpleNamespace(
        _settings=settings,
        _tab_manager=SimpleNamespace(current_editor=lambda: FakeEditor("demo.py")),
        _interpreter_manager=SimpleNamespace(
            detect_interpreters=lambda file_path: detected_paths.append(file_path) or interpreters
        ),
        _update_interpreter_label=lambda: selected.append("updated"),
    )
    controller = ExecutionController(
        MainWindowContext(window=window, settings=settings, file_manager=None, recent_files=None)
    )
    controller._update_interpreter_label = lambda: selected.append("updated")

    def cancel_dialog(parent, title, label, items, current, editable):
        dialog_items.extend(items)
        return "", False

    monkeypatch.setattr(execution_module.QInputDialog, "getItem", cancel_dialog)

    controller.action_select_interpreter()

    assert detected_paths == ["demo.py"]
    assert dialog_items == ["Python A  (a.exe)", "Python B  (b.exe)"]
    assert settings.values["run.python_interpreter"] == "existing.exe"
    assert selected == []


def test_repl_working_dir_start_output_and_restart_debug_branch(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    settings = FakeSettings({"general.project_folder": str(project)})
    editor = FakeEditor(str(tmp_path / "demo.py"))
    output = FakeOutputPanel()
    repl = SimpleNamespace(
        started=[],
        is_running=False,
        start=lambda interpreter, working_dir: repl.started.append((interpreter, working_dir)),
    )
    calls = []
    window = SimpleNamespace(
        _settings=settings,
        _tab_manager=SimpleNamespace(current_editor=lambda: editor),
        _interpreter_manager=SimpleNamespace(get_interpreter=lambda settings, file_path: "python.exe"),
        _repl_manager=repl,
        _output_panel=output,
        _debug_manager=SimpleNamespace(is_running=lambda: True, stop_debug=lambda: calls.append("debug_stop")),
        _process_runner=SimpleNamespace(is_running=lambda: False, stop=lambda: calls.append("process_stop")),
    )
    controller = ExecutionController(
        MainWindowContext(window=window, settings=settings, file_manager=None, recent_files=None)
    )

    assert controller._resolve_repl_working_dir() == str(project)
    settings.values["general.project_folder"] = ""
    assert controller._resolve_repl_working_dir() == str(tmp_path)
    editor.file_path = None
    assert controller._resolve_repl_working_dir()

    controller._start_repl()
    controller._on_repl_output("Traceback NameError: name 'x' is not defined\n", "stderr")
    controller._on_repl_started()
    controller._on_repl_stopped()
    controller._on_repl_restart()

    assert repl.started
    assert output.outputs[-2:] == [
        ("Python console ready.\n", "system"),
        ("Python console stopped.\n", "system"),
    ]
    assert calls == ["debug_stop"]

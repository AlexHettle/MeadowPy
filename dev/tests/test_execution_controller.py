from types import SimpleNamespace

from meadowpy.ui.controllers.execution_controller import ExecutionController
from meadowpy.ui.controllers.window_context import MainWindowContext


class FakeSettings:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


class FakeProcessRunner:
    def __init__(self):
        self.calls = []

    def is_running(self):
        return False

    def run_code(self, code, interpreter, working_dir):
        self.calls.append((code, interpreter, working_dir))


class FakeEditor:
    file_path = "work/demo.py"

    def selectedText(self):
        return "print('selected')"


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

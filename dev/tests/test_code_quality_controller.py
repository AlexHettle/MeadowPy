from types import SimpleNamespace

from meadowpy.ui.controllers.code_quality_controller import CodeQualityController
from meadowpy.ui.controllers.window_context import MainWindowContext


class FakeEditor:
    def __init__(self):
        self.issues = None
        self.cursor = None
        self.focused = False

    def set_lint_issues(self, issues):
        self.issues = issues

    def setCursorPosition(self, line, col):
        self.cursor = (line, col)

    def setFocus(self):
        self.focused = True


class FakeProblemsPanel:
    def __init__(self):
        self.issues = None
        self.error = None

    def update_issues(self, issues):
        self.issues = issues

    def show_linter_error(self, message):
        self.error = message


class FakeStatusBar:
    def __init__(self):
        self.counts = None

    def update_lint_counts(self, errors, warnings):
        self.counts = (errors, warnings)


def make_controller():
    window = SimpleNamespace(
        _tab_manager=SimpleNamespace(current_editor=lambda: None),
        _problems_panel=FakeProblemsPanel(),
        _status_bar_manager=FakeStatusBar(),
    )
    ctx = MainWindowContext(window=window, settings=None, file_manager=None, recent_files=None)
    return CodeQualityController(ctx), window


def test_lint_finished_updates_target_editor_panel_and_status():
    controller, window = make_controller()
    editor = FakeEditor()
    controller._lint_target_editor = editor
    issues = [
        SimpleNamespace(severity="error"),
        SimpleNamespace(severity="warning"),
        SimpleNamespace(severity="warning"),
    ]

    controller._on_lint_finished(issues)

    assert editor.issues == issues
    assert window._problems_panel.issues == issues
    assert window._status_bar_manager.counts == (1, 2)


def test_lint_error_updates_problem_panel_and_clears_counts():
    controller, window = make_controller()

    controller._on_lint_error("flake8 missing")

    assert window._problems_panel.error == "flake8 missing"
    assert window._status_bar_manager.counts == (0, 0)


def test_problem_navigation_moves_current_editor():
    controller, window = make_controller()
    editor = FakeEditor()
    window._tab_manager = SimpleNamespace(current_editor=lambda: editor)

    controller._on_problem_navigate(4, 2)

    assert editor.cursor == (4, 2)
    assert editor.focused is True

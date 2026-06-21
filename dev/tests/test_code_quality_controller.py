from types import SimpleNamespace

import meadowpy.ui.controllers.code_quality_controller as code_quality_module
from meadowpy.ui.controllers.code_quality_controller import CodeQualityController
from meadowpy.ui.controllers.window_context import MainWindowContext


class FakeEditor:
    def __init__(self):
        self.issues = None
        self.cursor = None
        self.focused = False
        self.file_path = "demo.py"
        self.text_value = "print('demo')\n"
        self.cleared = 0

    def set_lint_issues(self, issues):
        self.issues = issues

    def clear_lint_markers(self):
        self.cleared += 1
        self.issues = []

    def text(self):
        return self.text_value

    def setCursorPosition(self, line, col):
        self.cursor = (line, col)

    def setFocus(self):
        self.focused = True


class FakeProblemsPanel:
    def __init__(self):
        self.issues = None
        self.error = None
        self.cleared = 0

    def update_issues(self, issues):
        self.issues = issues

    def show_linter_error(self, message):
        self.error = message

    def clear_issues(self):
        self.cleared += 1
        self.issues = []


class FakeStatusBar:
    def __init__(self):
        self.counts = None
        self.messages = []

    def update_lint_counts(self, errors, warnings):
        self.counts = (errors, warnings)

    def show_message(self, message):
        self.messages.append(message)


class FakeTimer:
    def __init__(self):
        self.starts = 0

    def start(self):
        self.starts += 1


class FakeSettings:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key, default=None):
        return self.values.get(key, default)


def make_controller():
    window = SimpleNamespace(
        _tab_manager=SimpleNamespace(current_editor=lambda: None),
        _problems_panel=FakeProblemsPanel(),
        _status_bar_manager=FakeStatusBar(),
    )
    ctx = MainWindowContext(window=window, settings=None, file_manager=None, recent_files=None)
    return CodeQualityController(ctx), window


def test_lint_finished_updates_target_editor_panel_and_status(monkeypatch):
    monkeypatch.setattr(code_quality_module, "CodeEditor", FakeEditor)
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


def test_editor_text_changed_and_file_saved_debounce_outline_and_lint(monkeypatch):
    monkeypatch.setattr(code_quality_module, "CodeEditor", FakeEditor)
    settings = FakeSettings({
        "editor.linting_enabled": True,
        "editor.lint_on_save": True,
    })
    editor = FakeEditor()
    window = SimpleNamespace(
        _settings=settings,
        _tab_manager=SimpleNamespace(current_editor=lambda: editor),
        _outline_timer=FakeTimer(),
        _lint_timer=FakeTimer(),
        _status_bar_manager=FakeStatusBar(),
    )
    controller = CodeQualityController(MainWindowContext(window, settings, None, None))
    lint_calls = []
    controller._do_lint = lambda: lint_calls.append("lint")

    controller._on_editor_text_changed()
    controller._on_file_saved("C:/work/demo.py")

    assert window._outline_timer.starts == 1
    assert window._lint_timer.starts == 1
    assert window._status_bar_manager.messages == ["Saved: demo.py"]
    assert lint_calls == ["lint"]

    settings.values["editor.linting_enabled"] = False
    controller._on_editor_text_changed()
    assert window._outline_timer.starts == 2
    assert window._lint_timer.starts == 1


def test_outline_refresh_visibility_and_lint_runner_paths(monkeypatch):
    monkeypatch.setattr(code_quality_module, "CodeEditor", FakeEditor)
    editor = FakeEditor()
    symbol_outline = SimpleNamespace(
        visible=True,
        updates=[],
        isVisible=lambda: symbol_outline.visible,
        update_symbols=lambda text: symbol_outline.updates.append(text),
    )
    lint_runner = SimpleNamespace(
        calls=[],
        run_lint=lambda text, path, linter, include_style_issues: lint_runner.calls.append(
            (text, path, linter, include_style_issues)
        ),
    )
    settings = FakeSettings({
        "editor.linting_enabled": True,
        "editor.linter": "flake8",
        "editor.show_lint_style_issues": False,
    })
    window = SimpleNamespace(
        _settings=settings,
        _tab_manager=SimpleNamespace(current_editor=lambda: editor),
        _symbol_outline=symbol_outline,
        _lint_runner=lint_runner,
    )
    controller = CodeQualityController(MainWindowContext(window, settings, None, None))

    controller._do_refresh_outline()
    controller._on_outline_visibility_changed(True)
    controller._refresh_symbol_outline(editor)
    controller._do_lint()

    assert symbol_outline.updates == [editor.text_value, editor.text_value, editor.text_value]
    assert lint_runner.calls == [(editor.text_value, "demo.py", "flake8", False)]
    assert controller._lint_target_editor is editor

    symbol_outline.visible = False
    settings.values["editor.linting_enabled"] = False
    controller._refresh_symbol_outline(editor)
    controller._do_lint()
    assert len(symbol_outline.updates) == 3
    assert len(lint_runner.calls) == 1


def test_large_file_editor_skips_outline_and_lint(monkeypatch):
    monkeypatch.setattr(code_quality_module, "CodeEditor", FakeEditor)
    editor = FakeEditor()
    editor.large_file_mode = True
    symbol_outline = SimpleNamespace(
        visible=True,
        updates=[],
        cleared=0,
        isVisible=lambda: symbol_outline.visible,
        update_symbols=lambda text: symbol_outline.updates.append(text),
        clear_symbols=lambda: setattr(
            symbol_outline,
            "cleared",
            symbol_outline.cleared + 1,
        ),
    )
    lint_runner = SimpleNamespace(
        calls=[],
        cancels=0,
        run_lint=lambda *args: lint_runner.calls.append(args),
        cancel=lambda: setattr(lint_runner, "cancels", lint_runner.cancels + 1),
    )
    settings = FakeSettings({
        "editor.linting_enabled": True,
        "editor.linter": "flake8",
    })
    window = SimpleNamespace(
        _settings=settings,
        _tab_manager=SimpleNamespace(current_editor=lambda: editor),
        _outline_timer=FakeTimer(),
        _lint_timer=FakeTimer(),
        _symbol_outline=symbol_outline,
        _lint_runner=lint_runner,
        _problems_panel=FakeProblemsPanel(),
        _status_bar_manager=FakeStatusBar(),
    )
    controller = CodeQualityController(MainWindowContext(window, settings, None, None))
    controller._lint_target_editor = editor

    controller._on_editor_text_changed()
    controller._do_refresh_outline()
    controller._on_outline_visibility_changed(True)
    controller._refresh_symbol_outline(editor)
    controller._do_lint()
    controller._on_lint_finished([SimpleNamespace(severity="error")])

    assert window._outline_timer.starts == 0
    assert window._lint_timer.starts == 0
    assert symbol_outline.updates == []
    assert symbol_outline.cleared >= 4
    assert lint_runner.calls == []
    assert lint_runner.cancels >= 2
    assert editor.issues == []
    assert window._problems_panel.issues == []
    assert window._status_bar_manager.counts == (0, 0)


def test_lint_finished_falls_back_to_current_editor_when_target_missing(monkeypatch):
    monkeypatch.setattr(code_quality_module, "CodeEditor", FakeEditor)
    controller, window = make_controller()
    editor = FakeEditor()
    window._tab_manager = SimpleNamespace(current_editor=lambda: editor)

    controller._on_lint_finished([SimpleNamespace(severity="warning")])

    assert editor.issues[0].severity == "warning"
    assert window._status_bar_manager.counts == (0, 1)


def test_lint_skips_and_clears_saved_non_python_editor(monkeypatch, tmp_path):
    monkeypatch.setattr(code_quality_module, "CodeEditor", FakeEditor)
    editor = FakeEditor()
    editor.file_path = str(tmp_path / "notes.txt")
    editor.issues = [SimpleNamespace(severity="error")]
    settings = FakeSettings({
        "editor.linting_enabled": True,
        "editor.linter": "flake8",
    })
    lint_runner = SimpleNamespace(
        calls=[],
        cancels=0,
        run_lint=lambda *args: lint_runner.calls.append(args),
        cancel=lambda: setattr(lint_runner, "cancels", lint_runner.cancels + 1),
    )
    window = SimpleNamespace(
        _settings=settings,
        _tab_manager=SimpleNamespace(current_editor=lambda: editor),
        _lint_runner=lint_runner,
        _problems_panel=FakeProblemsPanel(),
        _status_bar_manager=FakeStatusBar(),
    )
    controller = CodeQualityController(MainWindowContext(window, settings, None, None))

    controller._do_lint()

    assert lint_runner.calls == []
    assert lint_runner.cancels == 1
    assert editor.cleared == 1
    assert window._problems_panel.cleared == 1
    assert window._status_bar_manager.counts == (0, 0)


def test_lint_text_change_does_not_start_timer_for_non_python_file(monkeypatch, tmp_path):
    monkeypatch.setattr(code_quality_module, "CodeEditor", FakeEditor)
    editor = FakeEditor()
    editor.file_path = str(tmp_path / "notes.txt")
    settings = FakeSettings({"editor.linting_enabled": True})
    lint_runner = SimpleNamespace(
        cancels=0,
        cancel=lambda: setattr(lint_runner, "cancels", lint_runner.cancels + 1),
    )
    window = SimpleNamespace(
        _settings=settings,
        _tab_manager=SimpleNamespace(current_editor=lambda: editor),
        _outline_timer=FakeTimer(),
        _lint_timer=FakeTimer(),
        _lint_runner=lint_runner,
        _problems_panel=FakeProblemsPanel(),
        _status_bar_manager=FakeStatusBar(),
    )
    controller = CodeQualityController(MainWindowContext(window, settings, None, None))

    controller._on_editor_text_changed()

    assert window._outline_timer.starts == 1
    assert window._lint_timer.starts == 0
    assert lint_runner.cancels == 1


def test_late_lint_result_for_now_non_python_target_is_ignored(monkeypatch, tmp_path):
    monkeypatch.setattr(code_quality_module, "CodeEditor", FakeEditor)
    controller, window = make_controller()
    window._lint_runner = SimpleNamespace(cancel=lambda: None)
    editor = FakeEditor()
    editor.file_path = str(tmp_path / "notes.txt")
    controller._lint_target_editor = editor

    controller._on_lint_finished([SimpleNamespace(severity="error")])

    assert editor.issues == []
    assert window._problems_panel.issues == []
    assert window._status_bar_manager.counts == (0, 0)

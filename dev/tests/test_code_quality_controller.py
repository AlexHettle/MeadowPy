from types import SimpleNamespace

import meadowpy.ui.controllers.code_quality_controller as code_quality_module
import pytest
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
        self.visible = None
        self.raised = 0

    def update_issues(self, issues):
        self.issues = issues

    def show_linter_error(self, message):
        self.error = message

    def clear_issues(self):
        self.cleared += 1
        self.issues = []

    def setVisible(self, visible):
        self.visible = visible

    def raise_(self):
        self.raised += 1


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
        self.stops = 0

    def start(self):
        self.starts += 1

    def stop(self):
        self.stops += 1


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
    window._tab_manager = SimpleNamespace(current_editor=lambda: editor)
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


def test_background_save_results_are_cached_without_replacing_current_ui(
    monkeypatch,
):
    monkeypatch.setattr(code_quality_module, "CodeEditor", FakeEditor)
    controller, window = make_controller()
    target = FakeEditor()
    current = FakeEditor()
    current.file_path = "other.py"
    editors = [target, current]
    window._tab_manager = SimpleNamespace(
        current_editor=lambda: current,
        count=lambda: len(editors),
        widget=lambda index: editors[index],
    )
    controller._lint_target_editor = target
    issues = [SimpleNamespace(severity="error")]

    controller._on_lint_finished(issues)

    assert target.issues == issues
    assert window._problems_panel.issues is None
    assert window._status_bar_manager.counts is None


def test_late_lint_result_and_error_do_not_replace_another_tabs_state(
    monkeypatch,
):
    monkeypatch.setattr(code_quality_module, "CodeEditor", FakeEditor)
    controller, window = make_controller()
    target = FakeEditor()
    current = FakeEditor()
    current.file_path = "other.py"
    window._tab_manager = SimpleNamespace(current_editor=lambda: current)
    controller._lint_target_editor = target

    controller._on_lint_finished([SimpleNamespace(severity="error")])

    assert target.issues is None
    assert window._problems_panel.issues is None
    assert window._status_bar_manager.counts is None

    controller._lint_target_editor = target
    controller._on_lint_error("late error")
    assert window._problems_panel.error is None


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
    monkeypatch.setattr(
        code_quality_module.QTimer,
        "singleShot",
        lambda delay, callback: callback(),
    )
    settings = FakeSettings({
        "editor.linting_enabled": True,
        "editor.lint_on_save": True,
    })
    editor = FakeEditor()
    editor.file_path = "C:/work/demo.py"
    window = SimpleNamespace(
        _settings=settings,
        _tab_manager=SimpleNamespace(current_editor=lambda: editor),
        _outline_timer=FakeTimer(),
        _lint_timer=FakeTimer(),
        _status_bar_manager=FakeStatusBar(),
    )
    controller = CodeQualityController(MainWindowContext(window, settings, None, None))
    lint_calls = []
    controller._do_lint = lambda target=None: lint_calls.append(target)

    controller._on_editor_text_changed()
    controller._on_file_saved("C:/work/demo.py")

    assert window._outline_timer.starts == 1
    assert window._lint_timer.starts == 1
    assert window._lint_timer.stops == 1
    assert window._status_bar_manager.messages == ["Saved: demo.py"]
    assert lint_calls == [editor]

    settings.values["editor.linting_enabled"] = False
    controller._on_editor_text_changed()
    assert window._outline_timer.starts == 2
    assert window._lint_timer.starts == 1


def test_save_as_lints_after_the_editor_receives_its_new_path(monkeypatch):
    monkeypatch.setattr(code_quality_module, "CodeEditor", FakeEditor)
    callbacks = []
    monkeypatch.setattr(
        code_quality_module.QTimer,
        "singleShot",
        lambda delay, callback: callbacks.append(callback),
    )
    settings = FakeSettings({
        "editor.linting_enabled": True,
        "editor.lint_on_save": True,
    })
    editor = FakeEditor()
    editor.file_path = None
    window = SimpleNamespace(
        _settings=settings,
        _tab_manager=SimpleNamespace(current_editor=lambda: editor),
        _lint_timer=FakeTimer(),
        _status_bar_manager=FakeStatusBar(),
    )
    controller = CodeQualityController(
        MainWindowContext(window, settings, None, None)
    )
    lint_calls = []
    controller._do_lint = lambda target=None: lint_calls.append(target)

    saved_path = "C:/work/new_name.py"
    controller._on_file_saved(saved_path)

    assert len(callbacks) == 1
    assert lint_calls == []
    editor.file_path = saved_path
    callbacks[0]()
    assert lint_calls == [editor]


def test_outline_refresh_visibility_and_lint_runner_paths(monkeypatch):
    monkeypatch.setattr(code_quality_module, "CodeEditor", FakeEditor)
    editor = FakeEditor()
    symbol_outline = SimpleNamespace(
        visible=True,
        updates=[],
        isVisible=lambda: symbol_outline.visible,
        update_symbols=lambda text: symbol_outline.updates.append(text),
    )
    execution_context = object()
    monkeypatch.setattr(
        code_quality_module,
        "resolve_lint_context",
        lambda **kwargs: execution_context,
    )
    lint_runner = SimpleNamespace(
        calls=[],
        run_lint=lambda text, path, linter, include_style_issues, **kwargs: lint_runner.calls.append(
            (text, path, linter, include_style_issues, kwargs)
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
    assert lint_runner.calls == [(
        editor.text_value,
        "demo.py",
        "flake8",
        False,
        {"execution_context": execution_context},
    )]
    assert controller._lint_target_editor is editor

    symbol_outline.visible = False
    settings.values["editor.linting_enabled"] = False
    controller._refresh_symbol_outline(editor)
    controller._do_lint()
    assert len(symbol_outline.updates) == 3
    assert len(lint_runner.calls) == 1


def test_typing_trigger_can_be_disabled_and_clears_stale_results(monkeypatch):
    monkeypatch.setattr(code_quality_module, "CodeEditor", FakeEditor)
    editor = FakeEditor()
    settings = FakeSettings({
        "editor.linting_enabled": True,
        "editor.lint_while_typing": False,
    })
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
    assert editor.cleared == 1
    assert lint_runner.cancels == 1


def test_disabled_linting_never_restores_cached_tab_results(monkeypatch):
    monkeypatch.setattr(code_quality_module, "CodeEditor", FakeEditor)
    editor = FakeEditor()
    editor._lint_issues = [SimpleNamespace(severity="error")]
    settings = FakeSettings({"editor.linting_enabled": False})
    lint_runner = SimpleNamespace(cancels=0)
    lint_runner.cancel = lambda: setattr(
        lint_runner, "cancels", lint_runner.cancels + 1
    )
    window = SimpleNamespace(
        _settings=settings,
        _tab_manager=SimpleNamespace(current_editor=lambda: editor),
        _lint_runner=lint_runner,
        _problems_panel=FakeProblemsPanel(),
        _status_bar_manager=FakeStatusBar(),
    )
    controller = CodeQualityController(
        MainWindowContext(window, settings, None, None)
    )

    controller._show_cached_lint_state(editor)

    assert editor.issues == []
    assert window._problems_panel.issues == []
    assert window._status_bar_manager.counts == (0, 0)


def test_manual_lint_reveals_panel_and_runs_when_enabled():
    settings = FakeSettings({"editor.linting_enabled": True})
    panel = FakeProblemsPanel()
    timer = FakeTimer()
    window = SimpleNamespace(
        _settings=settings,
        _problems_panel=panel,
        _lint_timer=timer,
    )
    controller = CodeQualityController(MainWindowContext(window, settings, None, None))
    calls = []
    controller._do_lint = lambda: calls.append("lint")

    controller.action_run_linter()

    assert calls == ["lint"]
    assert panel.visible is True
    assert panel.raised == 1
    assert timer.stops == 1


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
    window._tab_manager = SimpleNamespace(current_editor=lambda: editor)
    controller._lint_target_editor = editor

    controller._on_lint_finished([SimpleNamespace(severity="error")])

    assert editor.issues == []
    assert window._problems_panel.issues == []
    assert window._status_bar_manager.counts == (0, 0)


def test_create_lint_runner_wires_signals_and_debounce_timer(monkeypatch):
    class Signal:
        def __init__(self):
            self.callbacks = []

        def connect(self, callback):
            self.callbacks.append(callback)

    class Runner:
        def __init__(self, parent):
            self.parent = parent
            self.lint_finished = Signal()
            self.lint_error = Signal()

    class Timer:
        def __init__(self, parent):
            self.parent = parent
            self.timeout = Signal()

        def setSingleShot(self, value):
            self.single_shot = value

        def setInterval(self, value):
            self.interval = value

    monkeypatch.setattr(code_quality_module, "LintRunner", Runner)
    monkeypatch.setattr(code_quality_module, "QTimer", Timer)
    settings = FakeSettings({"editor.lint_delay_ms": 875})
    controller = CodeQualityController(
        MainWindowContext(SimpleNamespace(_settings=settings), settings, None, None)
    )

    controller._create_lint_runner()

    assert controller._lint_runner.lint_finished.callbacks == [controller._on_lint_finished]
    assert controller._lint_runner.lint_error.callbacks == [controller._on_lint_error]
    assert controller._lint_timer.single_shot is True
    assert controller._lint_timer.interval == 875
    assert controller._lint_timer.timeout.callbacks == [controller._do_lint]


def test_saved_path_lookup_searches_all_tabs_and_honors_disabled_settings(monkeypatch):
    monkeypatch.setattr(code_quality_module, "CodeEditor", FakeEditor)
    first = FakeEditor()
    first.file_path = "first.py"
    second = FakeEditor()
    second.file_path = "second.py"
    settings = FakeSettings({"editor.linting_enabled": True, "editor.lint_on_save": True})
    tabs = SimpleNamespace(
        count=lambda: 2,
        widget=lambda index: (first, second)[index],
        current_editor=lambda: first,
    )
    window = SimpleNamespace(_settings=settings, _tab_manager=tabs)
    controller = CodeQualityController(MainWindowContext(window, settings, None, None))
    calls = []
    controller._do_lint = calls.append

    controller._lint_saved_path("second.py")
    controller._lint_saved_path("missing.py")
    settings.values["editor.lint_on_save"] = False
    controller._lint_saved_path("first.py")

    assert calls == [second]
    assert controller._editor_for_file_path(None) is None
    assert controller._same_file_path(None, "first.py") is False


def test_same_file_path_falls_back_to_text_when_resolution_fails(monkeypatch):
    monkeypatch.setattr(
        code_quality_module.Path,
        "resolve",
        lambda self, **kwargs: (_ for _ in ()).throw(OSError("bad path")),
    )
    assert CodeQualityController._same_file_path("same.py", "same.py") is True
    assert CodeQualityController._same_file_path("first.py", "second.py") is False


def test_navigation_and_outline_callbacks_are_safe_without_an_editor():
    controller, window = make_controller()
    window._symbol_outline = SimpleNamespace(
        visible=False,
        updates=[],
        isVisible=lambda: False,
        update_symbols=lambda text: window._symbol_outline.updates.append(text),
    )

    controller._on_outline_navigate(4)
    controller._on_problem_navigate(2, 3)
    controller._do_refresh_outline()
    controller._on_outline_visibility_changed(False)
    controller._on_outline_visibility_changed(True)
    controller._refresh_symbol_outline(FakeEditor())

    assert window._symbol_outline.updates == []


def test_lint_context_errors_clear_current_or_background_editor(monkeypatch):
    monkeypatch.setattr(code_quality_module, "CodeEditor", FakeEditor)
    monkeypatch.setattr(code_quality_module, "can_run_editor", lambda *args: True)
    monkeypatch.setattr(
        code_quality_module,
        "resolve_lint_context",
        lambda **kwargs: (_ for _ in ()).throw(
            code_quality_module.LintContextError("invalid lint context")
        ),
    )
    current = FakeEditor()
    background = FakeEditor()
    settings = FakeSettings({"editor.linting_enabled": True, "editor.linter": "flake8"})
    tabs = SimpleNamespace(current_editor=lambda: current)
    problems = FakeProblemsPanel()
    status = FakeStatusBar()
    window = SimpleNamespace(
        _settings=settings,
        _tab_manager=tabs,
        _problems_panel=problems,
        _status_bar_manager=status,
    )
    controller = CodeQualityController(MainWindowContext(window, settings, None, None))

    controller._do_lint(current)
    assert current.cleared == 1
    assert problems.error == "invalid lint context"
    controller._do_lint(background)
    assert background.cleared == 1


def test_lint_result_for_closed_editor_is_discarded(monkeypatch):
    monkeypatch.setattr(code_quality_module, "CodeEditor", FakeEditor)
    controller, window = make_controller()
    target = FakeEditor()
    window._tab_manager = SimpleNamespace(
        current_editor=lambda: None,
        count=lambda: 0,
        widget=lambda index: None,
    )
    controller._lint_target_editor = target

    controller._on_lint_finished([SimpleNamespace(severity="error")])

    assert controller._lint_target_editor is None
    assert target.issues is None


def test_cached_results_count_severities_and_clear_fallback_editors(monkeypatch):
    monkeypatch.setattr(code_quality_module, "CodeEditor", FakeEditor)
    editor = FakeEditor()
    editor._lint_issues = [
        SimpleNamespace(severity="error"),
        SimpleNamespace(severity="warning"),
        SimpleNamespace(severity="info"),
    ]
    settings = FakeSettings({"editor.linting_enabled": True})
    window = SimpleNamespace(
        _settings=settings,
        _tab_manager=SimpleNamespace(current_editor=lambda: editor),
        _problems_panel=FakeProblemsPanel(),
        _status_bar_manager=FakeStatusBar(),
    )
    controller = CodeQualityController(MainWindowContext(window, settings, None, None))
    controller._show_cached_lint_state(editor)
    assert window._status_bar_manager.counts == (1, 1)

    fallback = SimpleNamespace(issues=None, set_lint_issues=lambda issues: setattr(fallback, "issues", issues))
    controller._clear_lint_state(fallback)
    assert fallback.issues == []


def test_disabled_manual_lint_and_missing_timer_are_noops():
    settings = FakeSettings({"editor.linting_enabled": False})
    window = SimpleNamespace(_settings=settings)
    controller = CodeQualityController(MainWindowContext(window, settings, None, None))
    controller.action_run_linter()
    controller._stop_pending_lint_debounce()

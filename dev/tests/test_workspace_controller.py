from types import SimpleNamespace

import meadowpy.ui.controllers.workspace_controller as workspace_module
from PyQt6.Qsci import QsciScintilla
from meadowpy.constants import DEFAULT_WINDOW_LAYOUT_VERSION, DEFAULT_WINDOW_STATE
from meadowpy.ui.controllers.workspace_controller import WorkspaceController
from meadowpy.ui.controllers.window_context import MainWindowContext


class FakeEditor:
    def __init__(self):
        self.text_value = ""
        self.modified = True

    def setText(self, text):
        self.text_value = text

    def setModified(self, value):
        self.modified = value


class FakeTabManager:
    def __init__(self):
        self.closed_welcome = False
        self.editor = FakeEditor()
        self.welcome_args = None

    def close_welcome_tab(self):
        self.closed_welcome = True

    def update_theme(self):
        self.theme_updated = True

    def new_tab(self):
        return self.editor

    def count(self):
        return 0

    def show_welcome_tab(self, **kwargs):
        self.welcome_args = kwargs
        return FakeWelcome()


class FakeSettings:
    def get(self, key, default=None):
        values = {
            "editor.theme": "default_dark",
            "editor.custom_theme.base": "dark",
            "editor.custom_theme.accent": "#2F7A44",
        }
        return values.get(key, default)


class FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def disconnect(self, callback):
        raise TypeError("not connected")


class FakeAction:
    def __init__(self):
        self.enabled = None

    def setEnabled(self, value):
        self.enabled = value


class FakeWelcome:
    def __init__(self):
        self.action_new_file = FakeSignal()
        self.action_open_file = FakeSignal()
        self.action_open_folder = FakeSignal()
        self.template_selected = FakeSignal()


def test_template_selection_opens_clean_untitled_tab():
    tabs = FakeTabManager()
    window = SimpleNamespace(_tab_manager=tabs)
    controller = WorkspaceController(MainWindowContext(window, None, None, None))

    controller._on_template_selected("Hello", "print('hello')")

    assert tabs.closed_welcome is True
    assert tabs.editor.text_value == "print('hello')"
    assert tabs.editor.modified is False


def test_show_welcome_creates_welcome_tab_with_current_theme():
    settings = FakeSettings()
    tabs = FakeTabManager()
    window = SimpleNamespace(_settings=settings, _tab_manager=tabs)
    controller = WorkspaceController(MainWindowContext(window, settings, None, None))

    controller.action_show_welcome()

    assert tabs.welcome_args == {
        "theme_name": "default_dark",
        "custom_base": "dark",
        "custom_accent": "#2F7A44",
    }


class WorkspaceEditor:
    def __init__(self, file_path=None, text="print('hi')", modified=False):
        self.file_path = file_path
        self._text = text
        self.modified = modified
        self.cursor = None
        self.focused = False
        self.zoom_calls = []
        self.wrap_mode = 0
        self.deleted_later = False

    def text(self):
        return self._text

    def setModified(self, value):
        self.modified = value

    def setCursorPosition(self, line, col):
        self.cursor = (line, col)

    def setFocus(self):
        self.focused = True

    def lines(self):
        return 12

    def zoomTo(self, value):
        self.zoom_calls.append(("reset", value))

    def zoomIn(self):
        self.zoom_calls.append(("in",))

    def zoomOut(self):
        self.zoom_calls.append(("out",))

    def wrapMode(self):
        return self.wrap_mode

    def setWrapMode(self, mode):
        self.wrap_mode = mode

    def deleteLater(self):
        self.deleted_later = True


class WorkspaceTabs:
    def __init__(self, editors):
        self.editors = list(editors)
        self.current = self.editors[0] if self.editors else None
        self.opened = []
        self.updated_titles = []
        self.tab_text = []
        self.tooltips = []
        self.removed = []

    def current_editor(self):
        return self.current

    def new_tab(self):
        editor = FakeEditor()
        self.editors.append(editor)
        self.current = editor
        return editor

    def close_welcome_tab(self):
        self.closed_welcome = True

    def update_theme(self):
        self.theme_updated = True

    def currentIndex(self):
        return 0

    def update_tab_title(self, index):
        self.updated_titles.append(index)

    def open_file_in_tab(self, path, content):
        self.opened.append((path, content))
        return WorkspaceEditor(path, content)

    def count(self):
        return len(self.editors)

    def widget(self, index):
        return self.editors[index]

    def setTabText(self, index, text):
        self.tab_text.append((index, text))

    def setTabToolTip(self, index, text):
        self.tooltips.append((index, text))

    def removeTab(self, index):
        self.removed.append(index)


class MutableSettings:
    def __init__(self, values=None):
        self.values = values or {}
        self.set_calls = []

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.set_calls.append((key, value))
        self.values[key] = value


class RecordingPanel:
    def __init__(self):
        self.visible = None
        self.raised = 0
        self.hidden = 0
        self.root_paths = []
        self.focused = 0
        self.issues = []
        self._issues = ["issue"]
        self.cleared = 0

    def setVisible(self, value):
        self.visible = value

    def show(self):
        self.visible = True

    def raise_(self):
        self.raised += 1

    def hide(self):
        self.hidden += 1

    def set_root_path(self, path):
        self.root_paths.append(path)

    def set_root_folder(self, path):
        self.root_paths.append(path)

    def focus_search(self):
        self.focused += 1

    def update_issues(self, issues):
        self.issues.append(issues)

    def clear_symbols(self):
        self.cleared += 1

    def clear_issues(self):
        self.cleared += 1


def test_save_and_save_as_update_editor_state_and_tab_title(tmp_path):
    editor = WorkspaceEditor(str(tmp_path / "demo.py"), "print('save')")
    tabs = WorkspaceTabs([editor])
    file_manager = SimpleNamespace(
        saved=[],
        save_file=lambda path, text: file_manager.saved.append((path, text)) or True,
        save_file_as=lambda text, parent=None: str(tmp_path / "saved_as.py"),
    )
    window = SimpleNamespace(_tab_manager=tabs, _file_manager=file_manager)
    controller = WorkspaceController(
        MainWindowContext(window, MutableSettings(), file_manager, None)
    )

    controller.action_save()
    editor.file_path = None
    controller.action_save()

    assert file_manager.saved == [(str(tmp_path / "demo.py"), "print('save')")]
    assert editor.file_path == str(tmp_path / "saved_as.py")
    assert editor.modified is False
    assert tabs.updated_titles == [0, 0]


def test_save_failure_keeps_editor_dirty_and_reports_error(monkeypatch, tmp_path):
    editor = WorkspaceEditor(str(tmp_path / "readonly.py"), "print('new')", True)
    tabs = WorkspaceTabs([editor])
    status = SimpleNamespace(
        messages=[],
        show_message=lambda message, timeout=3000: status.messages.append(
            (message, timeout)
        ),
    )
    file_manager = SimpleNamespace(
        last_save_error=PermissionError("Permission denied"),
        last_save_error_path=editor.file_path,
        save_file=lambda path, text: False,
    )
    window = SimpleNamespace(
        _tab_manager=tabs,
        _file_manager=file_manager,
        _status_bar_manager=status,
    )
    controller = WorkspaceController(
        MainWindowContext(window, MutableSettings(), file_manager, None)
    )
    dialogs = []
    monkeypatch.setattr(
        workspace_module.QMessageBox,
        "critical",
        lambda parent, title, body: dialogs.append((title, body)),
    )

    assert controller.action_save() is False

    assert editor.modified is True
    assert tabs.updated_titles == []
    assert status.messages == [("Could not save: readonly.py", 7000)]
    assert dialogs[0][0] == "Could Not Save File"
    assert "Permission denied" in dialogs[0][1]


def test_open_recent_file_removes_missing_paths_and_opens_existing(monkeypatch, tmp_path):
    warnings = []
    missing = tmp_path / "missing.py"
    existing = tmp_path / "existing.py"
    existing.write_text("print('ok')", encoding="utf-8")
    tabs = WorkspaceTabs([])
    recent = SimpleNamespace(
        removed=[],
        added=[],
        remove=lambda path: recent.removed.append(path),
        add=lambda path: recent.added.append(path),
    )
    file_manager = SimpleNamespace(read_file=lambda path: "content")
    window = SimpleNamespace(
        _tab_manager=tabs,
        _file_manager=file_manager,
        _recent_files=recent,
    )
    controller = WorkspaceController(
        MainWindowContext(window, MutableSettings(), file_manager, recent)
    )
    monkeypatch.setattr(
        workspace_module.QMessageBox,
        "warning",
        lambda parent, title, body: warnings.append((title, body)),
    )

    controller.open_recent_file(str(missing))
    controller.open_recent_file(str(existing))

    assert recent.removed == [str(missing)]
    assert warnings[0][0] == "File Not Found"
    assert tabs.opened == [(str(existing), "content")]
    assert recent.added == [str(existing)]


def test_explorer_rename_and_delete_keep_open_tabs_in_sync(monkeypatch, tmp_path):
    monkeypatch.setattr(workspace_module, "CodeEditor", WorkspaceEditor)
    old_path = tmp_path / "old.py"
    new_path = tmp_path / "new.py"
    nested = tmp_path / "folder" / "child.py"
    editors = [
        WorkspaceEditor(str(old_path)),
        WorkspaceEditor(str(nested)),
        WorkspaceEditor(str(tmp_path / "other.py")),
    ]
    tabs = WorkspaceTabs(editors)
    controller = WorkspaceController(
        MainWindowContext(SimpleNamespace(_tab_manager=tabs), MutableSettings(), None, None)
    )

    controller._on_explorer_file_renamed(str(old_path), str(new_path))
    controller._on_explorer_file_deleted(str(tmp_path / "folder"))

    assert editors[0].file_path == str(new_path)
    assert tabs.tab_text == [(0, "new.py")]
    assert tabs.tooltips == [(0, str(new_path))]
    assert tabs.removed == [1]
    assert editors[1].deleted_later is True
    assert editors[0].deleted_later is False
    assert editors[2].deleted_later is False


def test_run_action_follows_active_editor_file_type(monkeypatch, tmp_path):
    monkeypatch.setattr(workspace_module, "CodeEditor", WorkspaceEditor)
    py_editor = WorkspaceEditor(str(tmp_path / "demo.py"))
    pyw_editor = WorkspaceEditor(str(tmp_path / "window.pyw"))
    text_editor = WorkspaceEditor(str(tmp_path / "notes.txt"))
    unsaved_editor = WorkspaceEditor(None)
    non_code_tab = object()
    tabs = WorkspaceTabs([py_editor])
    run_action = FakeAction()
    run_selection_action = FakeAction()
    debug_action = FakeAction()
    ai_review_action = FakeAction()
    labels = []
    toolbar = SimpleNamespace(labels=labels, update_run_file_label=labels.append)
    window = SimpleNamespace(
        _tab_manager=tabs,
        _run_action=run_action,
        _run_selection_action=run_selection_action,
        _debug_action=debug_action,
        _ai_review_file_action=ai_review_action,
        _toolbar_builder=toolbar,
    )
    controller = WorkspaceController(
        MainWindowContext(window, MutableSettings(), None, None)
    )

    controller._update_run_file_button(py_editor)
    assert (
        run_action.enabled,
        run_selection_action.enabled,
        debug_action.enabled,
        ai_review_action.enabled,
    ) == (True, True, True, True)

    controller._update_run_file_button(pyw_editor)
    assert (
        run_action.enabled,
        run_selection_action.enabled,
        debug_action.enabled,
        ai_review_action.enabled,
    ) == (True, True, True, True)

    controller._update_run_file_button(text_editor)
    assert (
        run_action.enabled,
        run_selection_action.enabled,
        debug_action.enabled,
        ai_review_action.enabled,
    ) == (False, False, False, True)

    controller._update_run_file_button(unsaved_editor)
    assert (
        run_action.enabled,
        run_selection_action.enabled,
        debug_action.enabled,
        ai_review_action.enabled,
    ) == (True, True, True, True)

    controller._update_run_file_button(non_code_tab)
    assert (
        run_action.enabled,
        run_selection_action.enabled,
        debug_action.enabled,
        ai_review_action.enabled,
    ) == (False, False, False, False)

    controller._update_run_file_button(None)
    assert (
        run_action.enabled,
        run_selection_action.enabled,
        debug_action.enabled,
        ai_review_action.enabled,
    ) == (False, False, False, False)


def test_goto_zoom_and_word_wrap_actions_update_current_editor(monkeypatch):
    editor = WorkspaceEditor()
    editor.wrap_mode = QsciScintilla.WrapMode.WrapNone
    settings = MutableSettings({"editor.word_wrap": False})
    word_wrap_action = SimpleNamespace(
        checked=None,
        setChecked=lambda value: setattr(word_wrap_action, "checked", value),
    )
    window = SimpleNamespace(
        _tab_manager=WorkspaceTabs([editor]),
        _settings=settings,
        _word_wrap_action=word_wrap_action,
    )
    controller = WorkspaceController(
        MainWindowContext(window, settings, None, None)
    )
    monkeypatch.setattr(
        workspace_module.QInputDialog,
        "getInt",
        lambda *args: (7, True),
    )

    controller.action_goto_line()
    controller.action_zoom(1)
    controller.action_zoom(-1)
    controller.action_zoom(0)
    controller.action_toggle_word_wrap()

    assert editor.cursor == (6, 0)
    assert editor.focused is True
    assert editor.zoom_calls == [("in",), ("out",), ("reset", 0)]
    assert settings.set_calls[-1] == ("editor.word_wrap", True)
    assert word_wrap_action.checked is True


def test_reset_layout_restores_default_window_state():
    settings = MutableSettings()
    status = SimpleNamespace(
        messages=[],
        show_message=lambda message: status.messages.append(message),
    )
    window = SimpleNamespace(
        _settings=settings,
        _status_bar_manager=status,
        restored_states=[],
    )
    window.restoreState = lambda state: window.restored_states.append(state) or True
    controller = WorkspaceController(
        MainWindowContext(window, settings, None, None)
    )

    controller.action_reset_layout()

    assert len(window.restored_states) == 1
    assert (
        bytes(window.restored_states[0].toBase64()).decode()
        == DEFAULT_WINDOW_STATE
    )
    assert settings.set_calls == [
        ("window.state", DEFAULT_WINDOW_STATE),
        ("window.layout_version", DEFAULT_WINDOW_LAYOUT_VERSION),
    ]
    assert status.messages == ["Layout reset to default"]


def test_initial_refresh_actions_and_navigation_open_existing_files(monkeypatch, tmp_path):
    selected = tmp_path / "selected.py"
    selected.write_text("print('selected')\n", encoding="utf-8")
    traceback_file = tmp_path / "traceback.py"
    traceback_file.write_text("print('trace')\n", encoding="utf-8")
    editor = WorkspaceEditor(str(selected))
    tabs = WorkspaceTabs([editor])
    settings = MutableSettings({
        "repl.auto_start": True,
        "run.working_directory": "file",
    })
    file_manager = SimpleNamespace(
        opened_result=(str(selected), "opened content"),
        reads=[],
        open_file=lambda parent=None: file_manager.opened_result,
        read_file=lambda path: file_manager.reads.append(path) or "read content",
    )
    recent = SimpleNamespace(added=[], add=lambda path: recent.added.append(path))
    file_explorer = RecordingPanel()
    search_panel = RecordingPanel()
    output_panel = RecordingPanel()
    find_bar = SimpleNamespace(find=0, replace=0)
    find_bar.toggle_find = lambda: setattr(find_bar, "find", find_bar.find + 1)
    find_bar.toggle_replace = lambda: setattr(find_bar, "replace", find_bar.replace + 1)
    calls = []
    window = SimpleNamespace(
        _settings=settings,
        _tab_manager=tabs,
        _file_manager=file_manager,
        _recent_files=recent,
        _file_explorer=file_explorer,
        _search_panel=search_panel,
        _output_panel=output_panel,
        _find_replace_bar=find_bar,
        _ollama_client=SimpleNamespace(start=lambda: calls.append("ollama_start")),
    )
    controller = WorkspaceController(
        MainWindowContext(window, settings, file_manager, recent)
    )
    controller._refresh_symbol_outline = lambda ed: calls.append(("outline", ed))
    controller._do_lint = lambda: calls.append("lint")
    controller._update_interpreter_label = lambda: calls.append("interpreter")
    controller._start_repl = lambda: calls.append("repl")

    controller._initial_refresh()
    controller.action_new_file()
    controller.action_open_file()
    controller._on_explorer_file_selected(str(selected))
    controller._on_explorer_file_selected(str(tmp_path / "missing.py"))
    controller.action_toggle_find()
    controller.action_toggle_find_replace()
    controller.action_search_in_files()
    controller.action_toggle_output_panel()
    controller._on_traceback_navigate(str(traceback_file), 3)
    controller._on_traceback_navigate(str(tmp_path / "missing_trace.py"), 3)
    controller._on_search_navigate(str(traceback_file), 4)
    controller.open_file_in_tab("manual.py", "content")

    assert calls == [
        ("outline", editor),
        "lint",
        "interpreter",
        "ollama_start",
        "repl",
    ]
    assert isinstance(tabs.editors[-1], FakeEditor)
    assert tabs.opened == [
        (str(selected), "opened content"),
        (str(selected), "read content"),
        (str(traceback_file), "read content"),
        (str(traceback_file), "read content"),
        ("manual.py", "content"),
    ]
    assert recent.added == [str(selected)]
    assert find_bar.find == 1
    assert find_bar.replace == 1
    assert search_panel.focused == 1
    assert output_panel.visible is True
    assert output_panel.raised == 1


def test_open_folder_and_dialog_actions_wire_results(monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QFileDialog
    from meadowpy.ui.dialogs import (
        about_dialog,
        example_library_dialog,
        preferences_dialog,
        shortcut_reference_dialog,
    )

    folder = tmp_path / "project"
    folder.mkdir()
    settings = MutableSettings()
    file_explorer = RecordingPanel()
    search_panel = RecordingPanel()
    exec_calls = []
    connected = []

    class FakeDialog:
        def __init__(self, *args, **kwargs):
            self.example_selected = SimpleNamespace(
                connect=lambda callback: connected.append(callback)
            )
            self.preferences_applied = SimpleNamespace(
                connect=lambda callback: setattr(self, "applied_callback", callback)
            )

        def exec(self):
            exec_calls.append(type(self).__name__)

    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        lambda *args, **kwargs: str(folder),
    )
    monkeypatch.setattr(preferences_dialog, "PreferencesDialog", FakeDialog)
    monkeypatch.setattr(example_library_dialog, "ExampleLibraryDialog", FakeDialog)
    monkeypatch.setattr(shortcut_reference_dialog, "ShortcutReferenceDialog", FakeDialog)
    monkeypatch.setattr(about_dialog, "AboutDialog", FakeDialog)

    window = SimpleNamespace(
        _settings=settings,
        _file_explorer=file_explorer,
        _search_panel=search_panel,
        _tab_manager=WorkspaceTabs([]),
    )
    controller = WorkspaceController(
        MainWindowContext(window, settings, None, None)
    )

    controller.action_open_folder()
    controller.action_preferences()
    controller.action_example_library()
    controller.action_shortcut_reference()
    controller.action_about()

    assert file_explorer.root_paths == [str(folder)]
    assert settings.values["general.project_folder"] == str(folder)
    assert search_panel.root_paths == [str(folder)]
    assert len(exec_calls) == 4
    assert connected == [controller._on_template_selected]


class SignalEditor(WorkspaceEditor):
    display_name = "active.py"

    def __init__(self, text="class Demo:\n    def run(self):\n        pass\n"):
        super().__init__("active.py", text)
        self.cursor = (1, 4)
        self.cursorPositionChanged = FakeSignal()
        self.textChanged = FakeSignal()
        self.ai_explain_requested = FakeSignal()
        self.ai_improve_requested = FakeSignal()
        self.ai_docstring_requested = FakeSignal()
        self.refreshed_lint = 0
        self.refreshed_markers = 0
        self.cleared_lint = 0
        self.applied = 0

    def getCursorPosition(self):
        return self.cursor

    def refresh_lint_colors(self):
        self.refreshed_lint += 1

    def refresh_marker_colors(self):
        self.refreshed_markers += 1

    def clear_lint_markers(self):
        self.cleared_lint += 1


def test_tab_changed_and_settings_changed_refresh_dependent_ui(monkeypatch, qapp):
    monkeypatch.setattr(workspace_module, "CodeEditor", SignalEditor)
    applied = []
    monkeypatch.setattr(
        workspace_module.EditorConfigurator,
        "apply",
        lambda editor, settings: applied.append((editor, settings)),
    )

    fake_app = SimpleNamespace(stylesheets=[], setStyleSheet=lambda qss: fake_app.stylesheets.append(qss))
    monkeypatch.setattr(
        workspace_module,
        "QApplication",
        SimpleNamespace(instance=lambda: fake_app),
    )

    editor = SignalEditor()
    tabs = WorkspaceTabs([editor])
    settings = MutableSettings({
        "editor.theme": "custom",
        "editor.custom_theme.base": "dark",
        "editor.custom_theme.accent": "#336699",
    })
    symbol_outline = RecordingPanel()
    problems = RecordingPanel()
    status = SimpleNamespace(
        cursor_updates=[],
        lint_counts=[],
        indent_updates=0,
        update_cursor_position=lambda line, col: status.cursor_updates.append((line, col)),
        update_lint_counts=lambda errors, warnings: status.lint_counts.append((errors, warnings)),
        refresh_lint_colors=lambda: setattr(status, "lint_refreshed", True),
        update_indent_info=lambda: setattr(status, "indent_updates", status.indent_updates + 1),
    )
    ai_panel = SimpleNamespace(
        accents=[],
        apply_accent=lambda accent, is_dark: ai_panel.accents.append((accent, is_dark)),
        update_editor_context=lambda **kwargs: setattr(ai_panel, "context", kwargs),
    )
    toolbar = SimpleNamespace(colors=[], update_accent_color=lambda color: toolbar.colors.append(color))
    output = SimpleNamespace(
        colors=[],
        recolored=0,
        update_accent_color=lambda color: output.colors.append(color),
        recolor_for_theme=lambda: setattr(output, "recolored", output.recolored + 1),
    )
    calls = []
    window = SimpleNamespace(
        _settings=settings,
        _tab_manager=tabs,
        _symbol_outline=symbol_outline,
        _problems_panel=problems,
        _status_bar_manager=status,
        _ai_chat_panel=ai_panel,
        _toolbar_builder=toolbar,
        _output_panel=output,
        _file_explorer=RecordingPanel(),
        setWindowTitle=lambda title: calls.append(("title", title)),
        _apply_explorer_icon_theme=lambda: calls.append("explorer_theme"),
        _refresh_themed_icons=lambda: calls.append("icons"),
    )
    controller = WorkspaceController(
        MainWindowContext(window, settings, None, None)
    )
    controller._refresh_symbol_outline = lambda ed: calls.append(("outline", ed))
    controller._do_lint = lambda: calls.append("lint")
    controller._update_interpreter_label = lambda: calls.append("interpreter")
    controller._update_ai_context = lambda ed, line=None: calls.append(("ai_context", line))
    controller._on_editor_text_changed = lambda: calls.append("text_changed")
    controller._on_ai_explain_requested = lambda code: calls.append(("explain", code))
    controller._on_ai_improve_requested = lambda code: calls.append(("improve", code))
    controller._on_ai_docstring_requested = lambda code, line: calls.append(("docstring", line))

    controller._on_tab_changed(editor)
    controller._on_cursor_moved(2, 8)
    controller._on_tab_changed(None)
    controller._on_settings_changed("editor.custom_theme.accent", "#336699")
    controller._on_settings_changed("editor.show_symbol_outline", False)
    controller._on_settings_changed("editor.linting_enabled", False)
    controller._on_settings_changed("explorer.show_file_explorer", True)
    controller._on_preferences_applied(("editor.font_family",))

    assert ("title", "active.py - MeadowPy") in calls
    assert status.cursor_updates == [(1, 4), (2, 8)]
    assert ("outline", editor) in calls
    assert "lint" in calls
    assert "interpreter" in calls
    assert ("title", "MeadowPy") in calls
    assert symbol_outline.cleared == 1
    assert problems.cleared == 2
    assert fake_app.stylesheets
    assert "explorer_theme" in calls
    assert "icons" in calls
    assert output.recolored == 1
    assert getattr(status, "lint_refreshed") is True
    assert applied == [(editor, settings)] * 5
    assert editor.refreshed_lint == 1
    assert editor.refreshed_markers == 1
    assert symbol_outline.visible is False
    assert problems.hidden == 1
    assert status.lint_counts == [(0, 0), (0, 0)]
    assert window._file_explorer.visible is True


def test_linter_setting_change_clears_stale_results_and_runs_immediately(monkeypatch):
    monkeypatch.setattr(workspace_module, "CodeEditor", SignalEditor)
    monkeypatch.setattr(
        workspace_module.EditorConfigurator,
        "apply",
        lambda editor, settings: None,
    )

    editor = SignalEditor()
    tabs = WorkspaceTabs([editor])
    settings = MutableSettings({"editor.linting_enabled": True})
    problems = RecordingPanel()
    status = SimpleNamespace(
        lint_counts=[],
        update_lint_counts=lambda errors, warnings: status.lint_counts.append(
            (errors, warnings)
        ),
        update_indent_info=lambda: None,
    )
    lint_timer = SimpleNamespace(stops=0)
    lint_timer.stop = lambda: setattr(lint_timer, "stops", lint_timer.stops + 1)
    lint_runner = SimpleNamespace(cancels=0)
    lint_runner.cancel = lambda: setattr(
        lint_runner, "cancels", lint_runner.cancels + 1
    )
    calls = []
    window = SimpleNamespace(
        _settings=settings,
        _tab_manager=tabs,
        _problems_panel=problems,
        _status_bar_manager=status,
        _lint_timer=lint_timer,
        _lint_runner=lint_runner,
    )
    controller = WorkspaceController(
        MainWindowContext(window, settings, None, None)
    )
    controller._do_lint = lambda: calls.append("lint")

    controller._on_settings_changed("editor.linter", "pylint")

    assert lint_timer.stops == 1
    assert lint_runner.cancels == 1
    assert editor.cleared_lint == 1
    assert problems.cleared == 1
    assert status.lint_counts == [(0, 0)]
    assert calls == ["lint"]
    assert problems.visible is None


def test_enabling_linting_reveals_panel_and_runs_current_linter(monkeypatch):
    monkeypatch.setattr(workspace_module, "CodeEditor", SignalEditor)
    monkeypatch.setattr(
        workspace_module.EditorConfigurator,
        "apply",
        lambda editor, settings: None,
    )

    editor = SignalEditor()
    tabs = WorkspaceTabs([editor])
    settings = MutableSettings({"editor.linting_enabled": True})
    problems = RecordingPanel()
    status = SimpleNamespace(
        lint_counts=[],
        update_lint_counts=lambda errors, warnings: status.lint_counts.append(
            (errors, warnings)
        ),
        update_indent_info=lambda: None,
    )
    calls = []
    window = SimpleNamespace(
        _settings=settings,
        _tab_manager=tabs,
        _problems_panel=problems,
        _status_bar_manager=status,
    )
    controller = WorkspaceController(
        MainWindowContext(window, settings, None, None)
    )
    controller._do_lint = lambda: calls.append("lint")

    controller._on_settings_changed("editor.linting_enabled", True)

    assert editor.cleared_lint == 1
    assert problems.cleared == 1
    assert problems.visible is True
    assert status.lint_counts == [(0, 0)]
    assert calls == ["lint"]

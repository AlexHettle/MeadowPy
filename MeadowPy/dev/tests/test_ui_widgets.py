from __future__ import annotations

from types import SimpleNamespace

from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import QKeyEvent, QMouseEvent, QTextCursor
from PyQt6.QtWidgets import QMenu, QStatusBar

import meadowpy.ui.ai_chat_widgets as ai_chat_widgets_module
import meadowpy.ui.model_selector as model_selector_module
from meadowpy.core.debug_manager import DebugState
from meadowpy.core.linter import LintIssue
from meadowpy.ui.ai_chat_widgets import ChatBubble, ChatInput, ChatView
from meadowpy.ui.call_stack_panel import CallStackPanel
from meadowpy.ui.dialogs.venv_dialog import VenvDialog
from meadowpy.ui.model_selector import ModelSelectorPopup
from meadowpy.ui.problems_panel import ProblemsPanel
from meadowpy.ui.splash_screen import LoadingDotsWidget, MeadowPySplashScreen
from meadowpy.ui.status_bar import StatusBarManager
from meadowpy.ui.variable_inspector import VariableInspectorPanel
from meadowpy.ui.watch_panel import WatchPanel


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)


class FakeSettings:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key, default=None):
        return self.values.get(key, default)


def test_debug_panels_render_stack_variables_and_watch_expressions(qapp):
    stack = CallStackPanel()
    selected = Recorder()
    stack.frame_selected.connect(selected)
    stack.update_call_stack([
        {"function": "inner", "file": "C:/work/demo.py", "line": 12},
        {"function": "main", "file": "C:/work/demo.py", "line": 20},
    ])

    assert stack._list.count() == 2
    assert stack._list.item(0).text() == "inner (demo.py:12)"
    stack._list.setCurrentRow(1)
    assert selected.calls == [(1,)]
    stack.clear_stack()
    assert stack._list.count() == 0

    variables = VariableInspectorPanel()
    variables.update_variables({
        "locals": {"name": "'Ada'", "count": "2"},
        "globals": {"VERSION": "'1.0'"},
    })
    assert variables._tree.topLevelItemCount() == 2
    assert variables._tree.topLevelItem(0).text(0) == "Locals"
    assert variables._tree.topLevelItem(0).child(0).text(0) == "count"
    variables.clear_variables()
    variables.update_variables({"locals": {}, "globals": {}})
    assert variables._tree.topLevelItem(0).text(0) == "(no variables)"

    watch = WatchPanel()
    requested = Recorder()
    watch.evaluate_requested.connect(requested)
    watch._input.setText("len(items)")
    watch._add_expression()
    watch._input.setText("len(items)")
    watch._add_expression()

    assert watch.get_expressions() == ["len(items)"]
    assert requested.calls == [("len(items)",)]

    watch.update_value("len(items)", "3", "")
    assert watch._table.item(0, 1).text() == "3"
    watch.update_value("len(items)", "", "NameError")
    assert watch._table.item(0, 1).text() == "Error: NameError"

    watch.request_all_evaluations()
    assert requested.calls[-1] == ("len(items)",)
    watch.clear_values()
    assert watch._table.item(0, 1).text() == "(not evaluated)"
    watch._on_cell_clicked(0, 2)
    assert watch.get_expressions() == []

    for widget in (stack, variables, watch):
        widget.deleteLater()


def test_problems_panel_updates_counts_navigation_and_linter_errors(qapp):
    panel = ProblemsPanel(settings=FakeSettings({"editor.theme": "default_dark"}))
    navigated = Recorder()
    panel.navigate_to.connect(navigated)
    issues = [
        LintIssue(0, 4, "F821", "undefined name", "error"),
        LintIssue(2, 0, "W291", "trailing whitespace", "warning"),
    ]

    panel.update_issues(issues)

    assert panel.windowTitle() == "Problems — 1 error, 1 warning"
    assert panel._table.rowCount() == 2
    assert panel._table.item(0, 1).text() == "1"
    panel._on_cell_clicked(1, 3)
    assert navigated.calls == [(2, 0)]

    panel.show_linter_error("flake8 is missing")
    assert panel.windowTitle() == "Problems — Linter Error"
    assert panel._table.item(0, 3).text() == "flake8 is missing"
    panel.clear_issues()
    assert panel.windowTitle() == "Problems"
    assert panel._table.rowCount() == 0
    panel.deleteLater()


def test_status_bar_manager_renders_editor_debug_and_ai_state(qapp):
    status_bar = QStatusBar()
    settings = FakeSettings({"editor.use_spaces": True, "editor.tab_width": 2})
    manager = StatusBarManager(status_bar, settings)

    manager.update_cursor_position(4, 8)
    manager.update_encoding("UTF-16")
    manager.update_eol_mode("CRLF")
    manager.update_lint_counts(2, 1)
    manager.update_debug_state(DebugState.PAUSED)
    manager.update_interpreter("Python 3.11.13")
    manager.update_ollama_status(True, "qwen3")

    assert manager._cursor_label.text() == "Ln 5, Col 9"
    assert manager._encoding_label.text() == "UTF-16"
    assert manager._eol_label.text() == "CRLF"
    assert "2" in manager._lint_label.text()
    assert manager._debug_label.text() == "⏸ Paused"
    assert manager._interpreter_label.text() == "Python 3.11.13"
    assert manager.ollama_label.text() == "AI: qwen3"

    settings.values["editor.theme"] = "default_high_contrast"
    manager.refresh_lint_colors()
    assert "#000000" in manager._lint_label.text()
    status_bar.deleteLater()


def test_status_bar_manager_handles_empty_lint_ai_and_clickable_states(qapp):
    status_bar = QStatusBar()
    settings = FakeSettings(
        {
            "editor.use_spaces": False,
            "editor.tab_width": 4,
            "editor.theme": "default_dark",
        }
    )
    manager = StatusBarManager(status_bar, settings)
    clicked = Recorder()
    manager.ollama_label.clicked.connect(clicked)

    assert manager._indent_label.text() == "Tab Size: 4"

    manager.update_lint_counts(0, 0)
    assert manager._lint_label.text() == "\u2713 No issues"

    manager.update_lint_counts(1, 0)
    assert "1" in manager._lint_label.text()
    assert "\u26A0" not in manager._lint_label.text()

    manager.update_lint_counts(0, 2)
    assert "\u26A0" in manager._lint_label.text()

    settings.values["editor.theme"] = "default_high_contrast"
    manager.refresh_lint_colors()
    assert "#000000" in manager._lint_label.text()
    assert "\u25B2" in manager._lint_label.text()

    manager.update_ollama_status(False, "qwen3")
    assert manager.ollama_label.text() == "AI: Offline"
    manager.update_ollama_status(True, "")
    assert manager.ollama_label.text() == "AI: Select model..."

    click = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(1, 1),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    manager.ollama_label.mousePressEvent(click)
    assert clicked.calls == [()]

    manager.show_message("File saved", 10)
    assert status_bar.currentMessage() == "File saved"
    status_bar.deleteLater()


def test_model_selector_menu_builders_emit_user_choices(qapp):
    popup = ModelSelectorPopup()
    chosen = Recorder()
    popup.model_chosen.connect(chosen)

    offline_menu = QMenu()
    popup._build_offline_menu(offline_menu)
    assert offline_menu.actions()[0].text() == "Ollama is not running"
    setup_action = [
        action for action in offline_menu.actions()
        if action.text() == "Setup/check Ollama..."
    ][0]
    setup_action.trigger()
    assert chosen.calls[-1] == ("__setup__",)
    offline_menu.actions()[-1].trigger()
    assert chosen.calls[-1] == ("__retry__",)

    no_models_menu = QMenu()
    popup._build_no_models_menu(no_models_menu)
    assert no_models_menu.actions()[0].text() == "No models installed"
    setup_action = [
        action for action in no_models_menu.actions()
        if action.text() == "Setup/check Ollama..."
    ][0]
    setup_action.trigger()
    assert chosen.calls[-1] == ("__setup__",)
    no_models_menu.actions()[-1].trigger()
    assert chosen.calls[-1] == ("__refresh__",)

    popup.set_models(["llama3", "qwen3"])
    popup.set_current_model("qwen3")
    popup.set_connected(True)
    models_menu = QMenu()
    popup._build_model_list_menu(models_menu)
    qwen_action = [
        action for action in models_menu.actions()
        if action.text() == "qwen3"
    ][0]

    assert qwen_action.isChecked() is True
    qwen_action.trigger()
    assert chosen.calls[-1] == ("qwen3",)
    setup_action = [
        action for action in models_menu.actions()
        if action.text() == "Setup/check Ollama..."
    ][0]
    setup_action.trigger()
    assert chosen.calls[-1] == ("__setup__",)


def test_model_selector_show_at_chooses_menu_for_connection_state(monkeypatch, qapp):
    created_menus = []

    class FakeSignal:
        def __init__(self):
            self.callbacks = []

        def connect(self, callback):
            self.callbacks.append(callback)

    class FakeAction:
        def __init__(self, text):
            self._text = text
            self._enabled = True
            self._checkable = False
            self._checked = False
            self.triggered = FakeSignal()

        def text(self):
            return self._text

        def setEnabled(self, enabled):
            self._enabled = enabled

        def isEnabled(self):
            return self._enabled

        def setCheckable(self, checkable):
            self._checkable = checkable

        def isCheckable(self):
            return self._checkable

        def setChecked(self, checked):
            self._checked = checked

        def isChecked(self):
            return self._checked

    class FakeMenu:
        def __init__(self, parent=None):
            self.parent = parent
            self.object_name = ""
            self.exec_pos = None
            self._actions = []
            created_menus.append(self)

        def setObjectName(self, name):
            self.object_name = name

        def addAction(self, text):
            action = FakeAction(text)
            self._actions.append(action)
            return action

        def addSeparator(self):
            self._actions.append(FakeAction("---"))

        def actions(self):
            return self._actions

        def exec(self, pos):
            self.exec_pos = pos

    monkeypatch.setattr(model_selector_module, "QMenu", FakeMenu)
    popup = ModelSelectorPopup()
    pos = QPoint(4, 8)

    popup.show_at(pos)

    offline_menu = created_menus[-1]
    assert offline_menu.object_name == "modelSelectorMenu"
    assert offline_menu.exec_pos == pos
    assert [action.text() for action in offline_menu.actions()] == [
        "Ollama is not running",
        "---",
        "Setup/check Ollama...",
        "Check connection...",
    ]

    popup.set_connected(True)
    popup.show_at(pos)

    no_models_menu = created_menus[-1]
    assert [action.text() for action in no_models_menu.actions()] == [
        "No models installed",
        "---",
        "Setup/check Ollama...",
        "Refresh models...",
    ]

    popup.set_models(["llama3", "qwen3"])
    popup.set_current_model("qwen3")
    popup.show_at(pos)

    model_menu = created_menus[-1]
    qwen_action = [
        action for action in model_menu.actions()
        if action.text() == "qwen3"
    ][0]
    assert qwen_action.isCheckable() is True
    assert qwen_action.isChecked() is True
    assert [action.text() for action in model_menu.actions()] == [
        "Select AI Model",
        "---",
        "llama3",
        "qwen3",
        "---",
        "Setup/check Ollama...",
        "Refresh models...",
    ]


def test_chat_view_copy_all_action_disables_when_empty(monkeypatch, qapp):
    created_menus = []
    copied = []

    class FakeAction:
        def __init__(self, text):
            self._text = text
            self._enabled = True

        def text(self):
            return self._text

        def setEnabled(self, enabled):
            self._enabled = enabled

        def isEnabled(self):
            return self._enabled

    class FakeMenu:
        def __init__(self, parent=None):
            self.parent = parent
            self.actions = []
            created_menus.append(self)

        def addAction(self, text):
            action = FakeAction(text)
            self.actions.append(action)
            return action

        def exec(self, _pos):
            return self.actions[0]

    monkeypatch.setattr(ai_chat_widgets_module, "QMenu", FakeMenu)
    monkeypatch.setattr(
        ai_chat_widgets_module,
        "QApplication",
        SimpleNamespace(
            clipboard=lambda: SimpleNamespace(
                setText=lambda text: copied.append(text)
            )
        ),
    )

    view = ChatView()

    view._on_context_menu(QPoint(0, 0))

    assert created_menus[-1].actions[0].text() == "Copy All Chat"
    assert created_menus[-1].actions[0].isEnabled() is False
    assert copied == []

    view.add_bubble("user", "<b>Hello</b>")
    view.add_centered("<i>Stopped</i>", "aiChatStoppedLabel")
    view._on_context_menu(QPoint(0, 0))

    assert created_menus[-1].actions[0].isEnabled() is True
    assert copied == ["Hello\n\nStopped"]
    view.deleteLater()


def test_chat_input_enter_submits_shift_enter_and_text_key_edits(qapp):
    input_area = ChatInput()
    submitted = Recorder()
    input_area.submit_pressed.connect(submitted)
    input_area.setPlainText("hello")
    input_area.moveCursor(QTextCursor.MoveOperation.End)

    input_area.keyPressEvent(
        QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Return,
            Qt.KeyboardModifier.NoModifier,
        )
    )

    assert submitted.calls == [()]
    assert input_area.toPlainText() == "hello"

    input_area.keyPressEvent(
        QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Return,
            Qt.KeyboardModifier.ShiftModifier,
            "\n",
        )
    )
    input_area.keyPressEvent(
        QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_A,
            Qt.KeyboardModifier.NoModifier,
            "a",
        )
    )

    assert submitted.calls == [()]
    assert input_area.toPlainText() == "hello\na"
    input_area.deleteLater()


def test_chat_bubble_html_plain_text_and_link_forwarding(qapp):
    bubble = ChatBubble("ai")
    opened = Recorder()
    bubble.link_clicked.connect(opened)
    html = '<b>Hello</b> <a href="https://example.test">there</a>'

    bubble.set_html(html)
    bubble._label.linkActivated.emit("https://example.test")

    assert bubble.objectName() == "chatBubbleAi"
    assert bubble.html() == html
    assert bubble.plain_text() == "Hello there"
    assert opened.calls == [("https://example.test",)]

    user_bubble = ChatBubble("user")
    assert user_bubble.objectName() == "chatBubbleUser"
    bubble.deleteLater()
    user_bubble.deleteLater()


def test_chat_view_scroll_to_value_clamps_to_scrollbar_range(qapp):
    view = ChatView()
    scrollbar = view.verticalScrollBar()
    scrollbar.setRange(10, 50)

    view.scroll_to_value(100)
    assert view.scroll_value() == 50

    view.scroll_to_value(0)
    assert view.scroll_value() == 10

    view.scroll_to_value(30)
    assert view.scroll_value() == 30
    view.deleteLater()


def test_chat_view_clear_removes_rows_from_layout(qapp):
    view = ChatView()
    initial_count = view._inner_layout.count()

    view.add_bubble("user", "Hello")
    view.add_centered("<i>Stopped</i>", "aiChatStoppedLabel")
    assert view._inner_layout.count() == initial_count + 2

    view.clear()

    assert view._inner_layout.count() == initial_count
    assert view._rows == []
    view.deleteLater()


def test_venv_dialog_validates_inputs_and_reports_success(monkeypatch, qapp, tmp_path):
    messages = []

    class FakeManager:
        def __init__(self):
            self.created = []

        def detect_interpreters(self, file_path):
            return [
                SimpleNamespace(
                    label="System Python 3.11",
                    path="python.exe",
                )
            ]

        def create_venv(self, base_dir, venv_name, interpreter):
            if venv_name == "fail-env":
                raise RuntimeError("creation failed")
            self.created.append((base_dir, venv_name, interpreter))
            return str(tmp_path / venv_name)

    monkeypatch.setattr(
        "meadowpy.ui.dialogs.venv_dialog.QMessageBox.warning",
        lambda parent, title, body: messages.append(("warning", title, body)),
    )
    monkeypatch.setattr(
        "meadowpy.ui.dialogs.venv_dialog.QMessageBox.information",
        lambda parent, title, body: messages.append(("info", title, body)),
    )
    monkeypatch.setattr(
        "meadowpy.ui.dialogs.venv_dialog.QMessageBox.critical",
        lambda parent, title, body: messages.append(("critical", title, body)),
    )

    manager = FakeManager()
    dialog = VenvDialog(manager, str(tmp_path / "script.py"))
    chosen_dir = tmp_path / "chosen"
    monkeypatch.setattr(
        "meadowpy.ui.dialogs.venv_dialog.QFileDialog.getExistingDirectory",
        lambda parent, title, directory: str(chosen_dir),
    )

    dialog._browse_directory()

    assert dialog._dir_edit.text() == str(chosen_dir)

    dialog._dir_edit.setText("")
    dialog._create_venv()
    assert messages[-1][1] == "Missing Directory"

    dialog._dir_edit.setText(str(tmp_path))
    dialog._name_edit.setText("")
    dialog._create_venv()
    assert messages[-1][1] == "Missing Name"

    existing = tmp_path / ".venv"
    existing.mkdir()
    dialog._name_edit.setText(".venv")
    dialog._create_venv()
    assert messages[-1][1] == "Already Exists"

    dialog._name_edit.setText("no-interpreter-env")
    dialog._interp_combo.clear()
    dialog._create_venv()
    assert messages[-1][1] == "No Interpreter"

    dialog._interp_combo.addItem("System Python 3.11  (python.exe)", "python.exe")
    dialog._name_edit.setText("fail-env")
    dialog._create_venv()
    assert messages[-1] == (
        "critical",
        "Error",
        "Failed to create virtual environment:\ncreation failed",
    )
    assert dialog._info_label.text() == ""

    dialog._name_edit.setText("new-env")
    dialog._create_venv()

    assert manager.created == [(str(tmp_path), "new-env", "python.exe")]
    assert messages[-1][0] == "info"
    dialog.deleteLater()


def test_splash_screen_status_icon_and_loading_dots(qapp):
    dots = LoadingDotsWidget()
    dots._timer.stop()
    start = dots._active_index

    dots._advance()

    assert dots._active_index == (start + 1) % 3

    splash = MeadowPySplashScreen(None, "1.2.3")
    splash.set_status_text("Loading tests...")
    pixmap = splash._icon_pixmap(None)
    splash.center_on_screen()

    assert splash._status_label.text() == "Loading tests..."
    assert splash._version_label.text() == "v1.2.3"
    assert pixmap.isNull() is False

    dots.deleteLater()
    splash.deleteLater()

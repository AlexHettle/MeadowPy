from __future__ import annotations

from types import SimpleNamespace

from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QAction, QColor, QFont, QKeyEvent, QPalette
from PyQt6.QtWidgets import (
    QFontComboBox,
    QDialog,
    QLabel,
    QMainWindow,
    QPushButton,
    QTabBar,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QWidget,
)

import meadowpy.ui.ai_chat_panel as ai_chat_panel_module
import meadowpy.ui.dialogs.shortcut_reference_dialog as shortcut_reference_module
import meadowpy.ui.search_panel as search_panel_module
from meadowpy.core.settings import Settings
from meadowpy.core.shortcuts import get_shortcut, set_shortcut
from meadowpy.resources.resource_loader import get_stylesheet
from tests.helpers import DummySignal
from meadowpy.ui.ai_chat_panel import AIChatPanel
from meadowpy.ui.dialogs.about_dialog import AboutDialog
from meadowpy.ui.dialogs.accent_color_picker import (
    AccentColorPickerDialog,
    _HueBar,
    _SVCanvas,
)
from meadowpy.ui.dialogs.example_library_dialog import ExampleLibraryDialog
from meadowpy.ui.dialogs.ollama_setup_dialog import (
    OllamaSetupDialog,
    OllamaSetupCheckWorker,
    _normalize_api_url,
)
from meadowpy.ui.dialogs.preferences_dialog import PreferencesDialog
from meadowpy.ui.dialogs.shortcut_reference_dialog import ShortcutReferenceDialog
from meadowpy.ui.file_explorer import FileExplorerPanel
from meadowpy.ui.find_replace_bar import FindReplaceBar
from meadowpy.ui.keyword_help_popup import KeywordHelpPopup
from meadowpy.ui.output_panel import OutputPanel
from meadowpy.ui.panel_title_bar import (
    PANEL_TITLE_BAR_HEIGHT,
    PANEL_TITLE_CONTENT_HEIGHT,
    PANEL_TITLE_CONTROL_SIZE,
    PANEL_TITLE_ICON_BUTTON_SIZE,
    PANEL_TITLE_VERTICAL_MARGIN,
)
from meadowpy.ui.problems_panel import ProblemsPanel
from meadowpy.ui.search_panel import (
    SearchPanel,
    SearchResult,
    SearchWorker,
    _MAX_FILE_SIZE,
)
from meadowpy.ui.symbol_outline import SymbolOutlinePanel
from meadowpy.ui.tool_bar import ToolBarBuilder
from meadowpy.ui.welcome_widget import _WelcomeHeroWidget


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)


class FakeResponse:
    def __init__(self, body=b""):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeSettings:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key, default=None):
        return self.values.get(key, default)


def test_custom_panel_title_rows_share_height_and_centering(qapp):
    panels = [
        FileExplorerPanel(),
        ProblemsPanel(settings=FakeSettings({"editor.theme": "default_dark"})),
        OutputPanel(settings=FakeSettings({"editor.theme": "default_dark"})),
        AIChatPanel(),
        SearchPanel(),
        SymbolOutlinePanel(),
    ]
    title_label_names = [
        "explorerTitleLabel",
        "problemsTitleLabel",
        "outputTitleLabel",
        "aiChatTitleLabel",
        "searchTitleLabel",
        "outlineTitleLabel",
    ]
    try:
        for panel, label_name in zip(panels, title_label_names):
            title_bar = panel.titleBarWidget()
            layout = title_bar.layout()
            margins = layout.contentsMargins()
            title_label = title_bar.findChild(QLabel, label_name)

            assert title_bar.minimumHeight() == PANEL_TITLE_BAR_HEIGHT
            assert title_bar.maximumHeight() == PANEL_TITLE_BAR_HEIGHT
            assert margins.top() == PANEL_TITLE_VERTICAL_MARGIN
            assert margins.bottom() == PANEL_TITLE_VERTICAL_MARGIN
            assert layout.alignment() & Qt.AlignmentFlag.AlignVCenter
            assert title_label.minimumHeight() == PANEL_TITLE_CONTENT_HEIGHT
            assert title_label.maximumHeight() == PANEL_TITLE_CONTENT_HEIGHT

        control_bars = [
            panels[0].titleBarWidget(),
            panels[2].titleBarWidget(),
            panels[3].titleBarWidget(),
        ]
        explorer_title_buttons = panels[0].titleBarWidget().findChildren(
            QToolButton
        )
        other_title_buttons = [
            button
            for title_bar in control_bars[1:]
            for button in title_bar.findChildren(QToolButton)
        ]
        assert explorer_title_buttons
        assert other_title_buttons
        assert {
            (button.minimumWidth(), button.minimumHeight())
            for button in explorer_title_buttons
        } == {(PANEL_TITLE_ICON_BUTTON_SIZE, PANEL_TITLE_ICON_BUTTON_SIZE)}
        assert {
            (button.minimumWidth(), button.minimumHeight())
            for button in other_title_buttons
        } == {(PANEL_TITLE_CONTROL_SIZE, PANEL_TITLE_CONTROL_SIZE)}

        title_push_buttons = [
            button
            for title_bar in control_bars
            for button in title_bar.findChildren(QPushButton)
        ]
        assert title_push_buttons
        assert {
            (button.minimumHeight(), button.maximumHeight())
            for button in title_push_buttons
        } == {(PANEL_TITLE_CONTENT_HEIGHT, PANEL_TITLE_CONTENT_HEIGHT)}

        ai_title_bar = panels[3].titleBarWidget()
        status_dot_slot = ai_title_bar.findChild(QWidget, "aiChatStatusDotSlot")
        status_dot = ai_title_bar.findChild(QLabel, "aiChatStatusDot")
        model_label = ai_title_bar.findChild(QLabel, "aiChatModelLabel")
        assert status_dot_slot is not None
        assert status_dot is not None
        assert model_label is not None
        assert (
            status_dot_slot.minimumWidth(),
            status_dot_slot.minimumHeight(),
            status_dot_slot.maximumWidth(),
            status_dot_slot.maximumHeight(),
        ) == (
            12,
            PANEL_TITLE_CONTENT_HEIGHT,
            12,
            PANEL_TITLE_CONTENT_HEIGHT,
        )
        assert (status_dot.minimumWidth(), status_dot.minimumHeight()) == (8, 8)
        assert status_dot_slot.layout().itemAt(0).alignment() & (
            Qt.AlignmentFlag.AlignCenter
        )
        status_dot_margins = status_dot_slot.layout().contentsMargins()
        assert (
            status_dot_margins.left(),
            status_dot_margins.top(),
            status_dot_margins.right(),
            status_dot_margins.bottom(),
        ) == (2, 4, 2, 0)
        assert status_dot.testAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        assert (
            model_label.minimumHeight(),
            model_label.maximumHeight(),
        ) == (PANEL_TITLE_CONTENT_HEIGHT, PANEL_TITLE_CONTENT_HEIGHT)
        assert model_label.alignment() & Qt.AlignmentFlag.AlignVCenter
        assert status_dot.toolTip() == ""
        assert status_dot_slot.toolTip() == "Ollama is offline"
        panels[3].set_connected(True)
        assert status_dot.toolTip() == ""
        assert status_dot_slot.toolTip() == "Ollama is connected"
    finally:
        for panel in panels:
            panel.deleteLater()


def test_tabified_dock_tabs_match_panel_title_row_height(qapp):
    previous_stylesheet = qapp.styleSheet()
    window = QMainWindow()
    explorer_panel = FileExplorerPanel()
    problems_panel = ProblemsPanel(
        settings=FakeSettings({"editor.theme": "default_dark"})
    )
    output_panel = OutputPanel(
        settings=FakeSettings({"editor.theme": "default_dark"})
    )
    search_panel = SearchPanel()
    panels = [explorer_panel, problems_panel, output_panel, search_panel]
    try:
        qapp.setStyleSheet(get_stylesheet("default_dark"))
        window.resize(800, 500)
        window.setTabPosition(
            Qt.DockWidgetArea.LeftDockWidgetArea,
            QTabWidget.TabPosition.North,
        )
        window.setTabPosition(
            Qt.DockWidgetArea.BottomDockWidgetArea,
            QTabWidget.TabPosition.North,
        )
        window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, explorer_panel)
        window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, problems_panel)
        window.tabifyDockWidget(explorer_panel, problems_panel)
        window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, output_panel)
        window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, search_panel)
        window.tabifyDockWidget(output_panel, search_panel)
        window.show()
        qapp.processEvents()

        tab_bars = [
            tab_bar for tab_bar in window.findChildren(QTabBar)
            if tab_bar.count()
        ]
        assert tab_bars
        assert {
            tab_bar.tabRect(0).height() for tab_bar in tab_bars
        } == {PANEL_TITLE_BAR_HEIGHT}
        title_bar_y_positions = []
        for panel in panels:
            panel.raise_()
            qapp.processEvents()
            title_bar_y_positions.append(panel.titleBarWidget().geometry().y())
        assert set(title_bar_y_positions) == {0}
    finally:
        qapp.setStyleSheet(previous_stylesheet)
        window.deleteLater()
        for panel in panels:
            panel.deleteLater()


def test_output_panel_handles_repl_stdin_errors_history_and_clipboard(qapp):
    panel = OutputPanel(settings=FakeSettings({"editor.theme": "default_dark"}))
    repl_input = Recorder()
    stdin_input = Recorder()
    history_up = Recorder()
    history_down = Recorder()
    ai_fix = Recorder()
    panel.repl_input_submitted.connect(repl_input)
    panel.input_submitted.connect(stdin_input)
    panel.repl_history_up.connect(history_up)
    panel.repl_history_down.connect(history_down)
    panel.ai_fix_requested.connect(ai_fix)

    assert panel._send_btn.text() == ""
    assert not panel._send_btn.icon().isNull()
    assert panel._send_btn.width() == 32
    assert panel._send_btn.height() == 32
    assert not panel._send_btn.isEnabled()
    title_tooltips = {
        btn.toolTip() for btn in panel._title_bar.findChildren(QToolButton)
    }
    assert "Run (F5)" not in title_tooltips
    assert "Stop (Ctrl+F5)" not in title_tooltips

    panel.append_output("hello\r\n", "stdout")
    panel.append_output("friendly hint\n", "hint")
    panel.append_output(
        'Traceback\n  File "C:/tmp/app.py", line 7, in <module>\nBoom\n',
        "stderr",
    )

    assert "\r" not in panel._output_text.toPlainText()
    assert not panel._fix_btn.isHidden()

    panel._on_fix_with_ai()
    assert ai_fix.calls == [(
        'Traceback\n  File "C:/tmp/app.py", line 7, in <module>\nBoom',
    )]

    panel.update_repl_prompt("...   ")
    panel.set_input_text("x + 1")
    assert panel._send_btn.isEnabled()
    panel._on_input_submitted()
    assert not panel._send_btn.isEnabled()
    assert repl_input.calls == [("x + 1",)]
    assert "... x + 1" in panel._output_text.toPlainText()

    up_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier)
    down_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
    assert panel.eventFilter(panel._input_line, up_event) is True
    assert panel.eventFilter(panel._input_line, down_event) is True
    assert history_up.calls == [()]
    assert history_down.calls == [()]

    panel.set_running(True)
    assert panel._mode == panel._MODE_STDIN
    assert not panel._send_btn.isEnabled()
    panel.set_input_text("Ada")
    assert panel._send_btn.isEnabled()
    panel._on_input_submitted()
    assert not panel._send_btn.isEnabled()
    assert stdin_input.calls == [("Ada\n",)]

    panel.copy_output()
    assert "Ada" in qapp.clipboard().text()

    panel.set_running(False)
    assert panel._mode == panel._MODE_REPL
    panel.set_max_lines(2)
    panel.append_output("one\ntwo\nthree\n", "stdout")
    assert panel._output_text.document().blockCount() <= 2

    panel.recolor_for_theme()
    panel.clear_output()
    assert panel._output_text.toPlainText() == ""
    assert panel._output_history == []
    panel.deleteLater()


def test_search_worker_reports_real_matches_and_ignores_unsuitable_files(tmp_path):
    (tmp_path / "main.py").write_text("Alpha\nbeta alpha\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ALPHA\n", encoding="utf-8")
    hidden = tmp_path / ".git"
    hidden.mkdir()
    (hidden / "ignored.py").write_text("alpha\n", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"alpha")
    (tmp_path / "large.log").write_bytes(b"alpha\n" + b"x" * _MAX_FILE_SIZE)

    matches = []
    totals = []
    worker = SearchWorker(str(tmp_path), "alpha", False, False)
    worker.match_found.connect(matches.append)
    worker.finished.connect(totals.append)
    worker.run()

    assert totals == [3]
    assert worker.large_files_skipped == 1
    assert sorted(
        (m.file_path, m.line_num, m.column, m.line_text)
        for m in matches
    ) == sorted([
        (str(tmp_path / "main.py"), 1, 0, "Alpha"),
        (str(tmp_path / "main.py"), 2, 5, "beta alpha"),
        (str(tmp_path / "notes.txt"), 1, 0, "ALPHA"),
    ])

    case_matches = []
    case_totals = []
    case_worker = SearchWorker(str(tmp_path), "alpha", True, False)
    case_worker.match_found.connect(case_matches.append)
    case_worker.finished.connect(case_totals.append)
    case_worker.run()
    assert case_totals == [1]
    assert [
        (m.file_path, m.line_num, m.column, m.line_text)
        for m in case_matches
    ] == [(str(tmp_path / "main.py"), 2, 5, "beta alpha")]

    bad_regex_totals = []
    bad_regex_worker = SearchWorker(str(tmp_path), "[", False, True)
    bad_regex_worker.finished.connect(bad_regex_totals.append)
    bad_regex_worker.run()
    assert bad_regex_totals == [0]

    cancelled_totals = []
    cancelled_worker = SearchWorker(str(tmp_path), "alpha", False, False)
    cancelled_worker.cancel()
    cancelled_worker.finished.connect(cancelled_totals.append)
    cancelled_worker.run()
    assert cancelled_totals == [0]


def test_search_panel_builds_grouped_results_and_navigates(qapp, tmp_path):
    panel = SearchPanel()
    panel.set_root_path(str(tmp_path))
    navigated = Recorder()
    panel.navigate_to_file.connect(navigated)

    assert panel._scope_label.text().startswith("Searching in: ")
    assert panel._scope_label.toolTip() == str(tmp_path)

    file_path = str(tmp_path / "pkg" / "mod.py")
    panel._on_match_found(SearchResult(file_path, 2, 4, "    target()"))
    panel._on_match_found(SearchResult(file_path, 4, 0, "x" * 250))

    assert panel._tree.topLevelItemCount() == 1
    file_item = panel._tree.topLevelItem(0)
    assert file_item.text(0).endswith("(2)")
    assert file_item.childCount() == 2
    assert len(file_item.child(1).text(0)) < 230

    panel._on_item_double_clicked(file_item.child(0), 0)
    assert navigated.calls == [(file_path, 2)]

    panel._on_search_finished(2)
    assert panel._status_label.text() == "2 results in 1 file"
    assert panel._search_btn.isEnabled()
    panel._on_search_finished(0)
    assert panel._status_label.text() == "No results found."
    panel._large_files_skipped = 2
    panel._on_search_finished(0)
    assert panel._status_label.text() == "No results found. 2 large files skipped."
    panel._large_files_skipped = 1
    panel._on_search_finished(2)
    assert panel._status_label.text() == "2 results in 1 file 1 large file skipped."
    panel.focus_search()
    assert panel.isVisible()
    panel.deleteLater()


def test_search_panel_scope_empty_root_and_broad_root_cancel(qapp, tmp_path):
    panel = SearchPanel()

    assert panel._scope_label.text() == "Open a folder to search files."
    panel._search_input.setText("needle")
    panel._start_search()
    assert panel._status_label.text() == "Open a folder to search files."

    project = tmp_path / "parent" / "child"
    project.mkdir(parents=True)
    panel.set_root_path(str(project))
    assert panel._scope_label.text() == "Searching in: parent\\child"

    confirmations = []
    panel._is_broad_search_root = lambda root: True
    panel._confirm_broad_search_root = (
        lambda root: confirmations.append(root) or False
    )
    panel._start_search()

    assert confirmations == [str(project)]
    assert panel._status_label.text() == "Search cancelled."
    panel.deleteLater()


def test_search_panel_starts_confirmed_broad_search_and_cancels_previous(
    monkeypatch,
    qapp,
    tmp_path,
):
    class FakeThread:
        instances = []

        def __init__(self):
            self.started = DummySignal()
            self.finished = DummySignal()
            self.running = False
            self.start_calls = 0
            self.quit_calls = 0
            self.wait_calls = []
            self.terminate_calls = 0
            self.__class__.instances.append(self)

        def start(self):
            self.start_calls += 1
            self.running = True

        def isRunning(self):
            return self.running

        def quit(self):
            self.quit_calls += 1
            self.running = False

        def wait(self, timeout=None):
            self.wait_calls.append(timeout)
            self.running = False
            return True

        def terminate(self):
            self.terminate_calls += 1
            self.running = False

    class FakeWorker:
        instances = []

        def __init__(self, root_path, pattern, case_sensitive, use_regex):
            self.args = (root_path, pattern, case_sensitive, use_regex)
            self.match_found = DummySignal()
            self.finished = DummySignal()
            self.large_files_skipped = 0
            self.cancelled = False
            self.thread = None
            self.__class__.instances.append(self)

        def moveToThread(self, thread):
            self.thread = thread

        def run(self):
            pass

        def cancel(self):
            self.cancelled = True

    monkeypatch.setattr(search_panel_module, "QThread", FakeThread)
    monkeypatch.setattr(search_panel_module, "SearchWorker", FakeWorker)

    panel = SearchPanel()
    project = tmp_path / "parent" / "child"
    project.mkdir(parents=True)
    confirmations = []
    panel._is_broad_search_root = lambda root: True
    panel._confirm_broad_search_root = (
        lambda root: confirmations.append(root) or True
    )
    panel.set_root_path(str(project))
    panel._search_input.setText("needle")
    panel._case_cb.setChecked(True)
    panel._regex_cb.setChecked(True)

    panel._start_search()

    first_thread = FakeThread.instances[0]
    first_worker = FakeWorker.instances[0]
    assert confirmations == [str(project)]
    assert first_worker.args == (str(project), "needle", True, True)
    assert first_worker.thread is first_thread
    assert first_thread.start_calls == 1
    assert panel._status_label.text().startswith("Searching")
    assert not panel._search_btn.isEnabled()

    panel._search_input.setText("second")
    panel._start_search()

    second_thread = FakeThread.instances[1]
    second_worker = FakeWorker.instances[1]
    assert confirmations == [str(project)]
    assert first_worker.cancelled is True
    assert first_thread.quit_calls == 1
    assert panel._old_threads == [first_thread]
    assert panel._old_workers == [first_worker]
    assert second_worker.args == (str(project), "second", True, True)
    assert panel._thread is second_thread
    assert panel._worker is second_worker

    panel.stop()

    assert second_worker.cancelled is True
    assert panel._thread is None
    assert panel._worker is None
    assert panel._old_threads == []
    assert panel._old_workers == []
    assert first_thread.wait_calls == []
    assert second_thread.wait_calls == []
    panel.deleteLater()


class FakeEditor:
    def __init__(self):
        self.selected = "needle"
        self.has_selection = True
        self.find_first_results = []
        self.find_next_results = []
        self.find_first_calls = []
        self.replacements = []
        self.focused = False

    def hasSelectedText(self):
        return self.has_selection

    def selectedText(self):
        return self.selected

    def findFirst(self, *args):
        self.find_first_calls.append(args)
        if self.find_first_results:
            return self.find_first_results.pop(0)
        return True

    def findNext(self):
        if self.find_next_results:
            return self.find_next_results.pop(0)
        return False

    def replace(self, replacement):
        self.replacements.append(replacement)

    def setFocus(self):
        self.focused = True


class FakeFindWindow(QWidget):
    def __init__(self, editor):
        super().__init__()
        self._editor = editor
        self._central = QWidget()
        self._central.resize(700, 400)
        self._tab_manager = SimpleNamespace(current_editor=lambda: self._editor)

    def centralWidget(self):
        return self._central


def test_find_replace_bar_uses_editor_selection_and_replace_workflows(qapp):
    editor = FakeEditor()
    window = FakeFindWindow(editor)
    bar = FindReplaceBar(window)

    bar.toggle_find()
    assert not bar.isHidden()
    assert bar._find_input.text() == "needle"

    editor.find_first_calls.clear()
    editor.find_first_results = [False]
    bar._case_btn.setChecked(True)
    bar._word_btn.setChecked(True)
    bar._regex_btn.setChecked(True)
    bar.find_next()
    assert editor.find_first_calls[-1][:6] == ("needle", True, True, True, True, True)
    assert bar._match_label.text() == "No results"

    editor.find_first_results = [True]
    bar.find_previous()
    assert editor.find_first_calls[-1][5] is False

    bar.toggle_replace()
    assert bar._replace_visible is True
    assert not bar._replace_row.isHidden()
    bar._replace_input.setText("new")
    editor.find_first_results = [True]
    bar.replace_current()
    assert editor.replacements[-1] == "new"

    bar._find_input.setText("needle")
    editor.replacements.clear()
    editor.find_first_results = [True]
    editor.find_next_results = [True, False]
    bar.replace_all()
    assert editor.replacements == ["new", "new"]
    assert bar._match_label.text() == "2 replaced"

    bar.hide_bar()
    assert not bar.isVisible()
    assert editor.focused is True
    bar.deleteLater()
    window.deleteLater()


def test_symbol_outline_parses_symbols_preserves_tree_on_syntax_error_and_emits_navigation(qapp):
    panel = SymbolOutlinePanel()
    navigated = Recorder()
    panel.navigate_to_line.connect(navigated)

    panel.update_symbols(
        "class Greeter:\n"
        "    def greet(self):\n"
        "        return 'hi'\n"
        "\n"
        "async def load():\n"
        "    return 42\n"
    )

    assert panel._tree.topLevelItemCount() == 2
    class_item = panel._tree.topLevelItem(0)
    method_item = class_item.child(0)
    assert class_item.text(0).endswith("Greeter")
    assert method_item.text(0).endswith("greet")

    panel._on_item_clicked(method_item, 0)
    assert navigated.calls == [(1,)]

    panel.update_symbols("def broken(")
    assert panel._tree.topLevelItemCount() == 2

    panel.apply_icon_theme("#FF00AA", is_dark=True)
    panel.resize(260, 180)
    panel.show()
    qapp.processEvents()
    assert panel._tree.viewport().grab().isNull() is False

    panel.clear_symbols()
    assert panel._tree.topLevelItemCount() == 0
    panel.deleteLater()


def test_ai_chat_panel_builds_context_streams_messages_and_handles_insert_links(qapp):
    panel = AIChatPanel()
    requested = Recorder()
    stopped = Recorder()
    inserted = Recorder()
    setup = Recorder()
    panel.chat_requested.connect(requested)
    panel.chat_stop_requested.connect(stopped)
    panel.code_insert_requested.connect(inserted)
    panel.setup_requested.connect(setup)

    large_source = "print('start')\n" + ("x = 1\n" * 2000) + "print('end')\n"
    panel.update_editor_context("demo.py", "main", 2, large_source)
    prompt = panel._build_system_prompt()
    assert 'file "demo.py"' in prompt
    assert "inside \"main\"" in prompt
    assert "at line 3" in prompt
    assert "middle of file omitted" in prompt

    panel.set_model_name("qwen3")
    assert "qwen3" in panel._model_label.text()
    panel.apply_accent("#445566", True)
    panel.set_connected(False)
    assert not panel._input_area.isEnabled()
    assert panel._model_label.text() == "ollama"
    assert not panel._setup_btn.isHidden()
    panel._setup_btn.click()
    assert setup.calls == [()]
    panel.set_connected(True)
    assert panel._input_area.isEnabled()
    assert panel._setup_btn.isHidden()

    panel._input_area.setPlainText("Explain this file")
    panel._on_send()
    assert panel._streaming is True
    assert panel._messages == [{"role": "user", "content": "Explain this file"}]
    assert requested.calls[-1][0][-1] == {"role": "user", "content": "Explain this file"}

    panel.append_token("Here is code:\n")
    panel.append_token("```python\nprint('hi')\n```")
    assert "print('hi')" in panel._current_assistant_text
    assert "color:#445566" in panel._format_content_html(
        panel._current_assistant_text,
        allow_insert=True,
    )
    assert "#4A90D9" not in panel._format_content_html(
        panel._current_assistant_text,
        allow_insert=True,
    )
    panel.finish_response()
    assert panel._messages[-1]["role"] == "assistant"
    assert panel._streaming is False

    panel._on_link_clicked_str("meadowpy://insert-code/0")
    assert inserted.calls == [("print('hi')",)]
    panel._on_link_clicked_str("meadowpy://insert-code/not-an-index")

    panel.show_error("Ollama is unavailable")
    assert panel._messages[-1] == {"role": "error", "content": "Ollama is unavailable"}

    panel.send_message_programmatic("Try again")
    assert panel._streaming is True
    assert requested.calls[-1][0][-1] == {"role": "user", "content": "Try again"}
    panel._current_assistant_text = "partial answer"
    panel._on_stop()
    assert stopped.calls == [()]
    assert panel._messages[-1]["role"] == "stopped"
    assert panel._messages[-2] == {"role": "assistant", "content": "partial answer"}

    panel.clear_chat()
    assert panel._messages == []
    assert panel._chat_view.get_all_plain_text() == ""
    panel.deleteLater()


def test_ai_chat_render_restores_scroll_after_rebuild(monkeypatch, qapp):
    panel = AIChatPanel()

    monkeypatch.setattr(
        ai_chat_panel_module.QTimer,
        "singleShot",
        lambda _ms, callback: callback(),
    )

    class FakeChatView:
        def __init__(self):
            self.value = 180
            self.restored_values = []
            self.bottom_calls = 0
            self.updates_enabled = True
            self.update_states = []

        def scroll_value(self):
            return self.value

        def updatesEnabled(self):
            return self.updates_enabled

        def setUpdatesEnabled(self, enabled):
            self.updates_enabled = enabled
            self.update_states.append(enabled)

        def is_at_bottom(self, slack=20):
            return False

        def clear(self):
            self.value = 0

        def add_bubble(self, _role, _html_content):
            return SimpleNamespace(set_html=lambda _html: None)

        def add_centered(self, _html_content, _object_name):
            return SimpleNamespace()

        def scroll_to_value(self, value):
            self.value = value
            self.restored_values.append(value)

        def scroll_to_bottom(self):
            self.bottom_calls += 1

    chat_view = FakeChatView()
    panel._chat_view = chat_view
    panel._messages = [
        {"role": "user", "content": "Question"},
        {"role": "assistant", "content": "Answer"},
    ]
    panel._render_chat()

    assert chat_view.update_states[0] is False
    assert chat_view.update_states[-1] is True
    assert len(chat_view.restored_values) >= 2
    assert all(value == 180 for value in chat_view.restored_values)
    assert chat_view.bottom_calls == 0
    panel.deleteLater()


def test_shortcut_reference_dialog_filters_categories_rows_and_empty_state(qapp):
    dialog = ShortcutReferenceDialog()
    assert len(dialog._cards) >= 5

    dialog._on_filter("debug")
    visible_cards = [card for card in dialog._cards if not card.isHidden()]
    assert len(visible_cards) == 1
    assert dialog._selected_id.startswith("debug.")
    assert dialog._no_results.isHidden()

    dialog._on_filter("ctrl+shift+definitely-missing")
    assert all(card.isHidden() for card in dialog._cards)
    assert not dialog._no_results.isHidden()

    dialog._on_filter("")
    assert all(not card.isHidden() for card in dialog._cards)
    assert dialog._no_results.isHidden()
    dialog.deleteLater()


def test_shortcut_reference_dialog_keyboard_navigation_moves_visible_selection(qapp):
    dialog = ShortcutReferenceDialog()
    try:
        dialog._on_filter("debug")
        visible_ids = [row.definition.id for row in dialog._visible_rows()]
        assert len(visible_ids) > 2
        assert dialog._selected_id == visible_ids[0]

        down = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Down,
            Qt.KeyboardModifier.NoModifier,
        )
        up = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Up,
            Qt.KeyboardModifier.NoModifier,
        )
        page_down = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_PageDown,
            Qt.KeyboardModifier.NoModifier,
        )
        home = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Home,
            Qt.KeyboardModifier.NoModifier,
        )
        end = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_End,
            Qt.KeyboardModifier.NoModifier,
        )

        assert dialog.eventFilter(dialog._search, down) is True
        assert dialog._selected_id == visible_ids[1]

        assert dialog.eventFilter(dialog._search, up) is True
        assert dialog._selected_id == visible_ids[0]

        assert dialog.eventFilter(dialog._search, page_down) is True
        assert dialog._selected_id in visible_ids[1:]

        assert dialog.eventFilter(dialog._search, home) is False
        dialog.keyPressEvent(end)
        assert dialog._selected_id == visible_ids[-1]
        dialog.keyPressEvent(home)
        assert dialog._selected_id == visible_ids[0]
    finally:
        dialog.deleteLater()


def test_shortcut_reference_badge_row_renders_keys_and_empty_state(qapp):
    previous_stylesheet = qapp.styleSheet()
    row = shortcut_reference_module._ShortcutBadgeRow("Ctrl + Alt + S")
    try:
        qapp.setStyleSheet(
            """
            #shortcutKeyBadge { background: #112233; color: #AABBCC; }
            #shortcutEmptyBadge { color: #445566; }
            """
        )

        assert row._keys == ["Ctrl", "Alt", "S"]
        fill, text = row._badge_colors()
        assert fill.name().upper() == "#112233"
        assert text.name().upper() == "#AABBCC"
        assert (
            shortcut_reference_module._stylesheet_color("#missing", "color")
            is None
        )

        row.resize(row.sizeHint())
        assert row.grab().isNull() is False

        row.set_shortcut("")

        assert row._keys == []
        assert row.sizeHint().height() == 24
        assert row._empty_color().name().upper() == "#445566"
        assert row.grab().isNull() is False
    finally:
        qapp.setStyleSheet(previous_stylesheet)
        row.deleteLater()


def test_shortcut_reset_button_styles_include_hover_and_disabled_states(qapp):
    default_stylesheet = get_stylesheet("default_dark")
    high_contrast_stylesheet = get_stylesheet("default_high_contrast")

    assert "#shortcutResetBtn:enabled:hover" in default_stylesheet
    assert "#shortcutResetBtn:disabled" in default_stylesheet
    assert "#shortcutResetBtn:enabled:hover" in high_contrast_stylesheet
    assert "#shortcutResetBtn:disabled" in high_contrast_stylesheet


def test_shortcut_capture_dialog_ignores_typing_keys_and_accepts_function_keys(qapp):
    definition = shortcut_reference_module.ShortcutDefinition(
        "test.capture",
        "Test",
        "Capture Test",
        "Ctrl+T",
        "Used by the shortcut capture dialog test.",
    )
    dialog = shortcut_reference_module._ShortcutCaptureDialog(definition, "Ctrl+T")
    try:
        plain_letter = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_A,
            Qt.KeyboardModifier.NoModifier,
            "a",
        )
        shifted_letter = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_A,
            Qt.KeyboardModifier.ShiftModifier,
            "A",
        )
        function_key = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_F5,
            Qt.KeyboardModifier.NoModifier,
        )

        dialog.keyPressEvent(plain_letter)
        dialog.keyPressEvent(shifted_letter)
        assert dialog.shortcut() == ""
        assert dialog.result() != QDialog.DialogCode.Accepted.value

        dialog.keyPressEvent(function_key)
        assert dialog.shortcut() == "F5"
        assert dialog.result() == QDialog.DialogCode.Accepted.value
    finally:
        dialog.deleteLater()


def test_shortcut_reference_dialog_reflects_custom_shortcuts_and_reset(qapp, tmp_path):
    settings = Settings(tmp_path)
    dialog = ShortcutReferenceDialog(settings=settings)

    dialog._select_shortcut("file.preferences")
    assert dialog._detail_title.text() == "Preferences"
    assert dialog._detail_badges._keys == ["Ctrl", ","]
    assert get_shortcut(settings, "file.preferences") == "Ctrl+,"

    dialog._select_shortcut("file.save")
    assert dialog._detail_title.text() == "Save"
    assert not dialog._reset_btn.isEnabled()

    set_shortcut(settings, "file.save", "Ctrl+Alt+S")
    dialog._refresh_all()

    assert dialog._rows_by_id["file.save"]._shortcut_text == "ctrl+alt+s"
    assert dialog._detail_title.text() == "Save"
    assert dialog._reset_btn.isEnabled()
    assert "customized" in dialog._default_note.text()

    dialog._on_reset_current()

    assert get_shortcut(settings, "file.save") == "Ctrl+S"
    assert not dialog._reset_btn.isEnabled()
    dialog.deleteLater()


def test_shortcut_reference_dialog_clears_shortcut_from_capture(monkeypatch, qapp, tmp_path):
    settings = Settings(tmp_path)
    dialog = ShortcutReferenceDialog(settings=settings)
    captured = []

    class FakeCaptureDialog:
        def __init__(self, definition, current_shortcut, parent=None):
            captured.append((definition.id, current_shortcut, parent))

        def exec(self):
            return QDialog.DialogCode.Accepted

        def shortcut(self):
            return ""

    monkeypatch.setattr(
        shortcut_reference_module,
        "_ShortcutCaptureDialog",
        FakeCaptureDialog,
    )

    dialog._select_shortcut("file.save")
    dialog._on_change_clicked()

    assert captured == [("file.save", "Ctrl+S", dialog)]
    assert get_shortcut(settings, "file.save") == ""
    assert dialog._rows_by_id["file.save"]._shortcut_text == ""
    assert dialog._reset_btn.isEnabled()
    assert "customized" in dialog._default_note.text()
    dialog.deleteLater()


def test_shortcut_reference_dialog_handles_conflict_pick_and_use(monkeypatch, qapp, tmp_path):
    settings = Settings(tmp_path)
    dialog = ShortcutReferenceDialog(settings=settings)
    capture_shortcuts = iter(["Ctrl+O", "Ctrl+Alt+S"])
    conflict_choices = iter(["pick"])
    captures = []
    conflicts = []

    class FakeCaptureDialog:
        def __init__(self, definition, current_shortcut, parent=None):
            captures.append((definition.id, current_shortcut, parent))
            self._shortcut = next(capture_shortcuts)

        def exec(self):
            return QDialog.DialogCode.Accepted

        def shortcut(self):
            return self._shortcut

    class FakeConflictDialog:
        def __init__(self, shortcut, target, conflict, parent=None):
            conflicts.append((shortcut, target.id, conflict.id, parent))
            self._choice = next(conflict_choices)

        def exec(self):
            return QDialog.DialogCode.Accepted

        def choice(self):
            return self._choice

    monkeypatch.setattr(
        shortcut_reference_module,
        "_ShortcutCaptureDialog",
        FakeCaptureDialog,
    )
    monkeypatch.setattr(
        shortcut_reference_module,
        "_ShortcutConflictDialog",
        FakeConflictDialog,
    )

    dialog._select_shortcut("file.save")
    dialog._on_change_clicked()

    assert captures == [
        ("file.save", "Ctrl+S", dialog),
        ("file.save", "Ctrl+S", dialog),
    ]
    assert conflicts == [("Ctrl+O", "file.save", "file.open", dialog)]
    assert get_shortcut(settings, "file.save") == "Ctrl+Alt+S"
    assert get_shortcut(settings, "file.open") == "Ctrl+O"

    capture_shortcuts = iter(["Ctrl+O"])
    conflict_choices = iter(["use"])
    captures.clear()
    conflicts.clear()

    dialog._select_shortcut("file.save_as")
    dialog._on_change_clicked()

    assert captures == [("file.save_as", "Ctrl+Shift+S", dialog)]
    assert conflicts == [("Ctrl+O", "file.save_as", "file.open", dialog)]
    assert get_shortcut(settings, "file.save_as") == "Ctrl+O"
    assert get_shortcut(settings, "file.open") == ""
    assert dialog._rows_by_id["file.save_as"]._shortcut_text == "ctrl+o"
    dialog.deleteLater()


def test_file_explorer_context_actions_create_rename_delete_and_theme(monkeypatch, qapp, tmp_path):
    from meadowpy.ui import file_explorer as file_explorer_module

    panel = FileExplorerPanel()
    created = Recorder()
    renamed = Recorder()
    deleted = Recorder()
    root_changed = Recorder()
    panel.file_created.connect(created)
    panel.file_renamed.connect(renamed)
    panel.file_deleted.connect(deleted)
    panel.root_folder_changed.connect(root_changed)

    text_answers = iter([
        ("new.py", True),
        ("new.py", True),
        ("pkg", True),
        ("renamed.py", True),
    ])
    warnings = []
    criticals = []
    monkeypatch.setattr(
        file_explorer_module.QInputDialog,
        "getText",
        lambda *args, **kwargs: next(text_answers),
    )
    monkeypatch.setattr(
        file_explorer_module.QMessageBox,
        "warning",
        lambda parent, title, body: warnings.append((title, body)),
    )
    monkeypatch.setattr(
        file_explorer_module.QMessageBox,
        "critical",
        lambda parent, title, body: criticals.append((title, body)),
    )
    monkeypatch.setattr(
        file_explorer_module.QMessageBox,
        "question",
        lambda *args, **kwargs: file_explorer_module.QMessageBox.StandardButton.Yes,
    )

    panel.set_root_folder(str(tmp_path))
    assert panel.root_path == str(tmp_path)
    assert root_changed.calls == [(str(tmp_path),)]
    assert panel._project_badge.text() == tmp_path.name.upper()
    assert not panel._tree.isHidden()

    panel._action_new_file(tmp_path)
    new_file = tmp_path / "new.py"
    assert new_file.exists()
    assert created.calls == [(str(new_file),)]

    panel._action_new_file(tmp_path)
    assert warnings[-1][0] == "File Exists"

    panel._action_new_folder(tmp_path)
    assert (tmp_path / "pkg").is_dir()

    old_file = tmp_path / "old.py"
    old_file.write_text("print('old')\n", encoding="utf-8")
    panel._fs_model = SimpleNamespace(filePath=lambda index: str(old_file))
    panel._action_rename(object())
    renamed_file = tmp_path / "renamed.py"
    assert renamed_file.exists()
    assert renamed.calls == [(str(old_file), str(renamed_file))]

    panel._fs_model = SimpleNamespace(filePath=lambda index: str(renamed_file))
    panel._action_delete(object())
    assert not renamed_file.exists()
    assert deleted.calls[-1] == (str(renamed_file),)

    doomed_dir = tmp_path / "doomed"
    doomed_dir.mkdir()
    (doomed_dir / "child.txt").write_text("bye\n", encoding="utf-8")
    panel._fs_model = SimpleNamespace(filePath=lambda index: str(doomed_dir))
    panel._action_delete(object())
    assert not doomed_dir.exists()
    assert deleted.calls[-1] == (str(doomed_dir),)
    assert criticals == []

    panel._fs_model = None
    panel._proxy = None
    panel.apply_icon_theme("#3B82F6", is_dark=False)
    assert "#3B82F6" in panel._project_badge.styleSheet()
    panel.collapse_all()
    panel.refresh()
    panel.deleteLater()


def test_keyword_popup_exposes_content(qapp):
    popup = KeywordHelpPopup(
        "for",
        "Repeat code for every item in a collection.",
        "for name in names:\n    print(name)",
    )
    code_widgets = popup.findChildren(QTextEdit)
    assert code_widgets[0].toPlainText().startswith("for name")
    assert popup.minimumWidth() == 380

    popup.deleteLater()


def test_accent_color_picker_internal_widgets_pick_render_and_clamp(qapp):
    class FakeMouseEvent:
        def __init__(
            self,
            x=0.0,
            y=0.0,
            *,
            button=Qt.MouseButton.LeftButton,
            buttons=Qt.MouseButton.LeftButton,
        ):
            self._position = QPointF(float(x), float(y))
            self._button = button
            self._buttons = buttons

        def position(self):
            return self._position

        def button(self):
            return self._button

        def buttons(self):
            return self._buttons

    canvas = _SVCanvas()
    canvas.resize(240, 200)
    sv_changed = Recorder()
    canvas.sv_changed.connect(sv_changed)

    canvas.set_hsv(0.25, 0.5, 0.75)
    assert canvas._hue == 0.25
    assert canvas._sat == 0.5
    assert canvas._val == 0.75
    assert sv_changed.calls == []
    assert not canvas.grab().isNull()

    canvas._pick(canvas.width() * 2, -10)
    assert sv_changed.calls[-1] == (1.0, 1.0)
    canvas._pick(-10, canvas.height() * 2)
    assert sv_changed.calls[-1] == (0.0, 0.0)

    canvas.mousePressEvent(FakeMouseEvent(canvas.width() / 2, canvas.height() / 2))
    sat, val = sv_changed.calls[-1]
    assert abs(sat - 0.5) < 0.01
    assert abs(val - 0.5) < 0.01
    call_count = len(sv_changed.calls)
    canvas.mousePressEvent(
        FakeMouseEvent(
            canvas.width() / 2,
            canvas.height() / 2,
            button=Qt.MouseButton.RightButton,
        )
    )
    canvas.mouseMoveEvent(
        FakeMouseEvent(
            canvas.width(),
            canvas.height(),
            buttons=Qt.MouseButton.NoButton,
        )
    )
    assert len(sv_changed.calls) == call_count
    canvas.mouseMoveEvent(
        FakeMouseEvent(
            canvas.width(),
            canvas.height(),
            buttons=Qt.MouseButton.LeftButton,
        )
    )
    assert sv_changed.calls[-1] == (1.0, 0.0)

    huebar = _HueBar()
    huebar.resize(20, 200)
    hue_changed = Recorder()
    huebar.hue_changed.connect(hue_changed)

    huebar.set_hue(0.4)
    assert huebar._hue == 0.4
    assert hue_changed.calls == []
    assert not huebar.grab().isNull()

    huebar._pick(huebar.height() * 2)
    assert hue_changed.calls[-1] == (1.0,)
    huebar._pick(-10)
    assert hue_changed.calls[-1] == (0.0,)

    huebar.mousePressEvent(FakeMouseEvent(0, huebar.height() / 2))
    (hue,) = hue_changed.calls[-1]
    assert abs(hue - 0.5) < 0.01
    call_count = len(hue_changed.calls)
    huebar.mousePressEvent(
        FakeMouseEvent(
            0,
            huebar.height() / 2,
            button=Qt.MouseButton.RightButton,
        )
    )
    huebar.mouseMoveEvent(
        FakeMouseEvent(0, huebar.height(), buttons=Qt.MouseButton.NoButton)
    )
    assert len(hue_changed.calls) == call_count
    huebar.mouseMoveEvent(
        FakeMouseEvent(0, huebar.height(), buttons=Qt.MouseButton.LeftButton)
    )
    assert hue_changed.calls[-1] == (1.0,)

    huebar.deleteLater()
    canvas.deleteLater()


def test_accent_color_picker_preserves_hue_for_grayscale_colors(qapp):
    dialog = AccentColorPickerDialog("#336699")

    dialog._on_hue_changed(0.33)
    previous_hue = dialog._h
    dialog._push_color(QColor("#808080"))

    assert dialog._h == previous_hue
    assert dialog._s == 0.0
    assert dialog.selected_hex() == "#808080"

    dialog.deleteLater()


def test_dialogs_sync_color_example_about_and_preferences_state(monkeypatch, qapp, tmp_path):
    color_dialog = AccentColorPickerDialog("#336699")
    assert color_dialog.selected_hex() == "#336699"

    color_dialog._on_hex_edited("FF0000")
    assert color_dialog.selected_hex() == "#FF0000"
    assert color_dialog._spin_r.value() == 255

    color_dialog._spin_r.setValue(1)
    color_dialog._spin_g.setValue(2)
    color_dialog._spin_b.setValue(3)
    assert color_dialog.selected_hex() == "#010203"

    color_dialog._on_hue_changed(0.5)
    color_dialog._on_sv_changed(0.25, 0.75)
    assert color_dialog.selected_hex().startswith("#")

    example_dialog = ExampleLibraryDialog()
    example_opened = Recorder()
    example_dialog.example_selected.connect(example_opened)
    assert example_dialog._cat_buttons
    assert example_dialog._example_cards
    first_name = example_dialog._current_name
    first_code = example_dialog._current_code
    assert first_name
    assert first_code

    escaped = ExampleLibraryDialog._code_to_html("print('<tag>')\n\n")
    assert "&lt;tag&gt;" in escaped
    assert "<pre" in escaped

    example_dialog._on_example_clicked(10_000)
    assert not example_dialog._open_btn.isEnabled()
    example_dialog._on_example_clicked(0)
    example_dialog._on_open_clicked()
    assert example_opened.calls[-1] == (
        example_dialog._current_name,
        example_dialog._current_code,
    )

    about_dialog = AboutDialog(FakeSettings({"editor.theme": "default_high_contrast"}))
    assert about_dialog._is_high_contrast is True
    assert about_dialog._palette["accent"] == "#FFFFFF"

    settings = Settings(tmp_path)
    prefs = PreferencesDialog(settings)
    prefs._on_category_changed(5)
    assert prefs._pages.currentIndex() == 5
    filters = prefs._font_combo.fontFilters()
    assert filters & QFontComboBox.FontFilter.ScalableFonts

    current_family = settings.get("editor.font_family")
    target_family = next(
        (
            prefs._font_combo.itemText(i)
            for i in range(prefs._font_combo.count())
            if prefs._font_combo.itemText(i) != current_family
        ),
        current_family,
    )
    prefs._font_combo.blockSignals(True)
    prefs._font_combo.setCurrentFont(QFont(target_family))
    prefs._font_combo.blockSignals(False)

    prefs._stage("editor.font_size", 17)
    prefs._on_theme_changed("custom")
    assert not prefs._custom_theme_container.isHidden()
    prefs._refresh_accent_swatch("#112233")
    assert prefs._accent_hex_label.text() == "#112233"
    prefs._show_lint_style_issues.setChecked(False)
    assert prefs._pending_changes["editor.show_lint_style_issues"] is False
    prefs._restore_tabs.setChecked(True)
    assert prefs._pending_changes["general.restore_tabs_on_startup"] is True
    assert prefs._pending_changes["general.restore_tabs_on_startup_explicit"] is True

    from meadowpy.ui.dialogs import accent_color_picker as accent_module

    class FakeAccentDialog:
        DialogCode = AccentColorPickerDialog.DialogCode

        def __init__(self, current_hex, parent=None):
            self.current_hex = current_hex
            self.parent = parent

        def exec(self):
            return self.DialogCode.Accepted

        def selected_hex(self):
            return "#445566"

    monkeypatch.setattr(accent_module, "AccentColorPickerDialog", FakeAccentDialog)
    prefs._on_pick_accent()
    assert prefs._pending_changes["editor.custom_theme.accent"] == "#445566"

    applied_keys = []
    prefs.preferences_applied.connect(applied_keys.append)
    prefs._apply()
    assert (
        settings.get("editor.font_family")
        == prefs._font_combo.currentFont().family()
    )
    assert settings.get("editor.font_size") == 17
    assert settings.get("editor.theme") == "custom"
    assert settings.get("editor.custom_theme.accent") == "#445566"
    assert settings.get("editor.show_lint_style_issues") is False
    assert settings.get("general.restore_tabs_on_startup") is True
    assert settings.get("general.restore_tabs_on_startup_explicit") is True
    assert prefs._pending_changes == {}
    assert "editor.font_family" in applied_keys[-1]

    prefs.deleteLater()
    about_dialog.deleteLater()
    example_dialog.deleteLater()
    color_dialog.deleteLater()


def test_ollama_setup_dialog_updates_results_and_saves(qapp, tmp_path):
    settings = Settings(tmp_path)
    settings.set("ollama.api_url", "http://localhost:11434/")
    settings.set("ollama.auto_connect", True)
    settings.set("editor.theme", "custom")
    settings.set("editor.custom_theme.base", "dark")
    settings.set("editor.custom_theme.accent", "#445566")

    dialog = OllamaSetupDialog(settings)
    assert _normalize_api_url(" http://localhost:11434/ ") == "http://localhost:11434"
    assert (
        dialog._download_link.palette()
        .color(QPalette.ColorRole.Link)
        .name()
        .upper()
        == "#445566"
    )
    assert (
        dialog._download_link.palette()
        .color(QPalette.ColorRole.LinkVisited)
        .name()
        .upper()
        == "#445566"
    )
    assert 'style="color: #445566;"' in dialog._download_link.text()

    dialog._url_input.setText("http://localhost:11435/")
    dialog._auto_connect.setChecked(False)
    dialog._on_check_finished(True, "Ollama is running.", ["llama3", "qwen3"])

    assert dialog._model_combo.isEnabled()
    assert "2 model" in dialog._models_status.text()
    assert "color: #445566;" == dialog._server_status.styleSheet()
    assert "color: #445566;" == dialog._models_status.styleSheet()
    assert "color: #445566;" == dialog._selected_status.styleSheet()

    dialog._model_combo.setCurrentText("qwen3")
    dialog._save_settings()
    assert settings.get("ollama.api_url") == "http://localhost:11435"
    assert settings.get("ollama.auto_connect") is False
    assert settings.get("ollama.selected_model") == "qwen3"
    assert "qwen3" in dialog._selected_status.text()
    assert "color: #445566;" == dialog._selected_status.styleSheet()
    assert dialog._close_btn.text() == "Close"

    dialog._on_check_finished(False, "Cannot connect", [])
    assert not dialog._model_combo.isEnabled()
    assert "Cannot list models" in dialog._models_status.text()

    dialog.deleteLater()


def test_ollama_setup_check_worker_reports_health_and_models(monkeypatch):
    responses = iter([
        FakeResponse(b"Ollama is running"),
        FakeResponse(b'{"models": [{"name": "llama3"}, {"id": "skip"}]}'),
    ])
    monkeypatch.setattr(
        "meadowpy.ui.dialogs.ollama_setup_dialog.urllib.request.urlopen",
        lambda request, timeout=5: next(responses),
    )
    worker = OllamaSetupCheckWorker("http://localhost:11434/")
    finished = Recorder()
    worker.finished.connect(finished)

    worker.run()

    assert finished.calls == [(True, "Ollama is running", ["llama3"])]


class FakeToolbarWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._settings = FakeSettings({"editor.theme": "default_dark"})
        self.actions_called = []
        self.toolbars = []
        self._run_action = QAction("Run", self)
        self._stop_action = QAction("Stop", self)
        self._debug_action = QAction("Debug", self)
        self._tab_manager = SimpleNamespace(current_editor=lambda: self.editor)
        self.editor = SimpleNamespace(
            display_name="World_Counter.py",
            undo=lambda: self.actions_called.append("undo"),
            redo=lambda: self.actions_called.append("redo"),
        )

    def action_new_file(self):
        self.actions_called.append("new")

    def action_open_file(self):
        self.actions_called.append("open")

    def action_save(self):
        self.actions_called.append("save")

    def action_toggle_find(self):
        self.actions_called.append("find")

    def addToolBar(self, toolbar):
        self.toolbars.append(toolbar)


def test_toolbar_builder_creates_shared_actions_editor_calls_and_glow_state(qapp):
    window = FakeToolbarWindow()
    builder = ToolBarBuilder(window)
    toolbar = builder.build()

    assert toolbar.objectName() == "MainToolBar"
    assert builder._run_btn.objectName() == "runButton"
    assert builder._run_btn.size().width() == builder._run_btn.minimumWidth()
    assert builder._run_btn.height() == 32
    assert builder._run_btn._label_font.bold()
    assert builder._run_btn._label_font.pixelSize() == 13
    oversized_font = builder._run_btn.font()
    oversized_font.setPointSize(24)
    builder._run_btn.setFont(oversized_font)
    assert builder._run_btn._label_font.pixelSize() == 13
    assert builder._run_btn.text() == "Run World_Counter.py"
    assert toolbar.widgetForAction(window._stop_action).objectName() == "stopButton"
    assert toolbar.widgetForAction(window._debug_action).objectName() == "debugButton"
    assert window.toolbars == [toolbar]
    assert window._step_over_action.text() == "Step Over"
    assert not window._step_over_action.isVisible()

    builder._editor_call("undo")
    builder._editor_call("redo")
    builder._editor_call("missing")
    assert window.actions_called == ["undo", "redo"]

    builder.update_run_file_label(
        SimpleNamespace(display_name="World_Counter_With_A_Very_Long_Name.py")
    )
    assert builder._run_btn.displayed_text().endswith("...")
    assert builder._run_btn.width() == builder._run_btn.minimumWidth()

    builder.update_accent_color("#112233")
    assert builder._run_btn._accent.name().upper() == "#112233"

    stop_button = toolbar.widgetForAction(window._stop_action)
    stop_entry = [
        entry for entry in builder._glow._entries
        if entry["btn"] is stop_button
    ][0]

    hover = QEvent(QEvent.Type.HoverEnter)
    press = QEvent(QEvent.Type.MouseButtonPress)
    leave = QEvent(QEvent.Type.HoverLeave)
    assert builder._glow.eventFilter(stop_button, hover) is False
    assert stop_entry["state"] == "hover"
    assert builder._glow.eventFilter(stop_button, press) is False
    assert stop_entry["state"] == "press"
    assert builder._glow.eventFilter(stop_button, leave) is False
    assert stop_entry["state"] == "idle"

    toolbar.deleteLater()
    window.deleteLater()


def test_welcome_and_about_hero_widgets_render_theme_specific_artwork(qapp):
    welcome_hero = _WelcomeHeroWidget()
    welcome_hero.resize(360, 238)
    welcome_hero.apply_theme("default_high_contrast")
    welcome_pixmap = welcome_hero.grab()

    assert welcome_hero._palette["accent"] == "#FFFFFF"
    assert welcome_pixmap.isNull() is False

    about_dialog = AboutDialog(FakeSettings({"editor.theme": "custom"}))
    hero = about_dialog.findChild(QWidget)
    hero.resize(460, 384)
    about_pixmap = hero.grab()

    assert about_dialog._is_high_contrast is False
    assert about_pixmap.isNull() is False

    welcome_hero.deleteLater()
    about_dialog.deleteLater()

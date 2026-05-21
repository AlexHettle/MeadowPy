from __future__ import annotations

from types import SimpleNamespace

from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QAction, QColor, QFont, QKeyEvent, QPalette
from PyQt6.QtWidgets import QFontComboBox, QTextEdit, QToolButton, QWidget

from meadowpy.core.settings import Settings
from meadowpy.ui.ai_chat_panel import AIChatPanel
from meadowpy.ui.debug_toolbar import DebugToolBar
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
from meadowpy.ui.search_panel import SearchPanel, SearchResult, SearchWorker
from meadowpy.ui.symbol_outline import SymbolOutlinePanel
from meadowpy.ui.tool_bar import ToolBarBuilder, ToolbarGlowPainter
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

    matches = []
    totals = []
    worker = SearchWorker(str(tmp_path), "alpha", False, False)
    worker.match_found.connect(matches.append)
    worker.finished.connect(totals.append)
    worker.run()

    assert totals == [3]
    assert [m.line_num for m in matches] == [1, 2, 1]
    assert all(".git" not in m.file_path for m in matches)

    case_totals = []
    case_worker = SearchWorker(str(tmp_path), "alpha", True, False)
    case_worker.finished.connect(case_totals.append)
    case_worker.run()
    assert case_totals == [1]

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
    panel.focus_search()
    assert panel.isVisible()
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


def test_shortcut_reference_dialog_filters_categories_rows_and_empty_state(qapp):
    dialog = ShortcutReferenceDialog()
    assert len(dialog._cards) >= 5

    dialog._on_filter("debug")
    visible_cards = [card for card in dialog._cards if not card.isHidden()]
    assert len(visible_cards) == 1
    assert dialog._no_results.isHidden()

    dialog._on_filter("ctrl+shift+definitely-missing")
    assert all(card.isHidden() for card in dialog._cards)
    assert not dialog._no_results.isHidden()

    dialog._on_filter("")
    assert all(not card.isHidden() for card in dialog._cards)
    assert dialog._no_results.isHidden()
    dialog.deleteLater()


def test_file_explorer_context_actions_create_rename_delete_and_theme(monkeypatch, qapp, tmp_path):
    from meadowpy.ui import file_explorer as file_explorer_module

    panel = FileExplorerPanel()
    created = Recorder()
    renamed = Recorder()
    deleted = Recorder()
    panel.file_created.connect(created)
    panel.file_renamed.connect(renamed)
    panel.file_deleted.connect(deleted)

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


def test_debug_toolbar_and_keyword_popup_expose_action_state_and_content(qapp):
    window = QWidget()
    toolbar = DebugToolBar(window)
    assert not toolbar.isVisible()
    assert [action.text() for action in toolbar.actions()] == [
        "Step Over (F10)",
        "Step Into (F11)",
        "Step Out (Shift+F11)",
    ]

    toolbar.set_paused(False)
    assert all(not action.isEnabled() for action in toolbar.actions())
    toolbar.set_paused(True)
    assert all(action.isEnabled() for action in toolbar.actions())

    popup = KeywordHelpPopup(
        "for",
        "Repeat code for every item in a collection.",
        "for name in names:\n    print(name)",
    )
    code_widgets = popup.findChildren(QTextEdit)
    assert code_widgets[0].toPlainText().startswith("for name")
    assert popup.minimumWidth() == 380

    popup.deleteLater()
    toolbar.deleteLater()
    window.deleteLater()


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

from __future__ import annotations

from PyQt6.QtCore import QCoreApplication, QEvent, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QMessageBox, QToolButton, QWidget

from meadowpy.core.settings import Settings
from meadowpy.resources.resource_loader import run_button_accent_hex
from meadowpy.ui import tab_manager as tab_module
from meadowpy.ui.tab_manager import TabManager
from meadowpy.ui.welcome_widget import TEMPLATES, WelcomeWidget


class ParentWindow(QWidget):
    def __init__(self):
        super().__init__()


class FakeFileManager:
    def __init__(self):
        self.saved = 0
        self.saved_as = 0
        self.last_save_error = None
        self.last_save_error_path = None

    def save_file(self, file_path, content):
        self.saved += 1
        return True

    def save_file_as(self, content, parent=None):
        self.saved_as += 1
        return "/fake/saved.py"


class FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)


class FakeTabEditor(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.file_path = None
        self._untitled_name = "Untitled"
        self._text = ""
        self._modified = False
        self.deleted_later = False
        self.modification_changed = FakeSignal()

    @property
    def is_modified(self):
        return self._modified

    @property
    def display_name(self):
        if self.file_path:
            from pathlib import Path

            return Path(self.file_path).name
        return self._untitled_name

    def setText(self, text):
        self._text = text

    def text(self):
        return self._text

    def setModified(self, modified):
        self._modified = modified

    def deleteLater(self):
        self.deleted_later = True
        super().deleteLater()


def make_settings(tmp_path):
    settings = Settings(tmp_path)
    settings.set("editor.auto_complete", False)
    settings.set("editor.theme", "default_dark")
    settings.set("editor.custom_theme.base", "dark")
    return settings


def test_tab_manager_creates_deduplicates_titles_and_paths(qapp, tmp_path):
    settings = make_settings(tmp_path)
    parent = ParentWindow()
    tabs = TabManager(settings, parent=parent)
    changed = []
    created = []
    tabs.tab_changed.connect(changed.append)
    tabs.editor_created.connect(created.append)

    untitled = tabs.new_tab()
    script = tmp_path / "demo.py"
    opened = tabs.open_file_in_tab(str(script), "print('demo')\n")
    duplicate = tabs.open_file_in_tab(str(script), "ignored")

    assert untitled.display_name == "Untitled-1"
    assert opened is duplicate
    assert created == [untitled, opened]
    assert tabs.current_editor() is opened
    assert tabs.get_open_file_paths() == [str(script)]
    assert tabs.tabText(tabs.indexOf(opened)) == "demo.py"

    opened._untitled_name = "Changed"
    tabs.update_tab_title(tabs.indexOf(opened))
    assert tabs.tabText(tabs.indexOf(opened)) == "demo.py"

    opened.setModified(True)
    tabs._update_modified_indicator(opened, True)
    assert tabs.tabText(tabs.indexOf(opened)) == "demo.py"

    tabs._on_tab_changed(-1)
    assert changed[-1] is None

    tabs.deleteLater()
    parent.deleteLater()


def test_close_tab_prompt_save_discard_cancel_and_close_all(monkeypatch, qapp, tmp_path):
    monkeypatch.setattr(tab_module, "CodeEditor", FakeTabEditor)
    settings = make_settings(tmp_path)
    parent = ParentWindow()
    fake_fm = FakeFileManager()
    tabs = TabManager(settings, fake_fm, parent)
    closed = []
    tabs.editor_closed.connect(closed.append)

    first = tabs.new_tab(str(tmp_path / "first.py"), "print(1)\n")
    first.setModified(True)
    monkeypatch.setattr(
        tab_module.QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Cancel,
    )
    assert tabs.close_tab(tabs.indexOf(first)) is False
    assert tabs.indexOf(first) >= 0
    assert first.deleted_later is False

    monkeypatch.setattr(
        tab_module.QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Save,
    )
    assert tabs.close_tab(tabs.indexOf(first)) is True
    assert fake_fm.saved == 1
    assert first.deleted_later is True
    assert closed == [first]

    second = tabs.new_tab(str(tmp_path / "second.py"), "print(2)\n")
    third = tabs.new_tab(str(tmp_path / "third.py"), "print(3)\n")
    second.setModified(True)
    third.setModified(False)
    monkeypatch.setattr(
        tab_module.QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Discard,
    )
    assert tabs.close_all_tabs() is True
    assert tabs.count() == 0
    assert second.deleted_later is True
    assert third.deleted_later is True
    assert closed == [first, second, third]

    tabs.deleteLater()
    parent.deleteLater()


def test_middle_click_closes_saved_tab_and_prompts_for_modified_tab(
    monkeypatch, qapp, tmp_path
):
    settings = make_settings(tmp_path)
    tabs = TabManager(settings)
    saved = tabs.new_tab(str(tmp_path / "saved.py"), "print('saved')\n")
    modified = tabs.new_tab(str(tmp_path / "modified.py"), "print('modified')\n")
    prompts = []

    def cancel_close(parent, display_name):
        prompts.append((parent, display_name))
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(tab_module, "prompt_save_before_closing", cancel_close)
    tabs.resize(500, 300)
    tabs.show()
    qapp.processEvents()
    modified.setCursorPosition(0, 0)
    modified.insert("# unsaved change\n")
    assert modified.is_modified is True

    bar = tabs.tabBar()
    QTest.mouseClick(
        bar,
        Qt.MouseButton.MiddleButton,
        pos=bar.tabRect(tabs.indexOf(saved)).center(),
    )
    assert tabs.indexOf(saved) == -1
    assert prompts == []

    QTest.mouseClick(
        bar,
        Qt.MouseButton.MiddleButton,
        pos=bar.tabRect(tabs.indexOf(modified)).center(),
    )
    assert tabs.indexOf(modified) == 0
    assert prompts == [(tabs, "modified.py")]

    tabs.deleteLater()


def test_close_prompts_keep_tab_open_when_save_fails(monkeypatch, qapp, tmp_path):
    monkeypatch.setattr(tab_module, "CodeEditor", FakeTabEditor)
    settings = make_settings(tmp_path)
    parent = ParentWindow()
    fake_fm = FakeFileManager()
    fake_fm.last_save_error = PermissionError("Permission denied")
    tabs = TabManager(settings, fake_fm, parent)
    editor = tabs.new_tab(str(tmp_path / "readonly.py"), "print('dirty')\n")
    editor.setModified(True)
    dialogs = []
    monkeypatch.setattr(
        tab_module.QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Save,
    )
    monkeypatch.setattr(
        tab_module.QMessageBox,
        "critical",
        lambda parent, title, body: dialogs.append((title, body)),
    )
    fake_fm.save_file = lambda file_path, content: False

    assert tabs.close_tab(tabs.indexOf(editor)) is False
    assert tabs.indexOf(editor) >= 0
    assert tabs.prompt_save_all() is False
    assert dialogs[0][0] == "Could Not Save File"
    assert "Permission denied" in dialogs[0][1]

    tabs.deleteLater()
    parent.deleteLater()


def test_prompt_save_all_respects_cancel_and_save(monkeypatch, qapp, tmp_path):
    monkeypatch.setattr(tab_module, "CodeEditor", FakeTabEditor)
    settings = make_settings(tmp_path)
    parent = ParentWindow()
    fake_fm = FakeFileManager()
    tabs = TabManager(settings, fake_fm, parent)
    editor = tabs.new_tab(str(tmp_path / "dirty.py"), "print('dirty')\n")
    editor.setModified(True)

    monkeypatch.setattr(
        tab_module.QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Cancel,
    )
    assert tabs.prompt_save_all() is False
    assert tabs.current_editor() is editor

    monkeypatch.setattr(
        tab_module.QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Save,
    )
    assert tabs.prompt_save_all() is True
    assert fake_fm.saved == 1
    assert editor.is_modified is False

    tabs.deleteLater()
    parent.deleteLater()


def test_prompt_save_all_clears_saved_tab_when_later_prompt_is_cancelled(
    monkeypatch, qapp, tmp_path
):
    monkeypatch.setattr(tab_module, "CodeEditor", FakeTabEditor)
    settings = make_settings(tmp_path)
    parent = ParentWindow()
    fake_fm = FakeFileManager()
    tabs = TabManager(settings, fake_fm, parent)
    first = tabs.new_tab(content="print('first')\n")
    second = tabs.new_tab(str(tmp_path / "second.py"), "print('second')\n")
    first.setModified(True)
    second.setModified(True)
    responses = iter(
        [QMessageBox.StandardButton.Save, QMessageBox.StandardButton.Cancel]
    )
    monkeypatch.setattr(
        tab_module.QMessageBox,
        "question",
        lambda *args, **kwargs: next(responses),
    )

    assert tabs.prompt_save_all() is False

    assert fake_fm.saved_as == 1
    assert first.file_path == "/fake/saved.py"
    assert first.is_modified is False
    assert second.is_modified is True
    assert tabs.count() == 2

    tabs.deleteLater()
    parent.deleteLater()


def test_welcome_tab_reuse_theme_update_close_and_template_signal(qapp, tmp_path):
    settings = make_settings(tmp_path)
    parent = ParentWindow()
    tabs = TabManager(settings, parent=parent)

    welcome = tabs.show_welcome_tab("default_dark", "dark", "#2F7A44")
    same = tabs.show_welcome_tab("custom", "light", "#336699")

    assert same is welcome
    assert isinstance(tabs.widget(0), WelcomeWidget)
    assert welcome._hero_widget._palette["accent"] == run_button_accent_hex("custom", "#336699")

    selected = []
    welcome.template_selected.connect(lambda name, code: selected.append((name, code)))
    welcome._on_template_clicked(TEMPLATES[0])
    assert selected == [(TEMPLATES[0]["name"], TEMPLATES[0]["code"])]

    settings.set("editor.theme", "custom")
    settings.set("editor.custom_theme.base", "light")
    settings.set("editor.custom_theme.accent", "#123456")
    tabs.update_theme()
    assert welcome._hero_widget._palette["accent"] == run_button_accent_hex("custom", "#123456")

    destroyed = []
    welcome.destroyed.connect(lambda *_: destroyed.append(True))
    tabs.close_welcome_tab()
    assert tabs.count() == 0
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()
    assert destroyed == [True]

    tabs.deleteLater()
    parent.deleteLater()


def test_deferred_close_button_closes_editor_on_next_event_loop(monkeypatch, qapp, tmp_path):
    scheduled_delays = []
    monkeypatch.setattr(
        tab_module.QTimer,
        "singleShot",
        lambda delay, callback: scheduled_delays.append(delay) or callback(),
    )
    settings = make_settings(tmp_path)
    parent = ParentWindow()
    tabs = TabManager(settings, parent=parent)
    editor = tabs.new_tab(str(tmp_path / "deferred.py"), "print('x')\n")

    tabs._close_editor_tab(editor)

    assert scheduled_delays == [0]
    assert tabs.indexOf(editor) == -1
    tabs.deleteLater()
    parent.deleteLater()


def test_tab_right_widget_and_close_styles_cover_optional_dot_variants(qapp, tmp_path):
    button = QToolButton()
    side = tab_module._TabRightWidget(button, None)
    side.set_modified(True)
    side.refresh_dot_color()

    settings = make_settings(tmp_path)
    tabs = TabManager(settings)
    high_contrast = tabs._close_btn_stylesheet(False, True)
    light = tabs._close_btn_stylesheet(False, False)
    assert "#FFFFFF" in high_contrast
    assert "#60656D" in light
    side.deleteLater()
    tabs.deleteLater()


def test_editor_tab_bar_pointer_release_leave_and_deactivation(qapp, tmp_path):
    settings = make_settings(tmp_path)
    tabs = TabManager(settings)
    tabs.new_tab(content="print('tab')\n")
    bar = tabs.tabBar()
    inside = QPointF(bar.tabRect(0).center())
    outside = QPointF(-10, -10)

    def mouse_event(kind, position, button=Qt.MouseButton.NoButton, buttons=Qt.MouseButton.NoButton):
        return QMouseEvent(
            kind,
            position,
            position,
            button,
            buttons,
            Qt.KeyboardModifier.NoModifier,
        )

    bar.mouseMoveEvent(mouse_event(QEvent.Type.MouseMove, inside))
    assert bar.cursor().shape() == Qt.CursorShape.PointingHandCursor
    bar.mouseMoveEvent(mouse_event(QEvent.Type.MouseMove, outside))
    bar._set_visual_state("editorPressed", True)
    bar.mouseReleaseEvent(
        mouse_event(QEvent.Type.MouseButtonRelease, inside, Qt.MouseButton.LeftButton)
    )
    assert bar.property("editorPressed") is False
    bar._set_visual_state("editorPressed", True)
    bar.leaveEvent(QEvent(QEvent.Type.Leave))
    assert bar.property("editorPressed") is False
    bar._set_visual_state("editorPressed", True)
    bar.event(QEvent(QEvent.Type.WindowDeactivate))
    assert bar.property("editorPressed") is False
    tabs.deleteLater()


def test_tab_metadata_and_close_helpers_ignore_missing_or_non_editor_tabs(
    monkeypatch, qapp, tmp_path
):
    monkeypatch.setattr(tab_module, "CodeEditor", FakeTabEditor)
    settings = make_settings(tmp_path)
    tabs = TabManager(settings)
    editor = tabs.new_tab(content="print('inside')\n")
    outsider = FakeTabEditor(settings)
    tabs._refresh_tab_metadata(-1, editor)
    tabs._refresh_tab_metadata(tabs.count(), editor)
    tabs._update_modified_indicator(outsider, True)

    monkeypatch.setattr(tab_module.QTimer, "singleShot", lambda delay, callback: callback())
    tabs._close_editor_tab(outsider)
    assert tabs.count() == 1

    widget = QWidget()
    index = tabs.addTab(widget, "plain")
    tabs.update_tab_title(index)
    tabs._remove_tab_and_delete(index)
    assert tabs.count() == 1
    outsider.deleteLater()
    tabs.deleteLater()


def test_save_prompt_without_manager_and_failed_save_as_error(
    monkeypatch, qapp, tmp_path
):
    monkeypatch.setattr(tab_module, "CodeEditor", FakeTabEditor)
    settings = make_settings(tmp_path)
    editor = FakeTabEditor(settings)
    tabs = TabManager(settings)
    assert tabs._save_editor_for_prompt(editor) is True
    tabs.deleteLater()

    manager = FakeFileManager()
    manager.save_file_as = lambda content, parent=None: None
    manager.last_save_error = OSError("disk full")
    manager.last_save_error_path = str(tmp_path / "failed.py")
    dialogs = []
    monkeypatch.setattr(
        tab_module.QMessageBox,
        "critical",
        lambda parent, title, body: dialogs.append((title, body)),
    )
    tabs = TabManager(settings, manager)
    editor = tabs.new_tab(content="dirty")
    assert tabs._save_editor_for_prompt(editor) is False
    assert dialogs and "disk full" in dialogs[0][1]
    tabs.deleteLater()


def test_close_all_stops_after_cancelled_tab(monkeypatch, qapp, tmp_path):
    monkeypatch.setattr(tab_module, "CodeEditor", FakeTabEditor)
    tabs = TabManager(make_settings(tmp_path))
    tabs.new_tab(content="dirty")
    tabs.close_tab = lambda index: False
    assert tabs.close_all_tabs() is False
    assert tabs.count() == 1
    tabs.deleteLater()


def test_update_theme_handles_plain_tool_button_and_non_editor_tabs(qapp, tmp_path):
    settings = make_settings(tmp_path)
    tabs = TabManager(settings)
    plain = QWidget()
    index = tabs.addTab(plain, "plain")
    button = QToolButton()
    tabs.tabBar().setTabButton(
        index,
        tab_module.QTabBar.ButtonPosition.RightSide,
        button,
    )
    tabs.update_theme()
    assert button.styleSheet()
    tabs._on_tab_changed(index)
    assert tabs.current_editor() is None
    tabs.deleteLater()

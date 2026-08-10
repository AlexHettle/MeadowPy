from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PyQt6.QtCore import QEvent, QFileInfo, QModelIndex, QPointF, Qt
from PyQt6.QtGui import (
    QAction,
    QColor,
    QIcon,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFileIconProvider,
    QMessageBox,
    QMenuBar,
    QPushButton,
    QStyleOptionViewItem,
    QToolBar,
    QWidget,
)

import meadowpy.ui.file_explorer as file_explorer_module
from meadowpy.ui.file_explorer import (
    _BLOCKED_FILE_TOOLTIP,
    FileExplorerPanel,
    _ClickableLabel,
    _ExplorerIconProvider,
    _FileExplorerItemDelegate,
    _FilteredFileSystemModel,
    _MAX_PREFETCH_SUBDIRS,
    _directory_has_visible_entries,
)
from meadowpy.ui.glow_painter import HeaderGlowPainter
import meadowpy.ui.menu_bar as menu_bar_module
from meadowpy.ui.menu_bar import MenuBarBuilder
from meadowpy.ui.splash_screen import LoadingDotsWidget, MeadowPySplashScreen
from meadowpy.ui.tool_bar import CompactRunControlButton, RunFileButton, ToolBarBuilder


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


class _FakeFileInfo:
    def __init__(self, path, *, is_dir=False, suffix=""):
        self._path = path
        self._is_dir = is_dir
        self._suffix = suffix

    def isDir(self):
        return self._is_dir

    def filePath(self):
        return self._path

    def suffix(self):
        return self._suffix


def test_file_explorer_icon_provider_accessors_and_file_kinds(monkeypatch, qapp):
    icons = {}

    def fake_icon(name, color):
        pixmap = QPixmap(2, 2)
        pixmap.fill(QColor(color))
        icon = QIcon(pixmap)
        icons[(name, color)] = icon
        return icon

    monkeypatch.setattr(file_explorer_module, "load_tinted_icon", fake_icon)
    monkeypatch.setattr(
        file_explorer_module,
        "is_known_unsupported_editor_file",
        lambda path: path.endswith(".docx"),
    )
    provider = _ExplorerIconProvider("#123456", True)

    assert provider.empty_folder_icon().isNull() is False
    assert provider.empty_text_color() == "#6F766B"
    assert provider.blocked_file_icon().isNull() is False
    assert provider.blocked_file_text_color() == "#6F766B"
    assert provider.icon(QFileIconProvider.IconType.Folder).isNull() is False
    assert provider.icon(QFileIconProvider.IconType.File).isNull() is False
    assert provider.icon(_FakeFileInfo("folder", is_dir=True)).isNull() is False
    assert provider.icon(_FakeFileInfo("report.docx")).isNull() is False
    assert provider.icon(_FakeFileInfo("demo.py", suffix="PY")).isNull() is False
    assert provider.icon(_FakeFileInfo("notes.txt", suffix="txt")).isNull() is False


def test_file_explorer_delegate_applies_blocked_and_empty_visuals(qapp):
    pixmap = QPixmap(2, 2)
    pixmap.fill(QColor("#abcdef"))
    icon = QIcon(pixmap)

    class FakePanel:
        blocked = True
        empty = False

        def _is_blocked_editor_file(self, index):
            return self.blocked

        def _blocked_file_text_color(self):
            return "#123456"

        def _blocked_file_icon(self):
            return icon

        def _is_known_empty_folder(self, index):
            return self.empty

        def _empty_folder_text_color(self):
            return "#654321"

        def _empty_folder_icon(self):
            return icon

    panel = FakePanel()
    delegate = _FileExplorerItemDelegate(panel)
    blocked_option = QStyleOptionViewItem()
    delegate.initStyleOption(blocked_option, QModelIndex())
    assert blocked_option.palette.color(blocked_option.palette.ColorRole.Text).name() == "#123456"
    assert blocked_option.icon.isNull() is False

    panel.blocked = False
    panel.empty = True
    empty_option = QStyleOptionViewItem()
    delegate.initStyleOption(empty_option, QModelIndex())
    assert empty_option.palette.color(empty_option.palette.ColorRole.Text).name() == "#654321"
    assert empty_option.icon.isNull() is False
    delegate.deleteLater()


def test_file_explorer_context_menu_dispatches_every_action(monkeypatch, tmp_path):
    action_calls = []
    selected_action = {"value": None}

    class FakeIndex:
        def __init__(self, valid):
            self.valid = valid

        def isValid(self):
            return self.valid

    class FakeMenu:
        def __init__(self, parent):
            self.actions = []

        def addAction(self, text):
            action = SimpleNamespace(text=text)
            self.actions.append(action)
            return action

        def addSeparator(self):
            return None

        def exec(self, position):
            selected = selected_action["value"]
            if selected is None:
                return None
            if selected == "file":
                return self.actions[0]
            if selected == "folder":
                return self.actions[1]
            if selected == "rename":
                return self.actions[-2]
            return self.actions[-1]

    class FakeTree:
        def __init__(self):
            self.valid = True

        def indexAt(self, pos):
            return FakeIndex(self.valid)

        def viewport(self):
            return SimpleNamespace(mapToGlobal=lambda pos: pos)

    tree = FakeTree()
    panel = SimpleNamespace(
        _root_path=str(tmp_path),
        _tree=tree,
        _resolve_target_dir=lambda index: (tmp_path, "source"),
        _action_new_file=lambda path: action_calls.append(("file", path)),
        _action_new_folder=lambda path: action_calls.append(("folder", path)),
        _action_rename=lambda index: action_calls.append(("rename", index)),
        _action_delete=lambda index: action_calls.append(("delete", index)),
    )
    monkeypatch.setattr(file_explorer_module, "QMenu", FakeMenu)

    for action in ("file", "folder", "rename", "delete", None):
        selected_action["value"] = action
        FileExplorerPanel._on_context_menu(panel, object())

    tree.valid = False
    selected_action["value"] = "file"
    FileExplorerPanel._on_context_menu(panel, object())
    panel._root_path = None
    FileExplorerPanel._on_context_menu(panel, object())

    assert action_calls == [
        ("file", tmp_path),
        ("folder", tmp_path),
        ("rename", "source"),
        ("delete", "source"),
        ("file", tmp_path),
    ]


def test_file_explorer_action_failures_warn_without_emitting(
    monkeypatch,
    qapp,
    tmp_path,
):
    panel = FileExplorerPanel()
    warnings = []
    monkeypatch.setattr(
        file_explorer_module.QMessageBox,
        "warning",
        lambda *args: warnings.append(("warning", args[-1])),
    )
    monkeypatch.setattr(
        file_explorer_module.QMessageBox,
        "critical",
        lambda *args: warnings.append(("critical", args[-1])),
    )
    monkeypatch.setattr(
        file_explorer_module.QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

    existing = tmp_path / "existing.py"
    existing.write_text("", encoding="utf-8")
    responses = iter(
        (
            ("existing.py", True),
            ("existing.py", True),
            ("renamed.py", True),
        )
    )
    monkeypatch.setattr(
        file_explorer_module.QInputDialog,
        "getText",
        lambda *args, **kwargs: next(responses),
    )
    panel._action_new_file(tmp_path)
    panel._action_new_folder(tmp_path)

    panel._fs_model = SimpleNamespace(filePath=lambda index: str(existing))
    (tmp_path / "renamed.py").write_text("", encoding="utf-8")
    panel._action_rename(object())

    monkeypatch.setattr(
        file_explorer_module,
        "shutil",
        SimpleNamespace(
            rmtree=lambda path: (_ for _ in ()).throw(OSError("locked"))
        ),
    )
    folder = tmp_path / "folder"
    folder.mkdir()
    panel._fs_model = SimpleNamespace(filePath=lambda index: str(folder))
    panel._action_delete(object())

    assert [kind for kind, _message in warnings] == [
        "warning",
        "warning",
        "warning",
        "critical",
    ]
    assert folder.exists()
    panel.deleteLater()


def test_file_explorer_filesystem_errors_and_panel_fallbacks(monkeypatch, qapp, tmp_path):
    class FailingDirectory:
        def __init__(self, value):
            self.value = value

        def iterdir(self):
            raise OSError("denied")

    with monkeypatch.context() as patch:
        patch.setattr(file_explorer_module, "Path", FailingDirectory)
        assert _directory_has_visible_entries("blocked") is None

    panel = FileExplorerPanel()
    panel._icon_provider = None
    assert panel._empty_folder_icon().isNull()
    assert panel._empty_folder_text_color() == "#6F766B"
    assert panel._blocked_file_icon().isNull()
    assert panel._blocked_file_text_color() == "#6F766B"
    panel._on_title_new_file()
    panel._fs_model = None
    panel._prefetch_subdirs(QModelIndex())

    class BrokenProxy:
        def rowCount(self, index):
            raise RuntimeError("stale index")

    panel._proxy = BrokenProxy()
    panel._fs_model = SimpleNamespace(rowCount=lambda index: 4)
    valid_index = SimpleNamespace(isValid=lambda: True)
    assert panel._visible_child_count(valid_index, object()) == 4
    panel.deleteLater()


def test_file_explorer_create_and_rename_os_errors_are_reported(
    monkeypatch,
    qapp,
):
    class FailingPath:
        def __init__(self, value="old.py"):
            self.value = str(value)
            self.name = Path(self.value).name
            self.parent = self

        def __truediv__(self, name):
            return FailingPath(name)

        def exists(self):
            return False

        def touch(self):
            raise OSError("touch denied")

        def mkdir(self, parents=False):
            raise OSError("mkdir denied")

        def rename(self, target):
            raise OSError("rename denied")

    panel = FileExplorerPanel()
    messages = []
    responses = iter((("new.py", True), ("folder", True), ("renamed.py", True)))
    monkeypatch.setattr(file_explorer_module, "Path", FailingPath)
    monkeypatch.setattr(
        file_explorer_module.QInputDialog,
        "getText",
        lambda *args, **kwargs: next(responses),
    )
    monkeypatch.setattr(
        file_explorer_module.QMessageBox,
        "critical",
        lambda *args: messages.append(args[-1]),
    )
    parent = FailingPath("parent")
    panel._action_new_file(parent)
    panel._action_new_folder(parent)
    panel._fs_model = SimpleNamespace(filePath=lambda index: "old.py")
    panel._action_rename(object())

    assert messages == [
        "Could not create file:\ntouch denied",
        "Could not create folder:\nmkdir denied",
        "Could not rename:\nrename denied",
    ]
    panel.deleteLater()


def test_menu_bar_rebuilds_recent_files_and_routes_edit_commands(
    monkeypatch,
    qapp,
    tmp_path,
):
    opened = []
    cleared = []
    recent_paths = [str(tmp_path / "demo.py"), "standalone.py"]
    recent_files = SimpleNamespace(
        get_files=lambda: recent_paths,
        clear=lambda: cleared.append(True),
    )
    window = SimpleNamespace(
        _recent_files=recent_files,
        open_recent_file=opened.append,
    )
    builder = MenuBarBuilder(window)
    builder._recent_files_menu = menu_bar_module.QMenu()

    builder.rebuild_recent_files_menu()

    actions = builder._recent_files_menu.actions()
    assert actions[0].text() == f"{tmp_path.name}/demo.py"
    assert actions[0].toolTip() == recent_paths[0]
    assert actions[1].text() == "standalone.py"
    actions[0].trigger()
    actions[-1].trigger()
    assert opened == [recent_paths[0]]
    assert cleared == [True]

    focus_calls = []
    focus = SimpleNamespace(copy=lambda: focus_calls.append("focus"))
    monkeypatch.setattr(
        QApplication,
        "focusWidget",
        staticmethod(lambda: focus),
    )
    builder._focused_widget_call("copy")
    assert focus_calls == ["focus"]

    editor_calls = []
    editor = SimpleNamespace(copy=lambda: editor_calls.append("editor"))
    window._tab_manager = SimpleNamespace(current_editor=lambda: editor)
    monkeypatch.setattr(
        QApplication,
        "focusWidget",
        staticmethod(lambda: None),
    )
    builder._focused_widget_call("copy")
    assert editor_calls == ["editor"]
    window._tab_manager = SimpleNamespace(current_editor=lambda: None)
    builder._editor_call("copy")
    builder._recent_files_menu.deleteLater()


class FakeToolbarWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._settings = FakeSettings({"editor.theme": "default_dark"})
        self._run_action = QAction("Run", self)
        self._stop_action = QAction("Stop", self)
        self._debug_action = QAction("Debug", self)
        self._tab_manager = SimpleNamespace(current_editor=lambda: None)
        self.actions_called = []
        self.toolbars = []

    def action_new_file(self):
        pass

    def action_open_file(self):
        pass

    def action_save(self):
        self.actions_called.append("save")

    def action_toggle_find(self):
        pass

    def addToolBar(self, toolbar):
        self.toolbars.append(toolbar)


class TrackingSurface(QWidget):
    def __init__(self):
        super().__init__()
        self.update_count = 0

    def update(self):
        self.update_count += 1
        super().update()


class HoverButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._under_mouse = False

    def underMouse(self):
        return self._under_mouse


def test_header_glow_painter_tracks_button_states_and_renders(qapp):
    surface = TrackingSurface()
    surface.resize(96, 48)
    button = HoverButton("Run", surface)
    button.setGeometry(12, 8, 40, 28)
    painter = HeaderGlowPainter(surface)
    painter.add_button(button, QColor("#33AA55"))
    entry = painter._entries[0]

    assert painter.eventFilter(button, QEvent(QEvent.Type.HoverEnter)) is False
    assert entry["state"] == "hover"
    assert surface.update_count == 1

    assert painter.eventFilter(button, QEvent(QEvent.Type.HoverLeave)) is False
    assert entry["state"] == "idle"

    assert painter.eventFilter(button, QEvent(QEvent.Type.MouseButtonPress)) is False
    assert entry["state"] == "press"

    button._under_mouse = True
    assert painter.eventFilter(button, QEvent(QEvent.Type.MouseButtonRelease)) is False
    assert entry["state"] == "hover"

    painter.set_button_color(button, QColor("#445566"))
    assert entry["color"].name().upper() == "#445566"

    pixmap = surface.grab()
    assert pixmap.isNull() is False

    button.setEnabled(False)
    pixmap = surface.grab()
    assert pixmap.isNull() is False
    assert entry["state"] == "idle"

    surface.deleteLater()


def test_toolbar_compact_stop_debug_buttons_follow_actions(qapp):
    window = FakeToolbarWindow()
    builder = ToolBarBuilder(window)
    toolbar = builder.build()
    toolbar.resize(360, 42)

    stop_button = builder._stop_btn
    debug_button = builder._debug_btn

    assert stop_button.text() == "Stop"
    assert stop_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon
    assert stop_button._label_font.bold()
    assert stop_button._label_font.pixelSize() == builder._run_btn._label_font.pixelSize()
    assert debug_button._label_font.bold()
    assert debug_button._label_font.pixelSize() == builder._run_btn._label_font.pixelSize()
    assert stop_button.iconSize().width() == builder._COMPACT_CONTROL_ICON_SIZE
    assert stop_button.size().height() == builder._run_btn.height()
    assert stop_button.size().height() == builder._COMPACT_CONTROL_HEIGHT
    assert stop_button.size().width() >= builder._STOP_CONTROL_WIDTH
    assert stop_button.displayed_text() == "Stop"
    assert stop_button.symbol_color().name().upper() == "#E51400"
    assert debug_button.text() == "Debug"
    assert debug_button.size().width() >= builder._DEBUG_CONTROL_WIDTH
    assert debug_button.displayed_text() == "Debug"
    assert debug_button.symbol_color().name().upper() == "#FF9800"

    window._settings.values["editor.theme"] = "default_high_contrast"
    builder.update_accent_color("#FFFFFF")
    assert stop_button.symbol_color().name().upper() == "#FFFFFF"
    assert debug_button.symbol_color().name().upper() == "#FFFFFF"
    window._settings.values["editor.theme"] = "default_dark"
    builder.update_accent_color("#4CAF50")
    assert debug_button.symbol_color().name().upper() == "#4CAF50"

    triggered = []
    window._debug_action.triggered.connect(lambda: triggered.append("debug"))
    debug_button.click()
    assert triggered == ["debug"]

    window._stop_action.setToolTip("Stop the running program (Ctrl+F5)")
    window._stop_action.setEnabled(False)
    window._debug_action.setEnabled(False)
    qapp.processEvents()

    assert stop_button.text() == "Stop"
    assert stop_button.displayed_text() == "Stop"
    assert stop_button.toolTip() == "Stop the running program (Ctrl+F5)"
    assert stop_button.isEnabled() is False
    assert debug_button.isEnabled() is False

    for button in (stop_button, debug_button):
        background, foreground, border = button._colors()
        assert background.name().upper() == "#555555"
        assert foreground.name().upper() == "#888888"
        assert border is None
        assert button.symbol_color().name().upper() == "#888888"

    assert toolbar.grab().isNull() is False

    window._stop_action.setEnabled(True)
    window._debug_action.setEnabled(True)
    qapp.processEvents()
    assert stop_button.symbol_color().name().upper() == "#E51400"
    assert debug_button.symbol_color().name().upper() == "#4CAF50"

    toolbar.deleteLater()
    window.deleteLater()


def test_run_file_button_labels_elide_and_follow_action_state(qapp):
    action = QAction("Run")
    action.setToolTip("Run current file (F5)")
    button = RunFileButton(action)

    assert button.text() == "Run File"
    assert button.accessibleName() == "Run File"
    assert button.toolTip() == "Run current file (F5)"

    target_name = "weekly_report_generation_script_with_long_filename.py"
    button.set_target_name(f"  {target_name}  ")
    full_label = f"Run {target_name}"
    displayed = button.displayed_text()

    assert button.text() == full_label
    assert button.accessibleName() == full_label
    assert displayed.startswith("Run ")
    assert displayed.endswith("...")
    assert len(displayed) < len(full_label)

    action.setToolTip("Continue debugging (F6)")
    action.setEnabled(False)
    qapp.processEvents()

    assert button.text() == "Continue"
    assert button.displayed_text() == "Continue"
    assert button.toolTip() == "Continue debugging (F6)"
    assert button.isEnabled() is False

    button.deleteLater()


def test_run_file_button_sanitizes_target_and_accent_color(qapp):
    action = QAction("Run")
    button = RunFileButton(action)
    original_accent = button._accent.name()

    button.set_target_name(None)
    assert button.text() == "Run File"

    button.set_target_name("   ")
    assert button.text() == "Run File"

    button.set_accent_color("not-a-color")
    assert button._accent.name() == original_accent

    button.set_accent_color("#ABCDEF")
    assert button._accent.name() == "#abcdef"

    assert button._elide_text("Long label", 1) == "..."

    button.deleteLater()


def test_toolbar_buttons_cover_theme_state_and_missing_action_edges(qapp):
    action = QAction("Run")
    run_button = RunFileButton(action)
    run_button.setDefaultAction(None)
    run_button._sync_from_action()

    class StatefulControl(CompactRunControlButton):
        hovered = False
        pressed = False
        focused = False

        def underMouse(self):
            return self.hovered

        def isDown(self):
            return self.pressed

        def hasFocus(self):
            return self.focused

    control_action = QAction("Stop")
    control = StatefulControl(control_action, "A very long control label", "stop", 40)
    control.setFixedWidth(50)
    assert control.displayed_text() != "A very long control label"
    control.event(QEvent(QEvent.Type.FontChange))

    control.apply_theme("default_high_contrast")
    control.focused = True
    background, foreground, border = control._colors()
    assert background.name() == "#000000"
    assert foreground.name() == "#ffffff"
    assert border is not None
    assert control.grab().isNull() is False

    control.focused = False
    control.apply_theme("default_light", "light")
    control.pressed = True
    pressed_background, _foreground, pressed_border = control._colors()
    assert pressed_background.name() == "#4e555c"
    assert pressed_border is not None
    control.pressed = False
    control.hovered = True
    hover_background, _foreground, hover_border = control._colors()
    assert hover_background.name() == "#687079"
    assert hover_border is not None

    control.setDefaultAction(None)
    control._sync_from_action()
    run_button.deleteLater()
    control.deleteLater()


def test_toolbar_builder_helpers_without_optional_controls(qapp):
    window = QWidget()
    window._settings = FakeSettings({"editor.theme": "default_dark"})
    window._tab_manager = SimpleNamespace(current_editor=lambda: None)
    builder = ToolBarBuilder(window)
    builder.update_accent_color("#abcdef")
    builder.update_run_file_label(SimpleNamespace(display_name="demo.py"))

    toolbar = QToolBar(window)
    calls = []
    builder._add(toolbar, "new", "New", lambda: calls.append("new"))
    plain_action = toolbar.actions()[0]
    assert plain_action.toolTip() == "New"
    window._settings = None
    assert builder._active_shortcut("file.save")

    tracked = QAction("Tracked", window)
    builder._tooltip_actions = [(tracked, "Save", "file.save")]
    builder.update_shortcut_tooltips()
    assert tracked.toolTip().startswith("Save")

    editor = SimpleNamespace(run=lambda: calls.append("run"))
    window._tab_manager = SimpleNamespace(current_editor=lambda: editor)
    builder._editor_call("run")
    builder._editor_call("missing")
    assert calls == ["run"]

    toolbar.deleteLater()
    window.deleteLater()


def test_menu_and_toolbar_save_actions_route_to_action_save(qapp):
    toolbar_window = FakeToolbarWindow()
    toolbar = ToolBarBuilder(toolbar_window).build()
    save_action = next(
        action for action in toolbar.actions()
        if action.toolTip() == "Save the current file (Ctrl+S)"
    )

    save_action.trigger()

    assert toolbar_window.actions_called == ["save"]

    menu_calls = []

    class FakeMenuWindow(QWidget):
        def __init__(self):
            super().__init__()
            self._recent_files = SimpleNamespace(get_files=lambda: [])

        def action_new_file(self):
            pass

        def action_open_file(self):
            pass

        def action_open_folder(self):
            pass

        def action_save(self):
            menu_calls.append("save")

        def action_save_as(self):
            pass

        def action_close_tab(self):
            pass

        def action_preferences(self):
            menu_calls.append("preferences")

    menu_window = FakeMenuWindow()
    menu_bar = QMenuBar(menu_window)
    MenuBarBuilder(menu_window)._build_file_menu(menu_bar)
    file_menu = menu_bar.actions()[0].menu()
    save_menu_action = next(
        action for action in file_menu.actions()
        if action.text() == "&Save"
    )
    preferences_menu_action = next(
        action for action in file_menu.actions()
        if action.text() == "&Preferences..."
    )

    assert save_menu_action.shortcut() == QKeySequence("Ctrl+S")
    assert preferences_menu_action.shortcut() == QKeySequence("Ctrl+,")
    save_menu_action.trigger()
    preferences_menu_action.trigger()
    assert menu_calls == ["save", "preferences"]

    toolbar.deleteLater()
    toolbar_window.deleteLater()
    menu_bar.deleteLater()
    menu_window.deleteLater()


def test_ai_menu_review_action_is_exposed_and_routes(qapp):
    calls = []

    class FakeAIWindow(QWidget):
        def __init__(self):
            super().__init__()
            self._ai_chat_panel = SimpleNamespace(
                toggleViewAction=lambda: QAction("AI Chat", self)
            )

        def action_ai_review_file(self):
            calls.append("review")

        def action_ollama_setup(self):
            calls.append("setup")

        def _update_ai_review_action_enabled(self):
            calls.append(("refresh", self._ai_review_file_action.text()))

    ai_window = FakeAIWindow()
    menu_bar = QMenuBar(ai_window)
    MenuBarBuilder(ai_window)._build_ai_menu(menu_bar)
    ai_menu = menu_bar.actions()[0].menu()
    review_action = next(
        action for action in ai_menu.actions()
        if action.text() == "&Review Current File"
    )

    assert ai_window._ai_review_file_action is review_action
    assert review_action.shortcut() == QKeySequence("Ctrl+Shift+R")
    assert calls == [("refresh", "&Review Current File")]

    review_action.trigger()

    assert calls == [("refresh", "&Review Current File"), "review"]

    menu_bar.deleteLater()
    ai_window.deleteLater()


def test_splash_and_loading_dots_render_and_update_status(qapp):
    dots = LoadingDotsWidget()
    dots._timer.stop()
    dots._active_index = 2
    dots._advance()

    dots_pixmap = dots.grab()
    assert dots._active_index == 0
    assert dots_pixmap.isNull() is False

    splash = MeadowPySplashScreen(QIcon(), "9.9.9")
    splash.set_status_text("Loading tests")
    splash.center_on_screen()
    splash_pixmap = splash.grab()

    assert splash._status_label.text() == "Loading tests"
    assert splash._version_label.text() == "v9.9.9"
    assert splash._icon_pixmap(None).isNull() is False
    assert splash_pixmap.isNull() is False

    dots.deleteLater()
    splash.deleteLater()


def test_file_explorer_icon_provider_badge_click_and_live_theme(qapp, tmp_path):
    py_file = tmp_path / "main.py"
    txt_file = tmp_path / "notes.txt"
    blocked_file = tmp_path / "review.docx"
    py_file.write_text("print('hi')\n", encoding="utf-8")
    txt_file.write_text("hello\n", encoding="utf-8")
    blocked_file.write_bytes(b"PK\x03\x04\x14\x00\x00\x00word/document.xml")

    provider = _ExplorerIconProvider("#22AA44", is_dark=True)
    folder_icon = provider.icon(QFileInfo(str(tmp_path)))
    python_icon = provider.icon(QFileInfo(str(py_file)))
    generic_icon = provider.icon(QFileInfo(str(txt_file)))
    blocked_icon = provider.icon(QFileInfo(str(blocked_file)))
    typed_folder_icon = provider.icon(QFileIconProvider.IconType.Folder)

    assert folder_icon.isNull() is False
    assert python_icon.isNull() is False
    assert generic_icon.isNull() is False
    assert blocked_icon.isNull() is False
    assert typed_folder_icon.isNull() is False
    assert python_icon.cacheKey() != generic_icon.cacheKey()
    assert blocked_icon.cacheKey() != generic_icon.cacheKey()

    provider.rebuild("#3366DD", is_dark=False)
    assert provider.icon(QFileInfo(str(py_file))).isNull() is False

    panel = FileExplorerPanel()
    changed_folder = Recorder()
    panel.change_folder_requested.connect(changed_folder)
    panel.apply_icon_theme("#3366DD", is_dark=False)
    panel.set_root_folder(str(tmp_path))
    panel.apply_icon_theme("#AA4499", is_dark=True)

    assert "#AA4499" in panel._project_badge.styleSheet()
    assert panel._project_badge.text() == tmp_path.name.upper()

    click = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(panel._project_badge.rect().center()),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    panel._project_badge.mouseReleaseEvent(click)
    assert changed_folder.calls == [()]

    label = _ClickableLabel("Open")
    label.resize(80, 24)
    clicked = Recorder()
    label.clicked.connect(clicked)
    label_click = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(label.rect().center()),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    label.mouseReleaseEvent(label_click)
    assert clicked.calls == [()]

    panel.deleteLater()
    label.deleteLater()


class FakeModelIndex:
    def __init__(self, valid=True, key="root"):
        self._valid = valid
        self.key = key

    def isValid(self):
        return self._valid


class FakeExplorerModel:
    def __init__(self, paths, dirs):
        self.paths = paths
        self.dirs = set(dirs)
        self.fetched = []

    def rowCount(self, parent):
        return 2 if parent.key in {"dir", "loaded-dir"} else 0

    def index(self, *args):
        if len(args) == 1:
            return FakeModelIndex(True, "loaded-dir")
        row, _column, parent = args
        return FakeModelIndex(True, f"{parent.key}-child-{row}")

    def isDir(self, index):
        return index.key in self.dirs

    def canFetchMore(self, index):
        return self.isDir(index)

    def fetchMore(self, index):
        self.fetched.append(index.key)

    def hasChildren(self, index):
        return self.isDir(index)

    def filePath(self, index):
        return self.paths.get(index.key, index.key)


class FakeLargeExplorerModel(FakeExplorerModel):
    def rowCount(self, parent):
        return _MAX_PREFETCH_SUBDIRS + 5 if parent.key == "big" else 0

    def index(self, row, _column, parent):
        return FakeModelIndex(True, f"{parent.key}-child-{row}")


class FakeEmptyExplorerModel(FakeExplorerModel):
    def rowCount(self, parent):
        return 0

    def canFetchMore(self, index):
        return index.key == "dir" and index.key not in self.fetched

    def hasChildren(self, index):
        return self.isDir(index) and self.canFetchMore(index)


class FakeRootPrefetchModel(FakeExplorerModel):
    def rowCount(self, parent):
        return 2 if parent.key == "loaded-dir" else 0

    def canFetchMore(self, index):
        return index.key.startswith("loaded-dir-child-")


class FakeFilteredProxy(_FilteredFileSystemModel):
    def __init__(self, source_model, row_counts):
        super().__init__()
        self._source_model = source_model
        self._row_counts = row_counts

    def sourceModel(self):
        return self._source_model

    def mapToSource(self, proxy_index):
        return proxy_index

    def rowCount(self, parent=FakeModelIndex(False, "root")):
        return self._row_counts.get(parent.key, 0)


class FakeHasChildrenSource:
    def __init__(self, dirs, fetchable, paths=None):
        self.dirs = set(dirs)
        self.fetchable = set(fetchable)
        self.paths = paths or {}

    def isDir(self, index):
        return index.key in self.dirs

    def canFetchMore(self, index):
        return index.key in self.fetchable

    def filePath(self, index):
        return self.paths.get(index.key, index.key)


class FakeExplorerProxy:
    def __init__(self, source_index):
        self.source_index = source_index

    def mapToSource(self, proxy_index):
        if proxy_index.key.startswith("proxy-file"):
            return FakeModelIndex(True, "file")
        if proxy_index.key.startswith("proxy-dir"):
            return FakeModelIndex(True, "dir")
        return self.source_index

    def mapFromSource(self, source_index):
        return FakeModelIndex(source_index.isValid(), f"proxy-{source_index.key}")


class FakeExplorerTree:
    def __init__(self):
        self.expanded = []
        self.collapsed = []
        self.expanded_state = False

    def currentIndex(self):
        return FakeModelIndex(True, "proxy")

    def isExpanded(self, index):
        return self.expanded_state

    def expand(self, index):
        self.expanded.append(index.key)
        self.expanded_state = True

    def collapse(self, index):
        self.collapsed.append(index.key)
        self.expanded_state = False

    def rootIndex(self):
        return FakeModelIndex(False, "root")

    def viewport(self):
        return SimpleNamespace(update=lambda: None)


def test_file_explorer_animation_keyboard_navigation_and_cancel_branches(
    monkeypatch,
    qapp,
    tmp_path,
):
    from meadowpy.ui import file_explorer as file_explorer_module

    panel = FileExplorerPanel()
    selected = Recorder()
    panel.file_selected.connect(selected)
    panel._root_path = str(tmp_path)
    (tmp_path / "visible_child.py").write_text("print('hi')\n", encoding="utf-8")

    folder_index = FakeModelIndex(True, "dir")
    model = FakeExplorerModel(
        paths={
            "dir": str(tmp_path),
            "file": str(tmp_path / "demo.py"),
            "loaded-dir": str(tmp_path),
        },
        dirs={"dir", "dir-child-0", "dir-child-1", "loaded-dir"},
    )
    proxy = FakeExplorerProxy(folder_index)
    tree = FakeExplorerTree()
    panel._fs_model = model
    panel._proxy = proxy
    panel._tree = tree

    panel._prefetch_subdirs(folder_index)
    assert model.fetched == ["dir-child-0", "dir-child-1"]

    panel._on_item_expanded(FakeModelIndex(True, "proxy-dir"))
    assert str(tmp_path) in panel._pending_anim_paths
    assert tree.collapsed[-1] == "proxy-dir"
    assert "dir" in model.fetched

    monkeypatch.setattr(
        file_explorer_module,
        "QTimer",
        SimpleNamespace(singleShot=lambda _ms, callback: callback()),
    )
    panel._on_directory_loaded(str(tmp_path))
    assert str(tmp_path) not in panel._pending_anim_paths
    assert tree.expanded[-1] == "proxy-loaded-dir"
    assert model.fetched == ["dir-child-0", "dir-child-1", "dir"]

    panel._on_directory_loaded(str(tmp_path))
    assert model.fetched == ["dir-child-0", "dir-child-1", "dir"]

    empty_model = FakeEmptyExplorerModel(
        paths={
            "dir": str(tmp_path / "empty"),
            "loaded-dir": str(tmp_path / "empty"),
        },
        dirs={"dir", "loaded-dir"},
    )
    (tmp_path / "empty").mkdir()
    panel._fs_model = empty_model
    panel._proxy = FakeExplorerProxy(FakeModelIndex(True, "dir"))
    empty_tree = FakeExplorerTree()
    panel._tree = empty_tree

    panel._on_item_expanded(FakeModelIndex(True, "proxy-dir"))
    assert str(tmp_path / "empty") in panel._pending_anim_paths
    assert empty_tree.collapsed[-1] == "proxy-dir"
    panel._on_directory_loaded(str(tmp_path / "empty"))
    assert str(tmp_path / "empty") not in panel._pending_anim_paths
    assert empty_tree.expanded == []
    assert panel._is_known_empty_folder(FakeModelIndex(True, "proxy-dir")) is True

    root_model = FakeRootPrefetchModel(
        paths={"loaded-dir": str(tmp_path)},
        dirs={"loaded-dir-child-0", "loaded-dir-child-1"},
    )
    panel._fs_model = root_model
    panel._proxy = FakeExplorerProxy(FakeModelIndex(True, "loaded-dir"))
    panel._root_path = str(tmp_path)
    panel._on_directory_loaded(str(tmp_path))
    assert root_model.fetched == ["loaded-dir-child-0", "loaded-dir-child-1"]

    large_model = FakeLargeExplorerModel(paths={}, dirs={
        f"big-child-{row}" for row in range(_MAX_PREFETCH_SUBDIRS + 5)
    })
    panel._fs_model = large_model
    panel._prefetch_subdirs(FakeModelIndex(True, "big"))
    assert len(large_model.fetched) == _MAX_PREFETCH_SUBDIRS
    assert large_model.fetched[-1] == f"big-child-{_MAX_PREFETCH_SUBDIRS - 1}"
    panel._fs_model = model
    panel._proxy = proxy
    panel._tree = tree
    assert panel._is_known_empty_folder(FakeModelIndex(True, "proxy-dir")) is False

    enter = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Return,
        Qt.KeyboardModifier.NoModifier,
    )
    tree.expanded_state = False
    assert panel.eventFilter(tree, enter) is True
    assert tree.expanded[-1] == "proxy"

    tree.expanded_state = True
    assert panel.eventFilter(tree, enter) is True
    assert tree.collapsed[-1] == "proxy"

    file_model = FakeExplorerModel(
        paths={"file": str(tmp_path / "demo.py")},
        dirs=set(),
    )
    panel._fs_model = file_model
    panel._proxy = FakeExplorerProxy(FakeModelIndex(True, "file"))
    tree.expanded_state = False
    assert panel.eventFilter(tree, enter) is True
    assert selected.calls == [(str(tmp_path / "demo.py"),)]

    panel._on_double_clicked(FakeModelIndex(True, "proxy-file"))
    assert selected.calls[-1] == (str(tmp_path / "demo.py"),)

    previous_selected = list(selected.calls)
    blocked_file = tmp_path / "review.docx"
    blocked_file.write_bytes(b"PK\x03\x04\x14\x00\x00\x00word/document.xml")
    blocked_model = FakeExplorerModel(
        paths={"file": str(blocked_file)},
        dirs=set(),
    )
    panel._fs_model = blocked_model
    assert panel._is_blocked_editor_file(FakeModelIndex(True, "proxy-file")) is True
    assert panel.eventFilter(tree, enter) is True
    panel._on_double_clicked(FakeModelIndex(True, "proxy-file"))
    assert selected.calls == previous_selected

    text_file = tmp_path / "notes.txt"
    text_file.write_text("plain notes\n", encoding="utf-8")
    text_model = FakeExplorerModel(
        paths={"file": str(text_file)},
        dirs=set(),
    )
    panel._fs_model = text_model
    assert panel._is_blocked_editor_file(FakeModelIndex(True, "proxy-file")) is False
    assert panel.eventFilter(tree, enter) is True
    assert selected.calls[-1] == (str(text_file),)

    invalid_dir, invalid_source = panel._resolve_target_dir(FakeModelIndex(False, "bad"))
    assert invalid_dir == tmp_path
    assert invalid_source is None

    monkeypatch.setattr(
        file_explorer_module.QInputDialog,
        "getText",
        lambda *args, **kwargs: ("", False),
    )
    panel._action_new_file(tmp_path)
    panel._action_new_folder(tmp_path)

    existing = tmp_path / "existing.py"
    existing.write_text("x = 1\n", encoding="utf-8")
    panel._fs_model = SimpleNamespace(filePath=lambda index: str(existing))
    panel._action_rename(object())

    monkeypatch.setattr(
        file_explorer_module.QMessageBox,
        "question",
        lambda *args, **kwargs: file_explorer_module.QMessageBox.StandardButton.No,
    )
    panel._action_delete(object())
    assert existing.exists()

    panel.deleteLater()


def test_file_explorer_proxy_hides_expander_for_known_empty_dirs(qapp, tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    full_dir = tmp_path / "full"
    full_dir.mkdir()
    (full_dir / "demo.py").write_text("print('hi')\n", encoding="utf-8")
    hidden_only_dir = tmp_path / "hidden_only"
    hidden_only_dir.mkdir()
    (hidden_only_dir / "__pycache__").mkdir()
    blocked_file = tmp_path / "review.docx"
    blocked_file.write_bytes(b"PK\x03\x04\x14\x00\x00\x00word/document.xml")

    source = FakeHasChildrenSource(
        dirs={"lazy", "empty", "full", "hidden_only"},
        fetchable={"lazy", "empty", "hidden_only"},
        paths={
            "lazy": str(full_dir),
            "empty": str(empty_dir),
            "full": str(full_dir),
            "hidden_only": str(hidden_only_dir),
            "blocked": str(blocked_file),
        },
    )
    proxy = FakeFilteredProxy(source, {
        "empty": 0,
        "full": 2,
        "hidden_only": 0,
    })

    assert proxy.hasChildren(FakeModelIndex(True, "lazy")) is True
    assert proxy.hasChildren(FakeModelIndex(True, "full")) is True
    assert proxy.hasChildren(FakeModelIndex(True, "empty")) is False
    assert proxy.canFetchMore(FakeModelIndex(True, "empty")) is False
    assert proxy.hasChildren(FakeModelIndex(True, "hidden_only")) is False
    assert proxy.canFetchMore(FakeModelIndex(True, "hidden_only")) is False
    assert (
        proxy.data(FakeModelIndex(True, "blocked"), Qt.ItemDataRole.ToolTipRole)
        == _BLOCKED_FILE_TOOLTIP
    )

    proxy.deleteLater()


def test_file_explorer_click_and_delegate_noop_visual_branches(qapp):
    label = _ClickableLabel("Open")
    label.resize(80, 24)
    clicked = Recorder()
    label.clicked.connect(clicked)

    for button, position in (
        (Qt.MouseButton.RightButton, QPointF(label.rect().center())),
        (Qt.MouseButton.LeftButton, QPointF(-1, -1)),
    ):
        event = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            position,
            button,
            button,
            Qt.KeyboardModifier.NoModifier,
        )
        label.mouseReleaseEvent(event)
    assert clicked.calls == []

    class Panel:
        blocked = True
        empty = False

        def _is_blocked_editor_file(self, index):
            return self.blocked

        def _blocked_file_text_color(self):
            return "#123456"

        def _blocked_file_icon(self):
            return QIcon()

        def _is_known_empty_folder(self, index):
            return self.empty

        def _empty_folder_text_color(self):
            return "#654321"

        def _empty_folder_icon(self):
            return QIcon()

    panel = Panel()
    delegate = _FileExplorerItemDelegate(panel)
    delegate.initStyleOption(QStyleOptionViewItem(), QModelIndex())
    panel.blocked = False
    delegate.initStyleOption(QStyleOptionViewItem(), QModelIndex())
    panel.empty = True
    delegate.initStyleOption(QStyleOptionViewItem(), QModelIndex())

    delegate.deleteLater()
    label.deleteLater()


def test_file_explorer_model_and_panel_helper_boundaries(monkeypatch, qapp, tmp_path):
    raw_proxy = _FilteredFileSystemModel()
    assert raw_proxy._is_known_unsupported_file(QModelIndex()) is False
    assert raw_proxy.canFetchMore(QModelIndex()) is False
    assert raw_proxy.hasChildren(QModelIndex()) is False
    assert raw_proxy.data(QModelIndex(), Qt.ItemDataRole.DisplayRole) is None

    panel = FileExplorerPanel()
    invalid = FakeModelIndex(False, "invalid")
    assert panel._is_known_empty_folder(invalid) is False
    assert panel._is_blocked_editor_file(invalid) is False
    assert panel._select_file_if_openable(invalid) is False

    class Model:
        def __init__(self):
            self.fetchable = {"unknown-fetch"}
            self.counts = {"unknown-many": 2}

        def isDir(self, index):
            return index.key.startswith(("empty", "full", "unknown", "folder"))

        def filePath(self, index):
            return {
                "empty": str(tmp_path / "empty"),
                "full": str(tmp_path / "full"),
                "blocked": str(tmp_path / "review.docx"),
                "file": str(tmp_path / "demo.py"),
                "folder": str(tmp_path),
            }.get(index.key, index.key)

        def canFetchMore(self, index):
            return index.key in self.fetchable

        def rowCount(self, index):
            return self.counts.get(index.key, 0)

        def index(self, path):
            return FakeModelIndex(True, "loaded")

    class Proxy:
        def mapToSource(self, index):
            if index.key == "bad-source":
                return FakeModelIndex(False, "bad")
            return FakeModelIndex(True, index.key.removeprefix("proxy-"))

        def mapFromSource(self, index):
            return FakeModelIndex(index.key != "loaded-invalid", f"proxy-{index.key}")

        def rowCount(self, index):
            if index.key == "proxy-error":
                raise RuntimeError("stale")
            return 3

    model = Model()
    proxy = Proxy()
    panel._fs_model = model
    panel._proxy = proxy
    monkeypatch.setattr(
        file_explorer_module,
        "_directory_has_visible_entries",
        lambda path: False if Path(path).name == "empty" else (
            True if Path(path).name == "full" else None
        ),
    )
    monkeypatch.setattr(
        file_explorer_module,
        "is_known_unsupported_editor_file",
        lambda path: str(path).endswith(".docx"),
    )

    assert panel._is_known_empty_folder(FakeModelIndex(True, "bad-source")) is False
    assert panel._is_known_empty_folder(FakeModelIndex(True, "proxy-file")) is False
    assert panel._is_known_empty_folder(FakeModelIndex(True, "proxy-empty")) is True
    assert panel._is_known_empty_folder(FakeModelIndex(True, "proxy-full")) is False
    assert panel._is_known_empty_folder(
        FakeModelIndex(True, "proxy-unknown-fetch")
    ) is False
    assert panel._is_known_empty_folder(
        FakeModelIndex(True, "proxy-unknown-empty")
    ) is False
    model.counts["unknown-empty"] = 0
    proxy.rowCount = lambda index: 0
    assert panel._is_known_empty_folder(
        FakeModelIndex(True, "proxy-unknown-empty")
    ) is True

    assert panel._is_blocked_editor_file(FakeModelIndex(True, "bad-source")) is False
    assert panel._is_blocked_editor_file(FakeModelIndex(True, "proxy-folder")) is False
    assert panel._is_blocked_editor_file(FakeModelIndex(True, "proxy-blocked")) is True
    assert panel._select_file_if_openable(FakeModelIndex(True, "bad-source")) is False
    assert panel._select_file_if_openable(FakeModelIndex(True, "proxy-folder")) is False
    assert panel._select_file_if_openable(FakeModelIndex(True, "proxy-blocked")) is False
    selected = Recorder()
    panel.file_selected.connect(selected)
    assert panel._select_file_if_openable(FakeModelIndex(True, "proxy-file")) is True
    assert selected.calls == [(str(tmp_path / "demo.py"),)]

    panel._icon_provider = _ExplorerIconProvider("#123456", True)
    assert panel._empty_folder_icon().isNull() is False
    assert panel._empty_folder_text_color()
    assert panel._blocked_file_icon().isNull() is False
    assert panel._blocked_file_text_color()
    assert panel._visible_child_count(invalid, FakeModelIndex(True, "unknown-many")) == 2

    raw_proxy.deleteLater()
    panel.deleteLater()


def test_file_explorer_refresh_animation_and_resolution_edges(
    monkeypatch,
    qapp,
    tmp_path,
):
    panel = FileExplorerPanel()
    calls = []
    invalid = FakeModelIndex(False, "invalid")

    FileExplorerPanel._refresh_title_icons(
        SimpleNamespace(_title_icon_color="#123456")
    )
    panel._root_path = str(tmp_path)
    monkeypatch.setattr(
        panel,
        "_action_new_file",
        lambda path: calls.append(("new", path)),
    )
    panel._on_title_new_file()
    assert calls == [("new", tmp_path)]

    class MinimalTree:
        def collapse(self, index):
            calls.append(("collapse", index.key))

        def viewport(self):
            return SimpleNamespace(update=lambda: calls.append(("update",)))

    panel._tree = MinimalTree()
    panel._collapse_without_animation(FakeModelIndex(True, "plain"))
    assert panel._suppress_expand_handler is False

    panel._suppress_expand_handler = True
    panel._on_item_expanded(FakeModelIndex(True, "ignored"))
    panel._suppress_expand_handler = False
    panel._fs_model = None
    panel._on_item_expanded(FakeModelIndex(True, "ignored"))

    class Model:
        def __init__(self):
            self.fetch = False
            self.deleted = False

        def canFetchMore(self, index):
            return self.fetch

        def filePath(self, index):
            return str(tmp_path if index.key == "folder" else tmp_path / "demo.py")

        def isDir(self, index):
            return index.key == "folder"

        def rowCount(self, index):
            return 0

        def index(self, path):
            return FakeModelIndex(True, "loaded-invalid")

        def deleteLater(self):
            self.deleted = True

        def setIconProvider(self, provider):
            self.provider = provider

    class Proxy:
        def __init__(self):
            self.deleted = False

        def mapToSource(self, index):
            return FakeModelIndex(True, index.key.removeprefix("proxy-"))

        def mapFromSource(self, index):
            return FakeModelIndex(False, "invalid")

        def rowCount(self, index):
            return 0

        def deleteLater(self):
            self.deleted = True

    model = Model()
    proxy = Proxy()
    panel._fs_model = model
    panel._proxy = proxy
    monkeypatch.setattr(
        panel,
        "_collapse_without_animation",
        lambda index: calls.append(("empty-collapse", index.key)),
    )
    monkeypatch.setattr(
        panel,
        "_prefetch_subdirs",
        lambda index: calls.append(("prefetch", index.key)),
    )
    panel._on_item_expanded(FakeModelIndex(True, "proxy-folder"))
    assert ("empty-collapse", "proxy-folder") in calls

    panel._pending_anim_paths = {"pending"}
    panel._root_path = str(tmp_path)
    panel._on_directory_loaded("pending")
    panel._on_directory_loaded(str(tmp_path))
    assert ("prefetch", "loaded-invalid") in calls

    invalid_dir, invalid_source = panel._resolve_target_dir(invalid)
    assert invalid_dir == tmp_path
    assert invalid_source is None
    folder_dir, _ = panel._resolve_target_dir(FakeModelIndex(True, "proxy-folder"))
    file_dir, _ = panel._resolve_target_dir(FakeModelIndex(True, "proxy-file"))
    assert folder_dir == tmp_path
    assert file_dir == tmp_path

    panel._tree = SimpleNamespace(
        viewport=lambda: SimpleNamespace(update=lambda: calls.append(("theme-update",))),
        rootIndex=lambda: FakeModelIndex(True, "root"),
    )
    panel.apply_icon_theme("#abcdef", False)
    assert ("theme-update",) in calls

    monkeypatch.setattr(
        panel,
        "set_root_folder",
        lambda path: calls.append(("reset", path)),
    )
    panel.refresh()
    assert model.deleted is True
    assert proxy.deleted is True
    assert ("reset", str(tmp_path)) in calls

    panel.deleteLater()

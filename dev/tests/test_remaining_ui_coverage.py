from __future__ import annotations

from types import SimpleNamespace

from PyQt6.QtCore import QEvent, QFileInfo, QPointF, Qt
from PyQt6.QtGui import QAction, QColor, QIcon, QKeyEvent, QKeySequence, QMouseEvent
from PyQt6.QtWidgets import QFileIconProvider, QMenuBar, QWidget

from meadowpy.ui.file_explorer import (
    FileExplorerPanel,
    _ClickableLabel,
    _ExplorerIconProvider,
    _MAX_PREFETCH_SUBDIRS,
)
from meadowpy.ui.menu_bar import MenuBarBuilder
from meadowpy.ui.splash_screen import LoadingDotsWidget, MeadowPySplashScreen
from meadowpy.ui.tool_bar import ToolBarBuilder


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


def test_toolbar_glow_painter_renders_hover_and_disabled_states(qapp):
    window = FakeToolbarWindow()
    builder = ToolBarBuilder(window)
    toolbar = builder.build()
    toolbar.resize(360, 42)

    stop_button = toolbar.widgetForAction(window._stop_action)
    builder._glow.set_button_color(stop_button, QColor("#ABCDEF"))

    assert builder._glow.eventFilter(stop_button, QEvent(QEvent.Type.HoverEnter)) is False
    assert toolbar.grab().isNull() is False

    window._stop_action.setEnabled(False)
    assert builder._glow.eventFilter(toolbar, QEvent(QEvent.Type.Paint)) is True
    stop_entry = next(entry for entry in builder._glow._entries if entry["btn"] is stop_button)
    assert stop_entry["state"] == "idle"

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
            pass

    menu_window = FakeMenuWindow()
    menu_bar = QMenuBar(menu_window)
    MenuBarBuilder(menu_window)._build_file_menu(menu_bar)
    file_menu = menu_bar.actions()[0].menu()
    save_menu_action = next(
        action for action in file_menu.actions()
        if action.text() == "&Save"
    )

    assert save_menu_action.shortcut() == QKeySequence("Ctrl+S")
    save_menu_action.trigger()
    assert menu_calls == ["save"]

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
    py_file.write_text("print('hi')\n", encoding="utf-8")
    txt_file.write_text("hello\n", encoding="utf-8")

    provider = _ExplorerIconProvider("#22AA44", is_dark=True)
    folder_icon = provider.icon(QFileInfo(str(tmp_path)))
    python_icon = provider.icon(QFileInfo(str(py_file)))
    generic_icon = provider.icon(QFileInfo(str(txt_file)))
    typed_folder_icon = provider.icon(QFileIconProvider.IconType.Folder)

    assert folder_icon.isNull() is False
    assert python_icon.isNull() is False
    assert generic_icon.isNull() is False
    assert typed_folder_icon.isNull() is False
    assert python_icon.cacheKey() != generic_icon.cacheKey()

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

    large_model = FakeLargeExplorerModel(paths={}, dirs={
        f"big-child-{row}" for row in range(_MAX_PREFETCH_SUBDIRS + 5)
    })
    panel._fs_model = large_model
    panel._prefetch_subdirs(FakeModelIndex(True, "big"))
    assert len(large_model.fetched) == _MAX_PREFETCH_SUBDIRS
    assert large_model.fetched[-1] == f"big-child-{_MAX_PREFETCH_SUBDIRS - 1}"
    panel._fs_model = model

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

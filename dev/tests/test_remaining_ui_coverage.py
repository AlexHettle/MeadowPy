from __future__ import annotations

from types import SimpleNamespace

from PyQt6.QtCore import QEvent, QFileInfo, QPointF, Qt
from PyQt6.QtGui import QAction, QColor, QIcon, QKeyEvent, QKeySequence, QMouseEvent
from PyQt6.QtWidgets import (
    QFileIconProvider,
    QMenuBar,
    QPushButton,
    QWidget,
)

from meadowpy.ui.file_explorer import (
    _BLOCKED_FILE_TOOLTIP,
    FileExplorerPanel,
    _ClickableLabel,
    _ExplorerIconProvider,
    _FilteredFileSystemModel,
    _MAX_PREFETCH_SUBDIRS,
)
from meadowpy.ui.glow_painter import HeaderGlowPainter
from meadowpy.ui.menu_bar import MenuBarBuilder
from meadowpy.ui.splash_screen import LoadingDotsWidget, MeadowPySplashScreen
from meadowpy.ui.tool_bar import RunFileButton, ToolBarBuilder


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
    assert debug_button.symbol_color().name().upper() == "#FF9800"

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

from __future__ import annotations

import ctypes
from types import SimpleNamespace

import meadowpy.app as app_module
from PyQt6.QtCore import QEvent, Qt, QtMsgType
from PyQt6.QtGui import QKeyEvent, QRegion
from PyQt6.QtWidgets import QLineEdit, QMenu, QMenuBar

from meadowpy.app import (
    MeadowPyApp,
    _ClipboardShortcutFilter,
    _MenuRoundedMaskFilter,
    _install_qt_message_logger,
    _is_menubar_menu,
)
from meadowpy.constants import APP_NAME, VERSION


class FakeQApplication:
    def __init__(self, argv):
        self.argv = argv
        self.events_processed = 0
        self.event_filters = []
        self.stylesheets = []
        self.removed_filters = []
        self.sent_deferred_delete = False
        self.exec_called = False

    def setApplicationName(self, name):
        self.application_name = name

    def setOrganizationName(self, name):
        self.organization_name = name

    def setApplicationVersion(self, version):
        self.application_version = version

    def setStyleSheet(self, stylesheet):
        self.stylesheets.append(stylesheet)

    def installEventFilter(self, event_filter):
        self.event_filters.append(event_filter)

    def removeEventFilter(self, event_filter):
        self.removed_filters.append(event_filter)

    def processEvents(self):
        self.events_processed += 1

    def sendPostedEvents(self, obj, event_type):
        self.sent_deferred_delete = True

    def exec(self):
        self.exec_called = True
        return 7


class FakeSettings:
    def __init__(self):
        self.loaded = False
        self.values = {
            "editor.theme": "custom",
            "editor.custom_theme.base": "light",
            "editor.custom_theme.accent": "#246810",
        }

    def load(self):
        self.loaded = True

    def get(self, key, default=None):
        return self.values.get(key, default)


class FakeRecentFiles:
    def __init__(self, settings):
        self.settings = settings


class FakeFileManager:
    def __init__(self, settings, recent_files):
        self.settings = settings
        self.recent_files = recent_files
        self.reads = []

    def read_file(self, path):
        self.reads.append(path)
        return f"contents from {path}"


class FakeSplash:
    def __init__(self, icon, version):
        self.icon = icon
        self.version = version
        self.statuses = []
        self.centered = False
        self.shown = False
        self.closed = False
        self.deleted = False

    def set_status_text(self, message):
        self.statuses.append(message)

    def center_on_screen(self):
        self.centered = True

    def show(self):
        self.shown = True

    def close(self):
        self.closed = True

    def deleteLater(self):
        self.deleted = True


class FakeWidget:
    def __init__(self, name):
        self._name = name
        self.fonts = []

    def objectName(self):
        return self._name

    def setFont(self, font):
        self.fonts.append(font)


class FakeWindow:
    instances = []

    def __init__(self, settings, file_manager, recent_files, app_icon=None):
        self.settings = settings
        self.file_manager = file_manager
        self.recent_files = recent_files
        self.app_icon = app_icon
        self.opened = []
        self.visible = False
        self.raised = False
        self.activated = False
        self.closed = False
        self.deleted = False
        self.children = [
            FakeWidget("editor"),
            FakeWidget("codeEditor"),
            FakeWidget("outputText"),
        ]
        FakeWindow.instances.append(self)

    def findChildren(self, widget_type):
        return self.children

    def open_file_in_tab(self, path, content, *, large_file_mode=False):
        self.opened.append((path, content))

    def show(self):
        self.visible = True

    def raise_(self):
        self.raised = True

    def activateWindow(self):
        self.activated = True

    def isVisible(self):
        return self.visible

    def close(self):
        self.closed = True
        self.visible = False

    def deleteLater(self):
        self.deleted = True


class FakeEventFilter:
    def __init__(self, *args):
        self.args = args
        self.parent = args[-1] if args else None


class _CallableWinApi:
    def __init__(self, result=None, callback=None):
        self.result = result
        self.callback = callback
        self.argtypes = None
        self.restype = None
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        if self.callback is not None:
            return self.callback(*args)
        return self.result


def test_app_startup_applies_settings_opens_cli_files_and_tears_down(
    monkeypatch, tmp_path
):
    opened_file = tmp_path / "open_me.py"
    opened_file.write_text("print('hello')", encoding="utf-8")
    missing_file = tmp_path / "missing.py"
    settings = FakeSettings()
    stylesheet_calls = []
    sweep_calls = []

    monkeypatch.setattr(app_module, "QApplication", FakeQApplication)
    monkeypatch.setattr(app_module, "_install_qt_message_logger", lambda: "handler")
    monkeypatch.setattr(app_module, "Settings", lambda: settings)
    monkeypatch.setattr(app_module, "RecentFilesManager", FakeRecentFiles)
    monkeypatch.setattr(app_module, "FileManager", FakeFileManager)
    monkeypatch.setattr(app_module, "MainWindow", FakeWindow)
    monkeypatch.setattr(
        app_module,
        "sweep_selection_temp_files",
        lambda: sweep_calls.append(True),
    )
    monkeypatch.setattr(app_module, "MeadowPySplashScreen", FakeSplash)
    monkeypatch.setattr(app_module, "_MenuRoundedMaskFilter", FakeEventFilter)
    monkeypatch.setattr(app_module, "_ClipboardShortcutFilter", FakeEventFilter)
    monkeypatch.setattr(app_module, "remaining_delay_ms", lambda start, minimum: 0)

    def fake_get_stylesheet(theme_name, custom_base=None, custom_accent=None):
        stylesheet_calls.append((theme_name, custom_base, custom_accent))
        return "/* qss */"

    monkeypatch.setattr(app_module, "get_stylesheet", fake_get_stylesheet)

    def fake_load_font(self):
        self._app_font = "app-font"

    def fake_set_icon(self):
        self._app_icon = "app-icon"

    monkeypatch.setattr(MeadowPyApp, "_load_app_font", fake_load_font)
    monkeypatch.setattr(MeadowPyApp, "_set_app_icon", fake_set_icon)

    app = MeadowPyApp(["meadowpy", str(opened_file), str(missing_file)])

    assert app._qapp.application_name == APP_NAME
    assert app._qapp.organization_name == APP_NAME
    assert app._qapp.application_version == VERSION
    assert settings.loaded is True
    assert sweep_calls == [True]
    assert stylesheet_calls == [("custom", "light", "#246810")]
    assert app._qapp.stylesheets == ["/* qss */"]
    assert len(app._qapp.event_filters) == 2

    window = FakeWindow.instances[-1]
    assert window.opened == [
        (str(opened_file), f"contents from {opened_file}")
    ]
    assert window.children[0].fonts == ["app-font"]
    assert window.children[1].fonts == []
    assert window.children[2].fonts == []

    exit_code = app.run()

    assert exit_code == 7
    assert app._qapp.exec_called is True
    assert window.raised is True
    assert window.activated is True
    assert window.closed is True
    assert window.deleted is True
    assert app._qapp.sent_deferred_delete is True
    assert set(app._qapp.removed_filters) == set(app._qapp.event_filters)


def test_qt_message_logger_writes_location_and_warning_to_stderr(monkeypatch, tmp_path, capsys):
    installed = []
    monkeypatch.setattr(app_module.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        app_module,
        "qInstallMessageHandler",
        lambda handler: installed.append(handler),
    )

    handler = _install_qt_message_logger()
    context = type("Context", (), {"file": "demo.cpp", "line": 12})()

    handler(QtMsgType.QtInfoMsg, context, "plain info")
    handler(QtMsgType.QtWarningMsg, context, "careful")

    log_text = (tmp_path / ".meadowpy" / "meadowpy.log").read_text(encoding="utf-8")
    assert "[qt:QtInfoMsg] (demo.cpp:12) plain info" in log_text
    assert "[qt:QtWarningMsg] (demo.cpp:12) careful" in log_text
    assert "careful" in capsys.readouterr().err
    assert installed == [handler]


def test_menu_filter_prepares_menubar_and_floating_popups(qapp):
    menubar = QMenuBar()
    menu = QMenu("File", menubar)
    menu.resize(180, 80)
    menubar.addMenu(menu)
    floating = QMenu("Context")
    floating.resize(180, 80)
    event = QEvent(QEvent.Type.Show)
    event_filter = _MenuRoundedMaskFilter()

    assert _is_menubar_menu(menu) is True
    assert _is_menubar_menu(floating) is False

    assert event_filter.eventFilter(menu, event) is False
    assert event_filter.eventFilter(floating, event) is False
    assert menu.property("menubarMenu") is True
    assert floating.property("menubarMenu") is False
    assert menu.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert floating.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert menu.testAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    assert floating.testAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    assert menu.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    assert floating.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    assert bool(menu.windowFlags() & Qt.WindowType.NoDropShadowWindowHint)
    assert bool(floating.windowFlags() & Qt.WindowType.NoDropShadowWindowHint)
    assert not menu.autoFillBackground()
    assert not floating.autoFillBackground()
    assert menu.mask().isEmpty()
    assert floating.mask().isEmpty()

    menu.deleteLater()
    floating.deleteLater()
    menubar.deleteLater()


def test_menu_filter_clears_hard_masks_so_qss_controls_popup_surface(qapp):
    floating = QMenu("Context")
    floating.resize(100, 60)
    floating.setMask(QRegion(floating.rect()))
    event_filter = _MenuRoundedMaskFilter()

    assert not floating.mask().isEmpty()

    assert event_filter.eventFilter(floating, QEvent(QEvent.Type.Show)) is False

    assert floating.mask().isEmpty()
    assert floating.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert floating.testAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    assert floating.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    assert bool(floating.windowFlags() & Qt.WindowType.NoDropShadowWindowHint)
    assert not floating.autoFillBackground()

    floating.deleteLater()


def test_clipboard_shortcut_filter_accepts_text_widget_shortcuts(monkeypatch, qapp):
    class ShortcutSettings:
        def __init__(self):
            self.values = {}

        def get(self, key, default=None):
            return self.values.get(key, default)

        def set(self, key, value):
            self.values[key] = value

    text_widget = QLineEdit()
    shortcut_filter = _ClipboardShortcutFilter(ShortcutSettings())
    monkeypatch.setattr(
        app_module.QApplication,
        "focusWidget",
        staticmethod(lambda: text_widget),
    )

    copy_event = QKeyEvent(
        QEvent.Type.ShortcutOverride,
        Qt.Key.Key_C,
        Qt.KeyboardModifier.ControlModifier,
    )
    ordinary_event = QKeyEvent(
        QEvent.Type.ShortcutOverride,
        Qt.Key.Key_K,
        Qt.KeyboardModifier.ControlModifier,
    )
    key_press_event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_C,
        Qt.KeyboardModifier.ControlModifier,
    )

    assert shortcut_filter.eventFilter(text_widget, copy_event) is True
    assert copy_event.isAccepted()
    assert shortcut_filter.eventFilter(text_widget, ordinary_event) is False
    assert shortcut_filter.eventFilter(text_widget, key_press_event) is True

    monkeypatch.setattr(
        app_module.QApplication,
        "focusWidget",
        staticmethod(lambda: None),
    )
    assert shortcut_filter.eventFilter(text_widget, copy_event) is False
    text_widget.deleteLater()


def test_app_icon_status_splash_wait_and_close_helpers(monkeypatch, qapp):
    icons = []
    fake_qapp = SimpleNamespace(
        processEvents=lambda: setattr(fake_qapp, "processed", True),
        setWindowIcon=lambda icon: icons.append(icon),
    )
    app = SimpleNamespace(
        _qapp=fake_qapp,
        _app_icon=None,
        _splash=None,
        _splash_started_at=10.0,
        _MINIMUM_SPLASH_SECONDS=MeadowPyApp._MINIMUM_SPLASH_SECONDS,
    )
    app._process_pending_ui_events = lambda: MeadowPyApp._process_pending_ui_events(app)
    monkeypatch.setattr(app_module.sys, "platform", "linux")

    MeadowPyApp._set_app_icon(app)

    assert app._app_icon is not None
    assert icons == [app._app_icon]

    statuses = []
    app._splash = SimpleNamespace(
        set_status_text=lambda text: statuses.append(text),
        closed=False,
        close=lambda: setattr(app._splash, "closed", True),
    )
    MeadowPyApp._set_splash_status(app, "Almost ready")
    assert statuses == ["Almost ready"]
    assert fake_qapp.processed is True

    loop_state = {}

    class FakeLoop:
        def quit(self):
            loop_state["quit"] = True

        def exec(self):
            loop_state["exec"] = True

    delay_inputs = []
    monkeypatch.setattr(
        app_module,
        "remaining_delay_ms",
        lambda start, seconds: delay_inputs.append((start, seconds)) or 25,
    )
    monkeypatch.setattr(app_module, "QEventLoop", FakeLoop)
    monkeypatch.setattr(
        app_module.QTimer,
        "singleShot",
        lambda ms, callback: (loop_state.setdefault("ms", ms), callback()),
    )
    MeadowPyApp._wait_for_minimum_splash_time(app)
    assert delay_inputs == [(10.0, 1.5)]
    assert loop_state == {"ms": 25, "quit": True, "exec": True}

    MeadowPyApp._close_splash(app)
    assert app._splash is None


def test_wait_and_close_splash_are_noops_without_splash():
    app = SimpleNamespace(_splash=None)

    MeadowPyApp._set_splash_status(app, "ignored")
    MeadowPyApp._wait_for_minimum_splash_time(app)
    MeadowPyApp._close_splash(app)

    assert app._splash is None


def test_native_windows_icon_loads_both_sizes_and_sends_window_messages(
    monkeypatch,
    tmp_path,
):
    metrics = {11: 32, 12: 32, 49: 16, 50: 16}
    load_results = iter((101, 202))
    user32 = SimpleNamespace(
        LoadImageW=_CallableWinApi(callback=lambda *args: next(load_results)),
        SendMessageW=_CallableWinApi(result=1),
        GetSystemMetrics=_CallableWinApi(callback=lambda metric: metrics[metric]),
    )
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(user32=user32))
    monkeypatch.setattr(app_module.sys, "platform", "win32")
    controller = SimpleNamespace(_app_icon_path=tmp_path / "meadowpy.ico")
    widget = SimpleNamespace(winId=lambda: 42)

    MeadowPyApp._apply_native_app_icon(controller, widget)

    assert [call[2:5] for call in user32.LoadImageW.calls] == [
        (1, 32, 32),
        (1, 16, 16),
    ]
    assert user32.SendMessageW.calls == [
        (42, 0x0080, 1, 101),
        (42, 0x0080, 0, 202),
        (42, 0x0080, 2, 202),
    ]

    MeadowPyApp._apply_native_app_icon(controller, None)
    monkeypatch.setattr(app_module.sys, "platform", "linux")
    MeadowPyApp._apply_native_app_icon(controller, widget)
    assert len(user32.LoadImageW.calls) == 2


def test_native_icon_and_qt_logger_failures_are_nonfatal(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module.sys, "platform", "win32")
    controller = SimpleNamespace(_app_icon_path=tmp_path / "meadowpy.ico")
    MeadowPyApp._apply_native_app_icon(
        controller,
        SimpleNamespace(winId=lambda: (_ for _ in ()).throw(RuntimeError("no hwnd"))),
    )

    installed = []
    monkeypatch.setattr(app_module.Path, "home", lambda: tmp_path / "not-a-dir")
    (tmp_path / "not-a-dir").write_text("occupied", encoding="utf-8")
    monkeypatch.setattr(
        app_module,
        "qInstallMessageHandler",
        lambda handler: installed.append(handler),
    )
    handler = app_module._install_qt_message_logger()
    handler(app_module.QtMsgType.QtInfoMsg, None, "ignored write failure")
    assert installed == [handler]


def test_clipboard_filter_rejects_non_key_and_unsupported_focus(monkeypatch, qapp):
    shortcut_filter = _ClipboardShortcutFilter()
    monkeypatch.setattr(
        app_module.QApplication,
        "focusWidget",
        staticmethod(lambda: object()),
    )

    assert shortcut_filter.eventFilter(object(), QEvent(QEvent.Type.Show)) is False
    assert (
        shortcut_filter.eventFilter(
            object(),
            QKeyEvent(
                QEvent.Type.KeyPress,
                Qt.Key.Key_C,
                Qt.KeyboardModifier.ControlModifier,
            ),
        )
        is False
    )


def test_menu_helpers_cover_associated_menubars_and_non_menu_events(qapp):
    menubar = QMenuBar()
    associated = SimpleNamespace(
        associatedObjects=lambda: [object(), menubar]
    )
    menu_like = SimpleNamespace(parent=lambda: object(), menuAction=lambda: associated)
    assert _is_menubar_menu(menu_like) is True

    no_action = SimpleNamespace(parent=lambda: object(), menuAction=lambda: None)
    assert _is_menubar_menu(no_action) is False

    event_filter = _MenuRoundedMaskFilter()
    assert event_filter.eventFilter(object(), QEvent(QEvent.Type.Show)) is False

    floating = QMenu("Context")
    floating.resize(120, 60)
    assert event_filter.eventFilter(floating, QEvent(QEvent.Type.Polish)) is False
    assert event_filter.eventFilter(floating, QEvent(QEvent.Type.Resize)) is False
    floating.deleteLater()
    menubar.deleteLater()


def test_clipboard_filter_handles_non_key_keypress_and_reassigned_defaults(
    monkeypatch, qapp
):
    text_widget = QLineEdit()
    monkeypatch.setattr(
        app_module.QApplication,
        "focusWidget",
        staticmethod(lambda: text_widget),
    )
    shortcut_filter = _ClipboardShortcutFilter()

    fake_key_event = SimpleNamespace(type=lambda: QEvent.Type.KeyPress)
    assert shortcut_filter.eventFilter(text_widget, fake_key_event) is False

    modifier_only = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Control,
        Qt.KeyboardModifier.ControlModifier,
    )
    assert shortcut_filter.eventFilter(text_widget, modifier_only) is False

    monkeypatch.setattr(app_module, "STANDARD_EDIT_SHORTCUTS", {"edit.copy": ("copy", object())})
    monkeypatch.setattr(app_module, "get_default_shortcut", lambda shortcut_id: "Ctrl+C")
    monkeypatch.setattr(app_module, "get_shortcut", lambda settings, shortcut_id: "Ctrl+Shift+C")
    monkeypatch.setattr(
        app_module,
        "event_matches_shortcut",
        lambda event, shortcut: shortcut == "Ctrl+C",
    )
    assert shortcut_filter._event_matches_reassigned_default(modifier_only) is True
    text_widget.deleteLater()


def test_app_font_and_native_icon_helpers_cover_noop_paths(monkeypatch, qapp):
    fake_qapp = SimpleNamespace(fonts=[], setFont=lambda font: fake_qapp.fonts.append(font))
    controller = SimpleNamespace(_qapp=fake_qapp)
    MeadowPyApp._load_app_font(controller)
    assert fake_qapp.fonts == [controller._app_font]

    untouched = SimpleNamespace(_app_font=None, _window=SimpleNamespace(findChildren=lambda kind: []))
    MeadowPyApp._apply_font_to_all(untouched)

    monkeypatch.setattr(app_module.sys, "platform", "win32")
    no_handle = SimpleNamespace(_app_icon_path="icon.ico")
    MeadowPyApp._apply_native_app_icon(no_handle, SimpleNamespace(winId=lambda: 0))


def test_teardown_tolerates_deleted_qt_objects(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "qInstallMessageHandler",
        lambda handler: (_ for _ in ()).throw(RuntimeError("Qt gone")),
    )

    class Deleted:
        def close(self):
            raise RuntimeError("deleted")

        def deleteLater(self):
            raise RuntimeError("deleted")

        def isVisible(self):
            raise RuntimeError("deleted")

    class DeletedApp:
        def removeEventFilter(self, event_filter):
            raise RuntimeError("deleted")

        def sendPostedEvents(self, *args):
            raise RuntimeError("deleted")

        def processEvents(self):
            raise AssertionError("send already failed")

    controller = SimpleNamespace(
        _qt_message_handler=object(),
        _splash=Deleted(),
        _window=Deleted(),
        _menu_filter=object(),
        _clipboard_filter=object(),
        _qapp=DeletedApp(),
    )

    MeadowPyApp._teardown_qt_objects(controller)

    assert controller._qt_message_handler is None
    assert controller._splash is None
    assert controller._window is None
    assert controller._menu_filter is None
    assert controller._clipboard_filter is None

from types import SimpleNamespace

from PyQt6.QtCore import QElapsedTimer
from PyQt6.QtGui import QIcon

from meadowpy.core.debug_manager import DebugState
from meadowpy.core.file_manager import FileManager
from meadowpy.core.recent_files import RecentFilesManager
from meadowpy.core.settings import Settings
import meadowpy.ui.main_window as main_window_module
from meadowpy.ui.main_window import MainWindow
from meadowpy.ui.welcome_widget import WelcomeWidget
from helpers import DummySignal


def _wait_for_debug_state(qapp, manager, state, timeout_ms=5_000):
    timer = QElapsedTimer()
    timer.start()
    while manager.state != state and timer.elapsed() < timeout_ms:
        qapp.processEvents()
    return manager.state == state


def test_main_window_refreshes_theme_icons_and_shortcut_consumers(monkeypatch):
    icon_calls = []
    monkeypatch.setattr(
        main_window_module,
        "load_themed_icon",
        lambda name, theme: icon_calls.append((name, theme)) or QIcon(),
    )

    class IconConsumer:
        def __init__(self):
            self.icons = []

        def setIcon(self, icon):
            self.icons.append(icon)

    actions = [IconConsumer() for _ in range(4)]
    restart_button = IconConsumer()
    terminal_refreshes = []
    window = SimpleNamespace(
        _settings=SimpleNamespace(
            get=lambda key, default=None: "default_dark"
            if key == "editor.theme"
            else default
        ),
        _run_action=actions[0],
        _stop_action=actions[1],
        _debug_action=actions[2],
        _restart_console_action=actions[3],
        _output_panel=SimpleNamespace(_restart_repl_btn=restart_button),
        _terminal_panel=SimpleNamespace(
            refresh_theme_icons=lambda: terminal_refreshes.append(True)
        ),
    )

    MainWindow._refresh_themed_icons(window)

    assert icon_calls == [
        ("run", "default_dark"),
        ("stop", "default_dark"),
        ("debug", "default_dark"),
        ("restart", "default_dark"),
        ("restart", "default_dark"),
    ]
    assert all(len(action.icons) == 1 for action in actions)
    assert len(restart_button.icons) == 1
    assert terminal_refreshes == [True]

    reapplied = []
    toolbar_updates = []
    debug_updates = []
    window._shortcut_actions = {
        "file.save": ("save-action", "Save{shortcut_suffix}"),
        "file.open": ("open-action", None),
    }
    window._apply_shortcut_to_action = (
        lambda shortcut_id, action, tooltip: reapplied.append(
            (shortcut_id, action, tooltip)
        )
    )
    window._toolbar_builder = SimpleNamespace(
        update_shortcut_tooltips=lambda: toolbar_updates.append(True)
    )
    window._refresh_debug_shortcut_tooltips = lambda: debug_updates.append(True)

    MainWindow._refresh_shortcut_actions(window)

    assert [item[0] for item in reapplied] == ["file.save", "file.open"]
    assert toolbar_updates == [True]
    assert debug_updates == [True]


def test_full_window_step_into_print_does_not_abort(qapp, tmp_path):
    settings = Settings(tmp_path)
    settings.set("general.restore_tabs_on_startup", False)
    settings.set("editor.linting_enabled", False)
    settings.set("editor.linter", "pyflakes")
    settings.set("run.show_output_panel", False)
    settings.set("ollama.auto_connect", False)
    settings.set("repl.auto_start", False)
    recent_files = RecentFilesManager(settings)
    file_manager = FileManager(settings, recent_files)
    script = tmp_path / "step_into_repro.py"
    source = "print('first')\nprint('second')\n"
    script.write_text(source, encoding="utf-8")

    window = MainWindow(settings, file_manager, recent_files)
    try:
        window.show()
        qapp.processEvents()
        editor = window._tab_manager.open_file_in_tab(str(script), source)
        editor.toggle_breakpoint(0)
        editor.toggle_breakpoint(1)
        window.action_start_debug()

        assert _wait_for_debug_state(
            qapp,
            window._debug_manager,
            DebugState.PAUSED,
        )
        qapp.processEvents()
        window._step_into_action.trigger()
        assert _wait_for_debug_state(
            qapp,
            window._debug_manager,
            DebugState.PAUSED,
        )
        qapp.processEvents()
        assert window._tab_manager.current_editor() is editor
        assert editor.getCursorPosition()[0] == 1
    finally:
        window._debug_manager.stop_debug()
        window._shutdown_background_work()
        window.deleteLater()
        qapp.processEvents()


def test_main_window_builds_with_controller_layer(qapp, tmp_path):
    settings = Settings(tmp_path)
    settings.set("general.restore_tabs_on_startup", False)
    recent_files = RecentFilesManager(settings)
    file_manager = FileManager(settings, recent_files)

    window = MainWindow(settings, file_manager, recent_files)

    assert window._workspace_controller is not None
    assert window._code_quality_controller is not None
    assert window._execution_controller is not None
    assert window._debug_controller is not None
    assert window._ai_assistant_controller is not None
    assert window.action_run_file == window._execution_controller.action_run_file
    assert window.action_ai_review_file == window._ai_assistant_controller.action_ai_review_file
    assert isinstance(window._tab_manager.widget(0), WelcomeWidget)

    window._ollama_client.stop()
    window._lint_runner.stop()
    window._repl_manager.stop()
    window.deleteLater()


def test_connect_signals_wires_existing_and_new_editors_once():
    existing_editor = object()
    new_editor = object()
    wired = []
    tab_changed = DummySignal()
    editor_created = DummySignal()
    editor_closed = DummySignal()
    recent_changed = DummySignal()
    file_saved = DummySignal()
    settings_changed = DummySignal()
    window = SimpleNamespace(
        _tab_manager=SimpleNamespace(
            tab_changed=tab_changed,
            editor_created=editor_created,
            editor_closed=editor_closed,
            count=lambda: 1,
            widget=lambda index: existing_editor,
        ),
        _on_tab_changed=lambda editor: None,
        _wire_editor_breakpoints=wired.append,
        _on_editor_closed=lambda editor: wired.append(("closed", editor)),
        _recent_files=SimpleNamespace(recent_files_changed=recent_changed),
        _menu_builder=SimpleNamespace(rebuild_recent_files_menu=lambda: None),
        _file_manager=SimpleNamespace(file_saved=file_saved),
        _on_file_saved=lambda path: None,
        _settings=SimpleNamespace(settings_changed=settings_changed),
        _on_settings_changed=lambda key, value: None,
    )

    MainWindow._connect_signals(window)
    editor_created.emit(new_editor)
    editor_closed.emit(existing_editor)

    assert wired == [
        existing_editor,
        new_editor,
        ("closed", existing_editor),
    ]
    assert editor_created._callbacks == [window._wire_editor_breakpoints]
    assert editor_closed._callbacks == [window._on_editor_closed]


class FakeCloseEvent:
    def __init__(self):
        self.accepted = False
        self.ignored = False

    def accept(self):
        self.accepted = True

    def ignore(self):
        self.ignored = True


class FakeMimeData:
    def __init__(self, has_urls=True, urls=None):
        self._has_urls = has_urls
        self._urls = list(urls or [])

    def hasUrls(self):
        return self._has_urls

    def urls(self):
        return self._urls


class FakeDragEvent:
    def __init__(self, has_urls=True, urls=None):
        self.accepted = False
        self._mime_data = FakeMimeData(has_urls, urls)

    def mimeData(self):
        return self._mime_data

    def acceptProposedAction(self):
        self.accepted = True


def test_drag_events_accept_file_urls():
    event = FakeDragEvent(has_urls=True)

    MainWindow.dragEnterEvent(None, event)
    MainWindow.dragMoveEvent(None, event)

    assert event.accepted is True


class FakeUrl:
    def __init__(self, path, local=True):
        self._path = str(path)
        self._local = local

    def isLocalFile(self):
        return self._local

    def toLocalFile(self):
        return self._path


def test_drop_event_opens_files_and_project_folders(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    script = tmp_path / "demo.py"
    script.write_text("print('hi')", encoding="utf-8")
    calls = []
    window = SimpleNamespace(
        _file_explorer=SimpleNamespace(
            set_root_folder=lambda path: calls.append(("root", path)),
            show=lambda: calls.append(("explorer_show",)),
        ),
        _settings=SimpleNamespace(
            set=lambda key, value: calls.append(("setting", key, value))
        ),
        _search_panel=SimpleNamespace(
            set_root_path=lambda path: calls.append(("search_root", path))
        ),
        _file_manager=SimpleNamespace(
            read_file=lambda path: calls.append(("read", path)) or "content"
        ),
        _tab_manager=SimpleNamespace(
            open_file_in_tab=lambda path, content, large_file_mode=False: calls.append(
                ("open", path, content)
            )
        ),
        _recent_files=SimpleNamespace(
            add=lambda path: calls.append(("recent", path))
        ),
    )
    event = FakeDragEvent(urls=[
        FakeUrl(project),
        FakeUrl(script),
        FakeUrl(tmp_path / "remote.py", local=False),
    ])

    MainWindow.dropEvent(window, event)

    assert ("root", str(project)) in calls
    assert ("search_root", str(project)) not in calls
    assert ("read", str(script)) in calls
    assert ("open", str(script), "content") in calls
    assert ("recent", str(script)) in calls
    assert event.accepted is True


def test_close_event_ignores_without_shutdown_when_save_prompt_cancelled():
    calls = []
    window = SimpleNamespace(
        _tab_manager=SimpleNamespace(
            prompt_save_all=lambda: calls.append("prompt") or False
        ),
        _save_state=lambda: calls.append("save_state"),
        _settings=SimpleNamespace(save=lambda: calls.append("settings_save")),
        _shutdown_background_work=lambda: calls.append("shutdown"),
    )
    event = FakeCloseEvent()

    MainWindow.closeEvent(window, event)

    assert calls == ["prompt"]
    assert event.ignored is True
    assert event.accepted is False


def test_close_event_saves_then_stops_background_work():
    calls = []
    window = SimpleNamespace(
        _tab_manager=SimpleNamespace(
            prompt_save_all=lambda: calls.append("prompt") or True
        ),
        _save_state=lambda: calls.append("save_state"),
        _settings=SimpleNamespace(save=lambda: calls.append("settings_save")),
        _shutdown_background_work=lambda: calls.append("shutdown"),
    )
    event = FakeCloseEvent()

    MainWindow.closeEvent(window, event)

    assert calls == ["prompt", "save_state", "settings_save", "shutdown"]
    assert event.accepted is True
    assert event.ignored is False


def test_close_event_ignores_when_save_prompt_raises():
    calls = []

    def prompt_save_all():
        calls.append("prompt")
        raise RuntimeError("prompt failed")

    window = SimpleNamespace(
        _tab_manager=SimpleNamespace(prompt_save_all=prompt_save_all),
        _log_shutdown_error=lambda name, exc: calls.append(
            ("log", name, str(exc))
        ),
        _save_state=lambda: calls.append("save_state"),
        _settings=SimpleNamespace(save=lambda: calls.append("settings_save")),
        _shutdown_background_work=lambda: calls.append("shutdown"),
    )
    event = FakeCloseEvent()

    MainWindow.closeEvent(window, event)

    assert calls == ["prompt", ("log", "save_prompt", "prompt failed")]
    assert event.ignored is True
    assert event.accepted is False


def test_close_event_logs_save_errors_and_still_shuts_down():
    calls = []

    def save_state():
        calls.append("save_state")
        raise OSError("settings path unavailable")

    window = SimpleNamespace(
        _tab_manager=SimpleNamespace(
            prompt_save_all=lambda: calls.append("prompt") or True
        ),
        _save_state=save_state,
        _settings=SimpleNamespace(save=lambda: calls.append("settings_save")),
        _shutdown_background_work=lambda: calls.append("shutdown"),
        _log_shutdown_error=lambda name, exc: calls.append(
            ("log", name, str(exc))
        ),
    )
    event = FakeCloseEvent()

    MainWindow.closeEvent(window, event)

    assert calls == [
        "prompt",
        "save_state",
        ("log", "save_state", "settings path unavailable"),
        "shutdown",
    ]
    assert event.accepted is True
    assert event.ignored is False


def test_close_event_logs_shutdown_errors_and_still_accepts():
    calls = []

    def shutdown():
        calls.append("shutdown")
        raise RuntimeError("worker cleanup failed")

    window = SimpleNamespace(
        _tab_manager=SimpleNamespace(
            prompt_save_all=lambda: calls.append("prompt") or True
        ),
        _save_state=lambda: calls.append("save_state"),
        _settings=SimpleNamespace(save=lambda: calls.append("settings_save")),
        _shutdown_background_work=shutdown,
        _log_shutdown_error=lambda name, exc: calls.append(
            ("log", name, str(exc))
        ),
    )
    event = FakeCloseEvent()

    MainWindow.closeEvent(window, event)

    assert calls == [
        "prompt",
        "save_state",
        "settings_save",
        "shutdown",
        ("log", "shutdown", "worker cleanup failed"),
    ]
    assert event.accepted is True
    assert event.ignored is False


def test_shutdown_background_work_stops_long_running_components():
    calls = []

    class Stopper:
        def __init__(self, name):
            self.name = name

        def stop(self):
            calls.append(self.name)

    class FakeDebugManager:
        def is_running(self):
            return True

        def stop_debug(self):
            calls.append("debug")

    class FakeProcessRunner:
        def is_running(self):
            return True

        def stop(self):
            calls.append("process")

    window = SimpleNamespace(
        _ollama_client=Stopper("ollama"),
        _lint_runner=Stopper("lint"),
        _search_panel=Stopper("search"),
        _terminal_panel=Stopper("terminal"),
        _debug_manager=FakeDebugManager(),
        _process_runner=FakeProcessRunner(),
        _repl_manager=SimpleNamespace(
            is_running=True,
            stop=lambda: calls.append("repl"),
        ),
        _log_shutdown_error=lambda name, exc: calls.append(("log", name, str(exc))),
    )
    window._stop_shutdown_component = (
        lambda name, callback: MainWindow._stop_shutdown_component(
            window, name, callback
        )
    )

    MainWindow._shutdown_background_work(window)

    assert calls == [
        "ollama",
        "lint",
        "search",
        "terminal",
        "debug",
        "process",
        "repl",
    ]


def test_stop_shutdown_component_logs_errors_and_continues():
    calls = []

    def stop_callback():
        calls.append("stop")
        raise RuntimeError("stop failed")

    window = SimpleNamespace(
        _log_shutdown_error=lambda name, exc: calls.append(
            ("log", name, str(exc))
        )
    )

    MainWindow._stop_shutdown_component(window, "lint_runner", stop_callback)

    assert calls == ["stop", ("log", "lint_runner", "stop failed")]


def test_log_shutdown_error_writes_traceback(tmp_path):
    window = SimpleNamespace(
        _settings=SimpleNamespace(config_file_path=tmp_path / "settings.json")
    )

    try:
        raise RuntimeError("cleanup failed")
    except RuntimeError as exc:
        MainWindow._log_shutdown_error(window, "process_runner", exc)

    log_text = (tmp_path / "meadowpy.log").read_text(encoding="utf-8")
    assert "shutdown:process_runner" in log_text
    assert "RuntimeError: cleanup failed" in log_text


class FakeBytePayload:
    def __init__(self, text):
        self._text = text

    def data(self):
        return self._text.encode()


class FakeGeometry:
    def __init__(self, text):
        self._text = text

    def toBase64(self):
        return FakeBytePayload(self._text)


def test_save_state_persists_geometry_state_and_open_files():
    saved = {}
    window = SimpleNamespace(
        saveGeometry=lambda: FakeGeometry("geom"),
        saveState=lambda: FakeGeometry("state"),
        _tab_manager=SimpleNamespace(
            get_open_file_paths=lambda: ["a.py", "b.py"]
        ),
        _settings=SimpleNamespace(
            set=lambda key, value: saved.__setitem__(key, value)
        ),
    )

    MainWindow._save_state(window)

    assert saved == {
        "window.geometry": "geom",
        "window.state": "state",
        "general.open_files": ["a.py", "b.py"],
    }


def test_restore_state_reopens_existing_files_without_welcome(tmp_path):
    script = tmp_path / "demo.py"
    script.write_text("print('hi')", encoding="utf-8")
    calls = []

    def get_setting(key, default=None):
        return {
            "window.geometry": "AAAA",
            "window.state": "BBBB",
            "general.restore_tabs_on_startup": True,
            "general.open_files": [str(script), str(tmp_path / "missing.py")],
        }.get(key, default)

    window = SimpleNamespace(
        restoreGeometry=lambda payload: calls.append(("geom", bytes(payload))),
        restoreState=lambda payload: calls.append(("state", bytes(payload))),
        _settings=SimpleNamespace(get=get_setting),
        _file_manager=SimpleNamespace(
            read_file=lambda path: calls.append(("read", path)) or "content"
        ),
        _tab_manager=SimpleNamespace(
            open_file_in_tab=lambda path, content, large_file_mode=False: calls.append(
                ("open", path, content)
            ),
            count=lambda: 1,
        ),
        _show_welcome=lambda: calls.append(("welcome",)),
    )

    MainWindow._restore_state(window)

    assert ("read", str(script)) in calls
    assert ("open", str(script), "content") in calls
    assert ("welcome",) not in calls


def test_restore_state_reopens_files_with_default_settings(tmp_path):
    script = tmp_path / "remembered.py"
    script.write_text("print('remember me')", encoding="utf-8")
    settings = Settings(tmp_path)
    settings.set("general.open_files", [str(script)])
    opened = []
    calls = []

    window = SimpleNamespace(
        restoreState=lambda payload: calls.append(("state", bytes(payload))),
        _settings=settings,
        _file_manager=SimpleNamespace(
            read_file=lambda path: script.read_text(encoding="utf-8")
        ),
        _tab_manager=SimpleNamespace(
            open_file_in_tab=lambda path, content, large_file_mode=False: (
                opened.append((path, content))
            ),
            count=lambda: len(opened),
        ),
        _show_welcome=lambda: calls.append(("welcome",)),
    )

    MainWindow._restore_state(window)

    assert opened == [(str(script), "print('remember me')")]
    assert ("welcome",) not in calls

from types import SimpleNamespace

from meadowpy.core.file_manager import FileManager
from meadowpy.core.recent_files import RecentFilesManager
from meadowpy.core.settings import Settings
from meadowpy.ui.main_window import MainWindow
from meadowpy.ui.welcome_widget import WelcomeWidget


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
            open_file_in_tab=lambda path, content: calls.append(
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
    assert ("search_root", str(project)) in calls
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
        _debug_manager=FakeDebugManager(),
        _process_runner=FakeProcessRunner(),
        _repl_manager=SimpleNamespace(
            is_running=True,
            stop=lambda: calls.append("repl"),
        ),
    )

    MainWindow._shutdown_background_work(window)

    assert calls == ["ollama", "lint", "search", "debug", "process", "repl"]


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
            open_file_in_tab=lambda path, content: calls.append(
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

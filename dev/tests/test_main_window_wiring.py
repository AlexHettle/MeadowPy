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

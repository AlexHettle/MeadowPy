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

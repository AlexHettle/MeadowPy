from types import SimpleNamespace

from meadowpy.ui.controllers.workspace_controller import WorkspaceController
from meadowpy.ui.controllers.window_context import MainWindowContext


class FakeEditor:
    def __init__(self):
        self.text_value = ""
        self.modified = True

    def setText(self, text):
        self.text_value = text

    def setModified(self, value):
        self.modified = value


class FakeTabManager:
    def __init__(self):
        self.closed_welcome = False
        self.editor = FakeEditor()
        self.welcome_args = None

    def close_welcome_tab(self):
        self.closed_welcome = True

    def new_tab(self):
        return self.editor

    def count(self):
        return 0

    def show_welcome_tab(self, **kwargs):
        self.welcome_args = kwargs
        return FakeWelcome()


class FakeSettings:
    def get(self, key, default=None):
        values = {
            "editor.theme": "default_dark",
            "editor.custom_theme.base": "dark",
            "editor.custom_theme.accent": "#2F7A44",
        }
        return values.get(key, default)


class FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)


class FakeWelcome:
    def __init__(self):
        self.action_new_file = FakeSignal()
        self.action_open_file = FakeSignal()
        self.action_open_folder = FakeSignal()
        self.template_selected = FakeSignal()


def test_template_selection_opens_clean_untitled_tab():
    tabs = FakeTabManager()
    window = SimpleNamespace(_tab_manager=tabs)
    controller = WorkspaceController(MainWindowContext(window, None, None, None))

    controller._on_template_selected("Hello", "print('hello')")

    assert tabs.closed_welcome is True
    assert tabs.editor.text_value == "print('hello')"
    assert tabs.editor.modified is False


def test_show_welcome_creates_welcome_tab_with_current_theme():
    settings = FakeSettings()
    tabs = FakeTabManager()
    window = SimpleNamespace(_settings=settings, _tab_manager=tabs)
    controller = WorkspaceController(MainWindowContext(window, settings, None, None))

    controller.action_show_welcome()

    assert tabs.welcome_args == {
        "theme_name": "default_dark",
        "custom_base": "dark",
        "custom_accent": "#2F7A44",
    }

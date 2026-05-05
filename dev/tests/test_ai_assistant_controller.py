from types import SimpleNamespace

from meadowpy.ui.controllers.ai_assistant_controller import AIAssistantController
from meadowpy.ui.controllers.window_context import MainWindowContext


class FakeChatPanel:
    def __init__(self):
        self.prompts = []
        self.context = None

    def send_message_programmatic(self, prompt):
        self.prompts.append(prompt)

    def update_editor_context(self, **kwargs):
        self.context = kwargs


class FakeEditor:
    display_name = "demo.py"

    def __init__(self, text="print('hi')\n"):
        self._text = text
        self.cursor = (0, 0)

    def text(self, line=None):
        if line is None:
            return self._text
        return self._text.splitlines(True)[line]

    def getCursorPosition(self):
        return self.cursor


def make_controller(editor=None):
    window = SimpleNamespace(
        _ai_chat_panel=FakeChatPanel(),
        _tab_manager=SimpleNamespace(current_editor=lambda: editor),
    )
    ctx = MainWindowContext(window=window, settings=None, file_manager=None, recent_files=None)
    return AIAssistantController(ctx), window


def test_explain_selected_code_builds_beginner_prompt():
    controller, window = make_controller()

    controller._on_ai_explain_requested("x = 1")

    assert "explain" in window._ai_chat_panel.prompts[0].lower()
    assert "x = 1" in window._ai_chat_panel.prompts[0]


def test_review_file_includes_filename_and_code():
    editor = FakeEditor("def main():\n    pass\n")
    controller, window = make_controller(editor)

    controller.action_ai_review_file()

    assert "demo.py" in window._ai_chat_panel.prompts[0]
    assert "def main()" in window._ai_chat_panel.prompts[0]


def test_ai_context_finds_enclosing_function():
    editor = FakeEditor("def greet():\n    print('hi')\n")
    editor.cursor = (1, 4)
    controller, window = make_controller(editor)

    controller._update_ai_context(editor)

    assert window._ai_chat_panel.context["filename"] == "demo.py"
    assert window._ai_chat_panel.context["function_name"] == "def greet"
    assert window._ai_chat_panel.context["cursor_line"] == 1

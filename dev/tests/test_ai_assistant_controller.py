from types import SimpleNamespace

import meadowpy.ui.controllers.ai_assistant_controller as ai_controller_module
from meadowpy.ui.controllers.ai_assistant_controller import AIAssistantController
from meadowpy.ui.controllers.window_context import MainWindowContext


class FakeChatPanel:
    def __init__(self):
        self.prompts = []
        self.context = None
        self.model_names = []

    def send_message_programmatic(self, prompt):
        self.prompts.append(prompt)

    def update_editor_context(self, **kwargs):
        self.context = kwargs

    def set_model_name(self, model):
        self.model_names.append(model)


class FakeEditor:
    def __init__(self, text="print('hi')\n", file_path=None, display_name="demo.py"):
        self._text = text
        self.file_path = file_path
        self.display_name = display_name
        self.cursor = (0, 0)

    def text(self, line=None):
        if line is None:
            return self._text
        return self._text.splitlines(True)[line]

    def getCursorPosition(self):
        return self.cursor


class RichEditor:
    display_name = "demo.py"

    def __init__(self, lines=None, cursor=(0, 0)):
        self._lines = lines or ["print('hi')\n"]
        self.cursor = cursor
        self.inserted = []
        self.selections = []
        self.removed = 0
        self.focused = False

    def text(self, line=None):
        if line is None:
            return "".join(self._lines)
        if 0 <= line < len(self._lines):
            return self._lines[line]
        return ""

    def lines(self):
        return len(self._lines)

    def getCursorPosition(self):
        return self.cursor

    def setCursorPosition(self, line, col):
        self.cursor = (line, col)

    def insert(self, code):
        self.inserted.append(code)

    def setSelection(self, *args):
        self.selections.append(args)

    def removeSelectedText(self):
        self.removed += 1

    def setFocus(self):
        self.focused = True


def make_controller(editor=None):
    window = SimpleNamespace(
        _ai_chat_panel=FakeChatPanel(),
        _tab_manager=SimpleNamespace(current_editor=lambda: editor),
    )
    ctx = MainWindowContext(window=window, settings=None, file_manager=None, recent_files=None)
    return AIAssistantController(ctx), window


class FakeSettings:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key, default=None):
        return self.values.get(key, default)


class FakeStatusBar:
    def __init__(self):
        self.ollama_updates = []
        self.messages = []
        self.ollama_label = SimpleNamespace(
            rect=lambda: SimpleNamespace(topLeft=lambda: "top-left"),
            mapToGlobal=lambda pos: ("global", pos),
        )

    def update_ollama_status(self, connected, model):
        self.ollama_updates.append((connected, model))

    def show_message(self, message, timeout=3000):
        self.messages.append((message, timeout))


class FakeModelSelector:
    def __init__(self):
        self.connected = []
        self.models = []
        self.current = []
        self.shown_at = []

    def set_connected(self, connected):
        self.connected.append(connected)

    def set_models(self, models):
        self.models.append(models)

    def set_current_model(self, model):
        self.current.append(model)

    def show_at(self, pos):
        self.shown_at.append(pos)


class FakeOllamaClient:
    def __init__(self):
        self.is_connected = True
        self.connection_checks = 0
        self.selected = []
        self.sent_messages = []

    def check_connection(self):
        self.connection_checks += 1

    def select_model(self, model):
        self.selected.append(model)

    def send_chat(self, messages):
        self.sent_messages.append(messages)


def make_rich_controller(editor=None):
    window = SimpleNamespace(
        _settings=FakeSettings({"ollama.selected_model": "llama3"}),
        _status_bar_manager=FakeStatusBar(),
        _model_selector=FakeModelSelector(),
        _ollama_client=FakeOllamaClient(),
        _ai_chat_panel=FakeChatPanel(),
        _tab_manager=SimpleNamespace(current_editor=lambda: editor),
    )
    ctx = MainWindowContext(window=window, settings=window._settings, file_manager=None, recent_files=None)
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


def test_review_file_uses_text_prompt_for_saved_non_python_editor():
    editor = FakeEditor("hello\n", file_path="notes.txt", display_name="notes.txt")
    controller, window = make_controller(editor)

    controller.action_ai_review_file()

    prompt = window._ai_chat_panel.prompts[0]
    assert 'entire text file "notes.txt"' in prompt
    assert "hello" in prompt
    assert "Python file" not in prompt
    assert "```python" not in prompt


def test_selected_text_explain_and_improve_handle_non_python_editor():
    editor = FakeEditor("hello\n", file_path="notes.txt", display_name="notes.txt")
    controller, window = make_controller(editor)

    controller._on_ai_explain_requested("hello")
    controller._on_ai_improve_requested("hello")

    assert len(window._ai_chat_panel.prompts) == 1
    assert "following text" in window._ai_chat_panel.prompts[0]
    assert "```python" not in window._ai_chat_panel.prompts[0]


def test_ai_context_finds_enclosing_function():
    editor = FakeEditor("def greet():\n    print('hi')\n")
    editor.cursor = (1, 4)
    controller, window = make_controller(editor)

    controller._update_ai_context(editor)

    assert window._ai_chat_panel.context["filename"] == "demo.py"
    assert window._ai_chat_panel.context["function_name"] == "def greet"
    assert window._ai_chat_panel.context["cursor_line"] == 1


def test_large_file_ai_context_omits_full_file_text():
    editor = FakeEditor("def greet():\n    print('hi')\n")
    editor.large_file_mode = True
    editor.cursor = (1, 4)
    controller, window = make_controller(editor)

    controller._update_ai_context(editor)

    assert window._ai_chat_panel.context == {
        "filename": "demo.py",
        "function_name": "",
        "cursor_line": 1,
        "file_text": "",
    }


def test_large_file_review_is_blocked_with_status_message():
    editor = FakeEditor("print('huge')\n")
    editor.large_file_mode = True
    controller, window = make_rich_controller(editor)

    controller.action_ai_review_file()

    assert window._ai_chat_panel.prompts == []
    assert window._status_bar_manager.messages == [
        (
            "Full-file AI review is disabled for large files. "
            "Select a smaller section instead.",
            7000,
        )
    ]


def test_ollama_status_model_selection_and_chat_forwarding():
    controller, window = make_rich_controller()

    controller._on_ollama_connection_changed(True, "connected")
    controller._on_ollama_connection_changed(False, "offline")
    controller._on_ollama_models_updated(["llama3", "qwen3"])
    controller._on_model_chosen("__retry__")
    controller._on_model_chosen("__refresh__")
    controller._on_model_chosen("qwen3")
    controller._on_ollama_status_clicked()
    controller._on_chat_requested([{"role": "user", "content": "hi"}])

    assert window._status_bar_manager.ollama_updates[:2] == [
        (True, "llama3"),
        (False, ""),
    ]
    assert window._model_selector.connected == [True, False]
    assert window._model_selector.models == [["llama3", "qwen3"]]
    assert window._ollama_client.connection_checks == 2
    assert window._ollama_client.selected == ["qwen3"]
    assert window._model_selector.current == ["qwen3", "llama3"]
    assert window._model_selector.shown_at == [("global", "top-left")]
    assert window._ollama_client.sent_messages == [[{"role": "user", "content": "hi"}]]


def test_ollama_setup_dialog_opens_and_rechecks(monkeypatch):
    controller, window = make_rich_controller()
    dialogs = []

    class FakeSetupDialog:
        def __init__(self, settings, parent=None):
            self.settings = settings
            self.parent = parent
            dialogs.append(self)

        def exec(self):
            return 0

    monkeypatch.setattr(
        ai_controller_module,
        "OllamaSetupDialog",
        FakeSetupDialog,
    )

    controller._on_model_chosen("__setup__")

    assert dialogs[0].settings is window._settings
    assert dialogs[0].parent is window
    assert window._ollama_client.connection_checks == 1
    assert window._model_selector.current == ["llama3"]
    assert window._ai_chat_panel.model_names == ["llama3"]
    assert window._status_bar_manager.ollama_updates == [(True, "llama3")]


def test_ai_improve_docstring_runtime_and_lint_prompts_include_context():
    editor = RichEditor(
        [
            "def greet(name):\n",
            "    value = name.upper()\n",
            "\n",
            "    return value\n",
        ],
        cursor=(1, 4),
    )
    controller, window = make_rich_controller(editor)

    controller._on_ai_improve_requested("x=1")
    controller._on_ai_docstring_requested("def greet(name):\n    pass", 1)
    controller._on_output_ai_fix_requested("NameError: missing")
    controller._on_lint_ai_fix_requested("F821", 2, "undefined name")

    prompts = window._ai_chat_panel.prompts
    assert "suggest improvements" in prompts[0]
    assert "x=1" in prompts[0]
    assert "Generate a Python docstring" in prompts[1]
    assert editor.cursor == (1, 0)
    assert "**My code:**" in prompts[2]
    assert "NameError: missing" in prompts[2]
    assert "1: def greet(name):" in prompts[3]
    assert "2:     value = name.upper()  # <-- issue here" in prompts[3]
    assert "4:     return value" in prompts[3]


def test_ai_runtime_and_lint_prompts_handle_missing_editor_context():
    controller, window = make_rich_controller(editor=None)

    controller.action_ai_review_file()
    controller._on_output_ai_fix_requested("ZeroDivisionError")
    controller._on_lint_ai_fix_requested("W291", 5, "trailing whitespace")

    assert len(window._ai_chat_panel.prompts) == 2
    assert "I got the following Python error" in window._ai_chat_panel.prompts[0]
    assert "ZeroDivisionError" in window._ai_chat_panel.prompts[0]
    assert "W291" in window._ai_chat_panel.prompts[1]
    assert "relevant code" not in window._ai_chat_panel.prompts[1]


def test_code_insert_reindents_docstrings_and_generic_insertions():
    editor = RichEditor(
        ["def greet():\n", "    pass\n", "\n"],
        cursor=(1, 0),
    )
    controller, _ = make_rich_controller(editor)

    controller._on_code_insert_requested('```python\n"""Say hello."""\n```')

    assert editor.inserted == ['    """Say hello."""\n']
    assert editor.cursor == (2, 0)
    assert editor.selections == [(2, 0, 3, 0)]
    assert editor.removed == 1
    assert editor.focused is True

    generic = RichEditor(["print('a')\n"], cursor=(0, 10))
    controller, _ = make_rich_controller(generic)
    controller._on_code_insert_requested("print('b')")

    assert generic.inserted == ["print('b')\n"]
    assert generic.cursor == (1, 0)
    assert generic.focused is True


def test_docstring_insert_falls_back_to_normal_insert_without_triple_quotes():
    editor = RichEditor(["def greet():\n", "    pass\n"], cursor=(1, 0))
    controller, _ = make_rich_controller(editor)

    controller._on_code_insert_requested("return 42")

    assert editor.inserted == ["return 42\n"]
    assert editor.cursor == (2, 0)

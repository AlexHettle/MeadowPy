from meadowpy.core.settings import Settings
from meadowpy.editor.smart_indent import SmartIndentHandler
from tests.helpers import DummyEditor


def make_handler(tmp_path, text="", cursor=(0, 0), smart_indent=True, use_spaces=True, tab_width=4):
    settings = Settings(tmp_path)
    settings.set("editor.smart_indent", smart_indent)
    settings.set("editor.use_spaces", use_spaces)
    settings.set("editor.tab_width", tab_width)
    editor = DummyEditor(text)
    editor.setCursorPosition(*cursor)
    return editor, SmartIndentHandler(editor, settings)


def test_handle_return_returns_false_when_disabled(tmp_path):
    _, handler = make_handler(tmp_path, smart_indent=False)

    assert handler.handle_return() is False


def test_handle_return_adds_indent_after_colon(tmp_path):
    editor, handler = make_handler(tmp_path, text="if ready:", cursor=(0, 9))

    assert handler.handle_return() is True
    assert editor.all_text() == "if ready:\n    "
    assert editor.getCursorPosition() == (1, 4)


def test_handle_return_dedents_after_return_keyword(tmp_path):
    editor, handler = make_handler(tmp_path, text="    return value", cursor=(0, 16))

    assert handler.handle_return() is True
    assert editor.all_text() == "    return value\n"
    assert editor.getCursorPosition() == (1, 0)


def test_handle_return_uses_tabs_when_configured(tmp_path):
    editor, handler = make_handler(
        tmp_path,
        text="if ready:",
        cursor=(0, 9),
        use_spaces=False,
    )

    assert handler.handle_return() is True
    assert editor.all_text() == "if ready:\n\t"
    assert editor.getCursorPosition() == (1, 1)


def test_handle_return_falls_through_on_blank_line(tmp_path):
    _, handler = make_handler(tmp_path, text="    ", cursor=(0, 4))

    assert handler.handle_return() is False

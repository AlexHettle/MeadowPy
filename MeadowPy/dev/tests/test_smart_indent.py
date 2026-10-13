import pytest
from PyQt6.QtCore import QCoreApplication, QEvent, Qt
from PyQt6.QtTest import QTest

from meadowpy.editor.code_editor import CodeEditor
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


def test_handle_return_ignores_comment_colon(tmp_path):
    _, handler = make_handler(tmp_path, text="# TODO:", cursor=(0, 7))

    assert handler.handle_return() is False


def test_handle_return_adds_indent_after_colon_with_trailing_comment(tmp_path):
    editor, handler = make_handler(
        tmp_path,
        text="if ready:  # check",
        cursor=(0, 18),
    )

    assert handler.handle_return() is True
    assert editor.all_text() == "if ready:  # check\n    "
    assert editor.getCursorPosition() == (1, 4)


def test_handle_return_ignores_string_colon(tmp_path):
    _, handler = make_handler(tmp_path, text='label = "TODO:"', cursor=(0, 15))

    assert handler.handle_return() is False


def test_handle_return_dedents_after_return_keyword(tmp_path):
    editor, handler = make_handler(tmp_path, text="    return value", cursor=(0, 16))

    assert handler.handle_return() is True
    assert editor.all_text() == "    return value\n"
    assert editor.getCursorPosition() == (1, 0)


def test_handle_return_dedents_parenthesized_return_expression(tmp_path):
    text = "    return(value)"
    editor, handler = make_handler(tmp_path, text=text, cursor=(0, len(text)))

    assert handler.handle_return() is True
    assert editor.all_text() == f"{text}\n"
    assert editor.getCursorPosition() == (1, 0)


def test_handle_return_preserves_incomplete_parenthesized_expression(tmp_path):
    text = "    return("
    editor, handler = make_handler(tmp_path, text=text, cursor=(0, len(text)))

    assert handler.handle_return() is False
    assert editor.all_text() == text


def test_handle_return_dedents_unindented_keyword_to_empty_indent(tmp_path):
    editor, handler = make_handler(tmp_path, text="return value", cursor=(0, 12))

    assert handler.handle_return() is True
    assert editor.all_text() == "return value\n"
    assert editor.getCursorPosition() == (1, 0)


def test_handle_return_ignores_incomplete_python_tokenization(tmp_path):
    text = 'value = """unfinished'
    editor, handler = make_handler(tmp_path, text=text, cursor=(0, len(text)))

    assert handler.handle_return() is False
    assert editor.all_text() == text


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


@pytest.mark.parametrize("text", ["if ready:", "    return value"])
def test_handle_return_leaves_selection_for_default_handler(tmp_path, text):
    cursor = (0, len(text))
    editor, handler = make_handler(tmp_path, text=text, cursor=cursor)
    editor.setSelection(0, 0, *cursor)

    assert handler.handle_return() is False
    assert editor.all_text() == text
    assert editor.getCursorPosition() == cursor
    assert editor.hasSelectedText() is True
    assert editor.selection == (0, 0, *cursor)


@pytest.mark.parametrize("text", ["if ready:", "    return value"])
@pytest.mark.parametrize("key", [Qt.Key.Key_Return, Qt.Key.Key_Enter])
def test_enter_replaces_selected_code(qapp, tmp_path, text, key):
    settings = Settings(tmp_path)
    settings.set("editor.smart_indent", True)
    settings.set("editor.auto_complete", False)
    editor = CodeEditor(settings)
    original = text + "\nkeep = 1"
    try:
        editor.setText(original)
        editor.setSelection(0, 0, 0, len(text))
        assert editor.selectedText() == text

        QTest.keyClick(editor, key)

        assert editor.text() == "\n\nkeep = 1"
        assert editor.getCursorPosition() == (1, 0)
        assert editor.hasSelectedText() is False
        editor.undo()
        assert editor.text() == original
    finally:
        editor.close()
        editor.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qapp.processEvents()

import pytest

from meadowpy.core.settings import Settings
from meadowpy.editor.auto_close import AutoCloseHandler
from tests.helpers import DummyEditor, DummyKeyEvent


def make_handler(tmp_path, text="", cursor=(0, 0), enabled=True):
    settings = Settings(tmp_path)
    settings.set("editor.auto_close_brackets", enabled)
    editor = DummyEditor(text)
    editor.setCursorPosition(*cursor)
    return editor, AutoCloseHandler(editor, settings)


def test_handle_key_returns_false_when_feature_disabled(tmp_path):
    editor, handler = make_handler(tmp_path, enabled=False)

    assert handler.handle_key(DummyKeyEvent("(")) is False
    assert editor.all_text() == ""


def test_handle_key_ignores_empty_text_and_selection(tmp_path):
    editor, handler = make_handler(tmp_path)

    assert handler.handle_key(DummyKeyEvent("")) is False
    assert editor.all_text() == ""

    editor.set_selected(True)
    assert handler.handle_key(DummyKeyEvent("(")) is False
    assert editor.all_text() == ""


def test_handle_key_inserts_matching_pair_for_openers(tmp_path):
    editor, handler = make_handler(tmp_path, text="value", cursor=(0, 5))

    assert handler.handle_key(DummyKeyEvent("(")) is True
    assert editor.all_text() == "value()"
    assert editor.getCursorPosition() == (0, 6)


def test_handle_key_skips_existing_closer(tmp_path):
    editor, handler = make_handler(tmp_path, text="()", cursor=(0, 1))

    assert handler.handle_key(DummyKeyEvent(")")) is True
    assert editor.all_text() == "()"
    assert editor.getCursorPosition() == (0, 2)


def test_handle_key_inserts_quote_pair_when_followed_by_whitespace(tmp_path):
    editor, handler = make_handler(tmp_path, text="name ", cursor=(0, 5))

    assert handler.handle_key(DummyKeyEvent('"')) is True
    assert editor.all_text() == 'name ""'
    assert editor.getCursorPosition() == (0, 6)


def test_handle_key_inserts_quote_pair_at_end_of_line(tmp_path):
    editor, handler = make_handler(tmp_path, text="name", cursor=(0, 4))

    assert handler.handle_key(DummyKeyEvent("'")) is True
    assert editor.all_text() == "name''"
    assert editor.getCursorPosition() == (0, 5)


def test_handle_key_does_not_pair_quote_before_word_character(tmp_path):
    editor, handler = make_handler(tmp_path, text="name=value", cursor=(0, 5))

    assert handler.handle_key(DummyKeyEvent('"')) is False
    assert editor.all_text() == "name=value"
    assert editor.getCursorPosition() == (0, 5)


def test_handle_key_skips_existing_closing_quote(tmp_path):
    editor, handler = make_handler(tmp_path, text='"x"', cursor=(0, 2))

    assert handler.handle_key(DummyKeyEvent('"')) is True
    assert editor.getCursorPosition() == (0, 3)


def test_handle_key_does_not_pair_closing_quote_in_open_string(tmp_path):
    text = 'print("hello'
    editor, handler = make_handler(tmp_path, text=text, cursor=(0, len(text)))

    assert handler.handle_key(DummyKeyEvent('"')) is False
    assert editor.all_text() == text


def test_handle_key_does_not_pair_closing_quote_before_closer(tmp_path):
    text = 'print("hello)'
    cursor_col = len('print("hello')
    editor, handler = make_handler(tmp_path, text=text, cursor=(0, cursor_col))

    assert handler.handle_key(DummyKeyEvent('"')) is False
    assert editor.all_text() == text
    assert editor.getCursorPosition() == (0, cursor_col)


@pytest.mark.parametrize("quote", ["'", '"'])
@pytest.mark.parametrize("backslashes", [1, 2, 3, 4])
def test_handle_key_counts_only_unescaped_quotes(tmp_path, quote, backslashes):
    text = quote + "hello" + "\\" * backslashes + quote + " + "
    editor, handler = make_handler(tmp_path, text=text, cursor=(0, len(text)))

    handled = handler.handle_key(DummyKeyEvent(quote))

    if backslashes % 2:
        assert handled is False
        assert editor.all_text() == text
        assert editor.getCursorPosition() == (0, len(text))
    else:
        assert handled is True
        assert editor.all_text() == text + quote * 2
        assert editor.getCursorPosition() == (0, len(text) + 1)


@pytest.mark.parametrize("quote", ["'", '"'])
def test_handle_key_skips_closing_quote_after_escaped_quote(tmp_path, quote):
    prefix = quote + "hello\\" + quote + " world"
    text = prefix + quote
    editor, handler = make_handler(tmp_path, text=text, cursor=(0, len(prefix)))

    assert handler.handle_key(DummyKeyEvent(quote)) is True
    assert editor.all_text() == text
    assert editor.getCursorPosition() == (0, len(prefix) + 1)


@pytest.mark.parametrize("quote", ["'", '"'])
@pytest.mark.parametrize("backslashes", [1, 2, 3, 4])
def test_handle_key_does_not_skip_an_escaped_quote(tmp_path, quote, backslashes):
    prefix = quote + "hello" + "\\" * backslashes
    text = prefix + quote
    editor, handler = make_handler(tmp_path, text=text, cursor=(0, len(prefix)))

    handled = handler.handle_key(DummyKeyEvent(quote))

    assert handled is (backslashes % 2 == 0)
    assert editor.all_text() == text
    expected_col = len(prefix) + (backslashes % 2 == 0)
    assert editor.getCursorPosition() == (0, expected_col)


def test_handle_backspace_removes_auto_inserted_pair(tmp_path):
    editor, handler = make_handler(tmp_path, text="()", cursor=(0, 1))

    assert handler.handle_backspace() is True
    assert editor.all_text() == ""
    assert editor.getCursorPosition() == (0, 0)


def test_handle_backspace_returns_false_when_feature_disabled(tmp_path):
    editor, handler = make_handler(tmp_path, text="()", cursor=(0, 1), enabled=False)

    assert handler.handle_backspace() is False
    assert editor.all_text() == "()"


def test_handle_backspace_ignores_start_and_out_of_range_cursor(tmp_path):
    editor, handler = make_handler(tmp_path, text="()", cursor=(0, 0))

    assert handler.handle_backspace() is False
    assert editor.all_text() == "()"

    editor.setCursorPosition(0, 3)
    assert handler.handle_backspace() is False
    assert editor.all_text() == "()"


def test_handle_backspace_ignores_non_pair_characters(tmp_path):
    editor, handler = make_handler(tmp_path, text="ab", cursor=(0, 1))

    assert handler.handle_backspace() is False
    assert editor.all_text() == "ab"


def test_handle_backspace_ignores_selected_text(tmp_path):
    editor, handler = make_handler(tmp_path, text="()", cursor=(0, 1))
    editor.set_selected(True)

    assert handler.handle_backspace() is False
    assert editor.all_text() == "()"

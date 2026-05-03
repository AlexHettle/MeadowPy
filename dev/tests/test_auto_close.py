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


def test_handle_key_skips_existing_closing_quote(tmp_path):
    editor, handler = make_handler(tmp_path, text='"x"', cursor=(0, 2))

    assert handler.handle_key(DummyKeyEvent('"')) is True
    assert editor.getCursorPosition() == (0, 3)


def test_handle_backspace_removes_auto_inserted_pair(tmp_path):
    editor, handler = make_handler(tmp_path, text="()", cursor=(0, 1))

    assert handler.handle_backspace() is True
    assert editor.all_text() == ""
    assert editor.getCursorPosition() == (0, 0)


def test_handle_backspace_ignores_selected_text(tmp_path):
    editor, handler = make_handler(tmp_path, text="()", cursor=(0, 1))
    editor.set_selected(True)

    assert handler.handle_backspace() is False
    assert editor.all_text() == "()"

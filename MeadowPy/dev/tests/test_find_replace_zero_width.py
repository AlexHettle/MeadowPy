"""Real-editor regressions for zero-width Replace All searches."""

from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QCoreApplication, QEvent
from PyQt6.Qsci import QsciScintilla
from PyQt6.QtWidgets import QMainWindow

from meadowpy.ui.find_replace_bar import FindReplaceBar


@pytest.mark.parametrize(
    "source, pattern, replacement, expected, count",
    [
        ("abc", "$", "!", "abc!", 1),
        ("abc\n", "$", "!", "abc!\n", 1),
        ("a\nb", "$", "!", "a!\nb!", 2),
        ("a\r\nb", "$", "!", "a!\r\nb!", 2),
        ("abc\n", "$", "", "abc\n", 1),
        ("ab", "x*", "X", "XaXb", 2),
        ("ab", "x*", "", "ab", 2),
        ("é😀", "x*", "X", "XéX😀", 2),
        ("ab", "x*", "xx", "xxaxxb", 2),
        ("ab", r"\(x*\)", r"<\1>", "<>a<>b", 2),
        ("a\nb", "^", "!", "!a\n!b", 2),
        ("aba", r"\(a\)", r"<\1>", "<a>b<a>", 2),
    ],
)
def test_replace_all_advances_past_zero_width_matches(
    qapp, monkeypatch, source, pattern, replacement, expected, count
):
    editor = QsciScintilla()
    editor.setUtf8(True)
    window = QMainWindow()
    window.setCentralWidget(editor)
    window._tab_manager = SimpleNamespace(current_editor=lambda: editor)
    bar = FindReplaceBar(window)
    replacements = 0
    original_replace = editor.replace

    def bounded_replace(text):
        nonlocal replacements
        replacements += 1
        # Fail the regression promptly rather than letting the GUI loop hang.
        assert replacements <= count, (
            "Replace All revisited a zero-width match"
        )
        original_replace(text)

    monkeypatch.setattr(editor, "replace", bounded_replace)
    try:
        editor.setText(source)
        editor.SendScintilla(editor.SCI_EMPTYUNDOBUFFER)
        bar._regex_btn.setChecked(True)
        bar._find_input.setText(pattern)
        bar._replace_input.setText(replacement)

        bar.replace_all()

        assert editor.text() == expected
        assert replacements == count
        assert bar._match_label.text() == f"{count} replaced"
        if expected != source:
            editor.undo()
            assert editor.text() == source
            assert not editor.isUndoAvailable()
            editor.redo()
            assert editor.text() == expected
    finally:
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qapp.processEvents()


@pytest.mark.parametrize("pattern", ["$", "x*"])
def test_native_search_does_not_match_an_empty_eof_range(qapp, pattern):
    """Keep native search semantics rather than adding Python-regex matches."""
    editor = QsciScintilla()
    try:
        editor.setText("ab")
        assert not editor.findFirst(
            pattern, True, True, False, False, True, 0, 2
        )
    finally:
        editor.close()
        editor.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qapp.processEvents()

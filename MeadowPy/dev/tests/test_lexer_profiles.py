import pytest
from PyQt6.QtGui import QColor, QFont
from PyQt6.Qsci import QsciLexerJSON, QsciLexerYAML

from meadowpy.core.file_types import SyntaxLanguage
from meadowpy.editor.lexer_profiles import (
    apply_lexer_theme,
    create_configured_lexer,
    create_lexer,
)
from meadowpy.editor.themes import DEFAULT_DARK


def test_unsupported_language_has_no_native_lexer_and_rejects_theming():
    font = QFont("Consolas", 12)

    assert create_lexer(SyntaxLanguage.PLAIN) is None
    assert (
        create_configured_lexer(
            SyntaxLanguage.PLAIN,
            None,
            DEFAULT_DARK,
            font,
        )
        is None
    )
    with pytest.raises(ValueError, match="No native lexer profile"):
        apply_lexer_theme(
            object(),
            SyntaxLanguage.PLAIN,
            DEFAULT_DARK,
            font,
        )


def test_apply_lexer_theme_rejects_the_wrong_lexer_type(qapp):
    lexer = QsciLexerYAML()

    with pytest.raises(
        TypeError,
        match="requires QsciLexerJSON, not QsciLexerYAML",
    ):
        apply_lexer_theme(
            lexer,
            SyntaxLanguage.JSON,
            DEFAULT_DARK,
            QFont("Consolas", 12),
        )

    lexer.deleteLater()


def test_create_configured_lexer_applies_theme_and_font(qapp):
    font = QFont("Consolas", 13)

    lexer = create_configured_lexer(
        SyntaxLanguage.JSON,
        None,
        DEFAULT_DARK,
        font,
    )

    assert isinstance(lexer, QsciLexerJSON)
    assert lexer.defaultColor(QsciLexerJSON.Default).name() == QColor(
        DEFAULT_DARK.editor_foreground
    ).name()
    assert lexer.defaultPaper(QsciLexerJSON.Default).name() == QColor(
        DEFAULT_DARK.editor_background
    ).name()
    assert lexer.font(QsciLexerJSON.Keyword).family() == font.family()
    assert lexer.paper(QsciLexerJSON.Keyword).name() == QColor(
        DEFAULT_DARK.editor_background
    ).name()
    lexer.deleteLater()

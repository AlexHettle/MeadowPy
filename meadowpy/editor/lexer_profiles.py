"""Native QScintilla profiles for supported non-Python languages."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import cast

from PyQt6.QtCore import QObject
from PyQt6.QtGui import QColor, QFont
from PyQt6.Qsci import (
    QsciLexer,
    QsciLexerJSON,
    QsciLexerMarkdown,
    QsciLexerProperties,
    QsciLexerYAML,
)

from meadowpy.core.file_types import SyntaxLanguage
from meadowpy.editor.themes import EditorTheme, TokenColorRole


@dataclass(frozen=True)
class FontTraits:
    """Font traits layered on top of the user's editor font."""

    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike_out: bool = False


LexerConfigurator = Callable[[QsciLexer], None]


@dataclass(frozen=True)
class LexerProfile:
    """Declarative styling and setup for one native QScintilla lexer."""

    lexer_type: type[QsciLexer]
    style_roles: Mapping[int, TokenColorRole]
    font_traits: Mapping[int, FontTraits] = field(default_factory=dict)
    configure: LexerConfigurator | None = None


def _configure_json(base_lexer: QsciLexer) -> None:
    lexer = cast(QsciLexerJSON, base_lexer)
    # `.json` is strict JSON. Invalid JSON comments should not be accepted as
    # ordinary comment syntax, while escape sequences remain distinguishable.
    lexer.setHighlightComments(False)
    lexer.setHighlightEscapeSequences(True)
    lexer.setFoldCompact(True)


def _configure_yaml(base_lexer: QsciLexer) -> None:
    lexer = cast(QsciLexerYAML, base_lexer)
    lexer.setFoldComments(False)


def _configure_properties(base_lexer: QsciLexer) -> None:
    lexer = cast(QsciLexerProperties, base_lexer)
    lexer.setFoldCompact(True)
    # Keep initial spaces at their enabled default. QScintilla 2.14.1's
    # setInitialSpaces() property emitter incorrectly reads foldCompact().


JSON_PROFILE = LexerProfile(
    lexer_type=QsciLexerJSON,
    style_roles={
        QsciLexerJSON.Default: TokenColorRole.DEFAULT,
        QsciLexerJSON.Number: TokenColorRole.NUMBER,
        QsciLexerJSON.String: TokenColorRole.STRING,
        QsciLexerJSON.UnclosedString: TokenColorRole.ERROR,
        QsciLexerJSON.Property: TokenColorRole.NAME,
        QsciLexerJSON.EscapeSequence: TokenColorRole.SPECIAL,
        QsciLexerJSON.CommentLine: TokenColorRole.COMMENT,
        QsciLexerJSON.CommentBlock: TokenColorRole.COMMENT,
        QsciLexerJSON.Operator: TokenColorRole.OPERATOR,
        QsciLexerJSON.IRI: TokenColorRole.STRING,
        QsciLexerJSON.IRICompact: TokenColorRole.NAME,
        QsciLexerJSON.Keyword: TokenColorRole.KEYWORD,
        QsciLexerJSON.KeywordLD: TokenColorRole.SPECIAL,
        QsciLexerJSON.Error: TokenColorRole.ERROR,
    },
    font_traits={
        QsciLexerJSON.CommentLine: FontTraits(italic=True),
        QsciLexerJSON.Keyword: FontTraits(bold=True),
    },
    configure=_configure_json,
)


MARKDOWN_PROFILE = LexerProfile(
    lexer_type=QsciLexerMarkdown,
    style_roles={
        QsciLexerMarkdown.Default: TokenColorRole.DEFAULT,
        QsciLexerMarkdown.Special: TokenColorRole.SPECIAL,
        QsciLexerMarkdown.StrongEmphasisAsterisks: TokenColorRole.DEFAULT,
        QsciLexerMarkdown.StrongEmphasisUnderscores: TokenColorRole.DEFAULT,
        QsciLexerMarkdown.EmphasisAsterisks: TokenColorRole.DEFAULT,
        QsciLexerMarkdown.EmphasisUnderscores: TokenColorRole.DEFAULT,
        QsciLexerMarkdown.Header1: TokenColorRole.KEYWORD,
        QsciLexerMarkdown.Header2: TokenColorRole.KEYWORD,
        QsciLexerMarkdown.Header3: TokenColorRole.KEYWORD,
        QsciLexerMarkdown.Header4: TokenColorRole.KEYWORD,
        QsciLexerMarkdown.Header5: TokenColorRole.KEYWORD,
        QsciLexerMarkdown.Header6: TokenColorRole.KEYWORD,
        QsciLexerMarkdown.Prechar: TokenColorRole.COMMENT,
        QsciLexerMarkdown.UnorderedListItem: TokenColorRole.SPECIAL,
        QsciLexerMarkdown.OrderedListItem: TokenColorRole.SPECIAL,
        QsciLexerMarkdown.BlockQuote: TokenColorRole.COMMENT,
        QsciLexerMarkdown.StrikeOut: TokenColorRole.COMMENT,
        QsciLexerMarkdown.HorizontalRule: TokenColorRole.OPERATOR,
        QsciLexerMarkdown.Link: TokenColorRole.NAME,
        QsciLexerMarkdown.CodeBackticks: TokenColorRole.STRING,
        QsciLexerMarkdown.CodeDoubleBackticks: TokenColorRole.STRING,
        QsciLexerMarkdown.CodeBlock: TokenColorRole.STRING,
    },
    font_traits={
        QsciLexerMarkdown.StrongEmphasisAsterisks: FontTraits(bold=True),
        QsciLexerMarkdown.StrongEmphasisUnderscores: FontTraits(bold=True),
        QsciLexerMarkdown.EmphasisAsterisks: FontTraits(italic=True),
        QsciLexerMarkdown.EmphasisUnderscores: FontTraits(italic=True),
        QsciLexerMarkdown.Header1: FontTraits(bold=True),
        QsciLexerMarkdown.Header2: FontTraits(bold=True),
        QsciLexerMarkdown.Header3: FontTraits(bold=True),
        QsciLexerMarkdown.Header4: FontTraits(bold=True),
        QsciLexerMarkdown.Header5: FontTraits(bold=True),
        QsciLexerMarkdown.Header6: FontTraits(bold=True),
        QsciLexerMarkdown.StrikeOut: FontTraits(strike_out=True),
        QsciLexerMarkdown.Link: FontTraits(underline=True),
    },
)


YAML_PROFILE = LexerProfile(
    lexer_type=QsciLexerYAML,
    style_roles={
        QsciLexerYAML.Default: TokenColorRole.DEFAULT,
        QsciLexerYAML.Comment: TokenColorRole.COMMENT,
        QsciLexerYAML.Identifier: TokenColorRole.NAME,
        QsciLexerYAML.Keyword: TokenColorRole.KEYWORD,
        QsciLexerYAML.Number: TokenColorRole.NUMBER,
        QsciLexerYAML.Reference: TokenColorRole.SPECIAL,
        QsciLexerYAML.DocumentDelimiter: TokenColorRole.OPERATOR,
        QsciLexerYAML.TextBlockMarker: TokenColorRole.OPERATOR,
        QsciLexerYAML.SyntaxErrorMarker: TokenColorRole.ERROR,
        QsciLexerYAML.Operator: TokenColorRole.OPERATOR,
    },
    font_traits={
        QsciLexerYAML.Identifier: FontTraits(bold=True),
        QsciLexerYAML.DocumentDelimiter: FontTraits(bold=True),
        QsciLexerYAML.SyntaxErrorMarker: FontTraits(bold=True, italic=True),
    },
    configure=_configure_yaml,
)


PROPERTIES_PROFILE = LexerProfile(
    lexer_type=QsciLexerProperties,
    style_roles={
        QsciLexerProperties.Default: TokenColorRole.DEFAULT,
        QsciLexerProperties.Comment: TokenColorRole.COMMENT,
        QsciLexerProperties.Section: TokenColorRole.NAME,
        QsciLexerProperties.Assignment: TokenColorRole.OPERATOR,
        QsciLexerProperties.DefaultValue: TokenColorRole.STRING,
        QsciLexerProperties.Key: TokenColorRole.NAME,
    },
    configure=_configure_properties,
)


LEXER_PROFILES: Mapping[SyntaxLanguage, LexerProfile] = {
    SyntaxLanguage.JSON: JSON_PROFILE,
    SyntaxLanguage.MARKDOWN: MARKDOWN_PROFILE,
    SyntaxLanguage.YAML: YAML_PROFILE,
    SyntaxLanguage.PROPERTIES: PROPERTIES_PROFILE,
}


def get_lexer_profile(language: SyntaxLanguage) -> LexerProfile | None:
    """Return the native non-Python profile for ``language``, if any."""
    return LEXER_PROFILES.get(language)


def create_lexer(
    language: SyntaxLanguage,
    parent: QObject | None = None,
) -> QsciLexer | None:
    """Create and configure the native lexer for ``language``."""
    profile = get_lexer_profile(language)
    if profile is None:
        return None

    lexer = profile.lexer_type(parent)
    if profile.configure is not None:
        profile.configure(lexer)
    return lexer


def apply_lexer_theme(
    lexer: QsciLexer,
    language: SyntaxLanguage,
    theme: EditorTheme,
    font: QFont,
) -> None:
    """Apply semantic colors, uniform paper, and font traits to ``lexer``."""
    profile = get_lexer_profile(language)
    if profile is None:
        raise ValueError(f"No native lexer profile for {language!r}")
    if not isinstance(lexer, profile.lexer_type):
        raise TypeError(
            f"{language!r} requires {profile.lexer_type.__name__}, "
            f"not {type(lexer).__name__}"
        )

    background = QColor(theme.editor_background)
    lexer.setDefaultColor(QColor(theme.editor_foreground))
    lexer.setDefaultPaper(background)
    lexer.setDefaultFont(font)

    for style_id, role in profile.style_roles.items():
        lexer.setColor(QColor(theme.token_color(role)), style_id)
        # QScintilla has several legacy per-style pastel and error papers.
        # Setting every native style prevents those from leaking into dark or
        # high-contrast themes.
        lexer.setPaper(background, style_id)

        traits = profile.font_traits.get(style_id, FontTraits())
        style_font = QFont(font)
        style_font.setBold(traits.bold)
        style_font.setItalic(traits.italic)
        style_font.setUnderline(traits.underline)
        style_font.setStrikeOut(traits.strike_out)
        lexer.setFont(style_font, style_id)


def create_configured_lexer(
    language: SyntaxLanguage,
    parent: QObject | None,
    theme: EditorTheme,
    font: QFont,
) -> QsciLexer | None:
    """Create a native non-Python lexer and apply its complete profile."""
    lexer = create_lexer(language, parent)
    if lexer is not None:
        apply_lexer_theme(lexer, language, theme, font)
    return lexer

"""Applies settings to a CodeEditor instance."""

import builtins

from PyQt6.QtGui import QColor, QFont
from PyQt6.Qsci import QsciScintilla, QsciLexerPython

from meadowpy.core.settings import Settings
from meadowpy.editor.themes import get_theme


class EditorConfigurator:
    """Applies a Settings object to a CodeEditor widget."""

    @staticmethod
    def apply(editor: QsciScintilla, settings: Settings) -> None:
        """Apply all settings to the given editor instance."""
        EditorConfigurator._apply_font(editor, settings)
        EditorConfigurator._apply_indentation(editor, settings)
        EditorConfigurator._apply_caret(editor, settings)
        EditorConfigurator._apply_brace_matching(editor, settings)
        EditorConfigurator._apply_word_wrap(editor, settings)
        EditorConfigurator._apply_lexer(editor, settings)
        EditorConfigurator._apply_autocompletion(editor, settings)
        EditorConfigurator._apply_margins(editor, settings)
        EditorConfigurator._apply_breakpoint_margin(editor, settings)
        EditorConfigurator._apply_folding(editor, settings)
        EditorConfigurator._apply_general(editor, settings)

    @staticmethod
    def _apply_font(editor: QsciScintilla, settings: Settings) -> None:
        font = QFont(
            settings.get("editor.font_family"),
            settings.get("editor.font_size"),
        )
        font.setFixedPitch(True)
        editor.setFont(font)
        editor.setMarginsFont(font)

    @staticmethod
    def _apply_indentation(editor: QsciScintilla, settings: Settings) -> None:
        editor.setIndentationWidth(settings.get("editor.tab_width"))
        editor.setIndentationsUseTabs(not settings.get("editor.use_spaces"))
        editor.setAutoIndent(settings.get("editor.auto_indent"))
        editor.setTabIndents(True)
        editor.setBackspaceUnindents(True)
        editor.setIndentationGuides(settings.get("editor.show_indentation_guides"))

    @staticmethod
    def _apply_caret(editor: QsciScintilla, settings: Settings) -> None:
        theme = get_theme(
            settings.get("editor.theme"),
            custom_base=settings.get("editor.custom_theme.base"),
        )
        editor.setCaretLineVisible(settings.get("editor.highlight_current_line"))
        editor.setCaretLineBackgroundColor(QColor(theme.caret_line_background))
        editor.setCaretWidth(2)
        editor.setCaretForegroundColor(QColor(theme.editor_foreground))

    @staticmethod
    def _apply_brace_matching(editor: QsciScintilla, settings: Settings) -> None:
        if settings.get("editor.brace_matching"):
            editor.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)
        else:
            editor.setBraceMatching(QsciScintilla.BraceMatch.NoBraceMatch)

    @staticmethod
    def _apply_word_wrap(editor: QsciScintilla, settings: Settings) -> None:
        if settings.get("editor.word_wrap"):
            editor.setWrapMode(QsciScintilla.WrapMode.WrapWord)
        else:
            editor.setWrapMode(QsciScintilla.WrapMode.WrapNone)

    @staticmethod
    def _apply_margins(editor: QsciScintilla, settings: Settings) -> None:
        theme = get_theme(
            settings.get("editor.theme"),
            custom_base=settings.get("editor.custom_theme.base"),
        )

        if settings.get("editor.show_line_numbers"):
            editor.setMarginType(0, QsciScintilla.MarginType.NumberMargin)
            line_count = max(editor.lines(), 1)
            width = max(len(str(line_count)) + 1, 4)
            editor.setMarginWidth(0, "0" * width)
            editor.setMarginLineNumbers(0, True)
        else:
            editor.setMarginWidth(0, 0)
            editor.setMarginLineNumbers(0, False)

        editor.setMarginsBackgroundColor(QColor(theme.margin_background))
        editor.setMarginsForegroundColor(QColor(theme.margin_foreground))

    @staticmethod
    def _apply_lexer(editor: QsciScintilla, settings: Settings) -> None:
        theme = get_theme(
            settings.get("editor.theme"),
            custom_base=settings.get("editor.custom_theme.base"),
        )

        lexer = QsciLexerPython(editor)
        lexer.setDefaultFont(editor.font())

        # Apply theme colors
        for style_id, color in theme.foreground_colors.items():
            lexer.setColor(QColor(color), style_id)

        for style_id, color in theme.background_colors.items():
            lexer.setPaper(QColor(color), style_id)

        # Set default background for all styles
        lexer.setDefaultPaper(QColor(theme.editor_background))
        lexer.setDefaultColor(QColor(theme.editor_foreground))

        # Set paper for all defined styles to match editor background
        for style_id in theme.foreground_colors:
            lexer.setPaper(QColor(theme.editor_background), style_id)

        editor.setLexer(lexer)

        # Force the same font on ALL styles (setLexer resets per-style fonts)
        font = editor.font()
        for style_id in range(128):
            lexer.setFont(font, style_id)

        # Add Python built-in names as keyword set 2 for HighlightedIdentifier
        builtin_names = " ".join(dir(builtins))
        editor.SendScintilla(editor.SCI_SETKEYWORDS, 1, builtin_names.encode())

    @staticmethod
    def _apply_autocompletion(editor: QsciScintilla, settings: Settings) -> None:
        """Configure auto-completion using QsciAPIs."""
        if settings.get("editor.auto_complete"):
            from meadowpy.editor.completion import create_apis

            editor.setAutoCompletionSource(
                QsciScintilla.AutoCompletionSource.AcsAPIs
            )
            editor.setAutoCompletionThreshold(
                settings.get("editor.auto_complete_threshold")
            )
            editor.setAutoCompletionCaseSensitivity(False)
            editor.setAutoCompletionReplaceWord(True)
            editor.setAutoCompletionUseSingle(
                QsciScintilla.AutoCompletionUseSingle.AcusNever
            )
            # Create APIs object attached to the lexer
            lexer = editor.lexer()
            if lexer:
                apis = create_apis(lexer)
                # Store reference to prevent garbage collection
                editor._completion_apis = apis
        else:
            editor.setAutoCompletionSource(
                QsciScintilla.AutoCompletionSource.AcsNone
            )

    @staticmethod
    def _apply_breakpoint_margin(editor: QsciScintilla, settings: Settings) -> None:
        """Configure margin 2 as the breakpoint gutter."""
        theme = get_theme(
            settings.get("editor.theme"),
            custom_base=settings.get("editor.custom_theme.base"),
        )

        # Margin 2: narrow symbol margin for breakpoint dots
        editor.setMarginType(2, QsciScintilla.MarginType.SymbolMargin)
        editor.setMarginWidth(2, 14)
        editor.setMarginSensitivity(2, True)

        # Show breakpoint + current-line markers in this margin
        from meadowpy.editor.code_editor import MARKER_BREAKPOINT, MARKER_CURRENT_LINE
        editor.setMarginMarkerMask(
            2, (1 << MARKER_BREAKPOINT) | (1 << MARKER_CURRENT_LINE)
        )

        # Match margin background to theme
        editor.setMarginBackgroundColor(2, QColor(theme.margin_background))

        # Also make line-number margin (0) clickable to toggle breakpoints
        editor.setMarginSensitivity(0, True)

    @staticmethod
    def _apply_folding(editor: QsciScintilla, settings: Settings) -> None:
        theme = get_theme(
            settings.get("editor.theme"),
            custom_base=settings.get("editor.custom_theme.base"),
        )

        if settings.get("editor.code_folding"):
            editor.setFolding(QsciScintilla.FoldStyle.BoxedTreeFoldStyle, 1)
        else:
            editor.setFolding(QsciScintilla.FoldStyle.NoFoldStyle)

        editor.setFoldMarginColors(
            QColor(theme.fold_margin_background),
            QColor(theme.fold_margin_background),
        )

    @staticmethod
    def _apply_general(editor: QsciScintilla, settings: Settings) -> None:
        editor.setEolMode(QsciScintilla.EolMode.EolUnix)
        editor.setEolVisibility(False)
        editor.setUtf8(True)

        # Whitespace visibility (tabs + spaces)
        if settings.get("editor.show_whitespace"):
            editor.setWhitespaceVisibility(
                QsciScintilla.WhitespaceVisibility.WsVisible
            )
        else:
            editor.setWhitespaceVisibility(
                QsciScintilla.WhitespaceVisibility.WsInvisible
            )

"""Applies settings to a CodeEditor instance."""

import builtins

from PyQt6.QtGui import QColor, QFont
from PyQt6.Qsci import QsciScintilla, QsciLexerPython

from meadowpy.core.settings import Settings
from meadowpy.editor.themes import get_theme
from meadowpy.resources.resource_loader import current_accent_hex, theme_is_dark


class EditorConfigurator:
    """Applies a Settings object to a CodeEditor widget."""

    @staticmethod
    def apply(editor: QsciScintilla, settings: Settings) -> None:
        """Apply all settings to the given editor instance."""
        EditorConfigurator._apply_font(editor, settings)
        EditorConfigurator._apply_indentation(editor, settings)
        EditorConfigurator._apply_caret(editor, settings)
        EditorConfigurator._apply_selection(editor, settings)
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
    def _apply_selection(editor: QsciScintilla, settings: Settings) -> None:
        """Paint text selections in the current accent color."""
        theme_name = settings.get("editor.theme")
        custom_base = settings.get("editor.custom_theme.base")
        accent = current_accent_hex(
            theme_name,
            custom_base,
            settings.get("editor.custom_theme.accent"),
        )
        editor.setSelectionBackgroundColor(QColor(accent))
        # Selection foreground must contrast with the accent background.
        # In HC mode the accent is white, so flip the selected text to black.
        sel_fg = "#000000" if theme_name == "default_high_contrast" else "#FFFFFF"
        editor.setSelectionForegroundColor(QColor(sel_fg))

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

        # In HC mode the entire editor must be monochrome — but QsciLexerPython
        # has style IDs beyond what theme.foreground_colors covers (e.g. f-string
        # styles 16-19), and those keep their default purple/orange tints unless
        # we force-paint every slot. So in HC, override all 128 possible styles
        # to the theme's foreground/background.
        if settings.get("editor.theme") == "default_high_contrast":
            fg = QColor(theme.editor_foreground)
            bg = QColor(theme.editor_background)
            for style_id in range(128):
                lexer.setColor(fg, style_id)
                lexer.setPaper(bg, style_id)

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
        """Apply V2 fold margin styling.

        Replaces the default boxed-tree +/− with a clean circled style
        tinted in the current accent color, matching the rounded panel
        chrome used elsewhere in the IDE. The fold margin and the tree
        connector lines blend into the editor background so only the
        accent-colored circle reads as interactive.
        """
        theme_name = settings.get("editor.theme")
        custom_base = settings.get("editor.custom_theme.base")
        theme = get_theme(theme_name, custom_base=custom_base)

        if settings.get("editor.code_folding"):
            # Circled + tree style: rounded ⊕ / ⊖ markers with the
            # vertical connector lines that show fold hierarchy.
            editor.setFolding(QsciScintilla.FoldStyle.CircledTreeFoldStyle, 1)
        else:
            editor.setFolding(QsciScintilla.FoldStyle.NoFoldStyle)

        editor.setFoldMarginColors(
            QColor(theme.fold_margin_background),
            QColor(theme.fold_margin_background),
        )

        # Tint the fold markers with the current accent color.
        # QScintilla uses marker numbers 25–31 for fold indicators:
        #   25 SC_MARKNUM_FOLDERMIDTAIL   (T-junction connector)
        #   26 SC_MARKNUM_FOLDEREND       (end bump, in tree styles)
        #   27 SC_MARKNUM_FOLDEROPENMID   (mid expanded, tree styles)
        #   28 SC_MARKNUM_FOLDERTAIL      (corner connector)
        #   29 SC_MARKNUM_FOLDERSUB       (vertical connector)
        #   30 SC_MARKNUM_FOLDER          (collapsed ⊕)
        #   31 SC_MARKNUM_FOLDEROPEN      (expanded ⊖)
        accent = current_accent_hex(
            theme_name,
            custom_base,
            settings.get("editor.custom_theme.accent"),
        )
        is_dark = theme_is_dark(theme_name, custom_base)
        margin_bg = QColor(theme.fold_margin_background)
        accent_color = QColor(accent)
        # Foreground (the +/− glyph and the circle outline): accent.
        # Background (the circle fill): panel bg so the outline pops.
        for marker in (30, 31):   # FOLDER, FOLDEROPEN
            editor.setMarkerForegroundColor(accent_color, marker)
            editor.setMarkerBackgroundColor(margin_bg, marker)
        # Connector lines (tree styles) — neutralize them so only the
        # circles read. CircledFoldStyle doesn't draw them, but setting
        # colors is harmless and keeps other styles clean if switched.
        connector_color = QColor("#6B6B6B" if is_dark else "#B0B3B8")
        for marker in (25, 26, 27, 28, 29):
            editor.setMarkerForegroundColor(connector_color, marker)
            editor.setMarkerBackgroundColor(margin_bg, marker)

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

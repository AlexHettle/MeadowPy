"""Applies settings to a CodeEditor instance."""

import builtins
import keyword

from PyQt6.QtGui import QColor, QFont
from PyQt6.Qsci import QsciLexer, QsciLexerPython, QsciScintilla

from meadowpy.core.file_types import (
    SyntaxLanguage,
    is_python_file_path,
    syntax_language_for_path,
)
from meadowpy.core.settings import Settings
from meadowpy.editor.editor_fonts import editor_font_family
from meadowpy.editor.lexer_profiles import (
    apply_lexer_theme,
    create_lexer,
    get_lexer_profile,
)
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
        EditorConfigurator._apply_indentation_guides(editor, settings)
        EditorConfigurator._apply_autocompletion(editor, settings)
        EditorConfigurator._apply_margins(editor, settings)
        EditorConfigurator._apply_breakpoint_margin(editor, settings)
        EditorConfigurator._apply_folding(editor, settings)
        EditorConfigurator._apply_general(editor, settings)

    @staticmethod
    def _apply_font(editor: QsciScintilla, settings: Settings) -> None:
        font = QFont(
            editor_font_family(settings.get("editor.font_family")),
            settings.get("editor.font_size"),
        )
        font.setFixedPitch(True)
        EditorConfigurator._apply_editor_font_stylesheet(editor, font)
        editor.setFont(font)
        editor.setMarginsFont(font)
        try:
            editor.SendScintilla(
                QsciScintilla.SCI_STYLESETFONT,
                QsciScintilla.STYLE_DEFAULT,
                font.family().encode("utf-8"),
            )
            editor.SendScintilla(
                QsciScintilla.SCI_STYLESETSIZE,
                QsciScintilla.STYLE_DEFAULT,
                font.pointSize(),
            )
            editor.SendScintilla(QsciScintilla.SCI_STYLECLEARALL)
        except (AttributeError, TypeError, RuntimeError):
            pass

    @staticmethod
    def _apply_editor_font_stylesheet(editor: QsciScintilla, font: QFont) -> None:
        """Keep the global app QSS font rule from overriding editor text."""
        family = font.family().replace("\\", "\\\\").replace('"', '\\"')
        size = max(font.pointSize(), 1)
        editor.setStyleSheet(
            "QsciScintilla#codeEditor { "
            f'font-family: "{family}"; '
            f"font-size: {size}pt; "
            "}"
        )
        style = editor.style()
        style.unpolish(editor)
        style.polish(editor)
        editor.ensurePolished()

    @staticmethod
    def _apply_indentation(editor: QsciScintilla, settings: Settings) -> None:
        editor.setIndentationWidth(settings.get("editor.tab_width"))
        editor.setIndentationsUseTabs(not settings.get("editor.use_spaces"))
        editor.setAutoIndent(settings.get("editor.auto_indent"))
        editor.setTabIndents(True)
        editor.setBackspaceUnindents(True)

    @staticmethod
    def _apply_indentation_guides(
        editor: QsciScintilla, settings: Settings
    ) -> None:
        """Disable Scintilla's dotted guides; CodeEditor paints solid ones."""
        editor.setIndentationGuides(False)

        SCI_SETINDENTATIONGUIDES = 2132
        SC_IV_NONE = 0
        editor.SendScintilla(SCI_SETINDENTATIONGUIDES, SC_IV_NONE)

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

        language = syntax_language_for_path(
            getattr(editor, "file_path", None)
        )
        if language == SyntaxLanguage.PLAIN:
            EditorConfigurator._install_lexer(
                editor,
                None,
                SyntaxLanguage.PLAIN,
            )
            EditorConfigurator._apply_plain_text_style(editor, settings)
            return

        if language != SyntaxLanguage.PYTHON:
            profile = get_lexer_profile(language)
            if profile is None:
                EditorConfigurator._install_lexer(
                    editor,
                    None,
                    SyntaxLanguage.PLAIN,
                )
                EditorConfigurator._apply_plain_text_style(editor, settings)
                return

            lexer = editor.lexer()
            if not (
                getattr(editor, "_syntax_language", None) == language
                and isinstance(lexer, profile.lexer_type)
            ):
                lexer = create_lexer(language, editor)
                EditorConfigurator._install_lexer(
                    editor,
                    lexer,
                    language,
                )

            if lexer is not None:
                apply_lexer_theme(
                    lexer,
                    language,
                    theme,
                    editor.font(),
                )
                EditorConfigurator._colorise(editor)
            return

        lexer = editor.lexer()
        if not (
            getattr(editor, "_syntax_language", None)
            == SyntaxLanguage.PYTHON
            and isinstance(lexer, QsciLexerPython)
        ):
            lexer = QsciLexerPython(editor)
            EditorConfigurator._install_lexer(
                editor,
                lexer,
                SyntaxLanguage.PYTHON,
            )

        if not isinstance(lexer, QsciLexerPython):
            return
        lexer.setDefaultFont(editor.font())
        # Keyword set 2 is also used for Python built-ins.  Do not highlight
        # matching attribute names (for example ``path.open``) as though they
        # referred to the global built-in.
        lexer.setHighlightSubidentifiers(False)

        # Reset every slot before applying the palette. This prevents colors
        # from a previous theme surviving on less-common Python styles.
        font = editor.font()
        foreground = QColor(theme.editor_foreground)
        background = QColor(theme.editor_background)
        lexer.setDefaultColor(foreground)
        lexer.setDefaultPaper(background)
        for style_id in range(128):
            lexer.setColor(foreground, style_id)
            lexer.setPaper(background, style_id)
            lexer.setFont(font, style_id)

        for style_id, color in theme.foreground_colors.items():
            lexer.setColor(QColor(color), style_id)

        for style_id, color in theme.background_colors.items():
            lexer.setPaper(QColor(color), style_id)

        # QScintilla 2.14.1 ships a Python-2-era primary keyword list.  Replace
        # it with the hard keywords from the running Python so modern syntax
        # such as ``async``, ``await`` and ``nonlocal`` is styled correctly.
        # Contextual soft keywords stay excluded because this word-list lexer
        # cannot distinguish their valid identifier uses.
        keyword_names = " ".join(keyword.kwlist)
        editor.SendScintilla(editor.SCI_SETKEYWORDS, 0, keyword_names.encode())

        # Add Python built-in names as keyword set 2 for HighlightedIdentifier.
        # Hard keywords such as False, None and True belong exclusively to set
        # 1 so their classification cannot depend on keyword-list precedence.
        builtin_names = " ".join(
            name for name in dir(builtins) if not keyword.iskeyword(name)
        )
        editor.SendScintilla(editor.SCI_SETKEYWORDS, 1, builtin_names.encode())
        EditorConfigurator._colorise(editor)

    @staticmethod
    def _install_lexer(
        editor: QsciScintilla,
        lexer: QsciLexer | None,
        language: SyntaxLanguage,
    ) -> None:
        """Install ``lexer`` and release the previous editor-owned lexer."""
        previous = editor.lexer()
        if previous is lexer:
            editor._syntax_language = language
            return

        owns_previous = (
            previous is not None and previous.parent() is editor
        )
        editor.setLexer(lexer)
        editor._syntax_language = language
        if owns_previous:
            previous.deleteLater()

    @staticmethod
    def _colorise(editor: QsciScintilla) -> None:
        try:
            editor.SendScintilla(QsciScintilla.SCI_COLOURISE, 0, -1)
        except (AttributeError, TypeError, RuntimeError):
            pass

    @staticmethod
    def _apply_autocompletion(editor: QsciScintilla, settings: Settings) -> None:
        """Configure auto-completion using QsciAPIs."""
        if not EditorConfigurator._editor_uses_python_mode(editor):
            editor.setAutoCompletionSource(
                QsciScintilla.AutoCompletionSource.AcsNone
            )
            EditorConfigurator._clear_completion_apis(editor)
        elif settings.get("editor.auto_complete"):
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
            if lexer and not (
                getattr(editor, "_completion_lexer", None) is lexer
                and hasattr(editor, "_completion_apis")
            ):
                EditorConfigurator._clear_completion_apis(editor)
                apis = create_apis(lexer)
                # Store reference to prevent garbage collection
                editor._completion_apis = apis
                editor._completion_lexer = lexer
        else:
            editor.setAutoCompletionSource(
                QsciScintilla.AutoCompletionSource.AcsNone
            )
            EditorConfigurator._clear_completion_apis(editor)

    @staticmethod
    def _clear_completion_apis(editor: QsciScintilla) -> None:
        apis = getattr(editor, "_completion_apis", None)
        if apis is not None:
            try:
                apis.deleteLater()
            except (AttributeError, RuntimeError):
                pass
        for attribute in ("_completion_apis", "_completion_lexer"):
            if hasattr(editor, attribute):
                delattr(editor, attribute)

    @staticmethod
    def _editor_uses_python_mode(editor: QsciScintilla) -> bool:
        return is_python_file_path(getattr(editor, "file_path", None))

    @staticmethod
    def _scintilla_color(color: QColor) -> int:
        return color.red() | (color.green() << 8) | (color.blue() << 16)

    @staticmethod
    def _apply_plain_text_style(
        editor: QsciScintilla,
        settings: Settings,
    ) -> None:
        theme = get_theme(
            settings.get("editor.theme"),
            custom_base=settings.get("editor.custom_theme.base"),
        )
        font = editor.font()
        fg = QColor(theme.editor_foreground)
        bg = QColor(theme.editor_background)

        try:
            editor.setColor(fg)
            editor.setPaper(bg)
            editor.SendScintilla(
                QsciScintilla.SCI_STYLESETFORE,
                QsciScintilla.STYLE_DEFAULT,
                EditorConfigurator._scintilla_color(fg),
            )
            editor.SendScintilla(
                QsciScintilla.SCI_STYLESETBACK,
                QsciScintilla.STYLE_DEFAULT,
                EditorConfigurator._scintilla_color(bg),
            )
            editor.SendScintilla(
                QsciScintilla.SCI_STYLESETFONT,
                QsciScintilla.STYLE_DEFAULT,
                font.family().encode("utf-8"),
            )
            editor.SendScintilla(
                QsciScintilla.SCI_STYLESETSIZE,
                QsciScintilla.STYLE_DEFAULT,
                font.pointSize(),
            )
            editor.SendScintilla(QsciScintilla.SCI_STYLECLEARALL)
            editor.SendScintilla(QsciScintilla.SCI_CLEARDOCUMENTSTYLE)
            editor.SendScintilla(QsciScintilla.SCI_SETKEYWORDS, 1, b"")
            editor.SendScintilla(QsciScintilla.SCI_COLOURISE, 0, -1)
        except (AttributeError, TypeError, RuntimeError):
            pass

    @staticmethod
    def _apply_breakpoint_margin(editor: QsciScintilla, settings: Settings) -> None:
        """Configure margin 2 as the breakpoint gutter."""
        theme = get_theme(
            settings.get("editor.theme"),
            custom_base=settings.get("editor.custom_theme.base"),
        )

        # Margin 2: narrow symbol margin for breakpoint dots. Width must
        # leave room for custom breakpoint artwork so it stays centered
        # instead of clipping into the text area.
        editor.setMarginType(2, QsciScintilla.MarginType.SymbolMargin)
        from meadowpy.editor.code_editor import (
            BREAKPOINT_MARGIN_WIDTH,
            MARKER_BREAKPOINT,
            MARKER_CURRENT_LINE,
            MARKER_PHANTOM_BREAKPOINT,
        )
        editor.setMarginWidth(2, BREAKPOINT_MARGIN_WIDTH)
        editor.setMarginSensitivity(2, True)

        # Show breakpoint + current-line markers in this margin
        editor.setMarginMarkerMask(
            2,
            (
                (1 << MARKER_BREAKPOINT)
                | (1 << MARKER_CURRENT_LINE)
                | (1 << MARKER_PHANTOM_BREAKPOINT)
            ),
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

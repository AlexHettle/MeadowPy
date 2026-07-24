"""Smart indentation handler for Python code."""

from io import StringIO
import tokenize

from PyQt6.Qsci import QsciScintilla

from meadowpy.core.settings import Settings


_IGNORED_TOKEN_TYPES = {
    tokenize.COMMENT,
    tokenize.DEDENT,
    tokenize.ENDMARKER,
    tokenize.INDENT,
    tokenize.NEWLINE,
    tokenize.NL,
}


class SmartIndentHandler:
    """Handles smart indentation after Enter key press.

    - After a line ending with ':', adds one extra indent level.
    - After return/break/continue/pass/raise, dedents the next line.
    """

    DEDENT_KEYWORDS = {"return", "break", "continue", "pass", "raise"}

    def __init__(self, editor: QsciScintilla, settings: Settings):
        self._editor = editor
        self._settings = settings

    def handle_return(self) -> bool:
        """Called on Enter key. Returns True if handled (caller should skip default)."""
        if not self._settings.get("editor.smart_indent"):
            return False

        line, col = self._editor.getCursorPosition()
        line_text = self._editor.text(line)
        # Only look at text before the cursor
        text_before_cursor = line_text[:col]
        stripped = text_before_cursor.rstrip()

        if not stripped:
            return False  # empty line, let default handle it

        current_indent = self._get_line_indent(line)
        indent_str = self._get_indent_unit()

        # Case 1: Line ends with a code colon -> extra indent
        if self._ends_with_code_colon(text_before_cursor):
            new_indent = current_indent + indent_str
            self._insert_newline_with_indent(new_indent)
            return True

        # Case 2: Line starts with a dedent keyword -> next line should dedent
        if self._starts_with_dedent_keyword(text_before_cursor):
            if len(current_indent) >= len(indent_str):
                new_indent = current_indent[: -len(indent_str)]
            else:
                new_indent = ""
            self._insert_newline_with_indent(new_indent)
            return True

        return False  # fall through to default auto-indent

    def _get_line_indent(self, line: int) -> str:
        """Return the whitespace prefix of the given line."""
        text = self._editor.text(line)
        return text[: len(text) - len(text.lstrip())]

    def _get_indent_unit(self) -> str:
        """Return one indent level as a string (spaces or tab)."""
        if self._settings.get("editor.use_spaces"):
            return " " * self._settings.get("editor.tab_width")
        return "\t"

    def _ends_with_code_colon(self, text: str) -> bool:
        """Return True when the last meaningful token is a Python code colon."""
        last_token = None
        try:
            for token in tokenize.generate_tokens(StringIO(text).readline):
                if token.type in _IGNORED_TOKEN_TYPES:
                    continue
                last_token = token
        except (IndentationError, tokenize.TokenError):
            return False

        return (
            last_token is not None
            and last_token.type == tokenize.OP
            and last_token.string == ":"
        )

    def _starts_with_dedent_keyword(self, text: str) -> bool:
        """Return True when a complete line starts with a block-ending keyword."""
        first_token = None
        try:
            for token in tokenize.generate_tokens(StringIO(text).readline):
                if token.type in _IGNORED_TOKEN_TYPES:
                    continue
                if first_token is None:
                    first_token = token
        except (IndentationError, tokenize.TokenError):
            return False

        return (
            first_token is not None
            and first_token.type == tokenize.NAME
            and first_token.string in self.DEDENT_KEYWORDS
        )

    def _insert_newline_with_indent(self, indent: str) -> None:
        """Insert a newline followed by the given indentation."""
        self._editor.insert("\n" + indent)
        line, _ = self._editor.getCursorPosition()
        self._editor.setCursorPosition(line + 1, len(indent))

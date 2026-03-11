"""Smart indentation handler for Python code."""

from PyQt6.Qsci import QsciScintilla

from meadowpy.core.settings import Settings


class SmartIndentHandler:
    """Handles smart indentation after Enter key press.

    - After a line ending with ':', adds one extra indent level.
    - After return/break/continue/pass/raise, dedents the next line.
    """

    INDENT_AFTER_COLON = True

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

        # Case 1: Line ends with colon -> extra indent
        if stripped.endswith(":"):
            new_indent = current_indent + indent_str
            self._insert_newline_with_indent(new_indent)
            return True

        # Case 2: Line starts with a dedent keyword -> next line should dedent
        first_word = stripped.split()[0] if stripped.split() else ""
        if first_word in self.DEDENT_KEYWORDS:
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

    def _insert_newline_with_indent(self, indent: str) -> None:
        """Insert a newline followed by the given indentation."""
        self._editor.insert("\n" + indent)
        line, _ = self._editor.getCursorPosition()
        self._editor.setCursorPosition(line + 1, len(indent))

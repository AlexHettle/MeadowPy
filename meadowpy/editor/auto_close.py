"""Auto-closing brackets and quotes handler."""

from PyQt6.Qsci import QsciScintilla

from meadowpy.core.settings import Settings


class AutoCloseHandler:
    """Handles auto-insertion of closing brackets and quotes.

    - Type '(' -> inserts '()' with cursor between
    - Type ')' when ')' is at cursor -> skips over it
    - Backspace between a pair -> deletes both characters
    """

    PAIRS = {
        "(": ")",
        "[": "]",
        "{": "}",
        '"': '"',
        "'": "'",
    }
    OPENERS = {"(", "[", "{"}
    CLOSERS = {")", "]", "}"}
    QUOTES = {'"', "'"}

    def __init__(self, editor: QsciScintilla, settings: Settings):
        self._editor = editor
        self._settings = settings

    def handle_key(self, event) -> bool:
        """Process a key event. Returns True if handled."""
        if not self._settings.get("editor.auto_close_brackets"):
            return False

        char = event.text()
        if not char:
            return False

        # Don't auto-close if there's a selection
        if self._editor.hasSelectedText():
            return False

        line, col = self._editor.getCursorPosition()
        line_text = self._editor.text(line)
        # Strip trailing newline for length comparisons
        line_content = line_text.rstrip("\n\r")

        # Case 1: Typing a closing bracket that already exists at cursor -> skip over
        if char in self.CLOSERS:
            if col < len(line_content) and line_content[col] == char:
                self._editor.setCursorPosition(line, col + 1)
                return True

        # Case 2: Typing a quote
        if char in self.QUOTES:
            # Skip over if closing quote already at cursor
            if col < len(line_content) and line_content[col] == char:
                count_before = line_content[:col].count(char)
                if count_before % 2 == 1:  # odd count = this is closing
                    self._editor.setCursorPosition(line, col + 1)
                    return True

            # Insert pair if next char is whitespace, EOL, or a closer
            next_char = line_content[col] if col < len(line_content) else ""
            if next_char == "" or next_char in " \t)]}:,;":
                self._editor.insert(char + char)
                self._editor.setCursorPosition(line, col + 1)
                return True

        # Case 3: Typing an opener -> insert pair
        if char in self.OPENERS:
            closing = self.PAIRS[char]
            self._editor.insert(char + closing)
            self._editor.setCursorPosition(line, col + 1)
            return True

        return False

    def handle_backspace(self) -> bool:
        """Delete both chars of an auto-inserted pair when backspacing between them."""
        if not self._settings.get("editor.auto_close_brackets"):
            return False

        # Don't handle if there's a selection
        if self._editor.hasSelectedText():
            return False

        line, col = self._editor.getCursorPosition()
        if col == 0:
            return False

        line_text = self._editor.text(line)
        line_content = line_text.rstrip("\n\r")

        if col > len(line_content):
            return False

        char_before = line_content[col - 1] if col > 0 else ""
        char_after = line_content[col] if col < len(line_content) else ""

        if char_before in self.PAIRS and self.PAIRS[char_before] == char_after:
            # Delete both characters of the pair
            self._editor.setSelection(line, col - 1, line, col + 1)
            self._editor.removeSelectedText()
            return True

        return False

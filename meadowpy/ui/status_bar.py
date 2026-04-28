"""Status bar management."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QStatusBar, QLabel

from meadowpy.core.settings import Settings
from meadowpy.resources.resource_loader import theme_is_high_contrast


class _ClickableLabel(QLabel):
    """A QLabel that emits clicked() on mouse press."""

    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class StatusBarManager:
    """Manages the status bar widgets: cursor position, encoding, EOL, indentation, lint counts, debug state, interpreter."""

    def __init__(self, status_bar: QStatusBar, settings: Settings):
        self._status_bar = status_bar
        self._settings = settings

        self._cursor_label = QLabel("Ln 1, Col 1")
        self._cursor_label.setToolTip("Current line and column number in the editor")

        self._encoding_label = QLabel("UTF-8")
        self._encoding_label.setToolTip("File character encoding")

        self._eol_label = QLabel("LF")
        self._eol_label.setToolTip("Line ending style (LF = Unix/Mac, CRLF = Windows)")

        self._indent_label = QLabel("")
        self._indent_label.setToolTip("Indentation style — spaces or tabs, and their width")

        self._lint_label = QLabel("")
        self._lint_label.setToolTip("Code issues found by the linter (errors and warnings)")

        self._debug_label = QLabel("")
        self._debug_label.setToolTip("Current debugger state")

        self._interpreter_label = QLabel("")
        self._interpreter_label.setToolTip("Python interpreter used to run your code")

        self._ollama_label = _ClickableLabel("AI: Offline")
        self._ollama_label.setToolTip(
            "Ollama AI connection status \u2014 click to select a model"
        )
        self._ollama_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ollama_label.setObjectName("ollamaStatusLabel")

        for label in [
            self._cursor_label,
            self._encoding_label,
            self._eol_label,
            self._indent_label,
            self._lint_label,
            self._debug_label,
            self._interpreter_label,
            self._ollama_label,
        ]:
            label.setMinimumWidth(70)
            self._status_bar.addPermanentWidget(label)

        self.update_indent_info()

    def update_cursor_position(self, line: int, col: int) -> None:
        self._cursor_label.setText(f"Ln {line + 1}, Col {col + 1}")

    def update_encoding(self, encoding: str) -> None:
        self._encoding_label.setText(encoding)

    def update_eol_mode(self, mode: str) -> None:
        self._eol_label.setText(mode)

    def update_indent_info(self) -> None:
        use_spaces = self._settings.get("editor.use_spaces")
        width = self._settings.get("editor.tab_width")
        self._indent_label.setText(
            f"Spaces: {width}" if use_spaces else f"Tab Size: {width}"
        )

    def update_lint_counts(self, errors: int, warnings: int) -> None:
        """Update the lint count display in the status bar."""
        # Cache so we can re-render with new colors on a theme switch.
        self._last_lint_counts = (errors, warnings)

        if errors == 0 and warnings == 0:
            self._lint_label.setText("\u2713 No issues")
            return

        is_hc = theme_is_high_contrast(
            self._settings.get("editor.theme") or ""
        )
        # In HC the status bar background is WHITE, so the glyphs need
        # to be BLACK to stay legible (white-on-white would disappear).
        # Also swap the warning sign ⚠ -> ▲ (BLACK UP-POINTING
        # TRIANGLE) because the system font renders ⚠ as a yellow
        # color emoji which ignores the inline color attribute. ▲
        # is a geometric-shapes codepoint that always renders as
        # monochrome text.
        error_color = "#000000" if is_hc else "#F44747"
        warning_color = "#000000" if is_hc else "#CCA700"
        warning_glyph = "\u25B2" if is_hc else "\u26A0"

        parts = []
        if errors:
            parts.append(
                f'<span style="color:{error_color};">\u2716</span> {errors}'
            )
        if warnings:
            parts.append(
                f'<span style="color:{warning_color};">{warning_glyph}</span> {warnings}'
            )
        self._lint_label.setText("&nbsp;&nbsp;".join(parts))

    def refresh_lint_colors(self) -> None:
        """Re-render the lint counts using the current theme's colors.

        Called by the main window when the theme changes so existing
        red/amber severity glyphs flip to white when entering HC (and
        back when leaving) without waiting for the next lint run.
        """
        errors, warnings = getattr(self, "_last_lint_counts", (0, 0))
        self.update_lint_counts(errors, warnings)

    def update_debug_state(self, state) -> None:
        """Update the debug state label in the status bar."""
        from meadowpy.core.debug_manager import DebugState
        state_labels = {
            DebugState.IDLE: "",
            DebugState.STARTING: "\u23F3 Starting...",
            DebugState.RUNNING: "\u25B6 Debugging",
            DebugState.PAUSED: "\u23F8 Paused",
            DebugState.STOPPING: "\u23F9 Stopping...",
        }
        self._debug_label.setText(state_labels.get(state, ""))

    def update_interpreter(self, label: str) -> None:
        """Update the interpreter display in the status bar."""
        self._interpreter_label.setText(label)

    def update_ollama_status(self, connected: bool, model_name: str) -> None:
        """Update the Ollama AI status indicator in the status bar."""
        if not connected:
            self._ollama_label.setText("AI: Offline")
        elif model_name:
            self._ollama_label.setText(f"AI: {model_name}")
        else:
            self._ollama_label.setText("AI: Select model...")

    @property
    def ollama_label(self) -> _ClickableLabel:
        """Expose the clickable label so MainWindow can connect its click signal."""
        return self._ollama_label

    def show_message(self, message: str, timeout: int = 3000) -> None:
        """Show a temporary message (e.g., 'File saved')."""
        self._status_bar.showMessage(message, timeout)

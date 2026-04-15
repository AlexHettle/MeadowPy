"""Output panel — displays program output with stdin support."""

import re

from PyQt6.QtCore import QEvent, QObject, QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QRadialGradient, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from meadowpy.resources.resource_loader import get_icon_path

# Matches Python traceback file references, e.g.:
#   File "C:\Users\Alex\script.py", line 42, in <module>
_TRACEBACK_RE = re.compile(r'^\s*File "([^"]+)", line (\d+)')


class _HeaderGlowPainter(QObject):
    """Paints radial glow effects on the output header behind registered buttons."""

    HOVER_RADIUS = 12
    HOVER_ALPHA = 55
    PRESS_RADIUS = 16
    PRESS_ALPHA = 90

    def __init__(self, surface: QWidget, parent=None):
        super().__init__(parent)
        self._surface = surface
        self._entries: list[dict] = []
        surface.installEventFilter(self)

    def add_button(self, button, color: QColor) -> None:
        entry = {"btn": button, "color": QColor(color), "state": "idle"}
        self._entries.append(entry)
        button.installEventFilter(self)

    def set_button_color(self, button, color: QColor) -> None:
        """Update the glow color for an already-registered button."""
        for entry in self._entries:
            if entry["btn"] is button:
                entry["color"] = QColor(color)
                self._surface.update()
                return

    def eventFilter(self, obj, event):
        etype = event.type()

        for entry in self._entries:
            if obj is entry["btn"]:
                if etype == QEvent.Type.HoverEnter and obj.isEnabled():
                    entry["state"] = "hover"
                    self._surface.update()
                elif etype == QEvent.Type.HoverLeave:
                    entry["state"] = "idle"
                    self._surface.update()
                elif etype == QEvent.Type.MouseButtonPress and obj.isEnabled():
                    entry["state"] = "press"
                    self._surface.update()
                elif etype == QEvent.Type.MouseButtonRelease:
                    entry["state"] = (
                        "hover" if obj.underMouse() and obj.isEnabled()
                        else "idle"
                    )
                    self._surface.update()
                return False

        if obj is self._surface and etype == QEvent.Type.Paint:
            obj.removeEventFilter(self)
            QApplication.sendEvent(obj, event)
            obj.installEventFilter(self)

            painter = QPainter(obj)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            for entry in self._entries:
                if entry["state"] == "idle":
                    continue
                btn = entry["btn"]
                if not btn.isEnabled():
                    entry["state"] = "idle"
                    continue
                center = QPointF(btn.geometry().center())
                if entry["state"] == "press":
                    radius = self.PRESS_RADIUS
                    alpha = self.PRESS_ALPHA
                else:
                    radius = self.HOVER_RADIUS
                    alpha = self.HOVER_ALPHA

                base = QColor(entry["color"])
                grad = QRadialGradient(center, radius)
                c0 = QColor(base); c0.setAlpha(alpha)
                c1 = QColor(base); c1.setAlpha(int(alpha * 0.55))
                c2 = QColor(base); c2.setAlpha(int(alpha * 0.2))
                c3 = QColor(base); c3.setAlpha(0)
                grad.setColorAt(0.0, c0)
                grad.setColorAt(0.35, c1)
                grad.setColorAt(0.65, c2)
                grad.setColorAt(1.0, c3)

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(grad))
                painter.drawEllipse(center, radius, radius)
            painter.end()
            return True

        return False


class OutputPanel(QDockWidget):
    """Bottom panel for displaying program output and accepting stdin.

    Operates in two modes:
    * **REPL** — input is sent to the persistent interactive console
    * **STDIN** — input is sent to a running script's stdin (existing behaviour)
    """

    input_submitted = pyqtSignal(str)          # script stdin text
    repl_input_submitted = pyqtSignal(str)     # REPL command text
    repl_restart_requested = pyqtSignal()      # user clicked Restart Console
    repl_history_up = pyqtSignal()             # Up arrow in REPL mode
    repl_history_down = pyqtSignal()           # Down arrow in REPL mode
    traceback_navigate = pyqtSignal(str, int)  # (file_path, line_number 1-based)
    ai_fix_requested = pyqtSignal(str)         # last error/traceback text

    _MODE_REPL = "repl"
    _MODE_STDIN = "stdin"

    def __init__(self, parent=None):
        super().__init__("Output", parent)
        self.setObjectName("OutputPanel")
        self.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea
            | Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self._max_lines = 10000
        self._last_error_text: str = ""  # stores the most recent stderr block
        self._mode = self._MODE_REPL
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Header toolbar ---
        header = QWidget()
        header.setObjectName("outputHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)

        header_layout.addStretch()

        self._run_btn = self._make_tool_button(
            "run", "Run (F5)"
        )
        self._stop_btn = self._make_tool_button(
            "stop", "Stop (Ctrl+F5)"
        )
        self._stop_btn.setEnabled(False)

        self._fix_btn = QPushButton("AI Analysis")
        self._fix_btn.setObjectName("outputFixAIBtn")
        self._fix_btn.setToolTip("Ask the AI to analyze the last error")
        self._fix_btn.setFixedHeight(22)
        self._fix_btn.setVisible(False)  # shown only when an error exists
        self._fix_btn.clicked.connect(self._on_fix_with_ai)

        self._clear_btn = self._make_tool_button(
            "clear_output", "Clear Output"
        )
        self._copy_btn = self._make_tool_button(
            "copy_output", "Copy Output"
        )

        self._restart_repl_btn = self._make_tool_button(
            "restart", "Restart Python Console"
        )
        self._restart_repl_btn.clicked.connect(
            lambda: self.repl_restart_requested.emit()
        )

        # Transparent hover/press for run/stop/restart so only the glow shows
        for btn in (self._run_btn, self._stop_btn, self._restart_repl_btn):
            btn.setStyleSheet(
                """
                QToolButton {
                    border: 1px solid transparent;
                    border-radius: 3px;
                    padding: 3px;
                    icon-size: 16px;
                }
                QToolButton:hover {
                    background: transparent;
                    border-color: transparent;
                }
                QToolButton:pressed {
                    background: transparent;
                    border-color: transparent;
                }
                """
            )
            header_layout.addWidget(btn)

        # Glow painter for run/stop/restart buttons
        self._header_glow = _HeaderGlowPainter(header, header)
        self._header_glow.add_button(self._run_btn, QColor("#4CAF50"))           # green
        self._header_glow.add_button(self._stop_btn, QColor("#E51400"))          # red
        self._header_glow.add_button(self._restart_repl_btn, QColor("#FF9800"))  # orange

        # Visual separator
        sep = QLabel("|")
        sep.setStyleSheet("color: #999; margin: 0 4px;")
        header_layout.addWidget(sep)

        for btn in (self._clear_btn, self._copy_btn):
            header_layout.addWidget(btn)

        # Fix with AI button (after a separator, right side)
        sep2 = QLabel("|")
        sep2.setStyleSheet("color: #999; margin: 0 4px;")
        self._fix_separator = sep2
        self._fix_separator.setVisible(False)
        header_layout.addWidget(self._fix_separator)
        header_layout.addWidget(self._fix_btn)

        layout.addWidget(header)

        # --- Output text area ---
        self._output_text = QPlainTextEdit()
        self._output_text.setObjectName("outputText")
        self._output_text.setReadOnly(True)
        self._output_text.setUndoRedoEnabled(False)
        font = QFont("Consolas", 13)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._output_text.setFont(font)
        # Enable mouse tracking for hover cursor changes on traceback lines
        self._output_text.setMouseTracking(True)
        self._output_text.viewport().setMouseTracking(True)
        # Event filter must be on viewport — mouse events go there, not the widget
        self._output_text.viewport().installEventFilter(self)
        layout.addWidget(self._output_text)

        # --- Input area (always visible) ---
        self._input_area = QWidget()
        self._input_area.setObjectName("outputInputArea")
        input_layout = QHBoxLayout(self._input_area)
        input_layout.setContentsMargins(8, 4, 8, 4)

        self._prompt_label = QLabel(">>>")
        self._prompt_label.setObjectName("replPrompt")
        self._prompt_label.setFont(font)
        input_layout.addWidget(self._prompt_label)

        self._input_line = QLineEdit()
        self._input_line.setObjectName("outputInput")
        self._input_line.setFont(font)
        self._input_line.setPlaceholderText("Type Python here...")
        self._input_line.setToolTip(
            "Type Python commands here (press Enter to run, "
            "Up/Down arrows for history)"
        )
        self._input_line.returnPressed.connect(self._on_input_submitted)
        self._input_line.installEventFilter(self)
        input_layout.addWidget(self._input_line)

        self._send_btn = QPushButton("Run")
        self._send_btn.setObjectName("replRunBtn")
        self._send_btn.setToolTip("Run the command (Enter)")
        self._send_btn.clicked.connect(self._on_input_submitted)
        input_layout.addWidget(self._send_btn)

        layout.addWidget(self._input_area)

        self.setWidget(container)

        # Button connections
        self._clear_btn.clicked.connect(self.clear_output)
        self._copy_btn.clicked.connect(self.copy_output)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append_output(self, text: str, stream: str = "stdout") -> None:
        """Append color-coded text to the output area.

        *stream* is one of ``"stdout"``, ``"stderr"``, ``"system"``,
        or ``"hint"`` (beginner-friendly error explanation).

        When *stream* is ``"stderr"``, lines that look like Python
        traceback file references are styled as clickable links.
        """
        # Normalize Windows \r\n → \n (QPlainTextEdit treats \r as
        # an extra line break, which causes spurious blank lines).
        text = text.replace("\r", "")

        # Detect whether scrollbar is at the bottom before inserting
        scrollbar = self._output_text.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum() - 4

        cursor = self._output_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        if stream == "stderr":
            self._last_error_text += text
            self._fix_btn.setVisible(True)
            self._fix_separator.setVisible(True)
            self._insert_stderr(cursor, text)
        else:
            fmt = QTextCharFormat()
            if stream == "hint":
                fmt.setForeground(QColor("#4EC9B0"))
                fmt.setFontItalic(True)
            elif stream == "system":
                fmt.setForeground(QColor("#888888"))
                fmt.setFontItalic(True)
            # stdout uses default text color (theme-dependent)
            cursor.insertText(text, fmt)

        # Enforce max line limit
        self._trim_output()

        # Auto-scroll only if user was already at the bottom
        if at_bottom:
            self._output_text.setTextCursor(cursor)
            self._output_text.ensureCursorVisible()

    def clear_output(self) -> None:
        """Clear all output text."""
        self._output_text.clear()
        self._last_error_text = ""
        self._fix_btn.setVisible(False)
        self._fix_separator.setVisible(False)

    def copy_output(self) -> None:
        """Copy all output text to the clipboard."""
        text = self._output_text.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)

    def set_running(self, running: bool) -> None:
        """Switch between script-stdin mode and REPL mode."""
        self._run_btn.setEnabled(not running)
        self._stop_btn.setEnabled(running)
        if running:
            self._mode = self._MODE_STDIN
            self._prompt_label.setText("Input:")
            self._send_btn.setText("Send")
            self._send_btn.setToolTip("Send input to the running program (Enter)")
            self._input_line.setPlaceholderText("Enter input...")
            self._input_line.setToolTip(
                "Type here when your program asks for input (press Enter to send)"
            )
            self._input_line.clear()
            self._input_line.setFocus()
            # Reset error state for the new run
            self._last_error_text = ""
            self._fix_btn.setVisible(False)
            self._fix_separator.setVisible(False)
        else:
            self._mode = self._MODE_REPL
            self._prompt_label.setText(">>>")
            self._send_btn.setText("Run")
            self._send_btn.setToolTip("Run the command (Enter)")
            self._input_line.setPlaceholderText("Type Python here...")
            self._input_line.setToolTip(
                "Type Python commands here (press Enter to run, "
                "Up/Down arrows for history)"
            )

    def set_max_lines(self, max_lines: int) -> None:
        self._max_lines = max_lines

    def update_accent_color(self, hex_color: str) -> None:
        """Refresh the Run button's glow color (called on theme change)."""
        self._header_glow.set_button_color(self._run_btn, QColor(hex_color))

    def update_font(self, family: str, size: int) -> None:
        """Update the monospace font for output and input."""
        font = QFont(family, size)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._output_text.setFont(font)
        self._input_line.setFont(font)

    @property
    def run_button(self) -> QToolButton:
        return self._run_btn

    @property
    def stop_button(self) -> QToolButton:
        return self._stop_btn

    # ------------------------------------------------------------------
    # Event filter — click & hover on traceback lines
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event):
        # Up/Down arrow keys in the input line → command history (REPL mode)
        if hasattr(self, "_input_line") and obj is self._input_line and self._mode == self._MODE_REPL:
            if event.type() == QEvent.Type.KeyPress:
                key = event.key()
                if key == Qt.Key.Key_Up:
                    self.repl_history_up.emit()
                    return True
                if key == Qt.Key.Key_Down:
                    self.repl_history_down.emit()
                    return True

        # Click & hover on traceback lines in the output area
        if obj is self._output_text.viewport():
            etype = event.type()

            if etype == QEvent.Type.MouseButtonPress:
                pos = event.position().toPoint()
                cursor = self._output_text.cursorForPosition(pos)
                line_text = cursor.block().text()
                match = _TRACEBACK_RE.match(line_text)
                if match:
                    file_path = match.group(1)
                    line_num = int(match.group(2))
                    self.traceback_navigate.emit(file_path, line_num)
                    return True

            if etype == QEvent.Type.MouseMove:
                pos = event.position().toPoint()
                cursor = self._output_text.cursorForPosition(pos)
                line_text = cursor.block().text()
                viewport = self._output_text.viewport()
                if _TRACEBACK_RE.match(line_text):
                    viewport.setCursor(
                        Qt.CursorShape.PointingHandCursor
                    )
                else:
                    viewport.setCursor(Qt.CursorShape.IBeamCursor)

        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _insert_stderr(self, cursor: QTextCursor, text: str) -> None:
        """Insert stderr text, styling traceback file lines as links."""
        stderr_fmt = QTextCharFormat()
        stderr_fmt.setForeground(QColor("#E51400"))

        link_fmt = QTextCharFormat()
        link_fmt.setForeground(QColor("#5999D4"))
        link_fmt.setFontUnderline(True)

        # Split into lines but preserve the original text exactly
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if _TRACEBACK_RE.match(line):
                cursor.insertText(line, link_fmt)
            else:
                cursor.insertText(line, stderr_fmt)
            # Re-add newlines between lines (split removes them)
            if i < len(lines) - 1:
                cursor.insertText("\n", stderr_fmt)

    def _on_fix_with_ai(self) -> None:
        """Emit the last error text for AI analysis."""
        if self._last_error_text.strip():
            self.ai_fix_requested.emit(self._last_error_text.strip())

    def update_repl_prompt(self, prompt: str) -> None:
        """Update the prompt label from the REPL (``>>>`` or ``...``)."""
        if self._mode == self._MODE_REPL:
            self._prompt_label.setText(prompt.rstrip())

    def set_input_text(self, text: str) -> None:
        """Set the input line text (used for command history navigation)."""
        self._input_line.setText(text)
        self._input_line.setCursorPosition(len(text))

    def _on_input_submitted(self) -> None:
        text = self._input_line.text()
        self._input_line.clear()

        if self._mode == self._MODE_STDIN:
            # Script is running — send to script stdin (existing behaviour)
            self.append_output(f"{text}\n", "stdout")
            self.input_submitted.emit(text + "\n")
        else:
            # REPL mode — echo with prompt, send to interactive console
            prompt = self._prompt_label.text()
            self.append_output(f"{prompt} {text}\n", "stdout")
            self.repl_input_submitted.emit(text)

    def _trim_output(self) -> None:
        """Remove earliest lines when output exceeds max_lines."""
        doc = self._output_text.document()
        while doc.blockCount() > self._max_lines:
            cursor = QTextCursor(doc.begin())
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.movePosition(
                QTextCursor.MoveOperation.NextBlock,
                QTextCursor.MoveMode.KeepAnchor,
            )
            cursor.removeSelectedText()

    @staticmethod
    def _make_tool_button(icon_name: str, tooltip: str) -> QToolButton:
        btn = QToolButton()
        btn.setToolTip(tooltip)
        icon_path = get_icon_path(icon_name)
        btn.setStyleSheet(
            f"""
            QToolButton {{
                border: 1px solid transparent;
                border-radius: 3px;
                padding: 3px;
                icon-size: 16px;
            }}
            QToolButton:hover {{
                background: rgba(128,128,128,0.2);
                border-color: rgba(128,128,128,0.3);
            }}
            """
        )
        from PyQt6.QtGui import QIcon
        btn.setIcon(QIcon(str(icon_path)))
        return btn

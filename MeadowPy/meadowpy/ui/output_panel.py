"""Output panel — displays program output with stdin support."""

from PyQt6.QtCore import QEvent, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QPainter,
    QTextBlockUserData,
    QTextCursor,
)
from PyQt6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from meadowpy.resources.resource_loader import (
    current_accent_hex,
    load_themed_icon,
    load_tinted_icon,
    theme_is_high_contrast,
)
from meadowpy.ui.output_panel_glow import HeaderGlowPainter
from meadowpy.ui.output_text_formatting import (
    TRACEBACK_RE,
    insert_stderr_text,
    normalize_output_text,
    stream_text_format,
)
from meadowpy.ui.panel_title_bar import (
    PANEL_TITLE_CONTENT_HEIGHT,
    PANEL_TITLE_CONTROL_SIZE,
    PANEL_TITLE_ICON_SIZE,
    configure_panel_title_bar,
    configure_panel_title_label,
)


class _HintBlockData(QTextBlockUserData):
    """Marks the first document block belonging to an error hint."""


class _HintGutter(QWidget):
    """Dedicated painting surface for output hint icons."""

    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def sizeHint(self) -> QSize:
        return QSize(self._editor.HINT_GUTTER_WIDTH, 0)

    def paintEvent(self, event) -> None:
        self._editor.paint_hint_gutter(event)


class _OutputTextEdit(QPlainTextEdit):
    """Plain-text output view that paints themed icons beside hint blocks."""

    HINT_GUTTER_WIDTH = 22
    HINT_ICON_SIZE = 16

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hint_icon = QIcon()
        self._hint_gutter = _HintGutter(self)
        self.setViewportMargins(self.HINT_GUTTER_WIDTH, 0, 0, 0)
        self.updateRequest.connect(self._update_hint_gutter)

    def set_hint_icon(self, icon: QIcon) -> None:
        """Set the icon painted in the reserved hint gutter."""
        self._hint_icon = icon
        self._hint_gutter.update()

    def insert_hint(
        self,
        cursor: QTextCursor,
        text: str,
        text_format,
    ) -> None:
        """Insert a hint while keeping its icon out of copied plain text."""
        cursor.block().setUserData(_HintBlockData())
        cursor.insertText(text, text_format)

    def paint_hint_gutter(self, event) -> None:
        """Paint icons beside visible hint blocks in the reserved gutter."""
        if self._hint_icon.isNull():
            return

        painter = QPainter(self._hint_gutter)
        painter.setClipRect(event.rect())
        block = self.firstVisibleBlock()
        top = self.blockBoundingGeometry(block).translated(
            self.contentOffset()
        ).top()

        while block.isValid() and top <= event.rect().bottom():
            height = self.blockBoundingRect(block).height()
            if (
                block.isVisible()
                and top + height >= event.rect().top()
                and isinstance(block.userData(), _HintBlockData)
            ):
                pixmap = self._hint_icon.pixmap(
                    QSize(self.HINT_ICON_SIZE, self.HINT_ICON_SIZE)
                )
                x = int((self._hint_gutter.width() - pixmap.width()) / 2)
                y = int(top + max(0.0, (height - pixmap.height()) / 2.0))
                painter.drawPixmap(x, y, pixmap)
            top += height
            block = block.next()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        contents = self.contentsRect()
        self._hint_gutter.setGeometry(QRect(
            contents.left(),
            contents.top(),
            self.HINT_GUTTER_WIDTH,
            contents.height(),
        ))

    def _update_hint_gutter(self, rect, dy: int) -> None:
        """Keep gutter icons aligned while output scrolls or repaints."""
        if dy:
            self._hint_gutter.scroll(0, dy)
        else:
            self._hint_gutter.update(
                0,
                rect.y(),
                self._hint_gutter.width(),
                rect.height(),
            )


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

    def __init__(self, parent=None, settings=None):
        super().__init__("Output", parent)
        self.setObjectName("OutputPanel")
        self.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea
            | Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self._max_lines = 10000
        self._last_error_text: str = ""  # stores the most recent stderr block
        # Keep an in-memory replay buffer of every (stream, text) chunk we've
        # appended. The visible QPlainTextEdit bakes color into character
        # formats, so when the theme switches between HC and non-HC we need
        # to clear the widget and replay everything to re-tint old output.
        self._output_history: list[tuple[str, str]] = []
        self._mode = self._MODE_REPL
        self._settings = settings
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        # -- custom dock title bar ("Output" + action buttons) ----------
        # Mirrors the File Explorer panel: a QFrame title bar with the
        # panel name on the left and the toolbar buttons on the right,
        # installed via setTitleBarWidget so the dock stays draggable.
        title_bar = QFrame()
        title_bar.setObjectName("outputTitleBar")
        title_bar.setFrameShape(QFrame.Shape.NoFrame)
        header_layout = QHBoxLayout(title_bar)
        configure_panel_title_bar(title_bar, header_layout, spacing=2)

        title_label = QLabel("Output")
        title_label.setObjectName("outputTitleLabel")
        configure_panel_title_label(title_label)
        header_layout.addWidget(title_label, 0, Qt.AlignmentFlag.AlignVCenter)

        header_layout.addStretch()

        self._fix_btn = QPushButton("AI Analysis")
        self._fix_btn.setObjectName("outputFixAIBtn")
        self._fix_btn.setToolTip("Ask the AI to analyze the last error")
        self._fix_btn.setFixedHeight(PANEL_TITLE_CONTENT_HEIGHT)
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
        restart_accent = QColor(self._current_accent_color())
        self._restart_repl_btn.setIcon(load_tinted_icon(
            "restart",
            restart_accent.name(),
            size=PANEL_TITLE_ICON_SIZE,
        ))
        self._restart_repl_btn.clicked.connect(
            lambda: self.repl_restart_requested.emit()
        )

        # Transparent hover/press for restart so only the glow shows.
        for btn in (self._restart_repl_btn,):
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
            header_layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)

        # Glow painter for the restart button follows the same live accent
        # as the icon (pure white when High Contrast is active).
        self._header_glow = HeaderGlowPainter(title_bar, title_bar)
        self._header_glow.add_button(self._restart_repl_btn, restart_accent)

        # Visual separator
        sep = QLabel("|")
        sep.setStyleSheet("color: #999; margin: 0 4px;")
        sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sep.setContentsMargins(0, 0, 0, 4)
        sep.setFixedHeight(PANEL_TITLE_CONTENT_HEIGHT)
        header_layout.addWidget(sep, 0, Qt.AlignmentFlag.AlignVCenter)

        for btn in (self._clear_btn, self._copy_btn):
            header_layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)

        # Fix with AI button (after a separator, right side)
        sep2 = QLabel("|")
        sep2.setStyleSheet("color: #999; margin: 0 4px;")
        self._fix_separator = sep2
        self._fix_separator.setVisible(False)
        self._fix_separator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._fix_separator.setFixedHeight(PANEL_TITLE_CONTENT_HEIGHT)
        header_layout.addWidget(
            self._fix_separator,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )
        header_layout.addWidget(self._fix_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        # Install the title bar as the dock's draggable title bar widget.
        self.setTitleBarWidget(title_bar)
        self._title_bar = title_bar

        # -- main container (rounded bottom corners, border l/r/bottom) -
        container = QFrame()
        container.setObjectName("outputContainer")
        container.setFrameShape(QFrame.Shape.NoFrame)
        layout = QVBoxLayout(container)
        # Keep row spacing inside the input area so controls are visually
        # centered against the full bottom band.
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Output text area ---
        self._output_text = _OutputTextEdit()
        self._output_text.setObjectName("outputText")
        self._output_text.setReadOnly(True)
        self._output_text.setUndoRedoEnabled(False)
        font = QFont("Consolas", 13)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._output_text.setFont(font)
        self._refresh_hint_icon()
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
        input_layout.setContentsMargins(8, 9, 8, 9)
        input_layout.setSpacing(6)
        input_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Prompt label is kept (for echoing the current prompt to the
        # output area on submit) but no longer shown in the UI — the
        # input line takes over that space.
        self._prompt_label = QLabel(">>>")
        self._prompt_label.setObjectName("replPrompt")
        self._prompt_label.setFont(font)
        self._prompt_label.hide()

        self._input_line = QLineEdit()
        self._input_line.setObjectName("outputInput")
        self._input_line.setFont(font)
        self._input_line.setFixedHeight(32)
        self._input_line.setPlaceholderText("Type Python here...")
        self._input_line.setToolTip(
            "Type Python commands here (press Enter to run, "
            "Up/Down arrows for history)"
        )
        self._input_line.returnPressed.connect(self._on_input_submitted)
        self._input_line.textChanged.connect(self._update_send_button_state)
        self._input_line.installEventFilter(self)
        input_layout.addWidget(
            self._input_line, 1, Qt.AlignmentFlag.AlignVCenter
        )

        self._send_btn = QPushButton("")
        self._send_btn.setObjectName("replRunBtn")
        self._send_btn.setToolTip("Run the command (Enter)")
        self._send_btn.setAccessibleName("Run command")
        self._send_btn.setFixedSize(32, 32)
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.setEnabled(False)
        self._refresh_send_arrow_icon()
        self._send_btn.clicked.connect(self._on_input_submitted)
        input_layout.addWidget(
            self._send_btn, 0, Qt.AlignmentFlag.AlignVCenter
        )

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
        text = normalize_output_text(text)

        # Record into the replay buffer so we can re-render with new colors
        # on a theme switch. Capped to avoid unbounded growth on long-running
        # programs; once full, the oldest chunks fall out (in line with the
        # widget's own _max_lines trim).
        self._output_history.append((stream, text))
        if len(self._output_history) > 20000:
            del self._output_history[: len(self._output_history) - 20000]

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
        elif stream == "hint":
            self._output_text.insert_hint(
                cursor,
                text,
                stream_text_format(stream, self._current_theme_name()),
            )
        else:
            cursor.insertText(
                text,
                stream_text_format(stream, self._current_theme_name()),
            )

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
        self._output_history.clear()
        self._fix_btn.setVisible(False)
        self._fix_separator.setVisible(False)

    def recolor_for_theme(self) -> None:
        """Re-render every previously appended chunk with the current theme.

        Character formats in QPlainTextEdit bake in the foreground color at
        insertion time — switching themes doesn't repaint old text. This
        clears the visible buffer and replays the recorded history so all
        existing output picks up the new theme's colors (e.g. red traceback
        text becomes white in HC, and back to red when leaving HC).
        """
        self._refresh_hint_icon()
        history_snapshot = list(self._output_history)
        # Reset visible state and history; append_output will rebuild both.
        self._output_text.clear()
        self._output_history.clear()
        # Temporarily clear stderr accumulator so _insert_stderr doesn't
        # double-count the replayed traceback text.
        prior_error = self._last_error_text
        self._last_error_text = ""
        for stream, text in history_snapshot:
            self.append_output(text, stream)
        # Preserve the original error tail so the AI Analysis button still
        # has the right context after a theme switch.
        self._last_error_text = prior_error

    def copy_output(self) -> None:
        """Copy all output text to the clipboard."""
        text = self._output_text.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)

    def set_running(self, running: bool) -> None:
        """Switch between script-stdin mode and REPL mode."""
        if running:
            self._mode = self._MODE_STDIN
            self._prompt_label.setText("Input:")
            self._send_btn.setToolTip("Send input to the running program (Enter)")
            self._send_btn.setAccessibleName("Send input")
            self._input_line.setPlaceholderText("Enter input...")
            self._input_line.setToolTip(
                "Type here when your program asks for input (press Enter to send)"
            )
            self._input_line.clear()
            self._update_send_button_state()
            self._input_line.setFocus()
            # Reset error state for the new run
            self._last_error_text = ""
            self._fix_btn.setVisible(False)
            self._fix_separator.setVisible(False)
        else:
            self._mode = self._MODE_REPL
            self._prompt_label.setText(">>>")
            self._send_btn.setToolTip("Run the command (Enter)")
            self._send_btn.setAccessibleName("Run command")
            self._input_line.setPlaceholderText("Type Python here...")
            self._input_line.setToolTip(
                "Type Python commands here (press Enter to run, "
                "Up/Down arrows for history)"
            )
            self._update_send_button_state()

    def set_max_lines(self, max_lines: int) -> None:
        self._max_lines = max_lines

    def update_accent_color(self, hex_color: str) -> None:
        """Refresh themed controls after accent changes."""
        color = QColor(hex_color)
        if color.isValid():
            self._restart_repl_btn.setIcon(load_tinted_icon(
                "restart",
                color.name(),
                size=PANEL_TITLE_ICON_SIZE,
            ))
            self._header_glow.set_button_color(
                self._restart_repl_btn,
                color,
            )
            self._refresh_hint_icon(color.name())
        self._refresh_send_arrow_icon()

    def update_font(self, family: str, size: int) -> None:
        """Update the monospace font for output and input."""
        font = QFont(family, size)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._output_text.setFont(font)
        self._input_line.setFont(font)

    # ------------------------------------------------------------------
    # Event filter — click & hover on traceback lines
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event):
        # Up/Down arrow keys in the input line → command history (REPL mode)
        if (
            hasattr(self, "_input_line")
            and obj is self._input_line
            and self._mode == self._MODE_REPL
        ):
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
                match = TRACEBACK_RE.match(line_text)
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
                if TRACEBACK_RE.match(line_text):
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
        insert_stderr_text(cursor, text, self._current_theme_name())

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
        self._update_send_button_state()

    def _update_send_button_state(self) -> None:
        """Enable the arrow button only when the input contains text."""
        self._send_btn.setEnabled(bool(self._input_line.text().strip()))

    def _refresh_send_arrow_icon(self) -> None:
        """Refresh the input submit arrow for the current theme."""
        is_hc = theme_is_high_contrast(self._current_theme_name())
        normal_color = "#000000" if is_hc else "#FFFFFF"
        disabled_color = "#7F7F7F" if is_hc else "#FFFFFF"
        size = QSize(18, 18)

        normal = load_tinted_icon("arrow_left_thick", normal_color, size=18)
        disabled = load_tinted_icon(
            "arrow_left_thick", disabled_color, size=18
        )
        icon = QIcon()
        normal_pixmap = normal.pixmap(size)
        disabled_pixmap = disabled.pixmap(size)
        for state in (QIcon.State.Off, QIcon.State.On):
            for mode in (
                QIcon.Mode.Normal,
                QIcon.Mode.Active,
                QIcon.Mode.Selected,
            ):
                icon.addPixmap(normal_pixmap, mode, state)
            icon.addPixmap(disabled_pixmap, QIcon.Mode.Disabled, state)

        self._send_btn.setIcon(icon)
        self._send_btn.setIconSize(size)

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

    def _make_tool_button(self, icon_name: str, tooltip: str) -> QToolButton:
        btn = QToolButton()
        btn.setToolTip(tooltip)
        btn.setFixedSize(PANEL_TITLE_CONTROL_SIZE, PANEL_TITLE_CONTROL_SIZE)
        btn.setIconSize(QSize(PANEL_TITLE_ICON_SIZE, PANEL_TITLE_ICON_SIZE))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            """
            QToolButton {
                border: 1px solid transparent;
                border-radius: 3px;
                padding: 3px;
                icon-size: 16px;
            }
            QToolButton:hover {
                background: rgba(128,128,128,0.2);
                border-color: rgba(128,128,128,0.3);
            }
            """
        )
        btn.setIcon(load_themed_icon(icon_name, self._current_theme_name()))
        return btn

    def _current_theme_name(self) -> str:
        """Return the active theme name (or '') from the injected settings."""
        if self._settings is not None:
            return self._settings.get("editor.theme") or ""
        return ""

    def _current_accent_color(self) -> str:
        """Return the active accent represented by the injected settings."""
        if self._settings is None:
            return current_accent_hex("")
        return current_accent_hex(
            self._current_theme_name(),
            self._settings.get("editor.custom_theme.base") or "dark",
            self._settings.get("editor.custom_theme.accent"),
        )

    def _refresh_hint_icon(self, color: str | None = None) -> None:
        """Retint the error-hint lightbulb for the active theme."""
        tint = QColor(color or self._current_accent_color())
        if not tint.isValid():
            return
        self._output_text.set_hint_icon(
            load_tinted_icon("lightbulb", tint.name(), size=16)
        )

"""AI Chat sidebar panel — ask questions about your code via Ollama."""

import html
import re

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QTextDocument
from PyQt6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from meadowpy.resources.resource_loader import load_tinted_icon

# Matches fenced code blocks:  ```lang\n...\n```  or  ```\n...\n```
# Allows optional spaces/tabs after the language name, and \r\n line endings.
# Also matches when there is no newline (content on same line as opening ```).
_CODE_BLOCK_RE = re.compile(
    r"```\w*[^\S\n]*\n(.*?)```"       # normal: newline after opening
    r"|"
    r"```\w*[ \t]+((?!`)..*?)```",     # inline: content on same line
    re.DOTALL,
)

# Fallback: matches triple-quoted strings ("""...""") when the AI omits
# fenced code blocks.  Used only when _CODE_BLOCK_RE finds nothing.
_TRIPLE_QUOTE_RE = re.compile(
    r'([ \t]*""".*?""")', re.DOTALL
)

# Default system prompt (beginner-friendly Python assistant)
_BASE_SYSTEM_PROMPT = (
    "You are a friendly and helpful Python coding assistant inside the "
    "MeadowPy IDE.  The user is likely a beginner.  Give clear, concise "
    "explanations.  Use short code examples when helpful.  "
    "If the user shares code, explain what it does in plain language.  "
    "ALWAYS wrap any code in fenced code blocks using triple backticks "
    "(```python ... ```) so the IDE can display it properly."
)

MAX_HISTORY_MESSAGES = 50  # keep conversation manageable


class _ChatInput(QPlainTextEdit):
    """Custom input that sends on Enter and inserts newline on Shift+Enter."""

    submit_pressed = pyqtSignal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # Shift+Enter → insert newline
                super().keyPressEvent(event)
            else:
                # Enter → send
                self.submit_pressed.emit()
        else:
            super().keyPressEvent(event)


class _Bubble(QFrame):
    """A single chat bubble — QFrame + QLabel styled via QSS for rounded corners."""

    link_clicked = pyqtSignal(str)  # raw href string

    def __init__(self, role: str, parent=None):
        super().__init__(parent)
        # role: "user" or "ai" — drives objectName for QSS styling
        self.setObjectName("chatBubbleUser" if role == "user" else "chatBubbleAi")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(0)

        self._label = QLabel()
        self._label.setTextFormat(Qt.TextFormat.RichText)
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self._label.setOpenExternalLinks(False)
        self._label.linkActivated.connect(self.link_clicked.emit)
        layout.addWidget(self._label)

    def set_html(self, html_content: str) -> None:
        self._label.setText(html_content)

    def html(self) -> str:
        return self._label.text()

    def plain_text(self) -> str:
        doc = QTextDocument()
        doc.setHtml(self._label.text())
        return doc.toPlainText()


class _ChatView(QScrollArea):
    """Scrollable message list. Bubbles are aligned left (AI) or right (user).

    Resize-aware: each bubble's maximum width is recalculated to a percentage
    of the viewport width so messages wrap nicely without filling the pane.
    """

    link_clicked = pyqtSignal(str)  # forwarded from any bubble

    _BUBBLE_WIDTH_RATIO = 0.78

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("aiChatView")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)

        self._rows: list[QWidget] = []

        inner = QWidget()
        inner.setObjectName("aiChatViewInner")
        self._inner_layout = QVBoxLayout(inner)
        self._inner_layout.setContentsMargins(10, 10, 10, 10)
        self._inner_layout.setSpacing(4)

        self._placeholder = QLabel(
            "Ask a question about your code!\n\n"
            "Try things like:\n"
            "  \u2022 \"What is a class?\"\n"
            "  \u2022 \"How do I create a list?\"\n"
            "  \u2022 \"Explain the for loop\""
        )
        self._placeholder.setObjectName("aiChatPlaceholder")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._placeholder.setWordWrap(True)
        self._inner_layout.addWidget(self._placeholder)
        self._inner_layout.addStretch(1)

        self.setWidget(inner)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

    # -- Bubble API ---------------------------------------------------

    def clear(self) -> None:
        for row in self._rows:
            row.deleteLater()
        self._rows.clear()
        self._placeholder.setVisible(True)

    def add_bubble(self, role: str, html_content: str) -> _Bubble:
        """Append a bubble aligned by role and return it."""
        bubble = _Bubble(role)
        bubble.set_html(html_content)
        bubble.link_clicked.connect(self.link_clicked.emit)
        self._append_row(bubble, align=("right" if role == "user" else "left"))
        self._constrain_widths()
        return bubble

    def add_centered(self, html_content: str, object_name: str) -> QLabel:
        """Add a centered label without a bubble (used for errors / stopped)."""
        lbl = QLabel()
        lbl.setObjectName(object_name)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        lbl.setText(html_content)
        self._append_row(lbl, align="center")
        return lbl

    def scroll_to_bottom(self) -> None:
        sb = self.verticalScrollBar()
        sb.setValue(sb.maximum())

    def is_at_bottom(self, slack: int = 20) -> bool:
        sb = self.verticalScrollBar()
        return sb.value() >= sb.maximum() - slack

    def get_all_plain_text(self) -> str:
        """Concatenate all message text (used by Copy All)."""
        pieces: list[str] = []
        for row in self._rows:
            lay = row.layout()
            for i in range(lay.count()):
                w = lay.itemAt(i).widget()
                if isinstance(w, _Bubble):
                    pieces.append(w.plain_text())
                elif isinstance(w, QLabel):
                    doc = QTextDocument()
                    doc.setHtml(w.text())
                    pieces.append(doc.toPlainText())
        return "\n\n".join(p for p in pieces if p)

    # -- Internal ------------------------------------------------------

    def _append_row(self, widget: QWidget, align: str) -> None:
        self._placeholder.setVisible(False)
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)

        if align == "right":
            row_layout.addStretch(1)
            row_layout.addWidget(widget)
        elif align == "left":
            row_layout.addWidget(widget)
            row_layout.addStretch(1)
        else:  # center
            row_layout.addStretch(1)
            row_layout.addWidget(widget)
            row_layout.addStretch(1)

        # Insert before the trailing stretch in the inner layout
        self._inner_layout.insertWidget(self._inner_layout.count() - 1, row)
        self._rows.append(row)

    def _constrain_widths(self) -> None:
        vw = self.viewport().width()
        if vw <= 0:
            return
        # Subtract inner left+right margins (20) so bubbles don't touch edges
        max_w = max(120, int((vw - 20) * self._BUBBLE_WIDTH_RATIO))
        for row in self._rows:
            lay = row.layout()
            for i in range(lay.count()):
                w = lay.itemAt(i).widget()
                if isinstance(w, _Bubble):
                    w.setMaximumWidth(max_w)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._constrain_widths()

    def _on_context_menu(self, pos) -> None:
        menu = QMenu(self)
        act_copy_all = menu.addAction("Copy All Chat")
        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen is act_copy_all:
            QApplication.clipboard().setText(self.get_all_plain_text())


class AIChatPanel(QDockWidget):
    """Dock widget providing an AI chat interface powered by Ollama."""

    chat_requested = pyqtSignal(list)  # full message history (list[dict])
    chat_stop_requested = pyqtSignal()  # request to cancel current stream
    code_insert_requested = pyqtSignal(str)  # code text to insert into editor

    def __init__(self, parent=None):
        super().__init__("AI Chat", parent)
        self.setObjectName("AIChatPanel")
        self.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea
            | Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.BottomDockWidgetArea
        )

        self._messages: list[dict] = []
        self._streaming = False
        self._current_assistant_text = ""
        self._streaming_bubble: "_Bubble | None" = None  # in-place updated bubble
        self._code_blocks: list[str] = []  # extracted code blocks for insert
        self._accent_hex = "#2F7A44"
        self._is_dark_theme = True

        # Context-aware help: current file info appended to system prompt
        self._context_file: str = ""   # e.g. "calculator.py"
        self._context_func: str = ""   # e.g. "def add(a, b):"
        self._context_line: int = -1   # 0-based cursor line
        self._context_text: str = ""   # current file contents (truncated)

        self._setup_ui()

    # -- UI construction ---------------------------------------------

    def _setup_ui(self) -> None:
        # -- custom dock title bar --------------------------------------
        # Mirrors File Explorer / Output panels: a QFrame title bar
        # installed as the dock's title widget (keeping the dock draggable)
        # with rounded top corners + border-top/left/right. The content
        # below lives in a QFrame container with matching bottom styling.
        title_bar = QFrame()
        title_bar.setObjectName("aiChatTitleBar")
        title_bar.setFrameShape(QFrame.Shape.NoFrame)
        title_bar.setFixedHeight(40)
        header_layout = QHBoxLayout(title_bar)
        header_layout.setContentsMargins(10, 2, 6, 8)
        header_layout.setSpacing(8)

        self._brand_icon = QLabel()
        self._brand_icon.setObjectName("aiChatBrandIcon")
        self._brand_icon.setFixedSize(16, 16)
        header_layout.addWidget(self._brand_icon)

        self._title_label = QLabel("AI Assistant")
        self._title_label.setObjectName("aiChatTitleLabel")
        header_layout.addWidget(self._title_label)

        header_layout.addStretch()

        self._status_dot = QLabel()
        self._status_dot.setObjectName("aiChatStatusDot")
        self._status_dot.setFixedSize(8, 8)
        header_layout.addWidget(self._status_dot)

        self._model_label = QLabel("ollama")
        self._model_label.setObjectName("aiChatModelLabel")
        self._model_label.setToolTip("Currently selected Ollama AI model")
        header_layout.addWidget(self._model_label)

        self._clear_btn = QToolButton()
        self._clear_btn.setObjectName("aiChatClearBtn")
        self._clear_btn.setText("\u2715")
        self._clear_btn.setToolTip("Clear the conversation and start fresh")
        self._clear_btn.setFixedSize(22, 22)
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.clicked.connect(self.clear_chat)
        header_layout.addWidget(self._clear_btn)

        self.setTitleBarWidget(title_bar)
        self._title_bar = title_bar

        # -- main container (rounded bottom corners, border l/r/bottom) -
        container = QFrame()
        container.setObjectName("aiChatContainer")
        container.setFrameShape(QFrame.Shape.NoFrame)
        layout = QVBoxLayout(container)
        # Bottom padding so inner widgets' square corners don't cover
        # the container's rounded bottom corners.
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(0)

        # Default visual state — will be refreshed when theme/connection info arrives
        self._set_status_dot(False)
        self._refresh_brand_icon()

        # Chat view — bubble-based message list
        self._chat_view = _ChatView()
        self._chat_view.link_clicked.connect(self._on_link_clicked_str)
        layout.addWidget(self._chat_view, 1)

        # Input area — text field with button overlaid at bottom-right
        input_container = QWidget()
        input_container.setObjectName("aiChatInputContainer")
        input_outer = QVBoxLayout(input_container)
        input_outer.setContentsMargins(8, 6, 8, 8)
        input_outer.setSpacing(6)

        self._input_area = _ChatInput()
        self._input_area.setObjectName("aiChatInput")
        self._input_area.setPlaceholderText("Ask a question about your code...")
        self._input_area.setMaximumHeight(100)
        self._input_area.setMinimumHeight(60)
        self._input_area.setToolTip(
            "Type your question here \u2014 press Enter to send, Shift+Enter for a new line"
        )
        self._input_area.submit_pressed.connect(self._on_send)
        self._input_area.textChanged.connect(self._update_send_btn)
        input_outer.addWidget(self._input_area, 1)

        # Button row below the input
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(6)

        self._hint_label = QLabel("Enter to send, Shift+Enter for new line")
        self._hint_label.setObjectName("aiChatHint")
        btn_row.addWidget(self._hint_label)
        btn_row.addStretch()

        self._btn_stack = QStackedWidget()
        self._btn_stack.setFixedWidth(76)
        # The stack needs a couple of extra pixels beyond the button's
        # own natural height so Qt has room to render the bottom rounded
        # corners of the QPushButton (otherwise they get drawn flat).
        self._btn_stack.setFixedHeight(36)

        self._send_btn = QPushButton("Send")
        self._send_btn.setObjectName("aiChatSendBtn")
        self._send_btn.setToolTip("Send your message (Enter)")
        self._send_btn.setEnabled(False)
        self._send_btn.setMinimumHeight(32)
        self._send_btn.clicked.connect(self._on_send)
        self._btn_stack.addWidget(self._send_btn)  # index 0

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("aiChatStopBtn")
        self._stop_btn.setToolTip("Stop the AI response")
        self._stop_btn.setMinimumHeight(32)
        self._stop_btn.clicked.connect(self._on_stop)
        self._btn_stack.addWidget(self._stop_btn)  # index 1

        self._btn_stack.setCurrentIndex(0)
        btn_row.addWidget(self._btn_stack)

        input_outer.addLayout(btn_row)

        layout.addWidget(input_container)

        self.setWidget(container)

    # -- Public API (called by MainWindow) ---------------------------

    _MAX_CONTEXT_CHARS = 8000  # cap so huge files don't blow the context window

    def update_editor_context(
        self,
        filename: str = "",
        function_name: str = "",
        cursor_line: int = -1,
        file_text: str = "",
    ) -> None:
        """Update the current editor context for context-aware AI help.

        Called by MainWindow whenever the active tab or cursor position changes.
        """
        self._context_file = filename
        self._context_func = function_name
        self._context_line = cursor_line
        if len(file_text) > self._MAX_CONTEXT_CHARS:
            half = self._MAX_CONTEXT_CHARS // 2
            self._context_text = (
                file_text[:half]
                + "\n\n... [middle of file omitted to fit context window] ...\n\n"
                + file_text[-half:]
            )
        else:
            self._context_text = file_text

    def _build_system_prompt(self) -> str:
        """Build the system prompt, including editor context when available."""
        parts = [_BASE_SYSTEM_PROMPT]

        context_bits: list[str] = []
        if self._context_file:
            context_bits.append(f"file \"{self._context_file}\"")
        if self._context_func:
            context_bits.append(f"inside \"{self._context_func}\"")
        if self._context_line >= 0:
            context_bits.append(f"at line {self._context_line + 1}")

        if context_bits:
            parts.append(
                "\n\nThe user is currently editing "
                + ", ".join(context_bits) + "."
            )

        # Include the actual file contents so the model isn't guessing.
        if self._context_text.strip():
            fence_lang = ""
            if self._context_file.endswith(".py"):
                fence_lang = "python"
            parts.append(
                f"\n\nHere are the current contents of {self._context_file or 'the file'} "
                "(this is the source of truth — do not invent or assume code that isn't shown):\n\n"
                f"```{fence_lang}\n{self._context_text}\n```"
            )

        return "".join(parts)

    def set_model_name(self, model: str) -> None:
        """Update the model label in the header: ``ollama \u00B7 modelname``."""
        if model:
            self._model_label.setText(f"ollama \u00B7 {model}")
        else:
            self._model_label.setText("ollama")

    def set_connected(self, connected: bool) -> None:
        """Enable / disable input based on connection state."""
        self._input_area.setEnabled(connected)
        if not connected:
            self._send_btn.setEnabled(False)
        else:
            self._update_send_btn()
        self._set_status_dot(connected)
        if not connected:
            self._model_label.setText("ollama")

    def apply_accent(self, accent_hex: str, is_dark: bool = True) -> None:
        """Update accent-tinted visuals (sparkle, status dot, bubbles) to theme."""
        self._accent_hex = accent_hex
        self._is_dark_theme = is_dark
        self._refresh_brand_icon()
        connected = self._input_area.isEnabled()
        self._set_status_dot(connected)
        # Re-render chat so bubble colors follow the theme
        self._render_chat()

    def _refresh_brand_icon(self) -> None:
        icon = load_tinted_icon("ai_sparkle", self._accent_hex, size=16)
        pix = icon.pixmap(16, 16)
        self._brand_icon.setPixmap(pix)

    def _set_status_dot(self, connected: bool) -> None:
        color = self._accent_hex if connected else "#6B6B6B"
        self._status_dot.setStyleSheet(
            f"background: {color}; border-radius: 4px;"
        )

    def append_token(self, token: str) -> None:
        """Append a single streamed token to the current assistant message.

        Updates the existing streaming bubble in place to avoid rebuilding the
        entire chat view (and the visual jumpiness that caused) for each token.
        """
        self._current_assistant_text += token

        # First token of the response: do a full render to insert the bubble
        # and capture a reference to it.
        if self._streaming_bubble is None:
            self._render_chat()
            return

        # Subsequent tokens: just rewrite the streaming bubble's contents.
        content_html = self._format_content_html(
            self._current_assistant_text, allow_insert=False
        )
        content_html += '<span style="opacity: 0.55;"> █</span>'
        self._streaming_bubble.set_html(content_html)

        if self._chat_view.is_at_bottom(slack=80):
            QTimer.singleShot(0, self._scroll_to_bottom)

    def finish_response(self) -> None:
        """Called when the AI stream completes."""
        # Save the complete assistant message into history
        if self._current_assistant_text:
            self._messages.append({
                "role": "assistant",
                "content": self._current_assistant_text,
            })
        self._current_assistant_text = ""
        self._streaming = False
        self._streaming_bubble = None
        self._input_area.setEnabled(True)
        self._update_send_btn()
        self._update_btn_visibility()
        self._input_area.setFocus()
        self._render_chat()

    def show_error(self, message: str) -> None:
        """Display an error in the chat and re-enable input."""
        self._current_assistant_text = ""
        self._streaming = False
        self._streaming_bubble = None
        self._input_area.setEnabled(True)
        self._update_send_btn()
        self._update_btn_visibility()
        self._input_area.setFocus()

        # Append a visual error block
        self._messages.append({
            "role": "error",
            "content": message,
        })
        self._render_chat()

    def send_message_programmatic(self, text: str) -> None:
        """Send a message as if the user typed it (used by context menu actions).

        Shows the chat panel, appends the message, and emits chat_requested
        so the AI responds immediately.
        """
        if not text.strip() or self._streaming:
            return

        # Make the panel visible
        self.show()
        self.raise_()

        # Append user message
        self._messages.append({"role": "user", "content": text})
        self._trim_history()

        # Set streaming state
        self._streaming = True
        self._send_btn.setEnabled(False)
        self._update_btn_visibility()
        self._current_assistant_text = ""

        # Render so the user sees the message
        self._render_chat()

        # Build the full message list (system prompt + history)
        full_messages = [{"role": "system", "content": self._build_system_prompt()}]
        for msg in self._messages:
            if msg["role"] in ("user", "assistant"):
                full_messages.append(msg)

        self.chat_requested.emit(full_messages)

    def clear_chat(self) -> None:
        """Reset the conversation."""
        self._messages.clear()
        self._code_blocks.clear()
        self._current_assistant_text = ""
        self._streaming = False
        self._streaming_bubble = None
        self._chat_view.clear()
        self._input_area.setEnabled(True)
        self._update_send_btn()
        self._update_btn_visibility()
        self._input_area.setFocus()


    # -- Internal ----------------------------------------------------

    def _scroll_to_bottom(self) -> None:
        """Scroll the chat view to the very bottom."""
        self._chat_view.scroll_to_bottom()

    def _on_link_clicked_str(self, href: str) -> None:
        """Handle bubble-label clicks — href is a raw string from QLabel."""
        url = QUrl(href)
        if url.scheme() == "meadowpy" and url.host() == "insert-code":
            try:
                idx = int(url.path().lstrip("/"))
                if 0 <= idx < len(self._code_blocks):
                    self.code_insert_requested.emit(self._code_blocks[idx])
            except (ValueError, IndexError):
                pass

    def _format_content_html(
        self, raw_content: str, *, allow_insert: bool = False
    ) -> str:
        """Convert message content to HTML, styling fenced code blocks.

        If *allow_insert* is True, each code block gets an 'Insert Code'
        link that triggers ``code_insert_requested``.

        Falls back to detecting triple-quoted strings (``\"\"\"...\"\"\"``)
        when no fenced code blocks are found.
        """
        # Choose which regex to use: prefer fenced blocks, fall back to
        # triple-quoted strings when the AI omits backtick fences.
        matches = list(_CODE_BLOCK_RE.finditer(raw_content))
        use_fallback = len(matches) == 0
        if use_fallback:
            matches = list(_TRIPLE_QUOTE_RE.finditer(raw_content))

        parts: list[str] = []
        last_end = 0

        for match in matches:
            # Text before this code block
            before = raw_content[last_end:match.start()]
            parts.append(
                html.escape(before).replace("\n", "<br>")
            )

            # Extract the code text
            if use_fallback:
                # Fallback: entire match is the triple-quoted string
                code_text = match.group(1).rstrip("\n")
            else:
                # Fenced: group 1 (normal) or group 2 (inline)
                code_text = (
                    match.group(1) or match.group(2) or ""
                ).rstrip("\n")

            code_html = html.escape(code_text)
            block_idx = len(self._code_blocks)
            self._code_blocks.append(code_text)

            insert_link = ""
            if allow_insert:
                insert_link = (
                    f'<div style="text-align:right; margin-top:2px;">'
                    f'<a href="meadowpy://insert-code/{block_idx}" '
                    f'style="color:#4A90D9; text-decoration:none; '
                    f'font-size:11px;">Insert at Cursor Position \u21B5</a></div>'
                )

            parts.append(
                f'<div class="code-block">'
                f'<pre style="margin:4px 0; padding:6px; '
                f'border-radius:4px; overflow-x:auto; '
                f'font-family:Consolas,monospace; font-size:12px;">'
                f'{code_html}</pre>'
                f'{insert_link}'
                f'</div>'
            )
            last_end = match.end()

        # Text after the last code block (or entire text if no blocks)
        remaining = raw_content[last_end:]
        parts.append(
            html.escape(remaining).replace("\n", "<br>")
        )

        return "".join(parts)

    def _update_send_btn(self) -> None:
        """Enable Send only when there is text and not streaming."""
        has_text = bool(self._input_area.toPlainText().strip())
        self._send_btn.setEnabled(has_text and not self._streaming)

    def _update_btn_visibility(self) -> None:
        """Toggle between Send and Stop buttons based on streaming state."""
        self._btn_stack.setCurrentIndex(1 if self._streaming else 0)

    def _on_stop(self) -> None:
        """Handle the user pressing Stop."""
        self.chat_stop_requested.emit()

        # Save whatever partial response was received
        if self._current_assistant_text:
            self._messages.append({
                "role": "assistant",
                "content": self._current_assistant_text,
            })
        self._current_assistant_text = ""

        # Record the stop in chat history
        self._messages.append({
            "role": "stopped",
            "content": "Response stopped by user.",
        })

        self._streaming = False
        self._streaming_bubble = None
        self._input_area.setEnabled(True)
        self._update_send_btn()
        self._update_btn_visibility()
        self._input_area.setFocus()
        self._render_chat()

    def _on_send(self) -> None:
        """Handle the user pressing Send / Enter."""
        text = self._input_area.toPlainText().strip()
        if not text or self._streaming:
            return

        # Append user message
        self._messages.append({"role": "user", "content": text})
        self._trim_history()

        # Clear input and disable while streaming
        self._input_area.clear()
        self._streaming = True
        self._send_btn.setEnabled(False)
        self._update_btn_visibility()
        self._current_assistant_text = ""

        # Render immediately so the user sees their message
        self._render_chat()

        # Build the full message list (system prompt + history)
        full_messages = [{"role": "system", "content": self._build_system_prompt()}]
        for msg in self._messages:
            if msg["role"] in ("user", "assistant"):
                full_messages.append(msg)

        self.chat_requested.emit(full_messages)

    def _trim_history(self) -> None:
        """Keep only the last MAX_HISTORY_MESSAGES messages."""
        # Only trim user/assistant messages (skip errors)
        while len(self._messages) > MAX_HISTORY_MESSAGES:
            self._messages.pop(0)

    def _render_chat(self) -> None:
        """Rebuild the bubble list from message history."""
        # Reset code block index — blocks are re-collected during rendering
        self._code_blocks.clear()

        at_bottom = self._chat_view.is_at_bottom()
        self._chat_view.clear()

        for msg in self._messages:
            role = msg["role"]

            if role == "user":
                content_html = html.escape(msg["content"]).replace("\n", "<br>")
                self._chat_view.add_bubble("user", content_html)
            elif role == "assistant":
                content_html = self._format_content_html(
                    msg["content"], allow_insert=True
                )
                self._chat_view.add_bubble("ai", content_html)
            elif role == "error":
                content_html = html.escape(msg["content"]).replace("\n", "<br>")
                self._chat_view.add_centered(
                    f"<i>{content_html}</i>", "aiChatErrorLabel"
                )
            elif role == "stopped":
                self._chat_view.add_centered(
                    f"<i>{html.escape(msg['content'])}</i>", "aiChatStoppedLabel"
                )

        # Append the in-progress assistant text (if streaming) and remember
        # the bubble so append_token can update it in place.
        self._streaming_bubble = None
        if self._streaming and self._current_assistant_text:
            content_html = self._format_content_html(
                self._current_assistant_text, allow_insert=False
            )
            content_html += '<span style="opacity: 0.55;"> \u2588</span>'
            self._streaming_bubble = self._chat_view.add_bubble("ai", content_html)
        elif self._streaming:
            self._streaming_bubble = self._chat_view.add_bubble(
                "ai", '<span style="opacity: 0.6;">Thinking\u2026</span>',
            )

        if at_bottom or self._streaming:
            QTimer.singleShot(0, self._scroll_to_bottom)

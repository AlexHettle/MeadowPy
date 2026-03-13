"""AI Chat sidebar panel — ask questions about your code via Ollama."""

import html
import re

from PyQt6.QtCore import QEvent, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QKeySequence
from PyQt6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

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


class _ChatDisplay(QTextBrowser):
    """QTextBrowser with robust copy / select-all support.

    Provides three layers of copy support:
    1. ShortcutOverride -- prevents Qt from consuming Ctrl+C/A before
       the widget sees them.
    2. keyPressEvent -- explicit copy/selectAll handling as a fallback.
    3. Context menu -- right-click Copy / Select All / Copy All Chat.
    """

    def event(self, e) -> bool:
        if e.type() == QEvent.Type.ShortcutOverride:
            # ShortcutOverride events are always QKeyEvent instances in Qt.
            # Guard with isinstance so we never call matches() on a bare QEvent.
            if isinstance(e, QKeyEvent):
                if e.matches(QKeySequence.StandardKey.Copy) or                    e.matches(QKeySequence.StandardKey.SelectAll):
                    e.accept()
                    return True
        return super().event(e)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copy()
            return
        if event.matches(QKeySequence.StandardKey.SelectAll):
            self.selectAll()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event) -> None:
        """Custom context menu with Copy, Select All, and Copy All Chat."""
        menu = self.createStandardContextMenu()
        menu.addSeparator()
        copy_all = menu.addAction("Copy All Chat")
        copy_all.triggered.connect(self._copy_all_to_clipboard)
        menu.exec(event.globalPos())

    def _copy_all_to_clipboard(self) -> None:
        """Copy all chat text to clipboard."""
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(self.toPlainText())


class AIChatPanel(QDockWidget):
    """Dock widget providing an AI chat interface powered by Ollama."""

    chat_requested = pyqtSignal(list)  # full message history (list[dict])
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
        self._code_blocks: list[str] = []  # extracted code blocks for insert

        # Context-aware help: current file info appended to system prompt
        self._context_file: str = ""   # e.g. "calculator.py"
        self._context_func: str = ""   # e.g. "def add(a, b):"
        self._context_line: int = -1   # 0-based cursor line

        self._setup_ui()

    # -- UI construction ---------------------------------------------

    def _setup_ui(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setObjectName("aiChatHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 6, 8, 6)

        self._model_label = QLabel("No model selected")
        self._model_label.setObjectName("aiChatModelLabel")
        self._model_label.setToolTip("Currently selected Ollama AI model")
        header_layout.addWidget(self._model_label)

        header_layout.addStretch()

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setObjectName("aiChatClearBtn")
        self._clear_btn.setToolTip("Clear the conversation and start fresh")
        self._clear_btn.setFixedHeight(24)
        self._clear_btn.clicked.connect(self.clear_chat)
        header_layout.addWidget(self._clear_btn)

        layout.addWidget(header)

        # Chat display
        self._chat_display = _ChatDisplay()
        self._chat_display.setObjectName("aiChatDisplay")
        self._chat_display.setOpenExternalLinks(False)
        self._chat_display.setOpenLinks(False)  # we handle links ourselves
        self._chat_display.setReadOnly(True)
        # QTextBrowser defaults to TextBrowserInteraction which omits
        # TextSelectableByKeyboard — so Ctrl+C / Ctrl+A won't work.
        # Add it explicitly to enable keyboard copy/select-all.
        self._chat_display.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self._chat_display.setPlaceholderText(
            "Ask a question about your code!\n\n"
            "Try things like:\n"
            '  \u2022 "What is a class?"\n'
            '  \u2022 "How do I create a list?"\n'
            '  \u2022 "Explain the for loop"'
        )
        self._chat_display.anchorClicked.connect(self._on_link_clicked)
        layout.addWidget(self._chat_display, 1)

        # Input area
        input_container = QWidget()
        input_container.setObjectName("aiChatInputContainer")
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(6, 6, 6, 6)
        input_layout.setSpacing(6)

        self._input_area = _ChatInput()
        self._input_area.setObjectName("aiChatInput")
        self._input_area.setPlaceholderText("Ask a question about your code...")
        self._input_area.setMaximumHeight(80)
        self._input_area.setToolTip(
            "Type your question here \u2014 press Enter to send, Shift+Enter for a new line"
        )
        self._input_area.submit_pressed.connect(self._on_send)
        input_layout.addWidget(self._input_area, 1)

        self._send_btn = QPushButton("Send")
        self._send_btn.setObjectName("aiChatSendBtn")
        self._send_btn.setToolTip("Send your message (Enter)")
        self._send_btn.setFixedHeight(36)
        self._send_btn.setFixedWidth(60)
        self._send_btn.setEnabled(False)
        self._send_btn.clicked.connect(self._on_send)
        self._input_area.textChanged.connect(self._update_send_btn)
        input_layout.addWidget(self._send_btn, 0, Qt.AlignmentFlag.AlignBottom)

        layout.addWidget(input_container)

        self.setWidget(container)

    # -- Public API (called by MainWindow) ---------------------------

    def update_editor_context(
        self,
        filename: str = "",
        function_name: str = "",
        cursor_line: int = -1,
    ) -> None:
        """Update the current editor context for context-aware AI help.

        Called by MainWindow whenever the active tab or cursor position changes.
        """
        self._context_file = filename
        self._context_func = function_name
        self._context_line = cursor_line

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

        return "".join(parts)

    def set_model_name(self, model: str) -> None:
        """Update the model label in the header."""
        if model:
            self._model_label.setText(f"Model: {model}")
        else:
            self._model_label.setText("No model selected")

    def set_connected(self, connected: bool) -> None:
        """Enable / disable input based on connection state."""
        self._input_area.setEnabled(connected)
        if not connected:
            self._send_btn.setEnabled(False)
        else:
            self._update_send_btn()
        if not connected:
            self._model_label.setText("Ollama")

    def append_token(self, token: str) -> None:
        """Append a single streamed token to the current assistant message."""
        self._current_assistant_text += token
        self._render_chat()

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
        self._input_area.setEnabled(True)
        self._update_send_btn()
        self._input_area.setFocus()
        self._render_chat()

    def show_error(self, message: str) -> None:
        """Display an error in the chat and re-enable input."""
        self._current_assistant_text = ""
        self._streaming = False
        self._input_area.setEnabled(True)
        self._update_send_btn()
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
        self._chat_display.clear()
        self._input_area.setEnabled(True)
        self._update_send_btn()
        self._input_area.setFocus()


    # -- Internal ----------------------------------------------------

    def _scroll_to_bottom(self) -> None:
        """Scroll the chat display to the very bottom."""
        sb = self._chat_display.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_link_clicked(self, url: QUrl) -> None:
        """Handle clicks on custom links (e.g. Insert Code buttons)."""
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
        """Re-render the full chat HTML from message history."""
        # Reset code block index — blocks are re-collected during rendering
        self._code_blocks.clear()

        parts: list[str] = []

        for msg in self._messages:
            role = msg["role"]

            if role == "user":
                content_html = html.escape(msg["content"]).replace(
                    "\n", "<br>"
                )
                parts.append(
                    f'<div class="user-message">'
                    f'<b>You:</b><br>{content_html}'
                    f'</div>'
                )
            elif role == "assistant":
                content_html = self._format_content_html(
                    msg["content"], allow_insert=True
                )
                parts.append(
                    f'<div class="assistant-message">'
                    f'<b>AI:</b><br>{content_html}'
                    f'</div>'
                )
            elif role == "error":
                content_html = html.escape(msg["content"]).replace(
                    "\n", "<br>"
                )
                parts.append(
                    f'<div class="error-message">'
                    f'<b>Error:</b> <i>{content_html}</i>'
                    f'</div>'
                )

        # Append the in-progress assistant text (if streaming)
        if self._streaming and self._current_assistant_text:
            # No insert buttons while still streaming
            content_html = self._format_content_html(
                self._current_assistant_text, allow_insert=False
            )
            parts.append(
                f'<div class="assistant-message">'
                f'<b>AI:</b><br>{content_html}'
                f'<span class="streaming-indicator"> \u2588</span>'
                f'</div>'
            )
        elif self._streaming:
            # Waiting for first token
            parts.append(
                f'<div class="assistant-message">'
                f'<b>AI:</b> <span class="streaming-indicator">'
                f'Thinking\u2026</span>'
                f'</div>'
            )

        full_html = (
            '<style>'
            '.user-message { margin: 8px 4px; padding: 8px; '
            'border-radius: 6px; }'
            '.assistant-message { margin: 8px 4px; padding: 8px; '
            'border-radius: 6px; }'
            '.error-message { margin: 8px 4px; padding: 8px; '
            'color: #E51400; }'
            '.streaming-indicator { opacity: 0.5; }'
            '.code-block { margin: 6px 0; }'
            '.code-block pre { background: rgba(0,0,0,0.15); }'
            '</style>'
            + "\n".join(parts)
        )

        # Preserve scroll position if user scrolled up.
        # During streaming always auto-scroll to the bottom.
        scrollbar = self._chat_display.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum() - 20

        self._chat_display.setHtml(full_html)

        if at_bottom or self._streaming:
            # Defer scroll to after Qt recalculates the layout,
            # because setHtml() resets the scrollbar and the new
            # maximum isn't available until the next event-loop tick.
            QTimer.singleShot(0, self._scroll_to_bottom)

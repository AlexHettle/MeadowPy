"""AI Chat sidebar panel — ask questions about your code via Ollama."""

import html
import re

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtWidgets import (
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from meadowpy.resources.resource_loader import load_tinted_icon
from meadowpy.ui.ai_chat_widgets import ChatBubble, ChatInput, ChatView
from meadowpy.ui.panel_title_bar import (
    PANEL_TITLE_CONTENT_HEIGHT,
    PANEL_TITLE_CONTROL_SIZE,
    configure_panel_title_bar,
    configure_panel_title_label,
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


class AIChatPanel(QDockWidget):
    """Dock widget providing an AI chat interface powered by Ollama."""

    chat_requested = pyqtSignal(list)  # full message history (list[dict])
    chat_stop_requested = pyqtSignal()  # request to cancel current stream
    code_insert_requested = pyqtSignal(str)  # code text to insert into editor
    setup_requested = pyqtSignal()  # request to open Ollama setup

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
        self._shutting_down = False
        self._current_assistant_text = ""
        self._streaming_bubble: ChatBubble | None = None  # in-place updated bubble
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
        header_layout = QHBoxLayout(title_bar)
        configure_panel_title_bar(title_bar, header_layout, spacing=8)

        self._brand_icon = QLabel()
        self._brand_icon.setObjectName("aiChatBrandIcon")
        self._brand_icon.setFixedSize(16, 16)
        header_layout.addWidget(self._brand_icon, 0, Qt.AlignmentFlag.AlignVCenter)

        self._title_label = QLabel("AI Assistant")
        self._title_label.setObjectName("aiChatTitleLabel")
        configure_panel_title_label(self._title_label)
        header_layout.addWidget(self._title_label, 0, Qt.AlignmentFlag.AlignVCenter)

        header_layout.addStretch()

        self._status_dot_slot = QWidget()
        self._status_dot_slot.setObjectName("aiChatStatusDotSlot")
        self._status_dot_slot.setFixedSize(12, PANEL_TITLE_CONTENT_HEIGHT)
        status_dot_layout = QHBoxLayout(self._status_dot_slot)
        status_dot_layout.setContentsMargins(2, 4, 2, 0)
        status_dot_layout.setSpacing(0)

        self._status_dot = QLabel()
        self._status_dot.setObjectName("aiChatStatusDot")
        self._status_dot.setFixedSize(8, 8)
        self._status_dot.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        status_dot_layout.addWidget(
            self._status_dot, 0, Qt.AlignmentFlag.AlignCenter
        )
        header_layout.addWidget(
            self._status_dot_slot, 0, Qt.AlignmentFlag.AlignVCenter
        )

        self._model_label = QLabel("ollama")
        self._model_label.setObjectName("aiChatModelLabel")
        configure_panel_title_label(self._model_label)
        self._model_label.setToolTip("Currently selected Ollama AI model")
        header_layout.addWidget(self._model_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self._setup_btn = QPushButton("Setup")
        self._setup_btn.setObjectName("aiChatSetupBtn")
        self._setup_btn.setToolTip("Set up or check Ollama")
        self._setup_btn.setFixedHeight(PANEL_TITLE_CONTENT_HEIGHT)
        self._setup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_btn.clicked.connect(self.setup_requested.emit)
        header_layout.addWidget(self._setup_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self._clear_btn = QToolButton()
        self._clear_btn.setObjectName("aiChatClearBtn")
        self._clear_btn.setText("\u2715")
        self._clear_btn.setToolTip("Clear the conversation and start fresh")
        self._clear_btn.setFixedSize(PANEL_TITLE_CONTROL_SIZE, PANEL_TITLE_CONTROL_SIZE)
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.clicked.connect(self.clear_chat)
        header_layout.addWidget(self._clear_btn, 0, Qt.AlignmentFlag.AlignVCenter)

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
        self._chat_view = ChatView()
        self._chat_view.link_clicked.connect(self._on_link_clicked_str)
        layout.addWidget(self._chat_view, 1)

        # Input area — text field with button overlaid at bottom-right
        input_container = QWidget()
        input_container.setObjectName("aiChatInputContainer")
        input_outer = QVBoxLayout(input_container)
        input_outer.setContentsMargins(8, 6, 8, 8)
        input_outer.setSpacing(6)

        self._input_area = ChatInput()
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
        self._setup_btn.setVisible(not connected)

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
        tooltip = "Ollama is connected" if connected else "Ollama is offline"
        self._status_dot.setStyleSheet(
            f"background: {color}; border-radius: 4px;"
        )
        self._status_dot_slot.setToolTip(tooltip)

    def append_token(self, token: str) -> None:
        """Append a single streamed token to the current assistant message.

        Updates the existing streaming bubble in place to avoid rebuilding the
        entire chat view (and the visual jumpiness that caused) for each token.
        """
        if self._shutting_down:
            return

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
        if self._shutting_down:
            return

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
        if self._shutting_down:
            return

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
        if self._shutting_down:
            return

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

    def prepare_for_shutdown(self) -> None:
        """Ignore late AI stream updates while the main window is closing."""
        self._shutting_down = True
        self._streaming = False
        if self._streaming_bubble is not None:
            self._streaming_bubble.stop_loading()
        self._streaming_bubble = None
        self._current_assistant_text = ""

    # -- Internal ----------------------------------------------------

    def _scroll_to_bottom(self) -> None:
        """Scroll the chat view to the very bottom."""
        if self._shutting_down:
            return
        try:
            self._chat_view.scroll_to_bottom()
        except RuntimeError:
            # A queued singleShot can fire after child widgets start teardown.
            pass

    def _set_chat_updates_enabled(self, enabled: bool) -> None:
        try:
            self._chat_view.setUpdatesEnabled(enabled)
        except RuntimeError:
            # The panel can be torn down while delayed scroll restores are queued.
            pass

    def _restore_chat_scroll(
        self,
        previous_value: int,
        *,
        to_bottom: bool,
        reenable_updates: bool = False,
    ) -> None:
        """Restore chat scroll after the bubble layout has been rebuilt."""
        if self._shutting_down:
            return

        def restore(*, enable_updates: bool = False) -> None:
            if self._shutting_down:
                return
            try:
                if to_bottom:
                    self._chat_view.scroll_to_bottom()
                else:
                    self._chat_view.scroll_to_value(previous_value)
            except RuntimeError:
                # A queued restore can fire after child widgets start teardown.
                pass
            finally:
                if enable_updates:
                    self._set_chat_updates_enabled(True)

        restore()
        QTimer.singleShot(0, restore)
        if reenable_updates:
            QTimer.singleShot(20, lambda: restore(enable_updates=True))
            QTimer.singleShot(60, restore)
        else:
            QTimer.singleShot(20, restore)

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
                link_color = html.escape(self._accent_hex, quote=True)
                insert_link = (
                    f'<div style="text-align:right; margin-top:2px;">'
                    f'<a href="meadowpy://insert-code/{block_idx}" '
                    f'style="color:{link_color}; text-decoration:none; '
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
        if self._shutting_down:
            return

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
        if self._shutting_down:
            return

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
        if self._shutting_down:
            return

        # Reset code block index — blocks are re-collected during rendering
        self._code_blocks.clear()

        previous_scroll = self._chat_view.scroll_value()
        restore_to_bottom = self._streaming or self._chat_view.is_at_bottom(slack=80)
        updates_were_enabled = self._chat_view.updatesEnabled()
        if updates_were_enabled:
            self._set_chat_updates_enabled(False)

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
            self._streaming_bubble = self._chat_view.add_loading_bubble(
                self._accent_hex,
            )

        self._restore_chat_scroll(
            previous_scroll,
            to_bottom=restore_to_bottom,
            reenable_updates=updates_were_enabled,
        )

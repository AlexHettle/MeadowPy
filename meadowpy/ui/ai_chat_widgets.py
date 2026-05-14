"""Reusable widgets for the AI chat panel."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QTextDocument
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ChatInput(QPlainTextEdit):
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


class ChatBubble(QFrame):
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


class ChatView(QScrollArea):
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

    def add_bubble(self, role: str, html_content: str) -> ChatBubble:
        """Append a bubble aligned by role and return it."""
        bubble = ChatBubble(role)
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
                if isinstance(w, ChatBubble):
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
                if isinstance(w, ChatBubble):
                    w.setMaximumWidth(max_w)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._constrain_widths()

    def _on_context_menu(self, pos) -> None:
        copy_text = self.get_all_plain_text()
        menu = QMenu(self)
        act_copy_all = menu.addAction("Copy All Chat")
        act_copy_all.setEnabled(bool(copy_text))
        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen is act_copy_all and copy_text:
            QApplication.clipboard().setText(copy_text)

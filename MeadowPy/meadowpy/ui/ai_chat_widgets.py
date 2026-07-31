"""Reusable widgets for the AI chat panel."""

from PyQt6.QtCore import QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QKeyEvent, QPainter, QPen, QTextDocument
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


class LoadingSpinner(QWidget):
    """Small accent-colored spinner used while the AI prepares a response."""

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._angle = 0
        self.setFixedSize(14, 14)
        self.setAccessibleName("Loading")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._timer = QTimer(self)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._advance)
        self._timer.start()

    def _advance(self) -> None:
        self._angle = (self._angle - 30) % 360
        self.update()

    def stop(self) -> None:
        """Stop animation when the waiting state is no longer visible."""
        self._timer.stop()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self._color)
        pen.setWidthF(2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(
            QRectF(2, 2, self.width() - 4, self.height() - 4),
            self._angle * 16,
            270 * 16,
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

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(0)

        self._spinner: LoadingSpinner | None = None

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
        self.stop_loading()
        self._label.setText(html_content)

    def set_loading(self, accent_hex: str) -> None:
        """Show an animated spinner beside the temporary thinking label."""
        self.stop_loading()
        self._spinner = LoadingSpinner(accent_hex, self)
        layout = self.layout()
        layout.setSpacing(7)
        layout.insertWidget(
            0,
            self._spinner,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )
        self._label.setText('<span style="opacity: 0.6;">Thinking…</span>')

    def stop_loading(self) -> None:
        """Remove the spinner while preserving the bubble for streamed text."""
        if self._spinner is None:
            return
        spinner = self._spinner
        self._spinner = None
        spinner.stop()
        spinner.hide()
        self.layout().removeWidget(spinner)
        self.layout().setSpacing(0)
        spinner.deleteLater()

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
            layout = row.layout()
            for index in range(layout.count()):
                widget = layout.itemAt(index).widget()
                if isinstance(widget, ChatBubble):
                    widget.stop_loading()
            self._inner_layout.removeWidget(row)
            row.setParent(None)
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

    def add_loading_bubble(self, accent_hex: str) -> ChatBubble:
        """Append the animated AI waiting bubble and return it."""
        bubble = ChatBubble("ai")
        bubble.set_loading(accent_hex)
        bubble.link_clicked.connect(self.link_clicked.emit)
        self._append_row(bubble, align="left")
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

    def scroll_value(self) -> int:
        return self.verticalScrollBar().value()

    def scroll_to_value(self, value: int) -> None:
        sb = self.verticalScrollBar()
        value = max(sb.minimum(), min(value, sb.maximum()))
        sb.setValue(value)

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

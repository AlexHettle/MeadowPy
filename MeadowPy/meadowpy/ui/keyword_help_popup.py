"""Popup widget showing beginner-friendly keyword/builtin explanations."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QTextEdit,
    QVBoxLayout,
)


class KeywordHelpPopup(QFrame):
    """A floating popup that shows an explanation and example for a Python keyword."""

    def __init__(self, keyword: str, explanation: str, example: str, parent=None):
        super().__init__(parent)
        self.setObjectName("KeywordHelpPopup")
        self.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(380)
        self.setMaximumWidth(500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Keyword title
        title = QLabel(f"<b>{keyword}</b>")
        title.setObjectName("kwHelpTitle")
        title_font = QFont()
        title_font.setPointSize(13)
        title.setFont(title_font)
        layout.addWidget(title)

        # Explanation
        desc = QLabel(explanation)
        desc.setObjectName("kwHelpDesc")
        desc.setWordWrap(True)
        desc_font = QFont()
        desc_font.setPointSize(10)
        desc.setFont(desc_font)
        layout.addWidget(desc)

        # Example code
        example_label = QLabel("Example:")
        example_label.setObjectName("kwHelpExampleLabel")
        ex_label_font = QFont()
        ex_label_font.setPointSize(9)
        ex_label_font.setBold(True)
        example_label.setFont(ex_label_font)
        layout.addWidget(example_label)

        code = QTextEdit()
        code.setObjectName("kwHelpCode")
        code.setReadOnly(True)
        code.setFont(QFont("Consolas", 10))
        code.setPlainText(example)
        # Size to content — estimate line count
        line_count = example.count("\n") + 1
        code.setFixedHeight(min(max(line_count * 18 + 12, 50), 200))
        layout.addWidget(code)

        self.adjustSize()

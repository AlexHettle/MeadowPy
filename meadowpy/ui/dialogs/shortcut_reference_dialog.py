"""Keyboard shortcut reference dialog – v2 card-based layout with search."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


# (category, action, shortcut)
SHORTCUTS = [
    ("File", "New File", "Ctrl+N"),
    ("File", "Open File", "Ctrl+O"),
    ("File", "Open Folder", "Ctrl+Shift+K"),
    ("File", "Save", "Ctrl+S"),
    ("File", "Save As", "Ctrl+Shift+S"),
    ("File", "Close Tab", "Ctrl+W"),
    ("File", "Preferences", "Ctrl+,"),
    ("File", "Exit", "Ctrl+Q"),

    ("Edit", "Undo", "Ctrl+Z"),
    ("Edit", "Redo", "Ctrl+Y"),
    ("Edit", "Cut", "Ctrl+X"),
    ("Edit", "Copy", "Ctrl+C"),
    ("Edit", "Paste", "Ctrl+V"),
    ("Edit", "Select All", "Ctrl+A"),
    ("Edit", "Find", "Ctrl+F"),
    ("Edit", "Replace", "Ctrl+H"),
    ("Edit", "Search in Files", "Ctrl+Shift+F"),
    ("Edit", "Go to Line", "Ctrl+G"),

    ("View", "Zoom In", "Ctrl+="),
    ("View", "Zoom Out", "Ctrl+-"),
    ("View", "Reset Zoom", "Ctrl+0"),
    ("View", "File Explorer", "Ctrl+Shift+E"),
    ("View", "Symbol Outline", "Ctrl+Shift+O"),
    ("View", "Problems Panel", "Ctrl+Shift+M"),
    ("View", "Output Panel", "Ctrl+`"),

    ("Run", "Run File", "F5"),
    ("Run", "Run Selection / Line", "Shift+F5"),
    ("Run", "Stop Process", "Ctrl+F5"),

    ("Debug", "Start Debugging", "F6"),
    ("Debug", "Continue", "Ctrl+F6"),
    ("Debug", "Step Over", "F10"),
    ("Debug", "Step Into", "F11"),
    ("Debug", "Step Out", "Shift+F11"),
    ("Debug", "Stop Debugging", "Ctrl+Shift+F5"),
    ("Debug", "Toggle Breakpoint", "F9"),

    ("Help", "Example Library", "Ctrl+Shift+L"),
]

# Group shortcuts by category, preserving order.
def _grouped_shortcuts():
    groups = {}
    order = []
    for cat, action, shortcut in SHORTCUTS:
        if cat not in groups:
            groups[cat] = []
            order.append(cat)
        groups[cat].append((action, shortcut))
    return [(cat, groups[cat]) for cat in order]


class _KeyBadge(QLabel):
    """A single keyboard-key styled badge (e.g. 'Ctrl')."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("shortcutKeyBadge")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class _ShortcutRow(QFrame):
    """One action row: action label on the left, key badges on the right."""

    def __init__(self, action: str, shortcut: str, parent=None):
        super().__init__(parent)
        self.setObjectName("shortcutRow")
        self._action_text = action.lower()
        self._shortcut_text = shortcut.lower()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(6)

        action_label = QLabel(action)
        action_label.setObjectName("shortcutActionLabel")
        layout.addWidget(action_label, 1)

        # Build key badges from shortcut string (e.g. "Ctrl+Shift+S")
        keys = shortcut.split("+")
        for i, key in enumerate(keys):
            badge = _KeyBadge(key.strip())
            layout.addWidget(badge)
            if i < len(keys) - 1:
                plus = QLabel("+")
                plus.setObjectName("shortcutKeyPlus")
                layout.addWidget(plus)

    def matches_filter(self, text: str) -> bool:
        return text in self._action_text or text in self._shortcut_text


class _CategoryCard(QFrame):
    """A card for one shortcut category with a header and rows."""

    def __init__(self, category: str, items: list, parent=None):
        super().__init__(parent)
        self.setObjectName("shortcutCard")
        self._category_lower = category.lower()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Category header
        header = QLabel(category)
        header.setObjectName("shortcutCardHeader")
        header_font = QFont()
        header_font.setPointSize(11)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        # Separator line
        sep = QFrame()
        sep.setObjectName("shortcutCardSep")
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        # Shortcut rows
        self._rows: list[_ShortcutRow] = []
        for action, shortcut in items:
            row = _ShortcutRow(action, shortcut)
            self._rows.append(row)
            layout.addWidget(row)

    def apply_filter(self, text: str) -> bool:
        """Filter rows by *text*. Returns True if any row is visible."""
        if not text:
            for row in self._rows:
                row.setVisible(True)
            return True

        if text in self._category_lower:
            for row in self._rows:
                row.setVisible(True)
            return True

        any_visible = False
        for row in self._rows:
            vis = row.matches_filter(text)
            row.setVisible(vis)
            any_visible = any_visible or vis
        return any_visible


class ShortcutReferenceDialog(QDialog):
    """v2 keyboard-shortcuts dialog with search and card layout."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setObjectName("ShortcutReferenceDialog")
        self.setMinimumSize(560, 500)
        self.resize(620, 640)
        self._cards: list[_CategoryCard] = []
        self._setup_ui()

    # ---- UI construction ----

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(12)

        # Title
        title = QLabel("Keyboard Shortcuts")
        title.setObjectName("shortcutTitle")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        root.addWidget(title)

        subtitle = QLabel(
            "All available keyboard shortcuts, organized by category."
        )
        subtitle.setObjectName("shortcutSubtitle")
        sub_font = QFont()
        sub_font.setPointSize(10)
        subtitle.setFont(sub_font)
        root.addWidget(subtitle)

        # Search bar
        self._search = QLineEdit()
        self._search.setObjectName("shortcutSearch")
        self._search.setPlaceholderText("Search shortcuts...")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_filter)
        root.addWidget(self._search)

        # Scrollable card area
        scroll = QScrollArea()
        scroll.setObjectName("shortcutScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        container.setObjectName("shortcutContainer")
        self._card_layout = QVBoxLayout(container)
        self._card_layout.setContentsMargins(0, 0, 4, 0)
        self._card_layout.setSpacing(14)

        for category, items in _grouped_shortcuts():
            card = _CategoryCard(category, items)
            self._cards.append(card)
            self._card_layout.addWidget(card)

        self._card_layout.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        # No-results label (hidden by default)
        self._no_results = QLabel("No matching shortcuts found.")
        self._no_results.setObjectName("shortcutNoResults")
        self._no_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_results.setVisible(False)
        root.addWidget(self._no_results)

        # Close button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("shortcutCloseBtn")
        close_btn.setMinimumHeight(34)
        close_btn.setMinimumWidth(90)
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

    # ---- Filtering ----

    def _on_filter(self, text: str) -> None:
        query = text.strip().lower()
        any_visible = False
        for card in self._cards:
            vis = card.apply_filter(query)
            card.setVisible(vis)
            any_visible = any_visible or vis
        self._no_results.setVisible(not any_visible)

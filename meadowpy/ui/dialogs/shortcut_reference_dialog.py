"""Keyboard shortcut reference dialog."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
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


class ShortcutReferenceDialog(QDialog):
    """Shows all keyboard shortcuts in a searchable table."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setObjectName("ShortcutReferenceDialog")
        self.setMinimumSize(520, 480)
        self.resize(560, 540)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Title
        title = QLabel("Keyboard Shortcuts")
        title.setObjectName("shortcutTitle")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        subtitle = QLabel("All available keyboard shortcuts, organized by category.")
        subtitle.setObjectName("shortcutSubtitle")
        sub_font = QFont()
        sub_font.setPointSize(10)
        subtitle.setFont(sub_font)
        layout.addWidget(subtitle)

        # Table
        self._table = QTableWidget()
        self._table.setObjectName("shortcutTable")
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Category", "Action", "Shortcut"])
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        self._populate_table()
        layout.addWidget(self._table, 1)

        # Close button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("shortcutCloseBtn")
        close_btn.setMinimumHeight(34)
        close_btn.setMinimumWidth(90)
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _populate_table(self) -> None:
        self._table.setRowCount(len(SHORTCUTS))

        prev_category = ""
        for row, (category, action, shortcut) in enumerate(SHORTCUTS):
            # Only show category name on first row of each group
            cat_text = category if category != prev_category else ""
            prev_category = category

            cat_item = QTableWidgetItem(cat_text)
            cat_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            if cat_text:
                cat_font = QFont()
                cat_font.setBold(True)
                cat_item.setFont(cat_font)

            action_item = QTableWidgetItem(action)
            action_item.setFlags(Qt.ItemFlag.ItemIsEnabled)

            shortcut_item = QTableWidgetItem(shortcut)
            shortcut_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            shortcut_font = QFont("Consolas", 10)
            shortcut_item.setFont(shortcut_font)

            self._table.setItem(row, 0, cat_item)
            self._table.setItem(row, 1, action_item)
            self._table.setItem(row, 2, shortcut_item)

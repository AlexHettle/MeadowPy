"""Example Library dialog — browse and open beginner Python examples."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from meadowpy.resources.example_library import EXAMPLE_CATEGORIES


class ExampleLibraryDialog(QDialog):
    """Browsable library of categorized Python examples.

    Signals
    -------
    example_selected(str, str)
        User clicked Open.  Arguments: (tab_name, code).
    """

    example_selected = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Example Library")
        self.setObjectName("ExampleLibraryDialog")
        self.setMinimumSize(820, 520)
        self.resize(900, 580)
        self._current_code: str = ""
        self._current_name: str = ""
        self._setup_ui()
        self._populate_categories()

    # ── UI setup ──────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Title
        title = QLabel("Python Example Library")
        title.setObjectName("exLibTitle")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        subtitle = QLabel("Browse examples by category, preview the code, and open it in a new tab.")
        subtitle.setObjectName("exLibSubtitle")
        sub_font = QFont()
        sub_font.setPointSize(10)
        subtitle.setFont(sub_font)
        layout.addWidget(subtitle)

        # Main splitter: category list | example list | code preview
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("exLibSplitter")

        # Left: category list
        self._cat_list = QListWidget()
        self._cat_list.setObjectName("exLibCatList")
        self._cat_list.setMaximumWidth(180)
        self._cat_list.currentRowChanged.connect(self._on_category_changed)
        splitter.addWidget(self._cat_list)

        # Middle: example list
        self._example_list = QListWidget()
        self._example_list.setObjectName("exLibExampleList")
        self._example_list.setMaximumWidth(220)
        self._example_list.currentRowChanged.connect(self._on_example_changed)
        splitter.addWidget(self._example_list)

        # Right: code preview
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(6)

        self._preview_title = QLabel("")
        self._preview_title.setObjectName("exLibPreviewTitle")
        preview_title_font = QFont()
        preview_title_font.setPointSize(12)
        preview_title_font.setBold(True)
        self._preview_title.setFont(preview_title_font)
        preview_layout.addWidget(self._preview_title)

        self._preview_desc = QLabel("")
        self._preview_desc.setObjectName("exLibPreviewDesc")
        self._preview_desc.setWordWrap(True)
        preview_layout.addWidget(self._preview_desc)

        self._code_preview = QTextEdit()
        self._code_preview.setObjectName("exLibCodePreview")
        self._code_preview.setReadOnly(True)
        self._code_preview.setFont(QFont("Consolas", 10))
        preview_layout.addWidget(self._code_preview)

        splitter.addWidget(preview_widget)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 0)
        splitter.setStretchFactor(2, 1)

        layout.addWidget(splitter, 1)

        # Bottom buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._open_btn = QPushButton("Open in New Tab")
        self._open_btn.setObjectName("exLibOpenBtn")
        self._open_btn.setMinimumHeight(34)
        self._open_btn.setMinimumWidth(140)
        self._open_btn.setEnabled(False)
        self._open_btn.clicked.connect(self._on_open_clicked)
        btn_row.addWidget(self._open_btn)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("exLibCloseBtn")
        close_btn.setMinimumHeight(34)
        close_btn.setMinimumWidth(90)
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    # ── Population ────────────────────────────────────────────────────

    def _populate_categories(self) -> None:
        for cat in EXAMPLE_CATEGORIES:
            item = QListWidgetItem(f"{cat['icon']}  {cat['name']}")
            self._cat_list.addItem(item)

        if self._cat_list.count() > 0:
            self._cat_list.setCurrentRow(0)

    def _on_category_changed(self, row: int) -> None:
        self._example_list.clear()
        self._clear_preview()

        if row < 0 or row >= len(EXAMPLE_CATEGORIES):
            return

        cat = EXAMPLE_CATEGORIES[row]
        for ex in cat["examples"]:
            item = QListWidgetItem(ex["name"])
            item.setToolTip(ex["desc"])
            self._example_list.addItem(item)

        if self._example_list.count() > 0:
            self._example_list.setCurrentRow(0)

    def _on_example_changed(self, row: int) -> None:
        cat_row = self._cat_list.currentRow()
        if cat_row < 0 or cat_row >= len(EXAMPLE_CATEGORIES):
            self._clear_preview()
            return

        cat = EXAMPLE_CATEGORIES[cat_row]
        if row < 0 or row >= len(cat["examples"]):
            self._clear_preview()
            return

        ex = cat["examples"][row]
        self._current_name = ex["name"]
        self._current_code = ex["code"]
        self._preview_title.setText(ex["name"])
        self._preview_desc.setText(ex["desc"])
        self._code_preview.setPlainText(ex["code"])
        self._open_btn.setEnabled(True)

    def _clear_preview(self) -> None:
        self._current_code = ""
        self._current_name = ""
        self._preview_title.setText("")
        self._preview_desc.setText("")
        self._code_preview.clear()
        self._open_btn.setEnabled(False)

    # ── Actions ───────────────────────────────────────────────────────

    def _on_open_clicked(self) -> None:
        if self._current_code:
            self.example_selected.emit(self._current_name, self._current_code)
            self.close()

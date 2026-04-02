"""Example Library dialog — browse and open beginner Python examples."""

from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFrame,
    QGridLayout,
    QStackedWidget,
)

import html as _html

from meadowpy.resources.example_library import EXAMPLE_CATEGORIES


class _CategoryButton(QWidget):
    """A styled category button with icon and name."""

    clicked = pyqtSignal()

    def __init__(self, icon: str, name: str, count: int, parent=None):
        super().__init__(parent)
        self.setObjectName("exLibCatBtn")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._selected = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # Icon
        icon_label = QLabel(icon)
        icon_label.setObjectName("exLibCatIcon")
        icon_font = QFont()
        icon_font.setPointSize(16)
        icon_label.setFont(icon_font)
        icon_label.setFixedWidth(28)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        # Name + count
        info = QVBoxLayout()
        info.setSpacing(0)
        info.setContentsMargins(0, 0, 0, 0)

        name_label = QLabel(name)
        name_label.setObjectName("exLibCatName")
        name_font = QFont()
        name_font.setPointSize(10)
        name_font.setBold(True)
        name_label.setFont(name_font)
        info.addWidget(name_label)

        count_label = QLabel(f"{count} example{'s' if count != 1 else ''}")
        count_label.setObjectName("exLibCatCount")
        count_font = QFont()
        count_font.setPointSize(8)
        count_label.setFont(count_font)
        info.addWidget(count_label)

        layout.addLayout(info, 1)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        # Re-polish child widgets so nested selectors update too
        for child in self.findChildren(QWidget):
            child.style().unpolish(child)
            child.style().polish(child)
        self.update()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class _ExampleCard(QWidget):
    """A card widget for an individual example."""

    clicked = pyqtSignal()

    def __init__(self, name: str, desc: str, parent=None):
        super().__init__(parent)
        self.setObjectName("exLibExCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._selected = False
        self.setFixedWidth(160)
        self.setMinimumHeight(90)
        self.setMaximumHeight(90)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        title = QLabel(name)
        title.setObjectName("exLibExCardTitle")
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setWordWrap(True)
        title.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title)

        description = QLabel(desc)
        description.setObjectName("exLibExCardDesc")
        desc_font = QFont()
        desc_font.setPointSize(9)
        description.setFont(desc_font)
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(description)

        layout.addStretch()

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        # Re-polish child widgets so nested selectors update too
        for child in self.findChildren(QWidget):
            child.style().unpolish(child)
            child.style().polish(child)
        self.update()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.clicked.emit()
        # Bubble up double-click so the dialog can handle "open on double-click"
        super().mouseDoubleClickEvent(event)


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
        self.setMinimumSize(900, 560)
        self.resize(1000, 640)
        self._current_code: str = ""
        self._current_name: str = ""
        self._cat_buttons: list[_CategoryButton] = []
        self._example_cards: list[_ExampleCard] = []
        self._current_cat: int = -1
        self._current_ex: int = -1
        self._setup_ui()
        self._populate_categories()

    # ── UI setup ──────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header banner ──
        header = QWidget()
        header.setObjectName("exLibHeader")
        header.setFixedHeight(72)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(24, 12, 24, 12)
        header_layout.setSpacing(2)

        title = QLabel("\U0001F4DA  Python Example Library")
        title.setObjectName("exLibTitle")
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)

        subtitle = QLabel("Browse examples by category, preview the code, and open it in a new tab.")
        subtitle.setObjectName("exLibSubtitle")
        sub_font = QFont()
        sub_font.setPointSize(9)
        subtitle.setFont(sub_font)
        header_layout.addWidget(subtitle)

        root.addWidget(header)

        # ── Separator line ──
        sep = QFrame()
        sep.setObjectName("exLibSep")
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        root.addWidget(sep)

        # ── Body: sidebar | content ──
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # -- Left sidebar: categories --
        sidebar = QWidget()
        sidebar.setObjectName("exLibSidebar")
        sidebar.setFixedWidth(200)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(8, 12, 8, 12)
        sidebar_layout.setSpacing(2)

        cat_header = QLabel("CATEGORIES")
        cat_header.setObjectName("exLibCatHeader")
        cat_header_font = QFont()
        cat_header_font.setPointSize(8)
        cat_header_font.setBold(True)
        cat_header.setFont(cat_header_font)
        cat_header.setContentsMargins(12, 0, 0, 6)
        sidebar_layout.addWidget(cat_header)

        self._cat_container = QVBoxLayout()
        self._cat_container.setSpacing(2)
        sidebar_layout.addLayout(self._cat_container)
        sidebar_layout.addStretch()

        body.addWidget(sidebar)

        # -- Vertical separator --
        vsep = QFrame()
        vsep.setObjectName("exLibVSep")
        vsep.setFrameShape(QFrame.Shape.VLine)
        vsep.setFixedWidth(1)
        body.addWidget(vsep)

        # -- Right content area --
        content = QWidget()
        content.setObjectName("exLibContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 12, 16, 12)
        content_layout.setSpacing(12)

        # Examples header row
        self._examples_header = QLabel("Select a category")
        self._examples_header.setObjectName("exLibExamplesHeader")
        ex_header_font = QFont()
        ex_header_font.setPointSize(12)
        ex_header_font.setBold(True)
        self._examples_header.setFont(ex_header_font)
        content_layout.addWidget(self._examples_header)

        # Example cards scroll area
        self._cards_scroll = QScrollArea()
        self._cards_scroll.setObjectName("exLibCardsScroll")
        self._cards_scroll.setWidgetResizable(True)
        self._cards_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._cards_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._cards_scroll.setFixedHeight(110)

        self._cards_widget = QWidget()
        self._cards_widget.setObjectName("exLibCardsWidget")
        self._cards_layout = QHBoxLayout(self._cards_widget)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(8)
        self._cards_layout.addStretch()
        self._cards_scroll.setWidget(self._cards_widget)
        content_layout.addWidget(self._cards_scroll)

        # Code preview area
        preview_frame = QWidget()
        preview_frame.setObjectName("exLibPreviewFrame")
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)

        # Preview header bar
        preview_bar = QWidget()
        preview_bar.setObjectName("exLibPreviewBar")
        preview_bar.setFixedHeight(40)
        preview_bar_layout = QHBoxLayout(preview_bar)
        preview_bar_layout.setContentsMargins(14, 0, 14, 0)
        preview_bar_layout.setSpacing(8)

        self._preview_title = QLabel("No example selected")
        self._preview_title.setObjectName("exLibPreviewTitle")
        pv_title_font = QFont()
        pv_title_font.setPointSize(10)
        pv_title_font.setBold(True)
        self._preview_title.setFont(pv_title_font)
        preview_bar_layout.addWidget(self._preview_title)

        preview_bar_layout.addStretch()

        self._preview_desc = QLabel("")
        self._preview_desc.setObjectName("exLibPreviewDesc")
        pv_desc_font = QFont()
        pv_desc_font.setPointSize(9)
        self._preview_desc.setFont(pv_desc_font)
        preview_bar_layout.addWidget(self._preview_desc)

        preview_layout.addWidget(preview_bar)

        # Code text area
        self._code_preview = QTextEdit()
        self._code_preview.setObjectName("exLibCodePreview")
        self._code_preview.setReadOnly(True)
        self._code_preview.setFont(QFont("Consolas", 10))
        self._code_preview.document().setDocumentMargin(12)
        self._code_preview.document().setDefaultStyleSheet(
            "p { margin: 0; padding: 0; }"
        )
        preview_layout.addWidget(self._code_preview)

        content_layout.addWidget(preview_frame, 1)

        body.addWidget(content, 1)
        root.addLayout(body, 1)

        # ── Footer with buttons ──
        footer_sep = QFrame()
        footer_sep.setObjectName("exLibSep")
        footer_sep.setFrameShape(QFrame.Shape.HLine)
        footer_sep.setFixedHeight(1)
        root.addWidget(footer_sep)

        footer = QWidget()
        footer.setObjectName("exLibFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 10, 16, 10)
        footer_layout.setSpacing(8)

        # Example count label
        self._count_label = QLabel("")
        self._count_label.setObjectName("exLibCountLabel")
        count_font = QFont()
        count_font.setPointSize(9)
        self._count_label.setFont(count_font)
        footer_layout.addWidget(self._count_label)

        total = sum(len(c["examples"]) for c in EXAMPLE_CATEGORIES)
        self._count_label.setText(
            f"{len(EXAMPLE_CATEGORIES)} categories \u00b7 {total} examples"
        )

        footer_layout.addStretch()

        self._open_btn = QPushButton("\u25B6  Open in New Tab")
        self._open_btn.setObjectName("exLibOpenBtn")
        self._open_btn.setMinimumHeight(34)
        self._open_btn.setMinimumWidth(160)
        self._open_btn.setEnabled(False)
        self._open_btn.clicked.connect(self._on_open_clicked)
        footer_layout.addWidget(self._open_btn)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("exLibCloseBtn")
        close_btn.setMinimumHeight(34)
        close_btn.setMinimumWidth(90)
        close_btn.clicked.connect(self.close)
        footer_layout.addWidget(close_btn)

        root.addWidget(footer)

    # ── Population ────────────────────────────────────────────────────

    def _populate_categories(self) -> None:
        for i, cat in enumerate(EXAMPLE_CATEGORIES):
            btn = _CategoryButton(
                cat["icon"], cat["name"], len(cat["examples"]), self
            )
            idx = i  # capture for closure
            btn.clicked.connect(lambda _idx=idx: self._on_category_clicked(_idx))
            self._cat_container.addWidget(btn)
            self._cat_buttons.append(btn)

        if self._cat_buttons:
            self._on_category_clicked(0)

    def _on_category_clicked(self, index: int) -> None:
        if index == self._current_cat:
            return
        self._current_cat = index

        # Update button selection states
        for i, btn in enumerate(self._cat_buttons):
            btn.set_selected(i == index)

        # Clear old cards
        self._example_cards.clear()
        while self._cards_layout.count() > 0:
            item = self._cards_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # Populate example cards
        cat = EXAMPLE_CATEGORIES[index]
        self._examples_header.setText(f"{cat['icon']}  {cat['name']}")

        for j, ex in enumerate(cat["examples"]):
            card = _ExampleCard(ex["name"], ex["desc"], self)
            eidx = j
            card.clicked.connect(lambda _j=eidx: self._on_example_clicked(_j))
            self._cards_layout.addWidget(card)
            self._example_cards.append(card)

        self._cards_layout.addStretch()

        # Auto-select first example
        self._current_ex = -1
        if self._example_cards:
            self._on_example_clicked(0)
        else:
            self._clear_preview()

    def _on_example_clicked(self, index: int) -> None:
        if self._current_cat < 0:
            return

        self._current_ex = index

        # Update card selection states
        for i, card in enumerate(self._example_cards):
            card.set_selected(i == index)

        cat = EXAMPLE_CATEGORIES[self._current_cat]
        if index < 0 or index >= len(cat["examples"]):
            self._clear_preview()
            return

        ex = cat["examples"][index]
        self._current_name = ex["name"]
        self._current_code = ex["code"]
        self._preview_title.setText(ex["name"])
        self._preview_desc.setText(ex["desc"])
        self._code_preview.setHtml(self._code_to_html(ex["code"]))
        self._open_btn.setEnabled(True)

    @staticmethod
    def _code_to_html(code: str) -> str:
        """Convert code to HTML with compact blank-line spacing."""
        lines = code.split(chr(10))
        lines = [l for l in lines if l.strip() != '']
        code = chr(10).join(lines)
        escaped = _html.escape(code)
        return (
            '<pre style="font-family: Consolas, monospace; font-size: 10pt; '
            'margin: 0; padding: 0; white-space: pre-wrap;">'
            + escaped
            + '</pre>'
        )

    def _clear_preview(self) -> None:
        self._current_code = ""
        self._current_name = ""
        self._preview_title.setText("No example selected")
        self._preview_desc.setText("")
        self._code_preview.clear()
        self._open_btn.setEnabled(False)

    # ── Actions ───────────────────────────────────────────────────────

    def _on_open_clicked(self) -> None:
        if self._current_code:
            self.example_selected.emit(self._current_name, self._current_code)
            self.close()

"""Symbol outline panel — shows classes and functions in the current file."""

import ast
import html as html_lib
from dataclasses import dataclass, field

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPalette, QTextDocument
from PyQt6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


# Roles stashed on each tree item so the delegate can render a colored
# glyph without duplicating what the base QStyle already drew.
_KIND_ROLE = Qt.ItemDataRole.UserRole + 1
_NAME_ROLE = Qt.ItemDataRole.UserRole + 2


class _NoFocusDelegate(QStyledItemDelegate):
    """Suppresses the dotted focus rectangle on items."""

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.state &= ~QStyle.StateFlag.State_HasFocus


class _SymbolItemDelegate(_NoFocusDelegate):
    """Paints the leading class/function glyph in the accent color.

    Uses a QTextDocument so the ``◆`` / ``ƒ`` prefix can be drawn in the
    accent color while the symbol name is drawn in the palette's text
    (or highlighted-text) color — mirroring how folders in the File
    Explorer are accent-tinted next to neutral file names.
    """

    _CLASS_GLYPH = "\u25C6"   # ◆
    _FUNC_GLYPH = "\u0192"    # ƒ

    def __init__(self, parent=None):
        super().__init__(parent)
        self._accent = QColor("#2F7A44")

    def set_accent_color(self, color) -> None:
        self._accent = QColor(color)
        parent = self.parent()
        if parent is not None:
            try:
                parent.viewport().update()
            except AttributeError:
                pass

    def paint(self, painter, option, index):
        kind = index.data(_KIND_ROLE)
        name = index.data(_NAME_ROLE)
        if kind not in ("class", "function", "method") or not name:
            super().paint(painter, option, index)
            return

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        # Blank the text so the base style draws only bg / selection /
        # branch / icon — we render the colored text ourselves.
        opt.text = ""

        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(
            QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget
        )

        text_rect = style.subElementRect(
            QStyle.SubElement.SE_ItemViewItemText, opt, opt.widget
        )

        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        fg = opt.palette.color(
            QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text
        )

        # Only the class diamond is tinted with the accent; ƒ for
        # functions/methods keeps the neutral text color.
        if kind == "class":
            glyph_html = (
                f'<span style="color:{self._accent.name()}">{self._CLASS_GLYPH}</span>'
            )
        else:
            glyph_html = (
                f'<span style="color:{fg.name()}">{self._FUNC_GLYPH}</span>'
            )
        html = (
            f'{glyph_html}'
            f'<span style="color:{fg.name()}">&nbsp;{html_lib.escape(name)}</span>'
        )

        doc = QTextDocument()
        doc.setDefaultFont(opt.font)
        doc.setDocumentMargin(0)
        doc.setHtml(html)

        painter.save()
        painter.translate(text_rect.topLeft())
        # Vertically center the single-line document in the text rect.
        doc_height = doc.size().height()
        y_off = max(0, (text_rect.height() - doc_height) / 2)
        painter.translate(0, y_off)
        doc.drawContents(
            painter,
            QRectF(0, 0, text_rect.width(), text_rect.height()),
        )
        painter.restore()


@dataclass
class SymbolInfo:
    """Represents a symbol (class, function, method) in the source file."""

    name: str
    kind: str  # 'class', 'function', 'method'
    line: int  # 0-based
    children: list["SymbolInfo"] = field(default_factory=list)


class SymbolOutlinePanel(QDockWidget):
    """Sidebar panel showing classes and functions in the current file."""

    navigate_to_line = pyqtSignal(int)  # emits 0-based line number

    def __init__(self, parent=None):
        super().__init__("Outline", parent)
        self.setObjectName("SymbolOutline")
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
            | Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self._setup_ui()

    def _setup_ui(self) -> None:
        # -- custom dock title bar -------------------------------------
        # Same pattern as File Explorer / Output / AI Chat / Search /
        # Problems: a QFrame title bar installed via setTitleBarWidget,
        # with rounded top corners and matching border. Content lives
        # in a QFrame container below with a rounded bottom.
        title_bar = QFrame()
        title_bar.setObjectName("outlineTitleBar")
        title_bar.setFrameShape(QFrame.Shape.NoFrame)
        title_bar.setFixedHeight(40)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(10, 2, 6, 8)
        title_layout.setSpacing(6)

        title_label = QLabel("Outline")
        title_label.setObjectName("outlineTitleLabel")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        self.setTitleBarWidget(title_bar)
        self._title_bar = title_bar

        # -- main container (rounded bottom corners, border l/r/bottom) -
        container = QFrame()
        container.setObjectName("outlineContainer")
        container.setFrameShape(QFrame.Shape.NoFrame)
        layout = QVBoxLayout(container)
        # Bottom padding so the tree's square corners don't cover
        # the container's rounded bottom corners.
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(0)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(16)
        self._tree.setObjectName("symbolTree")
        self._item_delegate = _SymbolItemDelegate(self._tree)
        self._tree.setItemDelegate(self._item_delegate)
        self._tree.itemClicked.connect(self._on_item_clicked)

        layout.addWidget(self._tree)
        self.setWidget(container)

    def update_symbols(self, source_code: str) -> None:
        """Parse source code and update the tree."""
        symbols = self._parse_symbols(source_code)
        # Only clear and rebuild if parsing succeeded
        if symbols is not None:
            self._tree.clear()
            self._populate_tree(symbols)
            self._tree.expandAll()

    def _parse_symbols(self, source: str) -> list[SymbolInfo] | None:
        """Use ast to extract classes and functions. Returns None on SyntaxError."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None  # keep previous state

        symbols = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                methods = []
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append(
                            SymbolInfo(
                                name=child.name,
                                kind="method",
                                line=child.lineno - 1,
                            )
                        )
                symbols.append(
                    SymbolInfo(
                        name=node.name,
                        kind="class",
                        line=node.lineno - 1,
                        children=methods,
                    )
                )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(
                    SymbolInfo(
                        name=node.name,
                        kind="function",
                        line=node.lineno - 1,
                    )
                )
        return symbols

    def _populate_tree(self, symbols: list[SymbolInfo]) -> None:
        """Build tree items from parsed symbols.

        The item's DisplayRole text is kept as a plain fallback
        (``◆ Name`` / ``ƒ Name``) so the item sorts and accessibility
        tools still see something sensible. The actual painting is done
        by the delegate, which reads the kind and bare name from custom
        roles and renders a colored glyph + neutral name.
        """
        kind_prefix = {
            "class": "\u25C6 ",  # ◆
            "function": "\u0192 ",  # ƒ
            "method": "\u0192 ",  # ƒ
        }
        for sym in symbols:
            prefix = kind_prefix.get(sym.kind, "")
            item = QTreeWidgetItem([f"{prefix}{sym.name}"])
            item.setData(0, Qt.ItemDataRole.UserRole, sym.line)
            item.setData(0, _KIND_ROLE, sym.kind)
            item.setData(0, _NAME_ROLE, sym.name)
            self._tree.addTopLevelItem(item)
            for child in sym.children:
                child_prefix = kind_prefix.get(child.kind, "")
                child_item = QTreeWidgetItem([f"{child_prefix}{child.name}"])
                child_item.setData(0, Qt.ItemDataRole.UserRole, child.line)
                child_item.setData(0, _KIND_ROLE, child.kind)
                child_item.setData(0, _NAME_ROLE, child.name)
                item.addChild(child_item)

    def apply_icon_theme(self, accent: str, is_dark: bool) -> None:
        """Update the accent color used to paint class/function glyphs."""
        self._item_delegate.set_accent_color(accent)

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        line = item.data(0, Qt.ItemDataRole.UserRole)
        if line is not None:
            self.navigate_to_line.emit(line)

    def clear_symbols(self) -> None:
        """Clear the tree (when no editor is active)."""
        self._tree.clear()

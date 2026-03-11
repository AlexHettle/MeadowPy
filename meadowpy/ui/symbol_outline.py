"""Symbol outline panel — shows classes and functions in the current file."""

import ast
from dataclasses import dataclass, field

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDockWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


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
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(16)
        self._tree.setObjectName("symbolTree")
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
        """Build tree items from parsed symbols."""
        kind_prefix = {
            "class": "\u25C6 ",  # ◆
            "function": "\u0192 ",  # ƒ
            "method": "\u0192 ",  # ƒ
        }
        for sym in symbols:
            prefix = kind_prefix.get(sym.kind, "")
            item = QTreeWidgetItem([f"{prefix}{sym.name}"])
            item.setData(0, Qt.ItemDataRole.UserRole, sym.line)
            self._tree.addTopLevelItem(item)
            for child in sym.children:
                child_prefix = kind_prefix.get(child.kind, "")
                child_item = QTreeWidgetItem([f"{child_prefix}{child.name}"])
                child_item.setData(0, Qt.ItemDataRole.UserRole, child.line)
                item.addChild(child_item)

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        line = item.data(0, Qt.ItemDataRole.UserRole)
        if line is not None:
            self.navigate_to_line.emit(line)

    def clear_symbols(self) -> None:
        """Clear the tree (when no editor is active)."""
        self._tree.clear()

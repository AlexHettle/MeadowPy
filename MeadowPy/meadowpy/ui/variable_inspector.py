"""Variable inspector panel — shows locals and globals during debug pause."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDockWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class VariableInspectorPanel(QDockWidget):
    """Dock panel that displays local and global variables when paused."""

    def __init__(self, parent=None):
        super().__init__("Variables", parent)
        self.setObjectName("VariableInspector")
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
        self._tree.setObjectName("variableTree")
        self._tree.setHeaderLabels(["Name", "Value"])
        self._tree.setColumnCount(2)
        self._tree.setIndentation(16)
        self._tree.setAlternatingRowColors(True)
        self._tree.setEditTriggers(QTreeWidget.EditTrigger.NoEditTriggers)

        # Resize first column to content, stretch second
        header = self._tree.header()
        header.setStretchLastSection(True)
        header.setDefaultSectionSize(150)

        layout.addWidget(self._tree)
        self.setWidget(container)

    def update_variables(self, variables: dict) -> None:
        """Update the tree with variable data.

        ``variables``: ``{"locals": {"name": "repr_value", ...}, "globals": {...}}``.
        """
        self._tree.clear()

        locals_dict = variables.get("locals", {})
        globals_dict = variables.get("globals", {})

        if locals_dict:
            locals_root = QTreeWidgetItem(["Locals", ""])
            locals_root.setFlags(
                locals_root.flags() & ~Qt.ItemFlag.ItemIsSelectable
            )
            font = locals_root.font(0)
            font.setBold(True)
            locals_root.setFont(0, font)
            self._tree.addTopLevelItem(locals_root)

            for name, value in sorted(locals_dict.items()):
                child = QTreeWidgetItem([name, value])
                child.setToolTip(1, value)  # full value on hover
                locals_root.addChild(child)

            locals_root.setExpanded(True)

        if globals_dict:
            globals_root = QTreeWidgetItem(["Globals", ""])
            globals_root.setFlags(
                globals_root.flags() & ~Qt.ItemFlag.ItemIsSelectable
            )
            font = globals_root.font(0)
            font.setBold(True)
            globals_root.setFont(0, font)
            self._tree.addTopLevelItem(globals_root)

            for name, value in sorted(globals_dict.items()):
                child = QTreeWidgetItem([name, value])
                child.setToolTip(1, value)
                globals_root.addChild(child)

            globals_root.setExpanded(True)

        if not locals_dict and not globals_dict:
            placeholder = QTreeWidgetItem(["(no variables)", ""])
            placeholder.setFlags(
                placeholder.flags() & ~Qt.ItemFlag.ItemIsSelectable
            )
            self._tree.addTopLevelItem(placeholder)

    def clear_variables(self) -> None:
        """Clear all variables from the tree."""
        self._tree.clear()

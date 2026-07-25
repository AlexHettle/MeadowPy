"""Watch expressions panel — user-defined expressions evaluated during debug."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class WatchPanel(QDockWidget):
    """Dock panel for user-defined watch expressions."""

    evaluate_requested = pyqtSignal(str)  # expression string

    def __init__(self, parent=None):
        super().__init__("Watch", parent)
        self.setObjectName("WatchPanel")
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
            | Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self._expressions: list[str] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Input row: text field + Add button
        input_row = QHBoxLayout()
        input_row.setSpacing(4)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Enter expression...")
        self._input.returnPressed.connect(self._add_expression)
        input_row.addWidget(self._input)

        self._add_btn = QPushButton("Add")
        self._add_btn.setFixedWidth(50)
        self._add_btn.clicked.connect(self._add_expression)
        input_row.addWidget(self._add_btn)

        layout.addLayout(input_row)

        # Table: Expression | Value | Remove
        self._table = QTableWidget()
        self._table.setObjectName("watchTable")
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Expression", "Value", ""])
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Interactive
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Fixed
        )
        self._table.setColumnWidth(0, 140)
        self._table.setColumnWidth(2, 30)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        layout.addWidget(self._table)
        self.setWidget(container)

    def _add_expression(self) -> None:
        """Add a new watch expression from the input field."""
        expr = self._input.text().strip()
        if not expr or expr in self._expressions:
            return

        self._expressions.append(expr)
        self._input.clear()
        self._rebuild_table()

        # Request evaluation immediately
        self.evaluate_requested.emit(expr)

    def _remove_expression(self, expr: str) -> None:
        """Remove a watch expression."""
        if expr in self._expressions:
            self._expressions.remove(expr)
            self._rebuild_table()

    def _rebuild_table(self) -> None:
        """Rebuild the table rows from the expression list."""
        self._table.setRowCount(len(self._expressions))
        for row, expr in enumerate(self._expressions):
            self._table.setItem(row, 0, QTableWidgetItem(expr))
            # Value column starts as "(not evaluated)"
            value_item = QTableWidgetItem("(not evaluated)")
            value_item.setForeground(QColor("#888888"))
            self._table.setItem(row, 1, value_item)

            # Remove button
            remove_item = QTableWidgetItem("\u2716")  # ✖
            remove_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            remove_item.setToolTip("Remove")
            self._table.setItem(row, 2, remove_item)

        # Connect cell click for remove column
        try:
            self._table.cellClicked.disconnect()
        except (TypeError, RuntimeError):
            pass
        self._table.cellClicked.connect(self._on_cell_clicked)

    def _on_cell_clicked(self, row: int, col: int) -> None:
        if col == 2 and row < len(self._expressions):
            self._remove_expression(self._expressions[row])

    def update_value(self, expression: str, result: str, error: str) -> None:
        """Update the value column for a specific expression."""
        for row in range(self._table.rowCount()):
            expr_item = self._table.item(row, 0)
            if expr_item and expr_item.text() == expression:
                if error:
                    value_item = QTableWidgetItem(f"Error: {error}")
                    value_item.setForeground(QColor("#E51400"))
                else:
                    value_item = QTableWidgetItem(result)
                    # No explicit foreground — inherits from QSS theme
                value_item.setToolTip(result if not error else error)
                self._table.setItem(row, 1, value_item)
                break

    def request_all_evaluations(self) -> None:
        """Re-request evaluation of all watch expressions (e.g. after a step)."""
        for expr in self._expressions:
            self.evaluate_requested.emit(expr)

    def get_expressions(self) -> list[str]:
        """Return the current list of watch expressions."""
        return list(self._expressions)

    def clear_values(self) -> None:
        """Reset all values to '(not evaluated)' without removing expressions."""
        for row in range(self._table.rowCount()):
            value_item = QTableWidgetItem("(not evaluated)")
            value_item.setForeground(QColor("#888888"))
            self._table.setItem(row, 1, value_item)

    def clear_all(self) -> None:
        """Remove all expressions and clear the table."""
        self._expressions.clear()
        self._table.setRowCount(0)

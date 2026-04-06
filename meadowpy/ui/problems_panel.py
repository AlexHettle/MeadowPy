"""Problems panel — shows linting issues with click-to-navigate."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDockWidget,
    QHeaderView,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from meadowpy.core.linter import LintIssue


class ProblemsPanel(QDockWidget):
    """Bottom panel showing linting issues with click-to-navigate."""

    navigate_to = pyqtSignal(int, int)  # line, column (both 0-based)
    ai_fix_requested = pyqtSignal(str, int, str)  # (code, line_1based, message)

    def __init__(self, parent=None):
        super().__init__("Problems", parent)
        self.setObjectName("ProblemsPanel")
        self.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea
            | Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self._issues: list[LintIssue] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Table
        self._table = QTableWidget()
        self._table.setObjectName("problemsTable")
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["", "Line", "Code", "Message"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Fixed
        )
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Fixed
        )
        self._table.setColumnWidth(0, 30)  # severity icon
        self._table.setColumnWidth(1, 60)  # line number
        self._table.setColumnWidth(2, 80)  # error code
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.cellClicked.connect(self._on_cell_clicked)
        self._table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self._table.customContextMenuRequested.connect(self._on_context_menu)

        layout.addWidget(self._table)
        self.setWidget(container)

    def update_issues(self, issues: list[LintIssue]) -> None:
        """Populate the table with lint issues."""
        self._issues = list(issues)
        self._table.setRowCount(len(issues))

        error_count = sum(1 for i in issues if i.severity == "error")
        warning_count = sum(1 for i in issues if i.severity == "warning")

        if issues:
            parts = []
            if error_count:
                parts.append(f"{error_count} error{'s' if error_count != 1 else ''}")
            if warning_count:
                parts.append(
                    f"{warning_count} warning{'s' if warning_count != 1 else ''}"
                )
            self.setWindowTitle(f"Problems — {', '.join(parts)}")
        else:
            self.setWindowTitle("Problems")

        for row, issue in enumerate(issues):
            # Severity indicator
            icon_text = "\u2716" if issue.severity == "error" else "\u26A0"
            severity_item = QTableWidgetItem(icon_text)
            severity_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 0, severity_item)

            # Line number (display as 1-based)
            line_item = QTableWidgetItem(str(issue.line + 1))
            line_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            line_item.setData(
                Qt.ItemDataRole.UserRole, (issue.line, issue.column)
            )
            self._table.setItem(row, 1, line_item)

            # Code
            self._table.setItem(row, 2, QTableWidgetItem(issue.code))

            # Message
            self._table.setItem(row, 3, QTableWidgetItem(issue.message))

    def _on_cell_clicked(self, row: int, column: int) -> None:
        line_item = self._table.item(row, 1)
        if line_item:
            data = line_item.data(Qt.ItemDataRole.UserRole)
            if data:
                line, col = data
                self.navigate_to.emit(line, col)

    def _on_context_menu(self, pos) -> None:
        """Show context menu with 'Fix with AI' option on the clicked row."""
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._issues):
            return

        issue = self._issues[row]
        menu = QMenu(self)

        fix_action = menu.addAction("AI Analysis...")
        fix_action.setToolTip("Ask the AI to analyze this linting issue")
        fix_action.triggered.connect(
            lambda: self.ai_fix_requested.emit(
                issue.code, issue.line + 1, issue.message
            )
        )

        menu.exec(self._table.viewport().mapToGlobal(pos))

    def show_linter_error(self, message: str) -> None:
        """Display a linter error (e.g. not installed) in the table."""
        self._issues.clear()
        self._table.setRowCount(1)
        self.setWindowTitle("Problems — Linter Error")

        icon_item = QTableWidgetItem("\u26A0")
        icon_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(0, 0, icon_item)

        self._table.setItem(0, 1, QTableWidgetItem("—"))
        self._table.setItem(0, 2, QTableWidgetItem("config"))
        self._table.setItem(0, 3, QTableWidgetItem(message))

    def clear_issues(self) -> None:
        """Clear all issues from the table."""
        self._issues.clear()
        self._table.setRowCount(0)
        self.setWindowTitle("Problems")

"""Call stack panel — shows the frame list during debug pause."""

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDockWidget,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)


class CallStackPanel(QDockWidget):
    """Dock panel that shows the call stack when the debugger is paused."""

    frame_selected = pyqtSignal(int)  # 0-based frame index

    def __init__(self, parent=None):
        super().__init__("Call Stack", parent)
        self.setObjectName("CallStackPanel")
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

        self._list = QListWidget()
        self._list.setObjectName("callStackList")
        self._list.setAlternatingRowColors(True)
        self._list.currentRowChanged.connect(self._on_row_changed)

        layout.addWidget(self._list)
        self.setWidget(container)

    def update_call_stack(self, call_stack: list[dict]) -> None:
        """Populate the list with call stack frames.

        ``call_stack``: list of ``{"file": str, "line": int (1-based), "function": str}``.
        Frames are in order newest-first (index 0 = current frame).
        """
        self._list.blockSignals(True)
        self._list.clear()

        for i, frame in enumerate(call_stack):
            func = frame.get("function", "<unknown>")
            filepath = frame.get("file", "")
            line = frame.get("line", 0)

            # Show short filename
            filename = Path(filepath).name if filepath else "<unknown>"
            display = f"{func} ({filename}:{line})"

            item = QListWidgetItem(display)
            item.setToolTip(f"{filepath}:{line}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self._list.addItem(item)

        # Select current frame (first row)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

        self._list.blockSignals(False)

    def _on_row_changed(self, row: int) -> None:
        if row >= 0:
            item = self._list.item(row)
            if item:
                frame_index = item.data(Qt.ItemDataRole.UserRole)
                self.frame_selected.emit(frame_index)

    def clear_stack(self) -> None:
        """Clear all frames from the list."""
        self._list.clear()

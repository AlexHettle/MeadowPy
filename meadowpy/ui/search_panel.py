"""Search across files panel — grep-like project-wide text search."""

import os
import re
from pathlib import Path

from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class _NoFocusDelegate(QStyledItemDelegate):
    """Suppresses the dotted focus rectangle on items."""

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.state &= ~QStyle.StateFlag.State_HasFocus


# ── Directories and extensions to skip ──────────────────────────────────
_SKIP_DIRS = {
    "__pycache__", ".git", ".venv", ".idea", ".vs", ".vscode",
    "node_modules", ".mypy_cache", ".pytest_cache", ".eggs",
    ".tox", "venv", "env", ".env",
}
_SKIP_SUFFIXES = {
    ".pyc", ".pyo", ".exe", ".dll", ".so", ".dylib", ".bin",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".svg",
    ".zip", ".tar", ".gz", ".whl", ".egg",
}
_MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB — skip huge files


# ── Background search worker ───────────────────────────────────────────

class SearchResult:
    """A single match in a file."""
    __slots__ = ("file_path", "line_num", "column", "line_text")

    def __init__(self, file_path: str, line_num: int, column: int, line_text: str):
        self.file_path = file_path
        self.line_num = line_num
        self.column = column
        self.line_text = line_text


class SearchWorker(QObject):
    """Scans project files in a background thread."""

    match_found = pyqtSignal(object)   # SearchResult
    finished = pyqtSignal(int)         # total match count

    def __init__(
        self,
        root_path: str,
        pattern: str,
        case_sensitive: bool,
        use_regex: bool,
    ):
        super().__init__()
        self._root = root_path
        self._pattern = pattern
        self._case_sensitive = case_sensitive
        self._use_regex = use_regex
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        count = 0
        try:
            regex = self._compile_pattern()
            if regex is None:
                self.finished.emit(0)
                return

            for dirpath, dirnames, filenames in os.walk(self._root):
                if self._cancelled:
                    break
                # Prune hidden/build directories in-place
                dirnames[:] = [
                    d for d in dirnames
                    if d not in _SKIP_DIRS and not d.startswith(".")
                ]
                for fname in filenames:
                    if self._cancelled:
                        break
                    fpath = os.path.join(dirpath, fname)
                    suffix = Path(fname).suffix.lower()
                    if suffix in _SKIP_SUFFIXES:
                        continue
                    try:
                        if os.path.getsize(fpath) > _MAX_FILE_SIZE:
                            continue
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            for line_num, line_text in enumerate(f, start=1):
                                if self._cancelled:
                                    break
                                m = regex.search(line_text)
                                if m:
                                    count += 1
                                    self.match_found.emit(
                                        SearchResult(
                                            fpath, line_num, m.start(),
                                            line_text.rstrip("\n\r"),
                                        )
                                    )
                    except (OSError, UnicodeDecodeError):
                        continue
        except Exception:
            pass
        self.finished.emit(count)

    def _compile_pattern(self) -> re.Pattern | None:
        flags = 0 if self._case_sensitive else re.IGNORECASE
        try:
            if self._use_regex:
                return re.compile(self._pattern, flags)
            return re.compile(re.escape(self._pattern), flags)
        except re.error:
            return None


# ── Search panel widget ─────────────────────────────────────────────────

class SearchPanel(QDockWidget):
    """Bottom dock panel for project-wide text search.

    Emits *navigate_to_file(str, int)* when the user clicks a result.
    """

    navigate_to_file = pyqtSignal(str, int)  # (file_path, 1-based line)

    def __init__(self, parent=None):
        super().__init__("Search", parent)
        self.setObjectName("SearchPanel")
        self.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea
            | Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )

        self._thread: QThread | None = None
        self._worker: SearchWorker | None = None
        self._root_path: str | None = None
        self._file_items: dict[str, QTreeWidgetItem] = {}
        self._old_threads: list[QThread] = []

        self._setup_ui()

    def _setup_ui(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # -- Search controls row --
        controls = QHBoxLayout()
        controls.setSpacing(6)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search in files…")
        self._search_input.setToolTip("Type text to search across all files in the open folder")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setMinimumHeight(28)
        self._search_input.returnPressed.connect(self._start_search)
        controls.addWidget(self._search_input, 1)

        self._case_cb = QCheckBox("Aa")
        self._case_cb.setToolTip("Match Case")
        controls.addWidget(self._case_cb)

        self._regex_cb = QCheckBox(".*")
        self._regex_cb.setToolTip("Use Regular Expression")
        controls.addWidget(self._regex_cb)

        self._search_btn = QPushButton("Search")
        self._search_btn.setToolTip("Search all files in the open folder (Enter)")
        self._search_btn.setMinimumHeight(28)
        self._search_btn.clicked.connect(self._start_search)
        controls.addWidget(self._search_btn)

        layout.addLayout(controls)

        # -- Status label --
        self._status_label = QLabel("")
        self._status_label.setObjectName("searchStatusLabel")
        layout.addWidget(self._status_label)

        # -- Results tree --
        self._tree = QTreeWidget()
        self._tree.setObjectName("searchResultsTree")
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(16)
        self._tree.setRootIsDecorated(True)
        self._tree.setItemDelegate(_NoFocusDelegate(self._tree))
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._tree, 1)

        self.setWidget(container)

    # ── Public API ──────────────────────────────────────────────────────

    def set_root_path(self, path: str) -> None:
        self._root_path = path

    def focus_search(self) -> None:
        """Show, raise, and focus the search input."""
        self.show()
        self.raise_()
        self._search_input.setFocus()
        self._search_input.selectAll()

    # ── Search lifecycle ────────────────────────────────────────────────

    def _start_search(self) -> None:
        query = self._search_input.text()
        if not query or not self._root_path:
            return

        # Cancel any running search
        self._cancel_search()

        # Clear previous results
        self._tree.clear()
        self._file_items.clear()
        self._status_label.setText("Searching…")
        self._search_btn.setEnabled(False)

        self._thread = QThread()
        self._worker = SearchWorker(
            self._root_path,
            query,
            self._case_cb.isChecked(),
            self._regex_cb.isChecked(),
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.match_found.connect(self._on_match_found)
        self._worker.finished.connect(self._on_search_finished)
        self._worker.finished.connect(self._thread.quit)
        # Clean up references only after the thread has actually stopped
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()

    def stop(self) -> None:
        """Shut down all threads cleanly (call during app close)."""
        self._cancel_search()
        for thread in self._old_threads:
            if thread.isRunning():
                thread.quit()
                if not thread.wait(500):
                    thread.terminate()
                    thread.wait(500)
        self._old_threads.clear()

    def _cancel_search(self) -> None:
        if self._worker:
            self._worker.cancel()
            # Disconnect signals so stale results don't arrive
            try:
                self._worker.match_found.disconnect(self._on_match_found)
                self._worker.finished.disconnect(self._on_search_finished)
            except TypeError:
                pass
        if self._thread and self._thread.isRunning():
            old_thread = self._thread
            old_thread.quit()
            # Keep a reference so it isn't GC'd while still running
            self._old_threads.append(old_thread)
            old_thread.finished.connect(
                lambda t=old_thread: self._cleanup_thread(t)
            )
        self._thread = None
        self._worker = None

    def _cleanup_thread(self, thread: QThread) -> None:
        try:
            self._old_threads.remove(thread)
        except ValueError:
            pass

    # ── Slots ───────────────────────────────────────────────────────────

    def _on_match_found(self, result: SearchResult) -> None:
        """Add a single result to the tree (called from worker thread via signal)."""
        # Get or create the file-level parent item
        file_item = self._file_items.get(result.file_path)
        if file_item is None:
            # Show path relative to project root
            try:
                display = str(Path(result.file_path).relative_to(self._root_path))
            except ValueError:
                display = result.file_path
            file_item = QTreeWidgetItem(self._tree, [display])
            file_item.setData(0, Qt.ItemDataRole.UserRole, result.file_path)
            font = file_item.font(0)
            font.setBold(True)
            file_item.setFont(0, font)
            file_item.setExpanded(True)
            self._file_items[result.file_path] = file_item

        # Add the line-level child item
        preview = result.line_text.strip()
        if len(preview) > 200:
            preview = preview[:200] + "…"
        child_text = f"  {result.line_num}: {preview}"
        child = QTreeWidgetItem(file_item, [child_text])
        child.setData(0, Qt.ItemDataRole.UserRole, result.file_path)
        child.setData(0, Qt.ItemDataRole.UserRole + 1, result.line_num)

        # Update file item count
        count = file_item.childCount()
        try:
            display = str(Path(result.file_path).relative_to(self._root_path))
        except ValueError:
            display = result.file_path
        file_item.setText(0, f"{display}  ({count})")

    def _on_search_finished(self, total: int) -> None:
        file_count = len(self._file_items)
        if total == 0:
            self._status_label.setText("No results found.")
        else:
            self._status_label.setText(
                f"{total} result{'s' if total != 1 else ''} "
                f"in {file_count} file{'s' if file_count != 1 else ''}"
            )
        self._search_btn.setEnabled(True)

    def _on_thread_finished(self) -> None:
        """Safe to drop references now — the thread has actually stopped."""
        self._thread = None
        self._worker = None

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        line_num = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if file_path:
            self.navigate_to_file.emit(file_path, line_num or 1)

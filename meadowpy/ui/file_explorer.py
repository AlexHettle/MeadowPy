"""File explorer panel — shows project directory tree."""

import shutil
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QModelIndex, QSortFilterProxyModel
from PyQt6.QtGui import QAction, QFileSystemModel
from PyQt6.QtWidgets import (
    QStyle,
    QStyledItemDelegate,
    QDockWidget,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)


# ── Hidden names / suffixes filtered from the tree ──────────────────────
_HIDDEN_NAMES = {
    "__pycache__", ".git", ".venv", ".idea", ".vs", ".vscode",
    "node_modules", ".mypy_cache", ".pytest_cache", ".eggs",
}
_HIDDEN_SUFFIXES = {".pyc", ".pyo"}


class _NoFocusDelegate(QStyledItemDelegate):
    """Suppresses the dotted focus rectangle on items."""

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.state &= ~QStyle.StateFlag.State_HasFocus


class _FilteredFileSystemModel(QSortFilterProxyModel):
    """Proxy that hides build artefacts and VCS directories."""

    def filterAcceptsRow(
        self, source_row: int, source_parent: QModelIndex
    ) -> bool:
        model = self.sourceModel()
        index = model.index(source_row, 0, source_parent)
        name = model.fileName(index)
        if name in _HIDDEN_NAMES:
            return False
        for suffix in _HIDDEN_SUFFIXES:
            if name.endswith(suffix):
                return False
        return True


class FileExplorerPanel(QDockWidget):
    """Left-side dock widget showing a project directory tree.

    Emits *file_selected(str)* when the user double-clicks a file.
    """

    file_selected = pyqtSignal(str)   # absolute file path
    file_renamed = pyqtSignal(str, str)  # (old_path, new_path)
    file_deleted = pyqtSignal(str)       # deleted path
    file_created = pyqtSignal(str)       # new file path (open in editor)

    def __init__(self, parent=None):
        super().__init__("Explorer", parent)
        self.setObjectName("FileExplorer")
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )

        self._root_path: str | None = None
        self._fs_model: QFileSystemModel | None = None
        self._proxy: _FilteredFileSystemModel | None = None

        self._setup_ui()

    # ── UI construction ─────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # -- header bar --------------------------------------------------
        header = QWidget()
        header.setObjectName("explorerHeader")
        header.setFixedHeight(30)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(8, 0, 4, 0)
        h_layout.setSpacing(2)

        self._folder_label = QLabel("No folder opened")
        self._folder_label.setObjectName("explorerFolderLabel")
        h_layout.addWidget(self._folder_label)
        h_layout.addStretch()

        self._collapse_btn = self._make_button("\u25B4", "Collapse All")
        self._collapse_btn.clicked.connect(self.collapse_all)
        h_layout.addWidget(self._collapse_btn)

        self._refresh_btn = self._make_button("\u21BB", "Refresh")
        self._refresh_btn.clicked.connect(self.refresh)
        h_layout.addWidget(self._refresh_btn)

        layout.addWidget(header)

        # -- tree view ---------------------------------------------------
        self._tree = QTreeView()
        self._tree.setObjectName("explorerTree")
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(16)
        self._tree.setAnimated(True)
        self._tree.setSortingEnabled(True)
        self._tree.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self._tree.setDragEnabled(True)
        self._tree.setDragDropMode(QTreeView.DragDropMode.DragOnly)
        self._tree.doubleClicked.connect(self._on_double_clicked)
        self._tree.setItemDelegate(_NoFocusDelegate(self._tree))
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._tree)

        # -- empty-state label (visible until a folder is opened) --------
        self._empty_label = QLabel("Open a folder to get started\n\nFile → Open Folder…")
        self._empty_label.setObjectName("explorerEmptyLabel")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        layout.addWidget(self._empty_label)

        self._tree.hide()
        header.hide()
        self._header = header

        self.setWidget(container)

    @staticmethod
    def _make_button(text: str, tooltip: str) -> QToolButton:
        btn = QToolButton()
        btn.setText(text)
        btn.setToolTip(tooltip)
        btn.setAutoRaise(True)
        btn.setFixedSize(24, 24)
        btn.setStyleSheet(
            "QToolButton { border: 1px solid transparent; border-radius: 3px;"
            " padding: 2px; font-size: 14px; color: #CCCCCC; }"
            " QToolButton:hover { background: rgba(128,128,128,0.2);"
            " border-color: rgba(128,128,128,0.3); color: #FFFFFF; }"
        )
        return btn

    # ── Public API ──────────────────────────────────────────────────────

    def set_root_folder(self, folder_path: str) -> None:
        """Set (or change) the root directory shown in the tree."""
        self._root_path = folder_path

        # Create model + proxy once, reuse on subsequent calls
        if self._fs_model is None:
            self._fs_model = QFileSystemModel(self)
            self._fs_model.setReadOnly(True)

            self._proxy = _FilteredFileSystemModel(self)
            self._proxy.setSourceModel(self._fs_model)
            self._proxy.setDynamicSortFilter(True)
            self._tree.setModel(self._proxy)

        self._fs_model.setRootPath(folder_path)
        source_index = self._fs_model.index(folder_path)
        proxy_index = self._proxy.mapFromSource(source_index)
        self._tree.setRootIndex(proxy_index)

        # Show only the Name column
        for col in range(1, self._fs_model.columnCount()):
            self._tree.hideColumn(col)

        # Sort alphabetically, folders first (default QFileSystemModel behaviour)
        self._tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)

        # Update header label
        self._folder_label.setText(Path(folder_path).name)
        self._folder_label.setToolTip(folder_path)

        # Switch from empty state to tree
        self._empty_label.hide()
        self._tree.show()
        self._header.show()

    def collapse_all(self) -> None:
        """Collapse every expanded node."""
        self._tree.collapseAll()
        # Scroll back to top after collapsing
        root = self._tree.rootIndex()
        if root.isValid():
            self._tree.scrollTo(root)

    def refresh(self) -> None:
        """Force the file-system model to re-read the root directory."""
        if self._root_path and self._fs_model:
            # Destroy and recreate the model to force a full re-read
            self._fs_model.deleteLater()
            self._fs_model = None
            self._proxy.deleteLater()
            self._proxy = None
            self.set_root_folder(self._root_path)

    @property
    def root_path(self) -> str | None:
        return self._root_path

    # ── Slots ───────────────────────────────────────────────────────────

    def _on_double_clicked(self, proxy_index: QModelIndex) -> None:
        source_index = self._proxy.mapToSource(proxy_index)
        if not self._fs_model.isDir(source_index):
            file_path = self._fs_model.filePath(source_index)
            self.file_selected.emit(file_path)

    # ── Context menu ────────────────────────────────────────────────────

    def _resolve_target_dir(self, proxy_index: QModelIndex) -> tuple[Path, QModelIndex | None]:
        """Return (target_directory, source_index_or_None) for context actions.

        If the click lands on a file, the target dir is its parent.
        If the click lands on a folder, the target dir is that folder.
        If the click lands on empty space, the target dir is the root.
        """
        if not proxy_index.isValid():
            return Path(self._root_path), None
        source_index = self._proxy.mapToSource(proxy_index)
        path = Path(self._fs_model.filePath(source_index))
        if path.is_dir():
            return path, source_index
        return path.parent, source_index

    def _on_context_menu(self, pos) -> None:
        """Show context menu at the given tree-view position."""
        if not self._root_path:
            return

        proxy_index = self._tree.indexAt(pos)
        target_dir, source_index = self._resolve_target_dir(proxy_index)

        menu = QMenu(self)

        # New File / New Folder are always available
        act_new_file = menu.addAction("New File…")
        act_new_folder = menu.addAction("New Folder…")

        # Rename / Delete only when clicking on an item
        act_rename = None
        act_delete = None
        if proxy_index.isValid():
            menu.addSeparator()
            act_rename = menu.addAction("Rename…")
            act_delete = menu.addAction("Delete")

        chosen = menu.exec(self._tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return

        if chosen is act_new_file:
            self._action_new_file(target_dir)
        elif chosen is act_new_folder:
            self._action_new_folder(target_dir)
        elif chosen is act_rename:
            self._action_rename(source_index)
        elif chosen is act_delete:
            self._action_delete(source_index)

    # ── Context-menu actions ────────────────────────────────────────────

    def _action_new_file(self, parent_dir: Path) -> None:
        name, ok = QInputDialog.getText(
            self, "New File", "File name:", text="untitled.py"
        )
        if not ok or not name.strip():
            return
        new_path = parent_dir / name.strip()
        if new_path.exists():
            QMessageBox.warning(self, "File Exists", f"'{name}' already exists.")
            return
        try:
            new_path.touch()
        except OSError as e:
            QMessageBox.critical(self, "Error", f"Could not create file:\n{e}")
            return
        self.file_created.emit(str(new_path))

    def _action_new_folder(self, parent_dir: Path) -> None:
        name, ok = QInputDialog.getText(
            self, "New Folder", "Folder name:", text="new_folder"
        )
        if not ok or not name.strip():
            return
        new_path = parent_dir / name.strip()
        if new_path.exists():
            QMessageBox.warning(self, "Already Exists", f"'{name}' already exists.")
            return
        try:
            new_path.mkdir(parents=True)
        except OSError as e:
            QMessageBox.critical(self, "Error", f"Could not create folder:\n{e}")

    def _action_rename(self, source_index: QModelIndex) -> None:
        old_path = Path(self._fs_model.filePath(source_index))
        new_name, ok = QInputDialog.getText(
            self, "Rename", "New name:", text=old_path.name
        )
        if not ok or not new_name.strip() or new_name.strip() == old_path.name:
            return
        new_path = old_path.parent / new_name.strip()
        if new_path.exists():
            QMessageBox.warning(self, "Already Exists", f"'{new_name}' already exists.")
            return
        try:
            old_path.rename(new_path)
        except OSError as e:
            QMessageBox.critical(self, "Error", f"Could not rename:\n{e}")
            return
        self.file_renamed.emit(str(old_path), str(new_path))

    def _action_delete(self, source_index: QModelIndex) -> None:
        path = Path(self._fs_model.filePath(source_index))
        kind = "folder" if path.is_dir() else "file"
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete {kind} '{path.name}'?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError as e:
            QMessageBox.critical(self, "Error", f"Could not delete:\n{e}")
            return
        self.file_deleted.emit(str(path))

"""File explorer panel — shows project directory tree."""

import shutil
from pathlib import Path

from PyQt6.QtCore import (
    Qt,
    QTimer,
    pyqtSignal,
    QModelIndex,
    QSortFilterProxyModel,
    QEvent,
    QSize,
)
from PyQt6.QtGui import (
    QColor,
    QFileSystemModel,
    QIcon,
    QPalette,
)
from PyQt6.QtWidgets import (
    QDockWidget,
    QFileIconProvider,
    QFrame,
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

from meadowpy.resources.resource_loader import load_tinted_icon
from meadowpy.core.file_manager import is_known_unsupported_editor_file
from meadowpy.ui.item_delegates import NoFocusDelegate
from meadowpy.ui.panel_title_bar import (
    PANEL_TITLE_ICON_SIZE,
    PANEL_TITLE_ICON_BUTTON_SIZE,
    configure_panel_title_bar,
    configure_panel_title_label,
)


# ── Hidden names / suffixes filtered from the tree ──────────────────────
_HIDDEN_NAMES = {
    "__pycache__", ".git", ".venv", ".idea", ".vs", ".vscode",
    "node_modules", ".mypy_cache", ".pytest_cache", ".eggs",
}
_HIDDEN_SUFFIXES = {".pyc", ".pyo"}
_MAX_PREFETCH_SUBDIRS = 40
_PENDING_REEXPAND_DELAY_MS = 30
_BLOCKED_FILE_TOOLTIP = "This file type cannot be opened in MeadowPy's text editor."


def _name_is_visible_in_explorer(name: str) -> bool:
    if name in _HIDDEN_NAMES:
        return False
    return not any(name.endswith(suffix) for suffix in _HIDDEN_SUFFIXES)


def _directory_has_visible_entries(path: str) -> bool | None:
    try:
        for child in Path(path).iterdir():
            if _name_is_visible_in_explorer(child.name):
                return True
        return False
    except OSError:
        return None


class _ExplorerIconProvider(QFileIconProvider):
    """Supplies custom folder/file icons for the explorer tree.

    Folder color follows the current accent color; file icons are themed
    to light/dark for legibility.
    """

    def __init__(self, accent: str, is_dark: bool):
        super().__init__()
        self._folder: QIcon = QIcon()
        self._empty_folder: QIcon = QIcon()
        self._empty_text_color = "#6F766B"
        self._blocked_file: QIcon = QIcon()
        self._blocked_file_text_color = "#6F766B"
        self._file_generic: QIcon = QIcon()
        self._file_python: QIcon = QIcon()
        self.rebuild(accent, is_dark)

    def rebuild(self, accent: str, is_dark: bool) -> None:
        self._folder = load_tinted_icon("folder_closed", accent)
        empty_color = "#6F766B" if is_dark else "#9A9A9A"
        self._empty_folder = load_tinted_icon("folder_closed", empty_color)
        self._empty_text_color = empty_color
        self._blocked_file = load_tinted_icon("file_generic", empty_color)
        self._blocked_file_text_color = empty_color
        file_color = "#C8C8C8" if is_dark else "#6B6B6B"
        self._file_generic = load_tinted_icon("file_generic", file_color)
        self._file_python = load_tinted_icon("file_python", file_color)

    def empty_folder_icon(self) -> QIcon:
        return self._empty_folder

    def empty_text_color(self) -> str:
        return self._empty_text_color

    def blocked_file_icon(self) -> QIcon:
        return self._blocked_file

    def blocked_file_text_color(self) -> str:
        return self._blocked_file_text_color

    def icon(self, arg):  # type: ignore[override]
        if isinstance(arg, QFileIconProvider.IconType):
            if arg == QFileIconProvider.IconType.Folder:
                return self._folder
            return self._file_generic
        # QFileInfo
        if arg.isDir():
            return self._folder
        if is_known_unsupported_editor_file(arg.filePath()):
            return self._blocked_file
        suffix = arg.suffix().lower()
        if suffix == "py":
            return self._file_python
        return self._file_generic


class _ClickableLabel(QLabel):
    """QLabel that emits ``clicked`` on left-mouse release."""

    clicked = pyqtSignal()

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class _FilteredFileSystemModel(QSortFilterProxyModel):
    """Proxy that hides build artefacts and VCS directories."""

    def _is_known_unsupported_file(self, proxy_index: QModelIndex) -> bool:
        model = self.sourceModel()
        if model is None or not proxy_index.isValid():
            return False
        try:
            source_index = self.mapToSource(proxy_index)
            return (
                source_index.isValid()
                and not model.isDir(source_index)
                and is_known_unsupported_editor_file(model.filePath(source_index))
            )
        except AttributeError:
            return False

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.ToolTipRole and self._is_known_unsupported_file(
            index
        ):
            return _BLOCKED_FILE_TOOLTIP
        return super().data(index, role)

    def canFetchMore(self, parent: QModelIndex = QModelIndex()) -> bool:
        model = self.sourceModel()
        if model is None or not parent.isValid():
            return super().canFetchMore(parent)

        source_parent = self.mapToSource(parent)
        try:
            if model.isDir(source_parent):
                has_visible_entries = _directory_has_visible_entries(
                    model.filePath(source_parent)
                )
                if has_visible_entries is False:
                    return False
        except AttributeError:
            pass
        return super().canFetchMore(parent)

    def hasChildren(self, parent: QModelIndex = QModelIndex()) -> bool:
        model = self.sourceModel()
        if model is None or not parent.isValid():
            return super().hasChildren(parent)

        source_parent = self.mapToSource(parent)
        try:
            if model.isDir(source_parent):
                has_visible_entries = _directory_has_visible_entries(
                    model.filePath(source_parent)
                )
                if has_visible_entries is False:
                    return False
                if has_visible_entries is True:
                    return True
                if model.canFetchMore(source_parent):
                    return True
                return self.rowCount(parent) > 0
        except AttributeError:
            pass
        return super().hasChildren(parent)

    def filterAcceptsRow(
        self, source_row: int, source_parent: QModelIndex
    ) -> bool:
        model = self.sourceModel()
        index = model.index(source_row, 0, source_parent)
        name = model.fileName(index)
        return _name_is_visible_in_explorer(name)


class _FileExplorerItemDelegate(NoFocusDelegate):
    """Applies explorer-specific visual states to tree items."""

    def __init__(self, panel: "FileExplorerPanel", parent=None):
        super().__init__(parent)
        self._panel = panel

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        if self._panel._is_blocked_editor_file(index):
            color = QColor(self._panel._blocked_file_text_color())
            option.palette.setColor(QPalette.ColorRole.Text, color)
            option.palette.setColor(QPalette.ColorRole.HighlightedText, color)
            icon = self._panel._blocked_file_icon()
            if not icon.isNull():
                option.icon = icon
            return

        if not self._panel._is_known_empty_folder(index):
            return

        color = QColor(self._panel._empty_folder_text_color())
        option.palette.setColor(QPalette.ColorRole.Text, color)
        option.palette.setColor(QPalette.ColorRole.HighlightedText, color)
        icon = self._panel._empty_folder_icon()
        if not icon.isNull():
            option.icon = icon


class FileExplorerPanel(QDockWidget):
    """Left-side dock widget showing a project directory tree.

    Emits *file_selected(str)* when the user double-clicks a file.
    """

    file_selected = pyqtSignal(str)   # absolute file path
    file_renamed = pyqtSignal(str, str)  # (old_path, new_path)
    file_deleted = pyqtSignal(str)       # deleted path
    file_created = pyqtSignal(str)       # new file path (open in editor)
    change_folder_requested = pyqtSignal()  # user clicked the project badge
    root_folder_changed = pyqtSignal(str)  # active project folder root

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
        self._icon_provider: _ExplorerIconProvider | None = None
        self._title_icon_color: str = "#C8C8C8"
        # Paths the user has expanded but whose children are still being
        # fetched asynchronously — we re-expand with animation once loaded.
        self._pending_anim_paths: set[str] = set()
        self._suppress_expand_handler: bool = False

        self._setup_ui()

    # ── UI construction ─────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        # -- custom dock title bar ("EXPLORER" + action buttons) ---------
        title_bar = QFrame()
        title_bar.setObjectName("explorerTitleBar")
        title_bar.setFrameShape(QFrame.Shape.NoFrame)
        t_layout = QHBoxLayout(title_bar)
        configure_panel_title_bar(title_bar, t_layout, right_margin=4, spacing=2)

        title_label = QLabel("File Explorer")
        title_label.setObjectName("explorerTitleLabel")
        configure_panel_title_label(title_label)
        t_layout.addWidget(title_label, 0, Qt.AlignmentFlag.AlignVCenter)
        t_layout.addStretch()

        self._new_file_btn = self._make_icon_button("New File")
        self._new_file_btn.clicked.connect(self._on_title_new_file)
        t_layout.addWidget(self._new_file_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self._menu_btn = self._make_icon_button("More Actions")
        self._menu_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self._menu_btn)
        menu.addAction("Collapse All", self.collapse_all)
        menu.addAction("Refresh", self.refresh)
        self._menu_btn.setMenu(menu)
        t_layout.addWidget(self._menu_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        # Custom title bar is set as the dock's title bar so the dock
        # remains draggable via this widget. The border is split between
        # this frame (top/left/right) and the content frame below
        # (left/right/bottom) so together they form one continuous outline.
        self.setTitleBarWidget(title_bar)
        self._title_bar = title_bar

        # -- main container (content frame with left/right/bottom border) ─
        container = QFrame()
        container.setObjectName("explorerContainer")
        container.setFrameShape(QFrame.Shape.NoFrame)
        layout = QVBoxLayout(container)
        # Small bottom padding so the tree's square corners don't cover
        # the container's rounded bottom corners.
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(0)

        # -- folder info row (folder name + PROJECT badge) --------------
        folder_row = QWidget()
        folder_row.setObjectName("explorerFolderRow")
        folder_row.setFixedHeight(44)
        f_layout = QHBoxLayout(folder_row)
        f_layout.setContentsMargins(10, 10, 10, 6)
        f_layout.setSpacing(8)

        f_layout.addStretch()

        self._project_badge = _ClickableLabel("")
        self._project_badge.setObjectName("explorerProjectBadge")
        self._project_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._project_badge.clicked.connect(self.change_folder_requested.emit)
        f_layout.addWidget(self._project_badge)

        layout.addWidget(folder_row)

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
        self._tree.expanded.connect(self._on_item_expanded)
        self._tree.setItemDelegate(_FileExplorerItemDelegate(self, self._tree))
        self._tree.installEventFilter(self)
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
        folder_row.hide()
        self._folder_row = folder_row

        self.setWidget(container)
        self._refresh_title_icons()

    @staticmethod
    def _make_icon_button(tooltip: str) -> QToolButton:
        btn = QToolButton()
        btn.setObjectName("explorerTitleButton")
        btn.setToolTip(tooltip)
        btn.setAutoRaise(True)
        btn.setFixedSize(
            PANEL_TITLE_ICON_BUTTON_SIZE,
            PANEL_TITLE_ICON_BUTTON_SIZE,
        )
        btn.setIconSize(QSize(PANEL_TITLE_ICON_SIZE, PANEL_TITLE_ICON_SIZE))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    def _refresh_title_icons(self) -> None:
        """(Re)paint the title-bar icons in the current theme color."""
        color = self._title_icon_color
        if hasattr(self, "_new_file_btn"):
            self._new_file_btn.setIcon(load_tinted_icon("new_file_tinted", color))
        if hasattr(self, "_menu_btn"):
            self._menu_btn.setIcon(load_tinted_icon("chevron_down_tinted", color))

    def _on_title_new_file(self) -> None:
        if not self._root_path:
            return
        self._action_new_file(Path(self._root_path))

    # ── First-expand animation fix ──────────────────────────────────────
    #
    # QFileSystemModel fetches each directory's contents lazily on a worker
    # thread. If the user expands a folder before its contents have been
    # loaded, QTreeView's animation captures an empty "after" state and
    # the animation is effectively skipped — the children then pop in
    # abruptly when ``directoryLoaded`` fires later.
    #
    # Strategy: pre-fetch one level ahead only from folders the user expands.
    # Doing this from every ``directoryLoaded`` signal recursively walks large
    # folders such as Documents and can make the app appear hung.
    #
    # As a safety net, if a user expands a directory before its cache is
    # populated, we collapse silently, wait for the load, and re-expand.

    def _prefetch_subdirs(self, source_parent_index: QModelIndex) -> None:
        if not self._fs_model:
            return
        row_count = self._fs_model.rowCount(source_parent_index)
        for row in range(row_count):
            if row >= _MAX_PREFETCH_SUBDIRS:
                break
            child = self._fs_model.index(row, 0, source_parent_index)
            if self._fs_model.isDir(child) and self._fs_model.canFetchMore(child):
                self._fs_model.fetchMore(child)

    def _visible_child_count(
        self, proxy_index: QModelIndex, source_index: QModelIndex
    ) -> int:
        if self._proxy and proxy_index.isValid():
            try:
                return self._proxy.rowCount(proxy_index)
            except (AttributeError, RuntimeError):
                pass
        return self._fs_model.rowCount(source_index) if self._fs_model else 0

    def _is_known_empty_folder(self, proxy_index: QModelIndex) -> bool:
        if not proxy_index.isValid() or not self._fs_model or not self._proxy:
            return False
        source_index = self._proxy.mapToSource(proxy_index)
        if not source_index.isValid() or not self._fs_model.isDir(source_index):
            return False
        has_visible_entries = _directory_has_visible_entries(
            self._fs_model.filePath(source_index)
        )
        if has_visible_entries is not None:
            return not has_visible_entries
        if self._fs_model.canFetchMore(source_index):
            return False
        return self._visible_child_count(proxy_index, source_index) == 0

    def _empty_folder_icon(self) -> QIcon:
        if self._icon_provider is None:
            return QIcon()
        return self._icon_provider.empty_folder_icon()

    def _empty_folder_text_color(self) -> str:
        if self._icon_provider is None:
            return "#6F766B"
        return self._icon_provider.empty_text_color()

    def _is_blocked_editor_file(self, proxy_index: QModelIndex) -> bool:
        if not proxy_index.isValid() or not self._fs_model or not self._proxy:
            return False
        source_index = self._proxy.mapToSource(proxy_index)
        if not source_index.isValid() or self._fs_model.isDir(source_index):
            return False
        return is_known_unsupported_editor_file(self._fs_model.filePath(source_index))

    def _blocked_file_icon(self) -> QIcon:
        if self._icon_provider is None:
            return QIcon()
        return self._icon_provider.blocked_file_icon()

    def _blocked_file_text_color(self) -> str:
        if self._icon_provider is None:
            return "#6F766B"
        return self._icon_provider.blocked_file_text_color()

    def _select_file_if_openable(self, proxy_index: QModelIndex) -> bool:
        if not self._fs_model or not self._proxy or not proxy_index.isValid():
            return False
        source_index = self._proxy.mapToSource(proxy_index)
        if not source_index.isValid() or self._fs_model.isDir(source_index):
            return False
        if self._is_blocked_editor_file(proxy_index):
            return False
        self.file_selected.emit(self._fs_model.filePath(source_index))
        return True

    def _collapse_without_animation(self, proxy_index: QModelIndex) -> None:
        was_animated = (
            self._tree.isAnimated()
            if hasattr(self._tree, "isAnimated")
            else True
        )
        if hasattr(self._tree, "setAnimated"):
            self._tree.setAnimated(False)
        self._suppress_expand_handler = True
        try:
            self._tree.collapse(proxy_index)
        finally:
            self._suppress_expand_handler = False
            if hasattr(self._tree, "setAnimated"):
                self._tree.setAnimated(was_animated)

    def _on_item_expanded(self, proxy_index: QModelIndex) -> None:
        if self._suppress_expand_handler or not self._fs_model or not self._proxy:
            return
        source_index = self._proxy.mapToSource(proxy_index)

        # Fallback: if this folder's own contents aren't cached yet, the
        # animation we just ran was a no-op. Collapse silently, fetch,
        # and re-expand once loaded.
        if self._fs_model.canFetchMore(source_index):
            path = self._fs_model.filePath(source_index)
            self._pending_anim_paths.add(path)
            self._collapse_without_animation(proxy_index)
            self._fs_model.fetchMore(source_index)
            return

        if self._visible_child_count(proxy_index, source_index) == 0:
            self._collapse_without_animation(proxy_index)
            self._tree.viewport().update()
            return

        # Pre-fetch grandchildren so the NEXT expand down also animates.
        self._prefetch_subdirs(source_index)

    def _on_directory_loaded(self, path: str) -> None:
        if not self._fs_model or not self._proxy:
            return

        source_index = self._fs_model.index(path)

        # If this load fulfils a pending re-expand, animate it now.
        if path in self._pending_anim_paths:
            self._pending_anim_paths.discard(path)
            proxy_index = self._proxy.mapFromSource(source_index)
            if proxy_index.isValid():
                if self._visible_child_count(proxy_index, source_index) == 0:
                    self._tree.viewport().update()
                    return
                # Give Qt a moment to publish the newly loaded rows and finish
                # the forced non-animated collapse before expanding for real.
                QTimer.singleShot(
                    _PENDING_REEXPAND_DELAY_MS,
                    lambda idx=proxy_index: self._tree.expand(idx),
                )
                self._prefetch_subdirs(source_index)
                return

        if self._root_path and Path(path).resolve() == Path(self._root_path).resolve():
            self._prefetch_subdirs(source_index)

        self._tree.viewport().update()

    # ── Public API ──────────────────────────────────────────────────────

    def set_root_folder(self, folder_path: str) -> None:
        """Set (or change) the root directory shown in the tree."""
        self._root_path = folder_path
        self._pending_anim_paths.clear()

        # Create model + proxy once, reuse on subsequent calls
        if self._fs_model is None:
            self._fs_model = QFileSystemModel(self)
            self._fs_model.setReadOnly(True)
            if self._icon_provider is not None:
                self._fs_model.setIconProvider(self._icon_provider)
            self._fs_model.directoryLoaded.connect(self._on_directory_loaded)

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

        # Update pill badge
        folder_name = Path(folder_path).name
        self._project_badge.setText(folder_name.upper())
        self._project_badge.setToolTip(f"{folder_path}\n\nClick to switch project folder")

        # Switch from empty state to tree
        self._empty_label.hide()
        self._tree.show()
        self._folder_row.show()
        self.root_folder_changed.emit(folder_path)

    def collapse_all(self) -> None:
        """Collapse every expanded node."""
        # Disable animation around collapseAll: with QFileSystemModel's async
        # directory loads in flight, animated collapse of a deep tree can
        # crash (visualRect calculations against indexes that vanish mid-anim).
        was_animated = self._tree.isAnimated()
        self._tree.setAnimated(False)
        self._suppress_expand_handler = True
        try:
            self._tree.collapseAll()
        finally:
            self._suppress_expand_handler = False
            self._tree.setAnimated(was_animated)
        # scrollToTop is safe; scrollTo(rootIndex) is not — the root has no row.
        self._tree.scrollToTop()

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

    def apply_icon_theme(self, accent: str, is_dark: bool) -> None:
        """Build (or rebuild) the custom icon provider with the given accent."""
        if self._icon_provider is None:
            self._icon_provider = _ExplorerIconProvider(accent, is_dark)
        else:
            self._icon_provider.rebuild(accent, is_dark)
        if self._fs_model is not None:
            self._fs_model.setIconProvider(self._icon_provider)
            # Force the view to repaint by nudging the root
            root = self._tree.rootIndex()
            if root.isValid():
                self._tree.viewport().update()

        # Retint the title-bar action icons to match the theme.
        self._title_icon_color = "#C8C8C8" if is_dark else "#6B6B6B"
        self._refresh_title_icons()

        # Re-style the PROJECT pill badge so its background/border/text
        # track the current accent (including custom themes).
        self._apply_badge_style(accent, is_dark)

    def _apply_badge_style(self, accent: str, is_dark: bool) -> None:
        # Neutral fill + text so the badge reads as a chip; accent only
        # appears as the border for a subtle theme accent.
        if is_dark:
            bg = "#2A2A2A"
            hover_bg = "#3A3A3A"
            text = "#C8C8C8"
            hover_text = "#FFFFFF"
        else:
            bg = "#F0F0F0"
            hover_bg = "#E0E0E0"
            text = "#6B6B6B"
            hover_text = "#1F1F1F"
        border = accent
        self._project_badge.setStyleSheet(
            "#explorerProjectBadge {"
            f" color: {text};"
            f" background: {bg};"
            f" border: 1px solid {border};"
            " border-radius: 4px;"
            " padding: 1px 7px;"
            " font-size: 10px;"
            " font-weight: bold;"
            " letter-spacing: 0.5px;"
            "}"
            "#explorerProjectBadge:hover {"
            f" color: {hover_text};"
            f" background: {hover_bg};"
            "}"
        )

    # ── Keyboard handling ────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        """Handle Enter/Return on the tree to open files or toggle folders."""
        if obj is self._tree and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                proxy_index = self._tree.currentIndex()
                if proxy_index.isValid() and self._proxy and self._fs_model:
                    source_index = self._proxy.mapToSource(proxy_index)
                    if self._fs_model.isDir(source_index):
                        # Toggle expand/collapse for folders
                        if self._tree.isExpanded(proxy_index):
                            self._tree.collapse(proxy_index)
                        else:
                            self._tree.expand(proxy_index)
                    else:
                        # Open the file
                        self._select_file_if_openable(proxy_index)
                return True
        return super().eventFilter(obj, event)

    # ── Slots ───────────────────────────────────────────────────────────

    def _on_double_clicked(self, proxy_index: QModelIndex) -> None:
        self._select_file_if_openable(proxy_index)

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

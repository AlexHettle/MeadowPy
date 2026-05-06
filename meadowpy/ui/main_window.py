"""Main application window."""

from pathlib import Path

from PyQt6.QtCore import QByteArray, QTimer, Qt
from PyQt6.QtGui import QIcon, QKeySequence
from PyQt6.QtWidgets import QMainWindow

from meadowpy.constants import APP_NAME
from meadowpy.core.settings import Settings
from meadowpy.core.file_manager import FileManager
from meadowpy.core.recent_files import RecentFilesManager
from meadowpy.resources.resource_loader import (
    current_accent_hex,
    load_themed_icon,
    run_button_accent_hex,
    theme_is_dark,
)
from meadowpy.ui.tab_manager import TabManager
from meadowpy.ui.menu_bar import MenuBarBuilder
from meadowpy.ui.tool_bar import ToolBarBuilder
from meadowpy.ui.status_bar import StatusBarManager
from meadowpy.ui.find_replace_bar import FindReplaceBar
from meadowpy.ui.file_explorer import FileExplorerPanel
from meadowpy.ui.symbol_outline import SymbolOutlinePanel
from meadowpy.ui.problems_panel import ProblemsPanel
from meadowpy.ui.output_panel import OutputPanel
from meadowpy.ui.search_panel import SearchPanel
from meadowpy.core.interpreter_manager import InterpreterManager
from meadowpy.ui.variable_inspector import VariableInspectorPanel
from meadowpy.ui.call_stack_panel import CallStackPanel
from meadowpy.ui.watch_panel import WatchPanel
from meadowpy.ui.ai_chat_panel import AIChatPanel
from meadowpy.ui.controllers import (
    AIAssistantController,
    CodeQualityController,
    DebugController,
    ExecutionController,
    MainWindowContext,
    WorkspaceController,
)


class MainWindow(QMainWindow):
    """The main application window."""

    def __init__(
        self,
        settings: Settings,
        file_manager: FileManager,
        recent_files: RecentFilesManager,
        app_icon: QIcon | None = None,
    ):
        super().__init__()
        if app_icon is not None and not app_icon.isNull():
            # Apply the icon before native window state is created so Windows
            # does not latch onto a fallback taskbar icon first.
            self.setWindowIcon(app_icon)
        self._settings = settings
        self._file_manager = file_manager
        self._recent_files = recent_files
        self._controller_context = MainWindowContext(
            window=self,
            settings=settings,
            file_manager=file_manager,
            recent_files=recent_files,
        )
        self._workspace_controller = WorkspaceController(self._controller_context)
        self._code_quality_controller = CodeQualityController(self._controller_context)
        self._execution_controller = ExecutionController(self._controller_context)
        self._debug_controller = DebugController(self._controller_context)
        self._ai_assistant_controller = AIAssistantController(self._controller_context)
        self._controllers = (
            self._workspace_controller,
            self._code_quality_controller,
            self._execution_controller,
            self._debug_controller,
            self._ai_assistant_controller,
        )

        self._setup_window()
        self._create_tab_manager()
        self._create_file_explorer()
        self._create_symbol_outline()
        self._create_problems_panel()
        self._create_output_panel()
        self._create_search_panel()
        self._create_lint_runner()
        self._create_process_runner()
        self._create_repl_manager()
        self._create_run_actions()
        self._create_debug_manager()
        self._create_debug_panels()
        self._create_debug_actions()
        self._create_ollama_client()
        self._create_ai_chat_panel()
        self._create_menu_bar()
        self._create_tool_bar()
        self._create_debug_toolbar()
        self._create_status_bar()
        self._create_find_replace_bar()
        self._connect_signals()
        self._restore_state()
        self._initial_refresh_pending = True

        # Apply the current theme's accent to the Run button glows. Light/Dark
        # themes pass through the original green; Custom passes the user's
        # chosen accent color.
        initial_accent = run_button_accent_hex(
            self._settings.get("editor.theme"),
            self._settings.get("editor.custom_theme.accent"),
        )
        self._toolbar_builder.update_accent_color(initial_accent)
        self._output_panel.update_accent_color(initial_accent)

        # Defer the first outline/lint refresh until the first real showEvent.
        # The splash screen keeps the event loop alive during startup, so a
        # singleShot queued here could fire before the window is visible.

    def __getattr__(self, name: str):
        """Resolve moved MainWindow behavior on focused controllers."""
        controllers = self.__dict__.get("_controllers", ())
        for controller in controllers:
            try:
                return object.__getattribute__(controller, name)
            except AttributeError:
                continue
        raise AttributeError(f"{type(self).__name__!s} has no attribute {name!r}")

    def _setup_window(self) -> None:
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(800, 600)
        self.resize(1200, 800)
        self.setAcceptDrops(True)

        # Put dock-widget tabs on top instead of bottom
        from PyQt6.QtWidgets import QTabWidget
        self.setTabPosition(
            Qt.DockWidgetArea.BottomDockWidgetArea, QTabWidget.TabPosition.North
        )
        self.setTabPosition(
            Qt.DockWidgetArea.RightDockWidgetArea, QTabWidget.TabPosition.North
        )
        self.setTabPosition(
            Qt.DockWidgetArea.LeftDockWidgetArea, QTabWidget.TabPosition.North
        )

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._initial_refresh_pending:
            self._initial_refresh_pending = False
            QTimer.singleShot(0, self._initial_refresh)

    def _create_tab_manager(self) -> None:
        from PyQt6.QtWidgets import QFrame, QVBoxLayout

        self._tab_manager = TabManager(self._settings, self)

        # Wrap the editor in a styled container so it picks up the same
        # rounded-bottom-corner border treatment as the surrounding panels.
        container = QFrame()
        container.setObjectName("editorContainer")
        container.setFrameShape(QFrame.Shape.NoFrame)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._tab_manager)
        self.setCentralWidget(container)

    def _apply_explorer_icon_theme(self) -> None:
        """Push the current accent + base to the file explorer's icon
        provider, and keep the symbol outline's glyph color in sync."""
        theme = self._settings.get("editor.theme")
        custom_base = self._settings.get("editor.custom_theme.base")
        accent = current_accent_hex(
            theme, custom_base, self._settings.get("editor.custom_theme.accent")
        )
        is_dark = theme_is_dark(theme, custom_base)
        if hasattr(self, "_file_explorer"):
            self._file_explorer.apply_icon_theme(accent, is_dark)
        if hasattr(self, "_symbol_outline"):
            self._symbol_outline.apply_icon_theme(accent, is_dark)

    def _create_file_explorer(self) -> None:
        """Create the file explorer dock widget on the left side."""
        self._file_explorer = FileExplorerPanel(self)
        self.addDockWidget(
            Qt.DockWidgetArea.LeftDockWidgetArea, self._file_explorer
        )
        self._apply_explorer_icon_theme()

        # Restore last project folder if it still exists
        project_folder = self._settings.get("general.project_folder")
        if project_folder and Path(project_folder).is_dir():
            self._file_explorer.set_root_folder(project_folder)

        if not self._settings.get("explorer.show_file_explorer"):
            self._file_explorer.hide()

        self._file_explorer.file_selected.connect(
            self._on_explorer_file_selected
        )
        self._file_explorer.file_created.connect(
            self._on_explorer_file_selected
        )
        self._file_explorer.file_renamed.connect(
            self._on_explorer_file_renamed
        )
        self._file_explorer.file_deleted.connect(
            self._on_explorer_file_deleted
        )
        self._file_explorer.change_folder_requested.connect(
            self.action_open_folder
        )

    def _create_symbol_outline(self) -> None:
        """Create the symbol outline dock widget on the right side."""
        self._symbol_outline = SymbolOutlinePanel(self)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._symbol_outline
        )
        # Push the current accent color so class/function glyphs are
        # tinted immediately on startup (not just after a theme change).
        self._apply_explorer_icon_theme()
        if not self._settings.get("editor.show_symbol_outline"):
            self._symbol_outline.hide()
        self._symbol_outline.navigate_to_line.connect(self._on_outline_navigate)
        # Refresh outline when it becomes visible (e.g. toggled from View menu)
        self._symbol_outline.visibilityChanged.connect(self._on_outline_visibility_changed)

        # Debounce timer for outline refresh
        self._outline_timer = QTimer(self)
        self._outline_timer.setSingleShot(True)
        self._outline_timer.setInterval(500)
        self._outline_timer.timeout.connect(self._do_refresh_outline)

    def _create_problems_panel(self) -> None:
        """Create the problems panel dock widget at the bottom."""
        self._problems_panel = ProblemsPanel(self, settings=self._settings)
        self.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea, self._problems_panel
        )
        if not self._settings.get("editor.linting_enabled"):
            self._problems_panel.hide()
        self._problems_panel.navigate_to.connect(self._on_problem_navigate)
        self._problems_panel.ai_fix_requested.connect(
            self._on_lint_ai_fix_requested
        )

    def _create_output_panel(self) -> None:
        """Create the output panel and tabify with problems panel."""
        self._output_panel = OutputPanel(self, settings=self._settings)
        self.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea, self._output_panel
        )
        # Tabify so Output and Problems share the bottom as tabs
        self.tabifyDockWidget(self._problems_panel, self._output_panel)
        # Start with problems tab visible (output shows on first run)
        self._problems_panel.raise_()

        self._output_panel.set_max_lines(
            self._settings.get("run.max_output_lines")
        )

        # Wire the output panel's Run/Stop buttons
        self._output_panel.run_button.clicked.connect(self.action_run_file)
        self._output_panel.stop_button.clicked.connect(self.action_stop_process)
        self._output_panel.input_submitted.connect(self._on_stdin_submitted)
        self._output_panel.traceback_navigate.connect(
            self._on_traceback_navigate
        )
        self._output_panel.ai_fix_requested.connect(
            self._on_output_ai_fix_requested
        )

        self._interpreter_manager = InterpreterManager()

    def _create_search_panel(self) -> None:
        """Create the search-across-files panel, tabified at the bottom."""
        self._search_panel = SearchPanel(self)
        self.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea, self._search_panel
        )
        self.tabifyDockWidget(self._output_panel, self._search_panel)
        self._search_panel.hide()

        # Keep the search panel's root path in sync with the project folder
        project_folder = self._settings.get("general.project_folder")
        if project_folder and Path(project_folder).is_dir():
            self._search_panel.set_root_path(project_folder)

        self._search_panel.navigate_to_file.connect(
            self._on_search_navigate
        )

    def _create_run_actions(self) -> None:
        """Create shared Run/Stop QActions used by menu, toolbar, and output panel."""
        theme_name = self._settings.get("editor.theme") or ""

        self._run_action = self._make_action(
            load_themed_icon("run", theme_name),
            "Run File", "F5", self.action_run_file,
        )
        self._run_action.setToolTip("Run your Python file (F5)")
        self._stop_action = self._make_action(
            load_themed_icon("stop", theme_name),
            "Stop Process", "Ctrl+F5", self.action_stop_process,
        )
        self._stop_action.setToolTip("Stop the running program (Ctrl+F5)")
        self._stop_action.setEnabled(False)

    def _refresh_themed_icons(self) -> None:
        """Reload every theme-sensitive icon so theme switches take effect.

        Called from the settings-changed handler. Without this, QActions
        created at startup keep their initial icons forever — switching
        from High Contrast back to Dark would leave Run/Stop/Debug as the
        white HC silhouettes instead of restoring the green/red/orange
        brand colors (and vice-versa).
        """
        theme_name = self._settings.get("editor.theme") or ""
        for attr, icon_name in (
            ("_run_action", "run"),
            ("_stop_action", "stop"),
            ("_debug_action", "debug"),
            ("_restart_console_action", "restart"),
        ):
            action = getattr(self, attr, None)
            if action is not None:
                action.setIcon(load_themed_icon(icon_name, theme_name))

        # Output panel's own toolbar buttons (run / stop / restart REPL)
        op = getattr(self, "_output_panel", None)
        if op is not None:
            for attr, icon_name in (
                ("_run_btn", "run"),
                ("_stop_btn", "stop"),
                ("_restart_repl_btn", "restart"),
            ):
                btn = getattr(op, attr, None)
                if btn is not None:
                    btn.setIcon(load_themed_icon(icon_name, theme_name))

    def _make_action(self, icon_or_path, text, shortcut, callback):
        from PyQt6.QtGui import QAction
        if isinstance(icon_or_path, QIcon):
            icon = icon_or_path
        elif icon_or_path:
            icon = QIcon(icon_or_path)
        else:
            icon = QIcon()
        action = QAction(icon, text, self)
        action.setShortcut(QKeySequence(shortcut))
        action.setToolTip(f"{text} ({shortcut})")
        action.triggered.connect(callback)
        return action

    def _create_debug_panels(self) -> None:
        """Create the debug dock panels (Variables, Call Stack, Watch)."""
        # Variable inspector — right side (tabified with outline)
        self._variable_inspector = VariableInspectorPanel(self)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._variable_inspector
        )
        self.tabifyDockWidget(self._symbol_outline, self._variable_inspector)
        self._variable_inspector.hide()

        # Call stack — right side
        self._call_stack_panel = CallStackPanel(self)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._call_stack_panel
        )
        self.tabifyDockWidget(self._variable_inspector, self._call_stack_panel)
        self._call_stack_panel.hide()

        # Watch panel — right side
        self._watch_panel = WatchPanel(self)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._watch_panel
        )
        self.tabifyDockWidget(self._call_stack_panel, self._watch_panel)
        self._watch_panel.hide()

        # Wire watch evaluate signal
        self._watch_panel.evaluate_requested.connect(
            lambda expr: self._debug_manager.send_evaluate(expr)
        )

    def _create_debug_actions(self) -> None:
        """Create shared debug QActions used by menu, toolbar, and debug toolbar."""
        theme_name = self._settings.get("editor.theme") or ""
        self._debug_action = self._make_action(
            load_themed_icon("debug", theme_name),
            "Start Debugging", "F6", self.action_start_debug,
        )
        self._debug_action.setToolTip("Run with debugger \u2014 pause at breakpoints (F6)")

    def _create_ai_chat_panel(self) -> None:
        """Create the AI chat sidebar panel on the right side."""
        self._ai_chat_panel = AIChatPanel(self)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._ai_chat_panel
        )
        # Tabify with symbol outline so they share the right side
        self.tabifyDockWidget(self._symbol_outline, self._ai_chat_panel)
        self._ai_chat_panel.hide()  # hidden by default, toggled from View menu

        # Set initial model name, accent, and connection state
        model = self._settings.get("ollama.selected_model") or ""
        self._ai_chat_panel.set_model_name(model)
        theme = self._settings.get("editor.theme")
        custom_base = self._settings.get("editor.custom_theme.base")
        self._ai_chat_panel.apply_accent(
            current_accent_hex(
                theme, custom_base,
                self._settings.get("editor.custom_theme.accent"),
            ),
            theme_is_dark(theme, custom_base),
        )
        self._ai_chat_panel.set_connected(self._ollama_client.is_connected)

        # Wire chat panel → send request
        self._ai_chat_panel.chat_requested.connect(self._on_chat_requested)
        self._ai_chat_panel.chat_stop_requested.connect(
            self._ollama_client.cancel_chat
        )
        self._ai_chat_panel.code_insert_requested.connect(
            self._on_code_insert_requested
        )

        # Wire ollama client → chat panel (streaming)
        self._ollama_client.chat_token.connect(self._ai_chat_panel.append_token)
        self._ollama_client.chat_finished.connect(self._ai_chat_panel.finish_response)
        self._ollama_client.chat_error.connect(self._ai_chat_panel.show_error)

        # Wire connection/model changes → chat panel
        self._ollama_client.connection_changed.connect(
            lambda connected, msg: self._ai_chat_panel.set_connected(connected)
        )
        self._ollama_client.model_selected.connect(
            self._ai_chat_panel.set_model_name
        )

    def _create_debug_toolbar(self) -> None:
        """Wire the inline debug step actions (created by ToolBarBuilder)."""
        self._step_over_action.triggered.connect(self.action_debug_step_over)
        self._step_into_action.triggered.connect(self.action_debug_step_into)
        self._step_out_action.triggered.connect(self.action_debug_step_out)

    def _create_menu_bar(self) -> None:
        self._menu_builder = MenuBarBuilder(self)
        self._menu_builder.build()

    def _create_tool_bar(self) -> None:
        self._toolbar_builder = ToolBarBuilder(self)
        self._toolbar_builder.build()

    def _create_status_bar(self) -> None:
        self._status_bar_manager = StatusBarManager(self.statusBar(), self._settings)
        self._status_bar_manager.ollama_label.clicked.connect(
            self._on_ollama_status_clicked
        )

    def _create_find_replace_bar(self) -> None:
        self._find_replace_bar = FindReplaceBar(self)

    def _connect_signals(self) -> None:
        # Tab changes -> update status bar
        self._tab_manager.tab_changed.connect(self._on_tab_changed)

        # Recent files changes -> rebuild menu
        self._recent_files.recent_files_changed.connect(
            lambda _: self._menu_builder.rebuild_recent_files_menu()
        )

        # File saved -> status bar message + lint
        self._file_manager.file_saved.connect(self._on_file_saved)

        # Settings changed -> update all editors
        self._settings.settings_changed.connect(self._on_settings_changed)

    def dragEnterEvent(self, event) -> None:
        """Accept drags that contain file URLs."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        """Keep accepting while dragging over the window."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        """Open each dropped file in a new tab."""
        if not event.mimeData().hasUrls():
            super().dropEvent(event)
            return
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            file_path = url.toLocalFile()
            path = Path(file_path)
            if path.is_dir():
                # Dropping a folder opens it in the file explorer
                self._file_explorer.set_root_folder(file_path)
                self._file_explorer.show()
                self._settings.set("general.project_folder", file_path)
                self._search_panel.set_root_path(file_path)
            elif path.is_file():
                content = self._file_manager.read_file(file_path)
                self._tab_manager.open_file_in_tab(file_path, content)
                self._recent_files.add(file_path)
        event.acceptProposedAction()

    def closeEvent(self, event) -> None:
        """Handle window close: save files, persist state, stop background work."""
        if not self._tab_manager.prompt_save_all():
            event.ignore()
            return

        self._save_state()
        self._settings.save()
        self._shutdown_background_work()
        event.accept()

    def _shutdown_background_work(self) -> None:
        """Stop long-running workers and subprocesses before Qt destroys widgets."""
        self._ollama_client.stop()
        self._lint_runner.stop()
        self._search_panel.stop()

        if self._debug_manager.is_running():
            self._debug_manager.stop_debug()
        if self._process_runner.is_running():
            self._process_runner.stop()
        if self._repl_manager.is_running:
            self._repl_manager.stop()

    def resizeEvent(self, event) -> None:
        """Reposition the find bar on window resize."""
        super().resizeEvent(event)
        if hasattr(self, "_find_replace_bar") and self._find_replace_bar.isVisible():
            self._find_replace_bar._reposition()

    def _save_state(self) -> None:
        """Persist window geometry and open files to settings."""
        self._settings.set(
            "window.geometry",
            self.saveGeometry().toBase64().data().decode(),
        )
        self._settings.set(
            "window.state",
            self.saveState().toBase64().data().decode(),
        )
        open_files = self._tab_manager.get_open_file_paths()
        self._settings.set("general.open_files", open_files)

    def _restore_state(self) -> None:
        """Restore window geometry and reopen previous files."""
        geom = self._settings.get("window.geometry")
        if geom:
            try:
                self.restoreGeometry(QByteArray.fromBase64(geom.encode()))
            except Exception:
                pass

        state = self._settings.get("window.state")
        if state:
            try:
                self.restoreState(QByteArray.fromBase64(state.encode()))
            except Exception:
                pass

        # Restore open tabs
        if self._settings.get("general.restore_tabs_on_startup"):
            for path in self._settings.get("general.open_files", []):
                if Path(path).exists():
                    content = self._file_manager.read_file(path)
                    self._tab_manager.open_file_in_tab(path, content)

        # If no tabs restored, show the Welcome screen
        if self._tab_manager.count() == 0:
            self._show_welcome()

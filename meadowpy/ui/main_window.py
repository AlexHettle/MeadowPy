"""Main application window."""

from pathlib import Path

from PyQt6.QtCore import QByteArray, QTimer, Qt
from PyQt6.QtGui import QIcon, QKeySequence
from PyQt6.QtWidgets import QMainWindow, QInputDialog, QMessageBox, QApplication
from PyQt6.Qsci import QsciScintilla

from meadowpy.constants import APP_NAME, VERSION
from meadowpy.core.settings import Settings
from meadowpy.core.file_manager import FileManager
from meadowpy.core.recent_files import RecentFilesManager
from meadowpy.core.linter import LintRunner
from meadowpy.editor.code_editor import CodeEditor
from meadowpy.editor.editor_config import EditorConfigurator
from meadowpy.resources.resource_loader import (
    current_accent_hex,
    get_icon_path,
    get_stylesheet,
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
from meadowpy.core.process_runner import ProcessRunner
from meadowpy.core.repl_manager import ReplManager
from meadowpy.core.interpreter_manager import InterpreterManager
from meadowpy.core.debug_manager import DebugManager, DebugState
from meadowpy.ui.variable_inspector import VariableInspectorPanel
from meadowpy.ui.call_stack_panel import CallStackPanel
from meadowpy.ui.watch_panel import WatchPanel
from meadowpy.core.ollama_client import OllamaClient
from meadowpy.ui.model_selector import ModelSelectorPopup
from meadowpy.ui.ai_chat_panel import AIChatPanel


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

        # Apply the current theme's accent to the Run button glows. Light/Dark
        # themes pass through the original green; Custom passes the user's
        # chosen accent color.
        initial_accent = run_button_accent_hex(
            self._settings.get("editor.theme"),
            self._settings.get("editor.custom_theme.accent"),
        )
        self._toolbar_builder.update_accent_color(initial_accent)
        self._output_panel.update_accent_color(initial_accent)

        # Defer initial outline/lint refresh until after the window is shown,
        # because isVisible() returns False during __init__.
        QTimer.singleShot(0, self._initial_refresh)

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

    def _create_process_runner(self) -> None:
        """Create the process runner and wire its signals."""
        self._process_runner = ProcessRunner(self)
        self._process_runner.output_received.connect(self._on_process_output)
        self._process_runner.process_started.connect(self._on_process_started)
        self._process_runner.process_finished.connect(self._on_process_finished)

    def _create_repl_manager(self) -> None:
        """Create the interactive REPL manager and wire its signals."""
        self._repl_manager = ReplManager(self)
        self._repl_manager.output_received.connect(self._on_repl_output)
        self._repl_manager.repl_started.connect(self._on_repl_started)
        self._repl_manager.repl_stopped.connect(self._on_repl_stopped)
        self._repl_manager.prompt_ready.connect(
            self._output_panel.update_repl_prompt
        )

        # Wire output panel REPL signals
        self._output_panel.repl_input_submitted.connect(self._on_repl_input)
        self._output_panel.repl_restart_requested.connect(self._on_repl_restart)
        self._output_panel.repl_history_up.connect(self._on_repl_history_up)
        self._output_panel.repl_history_down.connect(self._on_repl_history_down)

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

    def _create_debug_manager(self) -> None:
        """Create the debug manager and wire its signals."""
        self._debug_manager = DebugManager(self)
        self._debug_manager.state_changed.connect(self._on_debug_state_changed)
        self._debug_manager.paused.connect(self._on_debug_paused)
        self._debug_manager.resumed.connect(self._on_debug_resumed)
        self._debug_manager.eval_result.connect(self._on_debug_eval_result)
        self._debug_manager.debug_output.connect(self._on_process_output)
        self._debug_manager.debug_started.connect(self._on_debug_started)
        self._debug_manager.debug_finished.connect(self._on_debug_finished)

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

    def _create_ollama_client(self) -> None:
        """Create the Ollama connection manager and model selector popup."""
        self._ollama_client = OllamaClient(self._settings, self)
        self._model_selector = ModelSelectorPopup(self)

        # Wire signals
        self._ollama_client.connection_changed.connect(
            self._on_ollama_connection_changed
        )
        self._ollama_client.models_updated.connect(
            self._on_ollama_models_updated
        )
        self._model_selector.model_chosen.connect(self._on_model_chosen)

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

    def _create_lint_runner(self) -> None:
        """Create the lint runner and debounce timer."""
        self._lint_runner = LintRunner(self)
        self._lint_runner.lint_finished.connect(self._on_lint_finished)
        self._lint_runner.lint_error.connect(self._on_lint_error)

        self._lint_timer = QTimer(self)
        self._lint_timer.setSingleShot(True)
        self._lint_timer.setInterval(
            self._settings.get("editor.lint_delay_ms")
        )
        self._lint_timer.timeout.connect(self._do_lint)

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

    def _initial_refresh(self) -> None:
        """Run the first outline + lint update after the window is visible."""
        editor = self._tab_manager.current_editor()
        if editor:
            self._refresh_symbol_outline(editor)
            self._do_lint()
            self._update_interpreter_label()
        self._ollama_client.start()
        # Start the interactive Python console
        if self._settings.get("repl.auto_start"):
            self._start_repl()

    # ── Welcome screen ─────────────────────────────────────────────

    def _show_welcome(self) -> None:
        """Show the Welcome tab and wire its signals."""
        from meadowpy.ui.welcome_widget import WelcomeWidget

        # Check if a welcome tab already exists — avoid double-connecting
        for i in range(self._tab_manager.count()):
            if isinstance(self._tab_manager.widget(i), WelcomeWidget):
                self._tab_manager.setCurrentIndex(i)
                return

        is_dark = theme_is_dark(
            self._settings.get("editor.theme"),
            self._settings.get("editor.custom_theme.base"),
        )
        welcome = self._tab_manager.show_welcome_tab(is_dark=is_dark)
        welcome.action_new_file.connect(self._welcome_new_file)
        welcome.action_open_file.connect(self.action_open_file)
        welcome.action_open_folder.connect(self.action_open_folder)
        welcome.template_selected.connect(self._on_template_selected)

    def _welcome_new_file(self) -> None:
        """New File from welcome: close welcome tab, open blank tab."""
        self._tab_manager.close_welcome_tab()
        self._tab_manager.new_tab()

    def _on_template_selected(self, name: str, code: str) -> None:
        """Open a new untitled tab pre-filled with the template code."""
        self._tab_manager.close_welcome_tab()
        editor = self._tab_manager.new_tab()
        editor.setText(code)
        editor.setModified(False)

    def action_show_welcome(self) -> None:
        """Re-show the welcome tab (accessible from Help menu)."""
        self._show_welcome()

    # --- Action handlers ---

    def action_new_file(self) -> None:
        self._tab_manager.new_tab()

    def action_open_file(self) -> None:
        result = self._file_manager.open_file(parent=self)
        if result:
            path, content = result
            self._tab_manager.open_file_in_tab(path, content)

    def action_open_folder(self) -> None:
        """Show a directory picker and set it as the project folder."""
        from PyQt6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(
            self, "Open Folder", "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if folder:
            self._file_explorer.set_root_folder(folder)
            self._file_explorer.show()
            self._settings.set("general.project_folder", folder)
            self._search_panel.set_root_path(folder)

    def _on_explorer_file_selected(self, file_path: str) -> None:
        """Open a file from the explorer in an editor tab."""
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return
        content = self._file_manager.read_file(file_path)
        self._tab_manager.open_file_in_tab(file_path, content)
        self._recent_files.add(file_path)

    def _on_explorer_file_renamed(self, old_path: str, new_path: str) -> None:
        """Update any open tab whose file was renamed in the explorer."""
        old_resolved = str(Path(old_path).resolve())
        for i in range(self._tab_manager.count()):
            editor = self._tab_manager.widget(i)
            if not isinstance(editor, CodeEditor) or not editor.file_path:
                continue
            if str(Path(editor.file_path).resolve()) == old_resolved:
                editor.file_path = new_path
                editor._is_modified = False
                self._tab_manager.setTabText(i, Path(new_path).name)
                self._tab_manager.setTabToolTip(i, new_path)
                break

    def _on_explorer_file_deleted(self, deleted_path: str) -> None:
        """Close any open tab whose file was deleted in the explorer."""
        deleted_resolved = str(Path(deleted_path).resolve())
        # Iterate in reverse so indices stay valid after removal
        for i in range(self._tab_manager.count() - 1, -1, -1):
            editor = self._tab_manager.widget(i)
            if not isinstance(editor, CodeEditor) or not editor.file_path:
                continue
            editor_resolved = str(Path(editor.file_path).resolve())
            # Match exact file or any file inside a deleted folder
            if (editor_resolved == deleted_resolved
                    or editor_resolved.startswith(deleted_resolved + "\\")):
                self._tab_manager.removeTab(i)

    # ── Drag & Drop ──────────────────────────────────────────────────
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

    def action_save(self) -> None:
        editor = self._tab_manager.current_editor()
        if not editor:
            return
        if editor.file_path:
            self._file_manager.save_file(editor.file_path, editor.text())
            editor.setModified(False)
            self._tab_manager.update_tab_title(self._tab_manager.currentIndex())
        else:
            self.action_save_as()

    def action_save_as(self) -> None:
        editor = self._tab_manager.current_editor()
        if not editor:
            return
        path = self._file_manager.save_file_as(editor.text(), parent=self)
        if path:
            editor.file_path = path
            editor.setModified(False)
            self._tab_manager.update_tab_title(self._tab_manager.currentIndex())

    def action_close_tab(self) -> None:
        index = self._tab_manager.currentIndex()
        if index >= 0:
            self._tab_manager.close_tab(index)

    def action_toggle_find(self) -> None:
        self._find_replace_bar.toggle_find()

    def action_toggle_find_replace(self) -> None:
        self._find_replace_bar.toggle_replace()

    def action_search_in_files(self) -> None:
        """Open and focus the Search panel (Ctrl+Shift+F)."""
        self._search_panel.focus_search()

    def action_goto_line(self) -> None:
        editor = self._tab_manager.current_editor()
        if not editor:
            return
        line_count = editor.lines()
        line_num, ok = QInputDialog.getInt(
            self, "Go to Line", f"Line number (1-{line_count}):",
            1, 1, line_count,
        )
        if ok:
            editor.setCursorPosition(line_num - 1, 0)
            editor.setFocus()

    def action_zoom(self, direction: int) -> None:
        """Zoom in (1), out (-1), or reset (0)."""
        editor = self._tab_manager.current_editor()
        if not editor:
            return
        if direction == 0:
            editor.zoomTo(0)
        elif direction > 0:
            editor.zoomIn()
        else:
            editor.zoomOut()

    def action_toggle_word_wrap(self) -> None:
        editor = self._tab_manager.current_editor()
        if not editor:
            return
        current = editor.wrapMode() != QsciScintilla.WrapMode.WrapNone
        new_mode = (
            QsciScintilla.WrapMode.WrapNone
            if current
            else QsciScintilla.WrapMode.WrapWord
        )
        editor.setWrapMode(new_mode)
        self._settings.set("editor.word_wrap", not current)
        if hasattr(self, "_word_wrap_action"):
            self._word_wrap_action.setChecked(not current)

    def action_toggle_output_panel(self) -> None:
        """Show the output panel and raise it (used by Run actions)."""
        self._output_panel.setVisible(True)
        self._output_panel.raise_()

    # --- Run actions (Phase 3) ---

    def _resolve_working_dir(self, file_path: str | None) -> str:
        """Resolve the working directory based on settings.

        If run.working_directory is "project" and a project folder is open,
        use that. Otherwise fall back to the file's parent directory.
        """
        mode = self._settings.get("run.working_directory")
        if mode == "project":
            project = self._settings.get("general.project_folder")
            if project and Path(project).is_dir():
                return str(project)
        # Default: file's parent directory
        if file_path:
            return str(Path(file_path).parent)
        return "."

    def action_run_file(self) -> None:
        """Run the current file (F5)."""
        editor = self._tab_manager.current_editor()
        if not editor:
            return

        # Confirm if already running
        if self._process_runner.is_running():
            reply = QMessageBox.question(
                self,
                "Process Running",
                "A process is already running. Stop it and run again?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._process_runner.stop()

        # Save before run if configured
        if self._settings.get("run.save_before_run"):
            if editor.isModified():
                self.action_save()

        # Need a file path to run
        file_path = editor.file_path
        if not file_path:
            self.action_save_as()
            file_path = editor.file_path
            if not file_path:
                return  # user cancelled save-as

        # Resolve interpreter and working directory
        interpreter = self._interpreter_manager.get_interpreter(
            self._settings, file_path
        )
        working_dir = self._resolve_working_dir(file_path)

        # Clear output if configured
        if self._settings.get("run.clear_output_before_run"):
            self._output_panel.clear_output()

        # Show output panel if configured
        if self._settings.get("run.show_output_panel"):
            self._output_panel.show()
            self._output_panel.raise_()

        self._process_runner.run_file(file_path, interpreter, working_dir)

    def action_run_selection(self) -> None:
        """Run the selected text or current line (Shift+F5)."""
        editor = self._tab_manager.current_editor()
        if not editor:
            return

        # Confirm if already running
        if self._process_runner.is_running():
            reply = QMessageBox.question(
                self,
                "Process Running",
                "A process is already running. Stop it and run again?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._process_runner.stop()

        # Get selected text, or current line if no selection
        code = editor.selectedText()
        if not code.strip():
            line, _ = editor.getCursorPosition()
            code = editor.text(line)

        if not code.strip():
            return

        interpreter = self._interpreter_manager.get_interpreter(
            self._settings, editor.file_path
        )
        working_dir = self._resolve_working_dir(editor.file_path)

        if self._settings.get("run.clear_output_before_run"):
            self._output_panel.clear_output()

        if self._settings.get("run.show_output_panel"):
            self._output_panel.show()
            self._output_panel.raise_()

        self._process_runner.run_code(code, interpreter, working_dir)

    def action_stop_process(self) -> None:
        """Stop the currently running process or debug session (Ctrl+F5)."""
        if self._debug_manager.is_running():
            self._debug_manager.stop_debug()
        else:
            self._process_runner.stop()

    def action_toggle_breakpoint(self) -> None:
        """Toggle a breakpoint on the current cursor line (F9)."""
        editor = self._tab_manager.current_editor()
        if editor:
            line, _ = editor.getCursorPosition()
            editor.toggle_breakpoint(line)

    # --- Debug actions (Phase 4) ---

    def action_start_debug(self) -> None:
        """Start a debug session (F6)."""
        if self._debug_manager.state != DebugState.IDLE:
            return

        editor = self._tab_manager.current_editor()
        if not editor:
            return

        # Save before debug
        if self._settings.get("run.save_before_run"):
            if editor.isModified():
                self.action_save()

        file_path = editor.file_path
        if not file_path:
            self.action_save_as()
            file_path = editor.file_path
            if not file_path:
                return

        interpreter = self._interpreter_manager.get_interpreter(
            self._settings, file_path
        )
        working_dir = self._resolve_working_dir(file_path)

        # Collect breakpoints from ALL open tabs
        breakpoints = self._collect_all_breakpoints()

        # Clear and show output panel
        if self._settings.get("run.clear_output_before_run"):
            self._output_panel.clear_output()
        if self._settings.get("run.show_output_panel"):
            self._output_panel.show()
            self._output_panel.raise_()

        self._debug_manager.start_debug(
            file_path, interpreter, working_dir, breakpoints
        )

    def action_debug_continue(self) -> None:
        """Continue execution (F5 during debug)."""
        if self._debug_manager.state == DebugState.PAUSED:
            self._debug_manager.send_continue()

    def action_debug_step_over(self) -> None:
        """Step over the current line (F10)."""
        if self._debug_manager.state == DebugState.PAUSED:
            self._debug_manager.send_step_over()

    def action_debug_step_into(self) -> None:
        """Step into the current line (F11)."""
        if self._debug_manager.state == DebugState.PAUSED:
            self._debug_manager.send_step_into()

    def action_debug_step_out(self) -> None:
        """Step out of the current function (Shift+F11)."""
        if self._debug_manager.state == DebugState.PAUSED:
            self._debug_manager.send_step_out()

    def action_stop_debug(self) -> None:
        """Stop the current debug session (Shift+F5)."""
        self._debug_manager.stop_debug()

    def action_clear_all_breakpoints(self) -> None:
        """Clear breakpoints from all open editors."""
        for i in range(self._tab_manager.count()):
            editor = self._tab_manager.widget(i)
            if isinstance(editor, CodeEditor):
                editor.clear_breakpoints()

    def _collect_all_breakpoints(self) -> dict[str, list[int]]:
        """Collect breakpoints from all tabs: {filepath: [1-based lines]}."""
        result = {}
        for i in range(self._tab_manager.count()):
            editor = self._tab_manager.widget(i)
            if isinstance(editor, CodeEditor) and editor.file_path:
                bp_lines = editor.get_breakpoints()
                if bp_lines:
                    # Convert 0-based to 1-based for the protocol
                    result[editor.file_path] = [line + 1 for line in bp_lines]
        return result

    def _set_run_as_continue(self, as_continue: bool) -> None:
        """Swap the Run button between Run and Continue modes."""
        if as_continue:
            if not getattr(self, "_run_is_continue", False):
                self._run_action.triggered.disconnect(self.action_run_file)
                self._run_action.triggered.connect(self.action_debug_continue)
                self._run_action.setToolTip("Continue (F5)")
                self._run_is_continue = True
        else:
            if getattr(self, "_run_is_continue", False):
                self._run_action.triggered.disconnect(self.action_debug_continue)
                self._run_action.triggered.connect(self.action_run_file)
                self._run_action.setToolTip("Run File (F5)")
                self._run_is_continue = False

    def _on_debug_state_changed(self, state: DebugState) -> None:
        """Update UI state based on debug lifecycle changes."""
        is_debugging = state not in (DebugState.IDLE,)
        is_paused = state == DebugState.PAUSED

        # Show/hide inline debug step actions
        self._debug_separator.setVisible(is_debugging)
        self._step_over_action.setVisible(is_debugging)
        self._step_into_action.setVisible(is_debugging)
        self._step_out_action.setVisible(is_debugging)
        self._step_over_action.setEnabled(is_paused)
        self._step_into_action.setEnabled(is_paused)
        self._step_out_action.setEnabled(is_paused)

        # Repurpose Run button as Continue when debug is paused,
        # disable it when running (not paused), restore when idle.
        if is_paused:
            self._set_run_as_continue(True)
            self._run_action.setEnabled(True)
        elif is_debugging:
            self._run_action.setEnabled(False)
        else:
            self._set_run_as_continue(False)
            self._run_action.setEnabled(True)

        self._debug_action.setEnabled(not is_debugging)

        # Enable/disable debug menu actions
        # (these are created by MenuBarBuilder and stored on self)
        if hasattr(self, "_debug_continue_action"):
            self._debug_continue_action.setEnabled(is_paused)
            self._debug_step_over_action.setEnabled(is_paused)
            self._debug_step_into_action.setEnabled(is_paused)
            self._debug_step_out_action.setEnabled(is_paused)
            self._debug_stop_action.setEnabled(is_debugging)

        # Show debug panels when paused
        if is_paused:
            self._variable_inspector.show()
            self._variable_inspector.raise_()

        # Update status bar
        self._status_bar_manager.update_debug_state(state)

    def _on_debug_started(self, desc: str) -> None:
        """Handle debug session starting."""
        self._output_panel.set_running(True)
        self._stop_action.setEnabled(True)
        self._output_panel.append_output(f">>> {desc}\n", "system")
        self._status_bar_manager.show_message(desc)

    def _on_debug_paused(
        self, file_path: str, line: int, variables: dict, call_stack: list
    ) -> None:
        """Handle debugger pausing at a line."""
        # Open file and show current-line marker
        path = Path(file_path)
        if path.exists():
            # Check if file is already open
            editor = None
            for i in range(self._tab_manager.count()):
                e = self._tab_manager.widget(i)
                if isinstance(e, CodeEditor) and e.file_path == str(path):
                    editor = e
                    self._tab_manager.setCurrentWidget(editor)
                    break

            if editor is None:
                # Open the file in a new tab
                content = self._file_manager.read_file(str(path))
                editor = self._tab_manager.open_file_in_tab(str(path), content)

            if editor:
                self._clear_debug_markers()
                editor.set_current_line(line)
                editor.setFocus()

        # Update debug panels
        self._variable_inspector.update_variables(variables)
        self._call_stack_panel.update_call_stack(call_stack)

        # Show debug panels
        self._variable_inspector.show()
        self._call_stack_panel.show()
        self._watch_panel.show()
        self._variable_inspector.raise_()

        # Re-evaluate watch expressions
        self._watch_panel.request_all_evaluations()

    def _on_debug_resumed(self) -> None:
        """Handle debugger resuming execution."""
        self._clear_debug_markers()

    def _on_debug_eval_result(
        self, expression: str, result: str, error: str
    ) -> None:
        """Handle evaluation result from the debug helper."""
        self._watch_panel.update_value(expression, result, error)

    def _on_debug_finished(self, exit_code: int, desc: str) -> None:
        """Handle debug session ending."""
        self._output_panel.set_running(False)
        self._set_run_as_continue(False)
        self._run_action.setEnabled(True)
        self._debug_action.setEnabled(True)
        self._stop_action.setEnabled(False)
        self._output_panel.append_output(f">>> {desc}\n", "system")
        self._status_bar_manager.show_message(desc)

        # Clear all debug UI
        self._clear_debug_markers()
        self._variable_inspector.clear_variables()
        self._call_stack_panel.clear_stack()
        self._watch_panel.clear_values()

        # Hide debug step actions
        self._debug_separator.setVisible(False)
        self._step_over_action.setVisible(False)
        self._step_into_action.setVisible(False)
        self._step_out_action.setVisible(False)
        self._variable_inspector.hide()
        self._call_stack_panel.hide()
        self._watch_panel.hide()

    def _clear_debug_markers(self) -> None:
        """Clear the current-line marker from all editors."""
        for i in range(self._tab_manager.count()):
            editor = self._tab_manager.widget(i)
            if isinstance(editor, CodeEditor):
                editor.clear_current_line()

    def action_select_interpreter(self) -> None:
        """Show a dialog to select the Python interpreter."""
        editor = self._tab_manager.current_editor()
        file_path = editor.file_path if editor else None
        interpreters = self._interpreter_manager.detect_interpreters(file_path)

        items = [f"{info.label}  ({info.path})" for info in interpreters]
        item, ok = QInputDialog.getItem(
            self,
            "Select Python Interpreter",
            "Choose an interpreter:",
            items,
            0,
            False,
        )
        if ok and item:
            idx = items.index(item)
            chosen = interpreters[idx]
            self._settings.set("run.python_interpreter", chosen.path)
            self._update_interpreter_label()

    def action_create_venv(self) -> None:
        """Open the virtual environment creation dialog."""
        from meadowpy.ui.dialogs.venv_dialog import VenvDialog

        editor = self._tab_manager.current_editor()
        file_path = editor.file_path if editor else None
        dialog = VenvDialog(self._interpreter_manager, file_path, self)
        dialog.exec()

    def _on_process_output(self, text: str, stream: str) -> None:
        self._output_panel.append_output(text, stream)
        if stream == "stderr":
            from meadowpy.core.error_explainer import explain_error
            explanation = explain_error(text)
            if explanation:
                self._output_panel.append_output(explanation, "hint")

    def _on_process_started(self, desc: str) -> None:
        self._output_panel.set_running(True)
        self._run_action.setEnabled(False)
        self._debug_action.setEnabled(False)
        self._stop_action.setEnabled(True)
        self._output_panel.append_output(f">>> {desc}\n", "system")
        self._status_bar_manager.show_message(desc)

    def _on_process_finished(self, exit_code: int, desc: str) -> None:
        self._output_panel.set_running(False)
        self._run_action.setEnabled(True)
        self._debug_action.setEnabled(True)
        self._stop_action.setEnabled(False)
        self._output_panel.append_output(f">>> {desc}\n", "system")
        self._status_bar_manager.show_message(desc)

    def _on_stdin_submitted(self, text: str) -> None:
        if self._debug_manager.is_running():
            self._debug_manager.send_stdin(text)
        else:
            self._process_runner.send_stdin(text)

    # ── REPL handlers ──────────────────────────────────────────────

    def _start_repl(self) -> None:
        """Start the interactive Python console."""
        editor = self._tab_manager.current_editor()
        file_path = editor.file_path if editor else None
        interpreter = self._interpreter_manager.get_interpreter(
            self._settings, file_path
        )
        working_dir = self._resolve_repl_working_dir()
        self._repl_manager.start(interpreter, working_dir)

    def _resolve_repl_working_dir(self) -> str:
        """Determine working directory for the REPL."""
        project = self._settings.get("general.project_folder")
        if project and Path(project).is_dir():
            return str(project)
        editor = self._tab_manager.current_editor()
        if editor and editor.file_path:
            return str(Path(editor.file_path).parent)
        return str(Path.home())

    def _on_repl_input(self, text: str) -> None:
        """Send user input to the REPL subprocess."""
        self._repl_manager.add_to_history(text)
        self._repl_manager.send_input(text)

    def _on_repl_output(self, text: str, stream: str) -> None:
        """Display REPL output in the output panel."""
        self._output_panel.append_output(text, stream)
        if stream == "stderr":
            from meadowpy.core.error_explainer import explain_error
            explanation = explain_error(text)
            if explanation:
                self._output_panel.append_output(explanation, "hint")

    def _on_repl_started(self) -> None:
        self._output_panel.append_output(
            "Python console ready.\n", "system"
        )

    def _on_repl_stopped(self) -> None:
        self._output_panel.append_output(
            "Python console stopped.\n", "system"
        )

    def _on_repl_restart(self) -> None:
        """Restart the REPL with a fresh state."""
        # Stop any running script or debug session first
        if self._debug_manager.is_running():
            self._debug_manager.stop_debug()
        elif self._process_runner.is_running():
            self._process_runner.stop()
        self._output_panel.clear_output()
        if self._repl_manager.is_running:
            self._repl_manager.stop()
        self._start_repl()

    def _on_repl_history_up(self) -> None:
        text = self._repl_manager.history_up()
        if text is not None:
            self._output_panel.set_input_text(text)

    def _on_repl_history_down(self) -> None:
        text = self._repl_manager.history_down()
        if text is not None:
            self._output_panel.set_input_text(text)

    def _on_traceback_navigate(self, file_path: str, line: int) -> None:
        """Open the file from a traceback and jump to the given line."""
        path = Path(file_path)
        if not path.exists():
            return
        content = self._file_manager.read_file(str(path))
        editor = self._tab_manager.open_file_in_tab(str(path), content)
        if editor:
            editor.setCursorPosition(line - 1, 0)
            editor.setFocus()

    def _on_search_navigate(self, file_path: str, line: int) -> None:
        """Open a file from the search panel and jump to the given line."""
        path = Path(file_path)
        if not path.exists():
            return
        content = self._file_manager.read_file(str(path))
        editor = self._tab_manager.open_file_in_tab(str(path), content)
        if editor:
            editor.setCursorPosition(line - 1, 0)
            editor.setFocus()

    def _update_interpreter_label(self) -> None:
        """Update the status bar interpreter label."""
        editor = self._tab_manager.current_editor()
        file_path = editor.file_path if editor else None
        interpreter = self._interpreter_manager.get_interpreter(
            self._settings, file_path
        )
        version = self._interpreter_manager._get_version(interpreter)
        self._status_bar_manager.update_interpreter(f"Python {version}")

    def action_preferences(self) -> None:
        from meadowpy.ui.dialogs.preferences_dialog import PreferencesDialog

        dialog = PreferencesDialog(self._settings, self)
        dialog.exec()

    def action_example_library(self) -> None:
        from meadowpy.ui.dialogs.example_library_dialog import ExampleLibraryDialog

        dialog = ExampleLibraryDialog(self)
        dialog.example_selected.connect(self._on_template_selected)
        dialog.exec()

    def action_shortcut_reference(self) -> None:
        from meadowpy.ui.dialogs.shortcut_reference_dialog import ShortcutReferenceDialog

        dialog = ShortcutReferenceDialog(self)
        dialog.exec()

    def action_about(self) -> None:
        from meadowpy.ui.dialogs.about_dialog import AboutDialog

        dialog = AboutDialog(self)
        dialog.exec()

    def open_file_in_tab(self, file_path: str, content: str) -> None:
        """Public method for opening a file in a tab (used by app.py)."""
        self._tab_manager.open_file_in_tab(file_path, content)

    def open_recent_file(self, file_path: str) -> None:
        """Open a file from the recent files list."""
        path = Path(file_path)
        if not path.exists():
            QMessageBox.warning(
                self, "File Not Found",
                f"The file no longer exists:\n{file_path}",
            )
            self._recent_files.remove(file_path)
            return
        content = self._file_manager.read_file(file_path)
        self._tab_manager.open_file_in_tab(file_path, content)
        self._recent_files.add(file_path)

    # --- Event handlers ---

    def _on_tab_changed(self, editor) -> None:
        """Update status bar, outline, and lint when active tab changes."""
        if isinstance(editor, CodeEditor):
            # Auto-close the Welcome tab once a real editor is active
            self._tab_manager.close_welcome_tab()

            # Update title
            title = f"{editor.display_name} - {APP_NAME}"
            self.setWindowTitle(title)

            # Connect cursor position updates
            try:
                editor.cursorPositionChanged.disconnect(self._on_cursor_moved)
            except TypeError:
                pass
            editor.cursorPositionChanged.connect(self._on_cursor_moved)

            # Update cursor position now
            line, col = editor.getCursorPosition()
            self._status_bar_manager.update_cursor_position(line, col)

            # Connect text changes for outline + lint debounce
            try:
                editor.textChanged.disconnect(self._on_editor_text_changed)
            except TypeError:
                pass
            editor.textChanged.connect(self._on_editor_text_changed)

            # Connect AI context menu actions
            try:
                editor.ai_explain_requested.disconnect(self._on_ai_explain_requested)
            except TypeError:
                pass
            editor.ai_explain_requested.connect(self._on_ai_explain_requested)

            try:
                editor.ai_improve_requested.disconnect(self._on_ai_improve_requested)
            except TypeError:
                pass
            editor.ai_improve_requested.connect(self._on_ai_improve_requested)

            try:
                editor.ai_docstring_requested.disconnect(self._on_ai_docstring_requested)
            except TypeError:
                pass
            editor.ai_docstring_requested.connect(self._on_ai_docstring_requested)

            # Update AI chat panel context with current file info
            self._update_ai_context(editor)

            # Refresh outline, lint, and interpreter label
            self._refresh_symbol_outline(editor)
            self._do_lint()
            self._update_interpreter_label()
        else:
            self.setWindowTitle(APP_NAME)
            self._symbol_outline.clear_symbols()
            self._problems_panel.clear_issues()

    def _on_cursor_moved(self, line: int, col: int) -> None:
        self._status_bar_manager.update_cursor_position(line, col)
        # Update AI context with current cursor position
        editor = self._tab_manager.current_editor()
        if isinstance(editor, CodeEditor):
            self._update_ai_context(editor, line=line)

    def _on_editor_text_changed(self) -> None:
        """Debounce both outline refresh and lint on text changes."""
        self._outline_timer.start()
        if self._settings.get("editor.linting_enabled"):
            self._lint_timer.start()

    def _on_file_saved(self, path: str) -> None:
        """Handle file saved: show message + trigger lint."""
        self._status_bar_manager.show_message(f"Saved: {Path(path).name}")
        if self._settings.get("editor.lint_on_save"):
            self._do_lint()

    def _on_settings_changed(self, key: str, value) -> None:
        """Re-apply settings to all open editors when a setting changes."""
        # Swap app-wide stylesheet when theme OR any custom-theme setting changes
        theme_keys = (
            "editor.theme",
            "editor.custom_theme.base",
            "editor.custom_theme.accent",
        )
        if key in theme_keys:
            app = QApplication.instance()
            if app:
                app.setStyleSheet(get_stylesheet(
                    self._settings.get("editor.theme"),
                    custom_base=self._settings.get("editor.custom_theme.base"),
                    custom_accent=self._settings.get("editor.custom_theme.accent"),
                ))
            self._tab_manager.update_theme()
            self._apply_explorer_icon_theme()
            if hasattr(self, "_ai_chat_panel"):
                theme_name = self._settings.get("editor.theme")
                base = self._settings.get("editor.custom_theme.base")
                self._ai_chat_panel.apply_accent(
                    current_accent_hex(
                        theme_name, base,
                        self._settings.get("editor.custom_theme.accent"),
                    ),
                    theme_is_dark(theme_name, base),
                )
            # Re-tint the "Run" button glow in the toolbar & output panel to
            # match the current theme's accent (only Custom theme changes it).
            accent = run_button_accent_hex(
                self._settings.get("editor.theme"),
                self._settings.get("editor.custom_theme.accent"),
            )
            if hasattr(self, "_toolbar_builder"):
                self._toolbar_builder.update_accent_color(accent)
            if hasattr(self, "_output_panel"):
                self._output_panel.update_accent_color(accent)

            # Rebuild icons whose color depends on the theme (Run/Stop/Debug
            # are white in HC, original brand colors in dark/light/custom).
            # Without this, icons created at startup persist across theme
            # switches and you get white icons leaking into non-HC themes.
            self._refresh_themed_icons()

            # Re-render the Problems panel so its severity glyphs (✕ red /
            # ⚠ amber vs both white in HC) follow the new theme.
            if hasattr(self, "_problems_panel"):
                self._problems_panel.update_issues(
                    list(self._problems_panel._issues)
                )

            # Output panel bakes color into character formats at insert time,
            # so already-printed traceback text stays in the old theme's
            # colors until we replay the history.
            if hasattr(self, "_output_panel"):
                self._output_panel.recolor_for_theme()

            # Status bar lint counts use inline-HTML colors that don't update
            # on stylesheet change — re-render with the new theme's colors.
            if hasattr(self, "_status_bar_manager"):
                self._status_bar_manager.refresh_lint_colors()

        for i in range(self._tab_manager.count()):
            editor = self._tab_manager.widget(i)
            if isinstance(editor, CodeEditor):
                EditorConfigurator.apply(editor, self._settings)
                # Squiggle indicator colors are baked at set_lint_issues time
                # and don't follow stylesheet changes — re-apply with the
                # current theme's palette so HC switches refresh underlines.
                if key in theme_keys:
                    editor.refresh_lint_colors()
                    editor.refresh_marker_colors()

        self._status_bar_manager.update_indent_info()

        # Toggle outline/problems visibility based on settings
        if key == "editor.show_symbol_outline":
            self._symbol_outline.setVisible(value)
        if key == "editor.linting_enabled":
            if not value:
                self._problems_panel.hide()
                self._status_bar_manager.update_lint_counts(0, 0)
        if key == "explorer.show_file_explorer":
            self._file_explorer.setVisible(value)

    # --- Symbol outline ---

    def _on_outline_navigate(self, line: int) -> None:
        """Navigate editor to line when outline item is clicked."""
        editor = self._tab_manager.current_editor()
        if editor:
            editor.setCursorPosition(line, 0)
            editor.setFocus()

    def _do_refresh_outline(self) -> None:
        """Refresh the symbol outline (called after debounce)."""
        editor = self._tab_manager.current_editor()
        if editor:
            self._refresh_symbol_outline(editor)

    def _on_outline_visibility_changed(self, visible: bool) -> None:
        """Refresh the outline when the panel becomes visible."""
        if visible:
            editor = self._tab_manager.current_editor()
            if editor:
                self._symbol_outline.update_symbols(editor.text())

    def _refresh_symbol_outline(self, editor: CodeEditor) -> None:
        """Update the symbol outline from the editor's current text."""
        if self._symbol_outline.isVisible():
            self._symbol_outline.update_symbols(editor.text())

    # --- Linting ---

    def _on_problem_navigate(self, line: int, col: int) -> None:
        """Navigate editor to location when problem row is clicked."""
        editor = self._tab_manager.current_editor()
        if editor:
            editor.setCursorPosition(line, col)
            editor.setFocus()

    def _do_lint(self) -> None:
        """Actually run the linter (called after debounce or on save)."""
        editor = self._tab_manager.current_editor()
        if editor and self._settings.get("editor.linting_enabled"):
            self._lint_target_editor = editor
            self._lint_runner.run_lint(
                editor.text(),
                editor.file_path,
                self._settings.get("editor.linter"),
            )

    def _on_lint_finished(self, issues: list) -> None:
        """Receive lint results and update UI."""
        editor = getattr(self, "_lint_target_editor", None)
        if editor is None:
            editor = self._tab_manager.current_editor()
        if editor:
            editor.set_lint_issues(issues)
        self._problems_panel.update_issues(issues)

        # Update status bar with counts
        error_count = sum(1 for i in issues if i.severity == "error")
        warning_count = sum(1 for i in issues if i.severity == "warning")
        self._status_bar_manager.update_lint_counts(error_count, warning_count)

    def _on_lint_error(self, message: str) -> None:
        """Show a linter error (e.g. not installed) in the Problems panel."""
        self._problems_panel.show_linter_error(message)
        self._status_bar_manager.update_lint_counts(0, 0)

    # --- Ollama AI ---

    def _on_ollama_connection_changed(self, connected: bool, message: str) -> None:
        """Update the status bar when Ollama connection state changes."""
        model = self._settings.get("ollama.selected_model") if connected else ""
        self._status_bar_manager.update_ollama_status(connected, model)
        self._model_selector.set_connected(connected)

    def _on_ollama_models_updated(self, models: list) -> None:
        """Update the model selector when the model list is refreshed."""
        self._model_selector.set_models(models)
        # Update status bar in case the selected model was invalidated
        connected = self._ollama_client.is_connected
        model = self._settings.get("ollama.selected_model")
        self._status_bar_manager.update_ollama_status(connected, model)

    def _on_model_chosen(self, model_name: str) -> None:
        """Handle model selection from the popup menu."""
        if model_name in ("__retry__", "__refresh__"):
            self._ollama_client.check_connection()
        else:
            self._ollama_client.select_model(model_name)
            self._status_bar_manager.update_ollama_status(True, model_name)
            self._model_selector.set_current_model(model_name)

    def _on_ollama_status_clicked(self) -> None:
        """Show the model selector popup when the status bar label is clicked."""
        label = self._status_bar_manager.ollama_label
        # Position the menu just above the label
        pos = label.mapToGlobal(label.rect().topLeft())
        self._model_selector.set_current_model(
            self._settings.get("ollama.selected_model") or ""
        )
        self._model_selector.show_at(pos)

    def _on_chat_requested(self, messages: list) -> None:
        """Forward a chat request from the panel to the Ollama client."""
        self._ollama_client.send_chat(messages)

    def _on_ai_explain_requested(self, code: str) -> None:
        """Handle 'Explain this code' from the editor context menu."""
        # Build a user-friendly prompt with the selected code
        prompt = (
            "Please explain the following Python code in simple terms:\n\n"
            f"```python\n{code}\n```"
        )
        # Send it through the chat panel as if the user typed it
        self._ai_chat_panel.send_message_programmatic(prompt)

    def _on_ai_improve_requested(self, code: str) -> None:
        """Handle 'Review & improve' from the editor context menu."""
        prompt = (
            "Please review the following Python code and suggest improvements. "
            "Consider readability, best practices, potential bugs, performance, "
            "and structure. If the code could benefit from refactoring "
            "(reducing duplication, extracting functions, etc.), show the "
            "improved version. Keep your suggestions beginner-friendly:\n\n"
            f"```python\n{code}\n```"
        )
        self._ai_chat_panel.send_message_programmatic(prompt)

    def action_ai_review_file(self) -> None:
        """Send the entire current file to the AI for a code review."""
        editor = self._tab_manager.current_editor()
        if not editor:
            return
        code = editor.text()
        if not code.strip():
            return

        filename = editor.display_name
        prompt = (
            f"Please review the entire Python file \"{filename}\" below. "
            "Give feedback on:\n"
            "- Code structure and organization\n"
            "- Readability and naming\n"
            "- Potential bugs or issues\n"
            "- Best practices and improvements\n"
            "- Performance considerations\n\n"
            "Keep your review beginner-friendly and constructive:\n\n"
            f"```python\n{code}\n```"
        )
        self._ai_chat_panel.send_message_programmatic(prompt)

    def _on_ai_docstring_requested(self, code: str, insert_line: int) -> None:
        """Handle 'Generate docstring' from the editor context menu."""
        prompt = (
            "Generate a Python docstring for the function or class below.\n\n"
            "IMPORTANT rules for your response:\n"
            "1. Wrap your docstring in a fenced code block using "
            "triple backticks (```python ... ```).\n"
            "2. The code block must contain ONLY the docstring "
            'itself (the \"\"\"...\"\"\" triple-quoted string).\n'
            "3. Do NOT include the def/class line or any other code.\n"
            "4. The opening \"\"\" must be on the SAME line as the "
            "first sentence, with NO extra indentation before it — "
            "just the body-level indent.\n"
            "5. Keep every line under 79 characters (including indent) "
            "to avoid linter warnings.\n"
            "6. Do NOT put blank lines between sections of the "
            "docstring (no blank line between summary, Args, Returns, "
            "etc.) — blank lines inside docstrings cause linter "
            "warnings.\n"
            "7. Keep it beginner-friendly.\n\n"
            f"```python\n{code}\n```"
        )
        # Position cursor at the insertion point so "Insert at Cursor
        # Position" places the docstring in the right place.
        editor = self._tab_manager.current_editor()
        if editor and insert_line >= 0:
            # Figure out the body indentation (def indent + one level)
            line_text = editor.text(insert_line) if insert_line < editor.lines() else ""
            body_indent = len(line_text) - len(line_text.lstrip())
            if body_indent == 0:
                # Fallback: use def indent + 4 spaces
                def_text = editor.text(max(insert_line - 1, 0))
                def_indent = len(def_text) - len(def_text.lstrip())
                body_indent = def_indent + 4
            editor.setCursorPosition(insert_line, 0)

        self._ai_chat_panel.send_message_programmatic(prompt)

    def _on_output_ai_fix_requested(self, error_text: str) -> None:
        """Handle 'Fix with AI' from the output panel (runtime errors)."""
        # Include the current editor's code for context
        code_context = ""
        editor = self._tab_manager.current_editor()
        if editor:
            code_context = editor.text()

        if code_context:
            prompt = (
                "I got the following error when running my Python code. "
                "Please explain what went wrong and how to fix it.\n\n"
                "**My code:**\n"
                f"```python\n{code_context}\n```\n\n"
                "**Error:**\n"
                f"```\n{error_text}\n```"
            )
        else:
            prompt = (
                "I got the following Python error. "
                "Please explain what went wrong and how to fix it.\n\n"
                f"```\n{error_text}\n```"
            )
        self._ai_chat_panel.send_message_programmatic(prompt)

    def _on_lint_ai_fix_requested(
        self, code: str, line: int, message: str
    ) -> None:
        """Handle 'AI Analysis' from the problems panel (lint issues)."""
        # Get the relevant line plus surrounding context from the editor
        editor = self._tab_manager.current_editor()
        snippet_lines: list[str] = []
        if editor and line >= 1:
            total_lines = editor.lines()
            error_line_idx = line - 1  # convert to 0-based

            # Find first non-blank line above the error line
            above_idx = error_line_idx - 1
            while above_idx >= 0:
                text = editor.text(above_idx).rstrip("\n\r")
                if text.strip():
                    snippet_lines.append(f"{above_idx + 1}: {text}")
                    break
                above_idx -= 1

            # The error line itself
            error_text = editor.text(error_line_idx).rstrip("\n\r")
            snippet_lines.append(
                f"{line}: {error_text}  # <-- issue here"
            )

            # Find first non-blank line below the error line
            below_idx = error_line_idx + 1
            while below_idx < total_lines:
                text = editor.text(below_idx).rstrip("\n\r")
                if text.strip():
                    snippet_lines.append(f"{below_idx + 1}: {text}")
                    break
                below_idx += 1

        prompt = (
            f"My linter reported the following issue on line {line}:\n\n"
            f"**{code}**: {message}\n\n"
        )
        if snippet_lines:
            snippet = "\n".join(snippet_lines)
            prompt += (
                f"Here is the relevant code with surrounding context:\n"
                f"```python\n{snippet}\n```\n\n"
            )
        prompt += "Please explain what this means and how to fix it."
        self._ai_chat_panel.send_message_programmatic(prompt)

    def _on_code_insert_requested(self, code: str) -> None:
        """Insert AI-generated code at the current cursor position."""
        editor = self._tab_manager.current_editor()
        if not editor:
            return

        # If the cursor sits right after a def/class line (docstring
        # insertion), extract only the """...""" block from whatever the
        # AI returned, and re-indent it to match the function body.
        import re as _re
        line, _ = editor.getCursorPosition()
        if line > 0:
            prev_line = editor.text(line - 1)
            if prev_line.strip().startswith(("def ", "class ")):
                m = _re.search(r'([ \t]*""".*?""")', code, _re.DOTALL)
                if m:
                    docstring = m.group(1)
                    # Determine the correct body indentation
                    def_indent = len(prev_line) - len(prev_line.lstrip())
                    body_indent = " " * (def_indent + 4)
                    # Strip existing indentation and re-indent
                    lines = docstring.split("\n")
                    stripped = [l.lstrip() for l in lines]
                    code = "\n".join(
                        body_indent + s if s else "" for s in stripped
                    ).rstrip() + "\n"
                    # Force cursor to column 0 so our indent is exact
                    editor.setCursorPosition(line, 0)
                    # Insert and clean up
                    editor.insert(code)
                    # Remove blank line after insertion if one was created
                    inserted_lines = code.count("\n")
                    next_line = line + inserted_lines
                    if next_line < editor.lines():
                        if editor.text(next_line).strip() == "":
                            editor.setCursorPosition(next_line, 0)
                            editor.setSelection(
                                next_line, 0,
                                next_line + 1, 0,
                            )
                            editor.removeSelectedText()
                    editor.setFocus()
                    return

        # Ensure code ends with a newline for clean insertion
        if not code.endswith("\n"):
            code += "\n"
        line, col = editor.getCursorPosition()
        editor.insert(code)
        # Move cursor to end of inserted code
        inserted_lines = code.count("\n")
        last_line_text = code.rsplit("\n", 1)[-1] if "\n" in code else code
        new_line = line + inserted_lines
        new_col = len(last_line_text) if inserted_lines > 0 else col + len(code)
        editor.setCursorPosition(new_line, new_col)
        editor.setFocus()

    # --- Context-aware AI help ---

    def _update_ai_context(
        self, editor: CodeEditor, *, line: int | None = None
    ) -> None:
        """Push current editor context to the AI chat panel."""
        filename = editor.display_name or ""
        if line is None:
            line, _ = editor.getCursorPosition()

        # Try to find the enclosing function/class name
        func_name = ""
        if line >= 0:
            import re as _re
            for scan in range(line, -1, -1):
                text = editor.text(scan).rstrip()
                m = _re.match(r'^(\s*)(def|class)\s+(\w+)', text)
                if m:
                    func_name = f"{m.group(2)} {m.group(3)}"
                    break

        self._ai_chat_panel.update_editor_context(
            filename=filename,
            function_name=func_name,
            cursor_line=line,
            file_text=editor.text(),
        )

    # --- Window events ---

    def closeEvent(self, event) -> None:
        """Handle window close: kill process, save unsaved files, persist state."""
        # Kill any running process or debug session first
        if self._debug_manager.state != DebugState.IDLE:
            self._debug_manager.stop_debug()
        if self._process_runner.is_running():
            self._process_runner.stop()
        if self._repl_manager.is_running:
            self._repl_manager.stop()

        if self._tab_manager.prompt_save_all():
            self._save_state()
            self._settings.save()
            # Cancel any in-flight AI request (closes the HTTP socket)
            if self._ollama_client._chat_worker:
                self._ollama_client._chat_worker.cancel()
            self._ollama_client._auto_check_timer.stop()
            # Force-exit to avoid "QThread: Destroyed while thread is
            # still running" when a background thread (e.g. Ollama chat)
            # is stuck in a blocking C-level I/O call that cannot be
            # interrupted by QThread.quit/terminate on Windows.
            import os
            os._exit(0)
        else:
            event.ignore()

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

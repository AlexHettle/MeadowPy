"""Menu bar construction and actions."""

from pathlib import Path

from PyQt6.QtGui import QIcon, QKeySequence
from PyQt6.QtWidgets import QMenuBar, QMenu

from meadowpy.resources.resource_loader import get_icon_path, load_themed_icon


class MenuBarBuilder:
    """Constructs the main menu bar and all its actions."""

    def __init__(self, main_window):
        self._window = main_window
        self._recent_files_menu: QMenu | None = None

    def build(self) -> None:
        """Build the complete menu bar."""
        menu_bar = self._window.menuBar()
        self._build_file_menu(menu_bar)
        self._build_edit_menu(menu_bar)
        self._build_view_menu(menu_bar)
        self._build_run_menu(menu_bar)
        self._build_ai_menu(menu_bar)
        self._build_help_menu(menu_bar)

    def rebuild_recent_files_menu(self) -> None:
        """Rebuild the Recent Files submenu from the current list."""
        if self._recent_files_menu is None:
            return

        self._recent_files_menu.clear()
        files = self._window._recent_files.get_files()

        if not files:
            no_recent = self._recent_files_menu.addAction("(No Recent Files)")
            no_recent.setEnabled(False)
            return

        for filepath in files:
            display = filepath
            # Show just filename + parent for readability
            p = Path(filepath)
            if p.parent.name:
                display = f"{p.parent.name}/{p.name}"
            else:
                display = p.name

            action = self._recent_files_menu.addAction(display)
            action.setToolTip(filepath)
            action.triggered.connect(
                lambda checked, path=filepath: self._window.open_recent_file(path)
            )

        self._recent_files_menu.addSeparator()
        clear_action = self._recent_files_menu.addAction("Clear Recent Files")
        clear_action.triggered.connect(self._window._recent_files.clear)

    def _build_file_menu(self, menu_bar: QMenuBar) -> None:
        file_menu = menu_bar.addMenu("&File")

        new_action = file_menu.addAction("&New File")
        new_action.setShortcut(QKeySequence("Ctrl+N"))
        new_action.triggered.connect(self._window.action_new_file)

        open_action = file_menu.addAction("&Open File...")
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self._window.action_open_file)

        open_folder_action = file_menu.addAction("Open F&older...")
        open_folder_action.setShortcut(QKeySequence("Ctrl+Shift+K"))
        open_folder_action.triggered.connect(self._window.action_open_folder)

        file_menu.addSeparator()

        self._recent_files_menu = file_menu.addMenu("Recent Files")
        self.rebuild_recent_files_menu()

        file_menu.addSeparator()

        save_action = file_menu.addAction("&Save")
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self._window.action_save)

        save_as_action = file_menu.addAction("Save &As...")
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(self._window.action_save_as)

        file_menu.addSeparator()

        close_tab_action = file_menu.addAction("&Close Tab")
        close_tab_action.setShortcut(QKeySequence("Ctrl+W"))
        close_tab_action.triggered.connect(self._window.action_close_tab)

        file_menu.addSeparator()

        prefs_action = file_menu.addAction("&Preferences...")
        prefs_action.setShortcut(QKeySequence("Ctrl+,"))
        prefs_action.triggered.connect(self._window.action_preferences)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("E&xit")
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self._window.close)

    def _build_edit_menu(self, menu_bar: QMenuBar) -> None:
        edit_menu = menu_bar.addMenu("&Edit")

        # Do NOT bind Ctrl+C/V/X/Z/Y/A via setShortcut() here.
        # Every Qt text widget (QScintilla, QTextBrowser, QPlainTextEdit,
        # QLineEdit) handles these natively in its own keyPressEvent.
        # Binding them to window-level QActions hijacks the key before
        # the focused widget can process it, breaking copy/paste in
        # non-editor panels.  Menu-click still routes via the handler.

        undo = edit_menu.addAction("&Undo")
        undo.triggered.connect(lambda: self._focused_widget_call("undo"))

        redo = edit_menu.addAction("&Redo")
        redo.triggered.connect(lambda: self._focused_widget_call("redo"))

        edit_menu.addSeparator()

        cut = edit_menu.addAction("Cu&t")
        cut.triggered.connect(lambda: self._focused_widget_call("cut"))

        copy = edit_menu.addAction("&Copy")
        copy.triggered.connect(lambda: self._focused_widget_call("copy"))

        paste = edit_menu.addAction("&Paste")
        paste.triggered.connect(lambda: self._focused_widget_call("paste"))

        edit_menu.addSeparator()

        select_all = edit_menu.addAction("Select &All")
        select_all.triggered.connect(lambda: self._focused_widget_call("selectAll"))

        edit_menu.addSeparator()

        find = edit_menu.addAction("&Find...")
        find.setShortcut(QKeySequence("Ctrl+F"))
        find.triggered.connect(self._window.action_toggle_find)

        replace = edit_menu.addAction("&Replace...")
        replace.setShortcut(QKeySequence("Ctrl+H"))
        replace.triggered.connect(self._window.action_toggle_find_replace)

        search_files = edit_menu.addAction("Search in &Files...")
        search_files.setShortcut(QKeySequence("Ctrl+Shift+F"))
        search_files.triggered.connect(self._window.action_search_in_files)

        edit_menu.addSeparator()

        goto_line = edit_menu.addAction("&Go to Line...")
        goto_line.setShortcut(QKeySequence("Ctrl+G"))
        goto_line.triggered.connect(self._window.action_goto_line)

    def _build_view_menu(self, menu_bar: QMenuBar) -> None:
        view_menu = menu_bar.addMenu("&View")

        zoom_in = view_menu.addAction("Zoom &In")
        zoom_in.setShortcut(QKeySequence("Ctrl+="))
        zoom_in.triggered.connect(lambda: self._window.action_zoom(1))

        zoom_out = view_menu.addAction("Zoom &Out")
        zoom_out.setShortcut(QKeySequence("Ctrl+-"))
        zoom_out.triggered.connect(lambda: self._window.action_zoom(-1))

        zoom_reset = view_menu.addAction("&Reset Zoom")
        zoom_reset.setShortcut(QKeySequence("Ctrl+0"))
        zoom_reset.triggered.connect(lambda: self._window.action_zoom(0))

        view_menu.addSeparator()

        word_wrap = view_menu.addAction("&Word Wrap")
        word_wrap.setCheckable(True)
        word_wrap.setChecked(self._window._settings.get("editor.word_wrap", False))
        word_wrap.triggered.connect(self._window.action_toggle_word_wrap)
        self._window._word_wrap_action = word_wrap

        view_menu.addSeparator()

        # Use toggleViewAction() — Qt keeps checked state in sync automatically,
        # even when panels are closed via their title-bar X button.
        explorer = self._window._file_explorer.toggleViewAction()
        explorer.setText("File &Explorer")
        explorer.setShortcut(QKeySequence("Ctrl+Shift+E"))
        view_menu.addAction(explorer)

        outline = self._window._symbol_outline.toggleViewAction()
        outline.setText("Symbol &Outline")
        outline.setShortcut(QKeySequence("Ctrl+Shift+O"))
        view_menu.addAction(outline)

        problems = self._window._problems_panel.toggleViewAction()
        problems.setText("&Problems Panel")
        problems.setShortcut(QKeySequence("Ctrl+Shift+M"))
        view_menu.addAction(problems)

        output = self._window._output_panel.toggleViewAction()
        output.setText("&Output Panel")
        output.setShortcut(QKeySequence("Ctrl+`"))
        view_menu.addAction(output)

        search = self._window._search_panel.toggleViewAction()
        search.setText("&Search Panel")
        search.setShortcut(QKeySequence("Ctrl+Shift+J"))
        view_menu.addAction(search)

    def _build_run_menu(self, menu_bar: QMenuBar) -> None:
        run_menu = menu_bar.addMenu("&Run")

        # Use shared actions so enable/disable stays in sync
        run_menu.addAction(self._window._run_action)

        run_sel = run_menu.addAction("Run &Selection / Line")
        run_sel.setShortcut(QKeySequence("Shift+F5"))
        run_sel.triggered.connect(self._window.action_run_selection)

        run_menu.addAction(self._window._stop_action)

        run_menu.addSeparator()

        theme_name = self._window._settings.get("editor.theme") or ""
        _restart_icon = load_themed_icon("restart", theme_name)
        restart_console = run_menu.addAction(_restart_icon, "Restart Python &Console")
        restart_console.triggered.connect(self._window._on_repl_restart)
        # Expose so MainWindow._refresh_themed_icons can re-tint on theme switch
        self._window._restart_console_action = restart_console

        run_menu.addSeparator()

        # Debug actions
        run_menu.addAction(self._window._debug_action)

        self._window._debug_continue_action = run_menu.addAction("&Continue")
        self._window._debug_continue_action.setShortcut(QKeySequence("Ctrl+F6"))
        self._window._debug_continue_action.triggered.connect(self._window.action_debug_continue)
        self._window._debug_continue_action.setEnabled(False)

        self._window._debug_step_over_action = run_menu.addAction("Step &Over")
        self._window._debug_step_over_action.setShortcut(QKeySequence("F10"))
        self._window._debug_step_over_action.triggered.connect(self._window.action_debug_step_over)
        self._window._debug_step_over_action.setEnabled(False)

        self._window._debug_step_into_action = run_menu.addAction("Step &Into")
        self._window._debug_step_into_action.setShortcut(QKeySequence("F11"))
        self._window._debug_step_into_action.triggered.connect(self._window.action_debug_step_into)
        self._window._debug_step_into_action.setEnabled(False)

        self._window._debug_step_out_action = run_menu.addAction("Step Ou&t")
        self._window._debug_step_out_action.setShortcut(QKeySequence("Shift+F11"))
        self._window._debug_step_out_action.triggered.connect(self._window.action_debug_step_out)
        self._window._debug_step_out_action.setEnabled(False)

        self._window._debug_stop_action = run_menu.addAction("Stop &Debugging")
        self._window._debug_stop_action.setShortcut(QKeySequence("Ctrl+Shift+F5"))
        self._window._debug_stop_action.triggered.connect(self._window.action_stop_debug)
        self._window._debug_stop_action.setEnabled(False)

        run_menu.addSeparator()

        toggle_bp = run_menu.addAction("Toggle &Breakpoint")
        toggle_bp.setShortcut(QKeySequence("F9"))
        toggle_bp.triggered.connect(self._window.action_toggle_breakpoint)

        clear_all_bp = run_menu.addAction("Clear All Brea&kpoints")
        clear_all_bp.triggered.connect(self._window.action_clear_all_breakpoints)

        run_menu.addSeparator()

        select_interp = run_menu.addAction("Select &Interpreter...")
        select_interp.triggered.connect(self._window.action_select_interpreter)

        create_venv = run_menu.addAction("Create &Virtual Environment...")
        create_venv.triggered.connect(self._window.action_create_venv)

    def _build_ai_menu(self, menu_bar: QMenuBar) -> None:
        ai_menu = menu_bar.addMenu("A&I")

        review = ai_menu.addAction("&Review Current File")
        review.setShortcut(QKeySequence("Ctrl+Shift+R"))
        review.setToolTip(
            "Ask the AI to review your entire file and give feedback"
        )
        review.triggered.connect(self._window.action_ai_review_file)

        ai_menu.addSeparator()

        ai_chat = self._window._ai_chat_panel.toggleViewAction()
        ai_chat.setText("&AI Chat Panel")
        ai_chat.setShortcut(QKeySequence("Ctrl+Shift+A"))
        ai_menu.addAction(ai_chat)

    def _build_help_menu(self, menu_bar: QMenuBar) -> None:
        help_menu = menu_bar.addMenu("&Help")

        welcome = help_menu.addAction("&Welcome Screen")
        welcome.triggered.connect(self._window.action_show_welcome)

        examples = help_menu.addAction("&Example Library...")
        examples.setShortcut(QKeySequence("Ctrl+Shift+L"))
        examples.triggered.connect(self._window.action_example_library)

        shortcuts = help_menu.addAction("&Keyboard Shortcuts...")
        shortcuts.triggered.connect(self._window.action_shortcut_reference)

        help_menu.addSeparator()

        about = help_menu.addAction("&About MeadowPy")
        about.triggered.connect(self._window.action_about)

    def _focused_widget_call(self, method_name: str) -> None:
        """Route an edit command to the widget that currently has focus.

        Works for any Qt text widget (QScintilla, QTextBrowser,
        QPlainTextEdit, QLineEdit, etc.).  Falls back to the current
        editor if the focused widget does not support the method.
        """
        from PyQt6.QtWidgets import QApplication
        focus = QApplication.focusWidget()
        if focus and hasattr(focus, method_name):
            getattr(focus, method_name)()
            return
        # Fallback: try the active code editor
        self._editor_call(method_name)

    def _editor_call(self, method_name: str) -> None:
        """Call a method on the current editor if one exists."""
        editor = self._window._tab_manager.current_editor()
        if editor and hasattr(editor, method_name):
            getattr(editor, method_name)()

"""Application-wide constants and default settings."""

APP_NAME = "MeadowPy"
VERSION = "1.0.4"
CONFIG_DIR_NAME = ".meadowpy"
SETTINGS_FILENAME = "settings.json"
RECENT_FILES_MAX = 15
UNTITLED_PREFIX = "Untitled"

DEFAULT_SETTINGS = {
    "editor.font_family": "Consolas",
    "editor.font_size": 14,
    "editor.tab_width": 4,
    "editor.use_spaces": True,
    "editor.show_line_numbers": True,
    "editor.highlight_current_line": True,
    "editor.word_wrap": True,
    "editor.show_whitespace": False,
    "editor.show_indentation_guides": False,
    "editor.auto_indent": True,
    "editor.brace_matching": True,
    "editor.code_folding": True,
    "editor.theme": "default_dark",
    # When editor.theme == "custom", these determine the appearance:
    #   base   — which template to render ("light" or "dark")
    #   accent — the hex accent color that replaces the default green
    "editor.custom_theme.base": "dark",
    "editor.custom_theme.accent": "#3B82F6",
    "window.geometry": None,
    "window.state": "AAAA/wAAAAD9AAAAAgAAAAAAAAE9AAADGfwCAAAAAvsAAAAYAEYAaQBsAGUARQB4AHAAbABvAHIAZQByAQAAAEgAAAFyAAAAgwD////7AAAAFgBPAHUAdABwAHUAdABQAGEAbgBlAGwBAAABvQAAAaQAAACzAP///wAAAAEAAAEgAAADGfwCAAAAA/wAAABIAAABdwAAAIgBAAAi+gAAAAEBAAAAAvsAAAAaAFAAcgBvAGIAbABlAG0AcwBQAGEAbgBlAGwBAAAAAP////8AAABIAP////sAAAAaAFMAeQBtAGIAbwBsAE8AdQB0AGwAaQBuAGUBAAAFCgAAAPYAAABIAP////wAAAHCAAABnwAAAQoBAAAi+gAAAAABAAAAAvsAAAAWAEEASQBDAGgAYQB0AFAAYQBuAGUAbAEAAATgAAABIAAAAKgA////+wAAABYAUwBlAGEAcgBjAGgAUABhAG4AZQBsAQAAAAD/////AAAAzwD////8AAAAzgAAAK0AAAAAAP////r/////AQAAAAP7AAAAFABXAGEAdABjAGgAUABhAG4AZQBsAAAAAAD/////AAAAbgD////7AAAAHABDAGEAbABsAFMAdABhAGMAawBQAGEAbgBlAGwAAAAAAP////8AAABIAP////sAAAAiAFYAYQByAGkAYQBiAGwAZQBJAG4AcwBwAGUAYwB0AG8AcgAAAAAA/////wAAAEgA////AAADnQAAAxkAAAAEAAAABAAAAAgAAAAI/AAAAAEAAAACAAAAAQAAABYATQBhAGkAbgBUAG8AbwBsAEIAYQByAQAAAAD/////AAAAAAAAAAA=",
    "window.recent_files": [],
    # Phase 2: Code Intelligence
    "editor.smart_indent": True,
    "editor.auto_close_brackets": True,
    "editor.auto_complete": True,
    "editor.auto_complete_threshold": 2,
    "editor.show_symbol_outline": True,
    "editor.linting_enabled": True,
    "editor.linter": "flake8",
    "editor.lint_on_save": True,
    "editor.lint_delay_ms": 1500,

    # Phase 3: Code Execution
    "run.python_interpreter": "",           # empty = auto-detect (sys.executable)
    "run.working_directory": "file",        # "file" = file's parent dir
    "run.clear_output_before_run": True,
    "run.save_before_run": True,
    "run.max_output_lines": 10000,
    "run.show_output_panel": True,          # auto-show output panel on run

    "general.auto_save_interval": 0,
    "general.restore_tabs_on_startup": True,
    "general.open_files": [],

    # Phase 5: File Explorer
    "general.project_folder": "",
    "explorer.show_file_explorer": True,

    # Interactive Console (REPL)
    "repl.auto_start": True,

    # Phase 7: Ollama AI Integration
    "ollama.api_url": "http://localhost:11434",
    "ollama.selected_model": "",
    "ollama.auto_connect": True,
}

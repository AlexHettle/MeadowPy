"""Application preferences dialog."""

from typing import Any

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
    QStackedWidget, QDialogButtonBox, QWidget, QFormLayout,
    QSpinBox, QCheckBox, QComboBox, QFontComboBox, QLineEdit,
    QAbstractItemView,
)

from meadowpy.core.settings import Settings
from meadowpy.editor.themes import THEMES


class PreferencesDialog(QDialog):
    """Application preferences dialog with categorized settings."""

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._pending_changes: dict[str, Any] = {}

        self.setWindowTitle("Preferences")
        self.setMinimumSize(600, 450)
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        content_layout = QHBoxLayout()

        # Left: category list
        self._category_list = QListWidget()
        self._category_list.setFixedWidth(160)
        self._category_list.setObjectName("prefsCategory")
        self._category_list.addItems(["Editor", "Appearance", "Linting", "Execution", "General", "AI"])
        self._category_list.currentRowChanged.connect(self._on_category_changed)

        # Right: stacked pages
        self._pages = QStackedWidget()
        self._pages.addWidget(self._create_editor_page())
        self._pages.addWidget(self._create_appearance_page())
        self._pages.addWidget(self._create_linting_page())
        self._pages.addWidget(self._create_execution_page())
        self._pages.addWidget(self._create_general_page())
        self._pages.addWidget(self._create_ai_page())

        content_layout.addWidget(self._category_list)
        content_layout.addWidget(self._pages, 1)
        main_layout.addLayout(content_layout, 1)

        # Bottom buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        buttons.accepted.connect(self._apply_and_close)
        buttons.rejected.connect(self.reject)
        apply_btn = buttons.button(QDialogButtonBox.StandardButton.Apply)
        if apply_btn:
            apply_btn.clicked.connect(self._apply)
        main_layout.addWidget(buttons)

        self._category_list.setCurrentRow(0)

    def _create_editor_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        # Font family
        self._font_combo = QFontComboBox()
        self._font_combo.setCurrentFont(
            self._font_combo.font()
        )
        current_family = self._settings.get("editor.font_family")
        self._font_combo.setCurrentText(current_family)
        self._font_combo.currentTextChanged.connect(
            lambda v: self._stage("editor.font_family", v)
        )
        form.addRow("Font Family:", self._font_combo)

        # Font size
        self._font_size = QSpinBox()
        self._font_size.setRange(8, 72)
        self._font_size.setValue(self._settings.get("editor.font_size"))
        self._font_size.valueChanged.connect(
            lambda v: self._stage("editor.font_size", v)
        )
        form.addRow("Font Size:", self._font_size)

        # Tab width
        self._tab_width = QSpinBox()
        self._tab_width.setRange(1, 8)
        self._tab_width.setValue(self._settings.get("editor.tab_width"))
        self._tab_width.valueChanged.connect(
            lambda v: self._stage("editor.tab_width", v)
        )
        form.addRow("Tab Width:", self._tab_width)

        # Use spaces
        self._use_spaces = QCheckBox("Insert spaces instead of tabs")
        self._use_spaces.setChecked(self._settings.get("editor.use_spaces"))
        self._use_spaces.toggled.connect(
            lambda v: self._stage("editor.use_spaces", v)
        )
        form.addRow("", self._use_spaces)

        # Auto indent
        self._auto_indent = QCheckBox("Enable auto-indentation")
        self._auto_indent.setChecked(self._settings.get("editor.auto_indent"))
        self._auto_indent.toggled.connect(
            lambda v: self._stage("editor.auto_indent", v)
        )
        form.addRow("", self._auto_indent)

        # Smart indent
        self._smart_indent = QCheckBox("Enable smart indent/dedent")
        self._smart_indent.setChecked(self._settings.get("editor.smart_indent"))
        self._smart_indent.toggled.connect(
            lambda v: self._stage("editor.smart_indent", v)
        )
        form.addRow("", self._smart_indent)

        # Auto-close brackets
        self._auto_close = QCheckBox("Auto-close brackets and quotes")
        self._auto_close.setChecked(self._settings.get("editor.auto_close_brackets"))
        self._auto_close.toggled.connect(
            lambda v: self._stage("editor.auto_close_brackets", v)
        )
        form.addRow("", self._auto_close)

        # Auto-completion
        self._auto_complete = QCheckBox("Enable auto-completion")
        self._auto_complete.setChecked(self._settings.get("editor.auto_complete"))
        self._auto_complete.toggled.connect(
            lambda v: self._stage("editor.auto_complete", v)
        )
        form.addRow("", self._auto_complete)

        # Indentation guides
        self._indent_guides = QCheckBox("Show indentation guides")
        self._indent_guides.setChecked(
            self._settings.get("editor.show_indentation_guides")
        )
        self._indent_guides.toggled.connect(
            lambda v: self._stage("editor.show_indentation_guides", v)
        )
        form.addRow("", self._indent_guides)

        # Word wrap
        self._word_wrap = QCheckBox("Enable word wrap")
        self._word_wrap.setChecked(self._settings.get("editor.word_wrap"))
        self._word_wrap.toggled.connect(
            lambda v: self._stage("editor.word_wrap", v)
        )
        form.addRow("", self._word_wrap)

        # Brace matching
        self._brace_match = QCheckBox("Enable brace matching")
        self._brace_match.setChecked(self._settings.get("editor.brace_matching"))
        self._brace_match.toggled.connect(
            lambda v: self._stage("editor.brace_matching", v)
        )
        form.addRow("", self._brace_match)

        # Code folding
        self._code_folding = QCheckBox("Enable code folding")
        self._code_folding.setChecked(self._settings.get("editor.code_folding"))
        self._code_folding.toggled.connect(
            lambda v: self._stage("editor.code_folding", v)
        )
        form.addRow("", self._code_folding)

        return page

    def _create_appearance_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        # Theme
        _THEME_DISPLAY = {
            "default_light": "Light Theme",
            "default_dark": "Dark Theme",
        }
        self._theme_combo = QComboBox()
        for theme_name in THEMES:
            display = _THEME_DISPLAY.get(
                theme_name, theme_name.replace("_", " ").title()
            )
            self._theme_combo.addItem(display, theme_name)
        current_theme = self._settings.get("editor.theme")
        idx = self._theme_combo.findData(current_theme)
        if idx >= 0:
            self._theme_combo.setCurrentIndex(idx)
        self._theme_combo.currentIndexChanged.connect(
            lambda i: self._stage("editor.theme", self._theme_combo.itemData(i))
        )
        form.addRow("Theme:", self._theme_combo)

        # Show line numbers
        self._line_numbers = QCheckBox("Show line numbers")
        self._line_numbers.setChecked(self._settings.get("editor.show_line_numbers"))
        self._line_numbers.toggled.connect(
            lambda v: self._stage("editor.show_line_numbers", v)
        )
        form.addRow("", self._line_numbers)

        # Highlight current line
        self._highlight_line = QCheckBox("Highlight current line")
        self._highlight_line.setChecked(
            self._settings.get("editor.highlight_current_line")
        )
        self._highlight_line.toggled.connect(
            lambda v: self._stage("editor.highlight_current_line", v)
        )
        form.addRow("", self._highlight_line)

        # Show whitespace
        self._show_whitespace = QCheckBox("Show whitespace characters")
        self._show_whitespace.setChecked(
            self._settings.get("editor.show_whitespace")
        )
        self._show_whitespace.toggled.connect(
            lambda v: self._stage("editor.show_whitespace", v)
        )
        form.addRow("", self._show_whitespace)

        # Show symbol outline
        self._show_outline = QCheckBox("Show symbol outline panel")
        self._show_outline.setChecked(
            self._settings.get("editor.show_symbol_outline")
        )
        self._show_outline.toggled.connect(
            lambda v: self._stage("editor.show_symbol_outline", v)
        )
        form.addRow("", self._show_outline)

        return page

    def _create_linting_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        # Linter choice
        self._linter_combo = QComboBox()
        self._linter_combo.addItems(["flake8", "pylint"])
        current = self._settings.get("editor.linter")
        idx = self._linter_combo.findText(current)
        if idx >= 0:
            self._linter_combo.setCurrentIndex(idx)
        self._linter_combo.currentTextChanged.connect(
            lambda v: self._stage("editor.linter", v)
        )
        form.addRow("Linter:", self._linter_combo)

        # Enable linting
        self._linting_enabled = QCheckBox("Enable linting")
        self._linting_enabled.setChecked(
            self._settings.get("editor.linting_enabled")
        )
        self._linting_enabled.toggled.connect(
            lambda v: self._stage("editor.linting_enabled", v)
        )
        form.addRow("", self._linting_enabled)

        # Lint on save
        self._lint_on_save = QCheckBox("Lint on save")
        self._lint_on_save.setChecked(self._settings.get("editor.lint_on_save"))
        self._lint_on_save.toggled.connect(
            lambda v: self._stage("editor.lint_on_save", v)
        )
        form.addRow("", self._lint_on_save)

        return page

    def _create_execution_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        # Interpreter path
        self._interp_path = QLineEdit()
        self._interp_path.setPlaceholderText("(auto-detect system Python)")
        self._interp_path.setText(
            self._settings.get("run.python_interpreter")
        )
        self._interp_path.textChanged.connect(
            lambda v: self._stage("run.python_interpreter", v)
        )
        form.addRow("Interpreter Path:", self._interp_path)

        # Working directory mode
        self._working_dir_combo = QComboBox()
        self._working_dir_combo.addItem("File location", "file")
        self._working_dir_combo.addItem("Project folder", "project")
        current_wd = self._settings.get("run.working_directory")
        wd_idx = self._working_dir_combo.findData(current_wd)
        if wd_idx >= 0:
            self._working_dir_combo.setCurrentIndex(wd_idx)
        self._working_dir_combo.currentIndexChanged.connect(
            lambda i: self._stage(
                "run.working_directory", self._working_dir_combo.itemData(i)
            )
        )
        form.addRow("Working Directory:", self._working_dir_combo)

        # Save before run
        self._save_before_run = QCheckBox("Save file before running")
        self._save_before_run.setChecked(
            self._settings.get("run.save_before_run")
        )
        self._save_before_run.toggled.connect(
            lambda v: self._stage("run.save_before_run", v)
        )
        form.addRow("", self._save_before_run)

        # Clear output before run
        self._clear_before_run = QCheckBox("Clear output before running")
        self._clear_before_run.setChecked(
            self._settings.get("run.clear_output_before_run")
        )
        self._clear_before_run.toggled.connect(
            lambda v: self._stage("run.clear_output_before_run", v)
        )
        form.addRow("", self._clear_before_run)

        # Auto-show output panel
        self._show_output = QCheckBox("Show output panel on run")
        self._show_output.setChecked(
            self._settings.get("run.show_output_panel")
        )
        self._show_output.toggled.connect(
            lambda v: self._stage("run.show_output_panel", v)
        )
        form.addRow("", self._show_output)

        # Max output lines
        self._max_lines = QSpinBox()
        self._max_lines.setRange(1000, 100000)
        self._max_lines.setSingleStep(1000)
        self._max_lines.setValue(
            self._settings.get("run.max_output_lines")
        )
        self._max_lines.valueChanged.connect(
            lambda v: self._stage("run.max_output_lines", v)
        )
        form.addRow("Max Output Lines:", self._max_lines)

        return page

    def _create_general_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        # Restore tabs
        self._restore_tabs = QCheckBox("Restore tabs on startup")
        self._restore_tabs.setChecked(
            self._settings.get("general.restore_tabs_on_startup")
        )
        self._restore_tabs.toggled.connect(
            lambda v: self._stage("general.restore_tabs_on_startup", v)
        )
        form.addRow("", self._restore_tabs)

        return page

    def _create_ai_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        # Ollama API URL
        self._ollama_url = QLineEdit()
        self._ollama_url.setPlaceholderText("http://localhost:11434")
        self._ollama_url.setText(
            self._settings.get("ollama.api_url")
        )
        self._ollama_url.textChanged.connect(
            lambda v: self._stage("ollama.api_url", v)
        )
        form.addRow("Ollama API URL:", self._ollama_url)

        # Auto-connect on startup
        self._ollama_auto = QCheckBox("Automatically connect to Ollama on startup")
        self._ollama_auto.setChecked(self._settings.get("ollama.auto_connect"))
        self._ollama_auto.toggled.connect(
            lambda v: self._stage("ollama.auto_connect", v)
        )
        form.addRow("", self._ollama_auto)

        return page

    def _on_category_changed(self, index: int) -> None:
        self._pages.setCurrentIndex(index)

    def _stage(self, key: str, value: Any) -> None:
        """Stage a change to be applied later."""
        self._pending_changes[key] = value

    def _apply(self) -> None:
        """Apply pending changes to settings."""
        for key, value in self._pending_changes.items():
            self._settings.set(key, value)
        self._settings.save()
        self._pending_changes.clear()

    def _apply_and_close(self) -> None:
        self._apply()
        self.accept()

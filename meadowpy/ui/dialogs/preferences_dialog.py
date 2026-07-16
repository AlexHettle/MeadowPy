"""Application preferences dialog."""

import os
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QProcess, QTimer, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFont, QWheelEvent
from PyQt6.QtWidgets import (
    QApplication, QAbstractScrollArea, QDialog, QVBoxLayout, QHBoxLayout,
    QListWidget,
    QStackedWidget, QDialogButtonBox, QWidget, QFormLayout,
    QSpinBox, QCheckBox, QComboBox, QFontComboBox, QLineEdit,
    QPushButton, QRadioButton, QButtonGroup, QLabel, QFileDialog,
    QFrame, QGroupBox, QMessageBox, QScrollArea,
)

from meadowpy.core.settings import Settings
from meadowpy.core.interpreter_manager import InterpreterManager
from meadowpy.core.lint_context import (
    LintContextError,
    LintExecutionContext,
    resolve_lint_context,
    resolve_lint_target_root,
)
from meadowpy.core.linter import (
    LINTER_TEST_SOURCE,
    build_linter_stdin_command,
    lint_test_exit_succeeded,
)
from meadowpy.editor.editor_fonts import editor_font_family
from meadowpy.editor.themes import THEMES


class _SettingsOverlay:
    """Read staged Preferences values without persisting them."""

    def __init__(self, settings: Settings, overrides: dict[str, Any]):
        self._settings = settings
        self._overrides = overrides

    def get(self, key: str, default=None):
        if key in self._overrides:
            return self._overrides[key]
        return self._settings.get(key, default)


class _WheelSafeComboBox(QComboBox):
    """Let a surrounding scroll area own wheel gestures."""

    def wheelEvent(self, event) -> None:
        _forward_wheel_to_scroll_area(self, event)


class _WheelSafeSpinBox(QSpinBox):
    """Prevent page scrolling from silently changing a numeric value."""

    def wheelEvent(self, event) -> None:
        _forward_wheel_to_scroll_area(self, event)


def _forward_wheel_to_scroll_area(widget: QWidget, event: QWheelEvent) -> None:
    """Forward a value control's wheel gesture to its enclosing page."""

    parent = widget.parentWidget()
    while parent is not None and not isinstance(parent, QAbstractScrollArea):
        parent = parent.parentWidget()
    if parent is None:
        event.ignore()
        return

    pixel_delta = event.pixelDelta()
    angle_delta = event.angleDelta()
    use_horizontal = abs(pixel_delta.x()) > abs(pixel_delta.y())
    if pixel_delta.isNull():
        use_horizontal = abs(angle_delta.x()) > abs(angle_delta.y())
    scroll_bar = (
        parent.horizontalScrollBar()
        if use_horizontal
        else parent.verticalScrollBar()
    )
    pixel_distance = pixel_delta.x() if use_horizontal else pixel_delta.y()
    if pixel_distance:
        distance = pixel_distance
    else:
        angle_distance = angle_delta.x() if use_horizontal else angle_delta.y()
        distance = (
            angle_distance
            / 120
            * scroll_bar.singleStep()
            * QApplication.wheelScrollLines()
        )
    scroll_bar.setValue(scroll_bar.value() - round(distance))
    event.accept()


class PreferencesDialog(QDialog):
    """Application preferences dialog with categorized settings."""

    preferences_applied = pyqtSignal(object)

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._pending_changes: dict[str, Any] = {}
        self._lint_test_process: QProcess | None = None
        self._lint_test_provider: str | None = None
        self._lint_test_context: LintExecutionContext | None = None
        self._lint_test_stale = False
        self._lint_test_timed_out = False
        self._lint_test_timer = QTimer(self)
        self._lint_test_timer.setSingleShot(True)
        self._lint_test_timer.timeout.connect(self._on_lint_test_timeout)

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
        self._font_combo.setFontFilters(QFontComboBox.FontFilter.ScalableFonts)
        current_family = editor_font_family(self._settings.get("editor.font_family"))
        self._font_combo.setCurrentFont(QFont(current_family))
        self._font_combo.currentFontChanged.connect(self._stage_font_family)
        form.addRow("Editor Font Family:", self._font_combo)

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
            "default_high_contrast": "High Contrast (Accessibility)",
            "custom": "Custom Theme",
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
            lambda i: self._on_theme_changed(self._theme_combo.itemData(i))
        )
        form.addRow("Theme:", self._theme_combo)

        # ── Custom-theme controls (shown only when "Custom" is selected) ──
        self._custom_theme_container = QWidget()
        custom_layout = QFormLayout(self._custom_theme_container)
        custom_layout.setContentsMargins(0, 0, 0, 0)

        # Base: Light or Dark
        base_row = QHBoxLayout()
        base_row.setContentsMargins(0, 0, 0, 0)
        self._custom_base_group = QButtonGroup(self)
        self._custom_base_dark = QRadioButton("Dark")
        self._custom_base_light = QRadioButton("Light")
        self._custom_base_group.addButton(self._custom_base_dark)
        self._custom_base_group.addButton(self._custom_base_light)
        base_row.addWidget(self._custom_base_dark)
        base_row.addWidget(self._custom_base_light)
        base_row.addStretch()
        if (self._settings.get("editor.custom_theme.base") or "dark").lower() == "light":
            self._custom_base_light.setChecked(True)
        else:
            self._custom_base_dark.setChecked(True)
        self._custom_base_dark.toggled.connect(
            lambda v: v and self._stage("editor.custom_theme.base", "dark")
        )
        self._custom_base_light.toggled.connect(
            lambda v: v and self._stage("editor.custom_theme.base", "light")
        )
        base_container = QWidget()
        base_container.setLayout(base_row)
        custom_layout.addRow("Base:", base_container)

        # Accent color picker
        accent_row = QHBoxLayout()
        accent_row.setContentsMargins(0, 0, 0, 0)
        # Use a QLabel so the native button frame doesn't fight the
        # border-radius at the corners. Fixed square keeps the rounded
        # corners symmetric.
        self._accent_swatch = QLabel()
        self._accent_swatch.setFixedSize(22, 22)
        self._accent_hex_label = QLabel()
        self._pick_accent_btn = QPushButton("Pick color\u2026")
        self._pick_accent_btn.clicked.connect(self._on_pick_accent)
        accent_row.addWidget(self._accent_swatch)
        accent_row.addWidget(self._accent_hex_label)
        accent_row.addStretch()
        accent_row.addWidget(self._pick_accent_btn)
        accent_container = QWidget()
        accent_container.setLayout(accent_row)
        custom_layout.addRow("Accent:", accent_container)

        self._refresh_accent_swatch(
            self._settings.get("editor.custom_theme.accent") or "#3B82F6"
        )

        form.addRow("", self._custom_theme_container)
        self._custom_theme_container.setVisible(current_theme == "custom")

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
        page = QScrollArea()
        page.setObjectName("lintPreferencesScroll")
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("lintPreferencesContent")
        layout = QVBoxLayout(content)

        general_group = QGroupBox("General")
        general_form = QFormLayout(general_group)

        # Enable linting
        self._linting_enabled = QCheckBox("Enable linting")
        self._linting_enabled.setChecked(
            bool(self._settings.get("editor.linting_enabled", True))
        )
        self._linting_enabled.toggled.connect(
            lambda v: self._on_lint_common_changed(
                "editor.linting_enabled", v
            )
        )
        general_form.addRow("", self._linting_enabled)

        # Linter choice
        self._linter_combo = _WheelSafeComboBox()
        self._linter_combo.addItems(["flake8", "pylint"])
        current = self._settings.get("editor.linter", "flake8")
        idx = self._linter_combo.findText(current)
        if idx >= 0:
            self._linter_combo.setCurrentIndex(idx)
        self._active_lint_provider = self._linter_combo.currentText()
        self._linter_combo.currentTextChanged.connect(self._on_linter_changed)
        general_form.addRow("Linter:", self._linter_combo)

        # Styling issue visibility
        self._show_lint_style_issues = QCheckBox("Show styling issues")
        self._show_lint_style_issues.setChecked(
            bool(self._settings.get("editor.show_lint_style_issues", True))
        )
        self._show_lint_style_issues.toggled.connect(
            lambda v: self._on_lint_common_changed(
                "editor.show_lint_style_issues", v
            )
        )
        general_form.addRow("", self._show_lint_style_issues)
        layout.addWidget(general_group)

        trigger_group = QGroupBox("Triggers")
        trigger_form = QFormLayout(trigger_group)

        self._lint_while_typing = QCheckBox("Lint while typing")
        self._lint_while_typing.setChecked(
            bool(self._settings.get("editor.lint_while_typing", True))
        )
        self._lint_while_typing.toggled.connect(
            lambda v: self._on_lint_common_changed(
                "editor.lint_while_typing", v
            )
        )
        trigger_form.addRow("", self._lint_while_typing)

        # Lint on save
        self._lint_on_save = QCheckBox("Lint on save")
        self._lint_on_save.setChecked(
            bool(self._settings.get("editor.lint_on_save", True))
        )
        self._lint_on_save.toggled.connect(
            lambda v: self._on_lint_common_changed("editor.lint_on_save", v)
        )
        trigger_form.addRow("", self._lint_on_save)

        self._lint_delay = _WheelSafeSpinBox()
        self._lint_delay.setRange(100, 5000)
        self._lint_delay.setSingleStep(100)
        self._lint_delay.setSuffix(" ms")
        self._lint_delay.setValue(
            self._bounded_int_setting("editor.lint_delay_ms", 1500, 100, 5000)
        )
        self._lint_delay.valueChanged.connect(
            lambda v: self._on_lint_common_changed("editor.lint_delay_ms", v)
        )
        trigger_form.addRow("Typing Delay:", self._lint_delay)
        layout.addWidget(trigger_group)

        environment_group = QGroupBox("Environment")
        environment_form = QFormLayout(environment_group)

        self._lint_interpreter_mode_combo = _WheelSafeComboBox()
        self._lint_interpreter_mode_combo.addItem(
            "Selected Run interpreter", "selected"
        )
        self._lint_interpreter_mode_combo.addItem(
            "MeadowPy interpreter", "meadowpy"
        )
        self._lint_interpreter_mode_combo.addItem(
            "Custom interpreter", "custom"
        )
        self._set_combo_data(
            self._lint_interpreter_mode_combo,
            self._settings.get("editor.lint_interpreter_mode", "selected"),
            "selected",
        )
        self._lint_interpreter_mode_combo.currentIndexChanged.connect(
            self._on_lint_interpreter_mode_changed
        )
        environment_form.addRow(
            "Interpreter:", self._lint_interpreter_mode_combo
        )

        interpreter_row = QWidget()
        interpreter_layout = QHBoxLayout(interpreter_row)
        interpreter_layout.setContentsMargins(0, 0, 0, 0)
        self._lint_interpreter_path = QLineEdit()
        self._lint_interpreter_path.setPlaceholderText(
            "Select a Python executable"
        )
        self._lint_interpreter_path.setText(
            str(self._settings.get("editor.lint_interpreter_path", "") or "")
        )
        self._lint_interpreter_path.textChanged.connect(
            lambda v: self._on_lint_common_changed(
                "editor.lint_interpreter_path", v
            )
        )
        self._browse_lint_interpreter_btn = QPushButton("Browse…")
        self._browse_lint_interpreter_btn.clicked.connect(
            self._browse_lint_interpreter
        )
        interpreter_layout.addWidget(self._lint_interpreter_path, 1)
        interpreter_layout.addWidget(self._browse_lint_interpreter_btn)
        environment_form.addRow("Custom Path:", interpreter_row)

        self._lint_working_directory_combo = _WheelSafeComboBox()
        self._lint_working_directory_combo.addItem("Project folder", "project")
        self._lint_working_directory_combo.addItem("File location", "file")
        self._set_combo_data(
            self._lint_working_directory_combo,
            self._settings.get("editor.lint_working_directory", "project"),
            "project",
        )
        self._lint_working_directory_combo.currentIndexChanged.connect(
            self._on_lint_working_directory_changed
        )
        environment_form.addRow(
            "Working Directory:", self._lint_working_directory_combo
        )
        layout.addWidget(environment_group)

        configuration_group = QGroupBox("Configuration")
        configuration_form = QFormLayout(configuration_group)

        self._lint_config_mode_combo = _WheelSafeComboBox()
        self._lint_config_mode_combo.addItem(
            "Auto-detect project configuration", "auto"
        )
        self._lint_config_mode_combo.addItem(
            "Use linter defaults only", "defaults"
        )
        self._lint_config_mode_combo.addItem(
            "Use a specific configuration file", "explicit"
        )
        self._lint_config_mode_combo.currentIndexChanged.connect(
            self._on_lint_config_mode_changed
        )
        configuration_form.addRow("Configuration:", self._lint_config_mode_combo)

        config_row = QWidget()
        config_layout = QHBoxLayout(config_row)
        config_layout.setContentsMargins(0, 0, 0, 0)
        self._lint_config_path = QLineEdit()
        self._lint_config_path.setPlaceholderText(
            "Select a linter configuration file"
        )
        self._lint_config_path.textChanged.connect(self._on_lint_config_path_changed)
        self._browse_lint_config_btn = QPushButton("Browse…")
        self._browse_lint_config_btn.clicked.connect(self._browse_lint_config)
        config_layout.addWidget(self._lint_config_path, 1)
        config_layout.addWidget(self._browse_lint_config_btn)
        configuration_form.addRow("Config File:", config_row)

        self._lint_timeout = _WheelSafeSpinBox()
        self._lint_timeout.setRange(1, 120)
        self._lint_timeout.setSuffix(" seconds")
        self._lint_timeout.valueChanged.connect(self._on_lint_timeout_changed)
        configuration_form.addRow("Timeout:", self._lint_timeout)
        layout.addWidget(configuration_group)

        trust_group = QGroupBox("Project Trust")
        trust_layout = QVBoxLayout(trust_group)
        self._lint_project_label = QLabel()
        self._lint_project_label.setWordWrap(True)
        self._lint_trust_status_label = QLabel()
        self._lint_trust_status_label.setWordWrap(True)
        self._lint_trust_notice = QLabel()
        self._lint_trust_notice.setWordWrap(True)
        trust_buttons = QHBoxLayout()
        self._trust_lint_project_btn = QPushButton("Trust Current Target")
        self._trust_lint_project_btn.clicked.connect(self._trust_lint_project)
        self._revoke_lint_project_btn = QPushButton("Revoke Trust")
        self._revoke_lint_project_btn.clicked.connect(self._revoke_lint_project)
        trust_buttons.addWidget(self._trust_lint_project_btn)
        trust_buttons.addWidget(self._revoke_lint_project_btn)
        trust_buttons.addStretch()
        trust_layout.addWidget(self._lint_project_label)
        trust_layout.addWidget(self._lint_trust_status_label)
        trust_layout.addWidget(self._lint_trust_notice)
        trust_layout.addLayout(trust_buttons)
        layout.addWidget(trust_group)

        effective_group = QGroupBox("Effective Settings")
        effective_layout = QVBoxLayout(effective_group)
        self._lint_effective_summary = QLabel()
        self._lint_effective_summary.setWordWrap(True)
        self._lint_effective_summary.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._open_effective_config_btn = QPushButton("Open Effective Config")
        self._open_effective_config_btn.clicked.connect(
            self._open_effective_lint_config
        )
        self._test_linter_btn = QPushButton("Test Linter")
        self._test_linter_btn.clicked.connect(self._test_linter_settings)
        effective_buttons = QHBoxLayout()
        effective_buttons.addWidget(self._open_effective_config_btn)
        effective_buttons.addWidget(self._test_linter_btn)
        effective_buttons.addStretch()
        self._lint_test_result = QLabel()
        self._lint_test_result.setWordWrap(True)
        effective_layout.addWidget(self._lint_effective_summary)
        effective_layout.addLayout(effective_buttons)
        effective_layout.addWidget(self._lint_test_result)
        layout.addWidget(effective_group)
        layout.addStretch()

        page.setWidget(content)
        self._load_lint_provider_controls(self._active_lint_provider)
        self._update_lint_interpreter_controls()
        self._refresh_lint_summary()
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
        self._restore_tabs.toggled.connect(self._stage_restore_tabs)
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

    def _effective_value(self, key: str, default=None) -> Any:
        """Return a staged value when present, otherwise the saved value."""
        if key in self._pending_changes:
            return self._pending_changes[key]
        return self._settings.get(key, default)

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: Any, fallback: str) -> None:
        """Select a combo item by user data with a safe fallback."""
        index = combo.findData(value)
        if index < 0:
            index = combo.findData(fallback)
        combo.setCurrentIndex(max(index, 0))

    def _bounded_int_setting(
        self, key: str, default: int, minimum: int, maximum: int
    ) -> int:
        """Read an integer setting without letting bad JSON break the dialog."""
        value = self._settings.get(key, default)
        if isinstance(value, bool):
            return default
        try:
            number = int(value)
        except (TypeError, ValueError):
            return default
        return min(max(number, minimum), maximum)

    def _on_lint_common_changed(self, key: str, value: Any) -> None:
        self._stage(key, value)
        self._refresh_lint_summary()

    def _on_linter_changed(self, provider: str) -> None:
        if provider not in {"flake8", "pylint"}:
            return
        self._active_lint_provider = provider
        self._stage("editor.linter", provider)
        self._load_lint_provider_controls(provider)
        self._refresh_lint_summary()

    def _on_lint_interpreter_mode_changed(self, index: int) -> None:
        mode = self._lint_interpreter_mode_combo.itemData(index) or "selected"
        self._stage("editor.lint_interpreter_mode", mode)
        self._update_lint_interpreter_controls()
        self._refresh_lint_summary()

    def _on_lint_working_directory_changed(self, index: int) -> None:
        mode = self._lint_working_directory_combo.itemData(index) or "project"
        self._stage("editor.lint_working_directory", mode)
        self._refresh_lint_summary()

    @staticmethod
    def _lint_provider_key(provider: str, suffix: str) -> str:
        return f"editor.lint_{provider}_{suffix}"

    def _lint_provider_value(
        self, provider: str, suffix: str, default: Any
    ) -> Any:
        return self._effective_value(
            self._lint_provider_key(provider, suffix), default
        )

    def _load_lint_provider_controls(self, provider: str) -> None:
        """Load one provider's staged values into the shared config controls."""
        default_timeout = 10 if provider == "flake8" else 15
        mode = self._lint_provider_value(provider, "config_mode", "defaults")
        if mode not in {"auto", "defaults", "explicit"}:
            mode = "defaults"
        path = str(self._lint_provider_value(provider, "config_path", "") or "")
        timeout = self._lint_provider_value(
            provider, "timeout_seconds", default_timeout
        )
        if isinstance(timeout, bool):
            timeout = default_timeout
        try:
            timeout = int(timeout)
        except (TypeError, ValueError):
            timeout = default_timeout
        timeout = min(max(timeout, 1), 120)

        widgets = (
            self._lint_config_mode_combo,
            self._lint_config_path,
            self._lint_timeout,
        )
        for widget in widgets:
            widget.blockSignals(True)
        try:
            self._set_combo_data(self._lint_config_mode_combo, mode, "defaults")
            self._lint_config_path.setText(path)
            self._lint_timeout.setValue(timeout)
        finally:
            for widget in widgets:
                widget.blockSignals(False)
        self._update_lint_config_controls()

    def _on_lint_config_mode_changed(self, index: int) -> None:
        mode = self._lint_config_mode_combo.itemData(index) or "defaults"
        self._stage(
            self._lint_provider_key(
                self._active_lint_provider, "config_mode"
            ),
            mode,
        )
        self._update_lint_config_controls()
        self._refresh_lint_summary()

    def _on_lint_config_path_changed(self, value: str) -> None:
        self._stage(
            self._lint_provider_key(
                self._active_lint_provider, "config_path"
            ),
            value,
        )
        self._refresh_lint_summary()

    def _on_lint_timeout_changed(self, value: int) -> None:
        self._stage(
            self._lint_provider_key(
                self._active_lint_provider, "timeout_seconds"
            ),
            value,
        )
        self._refresh_lint_summary()

    def _update_lint_interpreter_controls(self) -> None:
        custom = (
            self._is_current_lint_project_trusted()
            and self._lint_interpreter_mode_combo.currentData() == "custom"
        )
        self._lint_interpreter_path.setEnabled(custom)
        self._browse_lint_interpreter_btn.setEnabled(custom)

    def _update_lint_config_controls(self) -> None:
        explicit = (
            self._is_current_lint_project_trusted()
            and self._lint_config_mode_combo.currentData() == "explicit"
        )
        self._lint_config_path.setEnabled(explicit)
        self._browse_lint_config_btn.setEnabled(explicit)

    def _browse_lint_interpreter(self) -> None:
        initial = self._lint_interpreter_path.text().strip()
        if initial and Path(initial).is_file():
            initial = str(Path(initial).parent)
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Python Interpreter",
            initial,
            "Python executable (python.exe python);;All files (*)",
        )
        if path:
            self._lint_interpreter_path.setText(path)

    def _browse_lint_config(self) -> None:
        initial = self._lint_config_path.text().strip()
        if initial and Path(initial).is_file():
            initial = str(Path(initial).parent)
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select {self._active_lint_provider.title()} Configuration",
            initial,
            "Configuration files (*.toml *.ini *.cfg *.flake8 *pylintrc*);;"
            "All files (*)",
        )
        if path:
            self._lint_config_path.setText(path)

    @staticmethod
    def _canonical_path(value: str | Path) -> str:
        """Return the normalized, resolved spelling used for trust checks."""
        path = Path(value).expanduser().resolve(strict=False)
        return os.path.normcase(str(path))

    @staticmethod
    def _path_is_within(path: str | Path, root: str | Path) -> bool:
        try:
            candidate = PreferencesDialog._canonical_path(path)
            boundary = PreferencesDialog._canonical_path(root)
            return os.path.commonpath([candidate, boundary]) == boundary
        except (OSError, ValueError):
            return False

    def _configured_lint_project(self) -> str | None:
        raw = self._effective_value("general.project_folder", "")
        if not isinstance(raw, str) or not raw.strip():
            return None
        try:
            return self._canonical_path(raw.strip())
        except (OSError, ValueError):
            return None

    def _current_lint_project(self) -> str | None:
        """Return the active file's inferred project or standalone folder."""

        file_path, project = self._lint_target_paths()
        try:
            target = resolve_lint_target_root(file_path, project)
            return self._canonical_path(target) if target else None
        except (LintContextError, OSError, ValueError):
            return None

    def _trusted_lint_roots(self) -> list[str]:
        raw = self._effective_value("security.trusted_lint_roots", [])
        if not isinstance(raw, (list, tuple)):
            return []
        roots: list[str] = []
        for value in raw:
            if not isinstance(value, str) or not value.strip():
                continue
            try:
                root = self._canonical_path(value.strip())
            except (OSError, ValueError):
                continue
            if root not in roots:
                roots.append(root)
        return roots

    def _is_lint_path_trusted(self, path: str | Path) -> bool:
        return any(
            self._path_is_within(path, root)
            for root in self._trusted_lint_roots()
        )

    def _is_current_lint_project_trusted(self) -> bool:
        project = self._current_lint_project()
        return bool(project and self._is_lint_path_trusted(project))

    def _matching_lint_trust_boundary(
        self, trusted_roots: list[str] | tuple[str, ...]
    ) -> str | None:
        """Match the runtime's deepest trusted root for the current target."""
        file_path, project = self._lint_target_paths()
        try:
            effective_root = resolve_lint_target_root(file_path, project)
        except LintContextError:
            effective_root = None
        if not effective_root:
            return None

        matches = [
            root
            for root in trusted_roots
            if isinstance(root, str)
            and root.strip()
            and self._path_is_within(effective_root, root)
        ]
        if not matches:
            return None
        return max(matches, key=lambda root: len(Path(root).parts))

    def _trust_lint_project(self) -> None:
        project = self._current_lint_project()
        if not project or not Path(project).is_dir():
            QMessageBox.warning(
                self,
                "No Lint Target to Trust",
                "Open or save a Python file before granting lint trust.",
            )
            return
        if self._is_current_lint_project_trusted():
            return
        reply = QMessageBox.question(
            self,
            "Trust Target for Linting?",
            "A trusted target's linter configuration, local plugins, and "
            "Python environment may execute code. Trust this target only "
            "if you know where it came from.\n\n"
            f"Target: {project}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        roots = self._trusted_lint_roots()
        roots.append(project)
        self._stage("security.trusted_lint_roots", roots)
        self._refresh_lint_summary()

    def _revoke_lint_project(self) -> None:
        project = self._current_lint_project()
        if not project:
            return
        roots = [
            root
            for root in self._trusted_lint_roots()
            if not self._path_is_within(project, root)
        ]
        self._stage("security.trusted_lint_roots", roots)
        self._refresh_lint_summary()

    def _lint_target_paths(self) -> tuple[str | None, str | None]:
        """Return the active file and live project root when available."""
        window = self.parent()
        file_path = None
        tab_manager = getattr(window, "_tab_manager", None)
        current_editor = getattr(tab_manager, "current_editor", None)
        if callable(current_editor):
            editor = current_editor()
            file_path = getattr(editor, "file_path", None)

        explorer = getattr(window, "_file_explorer", None)
        project = getattr(explorer, "root_path", None)
        if not project:
            project = self._configured_lint_project()
        return (
            str(file_path) if file_path else None,
            str(project) if project else None,
        )

    def _resolve_pending_lint_context(
        self,
    ) -> tuple[LintExecutionContext | None, str | None]:
        """Resolve exactly what a lint run would use without saving changes."""
        validated, error = self._validate_pending_changes()
        if validated is None:
            return None, error

        window = self.parent()
        interpreter_manager = getattr(window, "_interpreter_manager", None)
        if interpreter_manager is None:
            interpreter_manager = InterpreterManager()
        file_path, project = self._lint_target_paths()
        try:
            context = resolve_lint_context(
                settings=_SettingsOverlay(self._settings, validated),
                interpreter_manager=interpreter_manager,
                linter=self._active_lint_provider,
                file_path=file_path,
                project_root=project,
            )
        except LintContextError as exc:
            return None, str(exc)
        return context, None

    def _effective_lint_config_path(self) -> str | None:
        context, _ = self._resolve_pending_lint_context()
        return context.config_path if context is not None else None

    def _refresh_lint_summary(self) -> None:
        """Update trust controls and the human-readable effective context."""
        if not hasattr(self, "_lint_effective_summary"):
            return
        project = self._current_lint_project()
        trusted = self._is_current_lint_project_trusted()
        project_exists = bool(project and Path(project).is_dir())
        if project:
            self._lint_project_label.setText(f"Current lint target: {project}")
            trust_text = "Trusted" if trusted else "Not trusted"
        else:
            self._lint_project_label.setText("Current lint target: None")
            trust_text = "No saved Python target"
        self._lint_trust_status_label.setText(f"Lint trust: {trust_text}")
        self._trust_lint_project_btn.setEnabled(project_exists and not trusted)
        self._revoke_lint_project_btn.setEnabled(project_exists and trusted)
        if trusted:
            self._lint_trust_notice.setText(
                "Interpreter, working-directory, and configuration choices "
                "are active for this target."
            )
        elif project_exists:
            self._lint_trust_notice.setText(
                "Trust this target to activate its interpreter, working "
                "directory, and configuration choices. Until then, linting "
                "uses MeadowPy's isolated defaults."
            )
        else:
            self._lint_trust_notice.setText(
                "Open or save a Python file to configure project-dependent "
                "lint settings."
            )
        self._lint_interpreter_mode_combo.setEnabled(trusted)
        self._lint_working_directory_combo.setEnabled(trusted)
        self._lint_config_mode_combo.setEnabled(trusted)
        self._update_lint_interpreter_controls()
        self._update_lint_config_controls()

        provider = self._active_lint_provider
        context, context_error = self._resolve_pending_lint_context()
        config_path = context.config_path if context is not None else None
        if context is None:
            interpreter_text = "Unavailable"
            cwd_text = "Unavailable"
            config_text = "Unavailable"
            timeout_text = "Unavailable"
            target_trust_text = "Unavailable"
        else:
            interpreter_text = context.interpreter
            cwd_text = context.cwd
            timeout_text = f"{context.timeout_seconds} seconds"
            target_trust_text = "Trusted" if context.trusted else "Safe fallback"
            if context.config_path:
                config_text = context.config_path
            elif context.isolated and not context.trusted:
                config_text = "Linter defaults (current target is not trusted)"
            elif context.config_mode == "auto":
                config_text = "Auto-detect (no project config found)"
            else:
                config_text = "Linter defaults only"

        summary = (
            f"Linter: {provider}\n"
            f"Interpreter: {interpreter_text}\n"
            f"Working directory: {cwd_text}\n"
            f"Configuration: {config_text}\n"
            f"Timeout: {timeout_text}\n"
            f"Current target: {target_trust_text}"
        )
        if context_error:
            summary += f"\nProblem: {context_error}"
        self._lint_effective_summary.setText(summary)
        self._open_effective_config_btn.setEnabled(config_path is not None)
        if self._lint_test_process is not None:
            if (
                context != self._lint_test_context
                or provider != self._lint_test_provider
            ):
                self._lint_test_stale = True
                self._lint_test_result.setText(
                    "Lint settings changed during the test. Test again before "
                    "applying them."
                )
        else:
            self._lint_test_result.clear()

    def _open_effective_lint_config(self) -> None:
        path = self._effective_lint_config_path()
        if not path:
            QMessageBox.information(
                self,
                "No Effective Configuration",
                "There is no trusted linter configuration file to open.",
            )
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
            QMessageBox.warning(
                self,
                "Could Not Open Configuration",
                f"MeadowPy could not open:\n{path}",
            )

    def _test_linter_settings(self) -> None:
        """Asynchronously verify the pending linter execution context."""
        if self._lint_test_process is not None:
            return
        context, error = self._resolve_pending_lint_context()
        if context is None:
            self._lint_test_result.setText(
                f"Test could not start: {error or 'invalid lint settings'}"
            )
            return

        provider = self._active_lint_provider
        try:
            program, arguments, cwd = build_linter_stdin_command(
                provider, context, smoke_test=True
            )
        except ValueError as exc:
            self._lint_test_result.setText(f"Test could not start: {exc}")
            return

        process = QProcess(self)
        process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )
        process.setProgram(program)
        process.setArguments(arguments)
        process.setWorkingDirectory(cwd)
        process.started.connect(self._write_lint_test_source)
        process.finished.connect(self._on_lint_test_finished)
        process.errorOccurred.connect(self._on_lint_test_error)
        self._lint_test_process = process
        self._lint_test_provider = provider
        self._lint_test_context = context
        self._lint_test_stale = False
        self._lint_test_timed_out = False
        self._test_linter_btn.setEnabled(False)
        self._lint_test_result.setText(
            f"Testing {provider} with the effective settings..."
        )
        self._lint_test_timer.start(context.timeout_seconds * 1000)
        process.start()

    def _write_lint_test_source(self) -> None:
        process = self._lint_test_process
        if process is None:
            return
        process.write(LINTER_TEST_SOURCE.encode("utf-8"))
        process.closeWriteChannel()

    @staticmethod
    def _lint_test_output(process: QProcess) -> str:
        return bytes(process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )

    def _on_lint_test_finished(
        self, exit_code: int, exit_status: QProcess.ExitStatus
    ) -> None:
        process = self._lint_test_process
        if process is None:
            return
        if self._lint_test_stale:
            self._lint_test_result.setText(
                "Test result discarded because lint settings changed. Test "
                "again before applying them."
            )
            self._finish_lint_test()
            return
        if not self._lint_test_timed_out:
            output = self._lint_test_output(process)
            detail = " ".join(output.split())[:500]
            provider = self._lint_test_provider or self._active_lint_provider
            if (
                exit_status == QProcess.ExitStatus.NormalExit
                and lint_test_exit_succeeded(provider, exit_code, output)
            ):
                findings = (
                    " The smoke source produced lint findings."
                    if detail
                    else ""
                )
                self._lint_test_result.setText(
                    f"Test passed: {provider} loaded the effective settings."
                    f"{findings}"
                )
            else:
                suffix = f": {detail}" if detail else ""
                self._lint_test_result.setText(
                    f"Test failed (exit code {exit_code}){suffix}"
                )
        self._finish_lint_test()

    def _on_lint_test_error(self, _error) -> None:
        process = self._lint_test_process
        if process is None:
            return
        if self._lint_test_stale:
            self._lint_test_result.setText(
                "Test result discarded because lint settings changed. Test "
                "again before applying them."
            )
            self._finish_lint_test()
            return
        if not self._lint_test_timed_out:
            output = self._lint_test_output(process)
            detail = " ".join(output.split())[:500] or process.errorString()
            self._lint_test_result.setText(f"Test failed: {detail}")
        self._finish_lint_test()

    def _on_lint_test_timeout(self) -> None:
        process = self._lint_test_process
        if process is None:
            return
        self._lint_test_timed_out = True
        if self._lint_test_stale:
            self._lint_test_result.setText(
                "Test result discarded because lint settings changed. Test "
                "again before applying them."
            )
        else:
            self._lint_test_result.setText(
                "Test timed out using the configured linter timeout."
            )
        process.kill()

    def _finish_lint_test(self) -> None:
        self._lint_test_timer.stop()
        self._test_linter_btn.setEnabled(True)
        process = self._lint_test_process
        self._lint_test_process = None
        self._lint_test_provider = None
        self._lint_test_context = None
        self._lint_test_stale = False
        if process is not None:
            process.deleteLater()

    def _validate_pending_changes(self) -> tuple[dict[str, Any] | None, str | None]:
        """Validate and normalize every staged value before persisting any."""
        changes = dict(self._pending_changes)

        def value(key: str, default=None):
            if key in changes:
                return changes[key]
            return self._settings.get(key, default)

        if "editor.linter" in changes and changes["editor.linter"] not in {
            "flake8",
            "pylint",
        }:
            return None, "Choose either Flake8 or Pylint as the linter."

        if "editor.lint_delay_ms" in changes:
            delay = changes["editor.lint_delay_ms"]
            if isinstance(delay, bool) or not isinstance(delay, int):
                return None, "Typing delay must be a whole number."
            if not 100 <= delay <= 5000:
                return None, "Typing delay must be between 100 and 5000 ms."

        if "editor.lint_interpreter_mode" in changes:
            if changes["editor.lint_interpreter_mode"] not in {
                "selected",
                "meadowpy",
                "custom",
            }:
                return None, "Choose a valid linter interpreter mode."

        if "editor.lint_working_directory" in changes:
            if changes["editor.lint_working_directory"] not in {
                "project",
                "file",
            }:
                return None, "Choose a valid linter working directory."

        interpreter_path_key = "editor.lint_interpreter_path"
        if interpreter_path_key in changes:
            raw_path = changes[interpreter_path_key]
            if not isinstance(raw_path, str):
                return None, "Custom interpreter path must be text."
            raw_path = raw_path.strip()
            if raw_path:
                try:
                    changes[interpreter_path_key] = self._canonical_path(raw_path)
                except (OSError, ValueError):
                    return None, "Custom interpreter path is invalid."
            else:
                changes[interpreter_path_key] = ""

        interpreter_changed = bool(
            {"editor.lint_interpreter_mode", interpreter_path_key} & changes.keys()
        )
        if interpreter_changed and value(
            "editor.lint_interpreter_mode", "selected"
        ) == "custom":
            raw_path = changes.get(
                interpreter_path_key,
                self._settings.get(interpreter_path_key, ""),
            )
            if not raw_path:
                return None, "Select a custom Python interpreter."
            try:
                interpreter = Path(self._canonical_path(raw_path))
            except (OSError, ValueError):
                return None, "Custom interpreter path is invalid."
            if not interpreter.is_file():
                return None, "The custom Python interpreter does not exist."
            changes[interpreter_path_key] = str(interpreter)

        trusted_key = "security.trusted_lint_roots"
        if trusted_key in changes:
            raw_roots = changes[trusted_key]
            if not isinstance(raw_roots, (list, tuple)):
                return None, "Trusted lint roots must be a list of folders."
            normalized_roots: list[str] = []
            for root in raw_roots:
                if not isinstance(root, str) or not root.strip():
                    return None, "Trusted lint roots contain an invalid folder."
                try:
                    normalized = self._canonical_path(root.strip())
                except (OSError, ValueError):
                    return None, "A trusted lint root is invalid."
                if normalized not in normalized_roots:
                    normalized_roots.append(normalized)
            changes[trusted_key] = normalized_roots

        selected_provider = value("editor.linter", "flake8")
        trusted_roots = changes.get(
            trusted_key, self._settings.get(trusted_key, [])
        )
        if not isinstance(trusted_roots, (list, tuple)):
            trusted_roots = []
        trust_boundary = self._matching_lint_trust_boundary(trusted_roots)

        for provider in ("flake8", "pylint"):
            mode_key = self._lint_provider_key(provider, "config_mode")
            path_key = self._lint_provider_key(provider, "config_path")
            timeout_key = self._lint_provider_key(provider, "timeout_seconds")

            if mode_key in changes and changes[mode_key] not in {
                "auto",
                "defaults",
                "explicit",
            }:
                return None, f"Choose a valid {provider.title()} config mode."

            if timeout_key in changes:
                timeout = changes[timeout_key]
                if isinstance(timeout, bool) or not isinstance(timeout, int):
                    return None, f"{provider.title()} timeout must be a whole number."
                if not 1 <= timeout <= 120:
                    return None, (
                        f"{provider.title()} timeout must be between 1 and "
                        "120 seconds."
                    )

            if path_key in changes:
                raw_path = changes[path_key]
                if not isinstance(raw_path, str):
                    return None, f"{provider.title()} config path must be text."
                raw_path = raw_path.strip()
                if raw_path:
                    try:
                        changes[path_key] = self._canonical_path(raw_path)
                    except (OSError, ValueError):
                        return None, f"{provider.title()} config path is invalid."
                else:
                    changes[path_key] = ""

            provider_changed = bool(
                {mode_key, path_key, timeout_key} & changes.keys()
            )
            linter_switched_here = (
                "editor.linter" in changes and selected_provider == provider
            )
            should_validate = provider_changed or linter_switched_here
            mode = value(mode_key, "defaults")
            if should_validate and mode == "explicit":
                raw_path = changes.get(
                    path_key, self._settings.get(path_key, "")
                )
                if not raw_path:
                    return None, f"Select a {provider.title()} config file."
                try:
                    config = Path(self._canonical_path(raw_path))
                except (OSError, ValueError):
                    return None, f"{provider.title()} config path is invalid."
                if not config.is_file():
                    return None, f"The {provider.title()} config file does not exist."
                if not trust_boundary or not self._path_is_within(
                    config, trust_boundary
                ):
                    return None, (
                        f"The {provider.title()} config must be inside the "
                        "current target's trusted project folder."
                    )
                changes[path_key] = str(config)

        return changes, None

    def _stage_restore_tabs(self, enabled: bool) -> None:
        """Remember that the startup restore preference was chosen by the user."""
        self._stage("general.restore_tabs_on_startup", enabled)
        self._stage("general.restore_tabs_on_startup_explicit", True)

    def _stage_font_family(self, font: QFont) -> None:
        """Stage the selected font family from the font combo."""
        family = font.family() or self._font_combo.currentText()
        if family:
            self._stage("editor.font_family", family)

    def _on_theme_changed(self, theme_name: str) -> None:
        """React to the theme combo: stage the change, toggle custom controls."""
        self._stage("editor.theme", theme_name)
        self._custom_theme_container.setVisible(theme_name == "custom")

    def _on_pick_accent(self) -> None:
        """Open the custom colour picker and stage the chosen accent."""
        from meadowpy.ui.dialogs.accent_color_picker import AccentColorPickerDialog

        current_hex = (
            self._pending_changes.get("editor.custom_theme.accent")
            or self._settings.get("editor.custom_theme.accent")
            or "#3B82F6"
        )
        dlg = AccentColorPickerDialog(current_hex, self)
        if dlg.exec() == AccentColorPickerDialog.DialogCode.Accepted:
            hex_value = dlg.selected_hex()
            self._stage("editor.custom_theme.accent", hex_value)
            self._refresh_accent_swatch(hex_value)

    def _refresh_accent_swatch(self, hex_value: str) -> None:
        """Paint the swatch with the given hex and update its label."""
        self._accent_swatch.setStyleSheet(
            "QLabel {"
            f"    background: {hex_value};"
            "    border: 1px solid #888;"
            "    border-radius: 4px;"
            "}"
        )
        self._accent_hex_label.setText(hex_value)

    def _apply(self) -> bool:
        """Validate and atomically apply pending changes to settings."""
        self._stage_font_family(self._font_combo.currentFont())
        validated, error = self._validate_pending_changes()
        if validated is None:
            QMessageBox.warning(
                self,
                "Invalid Preferences",
                error or "One or more preference values are invalid.",
            )
            return False

        changed_keys = tuple(validated)
        for key, value in validated.items():
            self._settings.set(key, value)
        self._settings.save()
        self._pending_changes.clear()
        if changed_keys:
            self.preferences_applied.emit(changed_keys)
        if hasattr(self, "_active_lint_provider"):
            self._load_lint_provider_controls(self._active_lint_provider)
            self._lint_interpreter_path.blockSignals(True)
            self._lint_interpreter_path.setText(
                str(
                    self._settings.get("editor.lint_interpreter_path", "")
                    or ""
                )
            )
            self._lint_interpreter_path.blockSignals(False)
            self._refresh_lint_summary()
        return True

    def _apply_and_close(self) -> None:
        if self._apply():
            self.accept()

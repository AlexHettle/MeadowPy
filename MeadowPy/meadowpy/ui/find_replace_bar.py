"""VS Code-style floating find/replace bar."""

from PyQt6.QtCore import QEvent, QPoint, Qt
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QVBoxLayout, QLineEdit,
    QPushButton, QLabel, QWidget,
)

from meadowpy.editor.code_editor import CodeEditor


class FindReplaceBar(QFrame):
    """VS Code-style floating find/replace bar."""

    MAX_WIDTH = 620
    EDGE_MARGIN = 15
    COMPACT_WIDTH = 520

    def __init__(self, main_window):
        super().__init__(main_window)
        self._window = main_window
        self._replace_visible = False
        self._compact_layout = False
        self._layout_initialized = False
        self._central_widget = main_window.centralWidget()
        self._setup_ui()
        if self._central_widget is not None:
            self._central_widget.installEventFilter(self)
        self.hide()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # --- Find row ---
        self._find_layout = QGridLayout()
        self._find_layout.setContentsMargins(0, 0, 0, 0)
        self._find_layout.setHorizontalSpacing(6)
        self._find_layout.setVerticalSpacing(6)

        self._find_input = QLineEdit()
        self._find_input.setPlaceholderText("Find")
        self._find_input.setClearButtonEnabled(True)
        self._find_input.setMinimumWidth(80)
        self._find_input.setMinimumHeight(30)
        self._find_input.textChanged.connect(self._on_find_text_changed)
        self._find_input.returnPressed.connect(self.find_next)

        self._case_btn = self._make_toggle("Aa", "Match Case")
        self._word_btn = self._make_toggle("W", "Match Whole Word")
        self._regex_btn = self._make_toggle(".*", "Use Regular Expression")

        self._match_label = QLabel("")
        self._match_label.setMinimumWidth(40)
        self._match_label.setMaximumWidth(75)
        self._match_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._prev_btn = self._make_nav_btn("\u25B2", "Previous Match (Shift+Enter)")
        self._prev_btn.clicked.connect(self.find_previous)

        self._next_btn = self._make_nav_btn("\u25BC", "Next Match (Enter)")
        self._next_btn.clicked.connect(self.find_next)

        self._close_btn = self._make_nav_btn("\u2715", "Close (Escape)")
        self._close_btn.clicked.connect(self.hide_bar)

        self._find_widgets = (
            self._find_input,
            self._case_btn,
            self._word_btn,
            self._regex_btn,
            self._match_label,
            self._prev_btn,
            self._next_btn,
            self._close_btn,
        )
        self._apply_find_layout(compact=False)
        layout.addLayout(self._find_layout)

        # --- Replace row (hidden by default) ---
        self._replace_row = QWidget()
        replace_layout = QHBoxLayout(self._replace_row)
        replace_layout.setContentsMargins(0, 0, 0, 0)
        replace_layout.setSpacing(6)

        self._replace_input = QLineEdit()
        self._replace_input.setPlaceholderText("Replace")
        self._replace_input.setToolTip("Type the replacement text here")
        self._replace_input.setClearButtonEnabled(True)
        self._replace_input.setMinimumHeight(30)

        self._replace_btn = QPushButton("Replace")
        self._replace_btn.setToolTip("Replace the current match")
        self._replace_btn.setMinimumHeight(30)
        self._replace_btn.clicked.connect(self.replace_current)

        self._replace_all_btn = QPushButton("Replace All")
        self._replace_all_btn.setToolTip("Replace every match in the file at once")
        self._replace_all_btn.setMinimumHeight(30)
        self._replace_all_btn.clicked.connect(self.replace_all)

        replace_layout.addWidget(self._replace_input, 1)
        replace_layout.addWidget(self._replace_btn)
        replace_layout.addWidget(self._replace_all_btn)

        self._replace_row.hide()
        layout.addWidget(self._replace_row)

        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAutoFillBackground(True)
        self.setObjectName("FindReplaceBar")

    def _make_toggle(self, text: str, tooltip: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setToolTip(tooltip)
        btn.setFixedSize(32, 30)
        btn.setObjectName("findToggleBtn")
        return btn

    def _make_nav_btn(self, text: str, tooltip: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setToolTip(tooltip)
        btn.setFixedSize(32, 30)
        return btn

    def toggle_find(self) -> None:
        """Show find bar (hide replace row). Focus the find input."""
        self._replace_row.hide()
        self._replace_visible = False
        self._show_and_focus()

    def toggle_replace(self) -> None:
        """Show find + replace bar. Focus the find input."""
        self._replace_row.show()
        self._replace_visible = True
        self._show_and_focus()

    def hide_bar(self) -> None:
        """Hide the bar and return focus to the editor."""
        self.hide()
        editor = self._window._tab_manager.current_editor()
        if editor:
            editor.setFocus()

    def find_next(self) -> None:
        """Find the next occurrence."""
        editor = self._get_editor()
        if not editor:
            return
        text = self._find_input.text()
        if not text:
            return

        if not editor.findFirst(
            text,
            self._regex_btn.isChecked(),
            self._case_btn.isChecked(),
            self._word_btn.isChecked(),
            True,   # wrap around
            True,   # forward
        ):
            self._match_label.setText("No results")
        else:
            self._match_label.setText("")

    def find_previous(self) -> None:
        """Find the previous occurrence."""
        editor = self._get_editor()
        if not editor:
            return
        text = self._find_input.text()
        if not text:
            return

        if not editor.findFirst(
            text,
            self._regex_btn.isChecked(),
            self._case_btn.isChecked(),
            self._word_btn.isChecked(),
            True,   # wrap around
            False,  # backward
        ):
            self._match_label.setText("No results")
        else:
            self._match_label.setText("")

    def replace_current(self) -> None:
        """Replace the current match and find the next one."""
        editor = self._get_editor()
        if editor and editor.hasSelectedText():
            editor.replace(self._replace_input.text())
            self.find_next()

    def replace_all(self) -> None:
        """Replace all occurrences."""
        editor = self._get_editor()
        if not editor:
            return
        text = self._find_input.text()
        replacement = self._replace_input.text()
        if not text:
            return

        count = 0
        found = editor.findFirst(
            text, self._regex_btn.isChecked(), self._case_btn.isChecked(),
            self._word_btn.isChecked(), False, True, 0, 0,
        )
        while found:
            editor.replace(replacement)
            count += 1
            found = editor.findNext()

        self._match_label.setText(f"{count} replaced")

    def _show_and_focus(self) -> None:
        # Pre-fill with selected text from editor
        editor = self._get_editor()
        if editor and editor.hasSelectedText():
            selected = editor.selectedText()
            if "\n" not in selected:
                self._find_input.setText(selected)

        self._reposition()
        self.show()
        self._find_input.setFocus()
        self._find_input.selectAll()

    def _reposition(self) -> None:
        """Position the bar at the top-right of the central widget."""
        parent = self._window.centralWidget()
        if parent:
            available_width = max(1, parent.width() - 2 * self.EDGE_MARGIN)
            bar_width = min(self.MAX_WIDTH, available_width)
            self._apply_find_layout(bar_width < self.COMPACT_WIDTH)
            self.setFixedWidth(bar_width)
            self.adjustSize()
            origin = parent.mapTo(self._window, QPoint(0, 0))
            x = origin.x() + parent.width() - bar_width - self.EDGE_MARGIN
            self.move(x, origin.y() + 5)
            self.raise_()

    def _apply_find_layout(self, compact: bool) -> None:
        """Use a second controls row when horizontal space is limited."""
        if self._layout_initialized and self._compact_layout == compact:
            return
        if hasattr(self, "_find_widgets"):
            for widget in self._find_widgets:
                self._find_layout.removeWidget(widget)
        for column in range(8):
            self._find_layout.setColumnStretch(column, 0)

        if compact:
            self._find_layout.addWidget(self._find_input, 0, 0, 1, 7)
            self._find_layout.addWidget(self._close_btn, 0, 7)
            self._find_layout.addWidget(self._case_btn, 1, 0)
            self._find_layout.addWidget(self._word_btn, 1, 1)
            self._find_layout.addWidget(self._regex_btn, 1, 2)
            self._find_layout.addWidget(self._match_label, 1, 3, 1, 3)
            self._find_layout.addWidget(self._prev_btn, 1, 6)
            self._find_layout.addWidget(self._next_btn, 1, 7)
            self._find_layout.setColumnStretch(3, 1)
        else:
            for column, widget in enumerate(self._find_widgets):
                self._find_layout.addWidget(widget, 0, column)
            self._find_layout.setColumnStretch(0, 1)
        self._compact_layout = compact
        self._layout_initialized = True

    def eventFilter(self, watched, event) -> bool:
        if (
            watched is self._central_widget
            and event.type() in {QEvent.Type.Resize, QEvent.Type.Move}
            and self.isVisible()
        ):
            self._reposition()
        return super().eventFilter(watched, event)

    def _on_find_text_changed(self, text: str) -> None:
        """Incremental search as the user types."""
        if text:
            self.find_next()
        else:
            self._match_label.setText("")

    def _get_editor(self) -> CodeEditor | None:
        return self._window._tab_manager.current_editor()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide_bar()
        elif (
            event.key() == Qt.Key.Key_Return
            and event.modifiers() == Qt.KeyboardModifier.ShiftModifier
        ):
            self.find_previous()
        else:
            super().keyPressEvent(event)

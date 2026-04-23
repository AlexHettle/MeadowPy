"""Core code editor widget based on QScintilla."""

from pathlib import Path

from PyQt6.QtCore import pyqtSignal, Qt, QEvent
from PyQt6.QtGui import QColor, QKeySequence
from PyQt6.QtWidgets import QToolTip
from PyQt6.Qsci import QsciScintilla

from meadowpy.core.settings import Settings
from meadowpy.editor.editor_config import EditorConfigurator
from meadowpy.editor.smart_indent import SmartIndentHandler
from meadowpy.editor.auto_close import AutoCloseHandler


# Marker IDs for gutter symbols
MARKER_BREAKPOINT = 0    # Red filled circle for breakpoints
MARKER_CURRENT_LINE = 1  # Yellow arrow for current execution line during debug

# Indicator IDs for squiggle underlines
# QScintilla reserves indicators 0-7 for lexer use and 8-10 internally
# (8 = INDIC_CONTAINER used by findFirst/brace matching), so start at 14.
INDICATOR_ERROR = 14
INDICATOR_WARNING = 15


class CodeEditor(QsciScintilla):
    """Enhanced QScintilla editor widget with Python-specific configuration."""

    modification_changed = pyqtSignal(bool)
    ai_explain_requested = pyqtSignal(str)  # selected code text
    ai_improve_requested = pyqtSignal(str)  # selected code text
    ai_docstring_requested = pyqtSignal(str, int)  # (func/class code, insert line 0-based)

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._file_path: str | None = None
        self._untitled_name: str = "Untitled"

        # Phase 2: Smart indent and auto-close handlers
        self._smart_indent = SmartIndentHandler(self, settings)
        self._auto_close = AutoCloseHandler(self, settings)

        # Lint issue storage for hover tooltips
        self._lint_issues: list = []

        # Breakpoint storage (0-based line numbers)
        self._breakpoints: set[int] = set()

        # Define the breakpoint marker: a red filled circle
        self.markerDefine(QsciScintilla.MarkerSymbol.Circle, MARKER_BREAKPOINT)
        self.setMarkerForegroundColor(QColor("#E51400"), MARKER_BREAKPOINT)
        self.setMarkerBackgroundColor(QColor("#E51400"), MARKER_BREAKPOINT)

        # Define the current-line marker: a yellow right-arrow
        self.markerDefine(QsciScintilla.MarkerSymbol.RightArrow, MARKER_CURRENT_LINE)
        self.setMarkerForegroundColor(QColor("#000000"), MARKER_CURRENT_LINE)
        self.setMarkerBackgroundColor(QColor("#FFCC00"), MARKER_CURRENT_LINE)

        EditorConfigurator.apply(self, settings)
        self._connect_signals()

        # QScintilla reserves Ctrl+/ for one of its own built-in commands
        # (a word-select variant that moves the caret slightly backwards).
        # Clear the built-in mapping so our ``keyPressEvent`` override,
        # which maps Ctrl+/ to ``toggle_comment``, actually wins.
        # Scintilla's SCI_CLEARCMDKEY expects a single int encoded as
        # ``keyCode | (modifiers << 16)`` using its own SCMOD_* flags:
        # SHIFT=1, CTRL=2, ALT=4.
        _SCMOD_CTRL = 2
        self.SendScintilla(
            QsciScintilla.SCI_CLEARCMDKEY,
            ord("/") | (_SCMOD_CTRL << 16),
        )

    def _connect_signals(self) -> None:
        self.modificationChanged.connect(self._on_modification_changed)
        self.linesChanged.connect(self._update_margin_width)
        self.marginClicked.connect(self._on_margin_clicked)

    @property
    def file_path(self) -> str | None:
        return self._file_path

    @file_path.setter
    def file_path(self, path: str | None) -> None:
        self._file_path = path

    @property
    def is_modified(self) -> bool:
        return self.isModified()

    @property
    def display_name(self) -> str:
        """Return the file name for tab display, or 'Untitled-N'."""
        if self._file_path:
            return Path(self._file_path).name
        return self._untitled_name

    def apply_settings(self, settings: Settings) -> None:
        """Re-apply settings (called when preferences change)."""
        self._settings = settings
        EditorConfigurator.apply(self, settings)

    # ── Comment / Uncomment ──────────────────────────────────────────

    def _selection_is_commented(self) -> bool:
        """Return True if every non-blank line in the current range is
        already commented at the common minimum indent.

        Used to pick the right context-menu label
        (``Comment`` vs ``Uncomment``).
        """
        if self.hasSelectedText():
            line_from, _, line_to, index_to = self.getSelection()
            if index_to == 0 and line_to > line_from:
                line_to -= 1
        else:
            line_from, _ = self.getCursorPosition()
            line_to = line_from

        texts = []
        for i in range(line_from, line_to + 1):
            raw = self.text(i).rstrip("\r\n")
            if raw.strip():
                texts.append(raw)
        if not texts:
            return False
        min_indent = min(len(t) - len(t.lstrip()) for t in texts)
        return all(t[min_indent:min_indent + 1] == "#" for t in texts)

    def toggle_comment(self) -> None:
        """Toggle a Python ``#`` comment on the selected lines.

        If no text is selected, operates on the line containing the
        cursor. If every non-blank line in the range is already commented
        (a ``#`` at the common minimum indent), the comment markers are
        removed; otherwise ``# `` is inserted at that indent.
        """
        # Determine the line range to operate on.
        if self.hasSelectedText():
            line_from, _, line_to, index_to = self.getSelection()
            # A selection that ends at column 0 of the next line shouldn't
            # include that trailing empty line.
            if index_to == 0 and line_to > line_from:
                line_to -= 1
        else:
            line_from, _ = self.getCursorPosition()
            line_to = line_from

        # Capture each line's text plus its original line terminator.
        lines: list[tuple[str, str]] = []
        for i in range(line_from, line_to + 1):
            raw = self.text(i)
            if raw.endswith("\r\n"):
                lines.append((raw[:-2], "\r\n"))
            elif raw.endswith("\n") or raw.endswith("\r"):
                lines.append((raw[:-1], raw[-1]))
            else:
                lines.append((raw, ""))

        nonblank = [t for t, _ in lines if t.strip()]
        if not nonblank:
            return

        # Common minimum indent across non-blank lines — where ``#`` goes.
        min_indent = min(len(t) - len(t.lstrip()) for t in nonblank)
        all_commented = all(
            t[min_indent:min_indent + 1] == "#" for t in nonblank
        )

        new_lines: list[str] = []
        for text, eol in lines:
            if not text.strip():
                new_lines.append(text + eol)
                continue
            if all_commented:
                pre = text[:min_indent]
                post = text[min_indent:]
                if post.startswith("# "):
                    post = post[2:]
                elif post.startswith("#"):
                    post = post[1:]
                new_lines.append(pre + post + eol)
            else:
                new_lines.append(
                    text[:min_indent] + "# " + text[min_indent:] + eol
                )

        new_text = "".join(new_lines)

        # Replace the full line range as a single undoable edit.
        last_line_text, _ = lines[-1]
        self.beginUndoAction()
        try:
            self.setSelection(line_from, 0, line_to, len(last_line_text))
            self.replaceSelectedText(new_text)
        finally:
            self.endUndoAction()

        # Restore a line-range selection on the transformed block so the
        # user can repeat Ctrl+/ to undo/flip it.
        # Recompute the last line's length post-edit.
        new_last_len = len(self.text(line_to).rstrip("\r\n"))
        self.setSelection(line_from, 0, line_to, new_last_len)

    def _on_modification_changed(self, modified: bool) -> None:
        self.modification_changed.emit(modified)

    # --- Keyboard event override for smart indent + auto-close ---

    def keyPressEvent(self, event) -> None:
        """Override to handle smart indent and auto-close."""
        # Ctrl+/ → toggle comment (intercept before Scintilla / super)
        if (
            event.key() == Qt.Key.Key_Slash
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.toggle_comment()
            return

        # Smart indent on Enter
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._smart_indent.handle_return():
                return

        # Auto-close bracket deletion on Backspace
        if event.key() == Qt.Key.Key_Backspace:
            if self._auto_close.handle_backspace():
                return

        # Auto-close on character input (must be before super)
        if event.text() and self._auto_close.handle_key(event):
            return

        super().keyPressEvent(event)

    # --- Hover tooltip for lint issues ---

    def event(self, e) -> bool:
        """Show lint issue tooltip when hovering over squiggle-underlined code."""
        if e.type() == QEvent.Type.ToolTip:
            pos = self.SendScintilla(
                2023, e.pos().x(), e.pos().y()  # SCI_POSITIONFROMPOINTCLOSE
            )
            if pos >= 0:
                line, col = self.lineIndexFromPosition(pos)
                tooltip = self._get_lint_tooltip(line, col)
                if tooltip:
                    QToolTip.showText(e.globalPos(), tooltip, self)
                    return True
            QToolTip.hideText()
            return True
        return super().event(e)

    def _get_lint_tooltip(self, line: int, col: int) -> str | None:
        """Return tooltip text for any lint issue covering (line, col)."""
        parts = []
        for issue in self._lint_issues:
            if issue.line != line:
                continue
            # Squiggle runs from issue.column to end of line
            line_text = self.text(line)
            line_length = len(line_text.rstrip("\n\r"))
            col_start = min(max(issue.column, 0), max(line_length - 1, 0))
            if col_start <= col < line_length:
                parts.append(f"{issue.code}: {issue.message}")
        return "\n".join(parts) if parts else None

    # --- Zoom methods (override to update margin width) ---

    def zoomIn(self, range_=1) -> None:
        super().zoomIn(range_)
        self._update_margin_width()

    def zoomOut(self, range_=1) -> None:
        super().zoomOut(range_)
        self._update_margin_width()

    def zoomTo(self, size) -> None:
        super().zoomTo(size)
        self._update_margin_width()

    def wheelEvent(self, event) -> None:
        super().wheelEvent(event)
        # Ctrl+wheel triggers zoom inside Scintilla
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._update_margin_width()

    # ── Drag & Drop (forward file URLs to main window) ───────────
    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            # Forward to the main window's dropEvent
            event.ignore()
            self.window().dropEvent(event)
        else:
            super().dropEvent(event)

    # ── Context menu with "What does this mean?" ─────────────────

    def contextMenuEvent(self, event) -> None:
        """Add 'What does this mean?' to the right-click context menu."""
        from PyQt6.QtWidgets import QMenu

        menu = self.createStandardContextMenu()

        # Get the word under the cursor at the click position
        pos = self.SendScintilla(
            2023, event.pos().x(), event.pos().y()  # SCI_POSITIONFROMPOINTCLOSE
        )
        word = ""
        if pos >= 0:
            word = self.wordAtLineIndex(
                *self.lineIndexFromPosition(pos)
            )

        # Comment / Uncomment toggle (always available)
        menu.addSeparator()
        toggle_label = (
            "Uncomment Selection" if self._selection_is_commented()
            else "Comment Selection"
        )
        if not self.hasSelectedText():
            # Match VS Code / Sublime wording when there's no selection
            toggle_label = toggle_label.replace("Selection", "Line")
        toggle_action = menu.addAction(toggle_label)
        toggle_action.setShortcut(QKeySequence("Ctrl+/"))
        toggle_action.triggered.connect(self.toggle_comment)

        if word:
            from meadowpy.resources.keyword_help import KEYWORD_HELP
            if word in KEYWORD_HELP:
                menu.addSeparator()
                action = menu.addAction(f'What does "{word}" mean?')
                action.triggered.connect(lambda: self._show_keyword_help(word, event.globalPos()))

        # AI-powered actions when text is selected
        if self.hasSelectedText():
            selected = self.selectedText().strip()
            if selected:
                menu.addSeparator()
                explain_action = menu.addAction("Explain this code...")
                explain_action.setToolTip(
                    "Ask the AI to explain the selected code"
                )
                explain_action.triggered.connect(
                    lambda: self.ai_explain_requested.emit(selected)
                )

                improve_action = menu.addAction("Review && improve...")
                improve_action.setToolTip(
                    "Ask the AI to review the selected code and suggest improvements"
                )
                improve_action.triggered.connect(
                    lambda: self.ai_improve_requested.emit(selected)
                )

        # "Generate docstring..." when cursor is inside a def/class
        click_line = self.lineIndexFromPosition(pos)[0] if pos >= 0 else -1
        func_info = self._find_enclosing_def(click_line)
        if func_info:
            func_code, insert_line = func_info
            if not self.hasSelectedText():
                menu.addSeparator()
            docstring_action = menu.addAction("Generate docstring...")
            docstring_action.setToolTip(
                "Ask the AI to generate a docstring for this function or class"
            )
            docstring_action.triggered.connect(
                lambda: self.ai_docstring_requested.emit(
                    func_code, insert_line
                )
            )

        menu.exec(event.globalPos())

    def _show_keyword_help(self, word: str, pos) -> None:
        """Show the keyword help popup at the given screen position."""
        from meadowpy.resources.keyword_help import KEYWORD_HELP
        from meadowpy.ui.keyword_help_popup import KeywordHelpPopup

        info = KEYWORD_HELP.get(word)
        if not info:
            return

        popup = KeywordHelpPopup(
            word, info["explanation"], info["example"], parent=self
        )
        popup.move(pos)
        popup.show()

    def _find_enclosing_def(self, line: int) -> tuple[str, int] | None:
        """Find the enclosing def/class for the given 0-based line.

        Returns ``(function_or_class_code, insert_line)`` where
        *insert_line* is the 0-based line right after the ``def``/``class``
        signature (where the docstring should go).  Returns *None* if
        no enclosing definition is found.
        """
        import re as _re

        if line < 0:
            return None

        # Scan upward to find the nearest def/class line at the same or
        # lower indentation level.
        def_re = _re.compile(r"^(\s*)(def |class )")
        def_line = -1
        def_indent = 0
        for i in range(line, -1, -1):
            text = self.text(i)
            m = def_re.match(text)
            if m:
                def_line = i
                def_indent = len(m.group(1))
                break

        if def_line < 0:
            return None

        # Collect the full function/class body (lines with deeper indent
        # or blank lines, up to 30 lines for a reasonable prompt).
        total_lines = self.lines()
        body_lines = [self.text(def_line).rstrip("\n\r")]
        insert_line = def_line + 1

        # Handle multi-line signatures (lines ending with \ or unclosed paren)
        while insert_line < total_lines:
            prev = body_lines[-1]
            if prev.rstrip().endswith("\\") or prev.count("(") > prev.count(")"):
                body_lines.append(self.text(insert_line).rstrip("\n\r"))
                insert_line += 1
            else:
                break

        # Collect body lines (indented deeper than the def)
        max_body = 30
        collected = 0
        for i in range(insert_line, min(total_lines, insert_line + max_body)):
            text = self.text(i)
            stripped = text.lstrip()
            if stripped == "":
                body_lines.append("")
                collected += 1
                continue
            indent = len(text) - len(stripped)
            if indent <= def_indent:
                break  # exited the function/class body
            body_lines.append(text.rstrip("\n\r"))
            collected += 1

        func_code = "\n".join(body_lines)
        return (func_code, insert_line)

    def _update_margin_width(self) -> None:
        """Dynamically adjust line number margin width based on line count."""
        if self._settings.get("editor.show_line_numbers"):
            line_count = self.lines()
            width = max(len(str(line_count)) + 1, 4)
            self.setMarginWidth(0, "0" * width)

    # --- Breakpoint methods ---

    def _on_margin_clicked(self, margin: int, line: int, state) -> None:
        """Handle clicks on the breakpoint margin (2) or line number margin (0)."""
        if margin in (0, 2):
            self.toggle_breakpoint(line)

    def toggle_breakpoint(self, line: int) -> None:
        """Toggle a breakpoint on the given 0-based line number."""
        if line in self._breakpoints:
            self._breakpoints.discard(line)
            self.markerDelete(line, MARKER_BREAKPOINT)
        else:
            self._breakpoints.add(line)
            self.markerAdd(line, MARKER_BREAKPOINT)

    def get_breakpoints(self) -> set[int]:
        """Return the set of 0-based line numbers with breakpoints."""
        return self._breakpoints.copy()

    def clear_breakpoints(self) -> None:
        """Remove all breakpoint markers."""
        self._breakpoints.clear()
        self.markerDeleteAll(MARKER_BREAKPOINT)

    # --- Debug current-line methods ---

    def set_current_line(self, line: int) -> None:
        """Show the yellow current-execution-line arrow (0-based)."""
        self.clear_current_line()
        self.markerAdd(line, MARKER_CURRENT_LINE)
        self.ensureLineVisible(line)
        self.setCursorPosition(line, 0)

    def clear_current_line(self) -> None:
        """Remove the current-execution-line arrow."""
        self.markerDeleteAll(MARKER_CURRENT_LINE)

    # --- Lint marker methods ---

    def set_lint_issues(self, issues: list) -> None:
        """Apply gutter markers and squiggle underlines for lint issues."""
        self.clear_lint_markers()
        self._lint_issues = issues

        # Scintilla message IDs
        SCI_INDICSETSTYLE = 2080
        SCI_INDICSETFORE = 2082
        SCI_SETINDICATORCURRENT = 2500
        SCI_INDICATORFILLRANGE = 2504
        INDIC_SQUIGGLE = 1

        # (Re-)define squiggle indicators via Scintilla API directly.
        # QScintilla's wrapper can silently fail for certain indicator IDs,
        # so we bypass it to guarantee the styles are set.
        for ind_id, bgr_color in (
            (INDICATOR_ERROR, 0x0014E5),    # #E51400 in BGR
            (INDICATOR_WARNING, 0x4EADF0),  # #F0AD4E in BGR
        ):
            self.SendScintilla(SCI_INDICSETSTYLE, ind_id, INDIC_SQUIGGLE)
            self.SendScintilla(SCI_INDICSETFORE, ind_id, bgr_color)

        for issue in issues:
            if issue.severity == "error":
                indicator = INDICATOR_ERROR
            else:
                indicator = INDICATOR_WARNING

            # Squiggle underline from issue column to end of line
            line_text = self.text(issue.line)
            line_length = len(line_text.rstrip("\n\r"))
            if line_length > 0:
                col_start = min(max(issue.column, 0), line_length - 1)
                start_pos = self.positionFromLineIndex(issue.line, col_start)
                end_pos = self.positionFromLineIndex(issue.line, line_length)
                if end_pos > start_pos:
                    self.SendScintilla(SCI_SETINDICATORCURRENT, indicator)
                    self.SendScintilla(
                        SCI_INDICATORFILLRANGE, start_pos, end_pos - start_pos
                    )

    def clear_lint_markers(self) -> None:
        """Remove all lint markers and squiggle underlines."""
        self._lint_issues = []
        # Clear all squiggle indicators across the entire document
        SCI_SETINDICATORCURRENT = 2500
        SCI_INDICATORCLEARRANGE = 2505
        doc_length = self.length()
        if doc_length > 0:
            for indicator in (INDICATOR_ERROR, INDICATOR_WARNING):
                self.SendScintilla(SCI_SETINDICATORCURRENT, indicator)
                self.SendScintilla(SCI_INDICATORCLEARRANGE, 0, doc_length)

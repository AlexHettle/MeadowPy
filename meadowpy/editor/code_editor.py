"""Core code editor widget based on QScintilla."""

import ast
from pathlib import Path

from PyQt6.QtCore import pyqtSignal, Qt, QEvent, QRectF
from PyQt6.QtGui import (
    QColor,
    QKeySequence,
    QPainter,
    QPen,
    QBrush,
    QPixmap,
    QLinearGradient,
    QPainterPath,
)
from PyQt6.QtWidgets import QToolTip, QWidget
from PyQt6.Qsci import QsciScintilla

from meadowpy.core.file_types import (
    is_python_file_path,
    syntax_language_for_path,
)
from meadowpy.core.settings import Settings
from meadowpy.core.shortcuts import event_matches_shortcut, get_shortcut
from meadowpy.editor.editor_config import EditorConfigurator
from meadowpy.editor.smart_indent import SmartIndentHandler
from meadowpy.editor.auto_close import AutoCloseHandler
from meadowpy.resources.resource_loader import theme_is_dark


# Marker IDs for gutter symbols
MARKER_BREAKPOINT = 0    # Red filled circle for breakpoints
MARKER_CURRENT_LINE = 1  # Yellow arrow for current execution line during debug
MARKER_PHANTOM_BREAKPOINT = 2  # Muted circle shown while hovering the gutter
BREAKPOINT_MARGIN_WIDTH = 26
BREAKPOINT_MARKER_SIZE = 18

# Indicator IDs for squiggle underlines
# QScintilla reserves indicators 0-7 for lexer use and 8-10 internally
# (8 = INDIC_CONTAINER used by findFirst/brace matching), so start at 14.
INDICATOR_ERROR = 14
INDICATOR_WARNING = 15


class _IndentGuideOverlay(QWidget):
    """Transparent overlay that paints solid editor indentation guides."""

    def __init__(self, editor: "CodeEditor"):
        super().__init__(editor)
        self._editor = editor
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        try:
            self._editor._draw_indentation_guides(painter)
        finally:
            painter.end()


class CodeEditor(QsciScintilla):
    """Enhanced QScintilla editor widget with Python-specific configuration."""

    modification_changed = pyqtSignal(bool)
    ai_explain_requested = pyqtSignal(str)  # selected code text
    ai_improve_requested = pyqtSignal(str)  # selected code text
    ai_docstring_requested = pyqtSignal(str, int)  # (func/class code, insert line 0-based)

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.setObjectName("codeEditor")
        self._settings = settings
        self._file_path: str | None = None
        self._untitled_name: str = "Untitled"
        self.large_file_mode = False

        # Phase 2: Smart indent and auto-close handlers
        self._smart_indent = SmartIndentHandler(self, settings)
        self._auto_close = AutoCloseHandler(self, settings)

        # Lint issue storage for hover tooltips
        self._lint_issues: list = []

        # Breakpoint storage (0-based line numbers)
        self._breakpoints: set[int] = set()
        self._phantom_breakpoint_line: int | None = None
        self.setMouseTracking(True)

        # Define gutter marker shapes; colors are applied separately so they
        # can be refreshed when the theme changes.
        self.markerDefine(QsciScintilla.MarkerSymbol.RightArrow, MARKER_CURRENT_LINE)
        self._apply_marker_colors()

        EditorConfigurator.apply(self, settings)
        self._indent_guide_overlay = _IndentGuideOverlay(self)
        self._indent_guide_overlay.setGeometry(self.rect())
        self._indent_guide_overlay.raise_()
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
        self.linesChanged.connect(self._indent_guide_overlay.update)
        self.textChanged.connect(self._indent_guide_overlay.update)
        self.textChanged.connect(self._clear_phantom_breakpoint)
        self.marginClicked.connect(self._on_margin_clicked)

    @property
    def file_path(self) -> str | None:
        return self._file_path

    @file_path.setter
    def file_path(self, path: str | None) -> None:
        old_editor_mode = (
            syntax_language_for_path(self._file_path),
            is_python_file_path(self._file_path),
        )
        self._file_path = path
        new_editor_mode = (
            syntax_language_for_path(path),
            is_python_file_path(path),
        )
        if old_editor_mode != new_editor_mode:
            EditorConfigurator.apply(self, self._settings)
            overlay = getattr(self, "_indent_guide_overlay", None)
            if overlay is not None:
                overlay.update()
        if not self._breakpoints_supported():
            self.clear_breakpoints()

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
        self._indent_guide_overlay.update()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        """Keep the transparent indentation guide overlay in sync."""
        super().paintEvent(event)
        overlay = getattr(self, "_indent_guide_overlay", None)
        if overlay is not None:
            overlay.setGeometry(self.rect())
            overlay.raise_()
            overlay.update()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        overlay = getattr(self, "_indent_guide_overlay", None)
        if overlay is not None:
            overlay.setGeometry(self.rect())
            overlay.update()

    @staticmethod
    def _indent_columns(text: str, tab_width: int) -> int:
        """Return leading indentation width in visual columns."""
        columns = 0
        tab_width = max(tab_width, 1)
        for char in text:
            if char == " ":
                columns += 1
            elif char == "\t":
                columns += tab_width - (columns % tab_width)
            else:
                break
        return columns

    def _effective_guide_indent_columns(self, line: int, tab_width: int) -> int:
        """Return the indent width to paint, borrowing from blank lines."""
        text = self.text(line).rstrip("\r\n")
        if text.strip():
            return self._indent_columns(text, tab_width)

        for probe in range(line - 1, -1, -1):
            previous = self.text(probe).rstrip("\r\n")
            if previous.strip():
                return self._indent_columns(previous, tab_width)
        return 0

    def _draw_indentation_guides(self, painter: QPainter) -> None:
        """Draw solid indentation guides for the visible editor lines."""
        if not self._settings.get("editor.show_indentation_guides"):
            return

        tab_width = int(self._settings.get("editor.tab_width") or 4)
        if tab_width <= 0:
            return

        theme_name = self._settings.get("editor.theme")
        custom_base = self._settings.get("editor.custom_theme.base")
        if theme_name == "default_high_contrast":
            guide_color = QColor("#FFFFFF")
        elif theme_is_dark(theme_name, custom_base):
            guide_color = QColor("#565E66")
        else:
            guide_color = QColor("#B8C0C8")

        first_line, last_line = self._visible_document_line_range()
        if last_line <= first_line:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        pen = QPen(guide_color)
        pen.setWidth(1)
        pen.setCosmetic(True)
        painter.setPen(pen)

        segments: dict[tuple[int, int], list[tuple[int, int]]] = {}
        for line in range(first_line, last_line):
            indent_columns = self._effective_guide_indent_columns(line, tab_width)
            if indent_columns < tab_width:
                continue

            y_top = self._line_y(line)
            line_height = self._line_height(line)
            if y_top + line_height < 0 or y_top > self.height():
                continue

            for column in range(tab_width, indent_columns + 1, tab_width):
                x = self._guide_column_x(line, column)
                if 0 <= x <= self.width():
                    segments.setdefault((column, x), []).append(
                        (y_top - 1, y_top + line_height + 1)
                    )

        for (_column, x), line_segments in segments.items():
            for top, bottom in self._merge_line_segments(line_segments):
                painter.drawLine(x, top, x, bottom)

    def _visible_document_line_range(self) -> tuple[int, int]:
        """Return the physical document lines currently worth painting."""
        try:
            first_line = self.firstVisibleLine()
        except AttributeError:
            first_line = 0

        try:
            lines_on_screen = int(self.SendScintilla(2370))  # SCI_LINESONSCREEN
        except (TypeError, RuntimeError):
            lines_on_screen = max(self.height() // max(self.fontMetrics().height(), 1), 1)

        last_line = min(self.lines(), first_line + lines_on_screen + 2)
        return max(first_line, 0), max(last_line, 0)

    def _guide_column_x(self, line: int, column: int) -> int:
        """Return the x-coordinate for a visual column on a document line."""
        try:
            pos = int(self.SendScintilla(2456, line, column))  # SCI_FINDCOLUMN
        except (TypeError, RuntimeError):
            pos = self.positionFromLineIndex(line, min(column, len(self.text(line))))
        return int(self.SendScintilla(2164, 0, pos))  # SCI_POINTXFROMPOSITION

    def _line_y(self, line: int) -> int:
        """Return the y-coordinate for the top of a document line."""
        pos = self.positionFromLineIndex(line, 0)
        return int(self.SendScintilla(2165, 0, pos))  # SCI_POINTYFROMPOSITION

    def _line_height(self, line: int) -> int:
        """Return the rendered height for a document line."""
        try:
            return int(self.SendScintilla(2279, line))  # SCI_TEXTHEIGHT
        except (TypeError, RuntimeError):
            return self.fontMetrics().height()

    @staticmethod
    def _merge_line_segments(
        segments: list[tuple[int, int]]
    ) -> list[tuple[int, int]]:
        """Merge adjacent vertical line fragments into continuous strokes."""
        if not segments:
            return []

        merged: list[tuple[int, int]] = []
        start, end = sorted(segments)[0]
        for next_start, next_end in sorted(segments)[1:]:
            if next_start <= end + 1:
                end = max(end, next_end)
            else:
                merged.append((start, end))
                start, end = next_start, next_end
        merged.append((start, end))
        return merged

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
        if not self._breakpoints_supported():
            return

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
        for index, (text, eol) in enumerate(lines):
            # QScintilla line selections stop before the final line
            # terminator. Keep separators between selected lines, but do not
            # insert an extra newline before the editor's existing terminator.
            replacement_eol = "" if index == len(lines) - 1 else eol
            if not text.strip():
                new_lines.append(text + replacement_eol)
                continue
            if all_commented:
                pre = text[:min_indent]
                post = text[min_indent:]
                if post.startswith("# "):
                    post = post[2:]
                elif post.startswith("#"):
                    post = post[1:]
                new_lines.append(pre + post + replacement_eol)
            else:
                new_lines.append(
                    text[:min_indent] + "# " + text[min_indent:] + replacement_eol
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
        # Toggle comment shortcut (intercept before Scintilla / super)
        if (
            event_matches_shortcut(
                event,
                get_shortcut(self._settings, "edit.toggle_comment"),
            )
        ):
            if self._breakpoints_supported():
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

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        self._update_phantom_breakpoint(event.pos().x(), event.pos().y())
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._clear_phantom_breakpoint()
        super().leaveEvent(event)

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

        python_mode = self._breakpoints_supported()

        if python_mode:
            menu.addSeparator()
            toggle_label = (
                "Uncomment Selection" if self._selection_is_commented()
                else "Comment Selection"
            )
            if not self.hasSelectedText():
                # Match VS Code / Sublime wording when there's no selection
                toggle_label = toggle_label.replace("Selection", "Line")
            toggle_action = menu.addAction(toggle_label)
            shortcut = get_shortcut(
                getattr(self, "_settings", None),
                "edit.toggle_comment",
            )
            if shortcut:
                toggle_action.setShortcut(QKeySequence(shortcut))
            toggle_action.triggered.connect(self.toggle_comment)

        if word and python_mode:
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
                explain_label = (
                    "Explain this code..." if python_mode else "Explain this text..."
                )
                explain_action = menu.addAction(explain_label)
                explain_action.setToolTip(
                    "Ask the AI to explain the selected "
                    + ("code" if python_mode else "text")
                )
                explain_action.triggered.connect(
                    lambda: self.ai_explain_requested.emit(selected)
                )

                if python_mode:
                    improve_action = menu.addAction("Review && improve...")
                    improve_action.setToolTip(
                        "Ask the AI to review the selected code and suggest improvements"
                    )
                    improve_action.triggered.connect(
                        lambda: self.ai_improve_requested.emit(selected)
                    )

        # "Generate docstring..." when cursor is inside a def/class
        click_line = self.lineIndexFromPosition(pos)[0] if pos >= 0 else -1
        func_info = (
            self._find_enclosing_def(click_line)
            if python_mode
            else None
        )
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
        if not self._breakpoints_supported():
            return

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

    # --- Marker color theming ---

    @staticmethod
    def _breakpoint_marker_pixmap(
        fill: QColor,
        border: QColor,
        *,
        filled: bool,
    ) -> QPixmap:
        """Return an antialiased breakpoint marker pixmap for the gutter."""
        size = BREAKPOINT_MARKER_SIZE
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            if filled:
                outer = QRectF(3.0, 3.0, 12.0, 12.0)
                inner_edge = outer.adjusted(0.55, 0.55, -0.55, -0.55)
                clip = QPainterPath()
                clip.addEllipse(outer)
                painter.setClipPath(clip)

                painter.setPen(Qt.PenStyle.NoPen)
                gradient = QLinearGradient(0, outer.top(), 0, outer.bottom())
                gradient.setColorAt(0.0, fill.lighter(112))
                gradient.setColorAt(1.0, fill.darker(106))
                painter.setBrush(QBrush(gradient))
                painter.drawEllipse(outer)

                painter.setPen(QPen(border, 1.0))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(inner_edge)
                painter.setClipping(False)
            else:
                ghost_fill = QColor(fill)
                ghost_fill.setAlpha(22)
                ghost_border = QColor(border)
                ghost_border.setAlpha(155)
                outer = QRectF(3.0, 3.0, 12.0, 12.0)
                inner_edge = outer.adjusted(0.7, 0.7, -0.7, -0.7)
                clip = QPainterPath()
                clip.addEllipse(outer)
                painter.setClipPath(clip)

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(ghost_fill))
                painter.drawEllipse(outer)

                painter.setPen(QPen(ghost_border, 1.45))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(inner_edge)
                painter.setClipping(False)
        finally:
            painter.end()

        return pixmap

    def _define_breakpoint_markers(self) -> None:
        """Install custom breakpoint marker artwork for the current theme."""
        is_hc = self._settings.get("editor.theme") == "default_high_contrast"
        theme_name = self._settings.get("editor.theme")
        custom_base = self._settings.get("editor.custom_theme.base")
        is_dark = theme_is_dark(theme_name, custom_base)

        if is_hc:
            bp_fill = QColor("#FFFFFF")
            bp_border = QColor("#FFFFFF")
            ghost_fill = QColor("#FFFFFF")
            ghost_border = QColor("#FFFFFF")
        else:
            bp_fill = QColor("#E9483F")
            bp_border = QColor("#9E2F2B" if is_dark else "#B8322E")
            ghost_fill = QColor("#E9483F")
            ghost_border = QColor("#E9483F")

        self.markerDefine(
            self._breakpoint_marker_pixmap(
                bp_fill,
                bp_border,
                filled=True,
            ),
            MARKER_BREAKPOINT,
        )
        self.markerDefine(
            self._breakpoint_marker_pixmap(
                ghost_fill,
                ghost_border,
                filled=False,
            ),
            MARKER_PHANTOM_BREAKPOINT,
        )

    def _apply_marker_colors(self) -> None:
        """Set breakpoint / current-line marker colors for the active theme.

        High-contrast collapses both markers onto pure black & white so the
        gutter stays monochrome alongside everything else.
        """
        self._define_breakpoint_markers()
        is_hc = self._settings.get("editor.theme") == "default_high_contrast"
        if is_hc:
            bp_color = QColor("#FFFFFF")
            cur_fg = QColor("#000000")
            cur_bg = QColor("#FFFFFF")
        else:
            bp_color = QColor("#E9483F")
            cur_fg = QColor("#000000")
            cur_bg = QColor("#FFCC00")
            theme_name = self._settings.get("editor.theme")
            custom_base = self._settings.get("editor.custom_theme.base")
            phantom_color = QColor(
                "#6F7780" if theme_is_dark(theme_name, custom_base) else "#9AA3AD"
            )
        if is_hc:
            phantom_color = QColor("#808080")
        self.setMarkerForegroundColor(bp_color, MARKER_BREAKPOINT)
        self.setMarkerBackgroundColor(bp_color, MARKER_BREAKPOINT)
        self.setMarkerForegroundColor(cur_fg, MARKER_CURRENT_LINE)
        self.setMarkerBackgroundColor(cur_bg, MARKER_CURRENT_LINE)
        self.setMarkerForegroundColor(
            phantom_color, MARKER_PHANTOM_BREAKPOINT
        )
        self.setMarkerBackgroundColor(
            phantom_color, MARKER_PHANTOM_BREAKPOINT
        )

    def refresh_marker_colors(self) -> None:
        """Re-apply breakpoint / current-line marker colors after a theme change."""
        self._apply_marker_colors()

    # --- Breakpoint methods ---

    def _breakpoint_lines_from_markers(self) -> set[int]:
        """Return breakpoint line numbers from Scintilla's marker state."""
        marker_mask = 1 << MARKER_BREAKPOINT
        return {
            line
            for line in range(self.lines())
            if self.markersAtLine(line) & marker_mask
        }

    def _has_breakpoint_marker(self, line: int) -> bool:
        """Return True if the given line currently has a breakpoint marker."""
        if line < 0 or line >= self.lines():
            return False
        return bool(self.markersAtLine(line) & (1 << MARKER_BREAKPOINT))

    def _sync_breakpoints_from_markers(self) -> None:
        """Keep cached breakpoint lines aligned with movable editor markers."""
        self._breakpoints = self._breakpoint_lines_from_markers()

    def _breakpoints_supported(self) -> bool:
        """Return True when this tab can display debugger breakpoints."""
        return is_python_file_path(self._file_path)

    def _breakpoint_hover_margin_at_x(self, x: int) -> bool:
        """Return True when x is over a margin that toggles breakpoints."""
        line_number_width = int(self.marginWidth(0) or 0)
        fold_width = int(self.marginWidth(1) or 0)
        breakpoint_width = int(self.marginWidth(2) or 0)

        if 0 <= x < line_number_width:
            return True

        breakpoint_start = line_number_width + fold_width
        breakpoint_end = breakpoint_start + breakpoint_width
        return breakpoint_start <= x < breakpoint_end

    def _line_from_mouse_y(self, y: int) -> int | None:
        """Resolve a widget y-coordinate to a document line."""
        lookup_x = sum(int(self.marginWidth(i) or 0) for i in range(5)) + 1
        pos = self.SendScintilla(2022, lookup_x, y)  # SCI_POSITIONFROMPOINT
        if pos < 0:
            return None

        line, _column = self.lineIndexFromPosition(pos)
        if line < 0 or line >= self.lines():
            return None
        return line

    def _set_phantom_breakpoint(self, line: int | None) -> None:
        """Move or hide the hover-only breakpoint marker."""
        if self._phantom_breakpoint_line == line:
            return

        self._clear_phantom_breakpoint()
        if line is None:
            return

        self.markerAdd(line, MARKER_PHANTOM_BREAKPOINT)
        self._phantom_breakpoint_line = line

    def _clear_phantom_breakpoint(self) -> None:
        """Remove the hover-only breakpoint marker."""
        if self._phantom_breakpoint_line is not None:
            self.markerDeleteAll(MARKER_PHANTOM_BREAKPOINT)
            self._phantom_breakpoint_line = None

    def _update_phantom_breakpoint(self, x: int, y: int) -> None:
        """Show a ghost breakpoint on the executable line under the gutter."""
        if not self._breakpoints_supported():
            self._clear_phantom_breakpoint()
            return

        if not self._breakpoint_hover_margin_at_x(x):
            self._clear_phantom_breakpoint()
            return

        line = self._line_from_mouse_y(y)
        if line is None:
            self._clear_phantom_breakpoint()
            return

        resolved = self._resolve_breakpoint_line(line)
        if resolved is None or self._has_breakpoint_marker(resolved):
            self._clear_phantom_breakpoint()
            return

        self._set_phantom_breakpoint(resolved)

    def _breakable_lines(self) -> set[int]:
        """Return 0-based lines that can reasonably hold Python breakpoints."""
        try:
            tree = ast.parse(self.text())
        except SyntaxError:
            return {
                line
                for line in range(self.lines())
                if self.text(line).strip()
                and not self.text(line).lstrip().startswith("#")
            }

        return {
            node.lineno - 1
            for node in ast.walk(tree)
            if isinstance(node, ast.stmt) and hasattr(node, "lineno")
        }

    def _resolve_breakpoint_line(self, line: int) -> int | None:
        """Map a gutter click/hover to a nearby executable line."""
        if line < 0 or line >= self.lines():
            return None

        breakable_lines = sorted(self._breakable_lines())
        if line in breakable_lines:
            return line

        for candidate in breakable_lines:
            if candidate > line:
                return candidate
        for candidate in reversed(breakable_lines):
            if candidate < line:
                return candidate
        return None

    def _on_margin_clicked(self, margin: int, line: int, state) -> None:
        """Handle clicks on the breakpoint margin (2) or line number margin (0)."""
        if margin in (0, 2):
            self.toggle_breakpoint(line)

    def toggle_breakpoint(self, line: int) -> None:
        """Toggle a breakpoint on the given 0-based line number."""
        if not self._breakpoints_supported():
            self.clear_breakpoints()
            return

        line = self._resolve_breakpoint_line(line)
        if line is None:
            self._clear_phantom_breakpoint()
            return

        self._clear_phantom_breakpoint()
        if self._has_breakpoint_marker(line):
            self.markerDelete(line, MARKER_BREAKPOINT)
        else:
            self.markerAdd(line, MARKER_BREAKPOINT)
        self._sync_breakpoints_from_markers()

    def get_breakpoints(self) -> set[int]:
        """Return the set of 0-based line numbers with breakpoints."""
        if not self._breakpoints_supported():
            self.clear_breakpoints()
            return set()

        self._sync_breakpoints_from_markers()
        return self._breakpoints.copy()

    def clear_breakpoints(self) -> None:
        """Remove all breakpoint markers."""
        self._clear_phantom_breakpoint()
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
        # Scintilla expects color as 0xBBGGRR, not 0xRRGGBB. In HC mode both
        # severities collapse onto pure white so the editor stays monochrome.
        is_hc = self._settings.get("editor.theme") == "default_high_contrast"
        if is_hc:
            error_bgr = 0xFFFFFF
            warning_bgr = 0xFFFFFF
        else:
            error_bgr = 0x0014E5    # #E51400 in BGR
            warning_bgr = 0x4EADF0  # #F0AD4E in BGR
        for ind_id, bgr_color in (
            (INDICATOR_ERROR, error_bgr),
            (INDICATOR_WARNING, warning_bgr),
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

    def refresh_lint_colors(self) -> None:
        """Re-apply current lint markers using the current theme's colors.

        Squiggle indicator colors are set when ``set_lint_issues`` runs and
        don't update when the theme changes — without this, switching from
        HC back to dark would leave error squiggles white instead of red.
        """
        if self._lint_issues:
            self.set_lint_issues(list(self._lint_issues))

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

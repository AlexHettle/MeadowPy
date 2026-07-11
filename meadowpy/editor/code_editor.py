"""Core code editor widget based on QScintilla."""

import ast
from bisect import bisect_left
from collections.abc import Iterable, Mapping
from enum import Enum
from pathlib import Path

from PyQt6.QtCore import pyqtSignal, Qt, QEvent, QLineF, QRectF
from PyQt6.QtGui import (
    QColor,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
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


# Marker IDs for gutter symbols.  Keep these below Scintilla's reserved fold
# marker range (25-31).
MARKER_BREAKPOINT = 0
MARKER_CURRENT_LINE = 1
MARKER_BREAKPOINT_HOVER_ADD = 2
# Backwards-compatible name used by a few integrations and older tests.
MARKER_PHANTOM_BREAKPOINT = MARKER_BREAKPOINT_HOVER_ADD
MARKER_BREAKPOINT_PENDING = 3
MARKER_BREAKPOINT_REJECTED = 4
MARKER_BREAKPOINT_HOVER_REMOVE = 5
MARKER_BREAKPOINT_CURRENT = 6
MARKER_BREAKPOINT_PENDING_CURRENT = 7
MARKER_BREAKPOINT_REJECTED_CURRENT = 8
MARKER_BREAKPOINT_CURRENT_HOVER_REMOVE = 9
MARKER_CURRENT_LINE_HOVER_ADD = 10
BREAKPOINT_MARGIN_WIDTH = 26
BREAKPOINT_MARKER_SIZE = 18
BREAKPOINT_FORWARD_SEARCH_LIMIT = 5


class BreakpointState(str, Enum):
    """Debugger verification state for a requested breakpoint."""

    ACCEPTED = "accepted"
    PENDING = "pending"
    REJECTED = "rejected"


_BREAKPOINT_STATE_MARKERS = {
    BreakpointState.ACCEPTED: MARKER_BREAKPOINT,
    BreakpointState.PENDING: MARKER_BREAKPOINT_PENDING,
    BreakpointState.REJECTED: MARKER_BREAKPOINT_REJECTED,
}
_BREAKPOINT_MARKER_MASK = sum(
    1 << marker for marker in _BREAKPOINT_STATE_MARKERS.values()
)
_CURRENT_LINE_MARKERS = (
    MARKER_CURRENT_LINE,
    MARKER_BREAKPOINT_CURRENT,
    MARKER_BREAKPOINT_PENDING_CURRENT,
    MARKER_BREAKPOINT_REJECTED_CURRENT,
)

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
    # Emits a copied set of effective 0-based lines.  ``object`` keeps the
    # signal stable across Python/Qt versions while preserving set semantics.
    breakpoints_changed = pyqtSignal(object)
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
        self._published_breakpoints: set[int] = set()
        self._phantom_breakpoint_line: int | None = None
        self._phantom_breakpoint_is_remove = False
        self._phantom_breakpoint_marker: int | None = None
        self._rejected_breakpoint_reasons: dict[int, str] = {}
        self._current_line: int | None = None
        self._breakable_lines_cache: set[int] | None = None
        self._sorted_breakable_lines_cache: tuple[int, ...] | None = None
        self.setMouseTracking(True)

        # Define gutter marker shapes; colors are applied separately so they
        # can be refreshed when the theme changes.
        self.markerDefine(QsciScintilla.MarkerSymbol.RightArrow, MARKER_CURRENT_LINE)
        self._apply_marker_colors()

        EditorConfigurator.apply(self, settings)
        # Font metrics and DPR are reliable after the configurator runs.
        self._refresh_breakpoint_lane_artwork()
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
        self.textChanged.connect(self._invalidate_breakable_lines_cache)
        self.textChanged.connect(self._sync_breakpoints_from_markers)
        self.marginClicked.connect(self._on_margin_clicked)

    @property
    def file_path(self) -> str | None:
        return self._file_path

    @file_path.setter
    def file_path(self, path: str | None) -> None:
        previous_path = self._file_path
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
        else:
            self._refresh_breakpoint_lane_artwork()
            # A save-as/rename changes the path-keyed debugger payload even
            # when every marker stayed on the same line.
            if previous_path != path and self._breakpoint_lines_from_markers():
                self._emit_breakpoints_changed(force=True)

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
        self._refresh_breakpoint_lane_artwork()
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
        """Show plain-English gutter and lint hover help."""
        dpr_change = getattr(QEvent.Type, "DevicePixelRatioChange", None)
        if dpr_change is not None and e.type() == dpr_change:
            refresh = getattr(self, "_refresh_breakpoint_lane_artwork", None)
            if callable(refresh):
                refresh()

        if e.type() == QEvent.Type.ToolTip:
            breakpoint_tooltip = None
            tooltip_getter = getattr(self, "_get_breakpoint_tooltip", None)
            if callable(tooltip_getter):
                breakpoint_tooltip = tooltip_getter(
                    e.pos().x(),
                    e.pos().y(),
                )
            if breakpoint_tooltip:
                QToolTip.showText(e.globalPos(), breakpoint_tooltip, self)
                return True

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
        self._refresh_breakpoint_lane_artwork()

    def zoomOut(self, range_=1) -> None:
        super().zoomOut(range_)
        self._update_margin_width()
        self._refresh_breakpoint_lane_artwork()

    def zoomTo(self, size) -> None:
        super().zoomTo(size)
        self._update_margin_width()
        self._refresh_breakpoint_lane_artwork()

    def wheelEvent(self, event) -> None:
        super().wheelEvent(event)
        # Ctrl+wheel triggers zoom inside Scintilla
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._update_margin_width()
            self._refresh_breakpoint_lane_artwork()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        super().mouseMoveEvent(event)
        self._update_phantom_breakpoint(event.pos().x(), event.pos().y())

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._clear_phantom_breakpoint()
        self.unsetCursor()
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
        logical_size: int = BREAKPOINT_MARKER_SIZE,
        device_pixel_ratio: float = 1.0,
        symbol: str | None = None,
        symbol_color: QColor | None = None,
        dashed: bool = False,
        execution_ring: QColor | None = None,
    ) -> QPixmap:
        """Return flat, DPR-aware breakpoint artwork.

        ``logical_size`` is expressed in device-independent pixels.  The
        backing raster is allocated at the screen's real pixel density and
        tagged with its DPR so Scintilla does not blur a 1x asset on HiDPI
        displays.
        """
        size = max(int(logical_size), 12)
        dpr = max(float(device_pixel_ratio), 1.0)
        physical_size = max(int(round(size * dpr)), 1)
        pixmap = QPixmap(physical_size, physical_size)
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            if execution_ring is not None:
                ring_pen = QPen(execution_ring, 1.8)
                ring_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(ring_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QRectF(1.5, 1.5, size - 3.0, size - 3.0))
                diameter = max(8.0, min(11.0, size - 8.0))
            else:
                diameter = max(10.0, min(16.0, size - 4.0))

            inset = (size - diameter) / 2.0
            circle = QRectF(inset, inset, diameter, diameter)
            pen = QPen(border, 1.35)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            if dashed:
                pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(fill if filled else Qt.BrushStyle.NoBrush)
            painter.drawEllipse(circle)

            if symbol:
                glyph_color = symbol_color or border
                glyph_pen = QPen(glyph_color, 1.65)
                glyph_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(glyph_pen)
                center = size / 2.0
                arm = max(2.0, diameter * 0.22)
                if symbol in ("plus", "minus"):
                    painter.drawLine(
                        QLineF(center - arm, center, center + arm, center)
                    )
                    if symbol == "plus":
                        painter.drawLine(
                            QLineF(center, center - arm, center, center + arm)
                        )
                elif symbol == "slash":
                    painter.drawLine(
                        QLineF(
                            center - arm,
                            center + arm,
                            center + arm,
                            center - arm,
                        )
                    )
        finally:
            painter.end()

        return pixmap

    @staticmethod
    def _current_line_marker_pixmap(
        fill: QColor,
        border: QColor,
        *,
        logical_size: int = BREAKPOINT_MARKER_SIZE,
        device_pixel_ratio: float = 1.0,
    ) -> QPixmap:
        """Return a crisp execution chevron for a line without a breakpoint."""
        size = max(int(logical_size), 12)
        dpr = max(float(device_pixel_ratio), 1.0)
        pixmap = QPixmap(
            max(int(round(size * dpr)), 1),
            max(int(round(size * dpr)), 1),
        )
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            middle = size / 2.0
            path = QPainterPath()
            path.moveTo(size - 2.0, middle)
            path.lineTo(size * 0.38, middle - size * 0.30)
            path.lineTo(size * 0.38, middle - size * 0.12)
            path.lineTo(2.0, middle - size * 0.12)
            path.lineTo(2.0, middle + size * 0.12)
            path.lineTo(size * 0.38, middle + size * 0.12)
            path.lineTo(size * 0.38, middle + size * 0.30)
            path.closeSubpath()
            painter.setPen(QPen(border, 1.0))
            painter.setBrush(fill)
            painter.drawPath(path)
        finally:
            painter.end()
        return pixmap

    def _breakpoint_marker_logical_size(self) -> int:
        """Scale marker artwork modestly with the editor's line height."""
        try:
            line_height = int(self._line_height(0))
        except (AttributeError, TypeError, RuntimeError):
            line_height = BREAKPOINT_MARKER_SIZE
        return max(16, min(24, int(round(line_height * 0.95))))

    def _marker_device_pixel_ratio(self) -> float:
        try:
            return max(float(self.devicePixelRatioF()), 1.0)
        except (AttributeError, TypeError, RuntimeError):
            return 1.0

    def _define_breakpoint_markers(self) -> None:
        """Install custom breakpoint marker artwork for the current theme."""
        from meadowpy.editor.themes import get_theme

        theme = get_theme(
            self._settings.get("editor.theme"),
            custom_base=self._settings.get("editor.custom_theme.base"),
        )
        size = self._breakpoint_marker_logical_size()
        dpr = self._marker_device_pixel_ratio()
        margin = QColor(theme.margin_background)
        keyline = QColor(theme.breakpoint_keyline)
        current = QColor(theme.current_execution)

        marker_specs = {
            MARKER_BREAKPOINT: dict(
                fill=QColor(theme.breakpoint_active),
                border=keyline,
                filled=True,
            ),
            MARKER_BREAKPOINT_HOVER_ADD: dict(
                fill=QColor(theme.breakpoint_hover_add),
                border=QColor(theme.breakpoint_hover_add),
                filled=False,
                symbol="plus",
            ),
            MARKER_BREAKPOINT_PENDING: dict(
                fill=QColor(theme.breakpoint_pending),
                border=QColor(theme.breakpoint_pending),
                filled=False,
                dashed=True,
            ),
            MARKER_BREAKPOINT_REJECTED: dict(
                fill=QColor(theme.breakpoint_rejected),
                border=keyline,
                filled=True,
                symbol="slash",
                symbol_color=margin,
            ),
            MARKER_BREAKPOINT_HOVER_REMOVE: dict(
                fill=QColor(theme.breakpoint_hover_remove),
                border=keyline,
                filled=True,
                symbol="minus",
                symbol_color=margin,
            ),
            MARKER_BREAKPOINT_CURRENT: dict(
                fill=QColor(theme.breakpoint_active),
                border=keyline,
                filled=True,
                execution_ring=current,
            ),
            MARKER_BREAKPOINT_PENDING_CURRENT: dict(
                fill=QColor(theme.breakpoint_pending),
                border=QColor(theme.breakpoint_pending),
                filled=False,
                dashed=True,
                execution_ring=current,
            ),
            MARKER_BREAKPOINT_REJECTED_CURRENT: dict(
                fill=QColor(theme.breakpoint_rejected),
                border=keyline,
                filled=True,
                symbol="slash",
                symbol_color=margin,
                execution_ring=current,
            ),
            MARKER_BREAKPOINT_CURRENT_HOVER_REMOVE: dict(
                fill=QColor(theme.breakpoint_hover_remove),
                border=keyline,
                filled=True,
                symbol="minus",
                symbol_color=margin,
                execution_ring=current,
            ),
            MARKER_CURRENT_LINE_HOVER_ADD: dict(
                fill=QColor(theme.breakpoint_hover_add),
                border=QColor(theme.breakpoint_hover_add),
                filled=False,
                symbol="plus",
                execution_ring=current,
            ),
        }
        for marker, spec in marker_specs.items():
            self.markerDefine(
                self._breakpoint_marker_pixmap(
                    logical_size=size,
                    device_pixel_ratio=dpr,
                    **spec,
                ),
                marker,
            )

        self.markerDefine(
            self._current_line_marker_pixmap(
                current,
                QColor(theme.current_execution_foreground),
                logical_size=size,
                device_pixel_ratio=dpr,
            ),
            MARKER_CURRENT_LINE,
        )

    def _apply_marker_colors(self) -> None:
        """Install semantic breakpoint/current-line marker artwork."""
        self._define_breakpoint_markers()

    def _refresh_breakpoint_lane_artwork(self) -> None:
        """Refresh marker rasters and lane width after theme/zoom/DPR changes."""
        self._apply_marker_colors()
        supported = self._breakpoints_supported()
        size = self._breakpoint_marker_logical_size()
        width = max(BREAKPOINT_MARGIN_WIDTH, size + 8) if supported else 0
        self.setMarginWidth(2, width)
        self.setMarginSensitivity(2, supported)
        # Line numbers are for navigation/reading only; breakpoint toggles
        # belong to the dedicated lane.
        self.setMarginSensitivity(0, False)

    def refresh_marker_colors(self) -> None:
        """Re-apply breakpoint / current-line marker colors after a theme change."""
        self._refresh_breakpoint_lane_artwork()

    # --- Breakpoint methods ---

    def _breakpoint_lines_from_markers(self) -> set[int]:
        """Return breakpoint line numbers from Scintilla's marker state."""
        return set(self._marker_lines(_BREAKPOINT_MARKER_MASK))

    def _marker_lines(self, marker_mask: int):
        """Yield matching marker lines without scanning the whole document."""
        line = 0
        total = self.lines()
        while line < total:
            found = int(
                self.SendScintilla(
                    2047,  # SCI_MARKERNEXT
                    line,
                    marker_mask,
                )
            )
            if found < 0 or found >= total:
                return
            yield found
            line = found + 1

    def _has_breakpoint_marker(self, line: int) -> bool:
        """Return True if the given line currently has a breakpoint marker."""
        if line < 0 or line >= self.lines():
            return False
        return bool(self.markersAtLine(line) & _BREAKPOINT_MARKER_MASK)

    def _emit_breakpoints_changed(self, *, force: bool = False) -> None:
        current = self._breakpoint_lines_from_markers()
        self._breakpoints = current
        if force or current != self._published_breakpoints:
            self._published_breakpoints = current.copy()
            self.breakpoints_changed.emit(current.copy())

    def _sync_breakpoints_from_markers(self, *_args) -> None:
        """Keep cached breakpoint lines aligned with movable editor markers."""
        self._emit_breakpoints_changed()
        self._refresh_current_line_marker()

    def _breakpoints_supported(self) -> bool:
        """Return True when this tab can display debugger breakpoints."""
        return is_python_file_path(self._file_path)

    def _breakpoint_hover_margin_at_x(self, x: int) -> bool:
        """Return True only when x is over the dedicated breakpoint lane."""
        line_number_width = int(self.marginWidth(0) or 0)
        fold_width = int(self.marginWidth(1) or 0)
        breakpoint_width = int(self.marginWidth(2) or 0)
        breakpoint_start = line_number_width + fold_width
        breakpoint_end = breakpoint_start + breakpoint_width
        return (
            breakpoint_width > 0
            and breakpoint_start <= x < breakpoint_end
        )

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

    def _set_phantom_breakpoint(
        self,
        line: int | None,
        *,
        remove: bool = False,
    ) -> None:
        """Move the explicit add/remove hover marker."""
        marker = None
        if line is not None:
            current_line_getter = getattr(
                self,
                "_current_execution_line_from_markers",
                None,
            )
            is_current = (
                callable(current_line_getter)
                and current_line_getter() == line
            )
            if is_current:
                marker = (
                    MARKER_BREAKPOINT_CURRENT_HOVER_REMOVE
                    if remove
                    else MARKER_CURRENT_LINE_HOVER_ADD
                )
            else:
                marker = (
                    MARKER_BREAKPOINT_HOVER_REMOVE
                    if remove
                    else MARKER_BREAKPOINT_HOVER_ADD
                )
        if (
            self._phantom_breakpoint_line == line
            and getattr(self, "_phantom_breakpoint_is_remove", False) == remove
            and getattr(self, "_phantom_breakpoint_marker", None) == marker
        ):
            return

        self._clear_phantom_breakpoint()
        if line is None:
            return

        self.markerAdd(line, marker)
        self._phantom_breakpoint_line = line
        self._phantom_breakpoint_is_remove = remove
        self._phantom_breakpoint_marker = marker

    def _clear_phantom_breakpoint(self) -> None:
        """Remove the hover-only breakpoint marker."""
        if self._phantom_breakpoint_line is not None:
            marker = getattr(self, "_phantom_breakpoint_marker", None)
            if marker is None:
                marker = (
                    MARKER_BREAKPOINT_HOVER_REMOVE
                    if getattr(self, "_phantom_breakpoint_is_remove", False)
                    else MARKER_BREAKPOINT_HOVER_ADD
                )
            self.markerDeleteAll(marker)
            self._phantom_breakpoint_line = None
            self._phantom_breakpoint_is_remove = False
            self._phantom_breakpoint_marker = None

    def _update_phantom_breakpoint(self, x: int, y: int) -> None:
        """Show add/remove artwork and a pointer over the breakpoint lane."""
        if not self._breakpoints_supported():
            self._clear_phantom_breakpoint()
            unset_cursor = getattr(self, "unsetCursor", None)
            if callable(unset_cursor):
                unset_cursor()
            return

        if not self._breakpoint_hover_margin_at_x(x):
            self._clear_phantom_breakpoint()
            unset_cursor = getattr(self, "unsetCursor", None)
            if callable(unset_cursor):
                unset_cursor()
            return

        line = self._line_from_mouse_y(y)
        if line is None:
            self._clear_phantom_breakpoint()
            unset_cursor = getattr(self, "unsetCursor", None)
            if callable(unset_cursor):
                unset_cursor()
            return

        # Existing markers remain removable even if an edit has turned their
        # line into a blank/comment/non-executable line.
        resolved = (
            line
            if self._has_breakpoint_marker(line)
            else self._resolve_breakpoint_line(line)
        )
        if resolved is None:
            self._clear_phantom_breakpoint()
            unset_cursor = getattr(self, "unsetCursor", None)
            if callable(unset_cursor):
                unset_cursor()
            return

        self._set_phantom_breakpoint(
            resolved,
            remove=self._has_breakpoint_marker(resolved),
        )
        set_cursor = getattr(self, "setCursor", None)
        if callable(set_cursor):
            set_cursor(Qt.CursorShape.PointingHandCursor)

    def _get_breakpoint_tooltip(self, x: int, y: int) -> str | None:
        """Return beginner-friendly help for the breakpoint lane."""
        if (
            not self._breakpoints_supported()
            or not self._breakpoint_hover_margin_at_x(x)
        ):
            return None
        requested = self._line_from_mouse_y(y)
        if requested is None:
            return None
        line = (
            requested
            if self._has_breakpoint_marker(requested)
            else self._resolve_breakpoint_line(requested)
        )
        if line is None:
            return "No executable Python statement nearby"

        display_line = line + 1
        state = self.get_breakpoint_state(line)
        if state == BreakpointState.PENDING:
            return (
                f"Breakpoint on line {display_line} is waiting for the debugger. "
                "Click to remove it."
            )
        if state == BreakpointState.REJECTED:
            reason = self.get_breakpoint_rejection_reason(line)
            detail = f": {reason}" if reason else ""
            return (
                f"The debugger could not set the breakpoint on line "
                f"{display_line}{detail}. Click to remove it."
            )
        if state == BreakpointState.ACCEPTED:
            return f"Remove breakpoint from line {display_line}"
        if line != requested:
            return (
                f"Add breakpoint on line {display_line} "
                "(the next executable line)"
            )
        return f"Add breakpoint on line {display_line}"

    def _breakable_lines(self) -> set[int]:
        """Return 0-based lines that can reasonably hold Python breakpoints."""
        if self._breakable_lines_cache is not None:
            return self._breakable_lines_cache

        try:
            tree = ast.parse(self.text())
        except SyntaxError:
            result = {
                line
                for line in range(self.lines())
                if self.text(line).strip()
                and not self.text(line).lstrip().startswith("#")
            }
        else:
            result = {
                node.lineno - 1
                for node in ast.walk(tree)
                if isinstance(node, ast.stmt) and hasattr(node, "lineno")
            }
        self._breakable_lines_cache = result
        self._sorted_breakable_lines_cache = tuple(sorted(result))
        return result

    def _sorted_breakable_lines(self) -> tuple[int, ...]:
        """Return a cached ordered index used by gutter hover lookups."""
        if self._sorted_breakable_lines_cache is None:
            # `_breakable_lines()` normally populates both caches together.
            # The fallback also supports lightweight test/integration
            # harnesses that seed only the established set cache.
            self._sorted_breakable_lines_cache = tuple(
                sorted(self._breakable_lines())
            )
        return self._sorted_breakable_lines_cache

    def _invalidate_breakable_lines_cache(self, *_args) -> None:
        self._breakable_lines_cache = None
        self._sorted_breakable_lines_cache = None

    def _resolve_breakpoint_line(self, line: int) -> int | None:
        """Map a gutter click/hover to a nearby executable line."""
        if line < 0 or line >= self.lines():
            return None

        breakable_lines = self._sorted_breakable_lines()
        index = bisect_left(breakable_lines, line)
        if index < len(breakable_lines):
            candidate = breakable_lines[index]
            if candidate <= line + BREAKPOINT_FORWARD_SEARCH_LIMIT:
                return candidate
        return None

    def _on_margin_clicked(self, margin: int, line: int, state) -> None:
        """Handle clicks only in the dedicated breakpoint margin (2)."""
        if margin == 2:
            self.toggle_breakpoint(line)

    def get_breakpoint_state(self, line: int) -> BreakpointState | None:
        """Return the debugger state for a 0-based breakpoint line."""
        if line < 0 or line >= self.lines():
            return None
        markers = self.markersAtLine(line)
        for state in (
            BreakpointState.REJECTED,
            BreakpointState.PENDING,
            BreakpointState.ACCEPTED,
        ):
            if markers & (1 << _BREAKPOINT_STATE_MARKERS[state]):
                return state
        return None

    def _forget_rejection_reasons_at_line(self, line: int) -> None:
        for handle in tuple(self._rejected_breakpoint_reasons):
            marker_line = self.SendScintilla(2017, handle)  # SCI_MARKERLINEFROMHANDLE
            if marker_line < 0 or marker_line == line:
                self._rejected_breakpoint_reasons.pop(handle, None)

    def get_breakpoint_rejection_reason(self, line: int) -> str | None:
        """Return the debugger's rejection explanation for ``line``."""
        for handle, reason in tuple(self._rejected_breakpoint_reasons.items()):
            marker_line = self.SendScintilla(2017, handle)  # SCI_MARKERLINEFROMHANDLE
            if marker_line < 0:
                self._rejected_breakpoint_reasons.pop(handle, None)
            elif marker_line == line:
                return reason
        return None

    def _set_breakpoint_state(
        self,
        line: int,
        state: BreakpointState,
        reason: str = "",
    ) -> None:
        if not self._has_breakpoint_marker(line):
            return
        self._forget_rejection_reasons_at_line(line)
        for marker in _BREAKPOINT_STATE_MARKERS.values():
            self.markerDelete(line, marker)
        handle = self.markerAdd(line, _BREAKPOINT_STATE_MARKERS[state])
        if state == BreakpointState.REJECTED and reason and handle >= 0:
            self._rejected_breakpoint_reasons[int(handle)] = str(reason)

    def mark_breakpoints_pending(
        self,
        lines: Iterable[int] | None = None,
    ) -> None:
        """Mark requested 0-based lines as awaiting debugger confirmation."""
        current = self._breakpoint_lines_from_markers()
        targets = current if lines is None else current.intersection(lines)
        for line in targets:
            self._set_breakpoint_state(line, BreakpointState.PENDING)
        self._refresh_current_line_marker()

    def set_breakpoint_verification(
        self,
        accepted_lines: Iterable[int],
        rejected_lines: Mapping[int, str] | Iterable[int] = (),
    ) -> None:
        """Apply a debugger acknowledgment expressed with 0-based lines.

        Current breakpoints omitted from both collections stay pending.  A
        mapping for ``rejected_lines`` preserves the helper's explanation for
        the hover tooltip; a plain iterable is accepted for simpler clients.
        """
        accepted = {int(line) for line in accepted_lines}
        if isinstance(rejected_lines, Mapping):
            rejected = {
                int(line): str(reason)
                for line, reason in rejected_lines.items()
            }
        else:
            rejected = {int(line): "" for line in rejected_lines}

        for line in self._breakpoint_lines_from_markers():
            if line in rejected:
                self._set_breakpoint_state(
                    line,
                    BreakpointState.REJECTED,
                    rejected[line],
                )
            elif line in accepted:
                self._set_breakpoint_state(line, BreakpointState.ACCEPTED)
            else:
                self._set_breakpoint_state(line, BreakpointState.PENDING)
        self._refresh_current_line_marker()

    def toggle_breakpoint(self, line: int) -> None:
        """Toggle a breakpoint on the given 0-based line number."""
        if not self._breakpoints_supported():
            self.clear_breakpoints()
            return

        line = (
            line
            if self._has_breakpoint_marker(line)
            else self._resolve_breakpoint_line(line)
        )
        if line is None:
            self._clear_phantom_breakpoint()
            return

        self._clear_phantom_breakpoint()
        if self._has_breakpoint_marker(line):
            self._forget_rejection_reasons_at_line(line)
            for marker in _BREAKPOINT_STATE_MARKERS.values():
                self.markerDelete(line, marker)
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
        for marker in _BREAKPOINT_STATE_MARKERS.values():
            self.markerDeleteAll(marker)
        self._rejected_breakpoint_reasons.clear()
        self._sync_breakpoints_from_markers()

    # --- Debug current-line methods ---

    def set_current_line(self, line: int) -> None:
        """Show a current-line chevron or combined breakpoint ring."""
        self.clear_current_line()
        if line < 0 or line >= self.lines():
            return
        self._refresh_current_line_marker(line)
        self.ensureLineVisible(line)
        self.setCursorPosition(line, 0)

    def _current_execution_line_from_markers(self) -> int | None:
        mask = sum(1 << marker for marker in _CURRENT_LINE_MARKERS)
        return next(self._marker_lines(mask), None)

    def _refresh_current_line_marker(self, line: int | None = None) -> None:
        if line is None:
            line = self._current_execution_line_from_markers()
        if line is None or line < 0 or line >= self.lines():
            self._current_line = None
            return

        if self._current_line is not None and self._current_line != line:
            self._clear_phantom_breakpoint()
        for marker in _CURRENT_LINE_MARKERS:
            self.markerDeleteAll(marker)
        state = self.get_breakpoint_state(line)
        marker = {
            BreakpointState.ACCEPTED: MARKER_BREAKPOINT_CURRENT,
            BreakpointState.PENDING: MARKER_BREAKPOINT_PENDING_CURRENT,
            BreakpointState.REJECTED: MARKER_BREAKPOINT_REJECTED_CURRENT,
            None: MARKER_CURRENT_LINE,
        }[state]
        self.markerAdd(line, marker)
        self._current_line = line

    def clear_current_line(self) -> None:
        """Remove the current-execution-line arrow."""
        # Composite add/remove hover markers can carry the gold execution
        # ring.  Drop them with the current line so resume never leaves a
        # stale paused affordance behind under a stationary mouse.
        self._clear_phantom_breakpoint()
        for marker in _CURRENT_LINE_MARKERS:
            self.markerDeleteAll(marker)
        self._current_line = None

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

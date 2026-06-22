from __future__ import annotations

from types import SimpleNamespace

import meadowpy.editor.code_editor as code_editor_module
import meadowpy.editor.editor_fonts as editor_fonts
from helpers import DummySignal
from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import QColor, QKeyEvent, QWheelEvent
from PyQt6.Qsci import QsciScintilla

from meadowpy.core.settings import Settings
from meadowpy.editor.code_editor import CodeEditor
from meadowpy.editor.editor_config import EditorConfigurator
from meadowpy.resources.resource_loader import get_stylesheet


def make_editor(qapp, tmp_path) -> CodeEditor:
    settings = Settings(tmp_path)
    settings.set("editor.auto_complete", False)
    editor = CodeEditor(settings)
    return editor


def test_toggle_comment_comments_and_uncomments_selected_block(qapp, tmp_path):
    editor = make_editor(qapp, tmp_path)
    editor.setText("x = 1\n    y = 2\n\n")
    editor.setSelection(0, 0, 1, len("    y = 2"))

    editor.toggle_comment()

    assert editor.text(0).startswith("# x = 1")
    assert editor.text(1).startswith("#     y = 2")
    assert editor.text() == "# x = 1\n#     y = 2\n\n"
    assert editor._selection_is_commented() is True

    editor.toggle_comment()

    assert editor.text(0).startswith("x = 1")
    assert editor.text(1).startswith("    y = 2")
    assert editor.text() == "x = 1\n    y = 2\n\n"
    editor.deleteLater()


def test_toggle_comment_uses_current_line_when_nothing_is_selected(qapp, tmp_path):
    editor = make_editor(qapp, tmp_path)
    editor.setText("print('hi')\n")
    editor.setCursorPosition(0, 0)

    editor.toggle_comment()
    assert editor.text(0).startswith("# print('hi')")
    assert editor.text() == "# print('hi')\n"

    editor.toggle_comment()
    assert editor.text(0).startswith("print('hi')")
    assert editor.text() == "print('hi')\n"
    editor.deleteLater()


def test_toggle_comment_noops_for_non_python_files(qapp, tmp_path):
    editor = make_editor(qapp, tmp_path)
    editor.file_path = str(tmp_path / "notes.scala")
    editor.setText("value = 1\n")
    editor.setCursorPosition(0, 0)

    editor.toggle_comment()

    assert editor.text(0).startswith("value = 1")
    editor.deleteLater()


def test_find_enclosing_def_returns_prompt_code_and_docstring_line(qapp, tmp_path):
    editor = make_editor(qapp, tmp_path)
    editor.setText(
        "def greet(name):\n"
        "    value = name.upper()\n"
        "    return value\n"
        "\n"
        "print(greet('Ada'))\n"
    )

    func_code, insert_line = editor._find_enclosing_def(2)

    assert insert_line == 1
    assert "def greet(name):" in func_code
    assert "return value" in func_code
    editor.deleteLater()


def test_breakpoint_current_line_and_lint_helpers_track_editor_state(qapp, tmp_path):
    editor = make_editor(qapp, tmp_path)
    editor.setText("print(missing)\n")
    assert editor.marginWidth(2) >= code_editor_module.BREAKPOINT_MARGIN_WIDTH

    editor.toggle_breakpoint(0)
    assert editor.get_breakpoints() == {0}
    editor.toggle_breakpoint(0)
    assert editor.get_breakpoints() == set()

    editor.set_current_line(0)
    editor.clear_current_line()

    issue = SimpleNamespace(
        line=0,
        column=0,
        code="F821",
        message="undefined name 'missing'",
        severity="error",
    )
    editor.set_lint_issues([issue])
    assert "F821: undefined name" in editor._get_lint_tooltip(0, 2)

    editor.refresh_lint_colors()
    editor.clear_lint_markers()

    assert editor._get_lint_tooltip(0, 2) is None
    editor.deleteLater()


def test_breakpoint_marker_pixmaps_are_centered_and_antialiased(qapp):
    size = code_editor_module.BREAKPOINT_MARKER_SIZE
    marker = CodeEditor._breakpoint_marker_pixmap(
        QColor("#E9483F"),
        QColor("#9E2F2B"),
        filled=True,
    ).toImage()
    ghost = CodeEditor._breakpoint_marker_pixmap(
        QColor("#E9483F"),
        QColor("#E9483F"),
        filled=False,
    ).toImage()

    assert marker.pixelColor(0, 0).alpha() == 0
    assert ghost.pixelColor(0, 0).alpha() == 0

    center = marker.pixelColor(size // 2, size // 2)
    rim = marker.pixelColor(3, size // 2)
    ghost_center = ghost.pixelColor(size // 2, size // 2)
    assert center.alpha() > 220
    assert center.red() > 220
    assert center.green() < 120
    assert rim.red() < center.red()
    assert ghost_center.alpha() < center.alpha()

    # Keep the inset rim from leaking square pixels at the cardinal points.
    assert marker.pixelColor(size // 2, 2).alpha() == 0
    assert marker.pixelColor(size // 2, size - 3).alpha() == 0
    assert marker.pixelColor(2, size // 2).alpha() == 0
    assert marker.pixelColor(size - 3, size // 2).alpha() == 0
    assert ghost.pixelColor(size // 2, 2).alpha() == 0
    assert ghost.pixelColor(size // 2, size - 3).alpha() == 0
    assert ghost.pixelColor(2, size // 2).alpha() == 0
    assert ghost.pixelColor(size - 3, size // 2).alpha() == 0


def test_breakpoints_follow_editor_marker_line_changes(qapp, tmp_path):
    editor = make_editor(qapp, tmp_path)
    editor.setText("first\nsecond\nthird\n")

    editor.toggle_breakpoint(1)
    editor.insertAt("inserted\n", 0, 0)

    assert editor.get_breakpoints() == {2}

    editor.toggle_breakpoint(2)
    assert editor.get_breakpoints() == set()
    editor.deleteLater()


def test_breakpoints_on_non_code_lines_snap_to_next_statement(qapp, tmp_path):
    editor = make_editor(qapp, tmp_path)
    editor.setText("# heading\n\nvalue = 1\n# trailing\n\n")

    editor.toggle_breakpoint(0)
    assert editor.get_breakpoints() == {2}

    editor.toggle_breakpoint(1)
    assert editor.get_breakpoints() == set()

    editor.toggle_breakpoint(3)
    assert editor.get_breakpoints() == {2}

    editor.toggle_breakpoint(4)
    assert editor.get_breakpoints() == set()
    editor.deleteLater()


def test_non_python_file_path_blocks_breakpoints(qapp, tmp_path):
    editor = make_editor(qapp, tmp_path)
    editor.setText("print('hi')\n")
    editor.file_path = str(tmp_path / "demo.py")

    assert editor.lexer() is not None
    editor.toggle_breakpoint(0)
    assert editor.get_breakpoints() == {0}

    editor._completion_apis = object()
    editor.file_path = str(tmp_path / "requirements.txt")
    assert editor.lexer() is None
    assert not hasattr(editor, "_completion_apis")
    assert editor.get_breakpoints() == set()
    assert not (
        editor.markersAtLine(0)
        & (1 << code_editor_module.MARKER_BREAKPOINT)
    )

    editor.setText("PyQt6>=6.7.1\nflake8>=7.0.0\n")
    editor.toggle_breakpoint(0)

    assert editor.get_breakpoints() == set()

    editor.file_path = str(tmp_path / "restored.py")
    assert editor.lexer() is not None

    editor.deleteLater()


class PhantomBreakpointHarness:
    _breakpoint_hover_margin_at_x = CodeEditor._breakpoint_hover_margin_at_x
    _line_from_mouse_y = CodeEditor._line_from_mouse_y
    _set_phantom_breakpoint = CodeEditor._set_phantom_breakpoint
    _clear_phantom_breakpoint = CodeEditor._clear_phantom_breakpoint

    def __init__(self):
        self._phantom_breakpoint_line = None
        self.widths = {0: 24, 1: 12, 2: 18, 3: 0, 4: 0}
        self.line = 1
        self.resolved_line = 2
        self.real_breakpoints = set()
        self.added = []
        self.deleted = []
        self.supports_breakpoints = True

    def _breakpoints_supported(self):
        return self.supports_breakpoints

    def marginWidth(self, index):
        return self.widths.get(index, 0)

    def SendScintilla(self, message, x, y):
        assert message == 2022
        return 40

    def lineIndexFromPosition(self, _pos):
        return self.line, 0

    def lines(self):
        return 5

    def _resolve_breakpoint_line(self, _line):
        return self.resolved_line

    def _has_breakpoint_marker(self, line):
        return line in self.real_breakpoints

    def markerAdd(self, line, marker):
        self.added.append((line, marker))

    def markerDelete(self, line, marker):
        self.deleted.append((line, marker))

    def markerDeleteAll(self, marker):
        self.deleted.append(("all", marker))


def test_phantom_breakpoint_follows_hoverable_gutter_and_skips_real_breakpoints():
    marker = code_editor_module.MARKER_PHANTOM_BREAKPOINT
    harness = PhantomBreakpointHarness()

    CodeEditor._update_phantom_breakpoint(harness, 5, 12)
    assert harness._phantom_breakpoint_line == 2
    assert harness.added == [(2, marker)]

    CodeEditor._update_phantom_breakpoint(harness, 25, 12)
    assert harness._phantom_breakpoint_line is None
    assert harness.deleted == [("all", marker)]

    harness.real_breakpoints = {2}
    CodeEditor._update_phantom_breakpoint(harness, 40, 12)
    assert harness.added == [(2, marker)]


def test_phantom_breakpoint_hides_when_file_does_not_support_breakpoints():
    harness = PhantomBreakpointHarness()
    harness.supports_breakpoints = False
    harness._phantom_breakpoint_line = 2

    CodeEditor._update_phantom_breakpoint(harness, 5, 12)

    assert harness._phantom_breakpoint_line is None
    assert harness.deleted == [("all", code_editor_module.MARKER_PHANTOM_BREAKPOINT)]


def test_lint_markers_use_high_contrast_indicator_colors(qapp, tmp_path):
    settings = Settings(tmp_path)
    settings.set("editor.auto_complete", False)
    settings.set("editor.theme", "default_high_contrast")
    editor = CodeEditor(settings)
    editor.setText("print(missing)\n")

    issue = SimpleNamespace(
        line=0,
        column=0,
        code="F821",
        message="undefined name 'missing'",
        severity="error",
    )

    editor.set_lint_issues([issue])

    assert editor._get_lint_tooltip(0, 0) == "F821: undefined name 'missing'"
    editor.deleteLater()


def test_editor_configurator_applies_disabled_editor_features(qapp, tmp_path):
    settings = Settings(tmp_path)
    settings.set("editor.auto_complete", False)
    settings.set("editor.word_wrap", False)
    settings.set("editor.brace_matching", False)
    settings.set("editor.show_line_numbers", False)
    settings.set("editor.code_folding", False)
    settings.set("editor.show_whitespace", True)
    settings.set("editor.theme", "default_high_contrast")

    editor = CodeEditor(settings)
    EditorConfigurator.apply(editor, settings)

    assert editor.objectName() == "codeEditor"
    assert 'font-family: "Consolas"' in editor.styleSheet()
    assert editor.wrapMode() == QsciScintilla.WrapMode.WrapNone
    assert editor.marginWidth(0) == 0
    assert editor.lexer() is not None
    assert not hasattr(editor, "_completion_apis")
    editor.deleteLater()


def test_editor_font_survives_global_app_stylesheet(qapp, tmp_path):
    old_stylesheet = qapp.styleSheet()
    editor = None
    try:
        qapp.setStyleSheet(get_stylesheet("default_dark"))
        settings = Settings(tmp_path)
        settings.set("editor.font_family", "Consolas")
        editor = CodeEditor(settings)

        assert editor.font().family() == "Consolas"

        settings.set("editor.font_family", "Arial")
        EditorConfigurator.apply(editor, settings)

        assert editor.font().family() == "Arial"
        assert 'font-family: "Arial"' in editor.styleSheet()
    finally:
        if editor is not None:
            editor.deleteLater()
        qapp.setStyleSheet(old_stylesheet)


def test_editor_font_family_falls_back_to_safe_scalable_font(monkeypatch):
    monkeypatch.setattr(
        editor_fonts,
        "_families",
        lambda: ["Laggy Display", "Consolas"],
    )
    monkeypatch.setattr(
        editor_fonts,
        "_is_smoothly_scalable",
        lambda family: family == "Consolas",
    )

    assert not editor_fonts.is_editor_safe_font_family("Laggy Display")
    assert editor_fonts.editor_font_family("Laggy Display") == "Consolas"


def test_editor_font_helpers_handle_font_database_failures(monkeypatch):
    def raise_runtime_error(*args):
        raise RuntimeError("font database unavailable")

    monkeypatch.setattr(
        editor_fonts.QFontDatabase,
        "families",
        raise_runtime_error,
    )
    assert editor_fonts._families() == []
    assert editor_fonts.is_editor_safe_font_family(None) is False
    assert editor_fonts.is_editor_safe_font_family("") is False
    assert editor_fonts.is_editor_safe_font_family("Any Font") is True

    monkeypatch.setattr(
        editor_fonts.QFontDatabase,
        "isSmoothlyScalable",
        lambda family: family == "Smooth Mono",
    )
    assert editor_fonts._is_smoothly_scalable("Smooth Mono") is True

    monkeypatch.setattr(editor_fonts, "_families", lambda: ["Broken Mono"])
    monkeypatch.setattr(
        editor_fonts,
        "_is_smoothly_scalable",
        raise_runtime_error,
    )
    assert editor_fonts.is_editor_safe_font_family("Broken Mono") is False


def test_editor_font_family_falls_back_to_installed_safe_family(monkeypatch):
    monkeypatch.setattr(editor_fonts, "_families", lambda: ["Project Mono"])
    monkeypatch.setattr(
        editor_fonts,
        "EDITOR_FONT_FALLBACKS",
        ("Missing Fallback",),
    )
    monkeypatch.setattr(
        editor_fonts,
        "_is_smoothly_scalable",
        lambda family: family == "Project Mono",
    )

    assert editor_fonts.editor_font_family("Missing Preferred") == "Project Mono"


def test_editor_font_family_returns_default_when_no_safe_fonts(monkeypatch):
    monkeypatch.setattr(editor_fonts, "_families", lambda: ["Laggy Display"])
    monkeypatch.setattr(
        editor_fonts,
        "EDITOR_FONT_FALLBACKS",
        ("Missing Fallback",),
    )
    monkeypatch.setattr(
        editor_fonts,
        "_is_smoothly_scalable",
        lambda family: False,
    )

    assert editor_fonts.editor_font_family("Missing Preferred") == "Consolas"


class GuideStyleHarness:
    def __init__(self):
        self.indentation_guides = None
        self.scintilla_calls = []

    def setIndentationGuides(self, enabled):
        self.indentation_guides = enabled

    def SendScintilla(self, *args):
        self.scintilla_calls.append(args)


class DictSettings:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


def test_editor_configurator_disables_builtin_indentation_guides():
    editor = GuideStyleHarness()
    settings = DictSettings({
        "editor.show_indentation_guides": True,
        "editor.theme": "default_dark",
        "editor.custom_theme.base": "dark",
    })

    EditorConfigurator._apply_indentation_guides(editor, settings)

    assert editor.indentation_guides is False
    assert editor.scintilla_calls == [(2132, 0)]

    disabled = GuideStyleHarness()
    disabled_settings = DictSettings({
        "editor.show_indentation_guides": False,
    })

    EditorConfigurator._apply_indentation_guides(disabled, disabled_settings)

    assert disabled.indentation_guides is False
    assert disabled.scintilla_calls == [(2132, 0)]


class GuideIndentHarness:
    def __init__(self, lines):
        self.lines = lines

    _indent_columns = staticmethod(CodeEditor._indent_columns)

    def text(self, line):
        return self.lines[line]


def test_custom_indentation_guide_helpers_count_and_merge_lines():
    harness = GuideIndentHarness([
        "def greet():\n",
        "    print('hi')\n",
        "\n",
    ])

    assert CodeEditor._indent_columns("  \tvalue", 4) == 4
    assert CodeEditor._effective_guide_indent_columns(harness, 1, 4) == 4
    assert CodeEditor._effective_guide_indent_columns(harness, 2, 4) == 4
    assert CodeEditor._merge_line_segments([(0, 10), (10, 20), (30, 35)]) == [
        (0, 20),
        (30, 35),
    ]


def test_indent_overlay_delegates_painting_and_ends_painter(monkeypatch, qapp, tmp_path):
    editor = make_editor(qapp, tmp_path)
    painters = []
    seen = []

    class FakePainter:
        def __init__(self, widget):
            self.widget = widget
            self.ended = False
            painters.append(self)

        def end(self):
            self.ended = True

    monkeypatch.setattr(code_editor_module, "QPainter", FakePainter)
    editor._draw_indentation_guides = lambda painter: seen.append(painter)

    editor._indent_guide_overlay.paintEvent(None)

    assert seen == painters
    assert painters[0].widget is editor._indent_guide_overlay
    assert painters[0].ended is True
    editor.deleteLater()


class GuidePainterHarness:
    def __init__(self):
        self.render_hints = []
        self.pens = []
        self.lines = []

    def setRenderHint(self, *args):
        self.render_hints.append(args)

    def setPen(self, pen):
        self.pens.append(pen)

    def drawLine(self, x1, y1, x2, y2):
        self.lines.append((x1, y1, x2, y2))


class DrawGuidesHarness:
    _merge_line_segments = staticmethod(CodeEditor._merge_line_segments)

    def __init__(
        self,
        settings,
        *,
        visible_range=(0, 1),
        indents=None,
        y_positions=None,
        line_heights=None,
        width=100,
        height=100,
    ):
        self._settings = DictSettings(settings)
        self.visible_range = visible_range
        self.indents = indents or {0: 4}
        self.y_positions = y_positions or {0: 0}
        self.line_heights = line_heights or {0: 10}
        self._width = width
        self._height = height
        self.guide_columns = []

    def _visible_document_line_range(self):
        return self.visible_range

    def _effective_guide_indent_columns(self, line, tab_width):
        return self.indents.get(line, 0)

    def _line_y(self, line):
        return self.y_positions.get(line, 0)

    def _line_height(self, line):
        return self.line_heights.get(line, 10)

    def _guide_column_x(self, line, column):
        self.guide_columns.append((line, column))
        return column * 3

    def width(self):
        return self._width

    def height(self):
        return self._height


def test_draw_indentation_guides_returns_for_disabled_invalid_and_empty_ranges():
    base = {
        "editor.show_indentation_guides": False,
        "editor.tab_width": 4,
        "editor.theme": "default_dark",
        "editor.custom_theme.base": "dark",
    }
    disabled = DrawGuidesHarness(base)
    disabled_painter = GuidePainterHarness()

    CodeEditor._draw_indentation_guides(disabled, disabled_painter)

    assert disabled_painter.lines == []
    assert disabled_painter.pens == []

    invalid_tab = DrawGuidesHarness({
        **base,
        "editor.show_indentation_guides": True,
        "editor.tab_width": -1,
    })
    invalid_painter = GuidePainterHarness()

    CodeEditor._draw_indentation_guides(invalid_tab, invalid_painter)

    assert invalid_painter.lines == []
    assert invalid_painter.pens == []

    empty_range = DrawGuidesHarness({
        **base,
        "editor.show_indentation_guides": True,
    }, visible_range=(3, 3))
    empty_painter = GuidePainterHarness()

    CodeEditor._draw_indentation_guides(empty_range, empty_painter)

    assert empty_painter.lines == []
    assert empty_painter.pens == []


def test_draw_indentation_guides_uses_theme_colors_and_merges_segments():
    base = {
        "editor.show_indentation_guides": True,
        "editor.tab_width": 4,
        "editor.custom_theme.base": "dark",
    }

    expected_colors = {
        "default_high_contrast": "#ffffff",
        "default_dark": "#565e66",
        "default_light": "#b8c0c8",
    }
    for theme_name, expected_color in expected_colors.items():
        harness = DrawGuidesHarness({**base, "editor.theme": theme_name})
        painter = GuidePainterHarness()

        CodeEditor._draw_indentation_guides(harness, painter)

        assert painter.pens[0].color().name() == expected_color
        assert painter.lines == [(12, -1, 12, 11)]

    harness = DrawGuidesHarness(
        {**base, "editor.theme": "default_dark"},
        visible_range=(0, 4),
        indents={0: 0, 1: 4, 2: 8, 3: 4},
        y_positions={0: 0, 1: 0, 2: 10, 3: 150},
        line_heights={0: 10, 1: 10, 2: 10, 3: 10},
        height=50,
    )
    painter = GuidePainterHarness()

    CodeEditor._draw_indentation_guides(harness, painter)

    assert harness.guide_columns == [(1, 4), (2, 4), (2, 8)]
    assert painter.lines == [
        (12, -1, 12, 21),
        (24, 9, 24, 21),
    ]


class VisibleRangeHarness:
    def __init__(self):
        self.send_calls = []

    def firstVisibleLine(self):
        return 5

    def SendScintilla(self, message):
        self.send_calls.append(message)
        return 10

    def lines(self):
        return 20


class VisibleRangeFallbackHarness:
    def SendScintilla(self, _message):
        raise RuntimeError("Scintilla unavailable")

    def height(self):
        return 25

    def fontMetrics(self):
        return SimpleNamespace(height=lambda: 10)

    def lines(self):
        return 1


def test_visible_document_line_range_uses_scintilla_and_widget_fallbacks():
    normal = VisibleRangeHarness()

    assert CodeEditor._visible_document_line_range(normal) == (5, 17)
    assert normal.send_calls == [2370]

    fallback = VisibleRangeFallbackHarness()

    assert CodeEditor._visible_document_line_range(fallback) == (0, 1)


class GeometryHarness:
    def __init__(self, *, find_column_raises=False, text_height_raises=False):
        self.find_column_raises = find_column_raises
        self.text_height_raises = text_height_raises
        self.calls = []
        self.positions = []

    def SendScintilla(self, message, *args):
        self.calls.append((message, *args))
        if message == 2456:
            if self.find_column_raises:
                raise RuntimeError("find column failed")
            return 17
        if message == 2164:
            return 34
        if message == 2165:
            return 7
        if message == 2279:
            if self.text_height_raises:
                raise TypeError("height failed")
            return 16
        raise AssertionError(message)

    def positionFromLineIndex(self, line, column):
        self.positions.append((line, column))
        return 99

    def text(self, _line):
        return "abc"

    def fontMetrics(self):
        return SimpleNamespace(height=lambda: 13)


def test_guide_geometry_helpers_use_scintilla_and_fallback_paths():
    normal = GeometryHarness()

    assert CodeEditor._guide_column_x(normal, 2, 8) == 34
    assert normal.calls[:2] == [(2456, 2, 8), (2164, 0, 17)]
    assert CodeEditor._line_y(normal, 3) == 7
    assert normal.positions == [(3, 0)]
    assert CodeEditor._line_height(normal, 4) == 16

    fallback = GeometryHarness(find_column_raises=True, text_height_raises=True)

    assert CodeEditor._guide_column_x(fallback, 2, 8) == 34
    assert fallback.positions == [(2, 3)]
    assert CodeEditor._line_height(fallback, 4) == 13


def test_display_name_settings_modification_zoom_and_margin_helpers(qapp, tmp_path):
    editor = make_editor(qapp, tmp_path)
    seen = []
    editor.modification_changed.connect(seen.append)

    assert editor.display_name == "Untitled"
    editor.file_path = str(tmp_path / "demo.py")
    assert editor.display_name == "demo.py"
    assert editor.is_modified is False

    updated_settings = Settings(tmp_path)
    updated_settings.set("editor.auto_complete", False)
    updated_settings.set("editor.show_line_numbers", True)
    editor.apply_settings(updated_settings)
    editor._on_modification_changed(True)

    editor.setText("one\n" * 120)
    editor.zoomIn(1)
    editor.zoomOut(1)
    editor.zoomTo(10)
    editor._update_margin_width()
    editor.refresh_marker_colors()

    assert editor._settings is updated_settings
    assert seen[0] is True
    assert all(value is True for value in seen)
    assert editor.marginWidth(0) > 0
    editor.deleteLater()


def test_ctrl_wheel_refreshes_margin_width(qapp, tmp_path):
    editor = make_editor(qapp, tmp_path)
    calls = []
    editor._update_margin_width = lambda: calls.append("margin")

    event = QWheelEvent(
        QPointF(1, 1),
        QPointF(1, 1),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ControlModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )

    editor.wheelEvent(event)

    assert calls
    editor.deleteLater()


class CommentHarness:
    def __init__(self, lines, *, selected=True, selection=(0, 0, 0, 0), cursor=(0, 0)):
        self.lines = list(lines)
        self.selected = selected
        self.selection = selection
        self.cursor = cursor
        self.undo_started = 0
        self.undo_ended = 0
        self.replacements = []

    def hasSelectedText(self):
        return self.selected

    def getSelection(self):
        return self.selection

    def getCursorPosition(self):
        return self.cursor

    def text(self, line):
        return self.lines[line]

    def beginUndoAction(self):
        self.undo_started += 1

    def endUndoAction(self):
        self.undo_ended += 1

    def setSelection(self, line_from, col_from, line_to, col_to):
        self.selection = (line_from, col_from, line_to, col_to)
        self.selected = True

    def replaceSelectedText(self, text):
        self.replacements.append(text)
        line_from, col_from, line_to, col_to = self.selection
        replacement_text = (
            self.lines[line_from][:col_from]
            + text
            + self.lines[line_to][col_to:]
        )
        replacement = replacement_text.splitlines(keepends=True)
        self.lines[line_from:line_to + 1] = replacement

    def _breakpoints_supported(self):
        return True


def test_toggle_comment_handles_trailing_selection_blank_lines_and_line_endings():
    harness = CommentHarness(
        ["    x = 1\r\n", "\n", "next_line()\n"],
        selection=(0, 0, 2, 0),
    )

    CodeEditor.toggle_comment(harness)

    assert harness.lines[:2] == ["    # x = 1\r\n", "\n"]
    assert harness.lines[2] == "next_line()\n"
    assert harness.undo_started == 1
    assert harness.undo_ended == 1

    uncomment = CommentHarness(["    #value = 1"], selected=False, cursor=(0, 0))
    assert CodeEditor._selection_is_commented(uncomment) is True
    CodeEditor.toggle_comment(uncomment)
    assert uncomment.lines == ["    value = 1"]

    blank = CommentHarness(["    \n"], selected=False, cursor=(0, 0))
    assert CodeEditor._selection_is_commented(blank) is False
    CodeEditor.toggle_comment(blank)
    assert blank.replacements == []


class RecordingHandler:
    def __init__(self, return_value=False):
        self.return_value = return_value
        self.calls = []

    def handle_return(self):
        self.calls.append("return")
        return self.return_value

    def handle_backspace(self):
        self.calls.append("backspace")
        return self.return_value

    def handle_key(self, event):
        self.calls.append(("key", event.text()))
        return self.return_value


def test_key_press_event_routes_comment_indent_backspace_autoclose_and_fallback(qapp, tmp_path):
    editor = make_editor(qapp, tmp_path)
    calls = []
    editor.toggle_comment = lambda: calls.append("comment")

    editor.keyPressEvent(
        QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Slash,
            Qt.KeyboardModifier.ControlModifier,
            "/",
        )
    )
    assert calls == ["comment"]

    smart_indent = RecordingHandler(return_value=True)
    editor._smart_indent = smart_indent
    editor.keyPressEvent(
        QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Return,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    assert smart_indent.calls == ["return"]

    auto_close = RecordingHandler(return_value=True)
    editor._auto_close = auto_close
    editor.keyPressEvent(
        QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Backspace,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    editor.keyPressEvent(
        QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_ParenLeft,
            Qt.KeyboardModifier.NoModifier,
            "(",
        )
    )
    assert auto_close.calls == ["backspace", ("key", "(")]

    editor._smart_indent = RecordingHandler(return_value=False)
    editor._auto_close = RecordingHandler(return_value=False)
    editor.keyPressEvent(
        QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_A,
            Qt.KeyboardModifier.NoModifier,
            "a",
        )
    )
    assert editor._auto_close.calls == [("key", "a")]
    editor.deleteLater()


def test_ctrl_slash_does_not_comment_non_python_files(qapp, tmp_path):
    editor = make_editor(qapp, tmp_path)
    editor.file_path = str(tmp_path / "notes.txt")
    calls = []
    editor.toggle_comment = lambda: calls.append("comment")

    editor.keyPressEvent(
        QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Slash,
            Qt.KeyboardModifier.ControlModifier,
            "/",
        )
    )

    assert calls == []
    editor.deleteLater()


class FakePoint:
    def __init__(self, x=0, y=0):
        self._x = x
        self._y = y

    def x(self):
        return self._x

    def y(self):
        return self._y


class FakeTooltipEvent:
    def __init__(self, pos_result=7, tooltip="E001: bad"):
        self.pos_result = pos_result
        self.tooltip = tooltip

    def type(self):
        return QEvent.Type.ToolTip

    def pos(self):
        return FakePoint(2, 3)

    def globalPos(self):
        return QPoint(20, 30)


class TooltipHarness:
    def __init__(self, pos_result=7, tooltip="E001: bad"):
        self.pos_result = pos_result
        self.tooltip = tooltip

    def SendScintilla(self, *_args):
        return self.pos_result

    def lineIndexFromPosition(self, _pos):
        return 3, 4

    def _get_lint_tooltip(self, line, col):
        assert (line, col) == (3, 4)
        return self.tooltip


def test_tooltip_event_shows_lint_message_or_hides_when_missing(monkeypatch):
    tooltip_calls = []
    monkeypatch.setattr(
        code_editor_module,
        "QToolTip",
        SimpleNamespace(
            showText=lambda pos, text, widget: tooltip_calls.append(("show", pos, text, widget)),
            hideText=lambda: tooltip_calls.append(("hide",)),
        ),
    )

    shown = TooltipHarness(tooltip="F821: undefined")
    assert CodeEditor.event(shown, FakeTooltipEvent()) is True
    assert tooltip_calls[0][0] == "show"
    assert tooltip_calls[0][2] == "F821: undefined"

    hidden = TooltipHarness(tooltip=None)
    assert CodeEditor.event(hidden, FakeTooltipEvent()) is True
    assert tooltip_calls[-1] == ("hide",)

    off_editor = TooltipHarness(pos_result=-1)
    assert CodeEditor.event(off_editor, FakeTooltipEvent()) is True
    assert tooltip_calls[-1] == ("hide",)


class FakeMimeData:
    def __init__(self, has_urls):
        self._has_urls = has_urls

    def hasUrls(self):
        return self._has_urls


class FakeDropEvent:
    def __init__(self):
        self.accepted = 0
        self.ignored = 0
        self.mime = FakeMimeData(True)

    def mimeData(self):
        return self.mime

    def acceptProposedAction(self):
        self.accepted += 1

    def ignore(self):
        self.ignored += 1


class DropHarness:
    def __init__(self):
        self.forwarded = []

    def window(self):
        return SimpleNamespace(dropEvent=lambda event: self.forwarded.append(event))


def test_drag_and_drop_url_events_accept_and_forward_to_window():
    harness = DropHarness()
    event = FakeDropEvent()

    CodeEditor.dragEnterEvent(harness, event)
    CodeEditor.dragMoveEvent(harness, event)
    CodeEditor.dropEvent(harness, event)

    assert event.accepted == 2
    assert event.ignored == 1
    assert harness.forwarded == [event]


class FakeAction:
    def __init__(self, text):
        self.text = text
        self.tooltip = None
        self.shortcut = None
        self.triggered = DummySignal()

    def setToolTip(self, value):
        self.tooltip = value

    def setShortcut(self, value):
        self.shortcut = value


class FakeMenu:
    def __init__(self):
        self.entries = []
        self.exec_pos = None

    def addSeparator(self):
        self.entries.append("separator")

    def addAction(self, text):
        action = FakeAction(text)
        self.entries.append(action)
        return action

    def exec(self, pos):
        self.exec_pos = pos
        for entry in list(self.entries):
            if isinstance(entry, FakeAction):
                entry.triggered.emit()


class FakeContextEvent:
    def pos(self):
        return FakePoint(5, 6)

    def globalPos(self):
        return QPoint(50, 60)


class ContextHarness:
    def __init__(
        self,
        *,
        selected=True,
        commented=False,
        word="for",
        func_info=("def f():", 1),
        pos=10,
        python_mode=True,
    ):
        self.menu = FakeMenu()
        self.selected = selected
        self.commented = commented
        self.word = word
        self.func_info = func_info
        self.pos = pos
        self.python_mode = python_mode
        self.ai_explain_requested = DummySignal()
        self.ai_improve_requested = DummySignal()
        self.ai_docstring_requested = DummySignal()
        self.explained = []
        self.improved = []
        self.docstrings = []
        self.keyword_help = []
        self.comments = 0
        self.ai_explain_requested.connect(lambda text: self.explained.append(text))
        self.ai_improve_requested.connect(lambda text: self.improved.append(text))
        self.ai_docstring_requested.connect(lambda code, line: self.docstrings.append((code, line)))

    def createStandardContextMenu(self):
        return self.menu

    def SendScintilla(self, *_args):
        return self.pos

    def lineIndexFromPosition(self, _pos):
        return 2, 4

    def wordAtLineIndex(self, *_args):
        return self.word

    def _selection_is_commented(self):
        return self.commented

    def _breakpoints_supported(self):
        return self.python_mode

    def hasSelectedText(self):
        return self.selected

    def selectedText(self):
        return "x = 1"

    def _find_enclosing_def(self, line):
        assert line in (-1, 2)
        return self.func_info

    def _show_keyword_help(self, word, pos):
        self.keyword_help.append((word, pos))

    def toggle_comment(self):
        self.comments += 1


def test_context_menu_builds_keyword_ai_comment_and_docstring_actions():
    harness = ContextHarness(func_info=("def f():\n    pass", 1))

    CodeEditor.contextMenuEvent(harness, FakeContextEvent())

    action_texts = [entry.text for entry in harness.menu.entries if isinstance(entry, FakeAction)]
    assert "Comment Selection" in action_texts
    assert 'What does "for" mean?' in action_texts
    assert "Explain this code..." in action_texts
    assert "Review && improve..." in action_texts
    assert "Generate docstring..." in action_texts
    assert harness.menu.exec_pos == QPoint(50, 60)
    assert harness.comments == 1
    assert harness.keyword_help == [("for", QPoint(50, 60))]
    assert harness.explained == ["x = 1"]
    assert harness.improved == ["x = 1"]
    assert harness.docstrings == [("def f():\n    pass", 1)]


def test_context_menu_uses_line_comment_label_without_selection():
    harness = ContextHarness(
        selected=False,
        commented=True,
        word="",
        func_info=None,
        pos=-1,
    )

    CodeEditor.contextMenuEvent(harness, FakeContextEvent())

    action_texts = [entry.text for entry in harness.menu.entries if isinstance(entry, FakeAction)]
    assert action_texts == ["Uncomment Line"]
    assert harness.comments == 1


def test_context_menu_skips_python_keyword_and_docstring_actions_for_non_python_file():
    harness = ContextHarness(
        selected=False,
        word="for",
        func_info=("def f():\n    pass", 1),
        python_mode=False,
    )

    CodeEditor.contextMenuEvent(harness, FakeContextEvent())

    action_texts = [entry.text for entry in harness.menu.entries if isinstance(entry, FakeAction)]
    assert 'What does "for" mean?' not in action_texts
    assert "Generate docstring..." not in action_texts
    assert "Comment Line" not in action_texts
    assert "Comment Selection" not in action_texts
    assert "Uncomment Line" not in action_texts
    assert action_texts == []
    assert harness.comments == 0
    assert harness.keyword_help == []
    assert harness.docstrings == []


def test_context_menu_uses_text_ai_action_for_non_python_selection():
    harness = ContextHarness(
        selected=True,
        word="for",
        func_info=("def f():\n    pass", 1),
        python_mode=False,
    )

    CodeEditor.contextMenuEvent(harness, FakeContextEvent())

    action_texts = [entry.text for entry in harness.menu.entries if isinstance(entry, FakeAction)]
    assert "Explain this text..." in action_texts
    assert "Explain this code..." not in action_texts
    assert "Review && improve..." not in action_texts
    assert 'What does "for" mean?' not in action_texts
    assert "Generate docstring..." not in action_texts
    assert harness.explained == ["x = 1"]
    assert harness.improved == []
    assert harness.docstrings == []


def test_keyword_help_popup_handles_missing_and_known_keyword(monkeypatch, qapp, tmp_path):
    from meadowpy.ui import keyword_help_popup as popup_module

    popups = []

    class FakeKeywordHelpPopup:
        def __init__(self, word, explanation, example, parent=None):
            self.word = word
            self.explanation = explanation
            self.example = example
            self.parent = parent
            self.moved_to = None
            self.shown = False
            popups.append(self)

        def move(self, pos):
            self.moved_to = pos

        def show(self):
            self.shown = True

    monkeypatch.setattr(popup_module, "KeywordHelpPopup", FakeKeywordHelpPopup)
    editor = make_editor(qapp, tmp_path)

    editor._show_keyword_help("definitely_missing", QPoint(1, 2))
    editor._show_keyword_help("for", QPoint(3, 4))

    assert len(popups) == 1
    assert popups[0].word == "for"
    assert popups[0].moved_to == QPoint(3, 4)
    assert popups[0].shown is True

    editor.file_path = str(tmp_path / "notes.txt")
    editor._show_keyword_help("for", QPoint(5, 6))
    assert len(popups) == 1

    editor.deleteLater()


def test_find_enclosing_def_handles_negative_missing_backslash_signature_and_body(qapp, tmp_path):
    editor = make_editor(qapp, tmp_path)
    editor.setText(
        "value = 1\n"
        "\n"
        "def greet(name, \\\n"
        "          title):\n"
        "    full = f'{title} {name}'\n"
        "\n"
        "    return full\n"
        "\n"
        "print(greet('Ada', 'Dr.'))\n"
    )

    assert editor._find_enclosing_def(-1) is None
    assert editor._find_enclosing_def(0) is None

    func_code, insert_line = editor._find_enclosing_def(6)

    assert insert_line == 4
    assert "def greet(name, \\" in func_code
    assert "          title):" in func_code
    assert "return full" in func_code
    assert "print(greet" not in func_code
    editor.deleteLater()


def test_margin_clicks_lint_tooltip_edges_and_clear_paths(qapp, tmp_path):
    editor = make_editor(qapp, tmp_path)
    editor.setText("abc\n\nwarn = 1\n")

    editor._on_margin_clicked(1, 0, None)
    assert editor.get_breakpoints() == set()
    editor._on_margin_clicked(2, 0, None)
    assert editor.get_breakpoints() == {0}
    editor.clear_breakpoints()
    assert editor.get_breakpoints() == set()

    warning = SimpleNamespace(
        line=0,
        column=99,
        code="W001",
        message="tail warning",
        severity="warning",
    )
    negative_col = SimpleNamespace(
        line=2,
        column=-10,
        code="E002",
        message="start error",
        severity="error",
    )
    blank_line = SimpleNamespace(
        line=1,
        column=0,
        code="E003",
        message="blank line",
        severity="error",
    )
    editor.set_lint_issues([warning, negative_col, blank_line])

    assert editor._get_lint_tooltip(0, 2) == "W001: tail warning"
    assert editor._get_lint_tooltip(0, 3) is None
    assert editor._get_lint_tooltip(2, 0) == "E002: start error"

    editor.clear_lint_markers()
    editor.refresh_lint_colors()
    editor.setText("")
    editor.clear_lint_markers()
    editor.deleteLater()

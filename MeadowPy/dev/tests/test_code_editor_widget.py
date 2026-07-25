from __future__ import annotations

from types import SimpleNamespace

import meadowpy.editor.code_editor as code_editor_module
import meadowpy.editor.editor_fonts as editor_fonts
import pytest
from helpers import DummySignal
from PyQt6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import QColor, QHelpEvent, QImage, QKeyEvent, QMouseEvent, QPainter, QWheelEvent
from PyQt6.Qsci import (
    QsciLexerJSON,
    QsciLexerMarkdown,
    QsciLexerProperties,
    QsciLexerPython,
    QsciLexerYAML,
    QsciScintilla,
)

from meadowpy.core.file_types import SyntaxLanguage, syntax_language_for_path
from meadowpy.core.settings import Settings
from meadowpy.editor.code_editor import CodeEditor
from meadowpy.editor.editor_config import EditorConfigurator
from meadowpy.editor.lexer_profiles import get_lexer_profile
from meadowpy.editor.themes import get_theme
from meadowpy.resources.resource_loader import get_stylesheet


def make_editor(qapp, tmp_path) -> CodeEditor:
    settings = Settings(tmp_path)
    settings.set("editor.auto_complete", False)
    editor = CodeEditor(settings)
    return editor


def dispose_editor(qapp, editor: CodeEditor) -> None:
    """Close a native editor and flush its deferred Qt destruction."""
    editor.close()
    editor.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()


def _colorise(editor: CodeEditor) -> None:
    editor.SendScintilla(QsciScintilla.SCI_COLOURISE, 0, -1)


def _style_at(
    editor: CodeEditor,
    source: str,
    token: str,
    start: int = 0,
) -> int:
    """Return the lexer style at the token's first byte after ``start``."""
    character_position = source.index(token, start)
    byte_position = len(source[:character_position].encode("utf-8"))
    return int(
        editor.SendScintilla(QsciScintilla.SCI_GETSTYLEAT, byte_position)
    )


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


def test_breakpoint_marker_pixmaps_are_flat_centered_and_dpr_aware(qapp):
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
    hidpi = CodeEditor._breakpoint_marker_pixmap(
        QColor("#E9483F"),
        QColor("#9E2F2B"),
        filled=True,
        logical_size=size,
        device_pixel_ratio=2.0,
    )

    assert marker.pixelColor(0, 0).alpha() == 0
    assert ghost.pixelColor(0, 0).alpha() == 0

    center = marker.pixelColor(size // 2, size // 2)
    lower_center = marker.pixelColor(size // 2, size // 2 + 2)
    ghost_center = ghost.pixelColor(size // 2, size // 2)
    assert center.alpha() > 220
    assert center.red() > 220
    assert center.green() < 120
    # Flat artwork deliberately has no legacy top-to-bottom gradient.
    assert lower_center == center
    assert ghost_center.alpha() < center.alpha()
    assert hidpi.devicePixelRatio() == 2.0
    assert hidpi.width() == size * 2
    assert hidpi.height() == size * 2

    # Corners stay transparent even though antialiasing softens the circle.
    assert marker.pixelColor(0, 0).alpha() == 0
    assert marker.pixelColor(size - 1, size - 1).alpha() == 0
    assert ghost.pixelColor(0, 0).alpha() == 0
    assert ghost.pixelColor(size - 1, size - 1).alpha() == 0


@pytest.mark.parametrize("symbol", ["plus", "minus", "slash"])
def test_breakpoint_marker_symbol_variants_render(qapp, symbol):
    image = CodeEditor._breakpoint_marker_pixmap(
        QColor("#FF5C57"),
        QColor("#FFFFFF"),
        filled=symbol != "plus",
        symbol=symbol,
        symbol_color=QColor("#000000"),
    ).toImage()

    center = code_editor_module.BREAKPOINT_MARKER_SIZE // 2
    assert image.pixelColor(center, center).alpha() > 0


def test_breakpoints_follow_editor_marker_line_changes(qapp, tmp_path):
    editor = make_editor(qapp, tmp_path)
    editor.setText("first\nsecond\nthird\n")

    editor.toggle_breakpoint(1)
    editor.insertAt("inserted\n", 0, 0)

    assert editor.get_breakpoints() == {2}

    editor.toggle_breakpoint(2)
    assert editor.get_breakpoints() == set()
    editor.deleteLater()


def test_breakpoints_on_non_code_lines_resolve_forward_but_never_backward(
    qapp,
    tmp_path,
):
    editor = make_editor(qapp, tmp_path)
    editor.setText("# heading\n\nvalue = 1\n# trailing\n\n")

    editor.toggle_breakpoint(0)
    assert editor.get_breakpoints() == {2}

    editor.toggle_breakpoint(1)
    assert editor.get_breakpoints() == set()

    editor.toggle_breakpoint(3)
    assert editor.get_breakpoints() == set()

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


def test_breakpoints_changed_emits_effective_sets_and_path_resync(
    qapp,
    tmp_path,
):
    editor = make_editor(qapp, tmp_path)
    editor.setText("first = 1\nsecond = 2\n")
    changes = []
    editor.breakpoints_changed.connect(lambda lines: changes.append(set(lines)))

    editor.toggle_breakpoint(1)
    assert changes == [{1}]

    # Scintilla marker handles follow edits; the public signal reports the
    # moved effective line rather than the stale requested line.
    editor.insertAt("inserted = 0\n", 0, 0)
    assert changes[-1] == {2}

    editor.file_path = str(tmp_path / "renamed.py")
    assert changes[-1] == {2}
    assert changes.count({2}) >= 2

    editor.toggle_breakpoint(2)
    assert changes[-1] == set()
    before = len(changes)
    editor.clear_breakpoints()
    assert len(changes) == before
    dispose_editor(qapp, editor)


def test_breakpoint_verification_and_combined_current_line_states(
    qapp,
    tmp_path,
):
    editor = make_editor(qapp, tmp_path)
    editor.setText("print('ready')\n")
    editor.toggle_breakpoint(0)
    assert editor.get_breakpoint_state(0) == code_editor_module.BreakpointState.ACCEPTED

    editor.set_current_line(0)
    markers = editor.markersAtLine(0)
    assert markers & (1 << code_editor_module.MARKER_BREAKPOINT_CURRENT)

    editor.mark_breakpoints_pending()
    assert editor.get_breakpoint_state(0) == code_editor_module.BreakpointState.PENDING
    markers = editor.markersAtLine(0)
    assert markers & (1 << code_editor_module.MARKER_BREAKPOINT_PENDING_CURRENT)

    editor.set_breakpoint_verification([], {0: "the debugger skipped this line"})
    assert editor.get_breakpoint_state(0) == code_editor_module.BreakpointState.REJECTED
    assert editor.get_breakpoint_rejection_reason(0) == "the debugger skipped this line"
    markers = editor.markersAtLine(0)
    assert markers & (1 << code_editor_module.MARKER_BREAKPOINT_REJECTED_CURRENT)

    editor.set_breakpoint_verification([0])
    assert editor.get_breakpoint_state(0) == code_editor_module.BreakpointState.ACCEPTED
    assert editor.get_breakpoint_rejection_reason(0) is None

    # Removing a breakpoint while paused restores the standalone execution
    # chevron rather than erasing the current-line location.
    editor.clear_breakpoints()
    markers = editor.markersAtLine(0)
    assert markers & (1 << code_editor_module.MARKER_CURRENT_LINE)
    dispose_editor(qapp, editor)


def test_visible_adjacent_breakpoint_current_markers_repaint_safely(
    qapp,
    tmp_path,
):
    editor = make_editor(qapp, tmp_path)
    try:
        editor.file_path = str(tmp_path / "adjacent.py")
        editor.setText("print('first')\nprint('second')\n")
        editor.toggle_breakpoint(0)
        editor.toggle_breakpoint(1)
        editor.show()
        qapp.processEvents()

        editor.set_current_line(0)
        editor.repaint()
        qapp.processEvents()
        editor.clear_current_line()
        editor.set_current_line(1)
        editor.repaint()
        qapp.processEvents()

        assert editor.get_breakpoint_state(0) == (
            code_editor_module.BreakpointState.ACCEPTED
        )
        assert editor.get_breakpoint_state(1) == (
            code_editor_module.BreakpointState.ACCEPTED
        )
        assert editor.markersAtLine(1) & (
            1 << code_editor_module.MARKER_BREAKPOINT_CURRENT
        )
    finally:
        dispose_editor(qapp, editor)


def test_paused_breakpoint_remove_hover_uses_topmost_combined_marker(
    qapp,
    tmp_path,
):
    editor = make_editor(qapp, tmp_path)
    editor.setText("print('paused')\n")
    editor.toggle_breakpoint(0)
    editor.set_current_line(0)

    editor._set_phantom_breakpoint(0, remove=True)

    markers = editor.markersAtLine(0)
    combined_hover = code_editor_module.MARKER_BREAKPOINT_CURRENT_HOVER_REMOVE
    assert combined_hover > code_editor_module.MARKER_BREAKPOINT_REJECTED_CURRENT
    assert markers & (1 << combined_hover)
    assert editor._phantom_breakpoint_marker == combined_hover

    editor.clear_current_line()

    markers = editor.markersAtLine(0)
    current_mask = sum(
        1 << marker
        for marker in (
            code_editor_module.MARKER_CURRENT_LINE,
            code_editor_module.MARKER_BREAKPOINT_CURRENT,
            code_editor_module.MARKER_BREAKPOINT_PENDING_CURRENT,
            code_editor_module.MARKER_BREAKPOINT_REJECTED_CURRENT,
            code_editor_module.MARKER_BREAKPOINT_CURRENT_HOVER_REMOVE,
            code_editor_module.MARKER_CURRENT_LINE_HOVER_ADD,
        )
    )
    assert not (markers & current_mask)
    assert editor._phantom_breakpoint_line is None
    dispose_editor(qapp, editor)


def test_breakpoint_on_line_made_non_executable_remains_removable(
    qapp,
    tmp_path,
):
    editor = make_editor(qapp, tmp_path)
    editor.setText("first = 1\nsecond = 2\nthird = 3\n")
    editor.toggle_breakpoint(1)
    editor.setSelection(1, 0, 1, len("second = 2"))
    editor.replaceSelectedText("# no longer executable")

    assert editor.get_breakpoints() == {1}
    assert editor._resolve_breakpoint_line(1) == 2

    # The visible marker wins over forward resolution, so a click removes the
    # dot the user actually clicked instead of toggling line 3.
    editor.toggle_breakpoint(1)
    assert editor.get_breakpoints() == set()
    dispose_editor(qapp, editor)


def test_breakpoint_lane_hides_for_unsupported_files_and_line_numbers_ignore_clicks(
    qapp,
    tmp_path,
):
    editor = make_editor(qapp, tmp_path)
    editor.setText("print('ready')\n")

    editor._on_margin_clicked(0, 0, None)
    assert editor.get_breakpoints() == set()
    editor._on_margin_clicked(2, 0, None)
    assert editor.get_breakpoints() == {0}

    editor.file_path = str(tmp_path / "document.json")
    assert editor.marginWidth(2) == 0
    assert editor.marginSensitivity(2) is False
    assert editor.marginSensitivity(0) is False
    assert editor.get_breakpoints() == set()

    editor.file_path = str(tmp_path / "document.py")
    assert editor.marginWidth(2) >= code_editor_module.BREAKPOINT_MARGIN_WIDTH
    assert editor.marginSensitivity(2) is True
    dispose_editor(qapp, editor)


def test_breakpoint_resolution_is_forward_and_bounded(qapp, tmp_path):
    editor = make_editor(qapp, tmp_path)
    editor.setText("# heading\n\nvalue = 1\n")
    assert editor._resolve_breakpoint_line(0) == 2
    assert editor._resolve_breakpoint_line(2) == 2

    gap = code_editor_module.BREAKPOINT_FORWARD_SEARCH_LIMIT + 1
    editor.setText("# heading\n" + ("\n" * gap) + "value = 1\n")
    assert editor._resolve_breakpoint_line(0) is None
    dispose_editor(qapp, editor)


def _relative_luminance(color: QColor) -> float:
    channels = []
    for value in (color.redF(), color.greenF(), color.blueF()):
        channels.append(
            value / 12.92
            if value <= 0.04045
            else ((value + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast_ratio(first: str, second: str) -> float:
    first_luminance = _relative_luminance(QColor(first))
    second_luminance = _relative_luminance(QColor(second))
    lighter = max(first_luminance, second_luminance)
    darker = min(first_luminance, second_luminance)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.mark.parametrize(
    "theme_name",
    ["default_light", "default_dark", "default_high_contrast"],
)
def test_breakpoint_semantic_hover_tokens_exceed_three_to_one(theme_name):
    theme = get_theme(theme_name)

    assert _contrast_ratio(theme.breakpoint_hover_add, theme.margin_background) >= 3.0
    assert _contrast_ratio(theme.breakpoint_hover_remove, theme.margin_background) >= 3.0
    for color in (
        theme.breakpoint_active,
        theme.breakpoint_pending,
        theme.breakpoint_rejected,
        theme.current_execution,
    ):
        assert QColor(color).isValid()


def test_breakpoint_artwork_responds_to_editor_zoom(qapp, tmp_path):
    editor = make_editor(qapp, tmp_path)
    editor.setText("print('zoom')\n")
    before_size = editor._breakpoint_marker_logical_size()
    before_width = editor.marginWidth(2)

    editor.zoomIn(8)

    assert editor._breakpoint_marker_logical_size() > before_size
    assert editor.marginWidth(2) > before_width
    assert editor.marginWidth(2) == editor._breakpoint_marker_logical_size() + 8
    dispose_editor(qapp, editor)


@pytest.mark.parametrize(
    ("theme_name", "custom_base"),
    [
        ("default_light", "light"),
        ("default_dark", "dark"),
        ("default_high_contrast", "dark"),
        ("custom", "light"),
    ],
)
@pytest.mark.parametrize("device_pixel_ratio", [1.0, 2.0])
def test_rendered_breakpoint_lane_uses_theme_color_at_each_dpr(
    qapp,
    tmp_path,
    theme_name,
    custom_base,
    device_pixel_ratio,
):
    settings = Settings(tmp_path)
    settings.set("editor.auto_complete", False)
    settings.set("editor.theme", theme_name)
    settings.set("editor.custom_theme.base", custom_base)
    editor = CodeEditor(settings)
    try:
        editor._marker_device_pixel_ratio = lambda: device_pixel_ratio
        editor.refresh_marker_colors()
        editor.setText("print('rendered')\n")
        editor.toggle_breakpoint(0)
        editor.resize(360, 90)
        editor.show()
        qapp.processEvents()

        physical_width = round(editor.width() * device_pixel_ratio)
        physical_height = round(editor.height() * device_pixel_ratio)
        image = QImage(
            physical_width,
            physical_height,
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        image.setDevicePixelRatio(device_pixel_ratio)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        try:
            editor.render(painter)
        finally:
            painter.end()

        lane_start = editor.marginWidth(0) + editor.marginWidth(1)
        lane_end = lane_start + editor.marginWidth(2)
        pixel_start = round(lane_start * device_pixel_ratio)
        pixel_end = round(lane_end * device_pixel_ratio)
        expected = QColor(
            get_theme(theme_name, custom_base).breakpoint_active
        )

        matching_pixels = 0
        for x in range(pixel_start, pixel_end):
            for y in range(image.height()):
                actual = image.pixelColor(x, y)
                distance = (
                    abs(actual.red() - expected.red())
                    + abs(actual.green() - expected.green())
                    + abs(actual.blue() - expected.blue())
                )
                if actual.alpha() > 200 and distance <= 18:
                    matching_pixels += 1

        assert matching_pixels >= round(8 * device_pixel_ratio**2)
    finally:
        dispose_editor(qapp, editor)


def test_marker_lines_uses_scintilla_marker_next_not_document_scan():
    class MarkerHarness:
        def __init__(self):
            self.calls = []

        def lines(self):
            return 1_000_000

        def SendScintilla(self, message, start, mask):
            self.calls.append((message, start, mask))
            return {0: 10, 11: 500_000, 500_001: -1}[start]

    harness = MarkerHarness()
    mask = 1 << code_editor_module.MARKER_BREAKPOINT

    assert list(CodeEditor._marker_lines(harness, mask)) == [10, 500_000]
    assert harness.calls == [
        (2047, 0, mask),
        (2047, 11, mask),
        (2047, 500_001, mask),
    ]


def test_repeated_breakpoint_resolution_binary_searches_cached_index():
    class BisectOnlySequence:
        def __init__(self, length):
            self.length = length
            self.item_reads = 0

        def __len__(self):
            return self.length

        def __getitem__(self, index):
            self.item_reads += 1
            return index * 2

        def __iter__(self):
            raise AssertionError("breakpoint resolution scanned the cache")

    class ResolutionHarness:
        _sorted_breakable_lines = CodeEditor._sorted_breakable_lines

        def __init__(self):
            self.index = BisectOnlySequence(1_000_000)
            self._sorted_breakable_lines_cache = self.index

        def lines(self):
            return 2_000_000

        def _breakable_lines(self):
            raise AssertionError("the cached index was rebuilt")

    harness = ResolutionHarness()
    for _ in range(20):
        assert CodeEditor._resolve_breakpoint_line(harness, 1_234_567) == 1_234_568

    # Twenty binary searches over one million entries need only a few hundred
    # indexed reads; iteration/sorting would trigger the guards above.
    assert harness.index.item_reads < 500


def test_breakable_line_ast_is_cached_until_text_changes(
    qapp,
    tmp_path,
    monkeypatch,
):
    editor = make_editor(qapp, tmp_path)
    editor.setText("value = 1\n")
    real_parse = code_editor_module.ast.parse
    parsed_sources = []

    def recording_parse(source):
        parsed_sources.append(source)
        return real_parse(source)

    monkeypatch.setattr(code_editor_module.ast, "parse", recording_parse)
    assert editor._breakable_lines() == {0}
    first_sorted_cache = editor._sorted_breakable_lines_cache
    assert first_sorted_cache == (0,)
    assert editor._breakable_lines() == {0}
    assert editor._sorted_breakable_lines_cache is first_sorted_cache
    assert len(parsed_sources) == 1

    editor.insertAt("other = 2\n", 0, 0)
    assert editor._breakable_lines() == {0, 1}
    assert editor._sorted_breakable_lines_cache == (0, 1)
    assert editor._sorted_breakable_lines_cache is not first_sorted_cache
    assert len(parsed_sources) == 2
    dispose_editor(qapp, editor)


def test_python_lexer_classifies_current_keywords_and_builtins(qapp, tmp_path):
    editor = make_editor(qapp, tmp_path)
    editor.file_path = str(tmp_path / "modern_python.py")
    source = (
        "async def fetch():\n"
        "    await work()\n"
        "    nonlocal state\n"
        "    return False, True\n"
        "\n"
        "print(exec)\n"
        "open('standalone')\n"
        "obj.open()\n"
    )
    editor.setText(source)
    _colorise(editor)

    for keyword in ("async", "await", "nonlocal", "False", "True"):
        assert _style_at(editor, source, keyword) == QsciLexerPython.Keyword

    for builtin_name in ("print", "exec"):
        observed_style = _style_at(editor, source, builtin_name)
        assert observed_style == QsciLexerPython.HighlightedIdentifier

    standalone_open = source.index("open('standalone')")
    attribute_open = source.index("obj.open") + len("obj.")
    standalone_style = _style_at(editor, source, "open", standalone_open)
    attribute_style = _style_at(editor, source, "open", attribute_open)
    assert standalone_style == QsciLexerPython.HighlightedIdentifier
    assert attribute_style == QsciLexerPython.Identifier
    editor.deleteLater()


def test_python_fstring_styles_follow_each_editor_theme(qapp, tmp_path):
    settings = Settings(tmp_path)
    settings.set("editor.auto_complete", False)
    editor = CodeEditor(settings)
    editor.file_path = str(tmp_path / "fstrings.py")
    source = (
        'double = f"double_marker {value}"\n'
        "single = f'single_marker {value}'\n"
        'triple_double = f"""triple_double_marker {value}"""\n'
        "triple_single = f'''triple_single_marker {value}'''\n"
    )
    expected_styles = {
        "double_marker": (
            QsciLexerPython.DoubleQuotedFString,
            QsciLexerPython.DoubleQuotedString,
        ),
        "single_marker": (
            QsciLexerPython.SingleQuotedFString,
            QsciLexerPython.SingleQuotedString,
        ),
        "triple_double_marker": (
            QsciLexerPython.TripleDoubleQuotedFString,
            QsciLexerPython.TripleDoubleQuotedString,
        ),
        "triple_single_marker": (
            QsciLexerPython.TripleSingleQuotedFString,
            QsciLexerPython.TripleSingleQuotedString,
        ),
    }

    for theme_name in ("default_light", "default_dark"):
        settings.set("editor.theme", theme_name)
        EditorConfigurator.apply(editor, settings)
        editor.setText(source)
        _colorise(editor)

        lexer = editor.lexer()
        assert isinstance(lexer, QsciLexerPython)
        theme = get_theme(theme_name)
        for marker, styles in expected_styles.items():
            fstring_style, ordinary_string_style = styles
            assert _style_at(editor, source, marker) == fstring_style
            assert lexer.color(fstring_style).name() == QColor(
                theme.foreground_colors[ordinary_string_style]
            ).name()

    editor.deleteLater()


def test_high_contrast_lexer_keeps_every_python_style_monochrome(
    qapp,
    tmp_path,
):
    settings = Settings(tmp_path)
    settings.set("editor.auto_complete", False)
    settings.set("editor.theme", "default_high_contrast")
    editor = CodeEditor(settings)

    lexer = editor.lexer()
    assert isinstance(lexer, QsciLexerPython)
    for style in range(
        QsciLexerPython.Default,
        QsciLexerPython.TripleDoubleQuotedFString + 1,
    ):
        assert lexer.color(style).name() == "#ffffff"
        assert lexer.paper(style).name() == "#000000"
    editor.deleteLater()


def test_python_plain_python_transition_clears_and_restores_token_styles(
    qapp,
    tmp_path,
):
    editor = make_editor(qapp, tmp_path)
    source = "for item in items:\n    print(item)\n"
    editor.setText(source)
    _colorise(editor)

    assert _style_at(editor, source, "for") == QsciLexerPython.Keyword

    editor.file_path = str(tmp_path / "notes.txt")
    _colorise(editor)
    assert editor.lexer() is None
    assert _style_at(editor, source, "for") == QsciLexerPython.Default

    editor.file_path = str(tmp_path / "restored.py")
    _colorise(editor)
    assert isinstance(editor.lexer(), QsciLexerPython)
    assert _style_at(editor, source, "for") == QsciLexerPython.Keyword
    editor.deleteLater()


@pytest.mark.parametrize(
    ("suffix", "lexer_type"),
    [
        (".json", QsciLexerJSON),
        (".md", QsciLexerMarkdown),
        (".markdown", QsciLexerMarkdown),
        (".yaml", QsciLexerYAML),
        (".yml", QsciLexerYAML),
        (".ini", QsciLexerProperties),
        (".cfg", QsciLexerProperties),
        (".properties", QsciLexerProperties),
    ],
)
def test_non_python_formats_use_native_lexers_without_python_tools(
    qapp,
    tmp_path,
    suffix,
    lexer_type,
):
    settings = Settings(tmp_path)
    settings.set("editor.auto_complete", True)
    editor = CodeEditor(settings)
    assert hasattr(editor, "_completion_apis")

    editor.file_path = str(tmp_path / f"document{suffix}")

    assert isinstance(editor.lexer(), lexer_type)
    assert (
        editor.autoCompletionSource()
        == QsciScintilla.AutoCompletionSource.AcsNone
    )
    assert not hasattr(editor, "_completion_apis")
    assert not hasattr(editor, "_completion_lexer")

    editor.setText("value = 1\n")
    editor.toggle_breakpoint(0)
    assert editor.get_breakpoints() == set()
    editor.deleteLater()


@pytest.mark.parametrize("suffix", [".toml", ".csv", ".log", ".txt"])
def test_supported_plain_text_formats_stay_unlexed_and_non_python(
    qapp,
    tmp_path,
    suffix,
):
    settings = Settings(tmp_path)
    settings.set("editor.auto_complete", True)
    editor = CodeEditor(settings)

    editor.file_path = str(tmp_path / f"document{suffix}")

    assert editor.lexer() is None
    assert (
        editor.autoCompletionSource()
        == QsciScintilla.AutoCompletionSource.AcsNone
    )
    assert not hasattr(editor, "_completion_apis")
    editor.toggle_breakpoint(0)
    assert editor.get_breakpoints() == set()
    editor.deleteLater()


def test_switching_between_syntax_languages_replaces_stale_lexers(
    qapp,
    tmp_path,
):
    editor = make_editor(qapp, tmp_path)
    transitions = [
        ("document.json", QsciLexerJSON),
        ("document.md", QsciLexerMarkdown),
        ("document.yaml", QsciLexerYAML),
        ("document.ini", QsciLexerProperties),
    ]

    for file_name, lexer_type in transitions:
        previous = editor.lexer()
        editor.file_path = str(tmp_path / file_name)
        assert isinstance(editor.lexer(), lexer_type)
        assert editor.lexer() is not previous

    editor.file_path = str(tmp_path / "document.toml")
    assert editor.lexer() is None

    editor.file_path = str(tmp_path / "document.py")
    assert isinstance(editor.lexer(), QsciLexerPython)
    editor.deleteLater()


@pytest.mark.parametrize(
    ("suffix", "source", "expected_styles"),
    [
        (
            ".json",
            '{"count": 3, "ready": true}\n',
            {
                "count": QsciLexerJSON.Property,
                "3": QsciLexerJSON.Number,
                "true": QsciLexerJSON.Keyword,
            },
        ),
        (
            ".md",
            "# Heading\n**bold** and *emphasis* and `code`\n",
            {
                "#": QsciLexerMarkdown.Header1,
                "bold": QsciLexerMarkdown.StrongEmphasisAsterisks,
                "emphasis": QsciLexerMarkdown.EmphasisAsterisks,
                "code": QsciLexerMarkdown.CodeBackticks,
            },
        ),
        (
            ".yaml",
            "name: meadow\ncount: 3\n# note\nenabled: true\n",
            {
                "name": QsciLexerYAML.Identifier,
                "3": QsciLexerYAML.Number,
                "note": QsciLexerYAML.Comment,
                "true": QsciLexerYAML.Keyword,
            },
        ),
        (
            ".ini",
            "[section]\nkey=value\n",
            {
                "section": QsciLexerProperties.Section,
                "key": QsciLexerProperties.Key,
                "=": QsciLexerProperties.Assignment,
            },
        ),
    ],
)
def test_non_python_lexers_classify_representative_tokens(
    qapp,
    tmp_path,
    suffix,
    source,
    expected_styles,
):
    editor = make_editor(qapp, tmp_path)
    editor.file_path = str(tmp_path / f"document{suffix}")
    editor.setText(source)
    _colorise(editor)

    observed_styles = {
        token: _style_at(editor, source, token)
        for token in expected_styles
    }
    assert observed_styles == expected_styles

    editor.deleteLater()


def test_non_python_profiles_follow_theme_and_preserve_font_traits(
    qapp,
    tmp_path,
):
    settings = Settings(tmp_path)
    settings.set("editor.auto_complete", False)
    settings.set("editor.theme", "default_high_contrast")
    editor = CodeEditor(settings)
    editor.file_path = str(tmp_path / "document.md")

    lexer = editor.lexer()
    assert isinstance(lexer, QsciLexerMarkdown)
    profile = get_lexer_profile(
        syntax_language_for_path(editor.file_path)
    )
    assert profile is not None
    for style_id in profile.style_roles:
        assert lexer.color(style_id).name() == "#ffffff"
        assert lexer.paper(style_id).name() == "#000000"

    assert lexer.font(QsciLexerMarkdown.Header1).bold()
    assert lexer.font(QsciLexerMarkdown.EmphasisAsterisks).italic()
    assert lexer.font(QsciLexerMarkdown.Link).underline()
    editor.deleteLater()


def test_reapplying_settings_reuses_lexer_and_completion_objects(
    qapp,
    tmp_path,
):
    settings = Settings(tmp_path)
    settings.set("editor.auto_complete", True)
    editor = CodeEditor(settings)
    python_lexer = editor.lexer()
    completion_apis = editor._completion_apis

    EditorConfigurator.apply(editor, settings)

    assert editor.lexer() is python_lexer
    assert editor._completion_apis is completion_apis

    editor.file_path = str(tmp_path / "document.json")
    json_lexer = editor.lexer()
    EditorConfigurator.apply(editor, settings)

    assert editor.lexer() is json_lexer
    assert not hasattr(editor, "_completion_apis")
    editor.deleteLater()


def test_replacing_lexer_queues_completion_child_for_deletion_first():
    deletion_order = []

    class FakeLexer:
        def __init__(self, parent, name):
            self._parent = parent
            self._name = name

        def parent(self):
            return self._parent

        def deleteLater(self):
            deletion_order.append(self._name)

    class FakeApis:
        def deleteLater(self):
            deletion_order.append("apis")

    class FakeEditor:
        def __init__(self):
            self.old_lexer = FakeLexer(self, "old_lexer")
            self.new_lexer = FakeLexer(self, "new_lexer")
            self._completion_lexer = self.old_lexer
            self._completion_apis = FakeApis()

        def lexer(self):
            return self.old_lexer

        def setLexer(self, lexer):
            assert lexer is self.new_lexer
            deletion_order.append("set_lexer")

    editor = FakeEditor()

    EditorConfigurator._install_lexer(
        editor,
        editor.new_lexer,
        SyntaxLanguage.JSON,
    )

    assert deletion_order == ["apis", "set_lexer", "old_lexer"]
    assert not hasattr(editor, "_completion_apis")
    assert not hasattr(editor, "_completion_lexer")


class PhantomBreakpointHarness:
    _breakpoint_hover_margin_at_x = CodeEditor._breakpoint_hover_margin_at_x
    _line_from_mouse_y = CodeEditor._line_from_mouse_y
    _set_phantom_breakpoint = CodeEditor._set_phantom_breakpoint
    _clear_phantom_breakpoint = CodeEditor._clear_phantom_breakpoint
    _get_breakpoint_tooltip = CodeEditor._get_breakpoint_tooltip

    def __init__(self):
        self._phantom_breakpoint_line = None
        self._phantom_breakpoint_is_remove = False
        self.widths = {0: 24, 1: 12, 2: 18, 3: 0, 4: 0}
        self.line = 1
        self.resolved_line = 2
        self.real_breakpoints = set()
        self.added = []
        self.deleted = []
        self.supports_breakpoints = True
        self.cursor = None
        self.breakpoint_state = None
        self.rejection_reason = None

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

    def setCursor(self, cursor):
        self.cursor = cursor

    def unsetCursor(self):
        self.cursor = None

    def get_breakpoint_state(self, line):
        return self.breakpoint_state

    def get_breakpoint_rejection_reason(self, line):
        return self.rejection_reason


def test_breakpoint_hover_is_dedicated_lane_with_add_and_remove_states():
    add_marker = code_editor_module.MARKER_BREAKPOINT_HOVER_ADD
    remove_marker = code_editor_module.MARKER_BREAKPOINT_HOVER_REMOVE
    harness = PhantomBreakpointHarness()

    # Line-number and folding margins do not toggle breakpoints.
    CodeEditor._update_phantom_breakpoint(harness, 5, 12)
    assert harness._phantom_breakpoint_line is None
    CodeEditor._update_phantom_breakpoint(harness, 25, 12)
    assert harness._phantom_breakpoint_line is None

    CodeEditor._update_phantom_breakpoint(harness, 40, 12)
    assert harness._phantom_breakpoint_line == 2
    assert harness.added == [(2, add_marker)]
    assert harness.cursor == Qt.CursorShape.PointingHandCursor

    CodeEditor._update_phantom_breakpoint(harness, 25, 12)
    assert harness._phantom_breakpoint_line is None
    assert harness.deleted == [("all", add_marker)]
    assert harness.cursor is None

    harness.real_breakpoints = {2}
    CodeEditor._update_phantom_breakpoint(harness, 40, 12)
    assert harness.added[-1] == (2, remove_marker)
    assert harness._phantom_breakpoint_is_remove is True


def test_phantom_breakpoint_hides_when_file_does_not_support_breakpoints():
    harness = PhantomBreakpointHarness()
    harness.supports_breakpoints = False
    harness._phantom_breakpoint_line = 2

    CodeEditor._update_phantom_breakpoint(harness, 5, 12)

    assert harness._phantom_breakpoint_line is None
    assert harness.deleted == [("all", code_editor_module.MARKER_PHANTOM_BREAKPOINT)]


def test_breakpoint_tooltips_explain_every_lane_state():
    harness = PhantomBreakpointHarness()

    harness.supports_breakpoints = False
    assert harness._get_breakpoint_tooltip(40, 12) is None
    harness.supports_breakpoints = True
    assert harness._get_breakpoint_tooltip(5, 12) is None

    harness.line = None
    harness.SendScintilla = lambda *args: -1
    assert harness._get_breakpoint_tooltip(40, 12) is None
    harness.SendScintilla = lambda *args: 40
    harness.line = 1

    harness.resolved_line = None
    assert harness._get_breakpoint_tooltip(40, 12) == "No executable Python statement nearby"

    harness.resolved_line = 2
    harness.breakpoint_state = code_editor_module.BreakpointState.PENDING
    assert "waiting for the debugger" in harness._get_breakpoint_tooltip(40, 12)

    harness.breakpoint_state = code_editor_module.BreakpointState.REJECTED
    harness.rejection_reason = "not executable"
    assert "not executable" in harness._get_breakpoint_tooltip(40, 12)
    harness.rejection_reason = None
    assert "could not set" in harness._get_breakpoint_tooltip(40, 12)

    harness.breakpoint_state = code_editor_module.BreakpointState.ACCEPTED
    assert harness._get_breakpoint_tooltip(40, 12) == "Remove breakpoint from line 3"

    harness.breakpoint_state = None
    assert "next executable line" in harness._get_breakpoint_tooltip(40, 12)
    harness.resolved_line = 1
    assert harness._get_breakpoint_tooltip(40, 12) == "Add breakpoint on line 2"


def test_breakable_lines_falls_back_to_nonblank_source_after_syntax_error(qapp, tmp_path):
    settings = Settings(tmp_path)
    settings.set("editor.auto_complete", False)
    editor = CodeEditor(settings)
    editor.file_path = str(tmp_path / "broken.py")
    editor.setText("def broken(:\n# comment\nvalue = 1\n\n")
    editor._breakable_lines_cache = None

    assert editor._breakable_lines() == {0, 2}
    editor.deleteLater()


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


def test_editor_event_prioritizes_folding_and_breakpoint_tooltips(
    monkeypatch, qapp, tmp_path
):
    editor = make_editor(qapp, tmp_path)
    calls = []
    monkeypatch.setattr(
        code_editor_module,
        "QToolTip",
        SimpleNamespace(
            showText=lambda pos, text, widget: calls.append((text, widget)),
            hideText=lambda: calls.append(("hide", None)),
        ),
    )
    event = QHelpEvent(QEvent.Type.ToolTip, QPoint(2, 3), QPoint(20, 30))

    editor._get_folding_tooltip = lambda x, y: "Collapse function"
    editor._get_breakpoint_tooltip = lambda x, y: "breakpoint"
    assert editor.event(event) is True
    assert calls[-1] == ("Collapse function", editor)

    editor._get_folding_tooltip = lambda x, y: None
    assert editor.event(event) is True
    assert calls[-1] == ("breakpoint", editor)

    refreshes = []
    editor._refresh_breakpoint_lane_artwork = lambda: refreshes.append("breakpoint")
    editor._refresh_folding_lane_artwork = lambda: refreshes.append("fold")
    dpr_type = getattr(QEvent.Type, "DevicePixelRatioChange", None)
    if dpr_type is not None:
        editor.event(QEvent(dpr_type))
        assert refreshes == ["breakpoint", "fold"]
    editor.deleteLater()


def test_mouse_hover_press_release_and_leave_update_fold_feedback(qapp, tmp_path):
    editor = make_editor(qapp, tmp_path)
    calls = []
    editor._update_phantom_breakpoint = lambda x, y: calls.append(("breakpoint", x, y))
    editor._update_fold_hover = lambda x, y: calls.append(("fold", x, y))
    editor._fold_header_from_point = lambda x, y: 2
    editor._sync_fold_feedback_marker = lambda: calls.append("sync")
    editor._clear_phantom_breakpoint = lambda: calls.append("clear_breakpoint")
    editor._clear_fold_feedback = lambda *args: calls.append("clear_fold")

    move = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(4, 5),
        QPointF(4, 5),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(4, 5),
        QPointF(4, 5),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    release = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(4, 5),
        QPointF(4, 5),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    editor.mouseMoveEvent(move)
    editor.mousePressEvent(press)
    editor.mouseReleaseEvent(release)
    editor.leaveEvent(QEvent(QEvent.Type.Leave))

    assert ("breakpoint", 4, 5) in calls
    assert ("fold", 4, 5) in calls
    assert "sync" in calls
    assert "clear_breakpoint" in calls
    assert "clear_fold" in calls
    assert editor._fold_pressed_line is None
    editor.deleteLater()


def test_folding_helpers_cover_invalid_headers_state_changes_and_failures(qapp, tmp_path):
    editor = make_editor(qapp, tmp_path)
    assert editor._is_fold_header(-1) is False
    assert editor._fold_block_kind("class Demo:") == "class"
    assert editor._fold_block_kind("if ready:") == "code block"

    editor._fold_pressed_line = 3
    editor._fold_hover_line = 3
    editor._fold_header_from_point = lambda x, y: 4
    editor._sync_fold_feedback_marker = lambda: None
    editor._update_fold_hover(1, 1)
    assert editor._fold_pressed_line is None
    assert editor._fold_hover_line == 4

    editor._fold_pressed_line = None
    editor._fold_hover_line = 4
    syncs = []
    editor._sync_fold_feedback_marker = lambda: syncs.append(True)
    editor._update_fold_hover(1, 1)
    assert syncs == [True]

    class BrokenFoldHarness:
        _fold_block_kind = staticmethod(CodeEditor._fold_block_kind)
        text = lambda self, line: "def demo():"
        _fold_header_from_point = lambda self, x, y: 1
        SendScintilla = lambda self, *args: (_ for _ in ()).throw(RuntimeError("gone"))

    assert CodeEditor._get_folding_tooltip(BrokenFoldHarness(), 1, 1) is None
    editor.deleteLater()


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

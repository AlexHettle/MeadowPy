from __future__ import annotations

import pytest
from PyQt6.QtCore import QCoreApplication, QEvent, Qt
from PyQt6.QtGui import QColor, QImage
from PyQt6.Qsci import QsciScintilla

import meadowpy.editor.code_editor as code_editor_module
from meadowpy.core.settings import Settings
from meadowpy.editor.code_editor import CodeEditor
from meadowpy.editor.themes import get_theme


NESTED_SOURCE = (
    "def outer():\n"
    "    def inner():\n"
    "        return 1\n"
    "    return inner()\n"
    "\n"
    "def sibling():\n"
    "    return 2\n"
)


def _dispose_editor(qapp, editor: CodeEditor) -> None:
    editor.close()
    editor.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()


def _make_editor(qapp, tmp_path) -> tuple[CodeEditor, Settings]:
    settings = Settings(tmp_path)
    settings.set("editor.auto_complete", False)
    settings.set("editor.code_folding", True)
    editor = CodeEditor(settings)
    editor.file_path = str(tmp_path / "folding.py")
    editor.setText(NESTED_SOURCE)
    editor.resize(520, 260)
    editor.show()
    editor.SendScintilla(QsciScintilla.SCI_COLOURISE, 0, -1)
    qapp.processEvents()
    return editor, settings


def _line_visible(editor: CodeEditor, line: int) -> bool:
    return bool(
        editor.SendScintilla(QsciScintilla.SCI_GETLINEVISIBLE, line)
    )


def _alpha_bounds(image: QImage, minimum_alpha: int = 24) -> tuple[int, int]:
    points = [
        (x, y)
        for x in range(image.width())
        for y in range(image.height())
        if image.pixelColor(x, y).alpha() >= minimum_alpha
    ]
    assert points
    xs, ys = zip(*points)
    return max(xs) - min(xs) + 1, max(ys) - min(ys) + 1


def _relative_luminance(color: str) -> float:
    channels = []
    for value in (
        QColor(color).redF(),
        QColor(color).greenF(),
        QColor(color).blueF(),
    ):
        channels.append(
            value / 12.92
            if value <= 0.04045
            else ((value + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast_ratio(first: str, second: str) -> float:
    first_luminance = _relative_luminance(first)
    second_luminance = _relative_luminance(second)
    lighter = max(first_luminance, second_luminance)
    darker = min(first_luminance, second_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def test_enabled_folding_lane_uses_plain_style_and_custom_marker_mask(
    qapp,
    tmp_path,
):
    editor, _settings = _make_editor(qapp, tmp_path)
    try:
        expected_mask = (
            int(QsciScintilla.SC_MASK_FOLDERS)
            | code_editor_module._FOLD_FEEDBACK_MASK
        ) & 0xFFFFFFFF

        assert editor.folding() == QsciScintilla.FoldStyle.PlainFoldStyle
        assert editor.marginType(1) == QsciScintilla.MarginType.SymbolMargin
        assert editor.marginWidth(1) >= code_editor_module.FOLD_MARGIN_WIDTH
        assert editor.marginSensitivity(1) is True
        assert editor.marginMarkerMask(1) & 0xFFFFFFFF == expected_mask

        for marker in (
            QsciScintilla.SC_MARKNUM_FOLDEREND,
            QsciScintilla.SC_MARKNUM_FOLDEROPENMID,
            QsciScintilla.SC_MARKNUM_FOLDER,
            QsciScintilla.SC_MARKNUM_FOLDEROPEN,
        ):
            assert editor.SendScintilla(
                QsciScintilla.SCI_MARKERSYMBOLDEFINED,
                marker,
            ) == QsciScintilla.SC_MARK_PIXMAP
    finally:
        _dispose_editor(qapp, editor)


def test_nested_and_sibling_folds_toggle_independently(qapp, tmp_path):
    editor, _settings = _make_editor(qapp, tmp_path)
    try:
        assert editor._is_fold_header(0) is True
        assert editor._is_fold_header(1) is True
        assert editor._is_fold_header(5) is True
        assert editor._is_fold_header(2) is False

        editor.foldLine(1)
        assert not editor.SendScintilla(
            QsciScintilla.SCI_GETFOLDEXPANDED,
            1,
        )
        assert _line_visible(editor, 2) is False
        assert _line_visible(editor, 3) is True

        editor.foldLine(1)
        assert _line_visible(editor, 2) is True

        editor.foldLine(0)
        assert _line_visible(editor, 1) is False
        assert _line_visible(editor, 3) is False
        assert _line_visible(editor, 5) is True

        editor.foldLine(0)
        editor.foldLine(5)
        assert _line_visible(editor, 1) is True
        assert _line_visible(editor, 6) is False
    finally:
        _dispose_editor(qapp, editor)


def test_disabling_folding_unhides_contracted_code_before_hiding_lane(
    qapp,
    tmp_path,
):
    editor, settings = _make_editor(qapp, tmp_path)
    try:
        editor.foldLine(0)
        assert _line_visible(editor, 1) is False

        settings.set("editor.code_folding", False)
        editor.apply_settings(settings)

        assert editor.folding() == QsciScintilla.FoldStyle.NoFoldStyle
        assert editor.marginWidth(1) == 0
        assert editor.marginSensitivity(1) is False
        assert _line_visible(editor, 1) is True
        assert _line_visible(editor, 2) is True

        settings.set("editor.code_folding", True)
        editor.apply_settings(settings)

        assert editor.folding() == QsciScintilla.FoldStyle.PlainFoldStyle
        assert editor.marginWidth(1) >= code_editor_module.FOLD_MARGIN_WIDTH
        assert _line_visible(editor, 1) is True
    finally:
        _dispose_editor(qapp, editor)


def test_theme_and_zoom_refresh_preserve_collapsed_state(qapp, tmp_path):
    editor, settings = _make_editor(qapp, tmp_path)
    try:
        editor.foldLine(0)
        assert _line_visible(editor, 1) is False
        original_width = editor.marginWidth(1)

        settings.set("editor.theme", "default_light")
        editor.apply_settings(settings)
        editor.zoomIn(3)

        assert _line_visible(editor, 1) is False
        assert editor.marginWidth(1) >= original_width
        assert editor.marginMarkerMask(1) & code_editor_module._FOLD_FEEDBACK_MASK
        assert editor.SendScintilla(
            QsciScintilla.SCI_MARKERSYMBOLDEFINED,
            QsciScintilla.SC_MARKNUM_FOLDER,
        ) == QsciScintilla.SC_MARK_PIXMAP
    finally:
        _dispose_editor(qapp, editor)


def test_fold_chevrons_and_feedback_surfaces_are_dpr_aware(qapp):
    color = QColor("#A8ADB5")
    collapsed = CodeEditor._fold_marker_pixmap(
        color,
        expanded=False,
        logical_size=20,
        device_pixel_ratio=2.0,
    )
    expanded = CodeEditor._fold_marker_pixmap(
        color,
        expanded=True,
        logical_size=20,
        device_pixel_ratio=2.0,
    )
    hover = CodeEditor._fold_feedback_pixmap(
        QColor("#3A3D41"),
        border=QColor("#F1F3F4"),
        logical_size=20,
        device_pixel_ratio=2.0,
    )
    pressed = CodeEditor._fold_feedback_pixmap(
        QColor("#484C52"),
        border=QColor("#F1F3F4"),
        logical_size=20,
        device_pixel_ratio=2.0,
    )

    for pixmap in (collapsed, expanded, hover, pressed):
        assert pixmap.devicePixelRatio() == 2.0
        assert pixmap.width() == 40
        assert pixmap.height() == 40
        image = pixmap.toImage()
        assert image.pixelColor(0, 0).alpha() == 0
        assert image.pixelColor(39, 39).alpha() == 0

    collapsed_width, collapsed_height = _alpha_bounds(collapsed.toImage())
    expanded_width, expanded_height = _alpha_bounds(expanded.toImage())
    assert collapsed_height > collapsed_width
    assert expanded_width > expanded_height

    center = hover.width() // 2
    assert hover.toImage().pixelColor(center, center) == QColor("#3A3D41")
    assert pressed.toImage().pixelColor(center, center) == QColor("#484C52")


@pytest.mark.parametrize(
    ("theme_name", "custom_base"),
    [
        ("default_light", "light"),
        ("default_dark", "dark"),
        ("default_high_contrast", "dark"),
        ("custom", "light"),
        ("custom", "dark"),
    ],
)
def test_fold_indicator_tokens_have_non_text_contrast(theme_name, custom_base):
    theme = get_theme(theme_name, custom_base)

    assert _contrast_ratio(
        theme.fold_indicator,
        theme.fold_margin_background,
    ) >= 3.0
    assert _contrast_ratio(
        theme.fold_indicator_hover,
        theme.fold_margin_background,
    ) >= 3.0
    assert QColor(theme.fold_hover_background).isValid()
    assert QColor(theme.fold_pressed_background).isValid()
    assert theme.fold_hover_background != theme.fold_pressed_background


def test_fold_hover_and_tooltip_are_limited_to_real_headers(qapp, tmp_path):
    editor, _settings = _make_editor(qapp, tmp_path)
    try:
        fold_x = editor.marginWidth(0) + editor.marginWidth(1) // 2
        header_y = editor._line_y(0) + editor._line_height(0) // 2
        body_y = editor._line_y(3) + editor._line_height(3) // 2

        assert editor._fold_header_from_point(fold_x, header_y) == 0
        assert editor._fold_header_from_point(fold_x, body_y) is None

        editor._update_fold_hover(fold_x, header_y)
        assert editor._fold_hover_line == 0
        assert editor.cursor().shape() == Qt.CursorShape.PointingHandCursor
        assert editor.markersAtLine(0) & (
            1 << code_editor_module.MARKER_FOLD_HOVER
        )
        assert editor._get_folding_tooltip(
            fold_x,
            header_y,
        ).startswith("Collapse function")

        editor.foldLine(0)
        assert editor._get_folding_tooltip(
            fold_x,
            header_y,
        ).startswith("Expand function")
        editor.foldLine(0)

        editor._update_fold_hover(fold_x, body_y)
        assert editor._fold_hover_line is None
        assert editor.cursor().shape() != Qt.CursorShape.PointingHandCursor
        assert editor._get_folding_tooltip(fold_x, body_y) is None
    finally:
        _dispose_editor(qapp, editor)


def test_folding_and_breakpoint_lanes_remain_isolated(qapp, tmp_path):
    editor, _settings = _make_editor(qapp, tmp_path)
    try:
        line_number_width = editor.marginWidth(0)
        fold_x = line_number_width + editor.marginWidth(1) // 2
        breakpoint_x = (
            line_number_width
            + editor.marginWidth(1)
            + editor.marginWidth(2) // 2
        )
        header_y = editor._line_y(0) + editor._line_height(0) // 2

        assert editor._fold_hover_margin_at_x(fold_x) is True
        assert editor._breakpoint_hover_margin_at_x(fold_x) is False
        assert editor._fold_hover_margin_at_x(breakpoint_x) is False
        assert editor._breakpoint_hover_margin_at_x(breakpoint_x) is True

        editor._on_margin_clicked(1, 0, None)
        assert editor.get_breakpoints() == set()

        editor._update_phantom_breakpoint(fold_x, header_y)
        editor._update_fold_hover(fold_x, header_y)
        assert editor._fold_hover_line == 0
        assert editor._phantom_breakpoint_line is None

        editor._on_margin_clicked(2, 0, None)
        assert editor.get_breakpoints() == {0}

        editor._update_phantom_breakpoint(breakpoint_x, header_y)
        editor._update_fold_hover(breakpoint_x, header_y)
        assert editor._fold_hover_line is None
        assert editor._phantom_breakpoint_line == 0
    finally:
        _dispose_editor(qapp, editor)

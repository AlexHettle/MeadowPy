from __future__ import annotations

import re

import pytest
from PyQt6.QtCore import QCoreApplication, QEvent, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QTabBar, QToolButton

from meadowpy.core.settings import Settings
from meadowpy.resources.resource_loader import (
    current_accent_hex,
    get_stylesheet,
)
from meadowpy.resources.theme_colors import (
    resolve_accent_shades,
    theme_is_dark,
)
from meadowpy.ui.tab_manager import (
    TabManager,
    _EditorTabBar,
    _ModifiedDot,
    _TabRightWidget,
)


EDITOR_TAB_HEIGHT = 36
EDITOR_TAB_MINIMUM_RENDERED_WIDTH = 130
EDITOR_TAB_MAXIMUM_RENDERED_WIDTH = 224
EDITOR_SCROLL_BUTTON_WIDTH = 18
EDITOR_SCROLL_BUTTON_HEIGHT = 26


@pytest.fixture
def dark_editor_stylesheet(qapp):
    previous_stylesheet = qapp.styleSheet()
    qapp.setStyleSheet(get_stylesheet("default_dark"))
    try:
        yield
    finally:
        qapp.setStyleSheet(previous_stylesheet)
        qapp.processEvents()


def _make_settings(tmp_path) -> Settings:
    settings = Settings(tmp_path)
    settings.set("editor.auto_complete", False)
    settings.set("editor.theme", "default_dark")
    settings.set("editor.custom_theme.base", "dark")
    return settings


def _make_tabs(
    qapp,
    tmp_path,
    names: tuple[str, ...],
    *,
    width: int = 900,
):
    settings = _make_settings(tmp_path)
    tabs = TabManager(settings)
    editors = [
        tabs.new_tab(
            str(tmp_path / name),
            f"print({index})\n",
        )
        for index, name in enumerate(names)
    ]
    tabs.resize(width, 320)
    tabs.show()
    qapp.processEvents()
    tabs.tabBar()._configure_scroll_buttons()
    qapp.processEvents()
    return tabs, settings, editors


def _dispose_tabs(qapp, tabs: TabManager) -> None:
    tabs.close()
    tabs.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()


def _set_modified(editor, modified: bool) -> None:
    editor.setModified(modified)
    editor.modification_changed.emit(modified)


def _rule_blocks(stylesheet: str, selector: str) -> list[str]:
    return [
        match.group("body")
        for match in re.finditer(
            rf"{re.escape(selector)}\s*\{{(?P<body>[^}}]*)\}}",
            stylesheet,
        )
    ]


def _rule_block(stylesheet: str, selector: str) -> str:
    blocks = _rule_blocks(stylesheet, selector)
    assert blocks, f"Missing QSS selector: {selector}"
    return blocks[0]


def _declarations(block: str) -> dict[str, str]:
    declarations = {}
    for statement in block.split(";"):
        if ":" not in statement:
            continue
        name, value = statement.split(":", 1)
        declarations[name.strip()] = value.strip()
    return declarations


def _effective_state(
    stylesheet: str,
    selected_selector: str,
    state_selector: str | None = None,
) -> dict[str, str]:
    selected = _declarations(_rule_blocks(stylesheet, selected_selector)[-1])
    if state_selector is not None:
        selected.update(
            _declarations(_rule_blocks(stylesheet, state_selector)[-1])
        )
    return selected


def _assert_uniform_outline(
    declarations: dict[str, str],
    *,
    width: int,
    color: str,
    allow_dashed: bool,
) -> None:
    expected_styles = {"solid", "dashed"} if allow_dashed else {"solid"}
    outline_pattern = re.compile(
        rf"{width}px\s+(?P<style>solid|dashed)\s+{re.escape(color)}",
        re.IGNORECASE,
    )
    base_outline = declarations.get("border", "")
    base_match = outline_pattern.fullmatch(base_outline)
    assert base_match is not None
    assert base_match.group("style").lower() in expected_styles

    for side in ("top", "right", "bottom", "left"):
        side_outline = declarations.get(f"border-{side}", base_outline)
        side_match = outline_pattern.fullmatch(side_outline)
        assert side_match is not None
        assert side_match.group("style").lower() in expected_styles
        assert side_match.group("style").lower() == base_match.group(
            "style"
        ).lower()


def test_editor_tab_bar_and_controls_have_accessible_stable_geometry(
    qapp,
    tmp_path,
    dark_editor_stylesheet,
):
    name = "a_very_long_document_name_for_elision.py"
    tabs, _settings, editors = _make_tabs(qapp, tmp_path, (name,))
    bar = tabs.tabBar()
    try:
        assert isinstance(bar, _EditorTabBar)
        assert tabs.isMovable() is True
        assert tabs.documentMode() is True
        assert bar.expanding() is False
        assert bar.usesScrollButtons() is True
        assert bar.elideMode() == Qt.TextElideMode.ElideMiddle
        assert bar.focusPolicy() == Qt.FocusPolicy.TabFocus
        assert bar.hasMouseTracking() is True
        assert bar.accessibleName() == "Open file tabs"
        assert "Left and Right arrow keys" in bar.accessibleDescription()
        assert isinstance(bar.property("editorKeyboardFocus"), bool)
        assert bar.property("editorPressed") is False
        assert bar.minimumSizeHint().width() == 0
        assert bar.height() == EDITOR_TAB_HEIGHT
        assert EDITOR_TAB_MINIMUM_RENDERED_WIDTH <= bar.tabRect(0).width()
        assert bar.tabRect(0).width() <= EDITOR_TAB_MAXIMUM_RENDERED_WIDTH
        assert tabs.tabToolTip(0) == editors[0].file_path

        side = bar.tabButton(0, QTabBar.ButtonPosition.RightSide)
        assert isinstance(side, _TabRightWidget)
        close_button = side.close_btn
        assert (close_button.width(), close_button.height()) == (24, 24)
        assert close_button.cursor().shape() == Qt.CursorShape.PointingHandCursor
        assert close_button.accessibleName() == f"Close {name}"
        assert close_button.toolTip() == close_button.accessibleName()
        assert close_button.autoRaise() is True

        dot = side._dot
        assert isinstance(dot, _ModifiedDot)
        assert dot.isVisible() is False
        assert dot.testAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        assert dot.sizePolicy().retainSizeWhenHidden() is True
        assert dot.accessibleName() == f"{name} has unsaved changes"
    finally:
        _dispose_tabs(qapp, tabs)


def test_modified_dot_uses_accent_without_moving_tab_controls(
    qapp,
    tmp_path,
    dark_editor_stylesheet,
):
    tabs, settings, (editor,) = _make_tabs(qapp, tmp_path, ("dirty.py",))
    bar = tabs.tabBar()
    side = bar.tabButton(0, QTabBar.ButtonPosition.RightSide)
    assert isinstance(side, _TabRightWidget)
    dot = side._dot
    assert isinstance(dot, _ModifiedDot)
    try:
        initial_tab_size = bar.tabRect(0).size()
        initial_close_geometry = side.close_btn.geometry()

        _set_modified(editor, True)
        qapp.processEvents()

        assert dot.isVisible() is True
        assert bar.tabRect(0).size() == initial_tab_size
        assert side.close_btn.geometry() == initial_close_geometry
        image = dot.grab().toImage()
        center = image.rect().center()
        assert image.pixelColor(center) == QColor(
            current_accent_hex(settings.get("editor.theme"))
        )

        _set_modified(editor, False)
        qapp.processEvents()
        assert dot.isVisible() is False
        assert bar.tabRect(0).size() == initial_tab_size
    finally:
        _dispose_tabs(qapp, tabs)


def test_reorder_keeps_editor_modified_and_close_control_identity(
    qapp,
    tmp_path,
    dark_editor_stylesheet,
):
    names = ("first.py", "second.py", "third.py")
    tabs, _settings, editors = _make_tabs(qapp, tmp_path, names)
    bar = tabs.tabBar()
    first, second, third = editors
    first_side = bar.tabButton(0, QTabBar.ButtonPosition.RightSide)
    assert isinstance(first_side, _TabRightWidget)
    closed = []
    tabs.editor_closed.connect(closed.append)
    try:
        _set_modified(first, True)
        tabs.setCurrentWidget(first)
        qapp.processEvents()
        assert first_side._dot.isVisible() is True

        bar.moveTab(0, 2)
        qapp.processEvents()

        assert [tabs.widget(index) for index in range(3)] == [
            second,
            third,
            first,
        ]
        assert [tabs.tabText(index) for index in range(3)] == [
            "second.py",
            "third.py",
            "first.py",
        ]
        assert tabs.current_editor() is first
        assert bar.tabButton(2, QTabBar.ButtonPosition.RightSide) is first_side
        assert first_side._dot.isVisible() is True
        assert tabs.get_open_file_paths() == [
            second.file_path,
            third.file_path,
            first.file_path,
        ]

        _set_modified(first, False)
        first_side.close_btn.click()
        qapp.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.MetaCall)
        qapp.processEvents()
        assert tabs.count() == 2
        assert [tabs.widget(index) for index in range(2)] == [second, third]
        assert len(closed) == 1
        assert closed[0] is first
    finally:
        _dispose_tabs(qapp, tabs)


def test_editor_tab_overflow_buttons_are_visible_named_and_usable(
    qapp,
    tmp_path,
    dark_editor_stylesheet,
):
    names = tuple(
        f"long_document_name_number_{index}.py" for index in range(7)
    )
    tabs, _settings, _editors = _make_tabs(
        qapp,
        tmp_path,
        names,
        width=340,
    )
    bar = tabs.tabBar()
    try:
        assert sum(
            bar.tabRect(index).width() for index in range(bar.count())
        ) > bar.width()
        assert all(
            bar.tabRect(index).width() >= EDITOR_TAB_MINIMUM_RENDERED_WIDTH
            for index in range(bar.count())
        )
        scroll_buttons = [
            button
            for button in bar.findChildren(QToolButton)
            if button.parent() is bar and button.isVisible()
        ]
        assert len(scroll_buttons) == 2
        assert {
            button.accessibleName() for button in scroll_buttons
        } == {
            "Scroll file tabs left",
            "Scroll file tabs right",
        }
        for button in scroll_buttons:
            assert button.toolTip() == button.accessibleName()
            assert button.width() >= EDITOR_SCROLL_BUTTON_WIDTH
            assert button.height() >= EDITOR_SCROLL_BUTTON_HEIGHT

        bar.setCurrentIndex(bar.count() - 1)
        qapp.processEvents()
        assert bar.tabRect(bar.count() - 1).intersects(bar.rect())
        bar.setCurrentIndex(0)
        qapp.processEvents()
        assert bar.tabRect(0).intersects(bar.rect())
    finally:
        _dispose_tabs(qapp, tabs)


def test_editor_tab_keyboard_focus_and_pressed_properties_are_transient(
    qapp,
    tmp_path,
    dark_editor_stylesheet,
):
    tabs, _settings, _editors = _make_tabs(
        qapp,
        tmp_path,
        ("first.py", "second.py"),
    )
    bar = tabs.tabBar()
    try:
        bar.setCurrentIndex(0)
        bar.clearFocus()
        qapp.processEvents()
        bar.setFocus(Qt.FocusReason.MouseFocusReason)
        qapp.processEvents()
        assert bar.hasFocus() is True
        assert bar.property("editorKeyboardFocus") is False
        bar.clearFocus()
        qapp.processEvents()
        bar.setFocus(Qt.FocusReason.TabFocusReason)
        qapp.processEvents()
        assert bar.hasFocus() is True
        assert bar.property("editorKeyboardFocus") is True
        QTest.keyClick(bar, Qt.Key.Key_Right)
        assert bar.currentIndex() == 1

        QTest.mousePress(
            bar,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            bar.tabRect(0).center(),
        )
        assert bar.property("editorPressed") is True
        qapp.sendEvent(bar, QEvent(QEvent.Type.UngrabMouse))
        assert bar.property("editorPressed") is False

        QTest.mousePress(
            bar,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            bar.tabRect(1).center(),
        )
        assert bar.property("editorPressed") is True
        qapp.sendEvent(bar, QEvent(QEvent.Type.WindowDeactivate))
        assert bar.property("editorPressed") is False

        bar.clearFocus()
        qapp.processEvents()
        assert bar.property("editorKeyboardFocus") is False
    finally:
        _dispose_tabs(qapp, tabs)


@pytest.mark.parametrize(
    "theme_name",
    ["default_light", "default_dark", "default_high_contrast"],
)
def test_editor_tab_styles_are_scoped_and_rounded_for_every_theme(theme_name):
    stylesheet = get_stylesheet(theme_name)
    selectors = (
        "#editorTabs QTabBar",
        "QTabWidget#editorTabs::pane",
        "#editorTabs QTabBar::tab",
        "#editorTabs QTabBar::tab:first",
        "#editorTabs QTabBar::tab:hover:!selected",
        "#editorTabs QTabBar::tab:selected",
        '#editorTabs QTabBar[editorKeyboardFocus="true"]::tab:selected',
        '#editorTabs QTabBar[editorPressed="true"]::tab:selected',
        "#editorTabs QTabBar::tab:disabled",
        "#editorTabs QTabBar::scroller",
        "#editorTabs QTabBar > QToolButton",
        "#editorTabs QTabBar > QToolButton:hover",
        "#editorTabs QTabBar > QToolButton:pressed",
    )
    for selector in selectors:
        _rule_block(stylesheet, selector)

    rounded_selectors = (
        "#editorTabs QTabBar::tab",
        "#editorTabs QTabBar::tab:hover:!selected",
        "#editorTabs QTabBar::tab:selected",
        '#editorTabs QTabBar[editorKeyboardFocus="true"]::tab:selected',
        '#editorTabs QTabBar[editorPressed="true"]::tab:selected',
    )
    for selector in rounded_selectors:
        assert "border-radius: 6px" in _rule_block(stylesheet, selector)

    base_tab = _rule_block(stylesheet, "#editorTabs QTabBar::tab")
    assert "min-width: 104px" in base_tab
    assert "max-width: 196px" in base_tab
    assert "{{" not in base_tab


def test_high_contrast_editor_selected_state_keeps_trailing_marks_visible():
    stylesheet = get_stylesheet("default_high_contrast")
    selected_blocks = _rule_blocks(
        stylesheet,
        "#editorTabs QTabBar::tab:selected",
    )
    assert any(
        "background: #000000" in block and "color: #FFFFFF" in block
        for block in selected_blocks
    )


@pytest.mark.parametrize(
    ("theme_name", "custom_base", "custom_accent", "outline_width"),
    [
        ("default_light", "light", None, 1),
        ("default_dark", "dark", None, 1),
        ("custom", "light", "#336699", 1),
        ("custom", "dark", "#336699", 1),
        ("default_high_contrast", "dark", None, 1),
    ],
)
def test_editor_and_dock_selected_states_share_uniform_accent_outline(
    theme_name,
    custom_base,
    custom_accent,
    outline_width,
):
    stylesheet = get_stylesheet(
        theme_name,
        custom_base=custom_base,
        custom_accent=custom_accent,
    )
    is_dark = theme_is_dark(theme_name, custom_base)
    shades = resolve_accent_shades(theme_name, is_dark, custom_accent)
    outline_color = (
        shades["ACCENT_BRIGHT"] if is_dark else shades["ACCENT"]
    )

    editor_selected = "#editorTabs QTabBar::tab:selected"
    dock_selected = "QMainWindow > QTabBar::tab:selected"
    state_selectors = (
        (None, None, False),
        (
            '#editorTabs QTabBar[editorPressed="true"]::tab:selected',
            'QTabBar#dockPanelTabs[panelPressed="true"]::tab:selected',
            False,
        ),
        (
            '#editorTabs QTabBar[editorKeyboardFocus="true"]::tab:selected',
            'QTabBar#dockPanelTabs[panelKeyboardFocus="true"]::tab:selected',
            True,
        ),
    )
    comparable_properties = (
        "background",
        "color",
        "font-weight",
        "border-radius",
    )
    outlines = []
    for editor_state, dock_state, allow_dashed in state_selectors:
        editor = _effective_state(
            stylesheet,
            editor_selected,
            editor_state,
        )
        dock = _effective_state(
            stylesheet,
            dock_selected,
            dock_state,
        )

        assert {
            name: editor.get(name) for name in comparable_properties
        } == {
            name: dock.get(name) for name in comparable_properties
        }
        assert editor.get("border-radius") == "6px"
        assert editor.get("font-weight") == "600"
        _assert_uniform_outline(
            editor,
            width=outline_width,
            color=outline_color,
            allow_dashed=allow_dashed,
        )
        _assert_uniform_outline(
            dock,
            width=outline_width,
            color=outline_color,
            allow_dashed=allow_dashed,
        )
        outlines.append(
            (
                outline_width,
                outline_color.upper(),
                editor.get("border-radius"),
            )
        )

        if theme_name == "default_high_contrast":
            assert editor.get("color") == "#FFFFFF"
            if editor_state is None or allow_dashed:
                assert editor.get("background") == "#000000"

    assert len(set(outlines)) == 1

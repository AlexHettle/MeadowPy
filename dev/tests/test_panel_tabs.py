from __future__ import annotations

import re

import pytest
from PyQt6.QtCore import QCoreApplication, QEvent, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (
    QDockWidget,
    QMainWindow,
    QTabBar,
    QTabWidget,
    QToolButton,
    QWidget,
)

from meadowpy.resources.resource_loader import get_stylesheet
from meadowpy.ui.dock_tab_styler import (
    DOCK_TAB_BAR_OBJECT_NAME,
    DockTabStyler,
)


PANEL_TAB_HEIGHT = 36
PANEL_TAB_MINIMUM_WIDTH = 68
PANEL_TAB_HORIZONTAL_PADDING = 24


@pytest.fixture
def dark_dock_stylesheet(qapp):
    previous_stylesheet = qapp.styleSheet()
    qapp.setStyleSheet(get_stylesheet("default_dark"))
    try:
        yield
    finally:
        qapp.setStyleSheet(previous_stylesheet)
        qapp.processEvents()


def _dispose_windows(qapp, *windows: QMainWindow) -> None:
    for window in windows:
        window.close()
        window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()


def _add_dock(
    window: QMainWindow,
    title: str,
    object_name: str,
    area: Qt.DockWidgetArea = Qt.DockWidgetArea.BottomDockWidgetArea,
) -> QDockWidget:
    dock = QDockWidget(title, window)
    dock.setObjectName(object_name)
    body = QWidget(dock)
    body.setMinimumHeight(80)
    dock.setWidget(body)
    window.addDockWidget(area, dock)
    return dock


def _direct_dock_tab_bars(window: QMainWindow) -> list[QTabBar]:
    return [
        bar
        for bar in window.findChildren(QTabBar)
        if bar.parent() is window and bar.count()
    ]


def _bar_with_titles(window: QMainWindow, titles: set[str]) -> QTabBar:
    matches = [
        bar
        for bar in _direct_dock_tab_bars(window)
        if {bar.tabText(index) for index in range(bar.count())} == titles
    ]
    assert len(matches) == 1
    return matches[0]


def _make_tabbed_window(
    qapp,
    titles: tuple[str, ...] = ("Output", "AI Chat", "Search"),
    *,
    width: int = 900,
) -> tuple[QMainWindow, list[QDockWidget], DockTabStyler, QTabBar]:
    window = QMainWindow()
    window.setCentralWidget(QWidget(window))
    window.setTabPosition(
        Qt.DockWidgetArea.BottomDockWidgetArea,
        QTabWidget.TabPosition.North,
    )
    docks = [
        _add_dock(window, title, f"panelDock{index}")
        for index, title in enumerate(titles)
    ]
    for previous, current in zip(docks, docks[1:]):
        window.tabifyDockWidget(previous, current)

    styler = DockTabStyler(window)
    window.resize(width, 360)
    window.show()
    qapp.processEvents()
    styler.refresh()
    qapp.processEvents()
    bar = _bar_with_titles(window, set(titles))
    return window, docks, styler, bar


def _send_mouse_move(qapp, bar: QTabBar, position) -> None:
    local_position = QPointF(position)
    global_position = QPointF(bar.mapToGlobal(position))
    event = QMouseEvent(
        QEvent.Type.MouseMove,
        local_position,
        global_position,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    qapp.sendEvent(bar, event)
    qapp.processEvents()


def _rule_block(stylesheet: str, selector: str) -> str:
    match = re.search(
        rf"{re.escape(selector)}\s*\{{(?P<body>[^}}]*)\}}",
        stylesheet,
    )
    assert match is not None, f"Missing QSS selector: {selector}"
    return match.group("body")


def test_dock_tab_bar_has_semantics_accessibility_and_content_sizing(
    qapp,
    dark_dock_stylesheet,
):
    window, _docks, _styler, bar = _make_tabbed_window(qapp)
    try:
        assert bar.objectName() == DOCK_TAB_BAR_OBJECT_NAME
        assert bar.property("panelTabs") is True
        assert bar.drawBase() is False
        assert bar.expanding() is False
        assert bar.usesScrollButtons() is True
        assert bar.elideMode() == Qt.TextElideMode.ElideRight
        assert bar.focusPolicy() == Qt.FocusPolicy.TabFocus
        assert bar.focusPolicy() != Qt.FocusPolicy.NoFocus
        assert bar.hasMouseTracking() is True
        assert bar.accessibleName() == "Docked panel tabs"
        assert "Left and Right arrow keys" in bar.accessibleDescription()
        assert isinstance(bar.property("panelKeyboardFocus"), bool)
        assert bar.property("panelPressed") is False
        assert [bar.tabText(index) for index in range(bar.count())] == [
            "Output",
            "AI Chat",
            "Search",
        ]
        assert bar.height() == PANEL_TAB_HEIGHT

        for index in range(bar.count()):
            rect = bar.tabRect(index)
            label = bar.tabText(index).replace("&", "")
            text_width = bar.fontMetrics().horizontalAdvance(label)
            assert rect.height() == PANEL_TAB_HEIGHT
            assert rect.width() >= PANEL_TAB_MINIMUM_WIDTH
            assert rect.width() >= text_width + PANEL_TAB_HORIZONTAL_PADDING
            assert bar.tabAt(rect.center()) == index
    finally:
        _dispose_windows(qapp, window)


def test_dock_tabs_use_pointer_cursor_and_plain_text_tooltips(
    qapp,
    dark_dock_stylesheet,
):
    titles = ("Output", "A&I Chat", "Search")
    window, _docks, _styler, bar = _make_tabbed_window(
        qapp,
        titles,
    )
    try:
        assert [bar.tabToolTip(index) for index in range(bar.count())] == [
            "Output",
            "AI Chat",
            "Search",
        ]

        _send_mouse_move(qapp, bar, bar.tabRect(1).center())
        assert bar.cursor().shape() == Qt.CursorShape.PointingHandCursor
        assert bar.tabToolTip(1) == "AI Chat"

        blank_position = bar.rect().bottomRight()
        _send_mouse_move(qapp, bar, blank_position)
        assert bar.cursor().shape() != Qt.CursorShape.PointingHandCursor

        qapp.sendEvent(bar, QEvent(QEvent.Type.Leave))
        assert bar.cursor().shape() != Qt.CursorShape.PointingHandCursor
    finally:
        _dispose_windows(qapp, window)


def test_click_and_arrow_keys_activate_exact_dock_tabs(
    qapp,
    dark_dock_stylesheet,
):
    window, _docks, _styler, bar = _make_tabbed_window(qapp)
    changes: list[int] = []
    bar.currentChanged.connect(changes.append)
    try:
        bar.setCurrentIndex(0)
        qapp.processEvents()
        changes.clear()

        QTest.mouseClick(
            bar,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            bar.tabRect(2).center(),
        )
        assert bar.currentIndex() == 2
        assert changes == [2]
        assert bar.property("panelPressed") is False

        QTest.mousePress(
            bar,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            bar.tabRect(1).center(),
        )
        assert bar.property("panelPressed") is True
        qapp.sendEvent(bar, QEvent(QEvent.Type.UngrabMouse))
        assert bar.currentIndex() == 1
        assert bar.property("panelPressed") is False

        QTest.mousePress(
            bar,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            bar.tabRect(1).center(),
        )
        assert bar.property("panelPressed") is True
        qapp.sendEvent(bar, QEvent(QEvent.Type.WindowDeactivate))
        assert bar.property("panelPressed") is False

        bar.clearFocus()
        qapp.processEvents()
        bar.setFocus(Qt.FocusReason.MouseFocusReason)
        qapp.processEvents()
        assert bar.hasFocus()
        assert bar.property("panelKeyboardFocus") is False
        bar.clearFocus()
        qapp.processEvents()
        bar.setFocus(Qt.FocusReason.TabFocusReason)
        assert bar.hasFocus()
        assert bar.property("panelKeyboardFocus") is True
        QTest.keyClick(bar, Qt.Key.Key_Left)
        assert bar.currentIndex() == 0
        QTest.keyClick(bar, Qt.Key.Key_Right)
        assert bar.currentIndex() == 1
        assert changes == [2, 1, 0, 1]
    finally:
        _dispose_windows(qapp, window)


def test_narrow_dock_tabs_keep_overflow_buttons_usable(
    qapp,
    dark_dock_stylesheet,
):
    titles = (
        "Output",
        "AI Chat",
        "Search Results",
        "Problems",
        "Python Console",
        "Terminal",
    )
    window, _docks, _styler, bar = _make_tabbed_window(
        qapp,
        titles,
        width=300,
    )
    try:
        assert sum(bar.tabRect(index).width() for index in range(bar.count())) > (
            bar.width()
        )
        scroll_buttons = [
            button
            for button in bar.findChildren(QToolButton)
            if button.parent() is bar and button.isVisible()
        ]
        assert len(scroll_buttons) == 2
        assert {
            button.objectName() for button in scroll_buttons
        } == {"ScrollLeftButton", "ScrollRightButton"}
        assert {
            button.accessibleName() for button in scroll_buttons
        } == {
            "Scroll panel tabs left",
            "Scroll panel tabs right",
        }
        for button in scroll_buttons:
            assert button.width() >= 24
            assert button.height() >= 28
            assert button.toolTip() == button.accessibleName()

        bar.setCurrentIndex(bar.count() - 1)
        qapp.processEvents()
        last_rect = bar.tabRect(bar.count() - 1)
        assert last_rect.intersects(bar.rect())

        bar.setCurrentIndex(0)
        qapp.processEvents()
        assert bar.tabRect(0).intersects(bar.rect())
    finally:
        _dispose_windows(qapp, window)


def test_styler_configures_dock_tab_bars_created_after_startup(
    qapp,
    dark_dock_stylesheet,
):
    window = QMainWindow()
    window.setCentralWidget(QWidget(window))
    styler = DockTabStyler(window)
    window.resize(700, 360)
    window.show()
    qapp.processEvents()
    try:
        output = _add_dock(window, "Output", "dynamicOutputDock")
        search = _add_dock(window, "Search", "dynamicSearchDock")
        window.tabifyDockWidget(output, search)
        qapp.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.MetaCall)
        qapp.processEvents()

        bar = _bar_with_titles(window, {"Output", "Search"})
        assert bar.objectName() == DOCK_TAB_BAR_OBJECT_NAME
        assert bar.property("panelTabs") is True
        assert bar.accessibleName() == "Docked panel tabs"
        assert bar.focusPolicy() == Qt.FocusPolicy.TabFocus
    finally:
        _dispose_windows(qapp, window)


def test_styler_configures_tab_bar_recreated_by_layout_restore(
    qapp,
    dark_dock_stylesheet,
):
    source, _docks, _styler, _bar = _make_tabbed_window(qapp)
    state = source.saveState()

    target = QMainWindow()
    target.setCentralWidget(QWidget(target))
    _add_dock(target, "Output", "panelDock0")
    _add_dock(
        target,
        "AI Chat",
        "panelDock1",
        Qt.DockWidgetArea.RightDockWidgetArea,
    )
    _add_dock(target, "Search", "panelDock2")
    target_styler = DockTabStyler(target)
    target.resize(900, 360)
    target.show()
    qapp.processEvents()
    try:
        assert target.restoreState(state) is True
        qapp.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.MetaCall)
        qapp.processEvents()
        target_styler.refresh()

        bar = _bar_with_titles(target, {"Output", "AI Chat", "Search"})
        assert bar.objectName() == DOCK_TAB_BAR_OBJECT_NAME
        assert bar.property("panelTabs") is True
        assert bar.accessibleName() == "Docked panel tabs"
        assert bar.usesScrollButtons() is True
    finally:
        _dispose_windows(qapp, target, source)


def test_dock_tab_styler_does_not_reconfigure_editor_tab_bar(
    qapp,
    dark_dock_stylesheet,
):
    window = QMainWindow()
    editor_tabs = QTabWidget(window)
    editor_tabs.setObjectName("editorTabs")
    editor_tabs.addTab(QWidget(editor_tabs), "first.py")
    editor_tabs.addTab(QWidget(editor_tabs), "second.py")
    window.setCentralWidget(editor_tabs)

    output = _add_dock(window, "Output", "isolationOutputDock")
    search = _add_dock(window, "Search", "isolationSearchDock")
    window.tabifyDockWidget(output, search)
    editor_bar = editor_tabs.tabBar()
    window.resize(900, 360)
    window.show()
    qapp.processEvents()
    editor_state = (
        editor_bar.objectName(),
        editor_bar.property("panelTabs"),
        editor_bar.expanding(),
        editor_bar.elideMode(),
        editor_bar.accessibleName(),
        editor_bar.accessibleDescription(),
    )

    styler = DockTabStyler(window)
    styler.refresh()
    try:
        dock_bar = _bar_with_titles(window, {"Output", "Search"})
        assert dock_bar is not editor_bar
        assert dock_bar.objectName() == DOCK_TAB_BAR_OBJECT_NAME
        assert editor_bar.property("panelTabs") is not True
        assert (
            editor_bar.objectName(),
            editor_bar.property("panelTabs"),
            editor_bar.expanding(),
            editor_bar.elideMode(),
            editor_bar.accessibleName(),
            editor_bar.accessibleDescription(),
        ) == editor_state
    finally:
        _dispose_windows(qapp, window)


@pytest.mark.parametrize(
    ("theme_name", "custom_base", "custom_accent"),
    [
        ("default_light", "light", None),
        ("default_dark", "dark", None),
        ("default_high_contrast", "dark", None),
        ("custom", "light", "#336699"),
        ("custom", "dark", "#336699"),
    ],
)
def test_stylesheets_define_complete_dock_tab_states_and_scoped_overflow(
    theme_name,
    custom_base,
    custom_accent,
):
    stylesheet = get_stylesheet(
        theme_name,
        custom_base=custom_base,
        custom_accent=custom_accent,
    )

    selectors = (
        "QMainWindow > QTabBar",
        "QMainWindow > QTabBar::tab",
        "QMainWindow > QTabBar::tab:first",
        "QMainWindow > QTabBar::tab:hover:!selected",
        "QMainWindow > QTabBar::tab:pressed:!selected",
        "QMainWindow > QTabBar::tab:selected",
        'QTabBar#dockPanelTabs[panelKeyboardFocus="true"]::tab:selected',
        'QTabBar#dockPanelTabs[panelPressed="true"]::tab:selected',
        "QMainWindow > QTabBar::tab:disabled",
        "QTabBar#dockPanelTabs::scroller",
        "QTabBar#dockPanelTabs > QToolButton",
        "QTabBar#dockPanelTabs > QToolButton:hover",
        "QTabBar#dockPanelTabs > QToolButton:pressed",
        "#editorTabs QTabBar::scroller",
        "#editorTabs QTabBar > QToolButton",
    )
    for selector in selectors:
        _rule_block(stylesheet, selector)

    dock_tab_block = _rule_block(
        stylesheet,
        "QMainWindow > QTabBar::tab",
    )
    dock_scroller_block = _rule_block(
        stylesheet,
        "QTabBar#dockPanelTabs::scroller",
    )
    dock_button_block = _rule_block(
        stylesheet,
        "QTabBar#dockPanelTabs > QToolButton",
    )
    rounded_selected_blocks = (
        _rule_block(stylesheet, "QMainWindow > QTabBar::tab:selected"),
        _rule_block(
            stylesheet,
            'QTabBar#dockPanelTabs[panelKeyboardFocus="true"]::tab:selected',
        ),
        _rule_block(
            stylesheet,
            'QTabBar#dockPanelTabs[panelPressed="true"]::tab:selected',
        ),
    )
    assert "min-height: 31px" in dock_tab_block
    assert "min-width: 68px" in dock_tab_block
    assert "width: 52px" in dock_scroller_block
    assert "min-width: 18px" in dock_button_block
    assert "min-height: 26px" in dock_button_block
    for block in rounded_selected_blocks:
        assert "border-radius: 6px" in block
    assert "{{" not in dock_tab_block
    assert "{{" not in dock_scroller_block
    assert "{{" not in dock_button_block
    assert "\nQTabBar::scroller {" not in stylesheet
    assert "\nQTabBar > QToolButton {" not in stylesheet

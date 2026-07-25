"""Polish and accessibility behavior for QMainWindow-owned dock tab bars."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, QTimer, Qt
from PyQt6.QtWidgets import QMainWindow, QTabBar, QToolButton


DOCK_TAB_BAR_OBJECT_NAME = "dockPanelTabs"


class DockTabStyler(QObject):
    """Configure the private QTabBars Qt creates for tabified docks.

    QMainWindow can destroy and recreate these bars when a saved layout is
    restored or a dock is dragged into a new group.  The styler therefore
    discovers bars idempotently and watches the window for future additions.
    """

    def __init__(self, window: QMainWindow):
        super().__init__(window)
        self._window = window
        self._refresh_queued = False
        window.installEventFilter(self)
        window.tabifiedDockWidgetActivated.connect(self._queue_refresh)
        self.refresh()

    def refresh(self) -> None:
        """Apply panel-tab behavior to every QMainWindow-owned tab bar."""
        for bar in self._window.findChildren(QTabBar):
            if bar.parent() is self._window:
                self._configure_bar(bar)

    def _configure_bar(self, bar: QTabBar) -> None:
        bar.setObjectName(DOCK_TAB_BAR_OBJECT_NAME)
        bar.setProperty("panelTabs", True)
        if bar.property("panelKeyboardFocus") is None:
            bar.setProperty("panelKeyboardFocus", False)
        if bar.property("panelPressed") is None:
            bar.setProperty("panelPressed", False)
        # An object-name change after the application stylesheet was applied
        # needs an explicit polish pass on some Windows Qt styles.
        bar.style().unpolish(bar)
        bar.style().polish(bar)
        bar.setDrawBase(False)
        bar.setExpanding(False)
        bar.setUsesScrollButtons(True)
        bar.setElideMode(Qt.TextElideMode.ElideRight)
        # TabFocus keeps the accent outline keyboard-only; mouse clicks still
        # activate tabs without leaving a persistent focus ring behind.
        bar.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        bar.setMouseTracking(True)
        bar.setAccessibleName("Docked panel tabs")
        bar.setAccessibleDescription(
            "Switch between docked panels. Use the Left and Right arrow keys."
        )
        bar.installEventFilter(self)
        self._refresh_tab_tooltips(bar)
        self._configure_scroll_buttons(bar)
        bar.updateGeometry()
        bar.update()

    @staticmethod
    def _refresh_tab_tooltips(bar: QTabBar) -> None:
        for index in range(bar.count()):
            bar.setTabToolTip(index, bar.tabText(index).replace("&", ""))

    @staticmethod
    def _configure_scroll_buttons(bar: QTabBar) -> None:
        for button in bar.findChildren(QToolButton):
            if button.arrowType() == Qt.ArrowType.LeftArrow:
                label = "Scroll panel tabs left"
            elif button.arrowType() == Qt.ArrowType.RightArrow:
                label = "Scroll panel tabs right"
            else:
                continue
            button.setAccessibleName(label)
            button.setToolTip(label)
            # The ancestor bar receives its scoped object name at runtime;
            # repolish native scroll buttons so descendant QSS applies on the
            # first theme pass rather than only after a later theme switch.
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

    def _queue_refresh(self, *_args) -> None:
        if self._refresh_queued:
            return
        self._refresh_queued = True
        QTimer.singleShot(0, self._run_queued_refresh)

    def _run_queued_refresh(self) -> None:
        self._refresh_queued = False
        self.refresh()

    @staticmethod
    def _set_visual_state(bar: QTabBar, name: str, enabled: bool) -> None:
        if bool(bar.property(name)) == enabled:
            return
        bar.setProperty(name, enabled)
        bar.style().unpolish(bar)
        bar.style().polish(bar)
        bar.update()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched is self._window and event.type() == QEvent.Type.ChildAdded:
            # QMainWindow can announce a child before Qt has completed the
            # private QTabBar's derived-class construction. Always defer the
            # type check until the next event-loop turn.
            self._queue_refresh()
        elif watched is self._window and event.type() in {
            QEvent.Type.WindowDeactivate,
            QEvent.Type.Hide,
        }:
            for bar in self._window.findChildren(QTabBar):
                if bar.property("panelTabs"):
                    self._set_visual_state(bar, "panelPressed", False)

        if isinstance(watched, QTabBar) and watched.property("panelTabs"):
            if event.type() == QEvent.Type.FocusIn:
                is_keyboard_focus = event.reason() in {
                    Qt.FocusReason.TabFocusReason,
                    Qt.FocusReason.BacktabFocusReason,
                    Qt.FocusReason.ShortcutFocusReason,
                }
                self._set_visual_state(
                    watched,
                    "panelKeyboardFocus",
                    is_keyboard_focus,
                )
            elif event.type() == QEvent.Type.FocusOut:
                self._set_visual_state(watched, "panelKeyboardFocus", False)
                self._set_visual_state(watched, "panelPressed", False)
            elif event.type() == QEvent.Type.MouseButtonPress:
                is_tab_press = (
                    event.button() == Qt.MouseButton.LeftButton
                    and watched.tabAt(event.position().toPoint()) >= 0
                )
                self._set_visual_state(watched, "panelPressed", is_tab_press)
            elif event.type() in {
                QEvent.Type.MouseButtonRelease,
                QEvent.Type.UngrabMouse,
                QEvent.Type.WindowDeactivate,
                QEvent.Type.Hide,
            }:
                self._set_visual_state(watched, "panelPressed", False)
            elif event.type() == QEvent.Type.MouseMove:
                index = watched.tabAt(event.position().toPoint())
                if index >= 0:
                    watched.setCursor(Qt.CursorShape.PointingHandCursor)
                    watched.setTabToolTip(
                        index,
                        watched.tabText(index).replace("&", ""),
                    )
                else:
                    watched.unsetCursor()
            elif event.type() == QEvent.Type.Leave:
                self._set_visual_state(watched, "panelPressed", False)
                watched.unsetCursor()

        return super().eventFilter(watched, event)

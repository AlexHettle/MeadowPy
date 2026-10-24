from pathlib import Path

import pytest
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent, QKeySequence

import meadowpy.pyqtterm as pyqtterm_module
from meadowpy.ui.terminal_panel import TerminalPanel


class FakeSettings:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key, default=None):
        return self.values.get(key, default)


def _shortcut_override(key, modifiers):
    event = QKeyEvent(QEvent.Type.ShortcutOverride, key, modifiers, "")
    event.ignore()
    return event


def test_terminal_panel_defaults_to_home_directory_and_settings_font(qapp):
    panel = TerminalPanel(
        settings=FakeSettings(
            {"editor.font_family": "Consolas", "editor.font_size": 17}
        )
    )
    try:
        assert panel._working_directory == str(Path.home())
        assert panel._terminal_view._term_cwd == str(Path.home())
        assert panel._terminal_view._term_font_name == pyqtterm_module._TERM_DEFAULT_FONT_FAMILY
        assert panel._terminal_view._term_font_size == 17
    finally:
        panel.stop()


def test_terminal_panel_without_settings_uses_default_font_size(qapp):
    panel = TerminalPanel()
    try:
        assert panel._terminal_view._term_font_size == 13
    finally:
        panel.stop()


def test_terminal_panel_working_directory_is_forwarded(qapp, tmp_path):
    panel = TerminalPanel()
    try:
        panel.set_working_directory(str(tmp_path))
        assert panel._working_directory == str(tmp_path)
        assert panel._terminal_view._term_cwd == str(tmp_path)

        panel.set_working_directory("")
        assert panel._working_directory == str(Path.home())
        assert panel._terminal_view._term_cwd == str(Path.home())
    finally:
        panel.stop()


def test_terminal_panel_update_font_size_keeps_font_family(qapp):
    panel = TerminalPanel(settings=FakeSettings({"editor.font_family": "Arial"}))
    try:
        family = panel._terminal_view._term_font_name
        assert family == pyqtterm_module._TERM_DEFAULT_FONT_FAMILY
        before = panel._terminal_view.charheight

        panel.update_font_size(30)
        assert panel._terminal_view._term_font_size == 30
        assert panel._terminal_view._term_font_name == family
        assert panel._terminal_view.charheight > before

        panel.update_font_size(0)
        assert panel._terminal_view._term_font_size == 13
    finally:
        panel.stop()


@pytest.mark.parametrize(
    ("values", "foreground", "background"),
    [
        ({"editor.theme": "default_dark"}, "#CCCCCC", "#1E1E1E"),
        ({"editor.theme": "default_light"}, "#1E1E1E", "#FFFFFF"),
        ({"editor.theme": "default_high_contrast"}, "#FFFFFF", "#000000"),
        (
            {"editor.theme": "custom", "editor.custom_theme.base": "light"},
            "#1E1E1E",
            "#FFFFFF",
        ),
        (
            {"editor.theme": "custom", "editor.custom_theme.base": "dark"},
            "#CCCCCC",
            "#1E1E1E",
        ),
    ],
)
def test_terminal_panel_refresh_theme_recolors_terminal(
    qapp, values, foreground, background
):
    panel = TerminalPanel(settings=FakeSettings(values))
    try:
        panel.refresh_theme()
        assert panel._terminal_view._default_fg.name().upper() == foreground
        assert panel._terminal_view._default_bg.name().upper() == background
    finally:
        panel.stop()


def test_terminal_panel_restarts_shell_after_it_stops(qapp, monkeypatch):
    panel = TerminalPanel()
    restarts = []
    monkeypatch.setattr(panel._terminal_view, "restart", lambda: restarts.append(True))
    try:
        panel._on_terminal_stopped()
        qapp.processEvents()
        assert restarts == [True]
    finally:
        panel.stop()


def test_terminal_panel_stop_does_not_restart_shell(qapp, monkeypatch):
    panel = TerminalPanel()
    restarts = []
    monkeypatch.setattr(panel._terminal_view, "restart", lambda: restarts.append(True))

    panel.stop()
    qapp.processEvents()

    assert restarts == []
    assert panel._terminal_view._closed is True


def test_terminal_panel_toggle_shortcut_passes_through_terminal(qapp):
    panel = TerminalPanel()
    try:
        panel.toggleViewAction().setShortcut(QKeySequence("Ctrl+Shift+T"))
        toggle = _shortcut_override(
            Qt.Key.Key_T,
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
        )
        other = _shortcut_override(
            Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier
        )

        qapp.sendEvent(panel._terminal_view, toggle)
        qapp.sendEvent(panel._terminal_view, other)

        assert toggle.isAccepted() is False
        assert other.isAccepted() is True
    finally:
        panel.stop()


def test_terminal_panel_focus_terminal_focuses_view(qapp, monkeypatch):
    panel = TerminalPanel()
    calls = []
    monkeypatch.setattr(panel._terminal_view, "setFocus", lambda: calls.append("focus"))
    try:
        panel.focus_terminal()
        assert calls == ["focus"]
    finally:
        panel.stop()


def test_terminal_panel_toggle_on_focuses_the_terminal_and_toggle_off_does_not(
    qapp, monkeypatch
):
    panel = TerminalPanel()
    focused = []
    monkeypatch.setattr(panel, "focus_terminal", lambda: focused.append(True))
    try:
        panel._on_toggle_triggered(False)
        qapp.processEvents()
        assert focused == []

        panel._on_toggle_triggered(True)
        qapp.processEvents()
        assert focused == [True]
    finally:
        panel.stop()


def test_terminal_panel_does_not_restart_a_shell_after_shutdown_began(qapp, monkeypatch):
    panel = TerminalPanel()
    restarts = []
    monkeypatch.setattr(panel._terminal_view, "restart", lambda: restarts.append(True))
    try:
        panel._on_terminal_stopped()
        panel._mark_stopping()
        qapp.processEvents()

        assert restarts == []
    finally:
        panel.stop()


def test_terminal_panel_restarts_a_shell_that_exited_on_its_own(qapp, monkeypatch):
    panel = TerminalPanel()
    restarts = []
    monkeypatch.setattr(panel._terminal_view, "restart", lambda: restarts.append(True))
    try:
        panel._terminal_view.stopped.emit()
        qapp.processEvents()

        assert restarts == [True]
    finally:
        panel.stop()

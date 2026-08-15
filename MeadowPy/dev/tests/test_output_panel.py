from types import SimpleNamespace

import pytest

from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QColor, QKeyEvent, QTextCursor

from meadowpy.ui.output_panel import OutputPanel
from meadowpy.ui.output_text_formatting import (
    TRACEBACK_RE,
    normalize_output_text,
    stderr_text_formats,
    stream_text_format,
)


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)


class MutableSettings:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


def test_recolor_for_theme_replays_history_and_preserves_error_tail(qapp):
    settings = MutableSettings({"editor.theme": "default_dark"})
    panel = OutputPanel(settings=settings)
    stderr = (
        'Traceback\n'
        '  File "C:/tmp/demo.py", line 12, in <module>\n'
        "ZeroDivisionError: division by zero\n"
    )

    panel.append_output("hello\r\n", "stdout")
    panel.append_output("hint\n", "hint")
    panel.append_output(stderr, "stderr")

    before_text = panel._output_text.toPlainText()
    before_history = list(panel._output_history)
    before_error = panel._last_error_text
    before_hint_icon = panel._output_text._hint_icon.cacheKey()

    settings.set("editor.theme", "default_high_contrast")
    panel.recolor_for_theme()

    assert panel._output_text.toPlainText() == before_text
    assert panel._output_history == before_history
    assert panel._last_error_text == before_error
    assert panel._last_error_text.count("ZeroDivisionError") == 1
    assert not panel._fix_btn.isHidden()
    assert not panel._fix_separator.isHidden()
    assert panel._output_text._hint_icon.cacheKey() != before_hint_icon
    hint_block = panel._output_text.document().findBlockByNumber(1)
    assert hint_block.userData() is not None
    assert panel._output_text.viewportMargins().left() == 22

    panel.deleteLater()


@pytest.mark.parametrize(
    ("values", "expected_color"),
    [
        ({"editor.theme": "default_light"}, "#2E7D32"),
        ({"editor.theme": "default_dark"}, "#2F7A44"),
        ({
            "editor.theme": "custom",
            "editor.custom_theme.base": "light",
            "editor.custom_theme.accent": "#7A3EE6",
        }, "#7A3EE6"),
        ({"editor.theme": "default_high_contrast"}, "#FFFFFF"),
    ],
)
def test_error_hint_uses_theme_tinted_lightbulb_without_changing_plain_text(
    qapp,
    values,
    expected_color,
):
    panel = OutputPanel(settings=MutableSettings(values))

    panel.append_output("Check the variable name.\n", "hint")

    assert panel._output_text.toPlainText() == "Check the variable name.\n"
    hint_block = panel._output_text.document().begin()
    assert hint_block.userData() is not None

    panel.resize(700, 300)
    panel.show()
    qapp.processEvents()
    editor = panel._output_text
    text_start = editor.viewport().mapTo(
        editor,
        editor.cursorRect(QTextCursor(hint_block)).topLeft(),
    ).x()
    icon_left = (
        editor._hint_gutter.geometry().left()
        + (editor._hint_gutter.width() - editor.HINT_ICON_SIZE) // 2
    )
    assert icon_left + editor.HINT_ICON_SIZE < text_start

    image = panel._output_text._hint_icon.pixmap(16, 16).toImage()
    opaque_colors = {
        image.pixelColor(x, y).name().upper()
        for y in range(image.height())
        for x in range(image.width())
        if image.pixelColor(x, y).alpha() == 255
    }
    assert QColor(expected_color).name().upper() in opaque_colors
    assert sum(
        1
        for y in range(image.height())
        for x in range(image.width())
        if image.pixelColor(x, y).alpha() == 255
    ) >= 35

    panel.deleteLater()


def test_set_running_resets_error_state_and_switches_input_metadata(qapp):
    panel = OutputPanel(settings=MutableSettings({"editor.theme": "default_dark"}))
    panel.append_output("RuntimeError: boom\n", "stderr")
    panel.set_input_text("pending")

    assert panel._last_error_text
    assert not panel._fix_btn.isHidden()
    assert panel._send_btn.isEnabled()

    panel.set_running(True)

    assert panel._mode == panel._MODE_STDIN
    assert panel._last_error_text == ""
    assert panel._fix_btn.isHidden()
    assert panel._fix_separator.isHidden()
    assert panel._prompt_label.text() == "Input:"
    assert panel._input_line.placeholderText() == "Enter input..."
    assert panel._send_btn.toolTip().startswith("Send input")
    assert panel._send_btn.accessibleName() == "Send input"
    assert not panel._send_btn.isEnabled()

    panel.set_running(False)

    assert panel._mode == panel._MODE_REPL
    assert panel._prompt_label.text() == ">>>"
    assert panel._input_line.placeholderText() == "Type Python here..."
    assert panel._send_btn.toolTip().startswith("Run the command")
    assert panel._send_btn.accessibleName() == "Run command"

    panel.deleteLater()


def test_input_row_uses_symmetric_spacing_to_center_controls(qapp):
    panel = OutputPanel(settings=MutableSettings({"editor.theme": "default_dark"}))

    container_margins = panel.widget().layout().contentsMargins()
    input_margins = panel._input_area.layout().contentsMargins()

    assert container_margins.bottom() == 0
    assert input_margins.top() == input_margins.bottom() == 9
    assert panel._input_line.minimumHeight() == panel._input_line.maximumHeight()
    assert panel._send_btn.minimumHeight() == panel._send_btn.maximumHeight()
    assert panel._input_line.minimumHeight() == panel._send_btn.minimumHeight()

    panel.deleteLater()


def test_repl_history_shortcuts_are_ignored_in_stdin_mode(qapp):
    panel = OutputPanel(settings=MutableSettings({"editor.theme": "default_dark"}))
    history_up = Recorder()
    history_down = Recorder()
    panel.repl_history_up.connect(history_up)
    panel.repl_history_down.connect(history_down)

    up_event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Up,
        Qt.KeyboardModifier.NoModifier,
    )
    down_event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Down,
        Qt.KeyboardModifier.NoModifier,
    )

    assert panel.eventFilter(panel._input_line, up_event) is True
    assert panel.eventFilter(panel._input_line, down_event) is True
    assert history_up.calls == [()]
    assert history_down.calls == [()]

    panel.set_running(True)

    stdin_up_event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Up,
        Qt.KeyboardModifier.NoModifier,
    )
    stdin_down_event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Down,
        Qt.KeyboardModifier.NoModifier,
    )

    assert panel.eventFilter(panel._input_line, stdin_up_event) is False
    assert panel.eventFilter(panel._input_line, stdin_down_event) is False
    assert history_up.calls == [()]
    assert history_down.calls == [()]

    panel.deleteLater()


class _RecordingSignal:
    def __init__(self):
        self.calls = []

    def emit(self, *args):
        self.calls.append(args)


class _FakeBlock:
    def __init__(self, text):
        self._text = text

    def text(self):
        return self._text


class _FakeCursor:
    def __init__(self, line_text):
        self._line_text = line_text

    def block(self):
        return _FakeBlock(self._line_text)


class _FakeOutputText:
    def __init__(self, line_text):
        self._line_text = line_text
        self._viewport = object()
        self.positions = []

    def viewport(self):
        return self._viewport

    def cursorForPosition(self, pos):
        self.positions.append(pos)
        return _FakeCursor(self._line_text)


class _FakeMousePress:
    def __init__(self):
        self._position = QPointF(4, 8)

    def type(self):
        return QEvent.Type.MouseButtonPress

    def position(self):
        return self._position


def test_traceback_click_event_emits_navigation_target():
    output_text = _FakeOutputText(
        '  File "C:/tmp/demo.py", line 12, in <module>'
    )
    signal = _RecordingSignal()
    panel = SimpleNamespace(
        _output_text=output_text,
        traceback_navigate=signal,
    )

    handled = OutputPanel.eventFilter(
        panel,
        output_text.viewport(),
        _FakeMousePress(),
    )

    assert handled is True
    assert signal.calls == [("C:/tmp/demo.py", 12)]


def test_copy_output_leaves_clipboard_unchanged_when_empty(qapp):
    panel = OutputPanel(settings=MutableSettings({"editor.theme": "default_dark"}))
    qapp.clipboard().setText("existing clipboard")

    panel.copy_output()

    assert qapp.clipboard().text() == "existing clipboard"
    panel.deleteLater()


def test_font_and_accent_updates_refresh_output_panel_controls(qapp):
    panel = OutputPanel(settings=MutableSettings({"editor.theme": "default_dark"}))
    refreshes = []
    panel._refresh_send_arrow_icon = lambda: refreshes.append("refresh")
    original_restart_icon = panel._restart_repl_btn.icon().cacheKey()
    initial_restart_glow = next(
        entry for entry in panel._header_glow._entries
        if entry["btn"] is panel._restart_repl_btn
    )
    assert initial_restart_glow["color"].name().upper() == "#2F7A44"

    panel.update_font("Consolas", 17)
    panel.update_accent_color("#123456")

    assert panel._output_text.font().pointSize() == 17
    assert panel._input_line.font().pointSize() == 17
    assert refreshes == ["refresh"]
    assert panel._restart_repl_btn.icon().cacheKey() != original_restart_icon
    restart_glow = next(
        entry for entry in panel._header_glow._entries
        if entry["btn"] is panel._restart_repl_btn
    )
    assert restart_glow["color"].name().upper() == "#123456"
    restart_image = panel._restart_repl_btn.icon().pixmap(16, 16).toImage()
    center = restart_image.pixelColor(
        restart_image.width() // 2,
        restart_image.height() // 2,
    )
    assert center.name().upper() == "#123456"

    panel.deleteLater()


def test_output_text_formatting_helpers_cover_theme_specific_formats():
    assert normalize_output_text("a\r\nb\rc") == "a\nbc"
    assert TRACEBACK_RE.match('  File "C:/tmp/demo.py", line 42').groups() == (
        "C:/tmp/demo.py",
        "42",
    )

    hint = stream_text_format("hint", "default_dark")
    system = stream_text_format("system", "default_dark")
    stderr, link = stderr_text_formats("default_high_contrast")

    assert hint.fontItalic() is True
    assert hint.foreground().color().name().upper() == "#4EC9B0"
    assert system.fontItalic() is True
    assert system.foreground().color().name().upper() == "#888888"
    assert stderr.foreground().color().name().upper() == "#FFFFFF"
    assert link.foreground().color().name().upper() == "#FFFFFF"
    assert link.fontUnderline() is True

"""Widget behavior of the terminal: process lifecycle, resizing, keyboard,
selection, clipboard, mouse, wheel and painting.

The PTY and subprocess layers are replaced by small fakes (with the
platform switch patched) so every code path runs on every operating
system; only the tests marked as real-PTY tests spawn an actual shell.
"""

import os
import struct
import time
from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QEvent, QPoint, QPointF, QRect, QSize, Qt
from PyQt6.QtGui import (
    QColor,
    QFocusEvent,
    QInputMethodEvent,
    QKeyEvent,
    QMouseEvent,
    QPalette,
    QResizeEvent,
    QShowEvent,
    QWheelEvent,
)
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

import meadowpy.pyqtterm as pyqtterm_module
from meadowpy.pyqtterm import Terminal, _term_kill_pty_process
from tests.terminal_helpers import cursor, fit_to_grid, make_terminal, screen

# posix_pty and windows_pty replace Terminal._read; the reader tests need the
# real one.
REAL_READ = Terminal._read

NO_MODS = Qt.KeyboardModifier.NoModifier
CTRL = Qt.KeyboardModifier.ControlModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier
ALT = Qt.KeyboardModifier.AltModifier


@pytest.fixture
def term(qapp):
    terminal = make_terminal()
    yield terminal
    terminal.stop()


@pytest.fixture
def small(qapp):
    terminal = make_terminal(cols=5, rows=3)
    yield terminal
    terminal.stop()


class FakeProcess:
    """Stands in for both subprocess.Popen and a winpty process."""

    pid = 4242

    def __init__(self, polls=(None,), reads=()):
        self.polls = list(polls)
        self.reads = list(reads)
        self.terminated = False
        self.closed = False
        self.waited = False
        self.written = []
        self.window_sizes = []

    def poll(self):
        return self.polls.pop(0) if len(self.polls) > 1 else self.polls[0]

    def terminate(self):
        self.terminated = True

    def wait(self):
        self.waited = True
        return 0

    def close(self):
        self.closed = True

    def read(self, size):
        if not self.reads:
            raise EOFError
        return self.reads.pop(0)

    def write(self, text):
        self.written.append(text)

    def setwinsize(self, rows, cols):
        self.window_sizes.append((rows, cols))


def next_select(calls):
    """The next scripted select() answer; a callable entry runs first (to
    write more data into the pipe) and returns the answer."""
    entry = calls.selects.pop(0)
    return entry() if callable(entry) else entry


@pytest.fixture
def posix_pty(monkeypatch):
    """Make Terminal use its POSIX code path with fake pty/fcntl/termios/
    signal/select modules and a recording Popen, on any platform."""
    first_pipe = os.pipe()
    opened = [first_pipe]
    calls = SimpleNamespace(
        master=first_pipe[0],
        slave=first_pipe[1],
        ioctls=[],
        killpgs=[],
        popen_args=None,
        popen_kwargs=None,
        process=FakeProcess(),
        selects=[],
    )

    def fake_popen(argv, **kwargs):
        calls.popen_args = argv
        calls.popen_kwargs = kwargs
        return calls.process

    def fake_openpty():
        if len(opened) > 1 or calls.opened_first:
            opened.append(os.pipe())
        calls.opened_first = True
        calls.master, calls.slave = opened[-1]
        return calls.master, calls.slave

    calls.opened_first = False
    monkeypatch.setattr(pyqtterm_module, "_TERM_USES_POSIX_PTY", True)
    monkeypatch.setattr(
        pyqtterm_module, "pty", SimpleNamespace(openpty=fake_openpty), raising=False
    )
    monkeypatch.setattr(
        pyqtterm_module,
        "fcntl",
        SimpleNamespace(ioctl=lambda *args: calls.ioctls.append(args)),
        raising=False,
    )
    monkeypatch.setattr(
        pyqtterm_module, "termios", SimpleNamespace(TIOCSWINSZ=0x5414), raising=False
    )
    monkeypatch.setattr(pyqtterm_module, "struct", struct, raising=False)
    monkeypatch.setattr(
        pyqtterm_module, "signal", SimpleNamespace(SIGWINCH=28), raising=False
    )
    monkeypatch.setattr(
        pyqtterm_module,
        "select",
        SimpleNamespace(select=lambda r, w, x, t: next_select(calls)),
        raising=False,
    )
    monkeypatch.setattr(
        os, "killpg", lambda pid, sig: calls.killpgs.append((pid, sig)), raising=False
    )
    monkeypatch.setattr(pyqtterm_module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(Terminal, "_read", lambda self, *args: None)
    yield calls
    for pair in opened:
        for descriptor in pair:
            try:
                os.close(descriptor)
            except OSError:
                pass


@pytest.fixture
def windows_pty(monkeypatch):
    """Make Terminal use its Windows code path with a fake winpty."""
    calls = SimpleNamespace(spawn_args=None, spawn_kwargs=None, process=FakeProcess())

    def fake_spawn(argv, **kwargs):
        calls.spawn_args = argv
        calls.spawn_kwargs = kwargs
        return calls.process

    monkeypatch.setattr(pyqtterm_module, "_TERM_USES_POSIX_PTY", False)
    monkeypatch.setattr(
        pyqtterm_module, "PtyProcess", SimpleNamespace(spawn=fake_spawn), raising=False
    )
    monkeypatch.setattr(Terminal, "_read", lambda self, *args: None)
    return calls


def press(terminal, key, modifiers=NO_MODS, text=""):
    terminal.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, key, modifiers, text))
    sent = b"".join(terminal.written)
    terminal.written.clear()
    return sent


def mouse_event(kind, x, y, button=Qt.MouseButton.LeftButton, buttons=None, modifiers=NO_MODS):
    position = QPointF(x, y)
    if buttons is None:
        buttons = button
    return QMouseEvent(kind, position, position, button, buttons, modifiers)


def click(terminal, x, y, button=Qt.MouseButton.LeftButton, modifiers=NO_MODS):
    terminal.mousePressEvent(
        mouse_event(QEvent.Type.MouseButtonPress, x, y, button, modifiers=modifiers)
    )


def release(terminal, x, y, button=Qt.MouseButton.LeftButton, modifiers=NO_MODS):
    terminal.mouseReleaseEvent(
        mouse_event(QEvent.Type.MouseButtonRelease, x, y, button, Qt.MouseButton.NoButton, modifiers)
    )


def drag(terminal, x, y, button=Qt.MouseButton.LeftButton, modifiers=NO_MODS):
    terminal.mouseMoveEvent(
        mouse_event(QEvent.Type.MouseMove, x, y, Qt.MouseButton.NoButton, button, modifiers)
    )


def cell_xy(terminal, column, row):
    """Pixel position just inside the given 0-based cell."""
    return column * terminal.charwidth + 1, row * terminal.charheight + 1


def wheel(terminal, delta, modifiers=NO_MODS):
    event = QWheelEvent(
        QPointF(1, 1),
        QPointF(1, 1),
        QPoint(0, 0),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        modifiers,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    terminal.wheelEvent(event)
    return event


# ---------------------------------------------------------------------------
# Colors, fonts and geometry
# ---------------------------------------------------------------------------


def test_default_colors_come_from_the_palette_and_follow_it(term):
    palette = term.palette()
    palette.setColor(QPalette.ColorRole.Text, QColor("#112233"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#445566"))

    term.setPalette(palette)

    assert term._default_fg.name() == "#112233"
    assert term._default_bg.name() == "#445566"
    assert term._paint_fg.name() == "#112233"


def test_explicit_default_colors_override_the_palette_until_cleared(term):
    term.setDefaultColors("#ff0000", "#0000ff")
    assert term._default_fg.name() == "#ff0000"
    assert term._default_bg.name() == "#0000ff"
    assert term._cursor_color.name() == "#ff0000"

    term.setDefaultColors()
    assert term._default_fg == term.palette().color(QPalette.ColorRole.Text)


def test_custom_cursor_color_survives_a_default_color_change(term):
    term._process("\x1b]12;#00ff00\x07")

    term.setDefaultColors("#ff0000", "#0000ff")

    assert term._cursor_color.name() == "#00ff00"


def test_style_colors_resolve_defaults_explicit_colors_and_selection(term):
    term.setDefaultColors("#ffffff", "#000000")

    assert term._style_colors(("@fg", "@bg", 0, 0, 0, 0, 0), False) == (
        QColor("#ffffff"),
        None,
    )
    fg, bg = term._style_colors(("#ff0000", "#00ff00", 0, 0, 0, 0, 0), False)
    assert (fg.name(), bg.name()) == ("#ff0000", "#00ff00")
    fg, bg = term._style_colors(("#ff0000", "#00ff00", 0, 0, 0, 0, 0), True)
    assert (fg.name(), bg.name()) == ("#000000", "#ffffff")


def test_style_colors_are_cached(term):
    style = ("#ff0000", "@bg", 0, 0, 0, 0, 0)

    first = term._style_colors(style, False)

    assert term._style_colors(style, False) is first


def test_font_variants_are_cached_and_styled(term):
    plain = term._term_font_variant()
    bold = term._term_font_variant(bold=True)
    italic = term._term_font_variant(italic=True)

    assert term._term_font_variant() is plain
    assert bold.bold() and not plain.bold()
    assert italic.italic() and not plain.italic()
    assert plain.pointSizeF() == float(term._term_font_size)


def test_font_size_change_remeasures_cells_and_schedules_a_resize(term):
    term._term_started = True
    before = term.charheight
    new_size = term._term_font_size * 2

    term.setTerminalFontSize(new_size)

    assert term.charheight > before
    assert term._term_font_variant().pointSizeF() == float(new_size)
    assert term._resize_timer.isActive()


def test_font_size_change_before_start_does_not_schedule_a_resize(term):
    term.setTerminalFontSize(20)

    assert term._term_font_size == 20
    assert not term._resize_timer.isActive()


def test_size_hint_is_eighty_by_twenty_four_cells(term):
    assert term.sizeHint() == QSize(80 * term.charwidth, 24 * term.charheight)


def test_grid_size_follows_the_viewport(term):
    term.resize(30 * term.charwidth, 7 * term.charheight)
    QApplication.sendEvent(term, QResizeEvent(term.size(), QSize()))

    assert term._term_compute_size() == (30, 7)


def test_working_directory_can_be_set_for_the_next_shell(term):
    term.setWorkingDirectory("/somewhere")

    assert term._term_cwd == "/somewhere"


# ---------------------------------------------------------------------------
# Cursor and blinking
# ---------------------------------------------------------------------------


def test_cursor_type_and_visibility_setters(term):
    term.setcursortype("bar")
    assert term._cursor_shape == "bar"

    term._cursor_set_visible(False)
    assert term._cursor_dectcem_visible is False


def test_cursor_blink_tick_toggles_visibility_and_reschedules(term):
    assert term._cursor_blink_visible is True

    term._cursor_blink_tick()
    assert term._cursor_blink_visible is False
    assert term._cursor_blink_timer.isActive()

    term._cursor_blink_tick()
    assert term._cursor_blink_visible is True


def test_cursor_blink_tick_does_nothing_once_closed(term):
    term._closed = True

    term._cursor_blink_tick()

    assert term._cursor_blink_visible is True


def test_disabling_cursor_blink_stops_the_timer(term):
    term._cursor_set_blink_enabled(False)

    assert not term._cursor_blink_timer.isActive()
    assert term._cursor_blink_visible is True


def test_text_blink_toggles_while_blinking_text_is_painted(term):
    term._blink_painted = True

    term._blink_tick()
    assert term._blink_visible is False

    term._blink_tick()
    assert term._blink_visible is True


def test_text_blink_stops_when_nothing_blinks_any_more(term):
    term._start_blink()
    term._start_blink()
    assert term._blink_timer.isActive()
    term._blink_painted = False
    term._blink_visible = False

    term._blink_tick()

    assert not term._blink_timer.isActive()
    assert term._blink_visible is True


def test_text_blink_stops_once_closed(term):
    term._blink_painted = True
    term._closed = True
    term._start_blink()

    term._blink_tick()

    assert not term._blink_timer.isActive()


# ---------------------------------------------------------------------------
# Painting
# ---------------------------------------------------------------------------


def pixel(terminal, x, y):
    return terminal.grab().toImage().pixelColor(x, y).name()


def painted(qapp, columns=10, rows=3):
    terminal = make_terminal(cols=columns, rows=rows)
    terminal.setDefaultColors("#ffffff", "#000000")
    terminal._cursor_has_focus = False
    return terminal


def test_background_colors_and_default_background_are_painted(qapp):
    terminal = painted(qapp)
    try:
        terminal._process("\x1b[41m \x1b[0m")
        x, y = cell_xy(terminal, 0, 0)

        assert pixel(terminal, x, y) == "#cd0000"
        assert pixel(terminal, *cell_xy(terminal, 5, 1)) == "#000000"
    finally:
        terminal.stop()


def test_block_cursor_is_painted_in_the_foreground_color_when_focused(qapp):
    terminal = painted(qapp)
    try:
        terminal._cursor_has_focus = True
        terminal._cursor_reset_blink_phase()
        terminal._process("\x1b[2;3H")

        assert pixel(terminal, *cell_xy(terminal, 2, 1)) == "#ffffff"
        assert pixel(terminal, *cell_xy(terminal, 3, 1)) == "#000000"
    finally:
        terminal.stop()


def test_cursor_is_not_painted_without_focus_or_when_hidden_or_blinked_off(qapp):
    terminal = painted(qapp)
    try:
        x, y = cell_xy(terminal, 0, 0)
        assert pixel(terminal, x, y) == "#000000"

        terminal._cursor_has_focus = True
        terminal._process("\x1b[?25l")
        assert pixel(terminal, x, y) == "#000000"

        terminal._process("\x1b[?25h")
        terminal._cursor_blink_visible = False
        assert pixel(terminal, x, y) == "#000000"

        terminal._cursor_blink_visible = True
        assert pixel(terminal, x, y) == "#ffffff"
    finally:
        terminal.stop()


def test_bar_and_underline_cursors_cover_only_part_of_the_cell(qapp):
    terminal = painted(qapp)
    try:
        terminal._cursor_has_focus = True
        terminal.setcursortype("bar")
        x, y = cell_xy(terminal, 0, 0)
        assert pixel(terminal, x, y) == "#ffffff"
        assert pixel(terminal, terminal.charwidth - 2, y) == "#000000"

        terminal.setcursortype("underline")
        assert pixel(terminal, x, y) == "#000000"
        assert pixel(terminal, x, terminal.charheight - 1) == "#ffffff"
    finally:
        terminal.stop()


def test_custom_cursor_color_is_painted(qapp):
    terminal = painted(qapp)
    try:
        terminal._cursor_has_focus = True
        terminal._process("\x1b]12;#ff0000\x07")

        assert pixel(terminal, *cell_xy(terminal, 0, 0)) == "#ff0000"
    finally:
        terminal.stop()


def test_block_cursor_covers_both_halves_of_a_wide_character(qapp):
    terminal = painted(qapp)
    try:
        terminal._cursor_has_focus = True
        terminal._process("日\x1b[1;1H")

        assert pixel(terminal, *cell_xy(terminal, 1, 0)) == "#ffffff"
    finally:
        terminal.stop()


def test_block_cursor_inverts_the_character_under_it(qapp):
    terminal = painted(qapp)
    try:
        terminal._cursor_has_focus = True
        terminal._process("W\x1b[1;1H")
        image = terminal.grab().toImage()

        brightness = {
            image.pixelColor(x, y).value()
            for x in range(terminal.charwidth)
            for y in range(terminal.charheight)
        }

        assert image.pixelColor(*cell_xy(terminal, 0, 0)).name() == "#ffffff"
        assert min(brightness) < 128
    finally:
        terminal.stop()


def test_underline_and_strikethrough_are_drawn_across_the_cell(qapp):
    terminal = painted(qapp)
    try:
        terminal._process("\x1b[4m \x1b[0m\x1b[9m \x1b[0m")
        underline_y = terminal._char_ascent + 1
        strike_y = terminal.charheight // 2

        assert pixel(terminal, 1, underline_y) == "#ffffff"
        assert pixel(terminal, 1, strike_y) == "#000000"
        assert pixel(terminal, terminal.charwidth + 1, strike_y) == "#ffffff"
    finally:
        terminal.stop()


def test_selection_is_painted_with_inverted_colors(qapp):
    terminal = painted(qapp)
    try:
        terminal._sel_anchor = (0, 0)
        terminal._sel_head = (1, 4)

        assert pixel(terminal, *cell_xy(terminal, 1, 0)) == "#ffffff"
        assert pixel(terminal, *cell_xy(terminal, 3, 1)) == "#ffffff"
        assert pixel(terminal, *cell_xy(terminal, 4, 1)) == "#000000"
        assert pixel(terminal, *cell_xy(terminal, 1, 2)) == "#000000"
    finally:
        terminal.stop()


def test_blinking_text_marks_the_screen_as_blinking_and_hides_when_off(qapp):
    terminal = painted(qapp)
    try:
        terminal._process("\x1b[5;47m \x1b[0m")
        x, y = cell_xy(terminal, 0, 0)

        terminal.grab()
        assert terminal._blink_painted is True
        assert terminal._blink_timer.isActive()

        terminal._blink_visible = False
        terminal.grab()
        assert pixel(terminal, x, y) == "#e5e5e5"
    finally:
        terminal.stop()


def test_painting_a_view_scrolled_into_scrollback_does_not_fail(qapp):
    terminal = painted(qapp, rows=3)
    try:
        terminal._process("\r\n".join(str(n) for n in range(20)))
        terminal.verticalScrollBar().setValue(0)
        terminal._sel_anchor = (0, 0)
        terminal._sel_head = (2, 1)
        terminal._cursor_has_focus = True

        assert terminal.grab().isNull() is False
    finally:
        terminal.stop()


# ---------------------------------------------------------------------------
# Scrollback and the scrollbar
# ---------------------------------------------------------------------------


def test_scrollbar_range_follows_the_scrollback_and_sticks_to_the_bottom(small):
    small._process("1\r\n2\r\n3\r\n4\r\n5\r\n6")
    small._after_output()
    bar = small.verticalScrollBar()

    assert bar.maximum() == len(small._rows) - 3
    assert bar.value() == bar.maximum()
    assert bar.pageStep() == 3


def test_scrolling_up_stops_following_new_output_until_back_at_the_bottom(small):
    small._process("1\r\n2\r\n3\r\n4\r\n5\r\n6")
    small._after_output()
    bar = small.verticalScrollBar()

    bar.setValue(0)
    assert small._follow_bottom is False
    small._after_output()
    assert bar.value() == 0

    bar.setValue(bar.maximum())
    assert small._follow_bottom is True


def test_scrollback_is_capped_and_the_selection_shifts_with_it(monkeypatch, small):
    monkeypatch.setattr(pyqtterm_module, "_TERM_MAX_SCROLLBACK_LINES", 2)
    small._process("1\r\n2\r\n3\r\n4\r\n5")
    small._sel_anchor = (3, 0)
    small._sel_head = (4, 1)

    small._process("\r\n6")

    assert len(small._rows) == small._nrows + 2
    assert small._sel_anchor == (2, 0)
    assert small._sel_head == (3, 1)


def test_selection_that_scrolls_out_of_the_scrollback_is_dropped(monkeypatch, small):
    monkeypatch.setattr(pyqtterm_module, "_TERM_MAX_SCROLLBACK_LINES", 2)
    small._process("1\r\n2\r\n3\r\n4\r\n5")
    small._sel_anchor = (0, 0)
    small._sel_head = (1, 1)

    small._process("\r\n6")

    assert small._sel_anchor is None
    assert small._sel_head is None


# ---------------------------------------------------------------------------
# Starting the shell
# ---------------------------------------------------------------------------


def test_first_show_starts_the_process_once(qapp, monkeypatch, term):
    starts = []
    monkeypatch.setattr(term, "_start_process", lambda: starts.append(True))

    term.showEvent(QShowEvent())
    term.showEvent(QShowEvent())
    qapp.processEvents()

    assert starts == [True]
    assert term._term_started is True


def test_posix_start_spawns_the_default_shell_on_a_pty(posix_pty, monkeypatch, tmp_path, term):
    monkeypatch.setenv("SHELL", "/bin/fake-shell")
    term._term_cwd = str(tmp_path)
    term.setDefaultColors("#ffffff", "#000000")

    term._start_process()

    assert posix_pty.popen_args[-1] == "/bin/fake-shell"
    assert posix_pty.popen_args[1:3] == ["-I", "-S"]
    kwargs = posix_pty.popen_kwargs
    assert kwargs["cwd"] == str(tmp_path)
    assert kwargs["start_new_session"] is True
    assert "preexec_fn" not in kwargs
    assert kwargs["stdin"] == kwargs["stdout"] == kwargs["stderr"] == posix_pty.slave
    assert kwargs["env"]["TERM"] == "xterm-256color"
    assert kwargs["env"]["COLORTERM"] == "truecolor"
    assert kwargs["env"]["COLORFGBG"] == "15;0"
    assert term.proc is posix_pty.process
    assert term.master_fd == posix_pty.master
    assert term._pty_holder == {"proc": posix_pty.process, "fd": posix_pty.master}
    assert term._read_generation == 1
    ((fd, request, size),) = [call for call in posix_pty.ioctls if call[1] == 0x5414]
    assert fd == posix_pty.master
    assert struct.unpack("HHHH", size)[:2] == (term._nrows, term._cols)


def test_posix_start_runs_a_custom_command_instead_of_the_shell(posix_pty, qapp):
    terminal = make_terminal(command=["top", "-b"])
    try:
        terminal._start_process()

        assert posix_pty.popen_args[-2:] == ["top", "-b"]
    finally:
        terminal.stop()


def test_nocolor_terminal_does_not_set_colorterm_itself(posix_pty, monkeypatch, qapp):
    monkeypatch.delenv("COLORTERM", raising=False)
    terminal = make_terminal(nocolor=True)
    try:
        terminal._start_process()

        assert "COLORTERM" not in posix_pty.popen_kwargs["env"]
    finally:
        terminal.stop()


def test_nocolor_terminal_still_advertises_the_color_support_it_inherited(
    posix_pty, monkeypatch, qapp
):
    monkeypatch.setenv("COLORTERM", "24bit")
    terminal = make_terminal(nocolor=True)
    try:
        terminal._start_process()

        assert posix_pty.popen_kwargs["env"]["COLORTERM"] == "24bit"
        assert posix_pty.popen_kwargs["env"]["TERM"] == "xterm-256color"
    finally:
        terminal.stop()


def test_posix_start_ignores_a_missing_working_directory(posix_pty, tmp_path, term):
    term._term_cwd = str(tmp_path / "missing")

    term._start_process()

    assert posix_pty.popen_kwargs["cwd"] is None


def test_posix_start_closes_the_slave_end_even_if_spawning_fails(
    posix_pty, monkeypatch, term
):
    def failing_popen(argv, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(pyqtterm_module.subprocess, "Popen", failing_popen)

    with pytest.raises(FileNotFoundError):
        term._start_process()

    with pytest.raises(OSError):
        os.close(posix_pty.slave)


def test_posix_start_resets_the_emulator_for_the_new_shell(posix_pty, term):
    term._process("old output")

    term._start_process()

    assert screen(term)[0] == ""


def test_windows_start_spawns_powershell_by_default(windows_pty, tmp_path, term):
    term._term_cwd = str(tmp_path)

    term._start_process()

    assert windows_pty.spawn_args == ["powershell.exe"]
    assert windows_pty.spawn_kwargs["cwd"] == str(tmp_path)
    assert windows_pty.spawn_kwargs["dimensions"] == (term._nrows, term._cols)
    assert term.proc is windows_pty.process
    assert term.master_fd is None


def test_windows_start_runs_a_custom_command(windows_pty, qapp):
    terminal = make_terminal(command=["cmd.exe", "/k"])
    try:
        terminal._start_process()

        assert windows_pty.spawn_args == ["cmd.exe", "/k"]
        assert windows_pty.spawn_kwargs["cwd"] is None
    finally:
        terminal.stop()


# ---------------------------------------------------------------------------
# Reading and writing the PTY
# ---------------------------------------------------------------------------


def isolate_reader(terminal):
    """Stop the reader's wake-up signal from draining the queue the test
    wants to inspect."""
    terminal._output_wake.disconnect(terminal._drain_output)


def run_reader(terminal, posix_pty, writes, selects, polls, fd=None):
    """Run Terminal._read against a real pipe with scripted select()."""
    isolate_reader(terminal)
    for data in writes:
        os.write(posix_pty.slave, data)
    posix_pty.selects.extend(selects)
    process = FakeProcess(polls=polls)
    queue = terminal._out_q
    REAL_READ(
        terminal,
        terminal._read_generation,
        queue,
        posix_pty.master if fd is None else fd,
        process,
    )
    items = []
    while not queue.empty():
        items.append(queue.get_nowait())
    return items


def test_posix_reader_decodes_output_and_signals_the_end(posix_pty, term):
    items = run_reader(
        term,
        posix_pty,
        writes=["héllo".encode()],
        selects=[([posix_pty.master], [], []), ([], [], [])],
        polls=[None, 0],
    )

    assert items == ["héllo", None]


def test_posix_reader_reassembles_multibyte_characters_split_across_reads(posix_pty, term):
    ready = ([posix_pty.master], [], [])

    def second_half_arrives():
        os.write(posix_pty.slave, b"\xa9")
        return ready

    items = run_reader(
        term,
        posix_pty,
        writes=[b"\xc3"],
        selects=[ready, second_half_arrives, ([], [], [])],
        polls=[None, 0],
    )

    assert "".join(item for item in items if item) == "é"
    assert items[-1] is None


def test_posix_reader_stops_at_end_of_file(posix_pty, term):
    os.close(posix_pty.slave)

    items = run_reader(
        term, posix_pty, writes=[], selects=[([posix_pty.master], [], [])], polls=[None]
    )

    assert items == [None]


def test_posix_reader_stops_when_reading_fails(posix_pty, term):
    items = run_reader(
        term,
        posix_pty,
        writes=[],
        selects=[([99999], [], [])],
        polls=[None],
        fd=99999,
    )

    assert items == [None]


def test_reader_of_a_stale_generation_exits_without_output(posix_pty, term):
    term._read_generation = 7

    REAL_READ(term, 3, term._out_q, posix_pty.master, FakeProcess())

    assert term._out_q.empty()


def test_reader_gives_up_on_a_full_queue_once_superseded(posix_pty, term):
    import queue
    import threading

    full = queue.Queue(maxsize=1)
    full.put("pending")
    os.write(posix_pty.slave, b"x")
    posix_pty.selects.append(([posix_pty.master], [], []))
    term._read_generation = 1
    timer = threading.Timer(0.3, lambda: setattr(term, "_read_generation", 2))
    timer.start()

    REAL_READ(term, 1, full, posix_pty.master, FakeProcess())
    timer.join()

    assert full.get_nowait() == "pending"
    assert full.empty()


def test_windows_reader_passes_text_and_decodes_bytes(windows_pty, term):
    process = FakeProcess(reads=["text", "bé".encode()])
    isolate_reader(term)
    term._read_generation = 1

    REAL_READ(term, 1, term._out_q, None, process)

    assert [term._out_q.get_nowait() for _ in range(3)] == ["text", "bé", None]


def test_windows_reader_skips_empty_reads(windows_pty, term):
    process = FakeProcess(reads=["", "x"])
    isolate_reader(term)
    term._read_generation = 1

    REAL_READ(term, 1, term._out_q, None, process)

    assert [term._out_q.get_nowait() for _ in range(2)] == ["x", None]


def test_posix_write_sends_bytes_to_the_pty(posix_pty, qapp):
    terminal = Terminal()
    try:
        terminal.master_fd = posix_pty.slave

        terminal._write(b"typed")

        assert os.read(posix_pty.master, 16) == b"typed"
    finally:
        terminal.master_fd = None
        terminal.stop()


def test_posix_write_to_a_closed_pty_is_ignored(posix_pty, qapp):
    terminal = Terminal()
    try:
        terminal.master_fd = None

        terminal._write(b"lost")
    finally:
        terminal.stop()


def test_windows_write_sends_decoded_text(windows_pty, qapp):
    terminal = Terminal()
    try:
        terminal.proc = windows_pty.process

        terminal._write("é".encode())

        assert windows_pty.process.written == ["é"]
    finally:
        terminal.proc = None
        terminal.stop()


def test_windows_write_without_a_process_is_ignored(windows_pty, qapp):
    terminal = Terminal()
    try:
        terminal._write(b"lost")
    finally:
        terminal.stop()


# ---------------------------------------------------------------------------
# Draining output and the end of the process
# ---------------------------------------------------------------------------


def collect(signal):
    seen = []
    signal.connect(lambda *args: seen.append(args))
    return seen


def test_drain_output_renders_queued_text_and_reports_it(term):
    processed = collect(term.outputProcessed)
    term._out_q.put("hello")
    term._out_q.put("\r\nworld")

    term._drain_output()

    assert screen(term)[:2] == ["hello", "world"]
    assert len(processed) == 1


def test_drain_output_with_nothing_queued_does_nothing(term):
    processed = collect(term.outputProcessed)

    term._drain_output()

    assert processed == []


def test_drain_output_ignores_output_after_the_terminal_closed(term):
    term._out_q.put("late")
    term._closed = True

    term._drain_output()

    assert screen(term)[0] == ""


def test_drain_output_spreads_a_large_backlog_over_several_frames(
    monkeypatch, term
):
    monkeypatch.setattr(pyqtterm_module, "_TERM_FRAME_BUDGET", -1)
    for letter in "abc":
        term._out_q.put(letter)

    term._drain_output()
    assert screen(term)[0] == "a"

    QTest.qWait(200)

    assert screen(term)[0] == "abc"


def test_drain_output_survives_an_emulator_error(monkeypatch, capsys, term):
    def fail(text):
        raise ValueError("boom")

    monkeypatch.setattr(term, "_process", fail)
    term._out_q.put("x")

    term._drain_output()

    assert "ValueError: boom" in capsys.readouterr().err


def test_process_exit_without_end_message_tears_the_terminal_down(qapp, term):
    ended = collect(term.processEnded)
    stopped = collect(term.stopped)
    term._out_q.put("bye")
    term._out_q.put(None)

    term._drain_output()
    qapp.processEvents()

    assert screen(term)[0] == "bye"
    assert term.running is False
    assert len(ended) == 1
    assert len(stopped) == 1


def test_process_exit_with_end_message_waits_for_a_key(qapp):
    terminal = make_terminal(endmessage="[done]\nbye")
    try:
        stopped = collect(terminal.stopped)
        terminal._process("output")
        terminal._out_q.put(None)

        terminal._drain_output()

        assert terminal._awaiting_key is True
        assert stopped == []
        assert screen(terminal)[:4] == ["output", "", "", "[done]"]
        assert screen(terminal)[4] == "bye"

        press(terminal, Qt.Key.Key_X, text="x")
        assert len(stopped) == 1
        assert terminal._awaiting_key is False
    finally:
        terminal.stop()


def test_end_message_uses_the_default_style_and_handles_an_empty_screen(qapp):
    terminal = make_terminal(endmessage="[done]", nocolor=False)
    try:
        terminal._process("\x1b[31m")
        terminal._out_q.put(None)

        terminal._drain_output()

        assert terminal._screen_row(3).styles[0] == ("@fg", "@bg", False, False, False, False, False)
        assert screen(terminal)[3] == "[done]"
    finally:
        terminal.stop()


def test_end_message_in_nocolor_mode(qapp):
    terminal = make_terminal(endmessage="[done]", nocolor=True)
    try:
        terminal._out_q.put(None)

        terminal._drain_output()

        assert terminal._awaiting_key is True
    finally:
        terminal.stop()


def test_keys_are_ignored_after_the_process_ended_without_waiting(term):
    term.running = False

    assert press(term, Qt.Key.Key_A, text="a") == b""
    assert term._closed is False


def test_terminating_twice_reports_once_and_clears_pending_output(posix_pty, term):
    stopped = collect(term.stopped)
    ended = collect(term.processEnded)
    term._start_process()
    term._out_q.put("unread")

    term.stop()
    term.stop()

    assert len(stopped) == 1
    assert len(ended) == 1
    assert term._out_q.empty()
    assert posix_pty.process.terminated is True
    assert term.master_fd is None
    assert term._pty_holder == {"proc": None, "fd": None}


def test_about_to_quit_terminates_and_ignores_a_deleted_widget(monkeypatch, term):
    stopped = collect(term.stopped)

    term._on_about_to_quit()
    assert len(stopped) == 1

    def deleted():
        raise RuntimeError("wrapped C/C++ object has been deleted")

    monkeypatch.setattr(term, "_terminate_process", deleted)
    term._on_about_to_quit()
    monkeypatch.undo()


def test_restart_starts_a_fresh_shell_without_reporting_a_stop(posix_pty, term):
    stopped = collect(term.stopped)
    term._start_process()
    term._process("old")
    first_generation = term._read_generation

    term.restart()

    assert stopped == []
    assert term._closed is False
    assert term.running is True
    assert screen(term)[0] == ""
    assert term._read_generation > first_generation


def test_restart_after_a_full_stop_starts_again(posix_pty, term):
    term._start_process()
    term.stop()
    assert term._closed is True

    term.restart()

    assert term._closed is False
    assert term.running is True


def test_kill_helper_terminates_posix_processes_and_closes_the_fd(monkeypatch):
    monkeypatch.setattr(pyqtterm_module, "_TERM_USES_POSIX_PTY", True)
    read_end, write_end = os.pipe()
    process = FakeProcess()
    holder = {"proc": process, "fd": read_end}

    _term_kill_pty_process(holder)
    _term_kill_pty_process(holder)

    assert process.terminated is True
    assert holder == {"proc": None, "fd": None}
    with pytest.raises(OSError):
        os.close(read_end)
    os.close(write_end)


def test_kill_helper_closes_windows_processes(monkeypatch):
    monkeypatch.setattr(pyqtterm_module, "_TERM_USES_POSIX_PTY", False)
    process = FakeProcess()

    _term_kill_pty_process({"proc": process, "fd": None})

    assert process.closed is True


def test_kill_helper_ignores_failures(monkeypatch):
    class Broken:
        def terminate(self):
            raise OSError

        def close(self):
            raise OSError

    for posix in (True, False):
        monkeypatch.setattr(pyqtterm_module, "_TERM_USES_POSIX_PTY", posix)
        _term_kill_pty_process({"proc": Broken(), "fd": 99999})


# ---------------------------------------------------------------------------
# Resizing
# ---------------------------------------------------------------------------


def started(terminal):
    terminal._term_started = True
    terminal.proc = FakeProcess()
    return terminal


def test_resize_event_schedules_a_grid_refit_only_while_running(term):
    term.resizeEvent(QResizeEvent(QSize(100, 100), QSize()))
    assert not term._resize_timer.isActive()

    started(term)
    term.resizeEvent(QResizeEvent(QSize(100, 100), QSize()))
    assert term._resize_timer.isActive()

    term._resize_timer.stop()
    term._closed = True
    term.resizeEvent(QResizeEvent(QSize(100, 100), QSize()))
    assert not term._resize_timer.isActive()


def test_apply_resize_waits_for_a_running_process(term):
    resized = []
    term._term_resize_grid = lambda cols, rows: resized.append((cols, rows))
    term.resize(40 * term.charwidth, 9 * term.charheight)
    QApplication.sendEvent(term, QResizeEvent(term.size(), QSize()))

    term._term_apply_resize()
    started(term)
    term.proc = None
    term._term_apply_resize()
    term.proc = FakeProcess()
    term._closed = True
    term._term_apply_resize()

    assert resized == []


def test_apply_resize_refits_only_when_the_size_changed(term):
    started(term)
    resized = []
    term._term_resize_grid = lambda cols, rows: resized.append((cols, rows))

    term._term_apply_resize()
    assert resized == []

    term.resize(40 * term.charwidth, 9 * term.charheight)
    QApplication.sendEvent(term, QResizeEvent(term.size(), QSize()))
    term._term_apply_resize()
    assert resized == [(40, 9)]


@pytest.fixture
def filled(qapp):
    terminal = make_terminal(cols=10, rows=4)
    terminal._process("1\r\n2\r\n3\r\n4")
    yield terminal
    terminal.stop()


def test_shrinking_pushes_the_top_rows_into_scrollback(filled):
    filled._term_resize_grid(10, 2)

    assert screen(filled) == ["3", "4"]
    assert cursor(filled)[0] == 1
    assert filled._rows[0].chars[0] == "1"


def test_shrinking_drops_blank_rows_below_the_cursor_first(qapp):
    terminal = make_terminal(cols=10, rows=4)
    try:
        terminal._process("1\r\n2")

        terminal._term_resize_grid(10, 2)

        assert screen(terminal) == ["1", "2"]
        assert len(terminal._rows) == 2
    finally:
        terminal.stop()


def test_shrinking_with_content_below_the_cursor_cuts_the_bottom(filled):
    filled._process("\x1b[1;1H")

    filled._term_resize_grid(10, 2)

    assert screen(filled) == ["1", "2"]
    assert cursor(filled)[0] == 0


def test_growing_pulls_rows_back_out_of_scrollback_then_adds_blank_ones(filled):
    filled._term_resize_grid(10, 2)

    filled._term_resize_grid(10, 6)

    assert screen(filled) == ["1", "2", "3", "4", "", ""]
    assert cursor(filled)[0] == 3


def test_narrowing_truncates_rows_and_blanks_a_split_wide_character(qapp):
    terminal = make_terminal(cols=10, rows=2)
    try:
        terminal._process("1234日")

        terminal._term_resize_grid(5, 2)

        assert terminal._screen_row(0).chars == ["1", "2", "3", "4", " "]
    finally:
        terminal.stop()


def test_widening_pads_rows_and_adds_default_tab_stops(filled):
    filled._term_resize_grid(30, 4)

    assert all(len(row.chars) == 30 for row in filled._rows)
    assert {16, 24} <= filled._tab_stops
    assert filled._cols == 30


def test_resize_resets_the_scroll_region_selection_and_clamps_the_cursor(filled):
    filled._process("\x1b[2;3r")
    filled._sel_anchor = (0, 0)
    filled._sel_head = (1, 1)
    filled._cx = 9

    filled._term_resize_grid(5, 4)

    assert (filled._scroll_top, filled._scroll_bot) == (0, 3)
    assert filled._sel_anchor is None
    assert filled._cx == 5


def test_alternate_screen_resize_keeps_the_grid_and_reshapes_the_saved_screen(qapp):
    terminal = make_terminal(cols=10, rows=4)
    try:
        terminal._process("main1\r\nmain2\x1b[?1049hALT")

        terminal._term_resize_grid(12, 6)
        assert len(terminal._rows) == 6
        assert all(len(row.chars) == 12 for row in terminal._rows)
        assert screen(terminal)[0] == "ALT"

        terminal._term_resize_grid(8, 3)
        assert len(terminal._rows) == 3
        assert terminal._cy <= 2

        terminal._process("\x1b[?1049l")
        assert [text for text in screen(terminal) if text][-1] == "main2"
    finally:
        terminal.stop()


def test_posix_resize_tells_the_pty_and_the_process_group(posix_pty, term):
    term._start_process()
    posix_pty.ioctls.clear()

    term._term_resize_grid(30, 7)

    ((fd, request, size),) = posix_pty.ioctls
    assert (fd, request) == (posix_pty.master, 0x5414)
    assert struct.unpack("HHHH", size)[:2] == (7, 30)
    assert posix_pty.killpgs == [(FakeProcess.pid, 28)]


def test_posix_resize_without_a_pty_does_not_signal(posix_pty, term):
    term._term_resize_grid(30, 7)

    assert posix_pty.ioctls == []
    assert posix_pty.killpgs == []


def test_posix_resize_ignores_a_vanished_process(posix_pty, monkeypatch, term):
    term._start_process()

    def gone(pid, sig):
        raise ProcessLookupError

    monkeypatch.setattr(os, "killpg", gone)

    term._term_resize_grid(30, 7)

    assert term._cols == 30


def test_windows_resize_sets_the_console_size(windows_pty, term):
    term._start_process()

    term._term_resize_grid(30, 7)

    assert windows_pty.process.window_sizes == [(7, 30)]


def test_windows_resize_ignores_a_missing_process(windows_pty, term):
    term._term_resize_grid(30, 7)

    assert term._cols == 30


# ---------------------------------------------------------------------------
# Keyboard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "modifiers", "text", "expected"),
    [
        (Qt.Key.Key_Return, NO_MODS, "\r", b"\r"),
        (Qt.Key.Key_Enter, NO_MODS, "\r", b"\r"),
        (Qt.Key.Key_Backspace, NO_MODS, "\x7f", b"\x7f"),
        (Qt.Key.Key_Tab, NO_MODS, "\t", b"\t"),
        (Qt.Key.Key_Tab, SHIFT, "\t", b"\x1b[Z"),
        (Qt.Key.Key_Backtab, SHIFT, "", b"\x1b[Z"),
        (Qt.Key.Key_Up, NO_MODS, "", b"\x1b[A"),
        (Qt.Key.Key_Down, NO_MODS, "", b"\x1b[B"),
        (Qt.Key.Key_Right, NO_MODS, "", b"\x1b[C"),
        (Qt.Key.Key_Left, NO_MODS, "", b"\x1b[D"),
        (Qt.Key.Key_Home, NO_MODS, "", b"\x1b[H"),
        (Qt.Key.Key_End, NO_MODS, "", b"\x1b[F"),
        (Qt.Key.Key_Up, CTRL, "", b"\x1b[1;5A"),
        (Qt.Key.Key_Left, SHIFT, "", b"\x1b[1;2D"),
        (Qt.Key.Key_Right, CTRL | SHIFT, "", b"\x1b[1;6C"),
        (Qt.Key.Key_Insert, NO_MODS, "", b"\x1b[2~"),
        (Qt.Key.Key_Delete, NO_MODS, "", b"\x1b[3~"),
        (Qt.Key.Key_PageUp, NO_MODS, "", b"\x1b[5~"),
        (Qt.Key.Key_PageDown, NO_MODS, "", b"\x1b[6~"),
        (Qt.Key.Key_Delete, CTRL, "", b"\x1b[3;5~"),
        (Qt.Key.Key_F5, NO_MODS, "", b"\x1b[15~"),
        (Qt.Key.Key_F12, NO_MODS, "", b"\x1b[24~"),
        (Qt.Key.Key_F5, SHIFT, "", b"\x1b[15;2~"),
        (Qt.Key.Key_F1, NO_MODS, "", b"\x1bOP"),
        (Qt.Key.Key_F4, NO_MODS, "", b"\x1bOS"),
        (Qt.Key.Key_F2, SHIFT, "", b"\x1b[1;2Q"),
        (Qt.Key.Key_A, NO_MODS, "a", b"a"),
        (Qt.Key.Key_A, SHIFT, "A", b"A"),
        (Qt.Key.Key_E, NO_MODS, "é", "é".encode()),
        (Qt.Key.Key_C, CTRL, "", b"\x03"),
        (Qt.Key.Key_D, CTRL, "", b"\x04"),
        (Qt.Key.Key_Z, CTRL, "", b"\x1a"),
        (Qt.Key.Key_Space, CTRL, " ", b"\x00"),
        (Qt.Key.Key_At, CTRL, "", b"\x00"),
        (Qt.Key.Key_2, CTRL, "", b"\x00"),
        (Qt.Key.Key_BracketLeft, CTRL, "", b"\x1b"),
        (Qt.Key.Key_3, CTRL, "", b"\x1b"),
        (Qt.Key.Key_Backslash, CTRL, "", b"\x1c"),
        (Qt.Key.Key_4, CTRL, "", b"\x1c"),
        (Qt.Key.Key_BracketRight, CTRL, "", b"\x1d"),
        (Qt.Key.Key_5, CTRL, "", b"\x1d"),
        (Qt.Key.Key_AsciiCircum, CTRL, "", b"\x1e"),
        (Qt.Key.Key_6, CTRL, "", b"\x1e"),
        (Qt.Key.Key_Underscore, CTRL, "", b"\x1f"),
        (Qt.Key.Key_Slash, CTRL, "", b"\x1f"),
        (Qt.Key.Key_7, CTRL, "", b"\x1f"),
        (Qt.Key.Key_Escape, NO_MODS, "\x1b", b"\x1b"),
    ],
)
def test_keys_are_translated_to_what_a_terminal_sends(term, key, modifiers, text, expected):
    assert press(term, key, modifiers, text) == expected


def test_arrow_keys_use_application_mode_when_requested(term):
    term._process("\x1b[?1h")

    assert press(term, Qt.Key.Key_Up) == b"\x1bOA"
    assert press(term, Qt.Key.Key_Left) == b"\x1bOD"
    assert press(term, Qt.Key.Key_Up, CTRL) == b"\x1b[1;5A"


def test_alt_sends_escape_before_the_key(term):
    assert press(term, Qt.Key.Key_X, ALT, "x") == b"\x1bx"
    assert press(term, Qt.Key.Key_Left, ALT) == b"\x1bb"
    assert press(term, Qt.Key.Key_Right, ALT) == b"\x1bf"
    assert press(term, Qt.Key.Key_Up, ALT) == b"\x1b\x1b[A"
    assert press(term, Qt.Key.Key_Down, ALT) == b"\x1b\x1b[B"
    assert press(term, Qt.Key.Key_F5, ALT) == b""

    term._process("\x1b[?1h")
    assert press(term, Qt.Key.Key_Up, ALT) == b"\x1b\x1bOA"


def test_modify_other_keys_level_two_reports_modified_named_keys(term):
    term._process("\x1b[>4;2m")

    assert press(term, Qt.Key.Key_Return, CTRL) == b"\x1b[27;5;13~"
    assert press(term, Qt.Key.Key_Backspace, SHIFT) == b"\x1b[27;2;127~"
    assert press(term, Qt.Key.Key_Escape, CTRL) == b"\x1b[27;5;27~"
    assert press(term, Qt.Key.Key_Tab, CTRL) == b"\x1b[27;5;9~"
    assert press(term, Qt.Key.Key_Tab, SHIFT, "\t") == b"\x1b[Z"
    assert press(term, Qt.Key.Key_Return) == b"\r"


def test_modify_other_keys_reports_modified_printable_keys(term):
    term._process("\x1b[>4;2m")
    assert press(term, Qt.Key.Key_A, CTRL) == b"\x1b[27;5;97~"
    assert press(term, Qt.Key.Key_A, SHIFT, "A") == b"\x1b[27;2;65~"

    term._process("\x1b[>4;1m")
    assert press(term, Qt.Key.Key_A, CTRL) == b"\x01"
    assert press(term, Qt.Key.Key_Period, CTRL, "") == b"\x1b[27;5;46~"


def test_modifier_only_keys_send_nothing(term):
    for key in (Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
        assert press(term, key) == b""


def test_typing_clears_the_selection_but_modifiers_do_not(term):
    term._sel_anchor = (0, 0)
    term._sel_head = (0, 3)

    press(term, Qt.Key.Key_Shift)
    assert term._sel_anchor is not None

    press(term, Qt.Key.Key_A, text="a")
    assert term._sel_anchor is None


def test_navigation_keys_clear_the_selection(term):
    term._sel_anchor = (0, 0)
    term._sel_head = (0, 3)

    press(term, Qt.Key.Key_Up)

    assert term._sel_anchor is None


def test_alt_keys_clear_the_selection(term):
    term._sel_anchor = (0, 0)
    term._sel_head = (0, 3)

    press(term, Qt.Key.Key_X, ALT, "x")

    assert term._sel_anchor is None


def test_terminal_claims_shortcuts_and_keeps_tab_for_the_shell(term):
    override = QKeyEvent(QEvent.Type.ShortcutOverride, Qt.Key.Key_C, CTRL, "")
    override.ignore()

    assert term.event(override) is True
    assert override.isAccepted() is True
    assert term.focusNextPrevChild(True) is False
    assert isinstance(term.event(QEvent(QEvent.Type.User)), bool)


def test_input_method_text_is_sent_to_the_shell(term):
    term._sel_anchor = (0, 0)
    term._sel_head = (0, 2)
    event = QInputMethodEvent()
    event.setCommitString("é")

    term.inputMethodEvent(event)

    assert term.written == ["é".encode()]
    assert term._sel_anchor is None
    assert event.isAccepted()


def test_input_method_without_commit_or_process_sends_nothing(term):
    term.inputMethodEvent(QInputMethodEvent())
    term.running = False
    event = QInputMethodEvent()
    event.setCommitString("x")

    term.inputMethodEvent(event)

    assert term.written == []


def test_input_method_cursor_rectangle_follows_the_cursor(term):
    term._process("\x1b[3;5H")

    rectangle = term.inputMethodQuery(Qt.InputMethodQuery.ImCursorRectangle)

    assert rectangle == QRect(
        4 * term.charwidth, 2 * term.charheight, term.charwidth, term.charheight
    )
    assert not isinstance(
        term.inputMethodQuery(Qt.InputMethodQuery.ImFont), QRect
    )


def test_focus_events_are_reported_only_when_requested(term):
    term.focusInEvent(QFocusEvent(QEvent.Type.FocusIn))
    assert term._cursor_has_focus is True
    assert term.written == []

    term._process("\x1b[?1004h")
    term.focusOutEvent(QFocusEvent(QEvent.Type.FocusOut))
    assert term._cursor_has_focus is False
    term.focusInEvent(QFocusEvent(QEvent.Type.FocusIn))

    assert term.written == [b"\x1b[O", b"\x1b[I"]


def test_focus_events_are_not_reported_after_the_process_ended(term):
    term._process("\x1b[?1004h")
    term.running = False

    term.focusInEvent(QFocusEvent(QEvent.Type.FocusIn))
    term.focusOutEvent(QFocusEvent(QEvent.Type.FocusOut))

    assert term.written == []


# ---------------------------------------------------------------------------
# Selection and clipboard
# ---------------------------------------------------------------------------


def test_selection_bounds_are_ordered_and_empty_selections_are_none(term):
    assert term._selection_bounds() is None

    term._sel_anchor = (2, 4)
    term._sel_head = (1, 1)
    assert term._selection_bounds() == ((1, 1), (2, 4))

    term._sel_head = (2, 4)
    assert term._selection_bounds() is None


def test_selection_text_trims_trailing_spaces_and_joins_wrapped_rows(small):
    small._process("abcdefgh\r\nxy")
    small._sel_anchor = (0, 0)
    small._sel_head = (2, 5)

    assert small._selection_text() == "abcdefgh\nxy"


def test_selection_text_of_part_of_one_line(term):
    term._process("hello world")
    term._sel_anchor = (0, 6)
    term._sel_head = (0, 11)

    assert term._selection_text() == "world"
    term._clear_selection()
    assert term._selection_text() == ""


def test_select_all_selects_the_whole_buffer(term):
    term._process("hi")

    term._select_all()

    assert term._sel_anchor == (0, 0)
    assert term._sel_head == (len(term._rows) - 1, term._cols)


def test_copy_selection_puts_the_text_on_the_clipboard(term):
    QApplication.clipboard().setText("before")
    term._process("copy me")

    term._copy_selection()
    assert QApplication.clipboard().text() == "before"

    term._sel_anchor = (0, 0)
    term._sel_head = (0, 7)
    term._copy_selection()
    assert QApplication.clipboard().text() == "copy me"


def test_paste_sends_clipboard_text_with_carriage_returns(term):
    QApplication.clipboard().setText("one\r\ntwo\nthree")
    term._sel_anchor = (0, 0)
    term._sel_head = (0, 1)

    term._paste_clipboard()

    assert term.written == [b"one\rtwo\rthree"]
    assert term._sel_anchor is None


def test_paste_is_wrapped_when_bracketed_paste_is_on(term):
    term._process("\x1b[?2004h")
    QApplication.clipboard().setText("text")

    term._paste_clipboard()

    assert term.written == [b"\x1b[200~text\x1b[201~"]


def test_paste_does_nothing_without_text_or_a_running_process(term):
    QApplication.clipboard().setText("")
    term._paste_clipboard()
    QApplication.clipboard().setText("text")
    term.running = False
    term._paste_clipboard()

    assert term.written == []


def test_copy_paste_and_select_all_shortcuts(term):
    term._process("hello")
    assert press(term, Qt.Key.Key_A, CTRL | SHIFT) == b""
    assert term._sel_anchor == (0, 0)

    term._sel_anchor = (0, 0)
    term._sel_head = (0, 5)
    assert press(term, Qt.Key.Key_C, CTRL | SHIFT) == b""
    assert QApplication.clipboard().text() == "hello"

    assert press(term, Qt.Key.Key_V, CTRL | SHIFT) == b"hello"


class FakeMenu:
    last = None

    def __init__(self, parent=None):
        self.actions = []
        self.executed_at = None
        FakeMenu.last = self

    def addAction(self, text, callback):
        action = SimpleNamespace(text=text, callback=callback, enabled=True)
        action.setEnabled = lambda enabled: setattr(action, "enabled", enabled)
        self.actions.append(action)
        return action

    def addSeparator(self):
        self.actions.append(None)

    def exec(self, position):
        self.executed_at = position


def test_right_click_opens_a_menu_with_copy_paste_and_select_all(monkeypatch, term):
    monkeypatch.setattr(pyqtterm_module, "QMenu", FakeMenu)

    click(term, 3, 3, Qt.MouseButton.RightButton)
    release(term, 3, 3, Qt.MouseButton.RightButton)

    menu = FakeMenu.last
    assert [a.text for a in menu.actions if a] == ["Copy", "Paste", "Select All"]
    assert menu.actions[0].enabled is False
    assert menu.executed_at == QPoint(3, 3)

    term._sel_anchor = (0, 0)
    term._sel_head = (0, 2)
    release(term, 3, 3, Qt.MouseButton.RightButton)
    assert FakeMenu.last.actions[0].enabled is True
    FakeMenu.last.actions[-1].callback()
    assert term._sel_head == (len(term._rows) - 1, term._cols)


# ---------------------------------------------------------------------------
# Mouse selection
# ---------------------------------------------------------------------------


def test_dragging_selects_text(term):
    term._process("hello world")
    cw = term.charwidth

    click(term, 2 * cw + 1, 1)
    drag(term, 5 * cw + 1, 1)
    release(term, 5 * cw + 1, 1)

    assert term._selection_text() == "llo"
    assert term._selecting is False


def test_dragging_above_or_below_the_view_scrolls_while_selecting(small):
    small._process("\r\n".join(str(n) for n in range(30)))
    small._after_output()
    bar = small.verticalScrollBar()
    bar.setValue(10)
    click(small, 1, small.charheight)

    drag(small, 1, -5)
    assert bar.value() == 9

    drag(small, 1, small.charheight * 3 + 5)
    assert bar.value() == 10


def test_dragging_without_a_press_selects_nothing(term):
    term._process("hello")

    drag(term, 20, 1)

    assert term._selection_bounds() is None


def test_moving_the_mouse_with_a_button_other_than_left_does_not_select(term):
    click(term, 1, 1)

    drag(term, 20, 1, Qt.MouseButton.MiddleButton)

    assert term._sel_head == term._sel_anchor


def test_double_click_selects_a_word_a_run_of_spaces_or_punctuation(term):
    term._process("foo_bar  ++ baz")
    cw = term.charwidth

    term.mouseDoubleClickEvent(
        mouse_event(QEvent.Type.MouseButtonDblClick, 4 * cw + 1, 1)
    )
    assert term._selection_text() == "foo_bar"

    term.mouseDoubleClickEvent(
        mouse_event(QEvent.Type.MouseButtonDblClick, 7 * cw + 1, 1)
    )
    assert term._sel_anchor == (0, 7)
    assert term._sel_head == (0, 9)

    term.mouseDoubleClickEvent(
        mouse_event(QEvent.Type.MouseButtonDblClick, 10 * cw + 1, 1)
    )
    assert term._selection_text() == "++"


def test_triple_click_selects_the_line_but_only_quickly(term):
    term._process("a whole line")
    term.mouseDoubleClickEvent(mouse_event(QEvent.Type.MouseButtonDblClick, 1, 1))

    click(term, 1, 1)
    assert term._selection_text() == "a whole line"

    term._last_double_click_time = time.monotonic() - 60
    click(term, 1, 1)
    assert term._selecting is True
    assert term._selection_bounds() is None


def test_double_click_with_a_wide_character_in_the_word(term):
    term._process("日本 x")

    term.mouseDoubleClickEvent(mouse_event(QEvent.Type.MouseButtonDblClick, 1, 1))

    assert term._sel_anchor == (0, 0)


def test_middle_click_pastes_and_other_buttons_are_ignored(term):
    QApplication.clipboard().setText("pasted")

    click(term, 1, 1, Qt.MouseButton.MiddleButton)
    click(term, 1, 1, Qt.MouseButton.BackButton)
    release(term, 1, 1, Qt.MouseButton.BackButton)

    assert term.written == [b"pasted"]


# ---------------------------------------------------------------------------
# Mouse reporting
# ---------------------------------------------------------------------------


def test_mouse_clicks_are_reported_in_sgr_encoding(term):
    term._process("\x1b[?1000h\x1b[?1006h")
    x, y = cell_xy(term, 2, 1)

    click(term, x, y)
    release(term, x, y)
    click(term, x, y, Qt.MouseButton.RightButton)

    assert term.written == [
        b"\x1b[<0;3;2M",
        b"\x1b[<0;3;2m",
        b"\x1b[<2;3;2M",
    ]
    assert term._selection_bounds() is None


def test_mouse_clicks_are_reported_in_legacy_encoding(term):
    term._process("\x1b[?1000h")
    x, y = cell_xy(term, 2, 1)

    click(term, x, y)
    release(term, x, y)
    click(term, x, y, Qt.MouseButton.MiddleButton)

    assert term.written == [
        bytes([27, ord("["), ord("M"), 32, 35, 34]),
        bytes([27, ord("["), ord("M"), 35, 35, 34]),
        bytes([27, ord("["), ord("M"), 33, 35, 34]),
    ]


def test_mouse_reports_include_modifier_bits(term):
    term._process("\x1b[?1000h\x1b[?1006h")
    x, y = cell_xy(term, 0, 0)

    click(term, x, y, modifiers=CTRL)
    click(term, x, y, modifiers=ALT)

    assert term.written == [b"\x1b[<16;1;1M", b"\x1b[<8;1;1M"]


def test_shift_click_bypasses_mouse_reporting_for_selection(term):
    term._process("\x1b[?1000h\x1b[?1006h")

    click(term, 1, 1, modifiers=SHIFT)

    assert term.written == []
    assert term._selecting is True


def test_mouse_positions_are_clamped_to_the_grid(term):
    term._process("\x1b[?1000h\x1b[?1006h")

    click(term, 9999, 9999)

    assert term.written == [b"\x1b[<0;20;5M"]


def test_dragging_is_reported_only_in_drag_or_motion_modes(term):
    term._process("\x1b[?1000h\x1b[?1006h")
    drag(term, *cell_xy(term, 1, 1))
    assert term.written == []
    assert term._sel_head is None

    term._process("\x1b[?1002h")
    drag(term, *cell_xy(term, 1, 1))
    drag(term, *cell_xy(term, 1, 1))
    drag(term, *cell_xy(term, 2, 1))

    assert term.written == [b"\x1b[<32;2;2M", b"\x1b[<32;3;2M"]


def test_hovering_is_reported_only_in_any_motion_mode(term):
    term._process("\x1b[?1002h\x1b[?1006h")
    term.mouseMoveEvent(
        mouse_event(
            QEvent.Type.MouseMove, 1, 1, Qt.MouseButton.NoButton, Qt.MouseButton.NoButton
        )
    )
    assert term.written == []

    term._process("\x1b[?1003h")
    term.mouseMoveEvent(
        mouse_event(
            QEvent.Type.MouseMove, 1, 1, Qt.MouseButton.NoButton, Qt.MouseButton.NoButton
        )
    )

    assert term.written == [b"\x1b[<35;1;1M"]


def test_mouse_reports_stop_when_the_process_has_ended(term):
    term._process("\x1b[?1000h\x1b[?1006h")
    term.running = False

    click(term, 1, 1)

    assert term.written == []


# ---------------------------------------------------------------------------
# Wheel
# ---------------------------------------------------------------------------


def test_wheel_is_reported_when_the_program_wants_mouse_events(term):
    term._process("\x1b[?1000h\x1b[?1006h")

    event = wheel(term, 240)
    wheel(term, -120)

    assert term.written == [b"\x1b[<64;1;1M", b"\x1b[<64;1;1M", b"\x1b[<65;1;1M"]
    assert event.isAccepted()


def test_shift_wheel_scrolls_the_view_even_with_mouse_reporting(small):
    small._process("\r\n".join(str(n) for n in range(30)))
    small._after_output()
    small._process("\x1b[?1000h\x1b[?1006h")
    bar = small.verticalScrollBar()
    top = bar.value()

    wheel(small, 120, SHIFT)

    assert small.written == []
    assert bar.value() < top


def test_wheel_in_the_alternate_screen_sends_arrow_keys(term):
    term._process("\x1b[?1049h")

    wheel(term, 120)
    wheel(term, -120)
    assert term.written == [b"\x1b[A"] * 3 + [b"\x1b[B"] * 3

    term.written.clear()
    term._process("\x1b[?1h")
    wheel(term, 120)
    wheel(term, -120)
    assert term.written == [b"\x1bOA"] * 3 + [b"\x1bOB"] * 3


def test_wheel_in_the_alternate_screen_scrolls_when_alternate_scroll_is_off(term):
    term._process("\x1b[?1049h\x1b[?1007l")

    wheel(term, 120)

    assert term.written == []


def test_wheel_scrolls_the_scrollback_by_lines(small):
    small._process("\r\n".join(str(n) for n in range(30)))
    small._after_output()
    bar = small.verticalScrollBar()
    bottom = bar.value()

    wheel(small, 120)
    assert bar.value() == bottom - 3

    wheel(small, -120)
    assert bar.value() == bottom

    wheel(small, 10)
    assert bar.value() == bottom - 1

    wheel(small, -10)
    assert bar.value() == bottom


def test_wheel_without_movement_is_ignored(small):
    small._process("\r\n".join(str(n) for n in range(30)))
    small._after_output()
    small._process("\x1b[?1000h\x1b[?1006h")
    bar = small.verticalScrollBar()
    value = bar.value()

    wheel(small, 0)

    assert small.written == []
    assert bar.value() == value


# ---------------------------------------------------------------------------
# Real PTY
# ---------------------------------------------------------------------------


def wait_for(condition, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QTest.qWait(20)
        if condition():
            return True
    return False


@pytest.mark.skipif(os.name != "posix", reason="needs a POSIX PTY")
def test_real_shell_output_input_and_exit(qapp):
    terminal = Terminal(command=["sh", "-c", "printf 'ready\\n'; read line; echo got:$line"])
    terminal._cols, terminal._nrows = 40, 5
    fit_to_grid(terminal)
    stopped = collect(terminal.stopped)
    try:
        terminal._start_process()
        assert wait_for(lambda: "ready" in "".join(screen(terminal)))

        terminal._write(b"abc\n")
        assert wait_for(lambda: "got:abc" in "".join(screen(terminal)))
        assert wait_for(lambda: len(stopped) == 1)
        assert terminal.running is False
    finally:
        terminal.stop()


@pytest.mark.skipif(os.name != "posix", reason="needs a POSIX PTY")
def test_real_shell_gets_a_controlling_terminal_of_the_right_size_in_its_cwd(
    qapp, tmp_path
):
    terminal = Terminal(
        command=["sh", "-c", "tty >/dev/null && stty size && pwd"], cwd=str(tmp_path)
    )
    terminal._cols, terminal._nrows = 33, 6
    fit_to_grid(terminal)
    try:
        terminal._start_process()

        assert wait_for(lambda: str(tmp_path.resolve()) in "".join(screen(terminal)))
        lines = [line for line in screen(terminal) if line]
        assert lines[0] == "6 33"
    finally:
        terminal.stop()


@pytest.mark.skipif(os.name != "posix", reason="needs a POSIX PTY")
def test_real_shell_resize_reaches_the_program(qapp):
    terminal = Terminal(
        command=["sh", "-c", "trap 'stty size' WINCH; stty size; while :; do sleep 0.05; done"]
    )
    terminal._cols, terminal._nrows = 40, 5
    fit_to_grid(terminal)
    try:
        terminal._start_process()
        terminal._term_started = True
        assert wait_for(lambda: "5 40" in "".join(screen(terminal)))

        terminal._term_resize_grid(50, 7)

        assert wait_for(lambda: "7 50" in "".join(screen(terminal)))
    finally:
        terminal.stop()

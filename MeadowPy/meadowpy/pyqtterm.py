"""A VT100/xterm terminal emulator widget for PyQt6: runs a real
subprocess over a PTY (see Terminal._start_process()), parses its output
as a stream of ANSI/VT escape sequences (see Terminal._process(), the
emulator's core), keeps the result in a grid of styled cells (scrollback
plus the live screen), and paints that grid itself. Input events
(keyPressEvent()/mouse handlers) are translated back into the escape
sequences/bytes the subprocess expects."""

import base64
import codecs
import os
import queue
import re
import subprocess
import sys
import threading
import time
import traceback
import unicodedata

from PyQt6.QtCore import QEvent, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPalette
from PyQt6.QtWidgets import QAbstractScrollArea, QApplication, QFrame, QMenu

_TERM_RESIZE_DEBOUNCE_MS = 300
_TERM_USES_POSIX_PTY = os.name == "posix"
if _TERM_USES_POSIX_PTY:
    import fcntl
    import pty
    import select
    import signal
    import struct
    import termios

    _TERM_DEFAULT_FONT_FAMILY = "monospace"
else:
    from winpty import PtyProcess

    _TERM_DEFAULT_FONT_FAMILY = "Courier"
_TERM_FRAME_MS = 16  # redraw scheduling for _drain_output() while there is backlog
_TERM_FRAME_BUDGET = 0.008  # max seconds of PTY output to process per redraw frame
_PTY_MAX_PENDING_ESC = 600000  # safety cap on a stalled/malformed escape sequence
_TERM_MAX_SCROLLBACK_LINES = 10000
_TERM_WHEEL_SCROLL_LINES = 3

_TERM_ANSI_16_HEX = (
    "#000000",
    "#cd0000",
    "#00cd00",
    "#cdcd00",
    "#0000ee",
    "#cd00cd",
    "#00cdcd",
    "#e5e5e5",
    "#7f7f7f",
    "#ff0000",
    "#00ff00",
    "#ffff00",
    "#5c5cff",
    "#ff00ff",
    "#00ffff",
    "#ffffff",
)
# Run by the child (as `python -I -S -c`, argv = the command to exec) after
# subprocess.Popen(start_new_session=True) has made it a session leader:
# take the PTY on stdin as the controlling terminal, then become the
# command. Doing this here instead of in a preexec_fn keeps Python code
# from running between fork() and exec() in the multi-threaded GUI process.
_TERM_EXEC_WITH_CONTROLLING_TTY = (
    "import fcntl, os, sys, termios\n"
    "fcntl.ioctl(0, termios.TIOCSCTTY, 0)\n"
    "os.execvp(sys.argv[1], sys.argv[1:])"
)
_TERM_ANSI_CUBE_LEVELS = (0, 95, 135, 175, 215, 255)

# A cell style is (fg, bg, bold, italic, underline, strike, blink), where
# fg/bg are '#rrggbb' or "@fg"/"@bg" standing for the terminal's current
# default colors.
_TERM_DEFAULT_STYLE = ("@fg", "@bg", False, False, False, False, False)

_TERM_CSI_RE = re.compile(r"\x1b\[([0-9;?<=>]*[ -/]*)([@-~])")
_TERM_CSI_PENDING_RE = re.compile(r"\x1b\[[0-9;?<=>]*[ -/]*")
_TERM_PRINTABLE_RUN_RE = re.compile(r"[^\x00-\x1f\x7f]+")
_TERM_OSC_END_RE = re.compile(r"\x07|\x1b\\")


def _ansi_256_hex(n):
    """Convert an ANSI 256-color palette index n to a '#rrggbb' hex
    string (the first 16 are the named ANSI colors, the next 216 form a
    6x6x6 color cube, and the last 24 are a grayscale ramp)."""
    if n < 16:
        return _TERM_ANSI_16_HEX[n]
    if n < 232:
        n -= 16
        return f"#{_TERM_ANSI_CUBE_LEVELS[n // 36]:02x}{_TERM_ANSI_CUBE_LEVELS[(n % 36) // 6]:02x}{_TERM_ANSI_CUBE_LEVELS[n % 6]:02x}"
    v = 8 + (n - 232) * 10
    return f"#{v:02x}{v:02x}{v:02x}"


def _sgr_new_state():
    """A fresh SGR (text style/color) state dict, as tracked per
    Terminal instance in self._sgr_state and mutated by _sgr_apply()."""
    return {
        "fg": None,
        "bg": None,
        "bold": False,
        "italic": False,
        "underline": False,
        "reverse": False,
        "blink": False,
        "strike": False,
        "conceal": False,
    }


def _sgr_apply(state, params):
    """Apply one SGR ('\\x1b[...m') escape's params to state in place
    (state as returned by _sgr_new_state()), handling the standard
    16/8-bright colors, 256-color and truecolor (38/48;5/2;...) forms,
    and the usual bold/italic/underline/etc attribute toggles."""
    if not params:
        params = [0]
    i = 0
    while i < len(params):
        c = params[i]
        if c == 0:
            state.update(
                fg=None,
                bg=None,
                bold=False,
                italic=False,
                underline=False,
                reverse=False,
                blink=False,
                strike=False,
                conceal=False,
            )
        elif c == 1:
            state["bold"] = True
        elif c == 3:
            state["italic"] = True
        elif c == 4:
            state["underline"] = True
        elif c == 5 or c == 6:
            state["blink"] = True
        elif c == 7:
            state["reverse"] = True
        elif c == 8:
            state["conceal"] = True
        elif c == 9:
            state["strike"] = True
        elif c == 22:
            state["bold"] = False
        elif c == 23:
            state["italic"] = False
        elif c == 24:
            state["underline"] = False
        elif c == 25:
            state["blink"] = False
        elif c == 27:
            state["reverse"] = False
        elif c == 28:
            state["conceal"] = False
        elif c == 29:
            state["strike"] = False
        elif 30 <= c <= 37:
            state["fg"] = c - 30
        elif c == 38:
            if i + 2 < len(params) and params[i + 1] == 5:
                state["fg"] = params[i + 2]
                i += 2
            elif i + 4 < len(params) and params[i + 1] == 2:
                state["fg"] = (params[i + 2], params[i + 3], params[i + 4])
                i += 4
        elif c == 39:
            state["fg"] = None
        elif 40 <= c <= 47:
            state["bg"] = c - 40
        elif c == 48:
            if i + 2 < len(params) and params[i + 1] == 5:
                state["bg"] = params[i + 2]
                i += 2
            elif i + 4 < len(params) and params[i + 1] == 2:
                state["bg"] = (params[i + 2], params[i + 3], params[i + 4])
                i += 4
        elif c == 49:
            state["bg"] = None
        elif 90 <= c <= 97:
            state["fg"] = c - 90 + 8
        elif 100 <= c <= 107:
            state["bg"] = c - 100 + 8
        i += 1


def _sgr_colour_hex(c):
    """Convert an SGR color value (an ANSI palette index, or an (r, g,
    b) truecolor tuple) to a '#rrggbb' hex string."""
    if c is None:
        return None
    if isinstance(c, tuple):
        return f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"
    return _ansi_256_hex(c)


def _term_char_width(ch):
    """A character's terminal column width: 0 for a combining mark
    (stacked onto the previous cell, not given one of its own), 2 for an
    East Asian wide/fullwidth character, 1 otherwise."""
    if unicodedata.category(ch) in ("Mn", "Me", "Cf"):
        return 0
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 2
    return 1


def _term_sgr_resolve(state, default_fg, default_bg):
    """Resolve an SGR state to the actual (fg, bg) hex colors to draw
    with, applying bold-brightens-color, reverse video, and conceal."""
    fg = default_fg if state["fg"] is None else _sgr_colour_hex(state["fg"])
    bg = default_bg if state["bg"] is None else _sgr_colour_hex(state["bg"])
    if state["bold"] and isinstance(state["fg"], int) and state["fg"] < 8:
        fg = _ansi_256_hex(state["fg"] + 8)
    if state["reverse"]:
        oldfg = fg
        fg = bg if bg is not None else default_bg
        bg = oldfg if oldfg is not None else default_fg
    if state["conceal"]:
        fg = bg
    return fg, bg


def _term_cell_style(state):
    """The cell style tuple (see _TERM_DEFAULT_STYLE) for an SGR state."""
    fg, bg = _term_sgr_resolve(state, "@fg", "@bg")
    return (
        fg,
        bg,
        state["bold"],
        state["italic"],
        state["underline"],
        state["strike"],
        state["blink"],
    )


def _term_erase_style(style):
    """The style erased/blank cells get when style is current: only its
    background carries over (e.g. after '\\x1b[42m' + erase, the erased
    cells should show green)."""
    if style[1] == "@bg":
        return _TERM_DEFAULT_STYLE
    return ("@fg", style[1], False, False, False, False, False)


class _TerminalRow:
    """One row of the grid: chars[i] is the text of cell i ("" for the
    right half of a wide character, possibly several code points for a
    base character with combining marks), styles[i] its style tuple.
    wrapped is whether the row's text continues on the next row because
    of autowrap (so copying joins them without a newline)."""

    __slots__ = ("chars", "styles", "wrapped")

    def __init__(self, cols, style=_TERM_DEFAULT_STYLE):
        self.chars = [" "] * cols
        self.styles = [style] * cols
        self.wrapped = False


def _term_kill_pty_process(holder):
    """Terminate the subprocess and close the PTY recorded in holder
    (see Terminal._pty_holder), if any are still open; safe to call
    more than once."""
    proc = holder.get("proc")
    fd = holder.get("fd")
    holder["proc"] = None
    holder["fd"] = None
    if proc is not None:
        try:
            if _TERM_USES_POSIX_PTY:
                proc.terminate()
                threading.Thread(target=proc.wait, daemon=True).start()
            else:
                proc.close()
        except Exception:
            pass
    if fd is not None:
        try:
            os.close(fd)
        except Exception:
            pass


class Terminal(QAbstractScrollArea):
    """A VT100/xterm terminal emulator widget: runs a real subprocess
    over a PTY, interprets its output as ANSI/VT escape sequences into a
    grid of styled cells, and paints that grid. Input events are
    translated back into the escape sequences/bytes the subprocess
    expects.

    Signals: processEnded (the subprocess exited), stopped (the process
    and its resources were fully torn down), outputProcessed (a batch of
    output was rendered).
    """

    processEnded = pyqtSignal()
    stopped = pyqtSignal()
    outputProcessed = pyqtSignal()
    _output_wake = pyqtSignal()

    _term_csi_keys = {
        Qt.Key.Key_Up: "A",
        Qt.Key.Key_Down: "B",
        Qt.Key.Key_Right: "C",
        Qt.Key.Key_Left: "D",
        Qt.Key.Key_Home: "H",
        Qt.Key.Key_End: "F",
    }
    _term_tilde_keys = {
        Qt.Key.Key_Insert: "2",
        Qt.Key.Key_Delete: "3",
        Qt.Key.Key_PageUp: "5",
        Qt.Key.Key_PageDown: "6",
        Qt.Key.Key_F5: "15",
        Qt.Key.Key_F6: "17",
        Qt.Key.Key_F7: "18",
        Qt.Key.Key_F8: "19",
        Qt.Key.Key_F9: "20",
        Qt.Key.Key_F10: "21",
        Qt.Key.Key_F11: "23",
        Qt.Key.Key_F12: "24",
    }
    _term_ss3_keys = {
        Qt.Key.Key_F1: "P",
        Qt.Key.Key_F2: "Q",
        Qt.Key.Key_F3: "R",
        Qt.Key.Key_F4: "S",
    }
    # _term_csi_keys/_term_tilde_keys/_term_ss3_keys map Qt keys to the
    # escape sequences a terminal application expects for that key (used
    # by _send_key()).
    _term_modifier_only_keys = frozenset(
        (
            Qt.Key.Key_Shift,
            Qt.Key.Key_Control,
            Qt.Key.Key_Alt,
            Qt.Key.Key_AltGr,
            Qt.Key.Key_Meta,
            Qt.Key.Key_Super_L,
            Qt.Key.Key_Super_R,
            Qt.Key.Key_Hyper_L,
            Qt.Key.Key_Hyper_R,
            Qt.Key.Key_CapsLock,
            Qt.Key.Key_NumLock,
            Qt.Key.Key_ScrollLock,
            Qt.Key.Key_Mode_switch,
        )
    )
    _term_selection_clearing_keys = frozenset(
        (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Backspace,
            Qt.Key.Key_Delete,
            Qt.Key.Key_Up,
            Qt.Key.Key_Down,
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
            Qt.Key.Key_Tab,
            Qt.Key.Key_Backtab,
            Qt.Key.Key_Home,
            Qt.Key.Key_End,
            Qt.Key.Key_PageUp,
            Qt.Key.Key_PageDown,
            Qt.Key.Key_Insert,
        )
    )

    def __init__(
        self,
        parent=None,
        command=None,
        endmessage=None,
        nocolor=False,
        font=_TERM_DEFAULT_FONT_FAMILY,
        fontsize=12,
        foreground=None,
        background=None,
        cwd=None,
    ):
        """command: the argv list to run (None for the user's default
        shell). cwd: the directory the subprocess starts in (None for
        the application's own; see setWorkingDirectory()). endmessage: text to show (and wait for a keypress on)
        once the process exits; if falsy, the terminal just tears itself
        down instead. nocolor: disable ANSI colors (and the custom
        cursor color escape). font: the font family name (a string) and
        fontsize: its size in points (a number), always used explicitly
        for the text, the bold/italic variants and the cell size.
        foreground/background: the default text/background colors; when
        omitted they come from the widget's palette and follow it."""
        super().__init__(parent)
        self.endmessage = endmessage
        self.nocolor = nocolor
        self._term_command = command
        self._term_cwd = cwd
        self._term_font_name = font
        self._term_font_size = fontsize
        self._term_font_variants = {}
        self._term_custom_default_colors = (foreground, background)
        self.running = True
        self._closed = False
        self._awaiting_key = False
        self._term_started = False
        self._read_generation = 0
        self._out_q = queue.Queue(maxsize=64)
        self._pty_holder = {"proc": None, "fd": None}
        self.proc = None
        self.master_fd = None
        self._cols = 1
        self._nrows = 1
        self._viewport_follow_syncing = False
        self._cursor_blink_visible = True
        self._cursor_has_focus = False
        self._blink_visible = True
        self._blink_painted = False
        self._last_double_click_time = None
        self._selecting = False
        self._color_cache = {}
        self._reverse_screen = False
        self._cursor_color_custom = False
        self._paint_fg = QColor("#000000")
        self._paint_bg = QColor("#ffffff")
        self._default_fg = QColor("#000000")
        self._default_bg = QColor("#ffffff")

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.viewport().setCursor(Qt.CursorShape.IBeamCursor)
        self.viewport().setMouseTracking(True)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

        self._cursor_blink_timer = QTimer(self)
        self._cursor_blink_timer.setSingleShot(True)
        self._cursor_blink_timer.timeout.connect(self._cursor_blink_tick)
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(500)
        self._blink_timer.timeout.connect(self._blink_tick)
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(_TERM_RESIZE_DEBOUNCE_MS)
        self._resize_timer.timeout.connect(self._term_apply_resize)
        self._output_wake.connect(self._drain_output)
        self.verticalScrollBar().valueChanged.connect(self._on_scrollbar_value)
        self.destroyed.connect(lambda *_, h=self._pty_holder: _term_kill_pty_process(h))
        QApplication.instance().aboutToQuit.connect(self._on_about_to_quit)

        self._term_measure_char_size()
        self._term_refresh_default_colors()
        self._reset_emulator_state()

    # ------------------------------------------------------------------
    # Emulator state
    # ------------------------------------------------------------------

    def _reset_emulator_state(self):
        """Reset every piece of emulator state (screen, cursor, tabs,
        SGR, modes, alternate screen) to its power-on default, keeping
        the current grid size."""
        self._cy = 0
        self._cx = 0
        self._saved_cursor = None
        self._saved_sgr = None
        self._pending_esc = ""
        self._osc_skipping = False
        self._last_char = ""
        self._modify_other_keys = 0
        self._sgr_state = _sgr_new_state()
        self._cell_style = _TERM_DEFAULT_STYLE
        self._erase_style = _TERM_DEFAULT_STYLE
        self._bracketed_paste = False
        self._focus_reporting = False
        self._autowrap = True
        self._app_cursor = False
        self._alternate_scroll = True
        self._mouse_mode = 0
        self._mouse_sgr = False
        self._mouse_last_pos = None
        self._alt_saved = None
        self._alt_mode = False
        self._reverse_screen = False
        self._origin_mode = False
        self._scroll_top = 0
        self._scroll_bot = self._nrows - 1
        self._follow_bottom = True
        self._sel_anchor = None
        self._sel_head = None
        self._cursor_shape = "block"
        self._cursor_color = self._default_fg
        self._cursor_color_custom = False
        self._cursor_dectcem_visible = True
        self._cursor_blink_enabled = True
        self._rows = [self._new_row() for _ in range(self._nrows)]
        self._term_reset_tabs()
        self._update_paint_colors()
        self._cursor_reset_blink_phase()
        self._sync_scrollbar()

    def _new_row(self, style=_TERM_DEFAULT_STYLE):
        return _TerminalRow(self._cols, style)

    def _screen_row(self, y):
        """The row object for 0-based screen row y."""
        return self._rows[len(self._rows) - self._nrows + y]

    def _term_reset_tabs(self):
        """Reset tab stops to the default every-8-columns (HTS/TBC use
        self._tab_stops directly to add/remove individual stops)."""
        self._tab_stops = set(range(8, self._cols, 8))

    def _term_next_tab(self, col):
        """The column Tab moves to from col, clamped to the last column."""
        _cands = [_s for _s in self._tab_stops if _s > col]
        if _cands:
            return min(min(_cands), self._cols - 1)
        return self._cols - 1

    def _term_effective_cx(self):
        """The cursor's column clamped to the grid (self._cx is one past
        the last column while an autowrap is pending)."""
        return min(self._cx, self._cols - 1)

    # ------------------------------------------------------------------
    # Colors, fonts, geometry
    # ------------------------------------------------------------------

    def setWorkingDirectory(self, directory):
        """Set the directory the next subprocess (first start or
        restart()) starts in; a running one is left where it is."""
        self._term_cwd = directory

    def setTerminalFontSize(self, size):
        """Change the font size (in points), keeping the family,
        re-measure the cells and, once the subprocess is running,
        refit the grid to the new cell size."""
        self._term_font_size = size
        self._term_font_variants = {}
        self._term_measure_char_size()
        self._sync_scrollbar()
        if self._term_started and not self._closed:
            self._resize_timer.start()

    def setDefaultColors(self, foreground=None, background=None):
        """Set the default text and background colors (anything QColor
        accepts); None for either goes back to the widget's palette."""
        self._term_custom_default_colors = (foreground, background)
        self._term_refresh_default_colors()

    def _term_refresh_default_colors(self):
        """Re-read the terminal's default fg/bg (explicit colors if set,
        otherwise the widget's palette), and repaint."""
        _fg, _bg = self._term_custom_default_colors
        palette = self.palette()
        self._default_fg = QColor(_fg) if _fg else palette.color(QPalette.ColorRole.Text)
        self._default_bg = QColor(_bg) if _bg else palette.color(QPalette.ColorRole.Base)
        if not self._cursor_color_custom:
            self._cursor_color = self._default_fg
        self._update_paint_colors()

    def _update_paint_colors(self):
        """Work out the fg/bg actually painted for "@fg"/"@bg" (swapped
        while the screen is in reverse video) and drop the cached
        per-style colors."""
        if self._reverse_screen:
            self._paint_fg, self._paint_bg = self._default_bg, self._default_fg
        else:
            self._paint_fg, self._paint_bg = self._default_fg, self._default_bg
        self._color_cache.clear()
        self.viewport().update()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.PaletteChange:
            self._term_refresh_default_colors()
        super().changeEvent(event)

    def _term_font_variant(self, bold=False, italic=False):
        """A font with this terminal's font family and size but bold
        and/or italic (cached)."""
        key = (bold, italic)
        if key not in self._term_font_variants:
            qfont = QFont(self._term_font_name)
            qfont.setPointSizeF(float(self._term_font_size))
            qfont.setStyleHint(QFont.StyleHint.Monospace)
            qfont.setFixedPitch(True)
            qfont.setKerning(False)
            qfont.setBold(bold)
            qfont.setItalic(italic)
            self._term_font_variants[key] = qfont
        return self._term_font_variants[key]

    def _term_measure_char_size(self):
        """Measure one monospace character's pixel size, needed to
        convert the widget's pixel size to a column/row grid size."""
        metrics = QFontMetricsF(self._term_font_variant())
        self.charwidth = max(1, round(metrics.horizontalAdvance("M")))
        self.charheight = max(1, int(metrics.height() + 0.999))
        self._char_ascent = int(metrics.ascent() + 0.5)

    def sizeHint(self):
        return QSize(80 * self.charwidth, 24 * self.charheight)

    def _term_compute_size(self):
        """The (cols, rows) that fit in the viewport's current pixel size."""
        viewport = self.viewport()
        return (
            max(1, viewport.width() // self.charwidth),
            max(1, viewport.height() // self.charheight),
        )

    def _style_colors(self, style, selected):
        """The (fg, bg) QColors to paint a cell of this style with; bg is
        None when it is the plain default background (nothing to fill)."""
        key = (style, selected)
        cached = self._color_cache.get(key)
        if cached is not None:
            return cached
        if selected:
            result = (self._paint_bg, self._paint_fg)
        else:
            result = (
                self._style_color(style[0]),
                None if style[1] == "@bg" else self._style_color(style[1]),
            )
        self._color_cache[key] = result
        return result

    def _style_color(self, colour):
        if colour == "@fg":
            return self._paint_fg
        if colour == "@bg":
            return self._paint_bg
        return QColor(colour)

    # ------------------------------------------------------------------
    # Cursor
    # ------------------------------------------------------------------

    def setcursortype(self, to="block"):
        """Set the cursor shape ('block', 'bar', or 'underline'), as
        requested by a DECSCUSR escape sequence."""
        self._cursor_shape = to
        self.viewport().update()

    def _cursor_set_color(self, color, custom=True):
        """Set the cursor's color; custom=False marks it as the
        terminal's default color rather than one set by an OSC 12
        escape (ignored in nocolor mode)."""
        if custom and self.nocolor:
            return
        self._cursor_color = QColor(color)
        self._cursor_color_custom = custom
        self.viewport().update()

    def _cursor_set_visible(self, visible):
        """Show/hide the cursor (DECTCEM, '\\x1b[?25h'/'\\x1b[?25l')."""
        self._cursor_dectcem_visible = visible
        self.viewport().update()

    def _cursor_set_blink_enabled(self, enabled):
        self._cursor_blink_enabled = enabled
        self._cursor_reset_blink_phase()
        self.viewport().update()

    def _cursor_reset_blink_phase(self):
        """Restart the blink cycle with the cursor visible (called on
        any cursor move/input)."""
        self._cursor_blink_visible = True
        self._cursor_blink_timer.stop()
        if self._cursor_blink_enabled and not self._closed:
            self._cursor_blink_timer.start(600)
        self.viewport().update()

    def _cursor_blink_tick(self):
        if self._closed:
            return
        self._cursor_blink_visible = not self._cursor_blink_visible
        self.viewport().update()
        self._cursor_blink_timer.start(600 if self._cursor_blink_visible else 300)

    def _start_blink(self):
        """Start the shared timer that toggles every SGR "blink" cell's
        visibility, if not already running."""
        if not self._blink_timer.isActive():
            self._blink_timer.start()

    def _blink_tick(self):
        """Toggle blinking text's visibility; stops itself once the last
        paint showed nothing blinking."""
        if self._closed or not self._blink_painted:
            self._blink_timer.stop()
            self._blink_visible = True
            self.viewport().update()
            return
        self._blink_visible = not self._blink_visible
        self.viewport().update()

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def _first_visible_line(self):
        return self.verticalScrollBar().value()

    def paintEvent(self, event):
        painter = QPainter(self.viewport())
        clip = event.rect()
        painter.fillRect(clip, self._paint_bg)
        charw, charh = self.charwidth, self.charheight
        first = self._first_visible_line()
        sel = self._selection_bounds()
        self._blink_painted = False
        for vy in range(clip.top() // charh, clip.bottom() // charh + 1):
            line = first + vy
            if line >= len(self._rows):
                break
            row = self._rows[line]
            sel_a = sel_b = 0
            if sel is not None and sel[0][0] <= line <= sel[1][0]:
                sel_a = sel[0][1] if line == sel[0][0] else 0
                sel_b = sel[1][1] if line == sel[1][0] else len(row.chars)
            self._paint_row(painter, row, vy * charh, sel_a, sel_b)
        self._paint_cursor(painter, first)
        painter.end()

    def _paint_row(self, painter, row, y, sel_a, sel_b):
        """Paint one row at pixel offset y: per-style runs of background,
        then each cell's glyph, underline and strikethrough."""
        charw, charh = self.charwidth, self.charheight
        chars, styles = row.chars, row.styles
        n = len(chars)
        i = 0
        while i < n:
            style = styles[i]
            selected = sel_a <= i < sel_b
            j = i + 1
            while j < n and (styles[j] is style or styles[j] == style):
                if (sel_a <= j < sel_b) != selected:
                    break
                j += 1
            fg, bg = self._style_colors(style, selected)
            if bg is not None:
                painter.fillRect(i * charw, y, (j - i) * charw, charh, bg)
            if style[6]:
                self._blink_painted = True
                self._start_blink()
            hide_text = style[6] and not self._blink_visible
            if not hide_text:
                painter.setFont(self._term_font_variant(style[2], style[3]))
                painter.setPen(fg)
                baseline = y + self._char_ascent
                for k in range(i, j):
                    c = chars[k]
                    if c and c != " ":
                        painter.drawText(k * charw, baseline, c)
            if style[4]:
                painter.fillRect(i * charw, y + self._char_ascent + 1, (j - i) * charw, 1, fg)
            if style[5]:
                painter.fillRect(i * charw, y + charh // 2, (j - i) * charw, 1, fg)
            i = j

    def _paint_cursor(self, painter, first):
        """Paint the cursor over its cell: a block (with the character
        under it in inverted colors), a bar, or an underline."""
        if (
            not self._cursor_dectcem_visible
            or not self._cursor_has_focus
            or (self._cursor_blink_enabled and not self._cursor_blink_visible)
        ):
            return
        charw, charh = self.charwidth, self.charheight
        line = len(self._rows) - self._nrows + self._cy
        y = (line - first) * charh
        if y < 0 or y >= self.viewport().height():
            return
        cx = self._term_effective_cx()
        row = self._rows[line]
        x = cx * charw
        style = row.styles[cx]
        char_fg, char_bg = self._style_colors(style, False)
        char_bg = char_bg if char_bg is not None else self._paint_bg
        if self._cursor_color_custom:
            cursor_bg, cursor_fg = self._cursor_color, self._paint_bg
        else:
            cursor_bg, cursor_fg = char_fg, char_bg
        if self._cursor_shape == "bar":
            painter.fillRect(x, y, 2, charh, cursor_bg)
        elif self._cursor_shape == "underline":
            painter.fillRect(x, y + charh - 2, charw, 2, cursor_bg)
        else:
            wide = cx + 1 < len(row.chars) and row.chars[cx + 1] == ""
            painter.fillRect(x, y, charw * (2 if wide else 1), charh, cursor_bg)
            c = row.chars[cx]
            if c and c != " ":
                painter.setFont(self._term_font_variant(style[2], style[3]))
                painter.setPen(cursor_fg)
                painter.drawText(x, y + self._char_ascent, c)

    # ------------------------------------------------------------------
    # Scrolling view
    # ------------------------------------------------------------------

    def _visible_row_count(self):
        return max(1, self.viewport().height() // self.charheight)

    def _sync_scrollbar(self):
        """Update the scrollbar range to the buffer size, keeping the
        view at the bottom while following it."""
        bar = self.verticalScrollBar()
        visible = self._visible_row_count()
        maximum = max(0, len(self._rows) - visible)
        self._viewport_follow_syncing = True
        try:
            bar.setRange(0, maximum)
            bar.setPageStep(visible)
            if self._follow_bottom:
                bar.setValue(maximum)
        finally:
            self._viewport_follow_syncing = False
        self.viewport().update()

    def _on_scrollbar_value(self, value):
        """Track whether the view is scrolled to the bottom, so new
        output keeps auto-scrolling only while the user hasn't scrolled
        up to look at history."""
        if not self._viewport_follow_syncing:
            self._follow_bottom = value >= self.verticalScrollBar().maximum()
        self.viewport().update()

    def _trim_scrollback(self):
        """Drop the oldest scrollback lines past the cap, shifting the
        selection along with the text."""
        excess = len(self._rows) - self._nrows - _TERM_MAX_SCROLLBACK_LINES
        if excess <= 0:
            return
        del self._rows[:excess]
        if self._sel_anchor is not None:
            if self._sel_anchor[0] < excess or self._sel_head[0] < excess:
                self._sel_anchor = self._sel_head = None
            else:
                self._sel_anchor = (self._sel_anchor[0] - excess, self._sel_anchor[1])
                self._sel_head = (self._sel_head[0] - excess, self._sel_head[1])

    # ------------------------------------------------------------------
    # Process management
    # ------------------------------------------------------------------

    def showEvent(self, event):
        """First time this terminal is actually shown, start its
        subprocess (sizing needs real widget dimensions, unavailable
        before then)."""
        super().showEvent(event)
        if not self._term_started:
            self._term_started = True
            QTimer.singleShot(0, self._start_process)

    def _start_process(self):
        """Size the grid, then spawn the subprocess attached to a PTY
        (Python's pty module on POSIX systems, pywinpty on Windows), sized to
        match, and start the background thread that reads its output."""
        self._cols, self._nrows = self._term_compute_size()
        self._reset_emulator_state()
        cwd = self._term_cwd if self._term_cwd and os.path.isdir(self._term_cwd) else None
        if _TERM_USES_POSIX_PTY:
            self.master_fd, slave_fd = pty.openpty()
            fcntl.ioctl(
                self.master_fd,
                termios.TIOCSWINSZ,
                struct.pack("HHHH", self._nrows, self._cols, 0, 0),
            )
            shell = os.environ.get("SHELL", "/bin/bash")
            env = os.environ.copy()
            env["TERM"] = "xterm-256color"
            if not self.nocolor:
                env["COLORTERM"] = "truecolor"
            # COLORFGBG is the (unofficial but widely honored) xterm
            # convention some programs use to detect a light vs dark
            # terminal background when they can't query it directly.
            _fg_is_light = self._default_fg.lightnessF() >= 0.5
            _bg_is_light = self._default_bg.lightnessF() >= 0.5
            env["COLORFGBG"] = f"{15 if _fg_is_light else 0};{15 if _bg_is_light else 0}"
            try:
                self.proc = subprocess.Popen(
                    [
                        sys.executable,
                        "-I",
                        "-S",
                        "-c",
                        _TERM_EXEC_WITH_CONTROLLING_TTY,
                        *(self._term_command if self._term_command else [shell]),
                    ],
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    close_fds=True,
                    start_new_session=True,
                    cwd=cwd,
                    env=env,
                )
            finally:
                os.close(slave_fd)
        else:
            self.proc = PtyProcess.spawn(
                self._term_command if self._term_command else ["powershell.exe"],
                cwd=cwd,
                dimensions=(self._nrows, self._cols),
            )
        self._pty_holder["proc"] = self.proc
        self._pty_holder["fd"] = self.master_fd
        self._read_generation += 1
        threading.Thread(
            target=self._read,
            args=(self._read_generation, self._out_q, self.master_fd, self.proc),
            daemon=True,
        ).start()

    def _read(self, gen, q, fd, proc):
        """Background-thread target: read raw output from the PTY/proc
        and put decoded chunks on q for _drain_output() to process on
        the GUI thread; puts a final None once the process/fd closes.
        gen guards against a stale thread (from a previous restart())
        still running after a newer one has started."""
        _dec = codecs.getincrementaldecoder("utf-8")(errors="replace")

        def _put(item):
            while self._read_generation == gen:
                try:
                    q.put(item, timeout=0.1)
                except queue.Full:
                    continue
                try:
                    self._output_wake.emit()
                except RuntimeError:
                    pass
                return

        while self._read_generation == gen:
            try:
                if _TERM_USES_POSIX_PTY:
                    r, _, _ = select.select([fd], [], [], 0.05)
                    if r:
                        data = os.read(fd, 4096)
                        if not data:
                            break
                        _put(_dec.decode(data))
                    elif proc.poll() is not None:
                        break
                else:
                    data = proc.read(4096)
                    if data:
                        _put(data if isinstance(data, str) else _dec.decode(data))
            except Exception:
                break
        _put(None)

    def _write(self, data):
        """Send raw bytes to the subprocess's stdin (via the PTY)."""
        try:
            if _TERM_USES_POSIX_PTY:
                view = memoryview(data)
                while view:
                    view = view[os.write(self.master_fd, view) :]
            else:
                self.proc.write(data.decode("utf-8", errors="replace"))
        except Exception:
            pass

    def _drain_output(self):
        """Process queued subprocess output for up to _TERM_FRAME_BUDGET
        seconds per call (so a burst of output can't freeze the UI),
        rescheduling itself if there's more backlog to catch up on, and
        handling the subprocess having exited."""
        if self._closed:
            return
        closed = backlog = had = False
        deadline = time.monotonic() + _TERM_FRAME_BUDGET
        while True:
            try:
                text = self._out_q.get_nowait()
            except queue.Empty:
                break
            if text is None:
                closed = True
                break
            try:
                self._process(text)
            except Exception:
                traceback.print_exc()
            had = True
            if time.monotonic() > deadline:
                backlog = True
                break
        if had:
            self._after_output()
            self.outputProcessed.emit()
        if closed:
            self._on_process_closed()
        elif backlog:
            QTimer.singleShot(_TERM_FRAME_MS, self._drain_output)

    def _after_output(self):
        self._cursor_reset_blink_phase()
        self._sync_scrollbar()

    def _on_process_closed(self):
        """The subprocess exited: show endmessage and wait for a
        keypress, or tear down right away if there is none."""
        self._emit_process_ended()
        if self.endmessage:
            last = 0
            for y in range(self._nrows - 1, -1, -1):
                if "".join(self._screen_row(y).chars).strip():
                    last = y
                    break
            self._cy = last
            if not self.nocolor:
                _sgr_apply(self._sgr_state, [0])
                self._refresh_cell_style()
            self._process("\r\n\r\n\r\n" + self.endmessage.replace("\n", "\r\n"))
            self._awaiting_key = True
            self._follow_bottom = True
            self._after_output()
        else:
            QTimer.singleShot(0, self._terminate_process)

    def _emit_process_ended(self):
        """Mark the subprocess as no longer running and emit
        processEnded once (idempotent)."""
        if not self.running:
            return
        self.running = False
        self.processEnded.emit()

    def _on_about_to_quit(self):
        try:
            self._terminate_process()
        except RuntimeError:
            pass

    def _terminate_process(self, restarting=False):
        """Kill the subprocess and release its PTY; safe to call more
        than once. restarting suppresses the actions (like emitting
        stopped) that only make sense when the terminal is actually
        closing for good."""
        if self._closed:
            return
        self._closed = True
        self._awaiting_key = False
        self._read_generation += 1
        self._emit_process_ended()
        try:
            while True:
                self._out_q.get_nowait()
        except queue.Empty:
            pass
        _term_kill_pty_process(self._pty_holder)
        self.master_fd = None
        self._cursor_blink_timer.stop()
        self._blink_timer.stop()
        self._resize_timer.stop()
        if not restarting:
            self.stopped.emit()

    def stop(self):
        """Kill the subprocess and release the PTY for good (emits
        stopped); safe to call more than once."""
        self._terminate_process()

    def restart(self):
        """Kill the current subprocess and start a fresh one with a
        blank screen, resetting all emulator state (cursor, tabs, SGR,
        modes, alternate screen) back to defaults."""
        self._terminate_process(restarting=True)
        self._out_q = queue.Queue(maxsize=64)
        self._closed = False
        self.running = True
        self._start_process()

    # ------------------------------------------------------------------
    # Resizing
    # ------------------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_scrollbar()
        if self._term_started and not self._closed:
            self._resize_timer.start()

    def _term_apply_resize(self):
        """Apply a settled resize: recompute the grid size and, if it
        actually changed, resize the grid and notify the subprocess."""
        if not self._term_started or self._closed or self.proc is None:
            return
        cols, rows = self._term_compute_size()
        if cols == self._cols and rows == self._nrows:
            return
        self._term_resize_grid(cols, rows)

    @staticmethod
    def _term_row_resize_cells(row, cols):
        """Pad or truncate a row to exactly cols cells."""
        n = len(row.chars)
        if n < cols:
            row.chars.extend([" "] * (cols - n))
            row.styles.extend([_TERM_DEFAULT_STYLE] * (cols - n))
        elif n > cols:
            del row.chars[cols:]
            del row.styles[cols:]
            if cols and row.chars[cols - 1] and _term_char_width(row.chars[cols - 1][0]) == 2:
                row.chars[cols - 1] = " "

    def _term_reshape_primary(self, rows_list, cy, new_rows, new_cols):
        """Reshape a primary-screen buffer (rows_list, with the cursor
        on screen row cy) from the current grid height to new_rows, and
        its screen rows' width to new_cols; returns the new cursor row.
        Shrinking drops blank rows below the cursor first and then
        pushes the top rows into scrollback; growing pulls rows back out
        of scrollback before adding blank ones."""
        old_rows = self._nrows
        if new_rows < old_rows:
            diff = old_rows - new_rows
            removable = 0
            while (
                removable < diff
                and old_rows - 1 - removable > cy
                and not "".join(rows_list[-1 - removable].chars).strip()
            ):
                removable += 1
            if removable:
                del rows_list[len(rows_list) - removable :]
            shift = min(diff - removable, cy)
            leftover = diff - removable - shift
            if leftover:
                del rows_list[len(rows_list) - leftover :]
            cy -= shift
        elif new_rows > old_rows:
            grow = new_rows - old_rows
            pull = min(grow, len(rows_list) - old_rows)
            cy += pull
            rows_list.extend(_TerminalRow(new_cols) for _ in range(grow - pull))
        for row in rows_list[len(rows_list) - new_rows :]:
            self._term_row_resize_cells(row, new_cols)
        return cy

    def _term_resize_grid(self, cols, rows):
        """Resize the character grid to cols x rows: in the alternate
        screen, pad/truncate every row and add/remove rows directly,
        since a full-screen app (e.g. vim, less) expects its exact grid
        to be preserved; in the primary screen, move rows between the
        screen and scrollback. Then tells the PTY and subprocess about
        the new size (TIOCSWINSZ + SIGWINCH) on Linux."""
        if self._alt_mode:
            for row in self._rows:
                self._term_row_resize_cells(row, cols)
            if rows > len(self._rows):
                self._rows.extend(_TerminalRow(cols) for _ in range(rows - len(self._rows)))
            else:
                del self._rows[rows:]
            self._cy = min(self._cy, rows - 1)
            saved = self._alt_saved
            saved_rows, saved_cy = saved[0], saved[1]
            saved_cy = self._term_reshape_primary(saved_rows, saved_cy, rows, cols)
            self._alt_saved = (saved_rows, saved_cy) + saved[2:]
        else:
            self._cy = self._term_reshape_primary(self._rows, self._cy, rows, cols)
        if cols > self._cols:
            # Newly exposed columns get the default tab stop every 8 columns.
            self._tab_stops.update(range((self._cols + 7) // 8 * 8, cols, 8))
        self._cols = cols
        self._nrows = rows
        self._cx = min(self._cx, cols)
        self._scroll_top = 0
        self._scroll_bot = rows - 1
        self._sel_anchor = self._sel_head = None
        if _TERM_USES_POSIX_PTY:
            if self.master_fd is not None:
                try:
                    fcntl.ioctl(
                        self.master_fd,
                        termios.TIOCSWINSZ,
                        struct.pack("HHHH", rows, cols, 0, 0),
                    )
                    os.killpg(self.proc.pid, signal.SIGWINCH)
                except Exception:
                    pass
        else:
            try:
                self.proc.setwinsize(rows, cols)
            except Exception:
                pass
        self._trim_scrollback()
        self._sync_scrollbar()

    # ------------------------------------------------------------------
    # Grid operations
    # ------------------------------------------------------------------

    def _fix_wide_overlap(self, row, start, end):
        """Blank the other half of any wide character cut in two by
        overwriting cells [start, end) of row."""
        chars = row.chars
        if start > 0 and start < len(chars) and chars[start] == "":
            chars[start - 1] = " "
        if end < len(chars) and chars[end] == "":
            chars[end] = " "

    def _fix_wide_orphans(self, row):
        """Blank every half-wide-character left over in row (after cells
        were shifted by insert/delete character)."""
        chars = row.chars
        for i, c in enumerate(chars):
            if c == "":
                if i == 0 or not chars[i - 1] or _term_char_width(chars[i - 1][0]) != 2:
                    chars[i] = " "
            elif _term_char_width(c[0]) == 2 and (i + 1 >= len(chars) or chars[i + 1] != ""):
                chars[i] = " "

    def _fill_row(self, y, start, end):
        """Blank cells [start, end) of screen row y with the erase style
        (current background)."""
        row = self._screen_row(y)
        end = min(end, len(row.chars))
        if start >= end:
            return
        self._fix_wide_overlap(row, start, end)
        row.chars[start:end] = [" "] * (end - start)
        row.styles[start:end] = [self._erase_style] * (end - start)
        if start == 0 and end >= len(row.chars):
            row.wrapped = False

    def _scroll_up(self, n=1):
        """Scroll the scroll region up n lines, blank lines entering at
        the bottom. With the region starting at the top of the primary
        screen the lines leaving it go into scrollback."""
        top, bot = self._scroll_top, self._scroll_bot
        for _ in range(min(n, bot - top + 1)):
            blank = self._new_row(self._erase_style)
            base = len(self._rows) - self._nrows
            if not self._alt_mode and top == 0:
                self._rows.insert(base + bot + 1, blank)
            else:
                del self._rows[base + top]
                self._rows.insert(base + bot, blank)
        self._trim_scrollback()

    def _scroll_down(self, n=1):
        """Scroll the scroll region down n lines, blank lines entering
        at the top."""
        top, bot = self._scroll_top, self._scroll_bot
        for _ in range(min(n, bot - top + 1)):
            base = len(self._rows) - self._nrows
            del self._rows[base + bot]
            self._rows.insert(base + top, self._new_row(self._erase_style))

    def _linefeed(self):
        """Move the cursor down one line, scrolling the region if it is
        on the region's last line."""
        if self._cy == self._scroll_bot:
            self._scroll_up(1)
        elif self._cy < self._nrows - 1:
            self._cy += 1

    def _reverse_linefeed(self):
        """Move the cursor up one line, scrolling the region down if it
        is on the region's first line."""
        if self._cy == self._scroll_top:
            self._scroll_down(1)
        elif self._cy > 0:
            self._cy -= 1

    def _origin_row(self, row):
        """Clamp a 1-based cursor-addressing row to a 0-based screen row,
        within the scroll region if origin mode (DECOM) is set."""
        if self._origin_mode:
            return min(max(self._scroll_top, self._scroll_top + row - 1), self._scroll_bot)
        return min(max(0, row - 1), self._nrows - 1)

    def _cursor_home(self):
        """Move the cursor to the top-left of the screen (or of the
        scroll region, in origin mode)."""
        self._cy = self._scroll_top if self._origin_mode else 0
        self._cx = 0

    def _put_text(self, run):
        """Write a run of printable characters at the cursor and
        advance it, wrapping to the next line (scrolling if needed) if
        it runs off the right edge and autowrap is on, or just parking
        at the last column if not. Characters are measured by terminal
        column width (a combining mark adds no column, an East Asian
        wide character adds two)."""
        cols = self._cols
        style = self._cell_style
        row = self._screen_row(self._cy)
        if run.isascii():
            while run:
                if self._cx >= cols:
                    if self._autowrap:
                        row.wrapped = True
                        self._linefeed()
                        self._cx = 0
                        row = self._screen_row(self._cy)
                    else:
                        self._cx = cols - 1
                space = cols - self._cx
                if len(run) > space and not self._autowrap:
                    # Everything past the last column overwrites it.
                    run = run[: space - 1] + run[-1]
                chunk, run = run[:space], run[space:]
                cx = self._cx
                self._fix_wide_overlap(row, cx, cx + len(chunk))
                row.chars[cx : cx + len(chunk)] = chunk
                row.styles[cx : cx + len(chunk)] = [style] * len(chunk)
                self._cx = cx + len(chunk)
            return
        for ch in run:
            w = _term_char_width(ch)
            if w == 0:
                px = min(self._cx, cols) - 1
                while px > 0 and row.chars[px] == "":
                    px -= 1
                if px >= 0:
                    row.chars[px] += ch
                continue
            if self._cx + w > cols:
                if self._autowrap:
                    row.wrapped = True
                    self._linefeed()
                    self._cx = 0
                    row = self._screen_row(self._cy)
                else:
                    self._cx = max(0, cols - w)
            cx = self._cx
            self._fix_wide_overlap(row, cx, cx + w)
            row.chars[cx] = ch
            row.styles[cx] = style
            if w == 2 and cx + 1 < cols:
                row.chars[cx + 1] = ""
                row.styles[cx + 1] = style
            self._cx = cx + w

    def _refresh_cell_style(self):
        """Recompute the style new characters get (and the style erased
        cells get) from the current SGR state."""
        if self.nocolor:
            return
        self._cell_style = _term_cell_style(self._sgr_state)
        self._erase_style = _term_erase_style(self._cell_style)
        if self._cell_style[6]:
            self._start_blink()

    def _erase_in_line(self, mode):
        y, cx, cols = self._cy, self._term_effective_cx(), self._cols
        if mode == 0:
            self._fill_row(y, cx, cols)
        elif mode == 1:
            self._fill_row(y, 0, cx + 1)
        else:
            self._fill_row(y, 0, cols)

    def _erase_in_display(self, mode):
        y, cx, cols = self._cy, self._term_effective_cx(), self._cols
        if mode == 0:
            self._fill_row(y, cx, cols)
            for r in range(y + 1, self._nrows):
                self._fill_row(r, 0, cols)
        elif mode == 1:
            for r in range(y):
                self._fill_row(r, 0, cols)
            self._fill_row(y, 0, cx + 1)
        elif mode == 2:
            self._clear_screen()
        elif mode == 3 and not self._alt_mode:
            del self._rows[: len(self._rows) - self._nrows]
            self._sel_anchor = self._sel_head = None
            # With the scrollback gone there is nothing to scroll back to.
            self._follow_bottom = True

    def _clear_screen(self):
        """Erase the whole screen. On the primary screen the rows
        holding text are first pushed into scrollback instead of being
        lost."""
        if not self._alt_mode:
            used = 0
            for y in range(self._nrows - 1, -1, -1):
                if "".join(self._screen_row(y).chars).strip():
                    used = y + 1
                    break
            self._rows.extend(self._new_row() for _ in range(used))
            self._trim_scrollback()
        for y in range(self._nrows):
            self._fill_row(y, 0, self._cols)

    def _deccolm_clear(self):
        """Clear the screen and home the cursor, as DECSET 3 (switching
        80/132-column mode) requires."""
        self._scroll_top = 0
        self._scroll_bot = self._nrows - 1
        self._clear_screen()
        self._cy = self._cx = 0

    def _enter_alt_screen(self):
        """Switch to a blank alternate screen buffer (DECSET 1049 etc,
        used by full-screen apps like vim/less), saving the current
        primary-screen content/cursor/SGR to restore on
        _leave_alt_screen()."""
        if self._alt_saved is not None:
            return
        self._alt_saved = (
            self._rows,
            self._cy,
            self._cx,
            dict(self._sgr_state),
            self._scroll_top,
            self._scroll_bot,
        )
        self._alt_mode = True
        self._rows = [self._new_row() for _ in range(self._nrows)]
        self._cy = self._cx = 0
        self._scroll_top = 0
        self._scroll_bot = self._nrows - 1
        self._sel_anchor = self._sel_head = None
        if not self.nocolor:
            _sgr_apply(self._sgr_state, [0])
            self._refresh_cell_style()

    def _leave_alt_screen(self):
        """Restore the primary screen saved by _enter_alt_screen()."""
        if self._alt_saved is None:
            return
        rows, cy, cx, sgr, scroll_top, scroll_bot = self._alt_saved
        self._alt_saved = None
        self._alt_mode = False
        self._rows = rows
        self._cy = cy
        self._cx = min(cx, self._cols)
        self._scroll_top, self._scroll_bot = scroll_top, scroll_bot
        self._sgr_state.update(sgr)
        self._refresh_cell_style()
        self._sel_anchor = self._sel_head = None

    def _full_reset(self):
        """RIS ('\\x1bc'): back to the power-on state, with a blank
        screen."""
        self._reset_emulator_state()
        self._cursor_set_color(self._default_fg, custom=False)

    # ------------------------------------------------------------------
    # OSC
    # ------------------------------------------------------------------

    def _osc_colour_reply(self, which, colour):
        """Reply to an OSC color query (e.g. '\\x1b]10;?\\x1b\\\\' asking
        for the foreground color) with colour's RGB in the same OSC
        reply format."""
        r, g, b = (_c * 257 for _c in QColor(colour).getRgb()[:3])
        self._write(f"\x1b]{which};rgb:{r:04x}/{g:04x}/{b:04x}\x1b\\".encode())

    @staticmethod
    def _osc_parse_colour(spec):
        """Parse an OSC color spec ('rgb:rr/gg/bb' or a named/#hex
        color Qt understands) to a '#rrggbb' string, or None if it isn't
        a color Qt recognizes."""
        spec = spec.strip()
        if spec.startswith("rgb:"):
            parts = spec[4:].split("/")
            if len(parts) == 3:
                try:
                    return "#" + "".join(
                        f"{int(p[:2], 16):02x}" if len(p) >= 2 else f"{int(p, 16):02x}"
                        for p in parts
                    )
                except Exception:
                    return None
            return None
        return spec if QColor(spec).isValid() else None

    def _handle_osc(self, body):
        """Handle an OSC ('\\x1b]...\\x1b\\\\' or BEL-terminated) escape's
        body: OSC 52 sets the system clipboard (base64-encoded); OSC
        10/11 query the fg/bg color; OSC 12/112 get/reset the cursor
        color. Every other OSC code (e.g. window title) is silently
        ignored."""
        if body.startswith("52;"):
            parts = body.split(";", 2)
            if len(parts) == 3 and parts[2] not in ("", "?"):
                try:
                    text = base64.b64decode(parts[2]).decode("utf-8", errors="replace")
                except Exception:
                    return
                QApplication.clipboard().setText(text)
        elif body.startswith("11;?"):
            self._osc_colour_reply("11", self._default_bg)
        elif body.startswith("10;?"):
            self._osc_colour_reply("10", self._default_fg)
        elif body.startswith("12;"):
            _spec = body[3:]
            if _spec == "?":
                self._osc_colour_reply("12", self._cursor_color)
            else:
                _col = self._osc_parse_colour(_spec)
                if _col:
                    self._cursor_set_color(_col)
        elif body == "112" or body.startswith("112;"):
            self._cursor_set_color(self._default_fg, custom=False)

    # ------------------------------------------------------------------
    # Escape sequence parsing
    # ------------------------------------------------------------------

    def _csi_embedded(self, rest):
        """Fallback parser for a CSI sequence ('\\x1b[' + rest) that
        didn't match the main CSI regex, e.g. one with C0 control
        characters embedded inside its parameters/intermediates.
        Separates those embedded controls (controls) from the rest of
        the sequence (cleaned) so the caller can splice them back into
        the input as their own, independently processed characters.
        Returns (controls, cleaned, consumed_length, status), where
        status is "splice" (both parts ready), "pending" (need more
        data before the sequence can be parsed) or "skip" (not a
        recognizable sequence, drop it)."""
        controls = ""
        cleaned = "\x1b["
        k = 2
        ln = len(rest)
        while k < ln:
            c = rest[k]
            o = ord(c)
            if c == "\x1b":
                return controls, "", k, "splice"
            if c == "\x18" or c == "\x1a":
                return controls, "", k + 1, "splice"
            if o < 0x20 or c == "\x7f":
                controls += c
                k += 1
                continue
            if 0x40 <= o <= 0x7E:
                if controls:
                    return controls, cleaned + c, k + 1, "splice"
                return "", "", 0, "skip"
            if 0x20 <= o <= 0x3F:
                cleaned += c
                k += 1
                continue
            return "", "", 0, "skip"
        if ln < _PTY_MAX_PENDING_ESC:
            return "", "", 0, "pending"
        return "", "", 0, "skip"

    def _process(self, text):
        """The terminal emulator's core: interpret one chunk of decoded
        subprocess output (text) and apply it to the cell grid.

        Scans text handling C0 control characters (newline, backspace,
        tab, ...) directly and recognizing ESC-introduced sequences: CSI
        ('\\x1b[...', see _handle_csi()), OSC ('\\x1b]...', see
        _handle_osc()), and the handful of other lone ESC sequences
        (save/restore cursor, index/reverse-index, character sets,
        ...). An escape sequence split across two output chunks is
        buffered in self._pending_esc and retried once more data
        arrives. Ordinary printable characters are written via
        _put_text() with the current SGR style applied.
        """
        if self._pending_esc:
            text = self._pending_esc + text
            self._pending_esc = ""
        if self._osc_skipping:
            _skip_end = _TERM_OSC_END_RE.search(text)
            if not _skip_end:
                if text.endswith("\x1b"):
                    self._pending_esc = "\x1b"
                return
            text = text[_skip_end.end() :]
            self._osc_skipping = False
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if ch >= " " and ch != "\x7f":
                m = _TERM_PRINTABLE_RUN_RE.match(text, i)
                run = m.group(0)
                self._put_text(run)
                self._last_char = run[-1]
                i = m.end()
            elif ch == "\r":
                self._cx = 0
                i += 1
            elif ch == "\x08":
                self._cx = max(0, self._term_effective_cx() - 1)
                i += 1
            elif ch == "\n" or ch == "\x0b" or ch == "\x0c":
                self._screen_row(self._cy).wrapped = False
                self._linefeed()
                i += 1
            elif ch == "\t":
                self._cx = self._term_next_tab(self._term_effective_cx())
                i += 1
            elif ch == "\x1b":
                if i + 1 >= n:
                    self._pending_esc = text[i:]
                    break
                nxt = text[i + 1]
                if nxt == "[":
                    m = _TERM_CSI_RE.match(text, i)
                    if m:
                        self._handle_csi(m.group(1), m.group(2))
                        i = m.end()
                    elif _TERM_CSI_PENDING_RE.fullmatch(text, i):
                        self._pending_esc = text[i:]
                        break
                    else:
                        _ctl, _clean, _consumed, _status = self._csi_embedded(text[i:])
                        if _status == "pending":
                            self._pending_esc = text[i:]
                            break
                        elif _status == "splice":
                            text = text[:i] + _ctl + _clean + text[i + _consumed :]
                            n = len(text)
                        else:
                            i += 2
                elif nxt == "]":
                    end_bel = text.find("\x07", i + 2)
                    end_st = text.find("\x1b\\", i + 2)
                    if end_bel >= 0 and (end_st < 0 or end_bel < end_st):
                        self._handle_osc(text[i + 2 : end_bel])
                        i = end_bel + 1
                    elif end_st >= 0:
                        self._handle_osc(text[i + 2 : end_st])
                        i = end_st + 2
                    elif n - i < _PTY_MAX_PENDING_ESC:
                        self._pending_esc = text[i:]
                        break
                    else:
                        self._osc_skipping = True
                        i = n
                elif nxt == "M":
                    self._reverse_linefeed()
                    i += 2
                elif nxt == "D":
                    self._linefeed()
                    i += 2
                elif nxt == "E":
                    self._linefeed()
                    self._cx = 0
                    i += 2
                elif nxt in "()*+#%":
                    if i + 2 >= n:
                        self._pending_esc = text[i:]
                        break
                    if nxt == "#" and text[i + 2] == "8":
                        for y in range(self._nrows):
                            row = self._screen_row(y)
                            row.chars[:] = ["E"] * self._cols
                            row.styles[:] = [_TERM_DEFAULT_STYLE] * self._cols
                        self._cy = self._cx = 0
                    i += 3
                elif nxt == "c":
                    self._full_reset()
                    i += 2
                elif nxt == "7":
                    self._saved_cursor = (self._alt_mode, self._cy, self._term_effective_cx())
                    self._saved_sgr = dict(self._sgr_state)
                    i += 2
                elif nxt == "8":
                    self._restore_cursor()
                    if self._saved_sgr is not None:
                        self._sgr_state.update(self._saved_sgr)
                        self._refresh_cell_style()
                    i += 2
                elif nxt == "H":
                    self._tab_stops.add(self._term_effective_cx())
                    i += 2
                elif nxt == "\x1b":
                    i += 1
                else:
                    i += 2
            else:
                i += 1

    def _restore_cursor(self):
        """Restore the cursor saved by ESC 7 / CSI s, if it was saved on
        the screen (primary or alternate) that is showing now."""
        if self._saved_cursor is not None and self._saved_cursor[0] == self._alt_mode:
            _, sy, sx = self._saved_cursor
            self._cy = min(sy, self._nrows - 1)
            self._cx = min(sx, self._cols - 1)

    def _handle_csi(self, prefix, final):
        """Execute one CSI sequence: prefix is the parameter bytes plus
        any intermediate bytes ('0;5', '?25', '>4;2', '1 ', ...), final
        its final byte."""
        private = prefix.startswith("?")
        digits = "".join(c for c in prefix if c in "0123456789;")
        p = [int(x) if x else 0 for x in digits.split(";")] if digits else [0]
        # cmd is the final byte for a plain ('12;34') or '?'-prefixed
        # sequence, empty for any other prefix ('>', ' ', ...), which
        # only the few specific cases below recognize.
        cmd = final if all(c in "0123456789;?" for c in prefix) else ""
        cols, nrows = self._cols, self._nrows
        y, cx = self._cy, self._term_effective_cx()
        mv = p[0] or 1
        if cmd == "K":
            self._erase_in_line(p[0])
        elif cmd == "J":
            self._erase_in_display(p[0])
        elif cmd in ("H", "f"):
            self._cy = self._origin_row(p[0] or 1)
            self._cx = min(max(0, (p[1] if len(p) > 1 and p[1] else 1) - 1), cols - 1)
        elif cmd == "A":
            limit = self._scroll_top if y >= self._scroll_top else 0
            self._cy = max(limit, y - mv)
        elif cmd == "B":
            limit = self._scroll_bot if y <= self._scroll_bot else nrows - 1
            self._cy = min(limit, y + mv)
        elif cmd == "C":
            self._cx = min(cx + mv, cols - 1)
        elif cmd == "D":
            self._cx = max(0, cx - mv)
        elif cmd == "E":
            self._cy = min(nrows - 1, y + mv)
            self._cx = 0
        elif cmd == "F":
            self._cy = max(0, y - mv)
            self._cx = 0
        elif cmd == "G":
            self._cx = min(mv - 1, cols - 1)
        elif cmd == "d":
            self._cy = self._origin_row(mv)
        elif cmd == "s" and not private:
            self._saved_cursor = (self._alt_mode, y, cx)
        elif cmd == "u" and not private:
            self._restore_cursor()
        elif cmd == "g":
            if p[0] == 0:
                self._tab_stops.discard(cx)
            elif p[0] == 3:
                self._tab_stops = set()
        elif cmd == "P":
            row = self._screen_row(y)
            mv = min(mv, cols - cx)
            del row.chars[cx : cx + mv]
            del row.styles[cx : cx + mv]
            row.chars.extend([" "] * mv)
            row.styles.extend([self._erase_style] * mv)
            self._fix_wide_orphans(row)
        elif cmd == "@":
            row = self._screen_row(y)
            mv = min(mv, cols - cx)
            row.chars[cx:cx] = [" "] * mv
            row.styles[cx:cx] = [self._erase_style] * mv
            del row.chars[cols:]
            del row.styles[cols:]
            self._fix_wide_orphans(row)
        elif cmd == "L":
            if self._scroll_top <= y <= self._scroll_bot:
                n = min(mv, self._scroll_bot - y + 1)
                base = len(self._rows) - nrows
                del self._rows[base + self._scroll_bot - n + 1 : base + self._scroll_bot + 1]
                self._rows[base + y : base + y] = [self._new_row(self._erase_style) for _ in range(n)]
                self._cx = 0
        elif cmd == "M":
            if self._scroll_top <= y <= self._scroll_bot:
                n = min(mv, self._scroll_bot - y + 1)
                base = len(self._rows) - nrows
                del self._rows[base + y : base + y + n]
                at = base + self._scroll_bot - n + 1
                self._rows[at:at] = [self._new_row(self._erase_style) for _ in range(n)]
                self._cx = 0
        elif cmd == "S":
            self._scroll_up(mv)
        elif cmd == "T":
            self._scroll_down(mv)
        elif cmd == "r":
            top = min(max(1, p[0] or 1), nrows)
            bot = min(max(top, (p[1] if len(p) > 1 else 0) or nrows), nrows)
            self._scroll_top, self._scroll_bot = top - 1, bot - 1
            self._cursor_home()
        elif cmd == "X":
            n = min(mv, cols - cx)
            row = self._screen_row(y)
            self._fix_wide_overlap(row, cx, cx + n)
            row.chars[cx : cx + n] = [" "] * n
            row.styles[cx : cx + n] = [self._erase_style] * n
        elif final == "c" and not private:
            if prefix.startswith(">"):
                self._write(b"\x1b[>1;10;0c")
            else:
                self._write(b"\x1b[?1;2c")
        elif cmd == "b":
            if self._last_char:
                self._put_text(self._last_char * mv)
        elif final == "q" and prefix.endswith(" "):
            _cs = p[0]
            if _cs in (0, 1, 2):
                self.setcursortype("block")
                self._cursor_set_blink_enabled(_cs != 2)
            elif _cs in (3, 4):
                self.setcursortype("underline")
                self._cursor_set_blink_enabled(_cs == 3)
            elif _cs in (5, 6):
                self.setcursortype("bar")
                self._cursor_set_blink_enabled(_cs == 5)
        elif cmd == "n":
            if p[0] == 6:
                self._write(f"\x1b[{y + 1};{cx + 1}R".encode())
            elif p[0] == 5:
                self._write(b"\x1b[0n")
        elif cmd == "m" and not private:
            if not self.nocolor:
                _sgr_apply(self._sgr_state, p)
                self._refresh_cell_style()
        elif final == "m" and private:
            _pp = p[0]
            _pv = self._modify_other_keys if _pp == 4 else 0
            self._write(f"\x1b[>{_pp};{_pv}m".encode())
        elif final == "m" and prefix.startswith(">"):
            if p[0] == 4:
                self._modify_other_keys = p[1] if len(p) > 1 else 0
        elif cmd == "h" and private:
            for code in p:
                self._set_private_mode(code, True)
        elif cmd == "l" and private:
            for code in p:
                self._set_private_mode(code, False)

    def _set_private_mode(self, code, on):
        """Set or reset one DEC private mode (CSI ? code h / l)."""
        if code in (1049, 1047, 47):
            if on:
                self._enter_alt_screen()
            else:
                self._leave_alt_screen()
        elif code == 3:
            self._deccolm_clear()
        elif code == 6:
            self._origin_mode = on
            self._cursor_home()
        elif code == 25:
            self._cursor_set_visible(on)
        elif code == 12:
            self._cursor_set_blink_enabled(on)
        elif code == 5:
            if self._reverse_screen != on:
                self._reverse_screen = on
                self._update_paint_colors()
        elif code == 2004:
            self._bracketed_paste = on
        elif code == 1004:
            self._focus_reporting = on
        elif code == 7:
            self._autowrap = on
        elif code == 1:
            self._app_cursor = on
        elif code in (1000, 1002, 1003):
            self._mouse_mode = code if on else 0
        elif code == 1006:
            self._mouse_sgr = on
        elif code == 1007:
            self._alternate_scroll = on

    # ------------------------------------------------------------------
    # Keyboard input
    # ------------------------------------------------------------------

    def event(self, e):
        # The terminal gets every key itself (Ctrl+letter, Tab, ...)
        # instead of the window's shortcuts getting first pick.
        if e.type() == QEvent.Type.ShortcutOverride:
            e.accept()
            return True
        return super().event(e)

    def focusNextPrevChild(self, next):
        return False

    def keyPressEvent(self, event):
        """Translate a keypress into the bytes/escape sequence the
        subprocess expects (arrow/function keys as CSI/SS3/tilde
        sequences depending on the current mode, Control-letter combos
        as their C0 control code, Alt-modified keys as ESC plus the key,
        everything else as its literal character), and send it."""
        event.accept()
        key = event.key()
        if key in self._term_modifier_only_keys:
            return
        mods = event.modifiers()
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        alt = bool(mods & Qt.KeyboardModifier.AltModifier)
        if ctrl and shift:
            if key == Qt.Key.Key_C:
                self._copy_selection()
                return
            if key == Qt.Key.Key_V:
                self._paste_clipboard()
                return
            if key == Qt.Key.Key_A:
                self._select_all()
                return
        if not self.running:
            if self._awaiting_key:
                self._terminate_process()
            return
        self._cursor_reset_blink_phase()
        text = event.text()
        if ctrl and Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
            text = chr(key - 64)
        if alt:
            self._clear_selection()
            self._send_meta_key(key, text)
            return
        if text or key in self._term_selection_clearing_keys:
            self._clear_selection()
        self._send_key(key, text, shift, ctrl)

    def _send_key(self, key, text, shift, ctrl):
        _kmod = 1 + (1 if shift else 0) + (4 if ctrl else 0)
        _mok_named = {
            Qt.Key.Key_Return: 13,
            Qt.Key.Key_Enter: 13,
            Qt.Key.Key_Backspace: 127,
            Qt.Key.Key_Tab: 9,
            Qt.Key.Key_Escape: 27,
        }
        if (
            self._modify_other_keys == 2
            and _kmod > 1
            and key in _mok_named
            and not (key == Qt.Key.Key_Tab and shift)
        ):
            self._write(f"\x1b[27;{_kmod};{_mok_named[key]}~".encode())
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._write(b"\r")
        elif key == Qt.Key.Key_Backspace:
            self._write(b"\x7f")
        elif key == Qt.Key.Key_Backtab or (key == Qt.Key.Key_Tab and shift):
            self._write(b"\x1b[Z")
        elif key == Qt.Key.Key_Tab:
            self._write(b"\t")
        elif key in self._term_csi_keys:
            _kl = self._term_csi_keys[key]
            if _kmod > 1:
                self._write(f"\x1b[1;{_kmod}{_kl}".encode())
            elif self._app_cursor:
                self._write(("\x1bO" + _kl).encode())
            else:
                self._write(("\x1b[" + _kl).encode())
        elif key in self._term_tilde_keys:
            _kn = self._term_tilde_keys[key]
            if _kmod > 1:
                self._write(f"\x1b[{_kn};{_kmod}~".encode())
            else:
                self._write(f"\x1b[{_kn}~".encode())
        elif key in self._term_ss3_keys:
            _kl = self._term_ss3_keys[key]
            if _kmod > 1:
                self._write(f"\x1b[1;{_kmod}{_kl}".encode())
            else:
                self._write(("\x1bO" + _kl).encode())
        elif ctrl and key in (Qt.Key.Key_Space, Qt.Key.Key_At, Qt.Key.Key_2):
            self._write(b"\x00")
        elif ctrl and key in (Qt.Key.Key_BracketLeft, Qt.Key.Key_3):
            self._write(b"\x1b")
        elif ctrl and key in (Qt.Key.Key_Backslash, Qt.Key.Key_4):
            self._write(b"\x1c")
        elif ctrl and key in (Qt.Key.Key_BracketRight, Qt.Key.Key_5):
            self._write(b"\x1d")
        elif ctrl and key in (Qt.Key.Key_AsciiCircum, Qt.Key.Key_6):
            self._write(b"\x1e")
        elif ctrl and key in (Qt.Key.Key_Underscore, Qt.Key.Key_Slash, Qt.Key.Key_7):
            self._write(b"\x1f")
        elif (
            self._modify_other_keys
            and _kmod > 1
            and 0x20 <= key <= 0x7E
            and (self._modify_other_keys == 2 or not text)
        ):
            _code = key + 32 if Qt.Key.Key_A <= key <= Qt.Key.Key_Z and not shift else key
            self._write(f"\x1b[27;{_kmod};{_code}~".encode())
        elif text:
            self._write(text.encode("utf-8"))

    def _send_meta_key(self, key, text):
        """Send Alt-modified keys as ESC followed by the plain key (the
        usual "meta sends escape" terminal convention)."""
        if text:
            self._write(b"\x1b" + text.encode("utf-8"))
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            _pfx = b"\x1bO" if self._app_cursor else b"\x1b["
            self._write(
                b"\x1b"
                + {
                    Qt.Key.Key_Left: b"b",
                    Qt.Key.Key_Right: b"f",
                    Qt.Key.Key_Up: _pfx + b"A",
                    Qt.Key.Key_Down: _pfx + b"B",
                }[key]
            )

    def inputMethodEvent(self, event):
        """Send text committed through an input method (composed
        characters, dead keys, ...)."""
        commit = event.commitString()
        if commit and self.running:
            self._clear_selection()
            self._write(commit.encode("utf-8"))
        event.accept()

    def inputMethodQuery(self, query):
        if query == Qt.InputMethodQuery.ImCursorRectangle:
            line = len(self._rows) - self._nrows + self._cy
            return QRect(
                self._term_effective_cx() * self.charwidth,
                (line - self._first_visible_line()) * self.charheight,
                self.charwidth,
                self.charheight,
            )
        return super().inputMethodQuery(query)

    def focusInEvent(self, event):
        """Show/resume-blinking the cursor and report focus gained
        (CSI I) if the subprocess asked for focus events (DECSET 1004)."""
        super().focusInEvent(event)
        self._cursor_has_focus = True
        self._cursor_reset_blink_phase()
        if self._focus_reporting and self.running:
            self._write(b"\x1b[I")

    def focusOutEvent(self, event):
        """Hide the cursor and report focus lost (CSI O) if the
        subprocess asked for focus events."""
        super().focusOutEvent(event)
        self._cursor_has_focus = False
        self.viewport().update()
        if self._focus_reporting and self.running:
            self._write(b"\x1b[O")

    # ------------------------------------------------------------------
    # Selection and clipboard
    # ------------------------------------------------------------------

    def _selection_bounds(self):
        """The selection as ((line, col), (line, col)) in reading order
        (end exclusive), or None when nothing is selected."""
        if self._sel_anchor is None or self._sel_anchor == self._sel_head:
            return None
        return tuple(sorted((self._sel_anchor, self._sel_head)))

    def _clear_selection(self):
        if self._sel_anchor is not None:
            self._sel_anchor = self._sel_head = None
            self.viewport().update()

    def _select_all(self):
        self._sel_anchor = (0, 0)
        self._sel_head = (len(self._rows) - 1, len(self._rows[-1].chars))
        self.viewport().update()

    def _selection_text(self):
        """The selected text, joining wrapped lines (rows flagged
        wrapped) back together without an inserted newline, matching
        the actual line the terminal's output put them on."""
        bounds = self._selection_bounds()
        if bounds is None:
            return ""
        (l0, c0), (l1, c1) = bounds
        parts = []
        joined_to_previous = False
        for line in range(l0, l1 + 1):
            row = self._rows[line]
            a = c0 if line == l0 else 0
            b = c1 if line == l1 else len(row.chars)
            seg = "".join(row.chars[a:b])
            if not row.wrapped:
                seg = seg.rstrip(" ")
            if joined_to_previous:
                parts[-1] += seg
            else:
                parts.append(seg)
            joined_to_previous = row.wrapped
        return "\n".join(parts).rstrip("\n")

    def _copy_selection(self):
        """Copy the selected text to the clipboard."""
        text = self._selection_text()
        if text:
            QApplication.clipboard().setText(text)

    def _paste_clipboard(self):
        """Send the clipboard's text to the subprocess (converting
        newlines to carriage returns), wrapped in bracketed-paste
        markers if the subprocess enabled that mode."""
        if not self.running:
            return
        data = QApplication.clipboard().text()
        if data:
            data = data.replace("\r\n", "\r").replace("\n", "\r")
            payload = data.encode("utf-8")
            if self._bracketed_paste:
                payload = b"\x1b[200~" + payload + b"\x1b[201~"
            self._write(payload)
            self._clear_selection()

    def _show_context_menu(self, global_pos):
        """Show the right-click context menu (Copy/Paste/Select All)."""
        menu = QMenu(self)
        menu.addAction("Copy", self._copy_selection).setEnabled(
            self._selection_bounds() is not None
        )
        menu.addAction("Paste", self._paste_clipboard)
        menu.addSeparator()
        menu.addAction("Select All", self._select_all)
        menu.exec(global_pos)

    # ------------------------------------------------------------------
    # Mouse input
    # ------------------------------------------------------------------

    def _term_mouse_cell(self, pos):
        """Convert a viewport pixel position to 1-based (col, row)
        terminal grid coordinates."""
        col = pos.x() // self.charwidth + 1
        row = pos.y() // self.charheight + 1
        return max(1, min(col, self._cols)), max(1, min(row, self._nrows))

    def _term_mouse_mods(self, mods):
        """The modifier bits (Shift/Meta/Control) to add to a mouse
        report, in the encoding mouse-reporting escape sequences use."""
        bits = 0
        if mods & Qt.KeyboardModifier.ShiftModifier:
            bits |= 4
        if mods & Qt.KeyboardModifier.AltModifier:
            bits |= 8
        if mods & Qt.KeyboardModifier.ControlModifier:
            bits |= 16
        return bits

    def _term_send_mouse(self, button, event, release=False, drag=False):
        """Report a mouse event to the subprocess if mouse reporting is
        enabled (self._mouse_mode) and Shift isn't held (which reserves
        the click for the terminal's own selection instead); returns
        whether it was actually sent, in either the modern SGR (1006) or
        legacy X10 mouse-report encoding depending on what the
        subprocess requested."""
        if not self.running or not self._mouse_mode:
            return False
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            return False
        if drag and self._mouse_mode < 1002:
            return False
        col, row = self._term_mouse_cell(event.position().toPoint())
        if drag and not release and (col, row) == self._mouse_last_pos:
            return True
        mods = self._term_mouse_mods(event.modifiers())
        cb = button + mods
        if drag:
            cb += 32
        if self._mouse_sgr:
            suffix = "m" if release else "M"
            self._write(f"\x1b[<{cb};{col};{row}{suffix}".encode())
        else:
            if release:
                cb = 3 + mods
            self._write(
                bytes([27, ord("["), ord("M"), min(cb + 32, 255), min(col + 32, 255), min(row + 32, 255)])
            )
        self._mouse_last_pos = (col, row)
        return True

    _term_mouse_button_codes = {
        Qt.MouseButton.LeftButton: 0,
        Qt.MouseButton.MiddleButton: 1,
        Qt.MouseButton.RightButton: 2,
    }

    def _term_line_col(self, pos, boundary):
        """The (buffer line, cell column) under a viewport pixel
        position; with boundary the column is the nearest cell edge
        (for selection ends) rather than the cell itself."""
        line = self._first_visible_line() + max(0, pos.y()) // self.charheight
        line = min(line, len(self._rows) - 1)
        width = len(self._rows[line].chars)
        x = pos.x() + (self.charwidth // 2 if boundary else 0)
        return line, max(0, min(x // self.charwidth, width if boundary else width - 1))

    def mousePressEvent(self, event):
        self._press_or_double_click(event, double=False)

    def mouseDoubleClickEvent(self, event):
        self._press_or_double_click(event, double=True)

    def _press_or_double_click(self, event, double):
        button = event.button()
        code = self._term_mouse_button_codes.get(button)
        if code is None:
            return
        if self._term_send_mouse(code, event):
            return
        pos = event.position().toPoint()
        if button == Qt.MouseButton.LeftButton:
            now = time.monotonic()
            if double:
                self._last_double_click_time = now
                self._select_word(*self._term_line_col(pos, boundary=False))
            elif (
                self._last_double_click_time is not None
                and now - self._last_double_click_time < QApplication.doubleClickInterval() / 1000
            ):
                self._last_double_click_time = None
                line = self._term_line_col(pos, boundary=False)[0]
                self._sel_anchor = (line, 0)
                self._sel_head = (line, len(self._rows[line].chars))
            else:
                self._sel_anchor = self._sel_head = self._term_line_col(pos, boundary=True)
                self._selecting = True
            self.viewport().update()
        elif button == Qt.MouseButton.MiddleButton:
            self._paste_clipboard()

    def _select_word(self, line, col):
        """Select the run of word characters (or of spaces, or of other
        punctuation) around cell col of line."""
        chars = self._rows[line].chars

        def _kind(c):
            if c in ("", " "):
                return 0
            return 1 if c[0].isalnum() or c[0] == "_" else 2

        kind = _kind(chars[col])
        a = col
        while a > 0 and _kind(chars[a - 1]) == kind:
            a -= 1
        b = col + 1
        while b < len(chars) and _kind(chars[b]) == kind:
            b += 1
        self._sel_anchor, self._sel_head = (line, a), (line, b)

    def mouseMoveEvent(self, event):
        buttons = event.buttons()
        if buttons:
            for button, code in self._term_mouse_button_codes.items():
                if buttons & button:
                    if self._term_send_mouse(code, event, drag=True):
                        return
                    break
            if self._selecting and buttons & Qt.MouseButton.LeftButton:
                pos = event.position().toPoint()
                bar = self.verticalScrollBar()
                if pos.y() < 0:
                    bar.setValue(bar.value() - 1)
                elif pos.y() >= self.viewport().height():
                    bar.setValue(bar.value() + 1)
                self._sel_head = self._term_line_col(pos, boundary=True)
                self.viewport().update()
        elif self._mouse_mode == 1003:
            self._term_send_mouse(3, event, drag=True)

    def mouseReleaseEvent(self, event):
        button = event.button()
        code = self._term_mouse_button_codes.get(button)
        if code is None:
            return
        if self._term_send_mouse(code, event, release=True):
            return
        if button == Qt.MouseButton.LeftButton:
            self._selecting = False
        elif button == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())

    def wheelEvent(self, event):
        """Report the scroll wheel to the subprocess if it wants mouse
        events, otherwise scroll the view (or, in the alternate screen,
        send the arrow-key escapes many full-screen apps treat as
        scrolling)."""
        delta = event.angleDelta().y()
        if not delta:
            return
        up = delta > 0
        steps = max(1, abs(delta) // 120)
        if self._mouse_mode and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            for _ in range(steps):
                self._term_send_mouse(64 if up else 65, event)
            event.accept()
            return
        if (
            self._alt_mode
            and self._alternate_scroll
            and self.running
            and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        ):
            _seq = (
                (b"\x1bOA" if self._app_cursor else b"\x1b[A")
                if up
                else (b"\x1bOB" if self._app_cursor else b"\x1b[B")
            )
            for _ in range(_TERM_WHEEL_SCROLL_LINES * steps):
                self._write(_seq)
            event.accept()
            return
        bar = self.verticalScrollBar()
        lines = round(delta / 120 * _TERM_WHEEL_SCROLL_LINES) or (1 if up else -1)
        bar.setValue(bar.value() - lines)
        event.accept()

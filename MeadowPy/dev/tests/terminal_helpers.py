"""Shared helpers for the terminal emulator tests."""

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QResizeEvent
from PyQt6.QtWidgets import QApplication

from meadowpy.pyqtterm import Terminal


def make_terminal(cols=20, rows=5, **kwargs):
    """A Terminal with a fixed grid, sized to show exactly that grid, whose
    answers to the subprocess are collected in terminal.written instead of
    being sent anywhere."""
    terminal = Terminal(**kwargs)
    terminal._cols = cols
    terminal._nrows = rows
    terminal._reset_emulator_state()
    terminal.written = []
    terminal._write = terminal.written.append
    fit_to_grid(terminal)
    return terminal


def fit_to_grid(terminal):
    """Give the widget the pixel size of its grid and let it lay out."""
    terminal.resize(
        terminal._cols * terminal.charwidth,
        terminal._nrows * terminal.charheight,
    )
    QApplication.sendEvent(terminal, QResizeEvent(terminal.size(), QSize()))


def screen(terminal):
    return [
        "".join(terminal._screen_row(y).chars).rstrip()
        for y in range(terminal._nrows)
    ]


def cursor(terminal):
    return terminal._cy, terminal._cx

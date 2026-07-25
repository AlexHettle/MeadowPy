"""Text formatting helpers for the output panel."""

import re

from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor

from meadowpy.resources.resource_loader import theme_is_high_contrast


# Matches Python traceback file references, e.g.:
#   File "C:\Users\Alex\script.py", line 42, in <module>
TRACEBACK_RE = re.compile(r'^\s*File "([^"]+)", line (\d+)')


def normalize_output_text(text: str) -> str:
    """Normalize output newlines for QPlainTextEdit insertion."""
    return text.replace("\r", "")


def stream_text_format(stream: str, theme_name: str) -> QTextCharFormat:
    """Return the character format for non-stderr output streams."""
    fmt = QTextCharFormat()
    is_hc = theme_is_high_contrast(theme_name)
    if stream == "hint":
        fmt.setForeground(QColor("#FFFFFF") if is_hc else QColor("#4EC9B0"))
        fmt.setFontItalic(True)
    elif stream == "system":
        fmt.setForeground(QColor("#FFFFFF") if is_hc else QColor("#888888"))
        fmt.setFontItalic(True)
    return fmt


def stderr_text_formats(theme_name: str) -> tuple[QTextCharFormat, QTextCharFormat]:
    """Return (stderr_format, traceback_link_format) for a theme."""
    is_hc = theme_is_high_contrast(theme_name)

    stderr_fmt = QTextCharFormat()
    stderr_fmt.setForeground(QColor("#FFFFFF") if is_hc else QColor("#E51400"))

    link_fmt = QTextCharFormat()
    link_fmt.setForeground(QColor("#FFFFFF") if is_hc else QColor("#5999D4"))
    link_fmt.setFontUnderline(True)

    return stderr_fmt, link_fmt


def insert_stderr_text(
    cursor: QTextCursor,
    text: str,
    theme_name: str,
) -> None:
    """Insert stderr text, styling traceback file lines as links."""
    stderr_fmt, link_fmt = stderr_text_formats(theme_name)

    lines = text.split("\n")
    for i, line in enumerate(lines):
        if TRACEBACK_RE.match(line):
            cursor.insertText(line, link_fmt)
        else:
            cursor.insertText(line, stderr_fmt)
        if i < len(lines) - 1:
            cursor.insertText("\n", stderr_fmt)

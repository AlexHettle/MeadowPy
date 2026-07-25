"""Terminal panel - interactive shell dock."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import locale
import os
import re
import subprocess
from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QKeySequence,
    QTextCharFormat,
    QTextCursor,
)
from PyQt6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QToolButton,
    QVBoxLayout,
)
from PyQt6.QtCore import QProcess, QProcessEnvironment, pyqtSignal

from meadowpy.resources.resource_loader import (
    load_themed_icon,
    theme_is_high_contrast,
)
from meadowpy.ui.panel_title_bar import (
    PANEL_TITLE_CONTROL_SIZE,
    PANEL_TITLE_ICON_SIZE,
    configure_panel_title_bar,
    configure_panel_title_label,
)


_ANSI_ESCAPE_RE = re.compile(
    r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07]*(?:\x07|\x1b\\)"
)

_ANSI_COLORS = {
    30: "#000000",
    31: "#C62828",
    32: "#2E7D32",
    33: "#B26A00",
    34: "#1565C0",
    35: "#7B1FA2",
    36: "#00838F",
    37: "#D0D0D0",
    90: "#707070",
    91: "#EF5350",
    92: "#66BB6A",
    93: "#FDD835",
    94: "#42A5F5",
    95: "#AB47BC",
    96: "#26C6DA",
    97: "#FFFFFF",
}


@dataclass(frozen=True)
class _CompletionResult:
    replacement_index: int
    replacement_length: int
    candidates: list[str]


_COMMON_POWERSHELL_COMMANDS = (
    "cd",
    "chdir",
    "clear",
    "cls",
    "copy",
    "cp",
    "del",
    "dir",
    "echo",
    "erase",
    "exit",
    "gc",
    "gci",
    "Get-ChildItem",
    "Get-Command",
    "Get-Content",
    "Get-Help",
    "Get-Location",
    "gi",
    "git",
    "ls",
    "mkdir",
    "move",
    "mv",
    "New-Item",
    "ni",
    "pip",
    "pwd",
    "python",
    "pytest",
    "Remove-Item",
    "rm",
    "rmdir",
    "Select-String",
    "Set-Content",
    "Set-Location",
    "type",
    "Where-Object",
)


def _normalize_terminal_text(text: str) -> str:
    """Normalize newlines and erase unsupported cursor-control noise."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _apply_sgr_code(
    fmt: QTextCharFormat,
    code: int,
    base_format: QTextCharFormat,
    *,
    high_contrast: bool,
) -> QTextCharFormat:
    """Return a format updated for one ANSI SGR code."""
    if code == 0:
        return QTextCharFormat(base_format)
    if code == 1:
        fmt.setFontWeight(QFont.Weight.Bold)
    elif code == 22:
        fmt.setFontWeight(QFont.Weight.Normal)
    elif code == 39:
        reset = QTextCharFormat(base_format)
        reset.setFontWeight(fmt.fontWeight())
        return reset
    elif code in _ANSI_COLORS:
        fmt.setForeground(QColor("#FFFFFF" if high_contrast else _ANSI_COLORS[code]))
    return fmt


def _ansi_segments(
    text: str,
    base_format: QTextCharFormat,
    *,
    high_contrast: bool,
):
    """Yield text segments paired with QTextCharFormat objects."""
    current = QTextCharFormat(base_format)
    pos = 0
    text = _normalize_terminal_text(text)
    for match in _ANSI_ESCAPE_RE.finditer(text):
        if match.start() > pos:
            yield text[pos:match.start()], QTextCharFormat(current)

        sequence = match.group(0)
        if sequence.startswith("\x1b[") and sequence.endswith("m"):
            params = sequence[2:-1]
            codes = [0] if not params else []
            for raw in params.split(";"):
                try:
                    codes.append(int(raw))
                except ValueError:
                    continue
            for code in codes:
                current = _apply_sgr_code(
                    current,
                    code,
                    base_format,
                    high_contrast=high_contrast,
                )
        pos = match.end()

    if pos < len(text):
        yield text[pos:], QTextCharFormat(current)


class _TerminalView(QPlainTextEdit):
    """Editable terminal surface that protects previous output."""

    command_submitted = pyqtSignal(str)
    completion_requested = pyqtSignal(str, int, int)
    history_previous_requested = pyqtSignal()
    history_next_requested = pyqtSignal()
    interrupt_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._input_start = 0
        self.setUndoRedoEnabled(False)
        self.setWordWrapMode(self.wordWrapMode())
        self.document().setMaximumBlockCount(10000)

    def append_output(
        self,
        text: str,
        base_format: QTextCharFormat,
        *,
        high_contrast: bool,
    ) -> None:
        """Append shell output while preserving any partially typed input."""
        pending_input = self.current_input()
        at_bottom = self._is_scrolled_to_bottom()

        self._remove_current_input()
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)

        for segment, fmt in _ansi_segments(
            text,
            base_format,
            high_contrast=high_contrast,
        ):
            if segment:
                cursor.insertText(segment, fmt)

        self._input_start = self._document_end_position()
        if pending_input:
            cursor.insertText(pending_input)
        self.setTextCursor(cursor)
        if at_bottom:
            self.ensureCursorVisible()

    def clear_all(self) -> None:
        self.clear()
        self._input_start = 0

    def current_input(self) -> str:
        cursor = QTextCursor(self.document())
        cursor.setPosition(min(self._input_start, self._document_end_position()))
        cursor.setPosition(
            self._document_end_position(),
            QTextCursor.MoveMode.KeepAnchor,
        )
        return cursor.selectedText().replace("\u2029", "\n")

    def current_input_cursor_column(self) -> int:
        cursor = self.textCursor()
        position = cursor.selectionStart() if cursor.hasSelection() else cursor.position()
        return max(0, min(position - self._input_start, len(self.current_input())))

    def set_current_input(self, text: str, cursor_column: int | None = None) -> None:
        self._remove_current_input()
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        if cursor_column is not None:
            cursor.setPosition(
                self._input_start + max(0, min(cursor_column, len(text)))
            )
        self.setTextCursor(cursor)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        modifiers = event.modifiers()

        if key == Qt.Key.Key_C and modifiers & Qt.KeyboardModifier.ControlModifier:
            if self.textCursor().hasSelection():
                self.copy()
            else:
                self.interrupt_requested.emit()
            event.accept()
            return

        completion_direction = 0
        if key == Qt.Key.Key_Backtab:
            completion_direction = -1
        elif key == Qt.Key.Key_Tab:
            completion_direction = (
                -1
                if modifiers & Qt.KeyboardModifier.ShiftModifier
                else 1
            )

        if completion_direction and not modifiers & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
        ):
            self._ensure_editable_cursor()
            self.completion_requested.emit(
                self.current_input(),
                self.current_input_cursor_column(),
                completion_direction,
            )
            event.accept()
            return

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._submit_current_input()
            event.accept()
            return

        if key == Qt.Key.Key_Up and not modifiers & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
        ):
            self.history_previous_requested.emit()
            event.accept()
            return

        if key == Qt.Key.Key_Down and not modifiers & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
        ):
            self.history_next_requested.emit()
            event.accept()
            return

        if key == Qt.Key.Key_Home and not modifiers & Qt.KeyboardModifier.ControlModifier:
            self._move_to_input_start(
                keep_anchor=bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
            )
            event.accept()
            return

        if key in (Qt.Key.Key_Left, Qt.Key.Key_Backspace):
            cursor = self.textCursor()
            if not cursor.hasSelection() and cursor.position() <= self._input_start:
                event.accept()
                return

        if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            if not self._selection_is_editable():
                event.accept()
                return

        if event.matches(QKeySequence.StandardKey.Cut):
            if not self._selection_is_editable():
                event.accept()
                return

        if event.matches(QKeySequence.StandardKey.Paste) or event.text():
            self._ensure_editable_cursor()

        super().keyPressEvent(event)

    def _submit_current_input(self) -> None:
        command = self.current_input()
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText("\n")
        self.setTextCursor(cursor)
        self._input_start = self._document_end_position()
        self.command_submitted.emit(command)

    def _document_end_position(self) -> int:
        return max(0, self.document().characterCount() - 1)

    def _remove_current_input(self) -> None:
        cursor = QTextCursor(self.document())
        cursor.setPosition(min(self._input_start, self._document_end_position()))
        cursor.setPosition(
            self._document_end_position(),
            QTextCursor.MoveMode.KeepAnchor,
        )
        cursor.removeSelectedText()
        self.setTextCursor(cursor)

    def _move_to_input_start(self, *, keep_anchor: bool = False) -> None:
        cursor = self.textCursor()
        cursor.setPosition(
            min(self._input_start, self._document_end_position()),
            QTextCursor.MoveMode.KeepAnchor
            if keep_anchor
            else QTextCursor.MoveMode.MoveAnchor,
        )
        self.setTextCursor(cursor)

    def _selection_is_editable(self) -> bool:
        cursor = self.textCursor()
        return (
            not cursor.hasSelection()
            or min(cursor.selectionStart(), cursor.selectionEnd()) >= self._input_start
        )

    def _ensure_editable_cursor(self) -> None:
        cursor = self.textCursor()
        if cursor.hasSelection() and not self._selection_is_editable():
            cursor.clearSelection()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.setTextCursor(cursor)
        elif cursor.position() < self._input_start:
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.setTextCursor(cursor)

    def _is_scrolled_to_bottom(self) -> bool:
        scrollbar = self.verticalScrollBar()
        return scrollbar.value() >= scrollbar.maximum() - 4


class TerminalPanel(QDockWidget):
    """Bottom dock panel for an interactive operating-system shell."""

    def __init__(
        self,
        parent=None,
        settings=None,
        *,
        auto_start_on_show: bool = True,
    ):
        super().__init__("Terminal", parent)
        self.setObjectName("TerminalPanel")
        self.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea
            | Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self._settings = settings
        self._auto_start_on_show = auto_start_on_show
        self._process: QProcess | None = None
        self._encoding = locale.getpreferredencoding(False) or "utf-8"
        self._working_directory = str(Path.home())
        self._history: list[str] = []
        self._history_index = 0
        self._last_prompt = ""
        self._last_submitted_command: str | None = None
        self._completion_candidates: list[str] = []
        self._completion_index = -1
        self._completion_base_prefix = ""
        self._completion_base_suffix = ""
        self._completion_current_line = ""
        self._setup_ui()
        self.visibilityChanged.connect(self._on_visibility_changed)

    def _setup_ui(self) -> None:
        title_bar = QFrame()
        title_bar.setObjectName("terminalTitleBar")
        title_bar.setFrameShape(QFrame.Shape.NoFrame)
        title_layout = QHBoxLayout(title_bar)
        configure_panel_title_bar(title_bar, title_layout, spacing=2)

        title_label = QLabel("Terminal")
        title_label.setObjectName("terminalTitleLabel")
        configure_panel_title_label(title_label)
        title_layout.addWidget(title_label, 0, Qt.AlignmentFlag.AlignVCenter)
        title_layout.addStretch()

        self._clear_btn = self._make_tool_button("clear_output", "Clear Terminal")
        title_layout.addWidget(self._clear_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.setTitleBarWidget(title_bar)
        self._title_bar = title_bar

        container = QFrame()
        container.setObjectName("terminalContainer")
        container.setFrameShape(QFrame.Shape.NoFrame)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._terminal_view = _TerminalView()
        self._terminal_view.setObjectName("terminalText")
        font = QFont("Consolas", 13)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._terminal_view.setFont(font)
        layout.addWidget(self._terminal_view)
        self.setWidget(container)

        self._terminal_view.command_submitted.connect(self.send_command)
        self._terminal_view.completion_requested.connect(self._on_completion_requested)
        self._terminal_view.history_previous_requested.connect(
            self._on_history_previous
        )
        self._terminal_view.history_next_requested.connect(self._on_history_next)
        self._terminal_view.interrupt_requested.connect(self.interrupt_process)

        self._clear_btn.clicked.connect(self.clear_terminal)

    def start_shell(self, working_directory: str | None = None) -> None:
        """Start the configured shell if it is not already running."""
        if working_directory:
            self.set_working_directory(working_directory)
        if self.is_running():
            return

        program, args = self._default_shell_command()
        self._process = QProcess(self)
        self._process.setWorkingDirectory(self._working_directory)
        self._process.setProcessChannelMode(
            QProcess.ProcessChannelMode.SeparateChannels
        )
        self._process.setProcessEnvironment(self._terminal_environment())
        self._connect_process_signals()
        self._process.start(program, args)

    def restart_shell(self) -> None:
        """Stop the current shell and start a fresh one."""
        self.stop()
        self.start_shell()
        self._terminal_view.setFocus()

    def focus_terminal(self) -> None:
        """Show, raise, start, and focus the terminal panel."""
        self.show()
        self.raise_()
        self.start_shell()
        self._terminal_view.setFocus()

    def set_working_directory(self, path: str) -> None:
        """Set the initial working directory for the next shell start."""
        if path and Path(path).is_dir():
            self._working_directory = str(Path(path))

    def send_command(self, command: str) -> None:
        """Send a command line to the shell."""
        if not self.is_running():
            self.start_shell()
        if not self.is_running():
            return

        if command.strip():
            self._add_history(command)
            self._last_submitted_command = command
        self._reset_completion()
        self._process.write((command + "\n").encode(self._encoding, errors="replace"))

    def interrupt_process(self) -> None:
        """Send a Ctrl+C byte to the shell process."""
        if self.is_running():
            self._process.write(b"\x03")

    def clear_terminal(self) -> None:
        self._terminal_view.clear_all()
        if self._last_prompt:
            self._terminal_view.append_output(
                self._last_prompt,
                self._stream_format("stdout"),
                high_contrast=self._is_high_contrast(),
            )

    def copy_terminal(self) -> None:
        cursor = self._terminal_view.textCursor()
        text = (
            cursor.selectedText().replace("\u2029", "\n")
            if cursor.hasSelection()
            else self._terminal_view.toPlainText()
        )
        if text:
            QApplication.clipboard().setText(text)

    def stop(self, timeout_ms: int = 1000) -> None:
        """Kill the shell process if it is still running."""
        if self._process is None:
            return
        process = self._process
        self._disconnect_process_signals()
        if process.state() != QProcess.ProcessState.NotRunning:
            process.kill()
            process.waitForFinished(timeout_ms)
        self._process = None

    def is_running(self) -> bool:
        return (
            self._process is not None
            and self._process.state() != QProcess.ProcessState.NotRunning
        )

    def refresh_theme_icons(self) -> None:
        """Reload title-bar icons after the app theme changes."""
        theme = self._current_theme_name()
        self._clear_btn.setIcon(load_themed_icon("clear_output", theme))

    def update_font(self, family: str, size: int) -> None:
        font = QFont(family, size)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._terminal_view.setFont(font)

    def _default_shell_command(self) -> tuple[str, list[str]]:
        if os.name == "nt":
            return "powershell.exe", ["-NoLogo", "-NoProfile", "-NoExit"]
        shell = os.environ.get("SHELL") or "/bin/sh"
        return shell, ["-i"]

    def _terminal_environment(self) -> QProcessEnvironment:
        env = QProcessEnvironment.systemEnvironment()
        env.insert("TERM", "xterm-256color")
        return env

    def _connect_process_signals(self) -> None:
        process = self._process
        process.readyReadStandardOutput.connect(self._on_stdout)
        process.readyReadStandardError.connect(self._on_stderr)
        process.finished.connect(self._on_finished)
        process.errorOccurred.connect(self._on_error)

    def _disconnect_process_signals(self) -> None:
        if self._process is None:
            return
        try:
            process = self._process
            process.readyReadStandardOutput.disconnect(self._on_stdout)
            process.readyReadStandardError.disconnect(self._on_stderr)
            process.finished.disconnect(self._on_finished)
            process.errorOccurred.disconnect(self._on_error)
        except (TypeError, RuntimeError):
            pass

    def _on_stdout(self) -> None:
        data = self._process.readAllStandardOutput().data()
        self._append_process_output(data, "stdout")

    def _on_stderr(self) -> None:
        data = self._process.readAllStandardError().data()
        self._append_process_output(data, "stderr")

    def _append_process_output(self, data: bytes, stream: str) -> None:
        text = data.decode(self._encoding, errors="replace")
        if stream == "stdout":
            text = self._filter_echoed_command(text)
            self._remember_prompt(text)
        if text:
            self._terminal_view.append_output(
                text,
                self._stream_format(stream),
                high_contrast=self._is_high_contrast(),
            )

    def _filter_echoed_command(self, text: str) -> str:
        command = self._last_submitted_command
        if not command:
            return text
        normalized = _normalize_terminal_text(text)
        for prefix in (command + "\n", command):
            if normalized.startswith(prefix):
                self._last_submitted_command = None
                return normalized[len(prefix):]
        return text

    def _remember_prompt(self, text: str) -> None:
        if os.name != "nt":
            return
        match = re.search(r"(PS ([^\n\r]*?)> )$", _normalize_terminal_text(text))
        if match:
            self._last_prompt = match.group(1)
            prompt_path = match.group(2)
            if prompt_path and Path(prompt_path).is_dir():
                self._working_directory = str(Path(prompt_path))

    def _on_completion_requested(
        self,
        line: str,
        cursor_column: int,
        direction: int,
    ) -> None:
        direction = -1 if direction < 0 else 1
        cursor_column = max(0, min(cursor_column, len(line)))
        if self._completion_candidates and line == self._completion_current_line:
            self._completion_index = (
                self._completion_index + direction
            ) % len(self._completion_candidates)
            self._apply_completion_candidate()
            return

        result = self._completion_result(line, cursor_column)
        if result is None or not result.candidates:
            self._reset_completion()
            return

        start = max(0, min(result.replacement_index, len(line)))
        length = max(0, min(result.replacement_length, len(line) - start))
        candidates = self._unique_completion_candidates(result.candidates)
        if not candidates:
            self._reset_completion()
            return

        self._completion_candidates = candidates
        self._completion_index = len(candidates) - 1 if direction < 0 else 0
        self._completion_base_prefix = line[:start]
        self._completion_base_suffix = line[start + length:]
        self._apply_completion_candidate()

    def _completion_result(
        self,
        line: str,
        cursor_column: int,
    ) -> _CompletionResult | None:
        result = self._powershell_completion_result(line, cursor_column)
        if result is not None and result.candidates:
            return result
        return self._fallback_completion_result(line, cursor_column)

    def _powershell_completion_result(
        self,
        line: str,
        cursor_column: int,
    ) -> _CompletionResult | None:
        if os.name != "nt":
            return None

        program, _args = self._default_shell_command()
        line_payload = base64.b64encode(line.encode("utf-8")).decode("ascii")
        script = (
            "$ProgressPreference = 'SilentlyContinue'\n"
            "$ErrorActionPreference = 'SilentlyContinue'\n"
            "try {\n"
            "    [Console]::OutputEncoding = "
            "[System.Text.UTF8Encoding]::new($false)\n"
            "    $line = [System.Text.Encoding]::UTF8.GetString("
            "[System.Convert]::FromBase64String('"
            + line_payload
            + "'))\n"
            f"    $cursor = {int(cursor_column)}\n"
            "    $result = TabExpansion2 -inputScript $line "
            "-cursorColumn $cursor\n"
            "    if ($null -ne $result) {\n"
            '        [Console]::Out.WriteLine(("MEADOWPY_COMPLETION`t{0}`t{1}" '
            "-f $result.ReplacementIndex, $result.ReplacementLength))\n"
            "        foreach ($match in $result.CompletionMatches) {\n"
            "            if ($null -ne $match.CompletionText) {\n"
            "                [Console]::Out.WriteLine($match.CompletionText)\n"
            "            }\n"
            "        }\n"
            "    }\n"
            "} catch {}\n"
        )
        encoded_script = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        try:
            completed = subprocess.run(
                [
                    program,
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-OutputFormat",
                    "Text",
                    "-EncodedCommand",
                    encoded_script,
                ],
                cwd=self._working_directory,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=1.5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return self._parse_powershell_completion(completed.stdout)

    def _parse_powershell_completion(self, output: str) -> _CompletionResult | None:
        lines = output.splitlines()
        for index, line in enumerate(lines):
            if not line.startswith("MEADOWPY_COMPLETION\t"):
                continue
            parts = line.split("\t")
            if len(parts) != 3:
                return None
            try:
                replacement_index = int(parts[1])
                replacement_length = int(parts[2])
            except ValueError:
                return None
            candidates = [
                candidate
                for candidate in lines[index + 1:]
                if candidate
                and not candidate.startswith("#< CLIXML")
                and not candidate.startswith("<Objs ")
            ]
            return _CompletionResult(
                replacement_index,
                replacement_length,
                candidates,
            )
        return None

    def _fallback_completion_result(
        self,
        line: str,
        cursor_column: int,
    ) -> _CompletionResult | None:
        start, token = self._completion_token(line, cursor_column)
        command_position = not line[:start].strip()
        token_body = token[1:] if token.startswith(("'", '"')) else token
        candidates: list[str] = []

        if command_position and not self._token_looks_like_path(token_body):
            candidates.extend(self._command_completion_candidates(token_body))

        if not command_position or self._token_looks_like_path(token_body):
            candidates.extend(self._path_completion_candidates(token))

        if command_position and not candidates:
            candidates.extend(self._path_completion_candidates(token))

        candidates = self._unique_completion_candidates(candidates)
        if not candidates:
            return None
        return _CompletionResult(start, cursor_column - start, candidates)

    def _completion_token(self, line: str, cursor_column: int) -> tuple[int, str]:
        prefix = line[:cursor_column]
        match = re.search(r"('(?:[^']*)|\"(?:[^\"]*)|\S*)$", prefix)
        token = match.group(0) if match else ""
        return cursor_column - len(token), token

    def _command_completion_candidates(self, prefix: str) -> list[str]:
        prefix_lower = prefix.lower()
        candidates = [
            command
            for command in _COMMON_POWERSHELL_COMMANDS
            if command.lower().startswith(prefix_lower)
        ]
        if len(prefix) >= 2:
            candidates.extend(self._path_executable_candidates(prefix))
        return sorted(candidates, key=str.lower)

    def _path_executable_candidates(self, prefix: str) -> list[str]:
        executable_exts = {
            ext.lower()
            for ext in os.environ.get(
                "PATHEXT",
                ".COM;.EXE;.BAT;.CMD;.PS1;.PY",
            ).split(";")
            if ext
        }
        prefix_lower = prefix.lower()
        candidates: list[str] = []
        for directory in os.environ.get("PATH", "").split(os.pathsep):
            try:
                for child in Path(directory).iterdir():
                    if len(candidates) >= 200:
                        return candidates
                    if not child.is_file():
                        continue
                    suffix = child.suffix.lower()
                    names = [child.name]
                    if os.name == "nt" and suffix in executable_exts:
                        names.append(child.stem)
                    for name in names:
                        if name.lower().startswith(prefix_lower):
                            candidates.append(name)
            except (OSError, ValueError):
                continue
        return candidates

    def _path_completion_candidates(self, token: str) -> list[str]:
        quote = token[0] if token.startswith(("'", '"')) else ""
        token_body = token[1:] if quote else token
        base_text, name_prefix = self._split_path_token(token_body)
        search_dir = self._completion_search_dir(base_text)
        if search_dir is None:
            return []

        name_prefix_lower = name_prefix.lower()
        candidates: list[str] = []
        try:
            children = list(search_dir.iterdir())
        except OSError:
            return []
        for child in sorted(children, key=lambda item: item.name.lower()):
            if not child.name.lower().startswith(name_prefix_lower):
                continue
            display = base_text + child.name
            try:
                is_dir = child.is_dir()
            except OSError:
                is_dir = False
            if is_dir:
                display += self._path_completion_separator(base_text)
            candidates.append(self._format_path_completion(display, quote))
        return candidates

    def _split_path_token(self, token: str) -> tuple[str, str]:
        separator_index = max(token.rfind("\\"), token.rfind("/"))
        if separator_index >= 0:
            return token[: separator_index + 1], token[separator_index + 1:]
        return "", token

    def _completion_search_dir(self, base_text: str) -> Path | None:
        if not base_text:
            return Path(self._working_directory)
        expanded = Path(os.path.expanduser(base_text))
        if not expanded.is_absolute():
            expanded = Path(self._working_directory) / expanded
        return expanded if expanded.is_dir() else None

    def _path_completion_separator(self, base_text: str) -> str:
        if "/" in base_text and "\\" not in base_text:
            return "/"
        return "\\" if os.name == "nt" else "/"

    def _format_path_completion(self, value: str, quote: str) -> str:
        if quote:
            return quote + value
        if any(character.isspace() for character in value):
            return "'" + value.replace("'", "''") + "'"
        return value

    def _token_looks_like_path(self, token: str) -> bool:
        return (
            token.startswith((".", "~", "/", "\\"))
            or "\\" in token
            or "/" in token
            or ":" in token
        )

    def _apply_completion_candidate(self) -> None:
        candidate = self._completion_candidates[self._completion_index]
        line = self._completion_base_prefix + candidate + self._completion_base_suffix
        cursor_column = len(self._completion_base_prefix) + len(candidate)
        self._terminal_view.set_current_input(line, cursor_column=cursor_column)
        self._completion_current_line = line

    def _reset_completion(self) -> None:
        self._completion_candidates = []
        self._completion_index = -1
        self._completion_base_prefix = ""
        self._completion_base_suffix = ""
        self._completion_current_line = ""

    def _unique_completion_candidates(self, candidates: list[str]) -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = candidate.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(candidate)
        return unique

    def _on_finished(self, exit_code: int, exit_status) -> None:
        self._process = None
        if exit_status == QProcess.ExitStatus.CrashExit:
            message = "Terminal process was terminated.\n"
        else:
            message = f"Terminal exited with code {exit_code}.\n"
        self._terminal_view.append_output(
            message,
            self._stream_format("system"),
            high_contrast=self._is_high_contrast(),
        )

    def _on_error(self, error) -> None:
        error_map = {
            QProcess.ProcessError.FailedToStart:
                "Terminal failed to start - check your shell path.\n",
            QProcess.ProcessError.Crashed: "Terminal process crashed.\n",
            QProcess.ProcessError.Timedout: "Terminal process timed out.\n",
            QProcess.ProcessError.WriteError: "Terminal write failed.\n",
            QProcess.ProcessError.ReadError: "Terminal read failed.\n",
        }
        message = error_map.get(error, f"Terminal error: {error}\n")
        self._terminal_view.append_output(
            message,
            self._stream_format("system"),
            high_contrast=self._is_high_contrast(),
        )

    def _stream_format(self, stream: str) -> QTextCharFormat:
        fmt = QTextCharFormat()
        if self._is_high_contrast():
            fmt.setForeground(QColor("#FFFFFF"))
        elif stream == "stderr":
            fmt.setForeground(QColor("#F44747"))
        elif stream == "system":
            fmt.setForeground(QColor("#6B7280"))
        return fmt

    def _add_history(self, command: str) -> None:
        stripped = command.strip()
        if self._history and self._history[-1] == stripped:
            self._history_index = len(self._history)
            return
        self._history.append(stripped)
        if len(self._history) > 500:
            self._history = self._history[-500:]
        self._history_index = len(self._history)

    def _on_history_previous(self) -> None:
        if not self._history:
            return
        self._reset_completion()
        if self._history_index > 0:
            self._history_index -= 1
        self._terminal_view.set_current_input(self._history[self._history_index])

    def _on_history_next(self) -> None:
        if not self._history:
            return
        self._reset_completion()
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            text = self._history[self._history_index]
        else:
            self._history_index = len(self._history)
            text = ""
        self._terminal_view.set_current_input(text)

    def _make_tool_button(self, icon_name: str, tooltip: str) -> QToolButton:
        button = QToolButton()
        button.setToolTip(tooltip)
        button.setFixedSize(PANEL_TITLE_CONTROL_SIZE, PANEL_TITLE_CONTROL_SIZE)
        button.setIconSize(QSize(PANEL_TITLE_ICON_SIZE, PANEL_TITLE_ICON_SIZE))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(
            """
            QToolButton {
                border: 1px solid transparent;
                border-radius: 3px;
                padding: 3px;
                icon-size: 16px;
            }
            QToolButton:hover {
                background: rgba(128,128,128,0.2);
                border-color: rgba(128,128,128,0.3);
            }
            """
        )
        button.setIcon(load_themed_icon(icon_name, self._current_theme_name()))
        return button

    def _on_visibility_changed(self, visible: bool) -> None:
        if visible and self._auto_start_on_show:
            self.start_shell()

    def _current_theme_name(self) -> str:
        if self._settings is not None:
            return self._settings.get("editor.theme") or ""
        return ""

    def _is_high_contrast(self) -> bool:
        return theme_is_high_contrast(self._current_theme_name())

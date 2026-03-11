"""Interactive Python REPL manager — persistent interpreter subprocess."""

import re

from PyQt6.QtCore import QObject, QProcess, pyqtSignal


# Regex to detect Python interactive prompts written to stderr
_PROMPT_RE = re.compile(r"(>>> |\.\.\. )")

# Regex to detect the Python startup banner (e.g. "Python 3.11.5 ...")
_BANNER_RE = re.compile(r"^Python \d+\.\d+")


class ReplManager(QObject):
    """Manages a persistent interactive Python subprocess.

    Launches ``python -u -i`` and keeps it alive so the user can type
    commands at any time.  Prompts (``>>> `` / ``... ``) are detected
    from stderr and emitted via :pyqtSignal:`prompt_ready` so the UI
    can update the prompt label.
    """

    output_received = pyqtSignal(str, str)   # (text, stream: "stdout"|"stderr"|"system")
    repl_started = pyqtSignal()
    repl_stopped = pyqtSignal()
    prompt_ready = pyqtSignal(str)           # ">>> " or "... "

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process: QProcess | None = None
        self._stderr_buffer: str = ""
        self._banner_done = False

        # Command history
        self._history: list[str] = []
        self._history_index: int = 0
        self._max_history: int = 500

    # ── Properties ──────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return (
            self._process is not None
            and self._process.state() != QProcess.ProcessState.NotRunning
        )

    # ── Public API ──────────────────────────────────────────────────

    def start(self, interpreter: str, working_dir: str) -> None:
        """Start the REPL subprocess."""
        if self.is_running:
            return

        self._banner_done = False
        self._stderr_buffer = ""

        self._process = QProcess(self)
        self._process.setWorkingDirectory(working_dir)
        self._process.setProcessChannelMode(
            QProcess.ProcessChannelMode.SeparateChannels
        )
        self._connect_signals()
        # -u: unbuffered stdout/stderr, -i: interactive mode
        self._process.start(interpreter, ["-u", "-i"])
        self.repl_started.emit()

    def stop(self) -> None:
        """Terminate the REPL process."""
        if not self.is_running:
            return
        self._disconnect_signals()
        self._process.kill()
        self._process.waitForFinished(1000)
        self._process = None
        self.repl_stopped.emit()

    def restart(self, interpreter: str, working_dir: str) -> None:
        """Kill the current REPL and start a fresh one."""
        self.stop()
        self.start(interpreter, working_dir)

    def send_input(self, text: str) -> None:
        """Send a line of input to the REPL."""
        if not self.is_running:
            return
        # Handle multiline paste: split on newlines and send each line
        for line in text.split("\n"):
            self._process.write((line + "\n").encode("utf-8"))

    # ── Command history ─────────────────────────────────────────────

    def add_to_history(self, command: str) -> None:
        """Add a command to the history (deduplicates consecutive entries)."""
        stripped = command.strip()
        if not stripped:
            return
        if self._history and self._history[-1] == stripped:
            # Don't add consecutive duplicates
            self._history_index = len(self._history)
            return
        self._history.append(stripped)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        self._history_index = len(self._history)

    def history_up(self) -> str | None:
        """Move up in history, return the command or None."""
        if not self._history:
            return None
        if self._history_index > 0:
            self._history_index -= 1
        return self._history[self._history_index]

    def history_down(self) -> str | None:
        """Move down in history, return the command or empty string."""
        if not self._history:
            return None
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            return self._history[self._history_index]
        # Past the end → clear input
        self._history_index = len(self._history)
        return ""

    def reset_history_cursor(self) -> None:
        """Reset the history browsing index to the end."""
        self._history_index = len(self._history)

    # ── Internal signal wiring ──────────────────────────────────────

    def _connect_signals(self) -> None:
        p = self._process
        p.readyReadStandardOutput.connect(self._on_stdout)
        p.readyReadStandardError.connect(self._on_stderr)
        p.finished.connect(self._on_finished)
        p.errorOccurred.connect(self._on_error)

    def _disconnect_signals(self) -> None:
        if self._process is None:
            return
        try:
            p = self._process
            p.readyReadStandardOutput.disconnect(self._on_stdout)
            p.readyReadStandardError.disconnect(self._on_stderr)
            p.finished.disconnect(self._on_finished)
            p.errorOccurred.disconnect(self._on_error)
        except (TypeError, RuntimeError):
            pass

    # ── Slots ───────────────────────────────────────────────────────

    def _on_stdout(self) -> None:
        data = self._process.readAllStandardOutput().data()
        text = data.decode("utf-8", errors="replace")
        if text:
            self.output_received.emit(text, "stdout")

    def _on_stderr(self) -> None:
        data = self._process.readAllStandardError().data()
        text = data.decode("utf-8", errors="replace")
        if not text:
            return

        self._stderr_buffer += text
        self._process_stderr_buffer()

    def _process_stderr_buffer(self) -> None:
        """Parse the stderr buffer, separating prompts from error text."""
        buf = self._stderr_buffer

        # Split around prompt markers, keeping them as separate tokens
        parts = _PROMPT_RE.split(buf)

        # Check if buffer ends with an incomplete prompt fragment
        # (e.g., just ">" or ">>" without a trailing space)
        last = parts[-1] if parts else ""
        if last and not last.endswith("\n") and not _PROMPT_RE.match(last):
            # Could be a partial prompt — keep it buffered
            if last in (">", ">>", ".", "..", ". ", ".. "):
                self._stderr_buffer = last
                parts = parts[:-1]
            else:
                self._stderr_buffer = ""
        else:
            self._stderr_buffer = ""

        for part in parts:
            if not part:
                continue

            if part in (">>> ", "... "):
                self._banner_done = True
                self.prompt_ready.emit(part)
            elif not self._banner_done:
                # All pre-prompt stderr is startup banner — show as system
                self.output_received.emit(part, "system")
            elif part.strip():
                self.output_received.emit(part, "stderr")

    def _on_finished(self, exit_code: int, exit_status) -> None:
        self._process = None
        self.repl_stopped.emit()

    def _on_error(self, error) -> None:
        error_map = {
            QProcess.ProcessError.FailedToStart:
                "Python console failed to start — check interpreter path",
            QProcess.ProcessError.Crashed: "Python console crashed",
        }
        msg = error_map.get(error)
        if msg:
            self.output_received.emit(msg, "system")

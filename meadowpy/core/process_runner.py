"""Process execution engine — runs Python scripts via QProcess."""

import os
import tempfile
from pathlib import Path

from PyQt6.QtCore import QObject, QProcess, pyqtSignal


class ProcessRunner(QObject):
    """Asynchronous Python script runner using QProcess."""

    output_received = pyqtSignal(str, str)   # (text, stream: "stdout"|"stderr"|"system")
    process_started = pyqtSignal(str)        # command description
    process_finished = pyqtSignal(int, str)  # (exit_code, description)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process: QProcess | None = None
        self._temp_file: str | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_file(
        self, file_path: str, interpreter: str, working_dir: str
    ) -> None:
        """Run a Python file: ``interpreter -u file_path``."""
        self._start_process(interpreter, ["-u", file_path], working_dir)
        self.process_started.emit(f"Running: {Path(file_path).name}")

    def run_code(
        self, code: str, interpreter: str, working_dir: str
    ) -> None:
        """Run arbitrary Python code via a temporary file."""
        tmp_dir = Path.home() / ".meadowpy" / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(suffix=".py", dir=str(tmp_dir))
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(code)
        self._temp_file = tmp_path
        self._start_process(interpreter, ["-u", tmp_path], working_dir)
        self.process_started.emit("Running selection")

    def send_stdin(self, text: str) -> None:
        """Write text to the running process's stdin."""
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.write(text.encode("utf-8"))

    def stop(self) -> None:
        """Stop the running process immediately."""
        if not self.is_running():
            return
        # On Windows, terminate() and kill() both call TerminateProcess —
        # there is no graceful SIGTERM equivalent. Kill directly.
        self._process.kill()

    def is_running(self) -> bool:
        return (
            self._process is not None
            and self._process.state() != QProcess.ProcessState.NotRunning
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _start_process(
        self, interpreter: str, args: list[str], working_dir: str
    ) -> None:
        """Create a QProcess and start it."""
        if self._process is not None:
            # Disconnect old signals to avoid double-fire
            self._disconnect_signals()
            if self._process.state() != QProcess.ProcessState.NotRunning:
                self._process.kill()
                self._process.waitForFinished(1000)

        self._process = QProcess(self)
        self._process.setWorkingDirectory(working_dir)
        self._process.setProcessChannelMode(
            QProcess.ProcessChannelMode.SeparateChannels
        )
        self._connect_signals()
        self._process.start(interpreter, args)

    def _connect_signals(self) -> None:
        p = self._process
        p.readyReadStandardOutput.connect(self._on_stdout)
        p.readyReadStandardError.connect(self._on_stderr)
        p.finished.connect(self._on_finished)
        p.errorOccurred.connect(self._on_error)

    def _disconnect_signals(self) -> None:
        try:
            p = self._process
            p.readyReadStandardOutput.disconnect(self._on_stdout)
            p.readyReadStandardError.disconnect(self._on_stderr)
            p.finished.disconnect(self._on_finished)
            p.errorOccurred.disconnect(self._on_error)
        except (TypeError, RuntimeError):
            pass

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_stdout(self) -> None:
        data = self._process.readAllStandardOutput().data()
        text = data.decode("utf-8", errors="replace")
        if text:
            self.output_received.emit(text, "stdout")

    def _on_stderr(self) -> None:
        data = self._process.readAllStandardError().data()
        text = data.decode("utf-8", errors="replace")
        if text:
            self.output_received.emit(text, "stderr")

    def _on_finished(self, exit_code: int, exit_status) -> None:
        self._cleanup_temp()
        if exit_status == QProcess.ExitStatus.CrashExit:
            desc = "Process was terminated"
        elif exit_code == 0:
            desc = "Process finished successfully"
        else:
            desc = f"Process exited with code {exit_code}"
        self.process_finished.emit(exit_code, desc)

    def _on_error(self, error) -> None:
        error_map = {
            QProcess.ProcessError.FailedToStart: "Failed to start — check interpreter path",
            QProcess.ProcessError.Crashed: "Process crashed",
            QProcess.ProcessError.Timedout: "Process timed out",
            QProcess.ProcessError.WriteError: "Write error",
            QProcess.ProcessError.ReadError: "Read error",
        }
        msg = error_map.get(error, f"Unknown error ({error})")
        self.output_received.emit(msg, "system")

    def _cleanup_temp(self) -> None:
        """Remove temporary file created by run_code()."""
        if self._temp_file:
            try:
                os.unlink(self._temp_file)
            except OSError:
                pass
            self._temp_file = None

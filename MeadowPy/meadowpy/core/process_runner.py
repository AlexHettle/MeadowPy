"""Process execution engine — runs Python scripts via QProcess."""

import os
import tempfile
from pathlib import Path

from PyQt6.QtCore import QObject, QProcess, pyqtSignal

from meadowpy.constants import CONFIG_DIR_NAME


_TEMP_FILE_PATTERNS = ("tmp*.py", "selection-*.py")


def _selection_temp_dir() -> Path:
    return Path.home() / CONFIG_DIR_NAME / "tmp"


def _unlink_temp_file(path: str | Path) -> bool:
    try:
        Path(path).unlink()
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return True


def sweep_selection_temp_files() -> None:
    """Remove leftover Run Selection temp files from previous app sessions."""
    tmp_dir = _selection_temp_dir()
    try:
        if not tmp_dir.is_dir():
            return
        for pattern in _TEMP_FILE_PATTERNS:
            for path in tmp_dir.glob(pattern):
                if path.is_file():
                    _unlink_temp_file(path)
    except OSError:
        pass


class ProcessRunner(QObject):
    """Asynchronous Python script runner using QProcess."""

    output_received = pyqtSignal(str, str)   # (text, stream: "stdout"|"stderr"|"system")
    process_started = pyqtSignal(str)        # command description
    process_finished = pyqtSignal(int, str)  # (exit_code, description)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process: QProcess | None = None
        self._temp_file: str | None = None
        self._process_description: str | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_file(
        self, file_path: str, interpreter: str, working_dir: str
    ) -> None:
        """Run a Python file: ``interpreter -u file_path``."""
        self._start_process(
            interpreter,
            ["-u", file_path],
            working_dir,
            description=f"Running: {Path(file_path).name}",
        )

    def run_code(
        self, code: str, interpreter: str, working_dir: str
    ) -> None:
        """Run arbitrary Python code via a temporary file."""
        tmp_dir = _selection_temp_dir()
        tmp_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            prefix="selection-",
            suffix=".py",
            dir=str(tmp_dir),
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(code)
        try:
            self._start_process(
                interpreter,
                ["-u", tmp_path],
                working_dir,
                description="Running selection",
                temp_file=tmp_path,
            )
        except Exception:
            if self._temp_file == tmp_path:
                self._cleanup_temp()
            else:
                _unlink_temp_file(tmp_path)
            raise

    def send_stdin(self, text: str) -> None:
        """Write text to the running process's stdin."""
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.write(text.encode("utf-8"))

    def stop(self, timeout_ms: int = 1000) -> None:
        """Stop the running process and wait briefly for Qt to tear it down."""
        if not self.is_running():
            return
        # On Windows, terminate() and kill() both call TerminateProcess —
        # there is no graceful SIGTERM equivalent. Kill directly.
        process = self._process
        process.kill()
        if process.waitForFinished(timeout_ms):
            self._cleanup_temp()

    def is_running(self) -> bool:
        return (
            self._process is not None
            and self._process.state() != QProcess.ProcessState.NotRunning
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _start_process(
        self,
        interpreter: str,
        args: list[str],
        working_dir: str,
        *,
        description: str,
        temp_file: str | None = None,
    ) -> None:
        """Create a QProcess and start it."""
        if self._process is not None:
            # Disconnect old signals to avoid double-fire
            old_process = self._process
            self._disconnect_signals(old_process)
            if old_process.state() != QProcess.ProcessState.NotRunning:
                old_process.kill()
                old_process.waitForFinished(1000)
            self._release_process(old_process)

        self._cleanup_temp()
        self._temp_file = temp_file
        self._process_description = description
        process = QProcess(self)
        self._process = process
        process.setWorkingDirectory(working_dir)
        process.setProcessChannelMode(
            QProcess.ProcessChannelMode.SeparateChannels
        )
        self._connect_signals()
        process.start(interpreter, args)

    def _connect_signals(self) -> None:
        p = self._process
        p.started.connect(self._on_started)
        p.readyReadStandardOutput.connect(self._on_stdout)
        p.readyReadStandardError.connect(self._on_stderr)
        p.finished.connect(self._on_finished)
        p.errorOccurred.connect(self._on_error)

    def _disconnect_signals(self, process=None) -> None:
        p = process if process is not None else self._process
        if p is None:
            return
        connections = (
            (p.started, self._on_started),
            (p.readyReadStandardOutput, self._on_stdout),
            (p.readyReadStandardError, self._on_stderr),
            (p.finished, self._on_finished),
            (p.errorOccurred, self._on_error),
        )
        for signal, slot in connections:
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass

    def _release_process(self, process=None) -> None:
        """Detach and schedule an owned process for event-loop deletion."""
        p = process if process is not None else self._process
        if p is None:
            return
        self._disconnect_signals(p)
        if p is self._process:
            self._process = None
            self._process_description = None
        delete_later = getattr(p, "deleteLater", None)
        if callable(delete_later):
            try:
                delete_later()
            except RuntimeError:
                pass

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_started(self) -> None:
        sender = self.sender()
        if sender is not None and sender is not self._process:
            return
        if self._process_description:
            self.process_started.emit(self._process_description)

    def _on_stdout(self) -> None:
        sender = self.sender()
        if self._process is None or (
            sender is not None and sender is not self._process
        ):
            return
        self._forward_process_output(self._process, "stdout")

    def _on_stderr(self) -> None:
        sender = self.sender()
        if self._process is None or (
            sender is not None and sender is not self._process
        ):
            return
        self._forward_process_output(self._process, "stderr")

    def _forward_process_output(self, process, stream: str) -> None:
        """Drain one process output channel and emit any remaining text."""
        try:
            if stream == "stdout":
                data = process.readAllStandardOutput().data()
            else:
                data = process.readAllStandardError().data()
        except RuntimeError:
            return
        text = data.decode("utf-8", errors="replace")
        if text:
            self.output_received.emit(text, stream)

    def _on_finished(self, exit_code: int, exit_status) -> None:
        sender = self.sender()
        if sender is not None and sender is not self._process:
            return

        process = self._process
        if process is not None:
            self._forward_process_output(process, "stdout")
            self._forward_process_output(process, "stderr")
        self._cleanup_temp()
        if exit_status == QProcess.ExitStatus.CrashExit:
            desc = "Process was terminated"
        elif exit_code == 0:
            desc = "Process finished successfully"
        else:
            desc = f"Process exited with code {exit_code}"
        self._release_process(process)
        self.process_finished.emit(exit_code, desc)

    def _on_error(self, error) -> None:
        sender = self.sender()
        if sender is not None and sender is not self._process:
            return
        error_map = {
            QProcess.ProcessError.FailedToStart: "Failed to start — check interpreter path",
            QProcess.ProcessError.Crashed: "Process crashed",
            QProcess.ProcessError.Timedout: "Process timed out",
            QProcess.ProcessError.WriteError: "Write error",
            QProcess.ProcessError.ReadError: "Read error",
        }
        msg = error_map.get(error, f"Unknown error ({error})")

        # QProcess does not emit ``finished`` when the executable cannot be
        # started. Treat that error as terminal so the UI can restore its run
        # controls and Run Selection can remove its temporary file.
        failed_to_start = error == QProcess.ProcessError.FailedToStart
        if failed_to_start:
            if self._process is not None:
                self._cleanup_temp()
                self._release_process()
                self.process_finished.emit(-1, msg)
            return

        self.output_received.emit(msg, "system")

    def _cleanup_temp(self) -> None:
        """Remove temporary file created by run_code()."""
        if self._temp_file:
            if _unlink_temp_file(self._temp_file):
                self._temp_file = None

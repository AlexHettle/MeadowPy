"""IDE-side debug controller — manages the debug subprocess and TCP protocol."""

import json
import os
from enum import Enum, auto
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QTcpServer, QTcpSocket, QHostAddress
from PyQt6.QtCore import QProcess


class DebugState(Enum):
    """Debugger lifecycle states."""
    IDLE = auto()
    STARTING = auto()   # process launched, waiting for socket connect
    RUNNING = auto()    # script running (not paused)
    PAUSED = auto()     # paused at breakpoint / step
    STOPPING = auto()   # teardown in progress


class DebugManager(QObject):
    """Manages a debug session: launches debug_helper.py, handles TCP comms.

    Signals
    -------
    state_changed(DebugState)
        Emitted whenever the debug lifecycle state changes.
    paused(str, int, dict, list)
        ``(file_path, line_0based, variables_dict, call_stack_list)``
    resumed()
        Script is running again after a pause.
    eval_result(str, str, str)
        ``(expression, result_or_None, error_or_None)``
    debug_output(str, str)
        ``(text, stream)`` — forwarded from QProcess stdout/stderr.
    debug_started(str)
        ``(description)``
    debug_finished(int, str)
        ``(exit_code, description)``
    """

    state_changed = pyqtSignal(object)  # DebugState
    paused = pyqtSignal(str, int, dict, list)
    resumed = pyqtSignal()
    eval_result = pyqtSignal(str, str, str)   # expression, result, error
    debug_output = pyqtSignal(str, str)
    debug_started = pyqtSignal(str)
    debug_finished = pyqtSignal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = DebugState.IDLE
        self._process: QProcess | None = None
        self._server: QTcpServer | None = None
        self._client: QTcpSocket | None = None
        self._recv_buf = bytearray()

        # Pending breakpoints to send once connected
        self._pending_breakpoints: dict[str, list[int]] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> DebugState:
        return self._state

    def _set_state(self, new_state: DebugState) -> None:
        if self._state != new_state:
            self._state = new_state
            self.state_changed.emit(new_state)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_debug(
        self,
        script_path: str,
        interpreter: str,
        working_dir: str,
        breakpoints: dict[str, list[int]] | None = None,
    ) -> None:
        """Launch a debug session.

        Parameters
        ----------
        script_path : str
            Path to the Python file to debug.
        interpreter : str
            Path to the Python interpreter.
        working_dir : str
            Working directory for the subprocess.
        breakpoints : dict, optional
            ``{filepath: [1-based line numbers]}``.
        """
        if self._state not in (DebugState.IDLE,):
            return

        self._pending_breakpoints = breakpoints or {}
        self._set_state(DebugState.STARTING)

        # Start TCP server on an OS-assigned port
        self._server = QTcpServer(self)
        self._server.newConnection.connect(self._on_new_connection)
        if not self._server.listen(QHostAddress.SpecialAddress.LocalHost, 0):
            self._set_state(DebugState.IDLE)
            self.debug_finished.emit(-1, "Failed to start debug server")
            return

        port = self._server.serverPort()

        # Locate the debug_helper.py script (next to this file)
        helper_path = str(Path(__file__).parent / "debug_helper.py")

        # Launch QProcess
        self._process = QProcess(self)
        self._process.setWorkingDirectory(working_dir)
        self._process.setProcessChannelMode(
            QProcess.ProcessChannelMode.SeparateChannels
        )
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_process_finished)
        self._process.errorOccurred.connect(self._on_process_error)

        args = ["-u", helper_path, str(port), script_path]
        self._process.start(interpreter, args)

        self.debug_started.emit(f"Debugging: {Path(script_path).name}")

    def send_continue(self) -> None:
        """Resume execution (run to next breakpoint or end)."""
        self._send_command({"cmd": "continue"})
        self._set_state(DebugState.RUNNING)
        self.resumed.emit()

    def send_step_over(self) -> None:
        """Step over the current line."""
        self._send_command({"cmd": "step_over"})
        self._set_state(DebugState.RUNNING)
        self.resumed.emit()

    def send_step_into(self) -> None:
        """Step into the current line."""
        self._send_command({"cmd": "step_into"})
        self._set_state(DebugState.RUNNING)
        self.resumed.emit()

    def send_step_out(self) -> None:
        """Step out of the current function."""
        self._send_command({"cmd": "step_out"})
        self._set_state(DebugState.RUNNING)
        self.resumed.emit()

    def send_evaluate(self, expression: str, frame_index: int = 0) -> None:
        """Evaluate an expression in the paused frame."""
        self._send_command({
            "cmd": "evaluate",
            "expression": expression,
            "frame_index": frame_index,
        })

    def send_stdin(self, text: str) -> None:
        """Write text to the debug subprocess's stdin (for input() calls)."""
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.write(text.encode("utf-8"))

    def is_running(self) -> bool:
        """Return True if a debug session is active (not IDLE)."""
        return self._state != DebugState.IDLE

    def update_breakpoints(self, breakpoints: dict[str, list[int]]) -> None:
        """Send updated breakpoints to the debug helper.

        ``breakpoints``: ``{filepath: [1-based line numbers]}``.
        """
        self._pending_breakpoints = breakpoints
        if self._client and self._client.state() == QTcpSocket.SocketState.ConnectedState:
            self._send_command({"cmd": "set_breakpoints", "breakpoints": breakpoints})

    def stop_debug(self) -> None:
        """Stop the current debug session."""
        if self._state == DebugState.IDLE:
            return

        self._set_state(DebugState.STOPPING)

        # Try graceful disconnect first
        if self._client and self._client.state() == QTcpSocket.SocketState.ConnectedState:
            try:
                self._send_command({"cmd": "disconnect"})
            except Exception:
                pass

        # Kill process
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
            self._process.waitForFinished(2000)

        self._cleanup()

    # ------------------------------------------------------------------
    # TCP server / socket
    # ------------------------------------------------------------------

    def _on_new_connection(self) -> None:
        """Accept the debug helper's socket connection."""
        self._client = self._server.nextPendingConnection()
        if self._client is None:
            return

        self._client.readyRead.connect(self._on_socket_data)
        self._client.disconnected.connect(self._on_socket_disconnected)
        self._recv_buf.clear()

        # Stop accepting further connections
        self._server.close()

    def _on_socket_data(self) -> None:
        """Read available data from the debug helper socket."""
        data = self._client.readAll().data()
        self._recv_buf.extend(data)

        # Process all complete lines
        while b"\n" in self._recv_buf:
            idx = self._recv_buf.index(b"\n")
            line = self._recv_buf[:idx].decode("utf-8")
            del self._recv_buf[: idx + 1]
            self._handle_message(line)

    def _on_socket_disconnected(self) -> None:
        """Handle debug helper disconnecting.

        The socket disconnects when the script finishes (debug_helper closes
        it in its finally block).  We must NOT call ``_cleanup()`` here because
        that disconnects QProcess signals and kills the process — which loses
        any remaining stdout/stderr that hasn't been read yet.

        Instead, we just tear down the socket and let ``_on_process_finished``
        handle the full cleanup (it drains remaining output first).
        """
        if self._state in (DebugState.IDLE, DebugState.STOPPING):
            return

        # Clean up the socket only — leave QProcess signals intact so
        # _on_process_finished can drain remaining stdout/stderr.
        if self._client:
            try:
                self._client.readyRead.disconnect(self._on_socket_data)
                self._client.disconnected.disconnect(self._on_socket_disconnected)
            except (TypeError, RuntimeError):
                pass
            self._client.close()
            self._client = None

        if self._server:
            self._server.close()
            self._server = None

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------

    def _handle_message(self, line: str) -> None:
        """Parse and dispatch a JSON message from the debug helper."""
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            return

        event = msg.get("event")

        if event == "connected":
            # Always send initial breakpoints (even if empty) —
            # debug_helper blocks waiting for this message.
            self._send_command({
                "cmd": "set_breakpoints",
                "breakpoints": self._pending_breakpoints,
            })
            self._set_state(DebugState.RUNNING)

        elif event == "paused":
            self._set_state(DebugState.PAUSED)
            file_path = msg.get("file", "")
            line_1based = msg.get("line", 1)
            variables = msg.get("variables", {"locals": {}, "globals": {}})
            call_stack = msg.get("call_stack", [])

            # Convert line to 0-based for IDE
            self.paused.emit(file_path, line_1based - 1, variables, call_stack)

        elif event == "eval_result":
            expression = msg.get("expression", "")
            result = msg.get("result")
            error = msg.get("error")
            self.eval_result.emit(
                expression,
                result if result is not None else "",
                error if error is not None else "",
            )

        elif event == "finished":
            # Script ended normally — process will exit soon
            pass

    # ------------------------------------------------------------------
    # QProcess slots
    # ------------------------------------------------------------------

    def _on_stdout(self) -> None:
        data = self._process.readAllStandardOutput().data()
        text = data.decode("utf-8", errors="replace")
        if text:
            self.debug_output.emit(text, "stdout")

    def _on_stderr(self) -> None:
        data = self._process.readAllStandardError().data()
        text = data.decode("utf-8", errors="replace")
        if text:
            self.debug_output.emit(text, "stderr")

    def _on_process_finished(self, exit_code: int, exit_status) -> None:
        # Drain any remaining stdout/stderr BEFORE cleanup disconnects
        # the signals and sets self._process = None.
        if self._process:
            remaining = self._process.readAllStandardOutput().data()
            if remaining:
                text = remaining.decode("utf-8", errors="replace")
                self.debug_output.emit(text, "stdout")
            remaining = self._process.readAllStandardError().data()
            if remaining:
                text = remaining.decode("utf-8", errors="replace")
                self.debug_output.emit(text, "stderr")

        if exit_status == QProcess.ExitStatus.CrashExit:
            desc = "Debug process was terminated"
        elif exit_code == 0:
            desc = "Debug session finished"
        else:
            desc = f"Debug process exited with code {exit_code}"

        self._cleanup()
        self.debug_finished.emit(exit_code, desc)

    def _on_process_error(self, error) -> None:
        error_map = {
            QProcess.ProcessError.FailedToStart: "Failed to start — check interpreter path",
            QProcess.ProcessError.Crashed: "Debug process crashed",
            QProcess.ProcessError.Timedout: "Debug process timed out",
        }
        msg = error_map.get(error, f"Debug error ({error})")
        self.debug_output.emit(msg, "system")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _send_command(self, obj: dict) -> None:
        """Send a JSON command to the debug helper."""
        if self._client and self._client.state() == QTcpSocket.SocketState.ConnectedState:
            data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
            self._client.write(data)
            self._client.flush()

    def _cleanup(self) -> None:
        """Clean up all resources and return to IDLE."""
        if self._client:
            try:
                self._client.readyRead.disconnect(self._on_socket_data)
                self._client.disconnected.disconnect(self._on_socket_disconnected)
            except (TypeError, RuntimeError):
                pass
            self._client.close()
            self._client = None

        if self._server:
            self._server.close()
            self._server = None

        if self._process:
            try:
                self._process.readyReadStandardOutput.disconnect(self._on_stdout)
                self._process.readyReadStandardError.disconnect(self._on_stderr)
                self._process.finished.disconnect(self._on_process_finished)
                self._process.errorOccurred.disconnect(self._on_process_error)
            except (TypeError, RuntimeError):
                pass
            if self._process.state() != QProcess.ProcessState.NotRunning:
                self._process.kill()
                self._process.waitForFinished(1000)
            self._process = None

        self._recv_buf.clear()
        self._set_state(DebugState.IDLE)

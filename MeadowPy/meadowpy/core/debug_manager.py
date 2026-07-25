"""IDE-side debug controller — manages the debug subprocess and TCP protocol."""

import json
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
    breakpoint_update_acknowledged(dict, dict)
        ``(accepted, rejected)`` where accepted is
        ``{path: [1-based lines]}`` and rejected is
        ``{path: {1-based line: human-readable reason}}``.
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
    breakpoint_update_acknowledged = pyqtSignal(dict, dict)
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
        self._process_started_slot = None
        self._pending_debug_description: str | None = None

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
            self._cleanup()
            self.debug_finished.emit(-1, "Failed to start debug server")
            return

        port = self._server.serverPort()

        # Locate the debug_helper.py script (next to this file)
        helper_path = str(Path(__file__).parent / "debug_helper.py")

        # Launch QProcess
        process = QProcess(self)
        self._process = process
        self._pending_debug_description = (
            f"Debugging: {Path(script_path).name}"
        )
        self._process_started_slot = (
            lambda current_process=process: self._on_process_started(
                current_process
            )
        )
        process.setWorkingDirectory(working_dir)
        process.setProcessChannelMode(
            QProcess.ProcessChannelMode.SeparateChannels
        )
        process.started.connect(self._process_started_slot)
        process.readyReadStandardOutput.connect(self._on_stdout)
        process.readyReadStandardError.connect(self._on_stderr)
        process.finished.connect(self._on_process_finished)
        process.errorOccurred.connect(self._on_process_error)

        args = ["-u", helper_path, str(port), script_path]
        process.start(interpreter, args)

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

        # ``waitForFinished`` normally delivers ``finished`` synchronously,
        # and that slot performs the teardown and emits the terminal event.
        # Keep a fallback for backends that stop without delivering it.
        if self._state != DebugState.IDLE:
            self._cleanup()
            self.debug_finished.emit(-1, "Debug process was terminated")

    # ------------------------------------------------------------------
    # TCP server / socket
    # ------------------------------------------------------------------

    def _on_new_connection(self) -> None:
        """Accept the debug helper's socket connection."""
        server = self._server
        if self._signal_sender_is_stale(server):
            return
        if server is None:
            return
        try:
            self._client = server.nextPendingConnection()
        except RuntimeError:
            return
        if self._client is None:
            return

        self._client.readyRead.connect(self._on_socket_data)
        self._client.disconnected.connect(self._on_socket_disconnected)
        self._recv_buf.clear()

        # Stop accepting further connections
        self._server.close()

    def _on_socket_data(self) -> None:
        """Read available data from the debug helper socket."""
        client = self._client
        if self._signal_sender_is_stale(client):
            return
        if client is None:
            return
        try:
            data = client.readAll().data()
        except RuntimeError:
            return
        self._recv_buf.extend(data)

        # Process all complete lines
        while b"\n" in self._recv_buf:
            idx = self._recv_buf.index(b"\n")
            payload = self._recv_buf[:idx]
            del self._recv_buf[: idx + 1]
            try:
                line = payload.decode("utf-8")
            except UnicodeDecodeError:
                continue
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
        if self._signal_sender_is_stale(self._client):
            return
        if self._state in (DebugState.IDLE, DebugState.STOPPING):
            return

        # Clean up the socket only — leave QProcess signals intact so
        # _on_process_finished can drain remaining stdout/stderr.
        client = self._client
        server = self._server
        self._client = None
        self._server = None

        if client:
            try:
                client.readyRead.disconnect(self._on_socket_data)
                client.disconnected.disconnect(self._on_socket_disconnected)
            except (TypeError, RuntimeError):
                pass
            client.close()

        if server:
            server.close()

        self._defer_delete(client, deleting_parent=server)
        self._defer_delete(server)

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------

    def _handle_message(self, line: str) -> None:
        """Parse and dispatch a JSON message from the debug helper."""
        try:
            msg = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            return
        if not isinstance(msg, dict):
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
            file_path = msg.get("file", "")
            line_1based = msg.get("line", 1)
            variables = msg.get("variables", {"locals": {}, "globals": {}})
            call_stack = msg.get("call_stack", [])

            if (
                not isinstance(file_path, str)
                or not file_path
                or not isinstance(line_1based, int)
                or isinstance(line_1based, bool)
                or line_1based < 1
                or not self._valid_variables(variables)
                or not self._valid_call_stack(call_stack)
            ):
                return

            self._set_state(DebugState.PAUSED)

            # Convert line to 0-based for IDE
            self.paused.emit(file_path, line_1based - 1, variables, call_stack)

        elif event == "eval_result":
            expression = msg.get("expression", "")
            result = msg.get("result")
            error = msg.get("error")
            if (
                not isinstance(expression, str)
                or (result is not None and not isinstance(result, str))
                or (error is not None and not isinstance(error, str))
            ):
                return
            self.eval_result.emit(
                expression,
                result if result is not None else "",
                error if error is not None else "",
            )

        elif event == "breakpoints_updated":
            accepted_payload = msg.get("accepted", {})
            rejected_payload = msg.get("rejected", {})
            if not isinstance(accepted_payload, dict) or not isinstance(
                rejected_payload, dict
            ):
                return

            accepted = {
                str(path): [
                    line for line in lines
                    if isinstance(line, int) and not isinstance(line, bool)
                ]
                for path, lines in accepted_payload.items()
                if isinstance(lines, list)
            }
            rejected = {}
            for path, lines in rejected_payload.items():
                if not isinstance(lines, dict):
                    continue
                normalized_lines = {}
                for line, reason in lines.items():
                    try:
                        line_number = int(line)
                    except (TypeError, ValueError):
                        continue
                    normalized_lines[line_number] = str(reason)
                if normalized_lines:
                    rejected[str(path)] = normalized_lines

            self.breakpoint_update_acknowledged.emit(accepted, rejected)

        elif event == "finished":
            # Script ended normally — process will exit soon
            pass

    # ------------------------------------------------------------------
    # QProcess slots
    # ------------------------------------------------------------------

    def _on_process_started(self, process) -> None:
        """Report a start only for the current successfully launched process."""
        if process is not self._process:
            return
        description = self._pending_debug_description
        if description is None or self._state == DebugState.IDLE:
            return
        self._pending_debug_description = None
        self.debug_started.emit(description)

    def _on_stdout(self) -> None:
        process = self._process
        if self._signal_sender_is_stale(process):
            return
        if process is None:
            return
        try:
            data = process.readAllStandardOutput().data()
        except RuntimeError:
            return
        text = data.decode("utf-8", errors="replace")
        if text:
            self.debug_output.emit(text, "stdout")

    def _on_stderr(self) -> None:
        process = self._process
        if self._signal_sender_is_stale(process):
            return
        if process is None:
            return
        try:
            data = process.readAllStandardError().data()
        except RuntimeError:
            return
        text = data.decode("utf-8", errors="replace")
        if text:
            self.debug_output.emit(text, "stderr")

    def _on_process_finished(self, exit_code: int, exit_status) -> None:
        if self._signal_sender_is_stale(self._process):
            return
        # A failed-start error has no process to finish.  Some native backends
        # may nevertheless leave a queued ``finished`` delivery behind; the
        # error handler has already emitted the one terminal event in that
        # case, so ignore the stale callback.
        if self._state == DebugState.IDLE and self._process is None:
            return

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
        if self._signal_sender_is_stale(self._process):
            return
        error_map = {
            QProcess.ProcessError.FailedToStart: "Failed to start — check interpreter path",
            QProcess.ProcessError.Crashed: "Debug process crashed",
            QProcess.ProcessError.Timedout: "Debug process timed out",
        }
        msg = error_map.get(error, f"Debug error ({error})")
        self.debug_output.emit(msg, "system")

        # QProcess does not emit ``finished`` when the executable cannot be
        # started.  Without explicit teardown the debugger stays STARTING and
        # the IDE controls remain disabled indefinitely.
        if error == QProcess.ProcessError.FailedToStart:
            session_is_active = (
                self._state != DebugState.IDLE
                or self._process is not None
                or self._server is not None
                or self._client is not None
            )
            if session_is_active:
                self._cleanup()
                self.debug_finished.emit(-1, msg)

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
        client = self._client
        server = self._server
        process = self._process
        process_started_slot = self._process_started_slot
        self._client = None
        self._server = None
        self._process = None
        self._process_started_slot = None
        self._pending_debug_description = None

        if client:
            try:
                client.readyRead.disconnect(self._on_socket_data)
                client.disconnected.disconnect(self._on_socket_disconnected)
            except (TypeError, RuntimeError):
                pass
            client.close()

        if server:
            server.close()

        if process:
            connections = (
                (process.started, process_started_slot),
                (process.readyReadStandardOutput, self._on_stdout),
                (process.readyReadStandardError, self._on_stderr),
                (process.finished, self._on_process_finished),
                (process.errorOccurred, self._on_process_error),
            )
            for signal, slot in connections:
                if slot is None:
                    continue
                try:
                    signal.disconnect(slot)
                except (TypeError, RuntimeError):
                    pass
            if process.state() != QProcess.ProcessState.NotRunning:
                process.kill()
                process.waitForFinished(1000)

        # A socket accepted by QTcpServer is normally parented to the server;
        # deleting both independently can double-delete native Qt storage.
        self._defer_delete(client, deleting_parent=server)
        self._defer_delete(server)
        self._defer_delete(process)

        self._recv_buf.clear()
        self._set_state(DebugState.IDLE)

    @staticmethod
    def _defer_delete(resource, *, deleting_parent=None) -> None:
        """Schedule one owned Qt resource for safe event-loop deletion."""
        if resource is None:
            return

        if deleting_parent is not None:
            parent = getattr(resource, "parent", None)
            if callable(parent):
                try:
                    if parent() is deleting_parent:
                        return
                except RuntimeError:
                    return

        delete_later = getattr(resource, "deleteLater", None)
        if callable(delete_later):
            try:
                delete_later()
            except RuntimeError:
                pass

    def _signal_sender_is_stale(self, current_resource) -> bool:
        """Return whether a queued Qt signal belongs to an older session."""
        sender = self.sender()
        return sender is not None and sender is not current_resource

    @staticmethod
    def _valid_variables(variables) -> bool:
        """Return whether a pause payload is safe for the variable panel."""
        if not isinstance(variables, dict):
            return False
        for scope_name in ("locals", "globals"):
            scope = variables.get(scope_name, {})
            if not isinstance(scope, dict):
                return False
            if any(
                not isinstance(name, str) or not isinstance(value, str)
                for name, value in scope.items()
            ):
                return False
        return True

    @staticmethod
    def _valid_call_stack(call_stack) -> bool:
        """Return whether a pause payload is safe for the call-stack panel."""
        if not isinstance(call_stack, list):
            return False
        for frame in call_stack:
            if not isinstance(frame, dict):
                return False
            file_path = frame.get("file", "")
            function = frame.get("function", "<unknown>")
            line = frame.get("line", 0)
            if (
                not isinstance(file_path, str)
                or not isinstance(function, str)
                or not isinstance(line, int)
                or isinstance(line, bool)
                or line < 0
            ):
                return False
        return True

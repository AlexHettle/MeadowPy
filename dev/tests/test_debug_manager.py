import json

from PyQt6.QtCore import QProcess as QtQProcess
from PyQt6.QtNetwork import QTcpSocket

from meadowpy.core.debug_manager import DebugManager, DebugState
from tests.helpers import FakeProcess, FakeServer, FakeSocket, SignalRecorder


class DebugProcess(FakeProcess):
    ProcessChannelMode = QtQProcess.ProcessChannelMode
    ExitStatus = QtQProcess.ExitStatus
    ProcessError = QtQProcess.ProcessError
    ProcessState = QtQProcess.ProcessState


def test_start_debug_emits_failure_when_server_cannot_listen(monkeypatch):
    manager = DebugManager()
    finished = SignalRecorder()
    manager.debug_finished.connect(finished)
    monkeypatch.setattr("meadowpy.core.debug_manager.QTcpServer", lambda parent: FakeServer(parent, listen_result=False))

    manager.start_debug("demo.py", "python.exe", "C:/work")

    assert manager.state == DebugState.IDLE
    assert finished.calls == [(-1, "Failed to start debug server")]


def test_start_debug_launches_helper_process(monkeypatch):
    manager = DebugManager()
    started = SignalRecorder()
    manager.debug_started.connect(started)
    created = {}

    def fake_server(parent):
        server = FakeServer(parent, listen_result=True, port=4321)
        created["server"] = server
        return server

    monkeypatch.setattr("meadowpy.core.debug_manager.QTcpServer", fake_server)

    class ProcessFactory(DebugProcess):
        def __init__(self, parent=None):
            super().__init__(parent)
            created["process"] = self

    monkeypatch.setattr("meadowpy.core.debug_manager.QProcess", ProcessFactory)

    manager.start_debug("demo.py", "python.exe", "C:/work")

    assert manager.state == DebugState.STARTING
    assert created["server"].listen_args[1] == 0
    interpreter, args = created["process"].start_args
    assert interpreter == "python.exe"
    assert args[0] == "-u"
    assert args[2] == "4321"
    assert args[3] == "demo.py"
    assert started.calls == [("Debugging: demo.py",)]


def test_connected_message_sends_breakpoints_and_sets_running():
    manager = DebugManager()
    manager._pending_breakpoints = {"demo.py": [3]}
    manager._client = FakeSocket(QTcpSocket.SocketState.ConnectedState)

    manager._handle_message(json.dumps({"event": "connected"}))

    assert manager.state == DebugState.RUNNING
    payload = json.loads(manager._client.written[0].decode("utf-8"))
    assert payload == {"cmd": "set_breakpoints", "breakpoints": {"demo.py": [3]}}


def test_paused_message_emits_zero_based_line():
    manager = DebugManager()
    paused = SignalRecorder()
    manager.paused.connect(paused)

    manager._handle_message(
        json.dumps(
            {
                "event": "paused",
                "file": "demo.py",
                "line": 7,
                "variables": {"locals": {"x": "1"}, "globals": {}},
                "call_stack": [{"file": "demo.py", "line": 7, "function": "main"}],
            }
        )
    )

    assert manager.state == DebugState.PAUSED
    assert paused.calls == [("demo.py", 6, {"locals": {"x": "1"}, "globals": {}}, [{"file": "demo.py", "line": 7, "function": "main"}])]


def test_eval_result_message_normalizes_missing_values():
    manager = DebugManager()
    results = SignalRecorder()
    manager.eval_result.connect(results)

    manager._handle_message(json.dumps({"event": "eval_result", "expression": "x", "result": None, "error": None}))

    assert results.calls == [("x", "", "")]


def test_resume_commands_send_protocol_and_update_state():
    manager = DebugManager()
    manager._state = DebugState.PAUSED
    manager._client = FakeSocket(QTcpSocket.SocketState.ConnectedState)
    resumed = SignalRecorder()
    manager.resumed.connect(resumed)

    manager.send_continue()
    manager.send_step_over()
    manager.send_step_into()
    manager.send_step_out()

    sent = [
        json.loads(payload.decode("utf-8"))["cmd"]
        for payload in manager._client.written
    ]
    assert sent == ["continue", "step_over", "step_into", "step_out"]
    assert manager.state == DebugState.RUNNING
    assert resumed.calls == [(), (), (), ()]


def test_evaluate_and_stdin_forward_to_debug_session():
    manager = DebugManager()
    manager._client = FakeSocket(QTcpSocket.SocketState.ConnectedState)
    manager._process = DebugProcess()
    manager._process.state_value = QtQProcess.ProcessState.Running

    manager.send_evaluate("x + 1", frame_index=2)
    manager.send_stdin("answer\n")

    sent = json.loads(manager._client.written[0].decode("utf-8"))
    assert sent == {"cmd": "evaluate", "expression": "x + 1", "frame_index": 2}
    assert manager._process.written == [b"answer\n"]


def test_update_breakpoints_sends_when_client_is_connected():
    manager = DebugManager()
    manager._client = FakeSocket(QTcpSocket.SocketState.ConnectedState)

    manager.update_breakpoints({"demo.py": [1, 2]})

    sent = json.loads(manager._client.written[0].decode("utf-8"))
    assert sent["cmd"] == "set_breakpoints"
    assert sent["breakpoints"] == {"demo.py": [1, 2]}


def test_new_connection_accepts_socket_and_sends_buffered_messages():
    manager = DebugManager()
    server = FakeServer()
    socket = FakeSocket(QTcpSocket.SocketState.ConnectedState)
    server.next_connection = socket
    manager._server = server
    paused = SignalRecorder()
    manager.paused.connect(paused)

    manager._on_new_connection()
    socket.queue_text(
        json.dumps({
            "event": "paused",
            "file": "demo.py",
            "line": 4,
            "variables": {"locals": {}, "globals": {}},
            "call_stack": [],
        }) + "\n"
    )
    manager._on_socket_data()

    assert server.closed is True
    assert manager._client is socket
    assert paused.calls == [("demo.py", 3, {"locals": {}, "globals": {}}, [])]


def test_socket_disconnect_cleans_socket_without_killing_process():
    manager = DebugManager()
    manager._state = DebugState.RUNNING
    manager._client = FakeSocket(QTcpSocket.SocketState.ConnectedState)
    manager._server = FakeServer()
    manager._process = DebugProcess()

    manager._on_socket_disconnected()

    assert manager._client is None
    assert manager._server is None
    assert manager._process is not None
    assert manager.state == DebugState.RUNNING


def test_stop_debug_disconnects_process_and_cleans_up():
    manager = DebugManager()
    manager._state = DebugState.RUNNING
    manager._client = FakeSocket(QTcpSocket.SocketState.ConnectedState)
    manager._process = DebugProcess()
    manager._process.state_value = QtQProcess.ProcessState.Running
    manager._server = FakeServer()

    manager.stop_debug()

    assert manager.state == DebugState.IDLE
    assert manager._process is None


def test_stdout_and_stderr_are_forwarded():
    manager = DebugManager()
    output = SignalRecorder()
    manager.debug_output.connect(output)
    manager._process = DebugProcess()
    manager._process.stdout_bytes = b"out"
    manager._process.stderr_bytes = b"err"

    manager._on_stdout()
    manager._on_stderr()

    assert output.calls == [("out", "stdout"), ("err", "stderr")]


def test_process_finished_drains_output_and_emits_summary():
    manager = DebugManager()
    output = SignalRecorder()
    finished = SignalRecorder()
    manager.debug_output.connect(output)
    manager.debug_finished.connect(finished)
    manager._process = DebugProcess()
    manager._process.stdout_bytes = b"stdout"
    manager._process.stderr_bytes = b"stderr"

    manager._on_process_finished(0, QtQProcess.ExitStatus.NormalExit)

    assert output.calls == [("stdout", "stdout"), ("stderr", "stderr")]
    assert finished.calls == [(0, "Debug session finished")]
    assert manager.state == DebugState.IDLE


def test_process_finished_reports_nonzero_and_crash_exit():
    manager = DebugManager()
    finished = SignalRecorder()
    manager.debug_finished.connect(finished)
    manager._process = DebugProcess()

    manager._on_process_finished(3, QtQProcess.ExitStatus.NormalExit)
    manager._process = DebugProcess()
    manager._on_process_finished(1, QtQProcess.ExitStatus.CrashExit)

    assert finished.calls == [
        (3, "Debug process exited with code 3"),
        (1, "Debug process was terminated"),
    ]


def test_process_error_emits_system_message():
    manager = DebugManager()
    output = SignalRecorder()
    manager.debug_output.connect(output)

    manager._on_process_error(QtQProcess.ProcessError.FailedToStart)

    assert output.calls
    assert output.calls[0][1] == "system"
    assert "Failed to start" in output.calls[0][0]


def test_cleanup_closes_server_socket_and_running_process():
    manager = DebugManager()
    manager._state = DebugState.RUNNING
    manager._client = FakeSocket(QTcpSocket.SocketState.ConnectedState)
    manager._server = FakeServer()
    manager._process = DebugProcess()
    manager._process.state_value = QtQProcess.ProcessState.Running

    manager._cleanup()

    assert manager.state == DebugState.IDLE
    assert manager._client is None
    assert manager._server is None
    assert manager._process is None

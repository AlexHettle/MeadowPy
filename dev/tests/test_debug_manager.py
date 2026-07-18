import json
import sys
from types import SimpleNamespace

from PyQt6.QtCore import QElapsedTimer, QEvent, QProcess as QtQProcess
from PyQt6.QtNetwork import QTcpSocket

from meadowpy.core.debug_manager import DebugManager, DebugState
from tests.helpers import (
    DummySignal,
    FakeProcess,
    FakeServer,
    FakeSocket,
    SignalRecorder,
)


class DebugProcess(FakeProcess):
    ProcessChannelMode = QtQProcess.ProcessChannelMode
    ExitStatus = QtQProcess.ExitStatus
    ProcessError = QtQProcess.ProcessError
    ProcessState = QtQProcess.ProcessState

    def __init__(self, parent=None):
        super().__init__(parent)
        self.started = DummySignal()


class SenderAwareDebugManager(DebugManager):
    def __init__(self):
        super().__init__()
        self.signal_sender = None

    def sender(self):
        return self.signal_sender


def _wait_until(qapp, predicate, timeout_ms=5_000):
    timer = QElapsedTimer()
    timer.start()
    while not predicate() and timer.elapsed() < timeout_ms:
        qapp.processEvents()
    return predicate()


def _flush_deferred_deletes(qapp):
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()


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
    assert started.calls == []

    created["process"].started.emit()
    created["process"].started.emit()

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


def test_breakpoint_update_acknowledgement_normalizes_wire_line_keys():
    manager = DebugManager()
    acknowledged = SignalRecorder()
    manager.breakpoint_update_acknowledged.connect(acknowledged)

    manager._handle_message(json.dumps({
        "event": "breakpoints_updated",
        "accepted": {"demo.py": [2, 5]},
        "rejected": {
            "demo.py": {
                "9": "Line demo.py:9 does not exist",
            },
        },
    }))

    assert acknowledged.calls == [(
        {"demo.py": [2, 5]},
        {"demo.py": {9: "Line demo.py:9 does not exist"}},
    )]


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


def test_socket_data_ignores_malformed_frames_and_keeps_processing():
    manager = DebugManager()
    manager._state = DebugState.RUNNING
    manager._client = FakeSocket(QTcpSocket.SocketState.ConnectedState)
    paused = SignalRecorder()
    manager.paused.connect(paused)
    valid = json.dumps({
        "event": "paused",
        "file": "demo.py",
        "line": 4,
        "variables": {"locals": {}, "globals": {}},
        "call_stack": [],
    }).encode("utf-8")
    manager._client._buffer = (
        b"\xff\n"
        b"not-json\n"
        b"[]\n"
        b'{"event":"paused","line":"four"}\n'
        + valid
        + b"\n"
    )

    manager._on_socket_data()

    assert paused.calls == [
        ("demo.py", 3, {"locals": {}, "globals": {}}, [])
    ]


def test_protocol_ignores_unsafe_pause_eval_and_breakpoint_containers():
    manager = DebugManager()
    manager._state = DebugState.RUNNING
    paused = SignalRecorder()
    evaluated = SignalRecorder()
    acknowledged = SignalRecorder()
    manager.paused.connect(paused)
    manager.eval_result.connect(evaluated)
    manager.breakpoint_update_acknowledged.connect(acknowledged)

    malformed = [
        {"event": "paused", "file": "demo.py", "line": True},
        {
            "event": "paused",
            "file": "demo.py",
            "line": 1,
            "variables": {"locals": [], "globals": {}},
        },
        {
            "event": "paused",
            "file": "demo.py",
            "line": 1,
            "call_stack": ["not-a-frame"],
        },
        {"event": "eval_result", "expression": "x", "result": []},
        {"event": "breakpoints_updated", "accepted": []},
        {"event": "breakpoints_updated", "rejected": []},
    ]
    for payload in malformed:
        manager._handle_message(json.dumps(payload))

    assert manager.state == DebugState.RUNNING
    assert paused.calls == []
    assert evaluated.calls == []
    assert acknowledged.calls == []


def test_queued_signals_from_old_native_resources_cannot_touch_new_session():
    manager = SenderAwareDebugManager()
    manager._state = DebugState.RUNNING
    current_server = FakeServer()
    current_client = FakeSocket(QTcpSocket.SocketState.ConnectedState)
    current_process = DebugProcess()
    current_process.state_value = QtQProcess.ProcessState.Running
    current_process.stdout_bytes = b"new stdout"
    current_process.stderr_bytes = b"new stderr"
    manager._server = current_server
    manager._client = current_client
    manager._process = current_process
    manager.signal_sender = object()
    output = SignalRecorder()
    finished = SignalRecorder()
    manager.debug_output.connect(output)
    manager.debug_finished.connect(finished)

    manager._on_new_connection()
    manager._on_socket_data()
    manager._on_socket_disconnected()
    manager._on_stdout()
    manager._on_stderr()
    manager._on_process_error(QtQProcess.ProcessError.FailedToStart)
    manager._on_process_finished(1, QtQProcess.ExitStatus.CrashExit)

    assert manager.state == DebugState.RUNNING
    assert manager._server is current_server
    assert manager._client is current_client
    assert manager._process is current_process
    assert current_server.closed is False
    assert current_client.closed is False
    assert current_process.killed is False
    assert output.calls == []
    assert finished.calls == []


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
    finished = SignalRecorder()
    manager.debug_finished.connect(finished)
    manager._state = DebugState.RUNNING
    manager._client = FakeSocket(QTcpSocket.SocketState.ConnectedState)
    manager._process = DebugProcess()
    manager._process.state_value = QtQProcess.ProcessState.Running
    manager._server = FakeServer()

    manager.stop_debug()

    assert manager.state == DebugState.IDLE
    assert manager._process is None
    assert finished.calls == [(-1, "Debug process was terminated")]


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


def test_failed_to_start_cleans_up_and_emits_one_terminal_event():
    manager = DebugManager()
    manager._state = DebugState.STARTING
    manager._server = FakeServer()
    manager._process = DebugProcess()
    output = SignalRecorder()
    finished = SignalRecorder()
    manager.debug_output.connect(output)
    manager.debug_finished.connect(finished)

    manager._on_process_error(QtQProcess.ProcessError.FailedToStart)
    manager._on_process_finished(1, QtQProcess.ExitStatus.CrashExit)
    manager._on_process_error(QtQProcess.ProcessError.FailedToStart)

    assert manager.state == DebugState.IDLE
    assert manager._server is None
    assert manager._client is None
    assert manager._process is None
    assert finished.calls == [(-1, output.calls[0][0])]
    assert len(output.calls) == 2


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


def test_native_qt_sessions_release_children_and_finish_exactly_once(
    qapp,
    tmp_path,
):
    manager = DebugManager()
    finished = SignalRecorder()
    started = SignalRecorder()
    manager.debug_finished.connect(finished)
    manager.debug_started.connect(started)
    script = tmp_path / "debug_lifecycle.py"
    script.write_text("print('done')\n", encoding="utf-8")

    for index in range(3):
        finished.calls.clear()
        started.calls.clear()
        missing = tmp_path / f"missing-python-{index}"
        manager.start_debug(str(script), str(missing), str(tmp_path), {})
        assert _wait_until(qapp, lambda: bool(finished.calls))
        assert manager.state == DebugState.IDLE
        assert len(finished.calls) == 1
        assert started.calls == []
        _flush_deferred_deletes(qapp)
        assert manager.children() == []

    finished.calls.clear()
    started.calls.clear()
    manager.start_debug(str(script), sys.executable, str(tmp_path), {})
    assert _wait_until(qapp, lambda: bool(finished.calls))
    assert manager.state == DebugState.IDLE
    assert finished.calls == [(0, "Debug session finished")]
    assert started.calls == [("Debugging: debug_lifecycle.py",)]
    _flush_deferred_deletes(qapp)
    assert manager.children() == []

    waiting_script = tmp_path / "debug_waiting.py"
    waiting_script.write_text("input('waiting')\n", encoding="utf-8")
    finished.calls.clear()
    started.calls.clear()
    manager.start_debug(
        str(waiting_script),
        sys.executable,
        str(tmp_path),
        {},
    )
    assert _wait_until(qapp, lambda: manager.state == DebugState.RUNNING)
    manager.stop_debug()
    assert manager.state == DebugState.IDLE
    assert len(finished.calls) == 1
    assert started.calls == [("Debugging: debug_waiting.py",)]
    _flush_deferred_deletes(qapp)
    assert manager.children() == []


def test_public_commands_are_safe_when_session_is_idle_or_already_active(monkeypatch):
    manager = DebugManager()
    manager.stop_debug()
    manager.send_stdin("ignored")
    manager.update_breakpoints({"demo.py": [1]})
    assert manager._pending_breakpoints == {"demo.py": [1]}

    manager._state = DebugState.RUNNING
    monkeypatch.setattr(
        "meadowpy.core.debug_manager.QTcpServer",
        lambda parent: (_ for _ in ()).throw(AssertionError("must not start")),
    )
    manager.start_debug("demo.py", "python", ".")
    assert manager.state == DebugState.RUNNING


def test_stop_debug_tolerates_disconnect_errors_and_stopped_process():
    manager = DebugManager()
    manager._state = DebugState.RUNNING
    manager._client = FakeSocket(QTcpSocket.SocketState.ConnectedState)
    manager._process = DebugProcess()
    manager._process.state_value = QtQProcess.ProcessState.NotRunning
    manager._send_command = lambda payload: (_ for _ in ()).throw(RuntimeError("gone"))
    finished = SignalRecorder()
    manager.debug_finished.connect(finished)

    manager.stop_debug()

    assert manager.state == DebugState.IDLE
    assert manager._process is None
    assert finished.calls == [(-1, "Debug process was terminated")]


def test_new_connection_and_socket_reads_cover_missing_native_resources():
    manager = DebugManager()
    manager._server = None
    manager._on_new_connection()

    class BrokenServer:
        def nextPendingConnection(self):
            raise RuntimeError("deleted")

    manager._server = BrokenServer()
    manager._on_new_connection()

    manager._server = FakeServer()
    manager._server.next_connection = None
    manager._on_new_connection()
    assert manager._client is None

    manager._on_socket_data()
    manager._client = SimpleNamespace(
        readAll=lambda: (_ for _ in ()).throw(RuntimeError("deleted"))
    )
    manager._on_socket_data()


def test_socket_disconnect_noops_while_idle_and_handles_deleted_signals():
    manager = DebugManager()
    client = FakeSocket(QTcpSocket.SocketState.ConnectedState)
    manager._client = client
    manager._state = DebugState.IDLE
    manager._on_socket_disconnected()
    assert manager._client is client

    manager._state = DebugState.RUNNING
    client.readyRead.disconnect = lambda callback: (_ for _ in ()).throw(RuntimeError("gone"))
    manager._server = FakeServer()
    manager._on_socket_disconnected()
    assert manager._client is None
    assert manager._server is None


def test_breakpoint_ack_skips_invalid_lines_and_empty_rejections():
    manager = DebugManager()
    acknowledged = SignalRecorder()
    manager.breakpoint_update_acknowledged.connect(acknowledged)
    manager._handle_message(json.dumps({
        "event": "breakpoints_updated",
        "accepted": {"demo.py": [1, True, "2"], "skip.py": "not-list"},
        "rejected": {
            "skip.py": [],
            "demo.py": {"bad": "reason", "4": "valid"},
            "empty.py": {"bad": "reason"},
        },
    }))

    assert acknowledged.calls == [
        ({"demo.py": [1]}, {"demo.py": {4: "valid"}})
    ]


def test_process_callbacks_ignore_missing_resources_and_empty_output():
    manager = DebugManager()
    manager._on_process_started(object())
    manager._on_stdout()
    manager._on_stderr()

    process = DebugProcess()
    manager._process = process
    manager._pending_debug_description = None
    manager._on_process_started(process)
    manager._pending_debug_description = "debugging"
    manager._state = DebugState.IDLE
    manager._on_process_started(process)
    manager._on_stdout()
    manager._on_stderr()


def test_process_callbacks_tolerate_deleted_process_and_unknown_error():
    manager = DebugManager()
    output = SignalRecorder()
    manager.debug_output.connect(output)

    class DeletedProcess:
        def readAllStandardOutput(self):
            raise RuntimeError("deleted")

        def readAllStandardError(self):
            raise RuntimeError("deleted")

    manager._process = DeletedProcess()
    manager._on_stdout()
    manager._on_stderr()
    manager._process = None
    manager._on_process_error(999)
    assert output.calls == [("Debug error (999)", "system")]


def test_send_command_ignores_disconnected_client():
    manager = DebugManager()
    client = FakeSocket(QTcpSocket.SocketState.UnconnectedState)
    manager._client = client
    manager._send_command({"cmd": "continue"})
    assert client.written == []


def test_deferred_delete_handles_parent_ownership_and_deleted_objects():
    parent = object()
    owned = SimpleNamespace(parent=lambda: parent, deleteLater=lambda: (_ for _ in ()).throw(AssertionError("owned")))
    DebugManager._defer_delete(owned, deleting_parent=parent)

    broken_parent = SimpleNamespace(
        parent=lambda: (_ for _ in ()).throw(RuntimeError("deleted")),
        deleteLater=lambda: (_ for _ in ()).throw(AssertionError("deleted")),
    )
    DebugManager._defer_delete(broken_parent, deleting_parent=parent)

    broken_delete = SimpleNamespace(
        deleteLater=lambda: (_ for _ in ()).throw(RuntimeError("deleted"))
    )
    DebugManager._defer_delete(broken_delete)
    DebugManager._defer_delete(None)


def test_protocol_validators_reject_malformed_scope_entries_and_frames():
    assert DebugManager._valid_variables({"locals": {1: "value"}, "globals": {}}) is False
    assert DebugManager._valid_variables({"locals": {"name": 1}, "globals": {}}) is False
    assert DebugManager._valid_call_stack("not-list") is False
    assert DebugManager._valid_call_stack([{"file": 1, "function": "f", "line": 1}]) is False
    assert DebugManager._valid_call_stack([{"file": "x", "function": 1, "line": 1}]) is False
    assert DebugManager._valid_call_stack([{"file": "x", "function": "f", "line": True}]) is False
    assert DebugManager._valid_call_stack([{"file": "x", "function": "f", "line": -1}]) is False

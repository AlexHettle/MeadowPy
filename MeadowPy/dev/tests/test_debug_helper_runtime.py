from __future__ import annotations

import importlib
import inspect
import json
import os
import socket
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

from meadowpy.core import debug_helper


def test_debug_helper_validation_and_protocol_failure_branches(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        debug_helper.os.path,
        "commonpath",
        lambda paths: (_ for _ in ()).throw(ValueError("different drives")),
    )
    assert debug_helper._path_is_within("A:/file", "B:/") is False

    monkeypatch.setattr(
        debug_helper.sysconfig,
        "get_paths",
        lambda: (_ for _ in ()).throw(KeyError("missing")),
    )
    assert debug_helper._interpreter_source_roots() == ((), ())

    syntax_file = tmp_path / "syntax.py"
    syntax_file.write_text("if True print('bad')\n", encoding="utf-8")
    lines, error = debug_helper._collect_executable_lines(str(syntax_file))
    assert lines == set()
    assert "line 1" in error
    lines, error = debug_helper._collect_executable_lines(str(tmp_path / "missing.py"))
    assert lines == set()
    assert "Cannot verify executable lines" in error

    sock = SimpleNamespace()
    debugger = debug_helper.MeadowPyDebugger(sock)
    script = tmp_path / "demo.py"
    script.write_text("value = 1\n", encoding="utf-8")
    monkeypatch.setattr(
        debug_helper,
        "_collect_executable_lines",
        lambda path: ({1}, None),
    )
    monkeypatch.setattr(
        debugger,
        "set_break",
        lambda path, line: (_ for _ in ()).throw(ValueError("bad break")),
    )
    monkeypatch.setattr(
        debug_helper,
        "_send",
        lambda *args: (_ for _ in ()).throw(OSError("gone")),
    )

    accepted, rejected = debugger._update_breakpoints(
        {str(script): ["bad", 0, 1]}
    )
    assert accepted[str(script)] == []
    assert rejected[str(script)]["bad"] == "Line number must be a positive integer"
    assert "Unable to set breakpoint" in rejected[str(script)][1]
    assert debugger._socket_disconnected is True


def test_debug_helper_pause_queue_and_disconnect_branches(monkeypatch):
    sock = SimpleNamespace()
    debugger = debug_helper.MeadowPyDebugger(sock)
    detach_calls = []
    monkeypatch.setattr(debugger, "_detach_debugger", lambda: detach_calls.append(True))
    monkeypatch.setattr(
        debug_helper,
        "_send",
        lambda *args: (_ for _ in ()).throw(OSError("gone")),
    )
    frame = SimpleNamespace(
        f_code=SimpleNamespace(co_filename="demo.py", co_name="demo"),
        f_lineno=4,
        f_locals={},
        f_globals={},
        f_back=None,
    )
    assert debugger._send_pause(frame, "step") is False
    assert detach_calls == [True]

    debugger._socket_disconnected = False
    debugger._command_queue.put({"cmd": "other", "value": 1})
    assert debugger._drain_running_commands() is True
    assert debugger._deferred_messages == [{"cmd": "other", "value": 1}]

    debugger._command_queue.put(debug_helper._SOCKET_DISCONNECTED)
    assert debugger._drain_running_commands() is False
    assert debugger._socket_disconnected is True
    assert len(detach_calls) == 2


def test_debug_helper_frame_filtering_and_bdb_callback_branches(monkeypatch):
    debugger = debug_helper.MeadowPyDebugger(SimpleNamespace())
    calls = []
    monkeypatch.setattr(
        debug_helper.bdb.Bdb,
        "set_return",
        lambda self, frame: calls.append(("return", frame)),
    )
    caller = SimpleNamespace(f_trace=None)
    frame = SimpleNamespace(f_back=caller)
    debugger.set_return(frame)
    assert caller.f_trace == debugger.trace_dispatch
    debugger.set_return(SimpleNamespace(f_back=None))
    assert len(calls) == 2

    monkeypatch.setattr(
        debug_helper.bdb.Bdb,
        "stop_here",
        lambda self, frame: "super-result",
    )
    monkeypatch.setattr(
        debug_helper,
        "_is_runtime_internal_source",
        lambda filename: filename == "stdlib.py",
    )
    library_frame = SimpleNamespace(
        f_globals={"__name__": "library"},
        f_code=SimpleNamespace(co_filename="stdlib.py"),
    )
    debugger.stopframe = None
    assert debugger.stop_here(library_frame) is False
    debugger.stopframe = library_frame
    assert debugger.stop_here(library_frame) == "super-result"
    main_frame = SimpleNamespace(
        f_globals={"__name__": "__main__"},
        f_code=SimpleNamespace(co_filename="stdlib.py"),
    )
    assert debugger.stop_here(main_frame) == "super-result"


def test_debug_helper_line_and_exception_callbacks_cover_resume_paths(monkeypatch):
    debugger = debug_helper.MeadowPyDebugger(SimpleNamespace())
    frame = SimpleNamespace(
        f_code=SimpleNamespace(co_filename="demo.py", co_flags=0),
        f_lineno=7,
        f_globals={"__name__": "__main__"},
    )
    actions = []
    monkeypatch.setattr(debug_helper, "_is_internal_frame", lambda path: False)
    monkeypatch.setattr(debugger, "_has_breakpoint", lambda filename, line: False)
    monkeypatch.setattr(
        debugger,
        "_set_continue_traced",
        lambda: actions.append("continue"),
    )
    monkeypatch.setattr(
        debugger,
        "_send_pause",
        lambda current_frame, reason: actions.append(reason) or False,
    )
    monkeypatch.setattr(
        debugger,
        "_command_loop",
        lambda current_frame: actions.append("loop"),
    )

    debugger._initial_continue = True
    debugger.user_line(frame)
    assert actions == ["continue"]

    debugger._initial_continue = False
    debugger.user_line(frame)
    assert actions[-1] == "step"
    monkeypatch.setattr(debugger, "_has_breakpoint", lambda filename, line: True)
    monkeypatch.setattr(
        debugger,
        "_send_pause",
        lambda current_frame, reason: actions.append(reason) or True,
    )
    debugger.user_line(frame)
    assert actions[-2:] == ["breakpoint", "loop"]

    monkeypatch.setattr(debug_helper, "_is_internal_frame", lambda path: True)
    before = list(actions)
    debugger.user_line(frame)
    assert actions == before

    stopframe = SimpleNamespace(
        f_code=SimpleNamespace(
            co_flags=debug_helper.bdb.GENERATOR_AND_COROUTINE_FLAGS
        )
    )
    debugger.stopframe = stopframe
    monkeypatch.setattr(debug_helper, "_is_internal_frame", lambda path: False)
    monkeypatch.setattr(
        debugger,
        "_send_pause",
        lambda current_frame, reason: actions.append("exception") or True,
    )
    debugger.user_exception(frame, (StopIteration, StopIteration(), None))
    assert actions[-2:] == ["exception", "loop"]
    before = list(actions)
    debugger.user_exception(frame, (ValueError, ValueError(), None))
    assert actions == before


def test_debug_helper_dispatch_receiver_and_protocol_parsing(monkeypatch):
    class ChunkSocket:
        def __init__(self):
            self.chunks = iter((b"bad-json\n[]\n{\"cmd\": \"continue\"}\n", b""))

        def recv(self, size):
            return next(self.chunks)

    debugger = debug_helper.MeadowPyDebugger(ChunkSocket())
    debugger._receive_commands()
    assert debugger._command_queue.get() == {"cmd": "continue"}
    assert debugger._command_queue.get() is debug_helper._SOCKET_DISCONNECTED

    debugger = debug_helper.MeadowPyDebugger(SimpleNamespace())
    debugger._receiver_thread = object()
    debugger._start_command_receiver()
    debugger._receiver_thread = None
    debugger._socket_disconnected = True
    debugger._start_command_receiver()

    results = iter((False, True, True))
    monkeypatch.setattr(debugger, "_drain_running_commands", lambda: next(results))
    monkeypatch.setattr(
        debug_helper.bdb.Bdb,
        "dispatch_line",
        lambda self, frame: "trace",
    )
    frame = SimpleNamespace()
    assert debugger.dispatch_line(frame) is None
    debugger._socket_disconnected = True
    assert debugger.dispatch_line(frame) is None
    debugger._socket_disconnected = False
    assert debugger.dispatch_line(frame) == "trace"


def test_debug_helper_command_loop_disconnect_breakpoints_and_evaluation(monkeypatch):
    debugger = debug_helper.MeadowPyDebugger(SimpleNamespace())
    detached = []
    monkeypatch.setattr(debugger, "_detach_debugger", lambda: detached.append(True))
    monkeypatch.setattr(
        debugger,
        "_update_breakpoints",
        lambda breaks: setattr(debugger, "_socket_disconnected", True),
    )
    debugger._deferred_messages = [{"cmd": "set_breakpoints", "breakpoints": {}}]
    debugger._command_loop(SimpleNamespace())
    assert detached == [True]

    internal = SimpleNamespace(
        f_code=SimpleNamespace(co_filename="internal.py"),
        f_globals={},
        f_locals={},
        f_back=None,
    )
    outer = SimpleNamespace(
        f_code=SimpleNamespace(co_filename="outer.py"),
        f_globals={"value": 3},
        f_locals={},
        f_back=None,
    )
    internal.f_back = outer
    frame = SimpleNamespace(
        f_code=SimpleNamespace(co_filename="demo.py"),
        f_globals={"value": 1},
        f_locals={},
        f_back=internal,
    )
    debugger = debug_helper.MeadowPyDebugger(SimpleNamespace())
    detached = []
    monkeypatch.setattr(debugger, "_detach_debugger", lambda: detached.append(True))
    monkeypatch.setattr(
        debug_helper,
        "_is_internal_frame",
        lambda path: path.endswith("internal.py"),
    )
    monkeypatch.setattr(
        debug_helper,
        "_send",
        lambda *args: (_ for _ in ()).throw(OSError("gone")),
    )
    debugger._deferred_messages = [
        {"cmd": "evaluate", "expression": "value", "frame_index": 2}
    ]
    debugger._command_loop(frame)
    assert debugger._socket_disconnected is True
    assert detached == [True]

    debugger = debug_helper.MeadowPyDebugger(SimpleNamespace())
    detached = []
    monkeypatch.setattr(debugger, "_detach_debugger", lambda: detached.append(True))
    debugger._receiver_thread = object()
    debugger._command_queue.put(debug_helper._SOCKET_DISCONNECTED)
    debugger._command_loop(frame)
    assert detached == [True]

    debugger = debug_helper.MeadowPyDebugger(SimpleNamespace())
    detached = []
    monkeypatch.setattr(debugger, "_detach_debugger", lambda: detached.append(True))
    monkeypatch.setattr(debug_helper, "_recv_line", lambda sock, buf: None)
    debugger._command_loop(frame)
    assert detached == [True]


def test_debug_helper_shutdown_receiver_handles_socket_errors_and_stubborn_thread(
    monkeypatch,
):
    class Receiver:
        def __init__(self, states):
            self.states = iter(states)
            self.joins = []

        def is_alive(self):
            return next(self.states)

        def join(self, timeout):
            self.joins.append(timeout)

    class FailingSocket:
        def shutdown(self, how):
            raise OSError("already closed")

        def close(self):
            raise OSError("already closed")

    debugger = debug_helper.MeadowPyDebugger(FailingSocket())
    assert debugger.shutdown_receiver() is True

    receiver = Receiver((True, True, False))
    debugger._receiver_thread = receiver
    debugger._command_queue.put({"cmd": "ignored"})
    assert debugger.shutdown_receiver(0.25) is True
    assert receiver.joins == [0.25, 0.25]
    assert debugger._receiver_thread is None

    stubborn = Receiver((True, True, True))
    debugger._receiver_thread = stubborn
    assert debugger.shutdown_receiver(0.1) is False
    assert debugger._receiver_thread is stubborn


class CapturingSocket:
    def __init__(self, chunks=None):
        self.chunks = list(chunks or [])
        self.sent = []

    def sendall(self, data):
        self.sent.append(data)

    def recv(self, size):
        if self.chunks:
            return self.chunks.pop(0)
        return b""


def _run_until_two_pauses(
    script,
    execution_globals,
    breakpoints,
    resume_command,
):
    """Run a real debugger session and return its first two pause events."""
    debugger_socket, ide_socket = socket.socketpair()
    ide_socket.settimeout(3)
    debugger = debug_helper.MeadowPyDebugger(debugger_socket)
    debugger._update_breakpoints(breakpoints)
    failures = []

    def run_target():
        try:
            debugger.run(
                compile(
                    script.read_text(encoding="utf-8"),
                    str(script),
                    "exec",
                ),
                execution_globals,
            )
        except Exception as exc:  # pragma: no cover - reported by assertion
            failures.append(exc)

    target_thread = threading.Thread(target=run_target, daemon=True)
    target_thread.start()
    recv_buf = bytearray()

    try:
        acknowledged_line = debug_helper._recv_line(ide_socket, recv_buf)
        first_line = debug_helper._recv_line(ide_socket, recv_buf)
        assert acknowledged_line is not None
        assert first_line is not None

        ide_socket.sendall((json.dumps({
            "cmd": resume_command,
        }) + "\n").encode("utf-8"))
        second_line = debug_helper._recv_line(ide_socket, recv_buf)
        assert second_line is not None

        ide_socket.sendall(b'{"cmd":"continue"}\n')
        target_thread.join(2)
        assert not target_thread.is_alive()
        assert failures == []

        return json.loads(first_line), json.loads(second_line)
    finally:
        if target_thread.is_alive():
            try:
                ide_socket.sendall(b'{"cmd":"disconnect"}\n')
            except OSError:
                pass
            target_thread.join(2)
        debugger.shutdown_receiver()
        debugger.clear_all_breaks()
        ide_socket.close()
        debugger_socket.close()


def _run_helper_subprocess(tmp_path, source):
    """Run the standalone helper over its real TCP/subprocess boundary."""
    script = tmp_path / "subprocess_target.py"
    script.write_text(source, encoding="utf-8")
    helper = os.path.abspath(debug_helper.__file__)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.settimeout(5)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    process = subprocess.Popen(
        [sys.executable, "-u", helper, str(server.getsockname()[1]), str(script)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    connection = None
    try:
        connection, _ = server.accept()
        connection.settimeout(5)
        recv_buf = bytearray()
        connected_line = debug_helper._recv_line(connection, recv_buf)
        assert connected_line is not None
        assert json.loads(connected_line) == {"event": "connected"}

        connection.sendall(b'{"cmd":"set_breakpoints","breakpoints":{}}\n')
        acknowledged_line = debug_helper._recv_line(connection, recv_buf)
        finished_line = debug_helper._recv_line(connection, recv_buf)
        assert acknowledged_line is not None
        assert finished_line is not None
        acknowledged = json.loads(acknowledged_line)
        assert acknowledged == {
            "event": "breakpoints_updated",
            "accepted": {},
            "rejected": {},
        }

        stdout, stderr = process.communicate(timeout=5)
        assert connection.recv(1) == b""
        return process.returncode, json.loads(finished_line), stdout, stderr
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        if connection is not None:
            connection.close()
        server.close()


def test_send_serializes_single_newline_delimited_json_message():
    sock = CapturingSocket()

    debug_helper._send(sock, {"event": "paused", "name": "Ada"})

    assert sock.sent == [b'{"event": "paused", "name": "Ada"}\n']


def test_runtime_internal_source_classification_keeps_packages_user_facing(
    monkeypatch,
    tmp_path,
):
    stdlib_root = tmp_path / "Lib"
    package_root = stdlib_root / "site-packages"
    stdlib_root.mkdir()
    package_root.mkdir()
    monkeypatch.setattr(
        debug_helper,
        "_STDLIB_ROOTS",
        (debug_helper._normalise_source_path(str(stdlib_root)),),
    )
    monkeypatch.setattr(
        debug_helper,
        "_SITE_PACKAGE_ROOTS",
        (debug_helper._normalise_source_path(str(package_root)),),
    )

    assert debug_helper._is_runtime_internal_source(
        "<frozen importlib._bootstrap>"
    ) is True
    assert debug_helper._is_runtime_internal_source(
        str(stdlib_root / "encodings" / "utf_8.py")
    ) is True
    assert debug_helper._is_runtime_internal_source(
        str(package_root / "vendor" / "module.py")
    ) is False
    assert debug_helper._is_runtime_internal_source("<string>") is False


def test_step_into_skips_stdlib_but_enters_user_and_installed_code(
    monkeypatch,
    tmp_path,
):
    stdlib_root = tmp_path / "Lib"
    package_root = stdlib_root / "site-packages"
    project_root = tmp_path / "project"
    package_root.mkdir(parents=True)
    project_root.mkdir()
    monkeypatch.setattr(
        debug_helper,
        "_STDLIB_ROOTS",
        (debug_helper._normalise_source_path(str(stdlib_root)),),
    )
    monkeypatch.setattr(
        debug_helper,
        "_SITE_PACKAGE_ROOTS",
        (debug_helper._normalise_source_path(str(package_root)),),
    )

    def make_function(path, module_name, function_name):
        source = (
            f"def {function_name}():\n"
            "    value = 42\n"
            "    return value\n"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        namespace = {"__name__": module_name, "__file__": str(path)}
        exec(compile(source, str(path), "exec"), namespace)
        return namespace[function_name]

    runtime_file = stdlib_root / "runtime_helper.py"
    user_file = project_root / "user_helper.py"
    package_file = package_root / "vendor" / "package_helper.py"
    runtime_helper = make_function(
        runtime_file,
        "runtime_helper",
        "runtime_helper",
    )
    user_helper = make_function(user_file, "user_helper", "user_helper")
    package_helper = make_function(
        package_file,
        "vendor.package_helper",
        "package_helper",
    )

    runtime_target = project_root / "call_runtime.py"
    runtime_target.write_text(
        "result = runtime_helper()\nfinished = True\n",
        encoding="utf-8",
    )
    first, second = _run_until_two_pauses(
        runtime_target,
        {
            "__name__": "__main__",
            "__file__": str(runtime_target),
            "runtime_helper": runtime_helper,
        },
        {str(runtime_target): [1]},
        "step_into",
    )
    assert (first["file"], first["line"], first["reason"]) == (
        str(runtime_target),
        1,
        "breakpoint",
    )
    assert (second["file"], second["line"], second["reason"]) == (
        str(runtime_target),
        2,
        "step",
    )

    user_target = project_root / "call_user.py"
    user_target.write_text(
        "result = user_helper()\nfinished = True\n",
        encoding="utf-8",
    )
    _, user_pause = _run_until_two_pauses(
        user_target,
        {
            "__name__": "__main__",
            "__file__": str(user_target),
            "user_helper": user_helper,
        },
        {str(user_target): [1]},
        "step_into",
    )
    assert (user_pause["file"], user_pause["line"]) == (str(user_file), 2)

    package_target = project_root / "call_package.py"
    package_target.write_text(
        "result = package_helper()\nfinished = True\n",
        encoding="utf-8",
    )
    _, package_pause = _run_until_two_pauses(
        package_target,
        {
            "__name__": "__main__",
            "__file__": str(package_target),
            "package_helper": package_helper,
        },
        {str(package_target): [1]},
        "step_into",
    )
    assert (package_pause["file"], package_pause["line"]) == (
        str(package_file),
        2,
    )


def test_step_into_real_importlib_call_returns_to_user_code(tmp_path):
    target = tmp_path / "call_importlib.py"
    target.write_text(
        "module = importlib.import_module('math')\nfinished = True\n",
        encoding="utf-8",
    )

    _, second = _run_until_two_pauses(
        target,
        {
            "__name__": "__main__",
            "__file__": str(target),
            "importlib": importlib,
        },
        {str(target): [1]},
        "step_into",
    )

    assert (second["file"], second["line"], second["reason"]) == (
        str(target),
        2,
        "step",
    )


def test_explicit_breakpoint_still_pauses_in_filtered_stdlib(
    monkeypatch,
    tmp_path,
):
    stdlib_root = tmp_path / "Lib"
    project_root = tmp_path / "project"
    stdlib_root.mkdir()
    project_root.mkdir()
    monkeypatch.setattr(
        debug_helper,
        "_STDLIB_ROOTS",
        (debug_helper._normalise_source_path(str(stdlib_root)),),
    )
    monkeypatch.setattr(debug_helper, "_SITE_PACKAGE_ROOTS", ())

    runtime_file = stdlib_root / "runtime_helper.py"
    runtime_source = (
        "def runtime_helper():\n"
        "    value = 42\n"
        "    return value\n"
    )
    runtime_file.write_text(runtime_source, encoding="utf-8")
    namespace = {
        "__name__": "runtime_helper",
        "__file__": str(runtime_file),
    }
    exec(compile(runtime_source, str(runtime_file), "exec"), namespace)

    target = project_root / "call_runtime.py"
    target.write_text(
        "result = runtime_helper()\nfinished = True\n",
        encoding="utf-8",
    )
    _, second = _run_until_two_pauses(
        target,
        {
            "__name__": "__main__",
            "__file__": str(target),
            "runtime_helper": namespace["runtime_helper"],
        },
        {str(target): [1], str(runtime_file): [2]},
        "continue",
    )

    assert (second["file"], second["line"], second["reason"]) == (
        str(runtime_file),
        2,
        "breakpoint",
    )


def test_step_over_from_explicit_stdlib_breakpoint_stays_in_frame(
    monkeypatch,
    tmp_path,
):
    stdlib_root = tmp_path / "Lib"
    project_root = tmp_path / "project"
    stdlib_root.mkdir()
    project_root.mkdir()
    monkeypatch.setattr(
        debug_helper,
        "_STDLIB_ROOTS",
        (debug_helper._normalise_source_path(str(stdlib_root)),),
    )
    monkeypatch.setattr(debug_helper, "_SITE_PACKAGE_ROOTS", ())

    runtime_file = stdlib_root / "runtime_helper.py"
    runtime_source = (
        "def runtime_helper():\n"
        "    value = 1\n"
        "    value += 1\n"
        "    return value\n"
    )
    runtime_file.write_text(runtime_source, encoding="utf-8")
    namespace = {"__name__": "runtime_helper", "__file__": str(runtime_file)}
    exec(compile(runtime_source, str(runtime_file), "exec"), namespace)

    target = project_root / "call_runtime.py"
    target.write_text(
        "result = runtime_helper()\nfinished = True\n",
        encoding="utf-8",
    )
    _, second = _run_until_two_pauses(
        target,
        {
            "__name__": "__main__",
            "__file__": str(target),
            "runtime_helper": namespace["runtime_helper"],
        },
        {str(runtime_file): [2]},
        "step_over",
    )

    assert (second["file"], second["line"], second["reason"]) == (
        str(runtime_file),
        3,
        "step",
    )


def test_step_out_from_callback_pauses_in_immediate_stdlib_caller(
    monkeypatch,
    tmp_path,
):
    stdlib_root = tmp_path / "Lib"
    project_root = tmp_path / "project"
    stdlib_root.mkdir()
    project_root.mkdir()
    monkeypatch.setattr(
        debug_helper,
        "_STDLIB_ROOTS",
        (debug_helper._normalise_source_path(str(stdlib_root)),),
    )
    monkeypatch.setattr(debug_helper, "_SITE_PACKAGE_ROOTS", ())

    callback_file = project_root / "callback.py"
    callback_source = (
        "def callback():\n"
        "    value = 42\n"
        "    return value\n"
    )
    callback_file.write_text(callback_source, encoding="utf-8")
    callback_namespace = {
        "__name__": "callback",
        "__file__": str(callback_file),
    }
    exec(
        compile(callback_source, str(callback_file), "exec"),
        callback_namespace,
    )

    runtime_file = stdlib_root / "runtime_wrapper.py"
    runtime_source = (
        "def runtime_wrapper(callback):\n"
        "    result = callback()\n"
        "    runtime_done = True\n"
        "    return result\n"
    )
    runtime_file.write_text(runtime_source, encoding="utf-8")
    runtime_namespace = {
        "__name__": "runtime_wrapper",
        "__file__": str(runtime_file),
    }
    exec(
        compile(runtime_source, str(runtime_file), "exec"),
        runtime_namespace,
    )

    target = project_root / "call_callback.py"
    target.write_text(
        "result = runtime_wrapper(callback)\nfinished = True\n",
        encoding="utf-8",
    )
    _, second = _run_until_two_pauses(
        target,
        {
            "__name__": "__main__",
            "__file__": str(target),
            "callback": callback_namespace["callback"],
            "runtime_wrapper": runtime_namespace["runtime_wrapper"],
        },
        {str(callback_file): [2]},
        "step_out",
    )

    assert (second["file"], second["line"], second["reason"]) == (
        str(runtime_file),
        3,
        "step",
    )


@pytest.mark.parametrize("resume_command", ["step_over", "step_out"])
def test_generator_completion_step_pauses_in_caller(
    tmp_path,
    resume_command,
):
    target = tmp_path / "generator_step.py"
    target.write_text(
        "def values():\n"
        "    yield 1\n"
        "iterator = values()\n"
        "first = next(iterator)\n"
        "try:\n"
        "    second = next(iterator)\n"
        "except StopIteration:\n"
        "    handled = True\n"
        "done = True\n",
        encoding="utf-8",
    )

    first, second = _run_until_two_pauses(
        target,
        {"__name__": "__main__", "__file__": str(target)},
        {str(target): [2]},
        resume_command,
    )

    assert (first["file"], first["line"], first["reason"]) == (
        str(target),
        2,
        "breakpoint",
    )
    assert (second["file"], second["line"], second["reason"]) == (
        str(target),
        6,
        "step",
    )


def test_step_over_handled_exception_pauses_in_handler_not_on_exception(
    tmp_path,
):
    target = tmp_path / "handled_exception.py"
    target.write_text(
        "try:\n"
        "    raise ValueError('expected')\n"
        "except ValueError:\n"
        "    handled = True\n"
        "done = True\n",
        encoding="utf-8",
    )

    _, second = _run_until_two_pauses(
        target,
        {"__name__": "__main__", "__file__": str(target)},
        {str(target): [2]},
        "step_over",
    )

    assert (second["file"], second["line"], second["reason"]) == (
        str(target),
        3,
        "step",
    )


def test_debugger_updates_breakpoints_and_detects_breakpoint_lines(tmp_path):
    script = tmp_path / "demo.py"
    script.write_text("print('one')\nprint('two')\n", encoding="utf-8")
    debugger = debug_helper.MeadowPyDebugger(CapturingSocket())

    debugger._update_breakpoints({str(script): [2]})

    assert debugger._has_breakpoint(str(script), 2) is True
    assert debugger._has_breakpoint(str(script), 1) is False


def test_debugger_acknowledges_accepted_and_rejected_breakpoints(tmp_path):
    script = tmp_path / "demo.py"
    script.write_text("print('one')\nprint('two')\n", encoding="utf-8")
    sock = CapturingSocket()
    debugger = debug_helper.MeadowPyDebugger(sock)

    accepted, rejected = debugger._update_breakpoints({str(script): [2, 99]})

    assert accepted == {str(script): [2]}
    assert list(rejected) == [str(script)]
    assert list(rejected[str(script)]) == [99]
    assert "does not exist" in rejected[str(script)][99]
    assert debugger._has_breakpoint(str(script), 2) is True
    assert debugger._has_breakpoint(str(script), 99) is False

    payload = json.loads(sock.sent[-1].decode("utf-8"))
    assert payload["event"] == "breakpoints_updated"
    assert payload["accepted"] == {str(script): [2]}
    # JSON object keys are strings on the wire.
    assert "does not exist" in payload["rejected"][str(script)]["99"]


def test_debugger_rejects_comment_and_blank_breakpoint_lines(tmp_path):
    script = tmp_path / "non_executable.py"
    script.write_text(
        "# A comment is a physical but non-executable line.\n"
        "\n"
        "value = 1\n",
        encoding="utf-8",
    )
    debugger = debug_helper.MeadowPyDebugger(CapturingSocket())

    accepted, rejected = debugger._update_breakpoints({
        str(script): [1, 2, 3],
    })

    assert accepted == {str(script): [3]}
    assert rejected == {
        str(script): {
            1: "Line 1 has no executable code",
            2: "Line 2 has no executable code",
        },
    }
    assert debugger._has_breakpoint(str(script), 1) is False
    assert debugger._has_breakpoint(str(script), 2) is False
    assert debugger._has_breakpoint(str(script), 3) is True


def test_debugger_accepts_executable_line_in_nested_code_object(tmp_path):
    script = tmp_path / "nested.py"
    script.write_text(
        "def outer():\n"
        "    def inner():\n"
        "        return 42\n"
        "    return inner()\n",
        encoding="utf-8",
    )
    debugger = debug_helper.MeadowPyDebugger(CapturingSocket())

    accepted, rejected = debugger._update_breakpoints({str(script): [3]})

    assert accepted == {str(script): [3]}
    assert rejected == {}
    assert debugger._has_breakpoint(str(script), 3) is True


def test_debugger_rejects_breakpoints_when_source_cannot_compile(tmp_path):
    script = tmp_path / "syntax_error.py"
    script.write_text("if True print('broken')\n", encoding="utf-8")
    debugger = debug_helper.MeadowPyDebugger(CapturingSocket())

    accepted, rejected = debugger._update_breakpoints({str(script): [1]})

    assert accepted == {str(script): []}
    reason = rejected[str(script)][1]
    assert reason.startswith("Cannot verify executable lines:")
    assert "line 1" in reason
    assert debugger._has_breakpoint(str(script), 1) is False


def test_dispatch_line_consumes_breakpoint_updates_while_running(
    monkeypatch,
    tmp_path,
):
    script = tmp_path / "demo.py"
    script.write_text("value = 1\nvalue = 2\n", encoding="utf-8")
    command = {
        "cmd": "set_breakpoints",
        "breakpoints": {str(script): [2]},
    }
    sock = CapturingSocket()
    debugger = debug_helper.MeadowPyDebugger(sock)
    debugger._command_queue.put(command)
    observed = []

    monkeypatch.setattr(
        debug_helper.bdb.Bdb,
        "dispatch_line",
        lambda self, frame: observed.append(
            self._has_breakpoint(str(script), 2)
        ),
    )

    debugger.dispatch_line(inspect.currentframe())

    assert observed == [True]
    payload = json.loads(sock.sent[-1].decode("utf-8"))
    assert payload == {
        "event": "breakpoints_updated",
        "accepted": {str(script): [2]},
        "rejected": {},
    }


def test_running_debugger_applies_live_breakpoint_and_pauses(tmp_path):
    script = tmp_path / "live_breakpoint.py"
    script.write_text(
        "started.set()\n"
        "while not stop.is_set():\n"
        "    value = 1\n"
        "    value = 2\n",
        encoding="utf-8",
    )
    debugger_socket, ide_socket = socket.socketpair()
    ide_socket.settimeout(3)
    debugger = debug_helper.MeadowPyDebugger(debugger_socket)
    started = threading.Event()
    stop = threading.Event()
    failure = []

    def run_target():
        try:
            debugger.run(
                compile(
                    script.read_text(encoding="utf-8"),
                    str(script),
                    "exec",
                ),
                {
                    "__name__": "__main__",
                    "__file__": str(script),
                    "started": started,
                    "stop": stop,
                },
            )
        except Exception as exc:  # pragma: no cover - reported by assertion
            failure.append(exc)

    target_thread = threading.Thread(target=run_target, daemon=True)
    target_thread.start()

    try:
        assert started.wait(2), "target did not begin running"
        ide_socket.sendall((json.dumps({
            "cmd": "set_breakpoints",
            "breakpoints": {str(script): [4]},
        }) + "\n").encode("utf-8"))

        recv_buf = bytearray()
        acknowledged_line = debug_helper._recv_line(ide_socket, recv_buf)
        paused_line = debug_helper._recv_line(ide_socket, recv_buf)
        assert acknowledged_line is not None
        assert paused_line is not None

        acknowledged = json.loads(acknowledged_line)
        paused = json.loads(paused_line)
        assert acknowledged == {
            "event": "breakpoints_updated",
            "accepted": {str(script): [4]},
            "rejected": {},
        }
        assert paused["event"] == "paused"
        assert paused["reason"] == "breakpoint"
        assert paused["file"] == str(script)
        assert paused["line"] == 4

        stop.set()
        ide_socket.sendall(b'{"cmd":"continue"}\n')
        target_thread.join(2)
        assert not target_thread.is_alive()
        assert failure == []
        receiver = debugger._receiver_thread
        assert receiver is not None
        assert debugger.shutdown_receiver() is True
        assert not receiver.is_alive()
    finally:
        stop.set()
        if target_thread.is_alive():
            try:
                ide_socket.sendall(b'{"cmd":"disconnect"}\n')
            except OSError:
                pass
            target_thread.join(2)
        debugger.shutdown_receiver()
        ide_socket.close()
        debugger_socket.close()


def test_paused_command_loop_applies_breakpoint_update(tmp_path):
    script = tmp_path / "paused_breakpoint.py"
    script.write_text("value = 1\n", encoding="utf-8")
    sock = CapturingSocket([
        (json.dumps({
            "cmd": "set_breakpoints",
            "breakpoints": {str(script): [1]},
        }) + "\n").encode("utf-8"),
        b'{"cmd":"continue"}\n',
    ])
    debugger = debug_helper.MeadowPyDebugger(sock)
    debugger._set_continue_traced = lambda: None

    debugger._command_loop(inspect.currentframe())

    assert debugger._has_breakpoint(str(script), 1) is True
    acknowledged = json.loads(sock.sent[-1].decode("utf-8"))
    assert acknowledged["event"] == "breakpoints_updated"
    assert acknowledged["accepted"] == {str(script): [1]}


def test_paused_command_loop_uses_receiver_queue_as_sole_reader():
    sock = CapturingSocket([b'{"cmd":"disconnect"}\n'])
    debugger = debug_helper.MeadowPyDebugger(sock)
    # A non-None receiver marks the production path.  The command loop must
    # consume its queue and leave the socket/buffer exclusively to that reader.
    debugger._receiver_thread = object()
    debugger._command_queue.put({"cmd": "continue"})
    continued = []
    debugger._set_continue_traced = lambda: continued.append(True)

    debugger._command_loop(inspect.currentframe())

    assert continued == [True]
    assert sock.chunks == [b'{"cmd":"disconnect"}\n']


def test_running_socket_eof_detaches_tracing_and_continues(tmp_path):
    script = tmp_path / "disconnect.py"
    script.write_text(
        "started.set()\n"
        "spins = 0\n"
        "while sys.gettrace() is not None and not force_stop.is_set():\n"
        "    spins += 1\n"
        "result['trace'] = sys.gettrace()\n"
        "completed.set()\n",
        encoding="utf-8",
    )
    debugger_socket, ide_socket = socket.socketpair()
    debugger = debug_helper.MeadowPyDebugger(debugger_socket)
    # Exercise detachment when bdb would ordinarily keep tracing because a
    # registered breakpoint still exists.
    debugger._update_breakpoints({str(script): [5]})
    started = threading.Event()
    completed = threading.Event()
    force_stop = threading.Event()
    result = {}
    failure = []

    def run_target():
        try:
            debugger.run(
                compile(
                    script.read_text(encoding="utf-8"),
                    str(script),
                    "exec",
                ),
                {
                    "__name__": "__main__",
                    "__file__": str(script),
                    "sys": sys,
                    "started": started,
                    "completed": completed,
                    "force_stop": force_stop,
                    "result": result,
                },
            )
        except Exception as exc:  # pragma: no cover - reported by assertion
            failure.append(exc)

    target_thread = threading.Thread(target=run_target, daemon=True)
    target_thread.start()

    try:
        assert started.wait(2), "target did not begin running"
        ide_socket.close()

        assert completed.wait(3), "target did not continue after socket EOF"
        target_thread.join(2)
        assert not target_thread.is_alive()
        assert failure == []
        assert result["trace"] is None
        assert debugger._breakpoints_map == {}
        assert debugger.breaks == {}
        receiver = debugger._receiver_thread
        assert receiver is not None
        assert debugger.shutdown_receiver() is True
        assert not receiver.is_alive()
    finally:
        force_stop.set()
        if target_thread.is_alive():
            target_thread.join(2)
        debugger.shutdown_receiver()
        try:
            ide_socket.close()
        except OSError:
            pass
        debugger_socket.close()


def test_command_loop_handles_evaluate_then_continue():
    sock = CapturingSocket([
        b'{"cmd":"evaluate","expression":"value + 5","frame_index":0}\n',
        b'{"cmd":"continue"}\n',
    ])
    debugger = debug_helper.MeadowPyDebugger(sock)
    continued = []
    debugger._set_continue_traced = lambda: continued.append(True)

    def sample():
        value = 37
        frame = inspect.currentframe()
        debugger._command_loop(frame)

    sample()

    payload = json.loads(sock.sent[0].decode("utf-8"))
    assert payload == {
        "event": "eval_result",
        "expression": "value + 5",
        "result": "42",
        "error": None,
    }
    assert continued == [True]


def test_command_loop_ignores_invalid_json_and_handles_resume_commands():
    commands = [
        ("step_over", "next"),
        ("step_into", "step"),
        ("step_out", "return"),
        ("disconnect", "continue"),
    ]

    for command, expected in commands:
        sock = CapturingSocket([b"not-json\n", f'{{"cmd":"{command}"}}\n'.encode()])
        debugger = debug_helper.MeadowPyDebugger(sock)
        calls = []
        debugger.set_next = lambda frame, calls=calls: calls.append("next")
        debugger.set_step = lambda calls=calls: calls.append("step")
        debugger.set_return = lambda frame, calls=calls: calls.append("return")
        debugger.set_continue = lambda calls=calls: calls.append("continue")

        frame = inspect.currentframe()
        debugger._command_loop(frame)

        assert calls == [expected]


def test_send_pause_emits_variables_and_call_stack():
    sock = CapturingSocket()
    debugger = debug_helper.MeadowPyDebugger(sock)

    def sample():
        local_value = "visible"
        frame = inspect.currentframe()
        debugger._send_pause(frame, "step")

    sample()

    payload = json.loads(sock.sent[0].decode("utf-8"))
    assert payload["event"] == "paused"
    assert payload["reason"] == "step"
    assert payload["variables"]["locals"]["local_value"] == "'visible'"
    assert payload["call_stack"][0]["function"] == "sample"


def test_user_line_initial_continue_skips_until_breakpoint(tmp_path):
    script = tmp_path / "demo.py"
    script.write_text("print('one')\n", encoding="utf-8")
    debugger = debug_helper.MeadowPyDebugger(CapturingSocket())
    pauses = []
    commands = []
    debugger.botframe = None
    debugger._send_pause = lambda frame, reason: (
        pauses.append((frame.f_lineno, reason)) or True
    )
    debugger._command_loop = lambda frame: commands.append(frame.f_lineno)

    def sample():
        frame = inspect.currentframe()
        debugger.user_line(frame)
        norm = os.path.normcase(os.path.abspath(frame.f_code.co_filename))
        debugger._breakpoints_map[norm] = set(range(frame.f_lineno, frame.f_lineno + 6))
        debugger.user_line(frame)

    sample()

    assert len(pauses) == 1
    assert pauses[0][1] == "breakpoint"
    assert commands == [pauses[0][0]]
    assert debugger._initial_continue is False


@pytest.mark.parametrize(
    ("source", "expected_code", "expected_reason", "stderr_text"),
    [
        ("value = 42\n", 0, "completed", ""),
        ("import sys\nsys.exit(7)\n", 7, "system_exit", ""),
        (
            "import sys\nsys.exit('requested exit')\n",
            1,
            "system_exit",
            "requested exit",
        ),
        (
            "raise RuntimeError('boom')\n",
            1,
            "exception",
            "RuntimeError: boom",
        ),
    ],
)
def test_real_helper_subprocess_preserves_target_exit_status(
    tmp_path,
    source,
    expected_code,
    expected_reason,
    stderr_text,
):
    returncode, finished, stdout, stderr = _run_helper_subprocess(
        tmp_path,
        source,
    )

    assert returncode == expected_code
    assert finished == {
        "event": "finished",
        "reason": expected_reason,
        "exit_code": expected_code,
    }
    assert stdout == ""
    if stderr_text:
        assert stderr_text in stderr
    else:
        assert stderr == ""


def test_main_exits_with_usage_when_arguments_are_missing(monkeypatch, capsys):
    monkeypatch.setattr(debug_helper.sys, "argv", ["debug_helper.py"])

    try:
        debug_helper.main()
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("main() should exit for missing arguments")

    assert "Usage: python debug_helper.py" in capsys.readouterr().err


def test_main_exits_when_socket_connection_fails(monkeypatch, capsys):
    class FailingSocket:
        def connect(self, address):
            raise OSError("refused")

    monkeypatch.setattr(debug_helper.sys, "argv", ["debug_helper.py", "4321", "demo.py"])
    monkeypatch.setattr(debug_helper.socket, "socket", lambda *args, **kwargs: FailingSocket())

    try:
        debug_helper.main()
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("main() should exit when it cannot connect")

    assert "cannot connect to IDE on port 4321" in capsys.readouterr().err


def test_main_sets_breakpoints_runs_script_and_sends_finished(monkeypatch, tmp_path):
    script = tmp_path / "target.py"
    script.write_text("value = 42\n", encoding="utf-8")
    sent = []
    debugger_records = []

    class FakeSocket:
        def __init__(self):
            self.connected_to = None
            self.closed = False

        def connect(self, address):
            self.connected_to = address

        def close(self):
            self.closed = True

    class FakeDebugger:
        def __init__(self, sock):
            self.sock = sock
            self._buf = None
            debugger_records.append(("init", sock))

        def _update_breakpoints(self, breakpoints):
            debugger_records.append(("breakpoints", breakpoints))

        def run(self, code, globals_dict):
            debugger_records.append((
                "run",
                globals_dict["__name__"],
                globals_dict["__file__"],
                "value" in code.co_names,
            ))

        def shutdown_receiver(self):
            debugger_records.append(("shutdown_receiver",))
            return True

    fake_socket = FakeSocket()
    monkeypatch.setattr(
        debug_helper.sys,
        "argv",
        ["debug_helper.py", "8765", str(script), "arg1"],
    )
    monkeypatch.setattr(
        debug_helper.socket,
        "socket",
        lambda *args, **kwargs: fake_socket,
    )
    monkeypatch.setattr(
        debug_helper,
        "_send",
        lambda sock, payload: sent.append(payload),
    )
    monkeypatch.setattr(
        debug_helper,
        "_recv_line",
        lambda sock, buf: json.dumps({
            "cmd": "set_breakpoints",
            "breakpoints": {str(script): [1]},
        }),
    )
    monkeypatch.setattr(debug_helper, "MeadowPyDebugger", FakeDebugger)
    old_path = list(sys.path)

    try:
        debug_helper.main()
    finally:
        sys.path[:] = old_path

    assert fake_socket.connected_to == ("127.0.0.1", 8765)
    assert debug_helper.sys.argv == [str(script), "arg1"]
    assert sent == [
        {"event": "connected"},
        {"event": "finished", "reason": "completed", "exit_code": 0},
    ]
    assert debugger_records[1] == ("breakpoints", {str(script): [1]})
    assert debugger_records[2] == ("run", "__main__", str(script), True)
    assert debugger_records[3] == ("shutdown_receiver",)
    assert fake_socket.closed is True


@pytest.mark.parametrize(
    ("initial_line", "outcome", "expected_reason", "expected_code"),
    (
        (
            json.dumps({"cmd": "continue"}),
            debug_helper.bdb.BdbQuit(),
            "debugger_quit",
            0,
        ),
        ("not-json", SystemExit(None), "system_exit", 0),
        (None, SystemExit(7), "system_exit", 7),
        (json.dumps({"cmd": "continue"}), SystemExit("goodbye"), "system_exit", 1),
        (None, RuntimeError("target failed"), "exception", 1),
    ),
)
def test_main_reports_target_exit_variants_and_tolerates_cleanup_errors(
    monkeypatch,
    tmp_path,
    capsys,
    initial_line,
    outcome,
    expected_reason,
    expected_code,
):
    script = tmp_path / "variant.py"
    script.write_text("value = 1\n", encoding="utf-8")
    sent = []

    class CleanupSocket:
        def connect(self, address):
            self.address = address

        def close(self):
            if isinstance(outcome, debug_helper.bdb.BdbQuit):
                raise OSError("already closed")

    class OutcomeDebugger:
        def __init__(self, sock):
            self._buf = None

        def _update_breakpoints(self, breakpoints):
            self.breakpoints = breakpoints

        def run(self, code, globals_dict):
            raise outcome

        def shutdown_receiver(self):
            return True

    def record_send(sock, payload):
        sent.append(payload)
        if payload["event"] == "finished" and isinstance(
            outcome, debug_helper.bdb.BdbQuit
        ):
            raise OSError("peer disconnected")

    monkeypatch.setattr(
        debug_helper.sys,
        "argv",
        ["debug_helper.py", "7654", str(script)],
    )
    monkeypatch.setattr(debug_helper.sys, "path", [])
    monkeypatch.setattr(debug_helper.socket, "socket", lambda *args: CleanupSocket())
    monkeypatch.setattr(debug_helper, "_recv_line", lambda sock, buf: initial_line)
    monkeypatch.setattr(debug_helper, "_send", record_send)
    monkeypatch.setattr(debug_helper, "MeadowPyDebugger", OutcomeDebugger)

    if expected_code:
        with pytest.raises(SystemExit, match=str(expected_code)):
            debug_helper.main()
    else:
        debug_helper.main()

    assert sent[-1] == {
        "event": "finished",
        "reason": expected_reason,
        "exit_code": expected_code,
    }
    if isinstance(outcome, SystemExit) and outcome.code == "goodbye":
        assert "goodbye" in capsys.readouterr().err
    elif isinstance(outcome, RuntimeError):
        assert "target failed" in capsys.readouterr().err

"""Standalone step-debugger helper — spawned by MeadowPy as a subprocess.

Usage::

    python -u debug_helper.py <port> <script.py> [script args ...]

* Connects to the IDE over a TCP socket on ``localhost:<port>``.
* Uses ``bdb.Bdb`` to intercept execution and pause at breakpoints / steps.
* Sends newline-delimited JSON events; receives JSON commands.
* **Zero MeadowPy imports** — this file must work with any Python interpreter.
"""

import bdb
import dis
import functools
import json
import linecache
import os
import queue
import socket
import sys
import sysconfig
import threading
import traceback
import types


# ---------------------------------------------------------------------------
# Protocol helpers
# ---------------------------------------------------------------------------

def _send(sock: socket.socket, obj: dict) -> None:
    """Send a JSON message terminated by newline."""
    data = json.dumps(obj, ensure_ascii=False) + "\n"
    sock.sendall(data.encode("utf-8"))


def _recv_line(sock: socket.socket, buf: bytearray) -> str | None:
    """Block until a full newline-delimited JSON line arrives, or return None on disconnect."""
    while b"\n" not in buf:
        try:
            chunk = sock.recv(4096)
        except OSError:
            return None
        if not chunk:
            return None
        buf.extend(chunk)
    idx = buf.index(b"\n")
    line = buf[:idx].decode("utf-8")
    del buf[: idx + 1]
    return line


# ---------------------------------------------------------------------------
# Variable / stack collection
# ---------------------------------------------------------------------------

_MAX_REPR = 256  # max length for repr() of a single value


def _safe_repr(value) -> str:
    """Return repr(value), truncated to _MAX_REPR chars."""
    try:
        r = repr(value)
    except Exception:
        r = "<error in repr>"
    if len(r) > _MAX_REPR:
        r = r[: _MAX_REPR - 3] + "..."
    return r


def _collect_variables(frame) -> dict:
    """Return ``{"locals": {...}, "globals": {...}}`` for *frame*."""
    local_vars = {}
    for name, val in frame.f_locals.items():
        if name.startswith("__") and name.endswith("__"):
            continue
        local_vars[name] = _safe_repr(val)

    global_vars = {}
    for name, val in frame.f_globals.items():
        if name.startswith("__") and name.endswith("__"):
            continue
        # Skip modules, functions, classes — keep only "simple" globals
        if isinstance(val, type) or callable(val):
            continue
        global_vars[name] = _safe_repr(val)

    return {"locals": local_vars, "globals": global_vars}


def _collect_call_stack(frame) -> list[dict]:
    """Walk *frame.f_back* chain, returning a list of dicts (newest first).

    Each dict: ``{"file": str, "line": int (1-based), "function": str}``.
    Internal frames (this file, bdb, etc.) are filtered out.
    """
    stack = []
    f = frame
    while f is not None:
        filename = os.path.normcase(os.path.abspath(f.f_code.co_filename))
        # Skip debugger internals
        if _is_internal_frame(filename):
            f = f.f_back
            continue
        stack.append({
            "file": f.f_code.co_filename,
            "line": f.f_lineno,             # already 1-based
            "function": f.f_code.co_name,
        })
        f = f.f_back
    return stack


def _is_internal_frame(norm_path: str) -> bool:
    """Return True if *norm_path* belongs to the debugger or stdlib bdb."""
    this_file = os.path.normcase(os.path.abspath(__file__))
    if norm_path == this_file:
        return True
    # Also skip bdb.py itself
    bdb_file = os.path.normcase(os.path.abspath(bdb.__file__))
    if norm_path == bdb_file:
        return True
    return False


def _normalise_source_path(path: str) -> str:
    """Return a stable path for interpreter-owned source classification."""
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def _path_is_within(path: str, root: str) -> bool:
    """Return whether *path* is *root* or one of its descendants."""
    try:
        return os.path.commonpath((path, root)) == root
    except ValueError:
        # Windows paths on different drives do not have a common path.
        return False


def _interpreter_source_roots() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return ``(stdlib roots, installed-package roots)`` for this Python."""
    try:
        paths = sysconfig.get_paths()
    except (AttributeError, KeyError, TypeError, ValueError):
        return (), ()

    def roots_for(*names: str) -> tuple[str, ...]:
        roots = {
            _normalise_source_path(path)
            for name in names
            if (path := paths.get(name))
        }
        return tuple(sorted(roots))

    return (
        roots_for("stdlib", "platstdlib"),
        roots_for("purelib", "platlib"),
    )


_STDLIB_ROOTS, _SITE_PACKAGE_ROOTS = _interpreter_source_roots()


@functools.lru_cache(maxsize=1024)
def _classify_runtime_internal_source(
    filename: str,
    stdlib_roots: tuple[str, ...],
    package_roots: tuple[str, ...],
) -> bool:
    """Classify a source path against immutable interpreter path roots."""
    if filename.startswith("<frozen ") and filename.endswith(">"):
        return True
    if filename.startswith("<") and filename.endswith(">"):
        return False

    path = _normalise_source_path(filename)
    if any(_path_is_within(path, root) for root in package_roots):
        return False
    return any(_path_is_within(path, root) for root in stdlib_roots)


def _is_runtime_internal_source(filename: str) -> bool:
    """Return True for Python's own implementation and standard-library code.

    Installed packages are deliberately excluded even when their
    ``site-packages`` directory sits below the standard-library root.
    """
    return _classify_runtime_internal_source(
        filename,
        _STDLIB_ROOTS,
        _SITE_PACKAGE_ROOTS,
    )


def _safe_evaluate(expression: str, frame) -> dict:
    """Evaluate *expression* in the context of *frame*."""
    try:
        result = eval(expression, frame.f_globals, frame.f_locals)  # noqa: S307
        return {"expression": expression, "result": _safe_repr(result), "error": None}
    except Exception as exc:
        return {"expression": expression, "result": None, "error": str(exc)}


def _collect_executable_lines(filepath: str) -> tuple[set[int], str | None]:
    """Return recursively compiled line starts, or a verification error."""
    try:
        with open(filepath, "r", encoding="utf-8") as source_file:
            source = source_file.read()
        root_code = compile(source, filepath, "exec")
    except SyntaxError as exc:
        detail = exc.msg
        if exc.lineno is not None:
            detail = f"{detail} (line {exc.lineno})"
        return set(), f"Cannot verify executable lines: {detail}"
    except (OSError, OverflowError, UnicodeError, ValueError) as exc:
        return set(), f"Cannot verify executable lines: {exc}"

    executable_lines: set[int] = set()

    def collect(code: types.CodeType) -> None:
        executable_lines.update(
            lineno
            for _, lineno in dis.findlinestarts(code)
            if isinstance(lineno, int) and lineno > 0
        )
        for constant in code.co_consts:
            if isinstance(constant, types.CodeType):
                collect(constant)

    collect(root_code)
    return executable_lines, None


# ---------------------------------------------------------------------------
# Debugger class
# ---------------------------------------------------------------------------

_SOCKET_DISCONNECTED = object()


class MeadowPyDebugger(bdb.Bdb):
    """``bdb.Bdb`` subclass that communicates with the IDE via a socket."""

    def __init__(self, sock: socket.socket):
        super().__init__()
        self._sock = sock
        self._buf = bytearray()
        self._deferred_messages: list[dict] = []
        self._command_queue: queue.SimpleQueue[object] = queue.SimpleQueue()
        self._receiver_thread: threading.Thread | None = None
        self._socket_disconnected = False
        self._breakpoints_map: dict[str, set[int]] = {}  # norm_path → {1-based lines}
        # On initial run, skip to the first breakpoint instead of pausing
        # on line 1.  Cleared once the user issues any step/continue command.
        self._initial_continue = True

    # -- breakpoint management -------------------------------------------------

    def _update_breakpoints(
        self,
        bp_dict: dict[str, list[int]],
    ) -> tuple[dict[str, list[int]], dict[str, dict[int, str]]]:
        """Replace the full breakpoint table.

        ``bp_dict``: ``{filepath: [1-based line numbers]}``.

        Returns ``(accepted, rejected)`` and sends the same information to the
        IDE.  ``bdb.Bdb.set_break`` returns a human-readable error string when
        a line cannot be registered, so only successfully registered lines are
        copied into ``_breakpoints_map``.
        """
        # Clear all existing bdb breakpoints
        self.clear_all_breaks()
        self._breakpoints_map.clear()

        accepted: dict[str, list[int]] = {}
        rejected: dict[str, dict[int, str]] = {}

        for filepath, lines in bp_dict.items():
            accepted_lines: list[int] = []
            rejected_lines: dict[int, str] = {}
            norm = os.path.normcase(os.path.abspath(filepath))
            linecache.checkcache(filepath)
            executable_lines, verification_error = _collect_executable_lines(
                filepath
            )
            for lineno in lines:
                valid_type = isinstance(lineno, int) and not isinstance(
                    lineno, bool
                )
                if not valid_type or lineno < 1:
                    rejected_lines[lineno] = (
                        "Line number must be a positive integer"
                    )
                    continue

                if verification_error is not None:
                    rejected_lines[lineno] = verification_error
                    continue

                if lineno not in executable_lines:
                    if linecache.getline(filepath, lineno):
                        rejected_lines[lineno] = (
                            f"Line {lineno} has no executable code"
                        )
                    else:
                        rejected_lines[lineno] = (
                            f"Line {filepath}:{lineno} does not exist"
                        )
                    continue

                try:
                    error = self.set_break(filepath, lineno)
                except (OSError, TypeError, ValueError) as exc:
                    error = f"Unable to set breakpoint: {exc}"

                if error:
                    rejected_lines[lineno] = str(error)
                elif lineno not in accepted_lines:
                    accepted_lines.append(lineno)

            accepted[filepath] = accepted_lines
            if accepted_lines:
                self._breakpoints_map[norm] = set(accepted_lines)
            if rejected_lines:
                rejected[filepath] = rejected_lines

        try:
            _send(self._sock, {
                "event": "breakpoints_updated",
                "accepted": accepted,
                "rejected": rejected,
            })
        except OSError:
            self._socket_disconnected = True

        return accepted, rejected

    def _has_breakpoint(self, filename: str, lineno: int) -> bool:
        norm = os.path.normcase(os.path.abspath(filename))
        return lineno in self._breakpoints_map.get(norm, set())

    # -- bdb callbacks ---------------------------------------------------------

    def run(self, cmd, globals=None, locals=None):
        """Run target code while a background thread receives IDE commands."""
        self._start_command_receiver()
        return super().run(cmd, globals, locals)

    def set_return(self, frame) -> None:
        """Arm Step Out and ensure a filtered immediate caller is traced."""
        caller = frame.f_back
        if caller is not None:
            # ``bdb.dispatch_call`` may have skipped a runtime-internal caller
            # while continuing toward a user breakpoint.  Reattach its local
            # trace so the explicit Step Out stopframe can actually be seen.
            caller.f_trace = self.trace_dispatch
        super().set_return(frame)

    def stop_here(self, frame) -> bool:
        """Stop in user code by default, while retaining library breakpoints.

        ``bdb`` checks ``break_here()`` separately from this method.  Filtering
        only the ordinary step decision therefore avoids accidental dives into
        Python/stdlib implementation details without making an explicit
        breakpoint in those files ineffective.
        """
        if (
            frame.f_globals.get("__name__") != "__main__"
            and _is_runtime_internal_source(frame.f_code.co_filename)
            and frame is not self.stopframe
        ):
            return False
        return super().stop_here(frame)

    def dispatch_line(self, frame):
        """Drain queued IDE commands before processing each target-code line.

        ``bdb`` invokes this method on the target thread for every traced line,
        including while it is otherwise continuing.  Draining here keeps live
        breakpoint mutation single-threaded.  A newly-added breakpoint takes
        effect before ``bdb`` decides whether the current line should stop.
        """
        if not self._drain_running_commands():
            return None
        trace_function = super().dispatch_line(frame)
        if self._socket_disconnected:
            return None
        return trace_function

    def user_line(self, frame):
        """Called by bdb when the debugger stops at a line."""
        filename = frame.f_code.co_filename
        lineno = frame.f_lineno  # 1-based

        # Skip internal frames
        norm = os.path.normcase(os.path.abspath(filename))
        if _is_internal_frame(norm):
            return

        is_breakpoint = self._has_breakpoint(filename, lineno)

        # On initial run, don't pause unless we hit a breakpoint.
        # This makes F6 behave as "run to first breakpoint" (like VS Code).
        # We set bdb's stop info directly instead of calling set_continue()
        # because set_continue() removes sys.settrace() which can cause
        # output loss on fast-finishing scripts.
        if self._initial_continue and not is_breakpoint:
            self._set_continue_traced()
            return

        # We're pausing — clear the initial-continue flag
        self._initial_continue = False

        reason = "breakpoint" if is_breakpoint else "step"

        if not self._send_pause(frame, reason):
            return
        self._command_loop(frame)

    def user_exception(self, frame, exc_info):
        """Called when an exception propagates to a frame being debugged."""
        # ``bdb`` uses a StopIteration/GeneratorExit in the caller as the
        # completion trap for Step Over / Step Out from a generator or
        # coroutine.  Preserve that stepping contract without enabling a
        # general break-on-exception mode for ordinary user exceptions.
        exception_type = exc_info[0]
        generator_stopframe = (
            self.stopframe is not None
            and frame is not self.stopframe
            and self.stopframe.f_code.co_flags
            & bdb.GENERATOR_AND_COROUTINE_FLAGS
        )
        if (
            not generator_stopframe
            or exception_type not in (StopIteration, GeneratorExit)
        ):
            return

        self._initial_continue = False
        if self._send_pause(frame, "step"):
            self._command_loop(frame)

    # -- pause + command loop --------------------------------------------------

    def _send_pause(self, frame, reason: str) -> bool:
        """Send a ``paused`` event to the IDE."""
        variables = _collect_variables(frame)
        call_stack = _collect_call_stack(frame)
        try:
            _send(self._sock, {
                "event": "paused",
                "reason": reason,
                "file": frame.f_code.co_filename,
                "line": frame.f_lineno,   # 1-based
                "variables": variables,
                "call_stack": call_stack,
            })
        except OSError:
            self._socket_disconnected = True
            self._detach_debugger()
            return False
        return True

    def _set_continue_traced(self) -> None:
        """Continue execution without allowing ``bdb`` to remove tracing.

        The standard ``set_continue()`` disables tracing when no breakpoints
        currently exist.  Keeping the trace installed is what allows the IDE
        to add the first breakpoint while target code is already running.
        """
        self.stopframe = self.botframe
        self.returnframe = None
        self.stoplineno = -1

    def _start_command_receiver(self) -> None:
        """Start the sole socket reader used while target code is running."""
        if self._receiver_thread is not None or self._socket_disconnected:
            return

        self._receiver_thread = threading.Thread(
            target=self._receive_commands,
            name="MeadowPyDebugReceiver",
            daemon=True,
        )
        self._receiver_thread.start()

    def _receive_commands(self) -> None:
        """Read and parse commands, but never mutate ``bdb`` state here."""
        try:
            lines: list[str] = []
            self._take_buffered_lines(lines)
            self._queue_protocol_lines(lines)

            while True:
                chunk = self._sock.recv(4096)
                if not chunk:
                    return

                self._buf.extend(chunk)
                lines = []
                self._take_buffered_lines(lines)
                self._queue_protocol_lines(lines)
        except (OSError, UnicodeDecodeError):
            pass
        finally:
            self._command_queue.put(_SOCKET_DISCONNECTED)

    def _queue_protocol_lines(self, lines: list[str]) -> None:
        """Parse complete protocol lines and enqueue valid JSON messages."""
        for line in lines:
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(msg, dict):
                self._command_queue.put(msg)

    def _drain_running_commands(self) -> bool:
        """Apply queued breakpoint commands without blocking target code.

        The receiver thread only performs socket I/O and JSON parsing.  All
        breakpoint mutations happen here, on the traced target thread.  False
        means the IDE disconnected and tracing has been cleanly detached.
        """
        if self._socket_disconnected:
            self._detach_debugger()
            return False

        # SimpleQueue.empty() is a low-cost in-process check, avoiding the
        # select()/recv() system call that previously ran for every traced line.
        while not self._command_queue.empty():
            msg = self._command_queue.get()

            if msg is _SOCKET_DISCONNECTED:
                self._socket_disconnected = True
                self._detach_debugger()
                return False

            cmd = msg.get("cmd")
            if cmd == "set_breakpoints":
                self._update_breakpoints(msg.get("breakpoints", {}))
                if self._socket_disconnected:
                    self._detach_debugger()
                    return False
            elif cmd == "disconnect":
                self._socket_disconnected = True
                self._detach_debugger()
                return False
            else:
                self._deferred_messages.append(msg)

        return True

    def _detach_debugger(self) -> None:
        """Remove tracing after socket loss while allowing user code to run."""
        self.clear_all_breaks()
        self._breakpoints_map.clear()
        # With no breaks, bdb's set_continue() clears sys.settrace() and all
        # active target-frame trace hooks instead of merely changing stop info.
        self.set_continue()

    def shutdown_receiver(self, timeout: float = 1.0) -> bool:
        """Unblock, join, and close the receiver's socket at session end."""
        receiver = self._receiver_thread
        if receiver is None:
            return True

        self._socket_disconnected = True
        if receiver.is_alive():
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            receiver.join(timeout)

        # Closing is both final cleanup and a fallback unblock for platforms
        # where shutdown alone did not release a native recv() promptly.
        try:
            self._sock.close()
        except OSError:
            pass
        if receiver.is_alive():
            receiver.join(timeout)

        stopped = not receiver.is_alive()
        if stopped:
            while not self._command_queue.empty():
                self._command_queue.get()
            self._receiver_thread = None
        return stopped

    def _take_buffered_lines(self, destination: list[str]) -> None:
        """Move all complete protocol lines from ``_buf`` to *destination*."""
        while b"\n" in self._buf:
            idx = self._buf.index(b"\n")
            destination.append(self._buf[:idx].decode("utf-8"))
            del self._buf[: idx + 1]

    def _command_loop(self, frame) -> None:
        """Block until the IDE sends a resume command."""
        while True:
            if self._deferred_messages:
                msg = self._deferred_messages.pop(0)
            elif self._receiver_thread is not None:
                queued = self._command_queue.get()
                if queued is _SOCKET_DISCONNECTED:
                    self._socket_disconnected = True
                    self._detach_debugger()
                    return
                msg = queued
            else:
                line = _recv_line(self._sock, self._buf)
                if line is None:
                    # Socket closed — abort debugging, let script finish
                    self._socket_disconnected = True
                    self._detach_debugger()
                    return

                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue

            cmd = msg.get("cmd")

            if cmd == "continue":
                self._set_continue_traced()
                return

            elif cmd == "step_over":
                self.set_next(frame)
                return

            elif cmd == "step_into":
                self.set_step()
                return

            elif cmd == "step_out":
                self.set_return(frame)
                return

            elif cmd == "set_breakpoints":
                self._update_breakpoints(msg.get("breakpoints", {}))
                if self._socket_disconnected:
                    self._detach_debugger()
                    return

            elif cmd == "evaluate":
                expr = msg.get("expression", "")
                frame_index = msg.get("frame_index", 0)
                # Walk up frames to find the requested index
                target = frame
                for _ in range(frame_index):
                    if target.f_back is not None:
                        # Skip internal frames while walking
                        candidate = target.f_back
                        while candidate is not None and _is_internal_frame(
                            os.path.normcase(os.path.abspath(candidate.f_code.co_filename))
                        ):
                            candidate = candidate.f_back
                        if candidate is not None:
                            target = candidate
                        else:
                            break
                    else:
                        break
                result = _safe_evaluate(expr, target)
                try:
                    _send(self._sock, {"event": "eval_result", **result})
                except OSError:
                    self._socket_disconnected = True
                    self._detach_debugger()
                    return

            elif cmd == "disconnect":
                self._socket_disconnected = True
                self._detach_debugger()
                return


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python debug_helper.py <port> <script.py> [args ...]",
              file=sys.stderr)
        sys.exit(1)

    port = int(sys.argv[1])
    script = sys.argv[2]
    # Set sys.argv for the target script so it sees its own args
    sys.argv = sys.argv[2:]

    # Connect to the IDE
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect(("127.0.0.1", port))
    except OSError as exc:
        print(f"debug_helper: cannot connect to IDE on port {port}: {exc}",
              file=sys.stderr)
        sys.exit(1)

    _send(sock, {"event": "connected"})

    # Wait for initial breakpoints (IDE sends set_breakpoints before we start)
    buf = bytearray()
    line = _recv_line(sock, buf)
    if line:
        try:
            msg = json.loads(line)
            if msg.get("cmd") == "set_breakpoints":
                # We'll pass them to the debugger below
                initial_breakpoints = msg.get("breakpoints", {})
            else:
                initial_breakpoints = {}
        except json.JSONDecodeError:
            initial_breakpoints = {}
    else:
        initial_breakpoints = {}

    # Create debugger and set initial breakpoints
    debugger = MeadowPyDebugger(sock)
    debugger._buf = buf  # carry over any buffered data
    # Always acknowledge the initial full table, including an empty table.
    debugger._update_breakpoints(initial_breakpoints)

    # Run the target script
    script_path = os.path.abspath(script)
    script_dir = os.path.dirname(script_path)

    # Add script directory to sys.path (like normal Python does)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    exit_code = 0
    finish_reason = "completed"

    try:
        debugger.run(
            compile(open(script_path, "r", encoding="utf-8").read(),
                    script_path, "exec"),
            {"__name__": "__main__",
             "__file__": script_path,
             "__builtins__": __builtins__},
        )
    except bdb.BdbQuit:
        finish_reason = "debugger_quit"
    except SystemExit as exc:
        finish_reason = "system_exit"
        if exc.code is None:
            exit_code = 0
        elif isinstance(exc.code, int):
            exit_code = exc.code
        else:
            # Match Python's command-line behavior for ``sys.exit(value)``:
            # non-integer values are printed and produce status 1.
            print(exc.code, file=sys.stderr)
            exit_code = 1
    except Exception:
        # Let the traceback print to stderr as normal
        traceback.print_exc()
        finish_reason = "exception"
        exit_code = 1
    finally:
        try:
            _send(sock, {
                "event": "finished",
                "reason": finish_reason,
                "exit_code": exit_code,
            })
        except OSError:
            pass
        shutdown_receiver = getattr(debugger, "shutdown_receiver", None)
        if shutdown_receiver is not None:
            shutdown_receiver()
        try:
            sock.close()
        except OSError:
            pass

    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()

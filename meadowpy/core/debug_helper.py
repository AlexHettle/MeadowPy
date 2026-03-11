"""Standalone step-debugger helper — spawned by MeadowPy as a subprocess.

Usage::

    python -u debug_helper.py <port> <script.py> [script args ...]

* Connects to the IDE over a TCP socket on ``localhost:<port>``.
* Uses ``bdb.Bdb`` to intercept execution and pause at breakpoints / steps.
* Sends newline-delimited JSON events; receives JSON commands.
* **Zero MeadowPy imports** — this file must work with any Python interpreter.
"""

import bdb
import json
import os
import socket
import sys
import threading
import traceback


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


def _safe_evaluate(expression: str, frame) -> dict:
    """Evaluate *expression* in the context of *frame*."""
    try:
        result = eval(expression, frame.f_globals, frame.f_locals)  # noqa: S307
        return {"expression": expression, "result": _safe_repr(result), "error": None}
    except Exception as exc:
        return {"expression": expression, "result": None, "error": str(exc)}


# ---------------------------------------------------------------------------
# Debugger class
# ---------------------------------------------------------------------------

class MeadowPyDebugger(bdb.Bdb):
    """``bdb.Bdb`` subclass that communicates with the IDE via a socket."""

    def __init__(self, sock: socket.socket):
        super().__init__()
        self._sock = sock
        self._buf = bytearray()
        self._breakpoints_map: dict[str, set[int]] = {}  # norm_path → {1-based lines}
        self._stepping = False      # True when step-over / step-into / step-out requested
        self._stop_on_next = False   # set by step_over
        self._current_frame = None
        # On initial run, skip to the first breakpoint instead of pausing
        # on line 1.  Cleared once the user issues any step/continue command.
        self._initial_continue = True

    # -- breakpoint management -------------------------------------------------

    def _update_breakpoints(self, bp_dict: dict[str, list[int]]) -> None:
        """Replace the full breakpoint table.

        ``bp_dict``: ``{filepath: [1-based line numbers]}``.
        """
        # Clear all existing bdb breakpoints
        self.clear_all_breaks()
        self._breakpoints_map.clear()

        for filepath, lines in bp_dict.items():
            norm = os.path.normcase(os.path.abspath(filepath))
            self._breakpoints_map[norm] = set(lines)
            for lineno in lines:
                self.set_break(filepath, lineno)

    def _has_breakpoint(self, filename: str, lineno: int) -> bool:
        norm = os.path.normcase(os.path.abspath(filename))
        return lineno in self._breakpoints_map.get(norm, set())

    # -- bdb callbacks ---------------------------------------------------------

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
            self.stopframe = self.botframe
            self.returnframe = None
            self.stoplineno = -1
            return

        # We're pausing — clear the initial-continue flag
        self._initial_continue = False

        reason = "breakpoint" if is_breakpoint else "step"

        self._current_frame = frame
        self._send_pause(frame, reason)
        self._command_loop(frame)

    def user_exception(self, frame, exc_info):
        """Called when an exception propagates to a frame being debugged."""
        # Let the exception propagate normally — don't block on it.
        pass

    # -- pause + command loop --------------------------------------------------

    def _send_pause(self, frame, reason: str) -> None:
        """Send a ``paused`` event to the IDE."""
        variables = _collect_variables(frame)
        call_stack = _collect_call_stack(frame)
        _send(self._sock, {
            "event": "paused",
            "reason": reason,
            "file": frame.f_code.co_filename,
            "line": frame.f_lineno,   # 1-based
            "variables": variables,
            "call_stack": call_stack,
        })

    def _command_loop(self, frame) -> None:
        """Block until the IDE sends a resume command."""
        while True:
            line = _recv_line(self._sock, self._buf)
            if line is None:
                # Socket closed — abort debugging, let script finish
                self.set_continue()
                return

            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            cmd = msg.get("cmd")

            if cmd == "continue":
                self.set_continue()
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
                _send(self._sock, {"event": "eval_result", **result})

            elif cmd == "disconnect":
                self.set_continue()
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
    if initial_breakpoints:
        debugger._update_breakpoints(initial_breakpoints)

    # Run the target script
    script_path = os.path.abspath(script)
    script_dir = os.path.dirname(script_path)

    # Add script directory to sys.path (like normal Python does)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    try:
        debugger.run(
            compile(open(script_path, "r", encoding="utf-8").read(),
                    script_path, "exec"),
            {"__name__": "__main__",
             "__file__": script_path,
             "__builtins__": __builtins__},
        )
    except bdb.BdbQuit:
        pass
    except SystemExit:
        pass
    except Exception:
        # Let the traceback print to stderr as normal
        traceback.print_exc()
    finally:
        try:
            _send(sock, {"event": "finished", "reason": "completed"})
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass


if __name__ == "__main__":
    main()

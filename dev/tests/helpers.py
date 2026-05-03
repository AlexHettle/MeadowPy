from __future__ import annotations


class SignalRecorder:
    def __init__(self):
        self.calls: list[tuple] = []

    def __call__(self, *args):
        self.calls.append(args)


class DummySignal:
    def __init__(self):
        self._callbacks: list = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def disconnect(self, callback):
        try:
            self._callbacks.remove(callback)
        except ValueError:
            raise TypeError("callback not connected") from None

    def emit(self, *args):
        for callback in list(self._callbacks):
            callback(*args)


class DummyKeyEvent:
    def __init__(self, text: str, matches: set | None = None):
        self._text = text
        self._matches = matches or set()
        self.accepted = False

    def text(self) -> str:
        return self._text

    def matches(self, key) -> bool:
        return key in self._matches

    def accept(self) -> None:
        self.accepted = True


class DummyEditor:
    def __init__(self, text: str = ""):
        self._lines = text.split("\n") if text else [""]
        self._cursor = (0, 0)
        self._selected = False
        self.selection = None

    def hasSelectedText(self) -> bool:
        return self._selected

    def set_selected(self, value: bool) -> None:
        self._selected = value

    def getCursorPosition(self) -> tuple[int, int]:
        return self._cursor

    def setCursorPosition(self, line: int, col: int) -> None:
        self._cursor = (line, col)

    def text(self, line: int) -> str:
        return self._lines[line]

    def insert(self, text: str) -> None:
        line, col = self._cursor
        current = self._lines[line]
        combined = current[:col] + text + current[col:]
        parts = combined.split("\n")
        self._lines[line : line + 1] = parts

    def setSelection(self, line_from: int, col_from: int, line_to: int, col_to: int) -> None:
        self.selection = (line_from, col_from, line_to, col_to)
        self._selected = True

    def removeSelectedText(self) -> None:
        line_from, col_from, line_to, col_to = self.selection
        if line_from != line_to:
            raise NotImplementedError("DummyEditor only supports single-line selections")
        current = self._lines[line_from]
        self._lines[line_from] = current[:col_from] + current[col_to:]
        self._cursor = (line_from, col_from)
        self._selected = False
        self.selection = None

    def all_text(self) -> str:
        return "\n".join(self._lines)


class FakeByteArray:
    def __init__(self, payload: bytes):
        self._payload = payload

    def data(self) -> bytes:
        return self._payload


class FakeProcess:
    class _State:
        NotRunning = 0
        Running = 1

    def __init__(self, parent=None):
        self.parent = parent
        self.state_value = self._State.NotRunning
        self.stdout_bytes = b""
        self.stderr_bytes = b""
        self.written: list[bytes] = []
        self.killed = False
        self.wait_calls: list[int] = []
        self.start_args = None
        self.working_directory = None
        self.channel_mode = None
        self.readyReadStandardOutput = DummySignal()
        self.readyReadStandardError = DummySignal()
        self.finished = DummySignal()
        self.errorOccurred = DummySignal()

    def setWorkingDirectory(self, directory: str) -> None:
        self.working_directory = directory

    def setProcessChannelMode(self, mode) -> None:
        self.channel_mode = mode

    def start(self, interpreter: str, args: list[str]) -> None:
        self.start_args = (interpreter, args)
        self.state_value = self._State.Running

    def state(self):
        return self.state_value

    def write(self, data: bytes) -> None:
        self.written.append(data)

    def kill(self) -> None:
        self.killed = True
        self.state_value = self._State.NotRunning

    def waitForFinished(self, timeout: int) -> bool:
        self.wait_calls.append(timeout)
        self.state_value = self._State.NotRunning
        return True

    def readAllStandardOutput(self):
        data = self.stdout_bytes
        self.stdout_bytes = b""
        return FakeByteArray(data)

    def readAllStandardError(self):
        data = self.stderr_bytes
        self.stderr_bytes = b""
        return FakeByteArray(data)


class FakeSocket:
    def __init__(self, connected_state):
        self.connected_state = connected_state
        self.state_value = connected_state
        self.readyRead = DummySignal()
        self.disconnected = DummySignal()
        self._buffer = b""
        self.written: list[bytes] = []
        self.closed = False
        self.flushed = False

    def state(self):
        return self.state_value

    def queue_text(self, text: str) -> None:
        self._buffer += text.encode("utf-8")

    def readAll(self):
        data = self._buffer
        self._buffer = b""
        return FakeByteArray(data)

    def write(self, data: bytes) -> None:
        self.written.append(data)

    def flush(self) -> None:
        self.flushed = True

    def close(self) -> None:
        self.closed = True
        self.state_value = None


class FakeServer:
    def __init__(self, parent=None, listen_result: bool = True, port: int = 8765):
        self.parent = parent
        self.listen_result = listen_result
        self.port = port
        self.newConnection = DummySignal()
        self.next_connection = None
        self.closed = False
        self.listen_args = None

    def listen(self, host, port: int) -> bool:
        self.listen_args = (host, port)
        return self.listen_result

    def serverPort(self) -> int:
        return self.port

    def close(self) -> None:
        self.closed = True

    def nextPendingConnection(self):
        return self.next_connection


class FakeThread:
    def __init__(self, running: bool = True, wait_result: bool = True):
        self._running = running
        self.wait_result = wait_result
        self.started = DummySignal()
        self.finished = DummySignal()
        self.quit_called = 0
        self.wait_calls: list[int] = []
        self.terminate_called = 0
        self.start_called = 0

    def isRunning(self) -> bool:
        return self._running

    def quit(self) -> None:
        self.quit_called += 1
        self._running = False

    def wait(self, timeout: int) -> bool:
        self.wait_calls.append(timeout)
        return self.wait_result

    def terminate(self) -> None:
        self.terminate_called += 1
        self._running = False

    def start(self) -> None:
        self.start_called += 1
        self._running = True
        self.started.emit()

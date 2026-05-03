import inspect

from meadowpy.core import debug_helper

MODULE_LEVEL_SAMPLE = "visible"


class BadRepr:
    def __repr__(self):
        raise RuntimeError("broken repr")


class FakeSocket:
    def __init__(self, chunks, fail=False):
        self._chunks = list(chunks)
        self._fail = fail

    def recv(self, size):
        if self._fail:
            raise OSError("socket closed")
        if self._chunks:
            return self._chunks.pop(0)
        return b""


def test_safe_repr_truncates_and_handles_errors():
    long_text = "x" * 300

    assert debug_helper._safe_repr(long_text).endswith("...")
    assert debug_helper._safe_repr(BadRepr()) == "<error in repr>"


def test_collect_variables_filters_dunders_callables_and_types():
    def sample():
        local_value = 10
        hidden__ = 99
        global MODULE_LEVEL_SAMPLE
        frame = inspect.currentframe()
        return debug_helper._collect_variables(frame)

    variables = sample()

    assert variables["locals"]["local_value"] == "10"
    assert "hidden__" in variables["locals"]
    assert variables["globals"]["MODULE_LEVEL_SAMPLE"] == "'visible'"
    assert "_collect_variables" not in variables["globals"]


def test_collect_call_stack_returns_user_frames():
    def outer():
        def inner():
            frame = inspect.currentframe()
            return debug_helper._collect_call_stack(frame)

        return inner()

    stack = outer()

    assert stack[0]["function"] == "inner"
    assert all(entry["file"] != debug_helper.__file__ for entry in stack)


def test_safe_evaluate_returns_success_and_error():
    def sample():
        value = 7
        frame = inspect.currentframe()
        return (
            debug_helper._safe_evaluate("value * 2", frame),
            debug_helper._safe_evaluate("missing + 1", frame),
        )

    success, failure = sample()

    assert success == {"expression": "value * 2", "result": "14", "error": None}
    assert failure["expression"] == "missing + 1"
    assert failure["result"] is None
    assert "missing" in failure["error"]


def test_recv_line_reads_buffered_and_streamed_data():
    buffer = bytearray()
    sock = FakeSocket([b'{"event"', b': 1}\nrest'])

    line = debug_helper._recv_line(sock, buffer)

    assert line == '{"event": 1}'
    assert buffer == bytearray(b"rest")


def test_recv_line_returns_none_on_disconnect():
    assert debug_helper._recv_line(FakeSocket([], fail=True), bytearray()) is None

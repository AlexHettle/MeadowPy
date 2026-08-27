import io
import json
import socket
import urllib.error

import meadowpy.core.ollama_client as ollama_module
from meadowpy.core.ollama_client import ChatWorker, OllamaClient, OllamaWorker
from meadowpy.core.settings import Settings
from tests.helpers import DummySignal, FakeThread, SignalRecorder


class FakeResponse:
    def __init__(self, body=None, lines=None):
        self.body = body or b""
        self.lines = list(lines or [])
        self.closed = False

    def read(self):
        return self.body

    def __iter__(self):
        return iter(self.lines)

    def readline(self):
        if not self.lines:
            return b""
        line = self.lines.pop(0)
        if isinstance(line, BaseException):
            raise line
        return line

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


def test_health_check_success(monkeypatch):
    worker = OllamaWorker("http://localhost:11434")
    monkeypatch.setattr(
        "meadowpy.core.ollama_client.urllib.request.urlopen",
        lambda request, timeout=5: FakeResponse(body=b"Connected"),
    )

    assert worker._do_health_check() == (True, "Connected")


def test_health_check_uses_default_message_for_empty_body(monkeypatch):
    worker = OllamaWorker("http://localhost:11434")
    monkeypatch.setattr(
        "meadowpy.core.ollama_client.urllib.request.urlopen",
        lambda request, timeout=5: FakeResponse(body=b" \n"),
    )

    assert worker._do_health_check() == (True, "Connected")


def test_health_check_returns_url_error(monkeypatch):
    worker = OllamaWorker("http://localhost:11434")
    monkeypatch.setattr(
        "meadowpy.core.ollama_client.urllib.request.urlopen",
        lambda request, timeout=5: (_ for _ in ()).throw(urllib.error.URLError("offline")),
    )

    ok, message = worker._do_health_check()
    assert ok is False
    assert "offline" in message


def test_health_check_returns_unexpected_exception_message(monkeypatch):
    worker = OllamaWorker("http://localhost:11434")
    monkeypatch.setattr(
        "meadowpy.core.ollama_client.urllib.request.urlopen",
        lambda request, timeout=5: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert worker._do_health_check() == (False, "boom")


def test_fetch_models_returns_only_named_entries(monkeypatch):
    worker = OllamaWorker("http://localhost:11434")
    payload = json.dumps({"models": [{"name": "llama3"}, {"id": "skip-me"}]}).encode("utf-8")
    monkeypatch.setattr(
        "meadowpy.core.ollama_client.urllib.request.urlopen",
        lambda request, timeout=10: FakeResponse(body=payload),
    )

    assert worker._do_fetch_models() == ["llama3"]


def test_chat_worker_streams_tokens_and_finishes(monkeypatch):
    worker = ChatWorker("http://localhost:11434", "llama3", [{"role": "user", "content": "hi"}])
    tokens = SignalRecorder()
    finished = SignalRecorder()
    worker.chat_token.connect(tokens)
    worker.finished.connect(finished)
    lines = [
        b'{"message": {"content": "Hel"}}\n',
        b'{"message": {"content": "lo"}, "done": true}\n',
    ]
    monkeypatch.setattr(
        "meadowpy.core.ollama_client.urllib.request.urlopen",
        lambda request, timeout=120: FakeResponse(lines=lines),
    )

    worker.run()

    assert tokens.calls == [("Hel",), ("lo",)]
    assert finished.calls == [()]


def test_chat_worker_skips_blank_lines_and_empty_tokens(monkeypatch):
    worker = ChatWorker("http://localhost:11434", "llama3", [])
    tokens = SignalRecorder()
    finished = SignalRecorder()
    worker.chat_token.connect(tokens)
    worker.finished.connect(finished)
    lines = [
        b"\n",
        b'{"message": {"content": ""}}\n',
        b'{"done": true}\n',
    ]
    monkeypatch.setattr(
        "meadowpy.core.ollama_client.urllib.request.urlopen",
        lambda request, timeout=120: FakeResponse(lines=lines),
    )

    worker.run()

    assert tokens.calls == []
    assert finished.calls == [()]


def test_chat_worker_ignores_invalid_json_and_cancel_closes_response(monkeypatch):
    worker = ChatWorker("http://localhost:11434", "llama3", [])
    tokens = SignalRecorder()
    worker.chat_token.connect(tokens)
    response = FakeResponse(lines=[
        b"not json\n",
        b'{"message": {"content": "ok"}, "done": true}\n',
    ])
    monkeypatch.setattr(
        "meadowpy.core.ollama_client.urllib.request.urlopen",
        lambda request, timeout=120: response,
    )

    worker.run()
    worker._response = response
    worker.cancel()

    assert tokens.calls == [("ok",)]
    assert response.closed is True


def test_chat_worker_stops_without_error_when_cancelled_read_raises(monkeypatch):
    worker = ChatWorker("http://localhost:11434", "llama3", [])
    errors = SignalRecorder()
    finished = SignalRecorder()
    worker.chat_error.connect(errors)
    worker.finished.connect(finished)

    class CancellingResponse(FakeResponse):
        def readline(self):
            worker._cancelled = True
            raise OSError("socket closed")

    response = CancellingResponse()
    monkeypatch.setattr(
        "meadowpy.core.ollama_client.urllib.request.urlopen",
        lambda request, timeout=120: response,
    )

    worker.run()

    assert errors.calls == []
    assert finished.calls == [()]
    assert response.closed is True


def test_chat_worker_cancel_shuts_down_underlying_socket():
    class FakeSocket:
        def __init__(self):
            self.shutdown_calls = []
            self.closed = False

        def shutdown(self, mode):
            self.shutdown_calls.append(mode)

        def close(self):
            self.closed = True

    class Raw:
        def __init__(self, sock):
            self._sock = sock

    class Fp:
        def __init__(self, sock):
            self.raw = Raw(sock)

    worker = ChatWorker("http://localhost:11434", "llama3", [])
    response = FakeResponse()
    sock = FakeSocket()
    response.fp = Fp(sock)
    worker._response = response

    worker.cancel()

    assert sock.shutdown_calls == [socket.SHUT_RDWR]
    assert sock.closed is True
    assert response.closed is True
    assert worker._response is None


def test_chat_worker_cancel_ignores_cleanup_errors():
    class FailingSocket:
        def shutdown(self, mode):
            raise OSError("shutdown failed")

        def close(self):
            raise OSError("close failed")

    class Raw:
        def __init__(self, sock):
            self._sock = sock

    class Fp:
        def __init__(self, sock):
            self.raw = Raw(sock)

    class FailingResponse(FakeResponse):
        def __init__(self):
            super().__init__()
            self.close_attempted = False

        def close(self):
            self.close_attempted = True
            raise OSError("response close failed")

    worker = ChatWorker("http://localhost:11434", "llama3", [])
    response = FailingResponse()
    response.fp = Fp(FailingSocket())
    worker._response = response

    worker.cancel()

    assert response.close_attempted is True
    assert worker._response is None


def test_chat_worker_reports_http_error_details(monkeypatch):
    worker = ChatWorker("http://localhost:11434", "llama3", [])
    errors = SignalRecorder()
    worker.chat_error.connect(errors)
    http_error = urllib.error.HTTPError(
        url="http://localhost:11434/api/chat",
        code=500,
        msg="Boom",
        hdrs=None,
        fp=io.BytesIO(b'{"error": "model missing"}'),
    )
    monkeypatch.setattr(
        "meadowpy.core.ollama_client.urllib.request.urlopen",
        lambda request, timeout=120: (_ for _ in ()).throw(http_error),
    )

    worker.run()

    assert errors.calls == [("Ollama error (500): model missing",)]


def test_chat_worker_suppresses_http_error_after_cancel(monkeypatch):
    worker = ChatWorker("http://localhost:11434", "llama3", [])
    worker._cancelled = True
    errors = SignalRecorder()
    finished = SignalRecorder()
    worker.chat_error.connect(errors)
    worker.finished.connect(finished)
    http_error = urllib.error.HTTPError(
        url="http://localhost:11434/api/chat",
        code=500,
        msg="Boom",
        hdrs=None,
        fp=io.BytesIO(b'{"error": "late"}'),
    )
    monkeypatch.setattr(
        "meadowpy.core.ollama_client.urllib.request.urlopen",
        lambda request, timeout=120: (_ for _ in ()).throw(http_error),
    )

    worker.run()

    assert errors.calls == []
    assert finished.calls == [()]


def test_chat_worker_reports_http_error_without_detail(monkeypatch):
    worker = ChatWorker("http://localhost:11434", "llama3", [])
    errors = SignalRecorder()
    worker.chat_error.connect(errors)
    http_error = urllib.error.HTTPError(
        url="http://localhost:11434/api/chat",
        code=404,
        msg="Not Found",
        hdrs=None,
        fp=io.BytesIO(b""),
    )
    monkeypatch.setattr(
        "meadowpy.core.ollama_client.urllib.request.urlopen",
        lambda request, timeout=120: (_ for _ in ()).throw(http_error),
    )

    worker.run()

    assert errors.calls == [("Ollama error (404): Not Found",)]


def test_chat_worker_reports_malformed_http_error_without_detail(monkeypatch):
    worker = ChatWorker("http://localhost:11434", "llama3", [])
    errors = SignalRecorder()
    worker.chat_error.connect(errors)
    http_error = urllib.error.HTTPError(
        url="http://localhost:11434/api/chat",
        code=400,
        msg="Bad Request",
        hdrs=None,
        fp=io.BytesIO(b"{not json"),
    )
    monkeypatch.setattr(
        "meadowpy.core.ollama_client.urllib.request.urlopen",
        lambda request, timeout=120: (_ for _ in ()).throw(http_error),
    )

    worker.run()

    assert errors.calls == [("Ollama error (400): Bad Request",)]


def test_chat_worker_reports_connection_errors(monkeypatch):
    worker = ChatWorker("http://localhost:11434", "llama3", [])
    errors = SignalRecorder()
    worker.chat_error.connect(errors)
    monkeypatch.setattr(
        "meadowpy.core.ollama_client.urllib.request.urlopen",
        lambda request, timeout=120: (_ for _ in ()).throw(urllib.error.URLError("refused")),
    )

    worker.run()

    assert errors.calls == [("Connection error: refused",)]


def test_ollama_worker_run_emits_health_and_models(monkeypatch):
    worker = OllamaWorker("http://localhost:11434")
    health = SignalRecorder()
    models = SignalRecorder()
    finished = SignalRecorder()
    worker.health_checked.connect(health)
    worker.models_fetched.connect(models)
    worker.finished.connect(finished)
    monkeypatch.setattr(worker, "_do_health_check", lambda: (True, "ok"))
    monkeypatch.setattr(worker, "_do_fetch_models", lambda: ["llama3"])

    worker.run()

    assert health.calls == [(True, "ok")]
    assert models.calls == [(["llama3"],)]
    assert finished.calls == [()]


def test_ollama_worker_run_emits_empty_models_when_unhealthy(monkeypatch):
    worker = OllamaWorker("http://localhost:11434")
    health = SignalRecorder()
    models = SignalRecorder()
    finished = SignalRecorder()
    fetch_calls = []
    worker.health_checked.connect(health)
    worker.models_fetched.connect(models)
    worker.finished.connect(finished)
    monkeypatch.setattr(worker, "_do_health_check", lambda: (False, "offline"))
    monkeypatch.setattr(worker, "_do_fetch_models", lambda: fetch_calls.append("fetch"))

    worker.run()

    assert health.calls == [(False, "offline")]
    assert models.calls == [([],)]
    assert finished.calls == [()]
    assert fetch_calls == []


def test_fetch_models_returns_empty_list_on_error(monkeypatch):
    worker = OllamaWorker("http://localhost:11434")
    monkeypatch.setattr(
        "meadowpy.core.ollama_client.urllib.request.urlopen",
        lambda request, timeout=10: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert worker._do_fetch_models() == []


def test_select_model_persists_setting_and_emits(tmp_path):
    settings = Settings(tmp_path)
    client = OllamaClient(settings)
    selected = SignalRecorder()
    client.model_selected.connect(selected)

    client.select_model("llama3")

    assert settings.get("ollama.selected_model") == "llama3"
    assert selected.calls == [("llama3",)]


def test_send_chat_requires_selected_model_and_connection(tmp_path):
    settings = Settings(tmp_path)
    client = OllamaClient(settings)
    errors = SignalRecorder()
    client.chat_error.connect(errors)

    client.send_chat([{"role": "user", "content": "hello"}])
    assert "No model selected" in errors.calls[0][0]

    settings.set("ollama.selected_model", "llama3")
    client.send_chat([{"role": "user", "content": "hello"}])
    assert "not connected" in errors.calls[1][0]


class FakeWorker:
    def __init__(self, *args):
        self.args = args
        self.health_checked = DummySignal()
        self.models_fetched = DummySignal()
        self.chat_token = DummySignal()
        self.chat_error = DummySignal()
        self.finished = DummySignal()
        self.moved_to = None
        self.cancelled = False
        self.run_called = 0

    def moveToThread(self, thread):
        self.moved_to = thread

    def run(self):
        self.run_called += 1
        self.finished.emit()

    def cancel(self):
        self.cancelled = True


def test_check_connection_starts_health_worker_thread(tmp_path, monkeypatch):
    settings = Settings(tmp_path)
    client = OllamaClient(settings)
    created_threads = []
    created_workers = []

    def make_thread():
        thread = FakeThread(running=False)
        created_threads.append(thread)
        return thread

    def make_worker(api_url):
        worker = FakeWorker(api_url)
        created_workers.append(worker)
        return worker

    monkeypatch.setattr("meadowpy.core.ollama_client.QThread", make_thread)
    monkeypatch.setattr("meadowpy.core.ollama_client.OllamaWorker", make_worker)

    client.check_connection()

    assert created_workers[0].args == ("http://localhost:11434",)
    assert created_workers[0].moved_to is created_threads[0]
    assert created_threads[0].start_called == 1


def test_send_chat_starts_chat_worker_thread(tmp_path, monkeypatch):
    settings = Settings(tmp_path)
    settings.set("ollama.selected_model", "llama3")
    client = OllamaClient(settings)
    client._connected = True
    created_workers = []
    monkeypatch.setattr(
        "meadowpy.core.ollama_client.QThread",
        lambda: FakeThread(running=False),
    )

    def make_worker(api_url, model, messages):
        worker = FakeWorker(api_url, model, messages)
        created_workers.append(worker)
        return worker

    monkeypatch.setattr("meadowpy.core.ollama_client.ChatWorker", make_worker)

    client.send_chat([{"role": "user", "content": "hello"}])

    assert created_workers[0].args == (
        "http://localhost:11434",
        "llama3",
        [{"role": "user", "content": "hello"}],
    )
    assert client._chat_thread.start_called == 1


def test_on_models_result_clears_missing_selected_model(tmp_path):
    settings = Settings(tmp_path)
    settings.set("ollama.selected_model", "gone-model")
    client = OllamaClient(settings)
    updated = SignalRecorder()
    client.models_updated.connect(updated)

    client._on_models_result(["llama3"])

    assert updated.calls == [(["llama3"],)]
    assert settings.get("ollama.selected_model") == ""


def test_health_result_updates_connection_and_clears_models(tmp_path):
    settings = Settings(tmp_path)
    client = OllamaClient(settings)
    client._models = ["llama3"]
    changed = SignalRecorder()
    updated = SignalRecorder()
    client.connection_changed.connect(changed)
    client.models_updated.connect(updated)

    client._on_health_result(False, "offline")

    assert client.is_connected is False
    assert client.current_models == []
    assert changed.calls == []
    assert updated.calls == [([],)]


def test_setting_changes_restart_or_stop_connection_checks(tmp_path):
    settings = Settings(tmp_path)
    client = OllamaClient(settings)
    calls = []
    client.check_connection = lambda: calls.append("check")

    client._on_setting_changed("ollama.api_url", "http://localhost:11435")
    client._on_setting_changed("ollama.auto_connect", True)
    client._on_setting_changed("ollama.auto_connect", False)

    assert calls == ["check", "check"]
    assert client._auto_check_timer.isActive() is False


def test_cancel_chat_moves_running_thread_to_keep_alive_list(tmp_path):
    settings = Settings(tmp_path)
    client = OllamaClient(settings)

    class Worker:
        def __init__(self):
            self.cancelled = False

        def cancel(self):
            self.cancelled = True

    worker = Worker()
    client._chat_worker = worker
    client._chat_thread = FakeThread(running=True)

    client.cancel_chat()

    assert client._chat_thread is None
    assert client._chat_worker is None
    assert len(client._old_threads) == 1
    assert client._old_workers == [worker]


def test_stop_cancels_workers_and_terminates_stubborn_threads(tmp_path):
    settings = Settings(tmp_path)
    client = OllamaClient(settings)
    chat_worker = FakeWorker()
    health_worker = FakeWorker()
    stubborn = FakeThread(running=True, wait_result=False)
    old = FakeThread(running=True, wait_result=True)
    client._chat_worker = chat_worker
    client._worker = health_worker
    client._chat_thread = stubborn
    client._thread = FakeThread(running=True, wait_result=True)
    client._old_threads = [old]
    client._old_workers = [object()]

    client.stop()

    assert chat_worker.cancelled is True
    assert stubborn.terminate_called == 1
    assert stubborn.wait_calls == [1_000, 1_000]
    assert client._chat_thread is None
    assert client._thread is None
    assert client._old_threads == []
    assert client._old_workers == []


def test_stop_suppresses_late_chat_worker_signals(tmp_path):
    settings = Settings(tmp_path)
    client = OllamaClient(settings)
    worker = FakeWorker()
    thread = FakeThread(running=True, wait_result=True)
    tokens = SignalRecorder()
    errors = SignalRecorder()
    finished = SignalRecorder()
    client.chat_token.connect(tokens)
    client.chat_error.connect(errors)
    client.chat_finished.connect(finished)

    worker.chat_token.connect(client._on_chat_token)
    worker.chat_error.connect(client._on_chat_error)
    worker.finished.connect(client._on_chat_worker_finished)
    worker.finished.connect(thread.quit)
    client._chat_worker = worker
    client._chat_thread = thread

    client.stop()
    worker.chat_token.emit("late")
    worker.chat_error.emit("late error")
    worker.finished.emit()

    assert client._shutting_down is True
    assert worker.cancelled is True
    assert tokens.calls == []
    assert errors.calls == []
    assert finished.calls == []


def test_stop_suppresses_late_old_chat_worker_signals(tmp_path):
    settings = Settings(tmp_path)
    client = OllamaClient(settings)
    worker = FakeWorker()
    thread = FakeThread(running=True, wait_result=True)
    tokens = SignalRecorder()
    errors = SignalRecorder()
    finished = SignalRecorder()
    client.chat_token.connect(tokens)
    client.chat_error.connect(errors)
    client.chat_finished.connect(finished)

    worker.chat_token.connect(client._on_chat_token)
    worker.chat_error.connect(client._on_chat_error)
    worker.finished.connect(client._on_chat_worker_finished)
    worker.finished.connect(thread.quit)
    client._old_workers = [worker]
    client._old_threads = [thread]

    client.stop()
    worker.chat_token.emit("late")
    worker.chat_error.emit("late error")
    worker.finished.emit()

    assert worker.cancelled is True
    assert tokens.calls == []
    assert errors.calls == []
    assert finished.calls == []


def test_old_health_thread_finish_does_not_clear_current_thread(tmp_path):
    settings = Settings(tmp_path)
    client = OllamaClient(settings)
    old_thread = FakeThread(running=False)
    old_worker = object()
    current_thread = FakeThread(running=True)
    current_worker = FakeWorker()
    client._old_threads = [old_thread]
    client._old_workers = [old_worker]
    client._thread = current_thread
    client._worker = current_worker

    client._on_health_thread_finished(old_thread, old_worker)

    assert client._thread is current_thread
    assert client._worker is current_worker
    assert client._old_threads == []
    assert client._old_workers == []


def test_current_health_thread_finish_clears_current_thread(tmp_path):
    settings = Settings(tmp_path)
    client = OllamaClient(settings)
    current_thread = FakeThread(running=False)
    current_worker = FakeWorker()
    client._thread = current_thread
    client._worker = current_worker

    client._on_health_thread_finished(current_thread, current_worker)

    assert client._thread is None
    assert client._worker is None


def test_old_chat_thread_finish_does_not_clear_current_thread(tmp_path):
    settings = Settings(tmp_path)
    client = OllamaClient(settings)
    old_thread = FakeThread(running=False)
    old_worker = object()
    current_thread = FakeThread(running=True)
    current_worker = FakeWorker()
    client._old_threads = [old_thread]
    client._old_workers = [old_worker]
    client._chat_thread = current_thread
    client._chat_worker = current_worker

    client._on_chat_thread_finished(old_thread, old_worker)

    assert client._chat_thread is current_thread
    assert client._chat_worker is current_worker
    assert client._old_threads == []
    assert client._old_workers == []


def test_current_chat_thread_finish_clears_current_thread(tmp_path):
    settings = Settings(tmp_path)
    client = OllamaClient(settings)
    current_thread = FakeThread(running=False)
    current_worker = FakeWorker()
    client._chat_thread = current_thread
    client._chat_worker = current_worker

    client._on_chat_thread_finished(current_thread, current_worker)

    assert client._chat_thread is None
    assert client._chat_worker is None


def test_chat_response_cleanup_handles_missing_different_and_nested_sockets():
    worker = ChatWorker("http://localhost:11434", "model", [])
    worker._close_response()

    class BrokenSocket:
        def __init__(self):
            self.shutdowns = 0
            self.closes = 0

        def shutdown(self, how):
            self.shutdowns += 1
            raise OSError("already closed")

        def close(self):
            self.closes += 1
            raise OSError("already closed")

    socket = BrokenSocket()
    response = FakeResponse()
    response.fp = type("FP", (), {"raw": type("Raw", (), {"_sock": socket})()})()
    current = FakeResponse()
    worker._response = current

    worker._close_response(response)

    assert socket.shutdowns == 1
    assert socket.closes == 1
    assert response.closed is True
    assert worker._response is current
    worker._close_response(current)
    assert worker._response is None


def test_chat_worker_reports_read_failure_and_generic_exception(monkeypatch):
    worker = ChatWorker("http://localhost:11434", "model", [])
    errors = SignalRecorder()
    finished = SignalRecorder()
    worker.chat_error.connect(errors)
    worker.finished.connect(finished)
    monkeypatch.setattr(
        ollama_module.urllib.request,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(lines=[OSError("stream failed")]),
    )
    worker.run()
    assert errors.calls == [("stream failed",)]
    assert finished.calls == [()]

    errors.calls.clear()
    monkeypatch.setattr(
        ollama_module.urllib.request,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("unexpected")),
    )
    worker = ChatWorker("http://localhost:11434", "model", [])
    worker.chat_error.connect(errors)
    worker.run()
    assert errors.calls == [("unexpected",)]


def test_chat_worker_breaks_on_eof_and_cancellation_after_read(monkeypatch):
    eof = FakeResponse(lines=[])
    worker = ChatWorker("http://localhost:11434", "model", [])
    monkeypatch.setattr(ollama_module.urllib.request, "urlopen", lambda *args, **kwargs: eof)
    worker.run()
    assert eof.closed is True

    response = FakeResponse(lines=[b'{"message":{"content":"ignored"}}\n'])
    worker = ChatWorker("http://localhost:11434", "model", [])
    original_readline = response.readline

    def cancel_then_read():
        line = original_readline()
        worker._cancelled = True
        return line

    response.readline = cancel_then_read
    tokens = SignalRecorder()
    worker.chat_token.connect(tokens)
    monkeypatch.setattr(ollama_module.urllib.request, "urlopen", lambda *args, **kwargs: response)
    worker.run()
    assert tokens.calls == []


def test_client_start_properties_and_normal_slots(qapp, tmp_path):
    settings = Settings(tmp_path)
    settings.set("ollama.auto_connect", True)
    settings.set("ollama.api_url", "")
    client = OllamaClient(settings)
    checks = []
    client.check_connection = lambda: checks.append("check")
    client.start()

    assert checks == ["check"]
    assert client._auto_check_timer.isActive() is True
    assert client.api_url == "http://localhost:11434"
    assert client.selected_model == ""
    assert client.is_chatting is False

    thread = FakeThread(running=True)
    client._chat_thread = thread
    assert client.is_chatting is True

    connection = SignalRecorder()
    models = SignalRecorder()
    tokens = SignalRecorder()
    errors = SignalRecorder()
    finished = SignalRecorder()
    client.connection_changed.connect(connection)
    client.models_updated.connect(models)
    client.chat_token.connect(tokens)
    client.chat_error.connect(errors)
    client.chat_finished.connect(finished)
    client._on_health_result(True, "online")
    client._on_models_result(["model"])
    client._on_chat_token("token")
    client._on_chat_error("error")
    client._on_chat_worker_finished()

    assert connection.calls == [(True, "online")]
    assert models.calls == [(["model"],)]
    assert tokens.calls == [("token",)]
    assert errors.calls == [("error",)]
    assert finished.calls == [()]


def test_client_ignores_signals_from_cancelled_chat_worker(tmp_path):
    client = OllamaClient(Settings(tmp_path))
    cancelled_worker = ChatWorker("http://localhost:11434", "old", [])
    active_worker = ChatWorker("http://localhost:11434", "new", [])
    tokens = SignalRecorder()
    errors = SignalRecorder()
    finished = SignalRecorder()
    client.chat_token.connect(tokens)
    client.chat_error.connect(errors)
    client.chat_finished.connect(finished)
    cancelled_worker.chat_token.connect(client._on_chat_token)
    cancelled_worker.chat_error.connect(client._on_chat_error)
    cancelled_worker.finished.connect(client._on_chat_worker_finished)
    active_worker.chat_token.connect(client._on_chat_token)
    active_worker.chat_error.connect(client._on_chat_error)
    active_worker.finished.connect(client._on_chat_worker_finished)
    client._chat_worker = active_worker

    cancelled_worker.chat_token.emit("late token")
    cancelled_worker.chat_error.emit("late error")
    cancelled_worker.finished.emit()

    assert tokens.calls == []
    assert errors.calls == []
    assert finished.calls == []

    active_worker.chat_token.emit("current token")
    active_worker.chat_error.emit("current error")
    active_worker.finished.emit()

    assert tokens.calls == [("current token",)]
    assert errors.calls == [("current error",)]
    assert finished.calls == [()]


def test_client_slots_ignore_results_and_settings_during_shutdown(tmp_path):
    settings = Settings(tmp_path)
    client = OllamaClient(settings)
    client._shutting_down = True
    client._models = ["kept"]
    calls = []
    client.check_connection = lambda: calls.append("check")
    client._on_health_result(False, "offline")
    client._on_models_result([])
    client._on_setting_changed("ollama.api_url", "changed")
    client._on_setting_changed("ollama.auto_connect", True)
    client._on_chat_token("late")
    client._on_chat_error("late")
    client._on_chat_worker_finished()
    assert client._models == ["kept"]
    assert calls == []


def test_worker_shutdown_helpers_cover_partial_workers_and_cancel_failures(tmp_path):
    client = OllamaClient(Settings(tmp_path))
    client._prepare_old_worker_for_shutdown(None, None)

    class PartialChat:
        def cancel(self):
            raise RuntimeError("deleted")

    partial = PartialChat()
    assert client._looks_like_chat_worker(partial) is True
    client._prepare_old_worker_for_shutdown(partial, None)

    health = FakeWorker()
    client._prepare_old_worker_for_shutdown(health, None)
    client._disconnect_chat_worker_signals(FakeWorker(), None)
    client._disconnect_health_worker_signals(FakeWorker(), None)


def test_cancel_and_cleanup_thread_edge_cases(tmp_path):
    client = OllamaClient(Settings(tmp_path))
    running = FakeThread(running=True)
    worker = object()
    client._thread = running
    client._worker = worker
    client._cancel_current()
    assert running.quit_called == 1
    assert client._old_threads == [running]
    assert client._old_workers == [worker]

    absent_thread = FakeThread(running=False)
    absent_worker = object()
    client._cleanup_thread(absent_thread, absent_worker)
    assert client._old_threads == [running]
    assert client._old_workers == [worker]


def test_cancel_chat_keeps_running_thread_without_missing_worker(tmp_path):
    client = OllamaClient(Settings(tmp_path))
    thread = FakeThread(running=True)
    client._chat_thread = thread
    client._chat_worker = None
    client.cancel_chat()
    assert client._old_threads == [thread]
    assert client._old_workers == []

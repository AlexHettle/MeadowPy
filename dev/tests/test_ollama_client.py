import io
import json
import urllib.error

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


def test_health_check_returns_url_error(monkeypatch):
    worker = OllamaWorker("http://localhost:11434")
    monkeypatch.setattr(
        "meadowpy.core.ollama_client.urllib.request.urlopen",
        lambda request, timeout=5: (_ for _ in ()).throw(urllib.error.URLError("offline")),
    )

    ok, message = worker._do_health_check()
    assert ok is False
    assert "offline" in message


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

    client._chat_worker = Worker()
    client._chat_thread = FakeThread(running=True)

    client.cancel_chat()

    assert client._chat_thread is None
    assert client._chat_worker is None
    assert len(client._old_threads) == 1


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

    client.stop()

    assert chat_worker.cancelled is True
    assert stubborn.terminate_called == 1
    assert client._chat_thread is None
    assert client._thread is None
    assert client._old_threads == []

import io
import json
import urllib.error

from meadowpy.core.ollama_client import ChatWorker, OllamaClient, OllamaWorker
from meadowpy.core.settings import Settings
from tests.helpers import FakeThread, SignalRecorder


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


def test_on_models_result_clears_missing_selected_model(tmp_path):
    settings = Settings(tmp_path)
    settings.set("ollama.selected_model", "gone-model")
    client = OllamaClient(settings)
    updated = SignalRecorder()
    client.models_updated.connect(updated)

    client._on_models_result(["llama3"])

    assert updated.calls == [(["llama3"],)]
    assert settings.get("ollama.selected_model") == ""


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

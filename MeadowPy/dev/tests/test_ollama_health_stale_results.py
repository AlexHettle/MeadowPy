"""Regression coverage for superseded Ollama health-check results."""

import pytest
from PyQt6.QtCore import Qt

from meadowpy.core.ollama_client import OllamaClient, OllamaWorker
from meadowpy.core.settings import Settings
from tests.helpers import FakeThread, SignalRecorder


@pytest.mark.parametrize(
    "connection_type",
    [Qt.ConnectionType.DirectConnection, Qt.ConnectionType.QueuedConnection],
    ids=["direct", "queued"],
)
@pytest.mark.parametrize("replacement_started", [False, True])
@pytest.mark.parametrize("connected", [False, True])
def test_superseded_health_results_do_not_change_current_state(
    qapp, tmp_path, connection_type, replacement_started, connected
):
    settings = Settings(tmp_path)
    settings.set("ollama.selected_model", "current")
    client = OllamaClient(settings)
    old_worker = OllamaWorker("http://old.invalid")
    old_thread = FakeThread(running=True)
    client._worker = old_worker
    client._thread = old_thread
    client._connected = not connected
    client._status_text = "current status"
    client._models = ["current"]
    connection = SignalRecorder()
    models = SignalRecorder()
    client.connection_changed.connect(connection)
    client.models_updated.connect(models)
    old_worker.health_checked.connect(client._on_health_result, connection_type)
    old_worker.models_fetched.connect(client._on_models_result, connection_type)

    def emit_old_results():
        old_worker.health_checked.emit(connected, "stale status")
        old_worker.models_fetched.emit(["stale"])

    if connection_type == Qt.ConnectionType.QueuedConnection:
        # Queue results while current, then retire the worker before delivery.
        emit_old_results()
    client._cancel_current()
    if replacement_started:
        client._worker = OllamaWorker("http://current.invalid")
    if connection_type == Qt.ConnectionType.DirectConnection:
        emit_old_results()
    qapp.processEvents()

    assert old_thread.quit_called == 1
    assert client._old_workers == [old_worker]
    assert client.is_connected is (not connected)
    assert client._status_text == "current status"
    assert client.current_models == ["current"]
    assert client.selected_model == "current"
    assert connection.calls == []
    assert models.calls == []


@pytest.mark.parametrize(
    "connection_type",
    [Qt.ConnectionType.DirectConnection, Qt.ConnectionType.QueuedConnection],
    ids=["direct", "queued"],
)
def test_current_health_results_still_update_state(
    qapp, tmp_path, connection_type
):
    settings = Settings(tmp_path)
    settings.set("ollama.selected_model", "current")
    client = OllamaClient(settings)
    worker = OllamaWorker("http://current.invalid")
    client._worker = worker
    connection = SignalRecorder()
    models = SignalRecorder()
    client.connection_changed.connect(connection)
    client.models_updated.connect(models)
    worker.health_checked.connect(client._on_health_result, connection_type)
    worker.models_fetched.connect(client._on_models_result, connection_type)

    worker.health_checked.emit(True, "online")
    worker.models_fetched.emit(["current"])
    qapp.processEvents()

    assert client.is_connected is True
    assert client.current_models == ["current"]
    assert client.selected_model == "current"
    assert connection.calls == [(True, "online")]
    assert models.calls == [(["current"],)]

    worker.health_checked.emit(False, "offline")
    worker.models_fetched.emit([])
    qapp.processEvents()

    assert client.is_connected is False
    assert client.current_models == []
    assert client.selected_model == ""
    assert connection.calls == [(True, "online"), (False, "offline")]
    assert models.calls == [(["current"],), ([],), ([],)]

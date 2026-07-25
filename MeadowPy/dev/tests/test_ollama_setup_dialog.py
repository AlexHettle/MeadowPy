from __future__ import annotations

import urllib.error
from types import SimpleNamespace

from PyQt6.QtGui import QCloseEvent, QPalette
from PyQt6.QtWidgets import QDialog

from meadowpy.core.settings import Settings
from meadowpy.ui.dialogs import ollama_setup_dialog as dialog_module
from meadowpy.ui.dialogs.ollama_setup_dialog import (
    OllamaSetupCheckWorker,
    OllamaSetupDialog,
)


class FakeSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)


class FakeThread:
    instances = []

    def __init__(self):
        self.started = FakeSignal()
        self.finished = FakeSignal()
        self.started_called = False
        self.quit_called = False
        FakeThread.instances.append(self)

    def isRunning(self):
        return False

    def start(self):
        self.started_called = True

    def quit(self):
        self.quit_called = True


class FakeWorker:
    instances = []

    def __init__(self, api_url):
        self.api_url = api_url
        self.finished = FakeSignal()
        self.thread = None
        FakeWorker.instances.append(self)

    def moveToThread(self, thread):
        self.thread = thread

    def run(self):
        pass


class FakeCloseEvent:
    def __init__(self):
        self.ignored = False

    def ignore(self):
        self.ignored = True


class RejectRecordingDialog(OllamaSetupDialog):
    def __init__(self, settings):
        self.reject_called = False
        super().__init__(settings)

    def reject(self):
        self.reject_called = True


def test_worker_reports_url_errors_unexpected_errors_and_model_fetch_failures(
    monkeypatch,
):
    worker = OllamaSetupCheckWorker("http://localhost:11434/")

    monkeypatch.setattr(
        dialog_module.urllib.request,
        "urlopen",
        lambda request, timeout=5: (_ for _ in ()).throw(
            urllib.error.URLError("offline")
        ),
    )
    connected, message = worker._check_health()
    assert connected is False
    assert "Cannot connect to Ollama: offline" == message

    monkeypatch.setattr(
        dialog_module.urllib.request,
        "urlopen",
        lambda request, timeout=5: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    connected, message = worker._check_health()
    assert connected is False
    assert message == "boom"

    assert worker._fetch_models() == []

    worker._check_health = lambda: (False, "no server")
    worker._fetch_models = lambda: (_ for _ in ()).throw(
        AssertionError("models should not be fetched when health fails")
    )
    finished = []
    worker.finished.connect(lambda connected, message, models: finished.append(
        (connected, message, models)
    ))

    worker.run()

    assert finished == [(False, "no server", [])]


def test_dialog_start_check_wires_worker_thread_and_cleans_up(
    monkeypatch,
    qapp,
    tmp_path,
):
    FakeThread.instances.clear()
    FakeWorker.instances.clear()
    monkeypatch.setattr(dialog_module, "QThread", FakeThread)
    monkeypatch.setattr(dialog_module, "OllamaSetupCheckWorker", FakeWorker)

    settings = Settings(tmp_path)
    settings.set("ollama.api_url", "http://localhost:11434/")
    dialog = OllamaSetupDialog(settings)
    dialog._url_input.setText("http://localhost:11435/")

    dialog._start_check()

    thread = FakeThread.instances[0]
    worker = FakeWorker.instances[0]
    assert dialog._check_btn.isEnabled() is False
    assert dialog._server_status.text() == "Checking Ollama..."
    assert dialog._models_status.text() == "Waiting for model list..."
    assert worker.api_url == "http://localhost:11435/"
    assert worker.thread is thread
    assert worker.run in thread.started.callbacks
    assert dialog._on_check_finished in worker.finished.callbacks
    assert thread.quit in worker.finished.callbacks
    assert dialog._on_thread_finished in thread.finished.callbacks
    assert thread.started_called is True

    dialog._on_thread_finished()

    assert dialog._check_btn.isEnabled() is True
    assert dialog._thread is None
    assert dialog._worker is None
    dialog.deleteLater()


def test_dialog_running_thread_blocks_duplicate_check_and_close(
    qapp,
    tmp_path,
):
    settings = Settings(tmp_path)
    dialog = OllamaSetupDialog(settings)
    dialog._thread = SimpleNamespace(isRunning=lambda: True)

    dialog._start_check()
    assert "Checking Ollama" not in dialog._server_status.text()

    dialog._request_close()
    assert "Please wait" in dialog._server_status.text()
    assert dialog.result() == QDialog.DialogCode.Rejected

    event = FakeCloseEvent()
    dialog.closeEvent(event)

    assert event.ignored is True
    assert "Please wait" in dialog._server_status.text()
    dialog.deleteLater()


def test_dialog_not_running_close_paths_and_missing_command_status(
    monkeypatch,
    qapp,
    tmp_path,
):
    monkeypatch.setattr(dialog_module.shutil, "which", lambda command: None)
    settings = Settings(tmp_path)
    dialog = RejectRecordingDialog(settings)

    assert "Not found on PATH" in dialog._command_status.text()

    dialog._request_close()
    assert dialog.reject_called is True

    event = QCloseEvent()
    dialog.closeEvent(event)
    assert event.isAccepted()
    dialog.deleteLater()


def test_dialog_model_selection_empty_model_and_invalid_accent_paths(
    monkeypatch,
    qapp,
    tmp_path,
):
    monkeypatch.setattr(dialog_module.shutil, "which", lambda command: "C:/ollama.exe")
    settings = Settings(tmp_path)
    settings.set("ollama.selected_model", "qwen3")
    settings.set("editor.theme", "custom")
    settings.set("editor.custom_theme.base", "dark")
    settings.set("editor.custom_theme.accent", "not-a-color")

    dialog = OllamaSetupDialog(settings)

    assert dialog._command_status.text() == "Found: C:/ollama.exe"
    assert (
        dialog._download_link.palette()
        .color(QPalette.ColorRole.Link)
        .name()
        .upper()
        == "#2F7A44"
    )

    dialog._on_check_finished(True, "Ollama is running.", ["llama3", "qwen3"])
    assert dialog._model_combo.currentText() == "qwen3"

    dialog._on_check_finished(True, "Ollama is running.", [])
    assert dialog._model_combo.isEnabled() is False
    assert "no models are installed" in dialog._models_status.text()

    settings.set("ollama.selected_model", "")
    dialog._url_input.setText(" http://localhost:11436/ ")
    dialog._auto_connect.setChecked(True)
    dialog._save_settings()

    assert settings.get("ollama.api_url") == "http://localhost:11436"
    assert settings.get("ollama.auto_connect") is True
    assert settings.get("ollama.selected_model") == ""
    assert dialog._save_btn.text() == "Saved"
    dialog.deleteLater()

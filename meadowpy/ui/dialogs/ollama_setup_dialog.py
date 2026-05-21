"""Guided Ollama setup and connection check dialog."""

import json
import shutil
import urllib.error
import urllib.request

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from meadowpy.core.settings import Settings
from meadowpy.resources.resource_loader import current_accent_hex


def _normalize_api_url(api_url: str | None) -> str:
    url = (api_url or "").strip() or "http://localhost:11434"
    return url.rstrip("/")


class OllamaSetupCheckWorker(QObject):
    """Checks the Ollama HTTP API without blocking the dialog."""

    finished = pyqtSignal(bool, str, list)

    def __init__(self, api_url: str):
        super().__init__()
        self._api_url = _normalize_api_url(api_url)

    def run(self) -> None:
        connected, message = self._check_health()
        models: list[str] = []
        if connected:
            models = self._fetch_models()
        self.finished.emit(connected, message, models)

    def _check_health(self) -> tuple[bool, str]:
        try:
            req = urllib.request.Request(f"{self._api_url}/")
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = resp.read().decode("utf-8", errors="replace").strip()
                return True, body or "Ollama is running."
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", str(exc))
            return False, f"Cannot connect to Ollama: {reason}"
        except Exception as exc:
            return False, str(exc)

    def _fetch_models(self) -> list[str]:
        try:
            req = urllib.request.Request(f"{self._api_url}/api/tags")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            models = data.get("models", [])
            return [m["name"] for m in models if "name" in m]
        except Exception:
            return []


class OllamaSetupDialog(QDialog):
    """Beginner-friendly Ollama setup, check, and model selection flow."""

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._thread: QThread | None = None
        self._worker: OllamaSetupCheckWorker | None = None

        self.setWindowTitle("Ollama Setup")
        self.setMinimumSize(560, 430)
        self._setup_ui()
        self._refresh_command_status()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        intro = QLabel(
            "MeadowPy uses Ollama for local AI. Use this checklist to "
            "confirm Ollama is installed, running, and has at least one model."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self._download_link = QLabel()
        self._download_link.setOpenExternalLinks(True)
        self._apply_link_accent(self._download_link)
        layout.addWidget(self._download_link)

        url_row = QHBoxLayout()
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("http://localhost:11434")
        self._url_input.setText(
            _normalize_api_url(self._settings.get("ollama.api_url"))
        )
        self._url_input.setToolTip("The local Ollama API address")
        url_row.addWidget(QLabel("API URL:"))
        url_row.addWidget(self._url_input, 1)
        layout.addLayout(url_row)

        self._auto_connect = QCheckBox("Automatically check Ollama on startup")
        self._auto_connect.setChecked(self._settings.get("ollama.auto_connect"))
        layout.addWidget(self._auto_connect)

        checklist = QFrame()
        checklist.setObjectName("ollamaSetupChecklist")
        grid = QGridLayout(checklist)
        grid.setColumnStretch(1, 1)
        self._command_status = self._add_status_row(
            grid, 0, "1. Ollama command"
        )
        self._server_status = self._add_status_row(
            grid, 1, "2. Ollama server"
        )
        self._models_status = self._add_status_row(
            grid, 2, "3. Installed models"
        )
        self._selected_status = self._add_status_row(
            grid, 3, "4. MeadowPy model"
        )
        layout.addWidget(checklist)

        model_row = QHBoxLayout()
        self._model_combo = QComboBox()
        self._model_combo.setEnabled(False)
        self._model_combo.currentTextChanged.connect(
            lambda _: self._refresh_selected_status()
        )
        self._save_model_btn = QPushButton("Use Selected Model")
        self._save_model_btn.setEnabled(False)
        self._save_model_btn.clicked.connect(self._save_settings)
        model_row.addWidget(QLabel("Available models:"))
        model_row.addWidget(self._model_combo, 1)
        model_row.addWidget(self._save_model_btn)
        layout.addLayout(model_row)

        actions = QHBoxLayout()
        self._check_btn = QPushButton("Check Now")
        self._check_btn.clicked.connect(self._start_check)
        self._save_btn = QPushButton("Save Settings")
        self._save_btn.clicked.connect(self._save_settings)
        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self._request_close)
        actions.addStretch()
        actions.addWidget(self._check_btn)
        actions.addWidget(self._save_btn)
        actions.addWidget(self._close_btn)
        layout.addLayout(actions)

    def _add_status_row(
        self, grid: QGridLayout, row: int, title: str
    ) -> QLabel:
        name = QLabel(title)
        value = QLabel("Not checked yet")
        value.setWordWrap(True)
        grid.addWidget(name, row, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(value, row, 1)
        return value

    def _set_status(self, label: QLabel, text: str, ok: bool | None) -> None:
        color = self._accent_hex() if ok else "#B00020"
        if ok is None:
            color = "#6B6B6B"
        label.setText(text)
        label.setStyleSheet(f"color: {color};")

    def _refresh_command_status(self) -> None:
        path = shutil.which("ollama")
        if path:
            self._set_status(self._command_status, f"Found: {path}", True)
        else:
            self._set_status(
                self._command_status,
                "Not found on PATH. Install Ollama, then reopen your terminal.",
                False,
            )
        self._refresh_selected_status()

    def _refresh_selected_status(self) -> None:
        selected = self._settings.get("ollama.selected_model") or ""
        current = self._model_combo.currentText()
        if current:
            selected = current
        if selected:
            self._set_status(
                self._selected_status,
                f"MeadowPy will use: {selected}",
                True,
            )
        else:
            self._set_status(
                self._selected_status,
                "No model selected yet.",
                False,
            )

    def _start_check(self) -> None:
        if self._thread and self._thread.isRunning():
            return

        self._check_btn.setEnabled(False)
        self._set_status(self._server_status, "Checking Ollama...", None)
        self._set_status(self._models_status, "Waiting for model list...", None)

        self._thread = QThread()
        self._worker = OllamaSetupCheckWorker(self._url_input.text())
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_check_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()

    def _on_check_finished(
        self, connected: bool, message: str, models: list[str]
    ) -> None:
        self._set_status(self._server_status, message, connected)

        self._model_combo.clear()
        self._model_combo.addItems(models)
        has_models = bool(models)
        self._model_combo.setEnabled(has_models)
        self._save_model_btn.setEnabled(has_models)

        selected = self._settings.get("ollama.selected_model") or ""
        if selected and selected in models:
            self._model_combo.setCurrentText(selected)

        if connected and has_models:
            self._set_status(
                self._models_status,
                f"Found {len(models)} model(s).",
                True,
            )
        elif connected:
            self._set_status(
                self._models_status,
                "Connected, but no models are installed yet.",
                False,
            )
        else:
            self._set_status(
                self._models_status,
                "Cannot list models until Ollama is running.",
                False,
            )
        self._refresh_selected_status()

    def _on_thread_finished(self) -> None:
        self._check_btn.setEnabled(True)
        self._thread = None
        self._worker = None

    def _save_settings(self) -> None:
        self._settings.set(
            "ollama.api_url",
            _normalize_api_url(self._url_input.text()),
        )
        self._settings.set("ollama.auto_connect", self._auto_connect.isChecked())
        model = self._model_combo.currentText()
        if model:
            self._settings.set("ollama.selected_model", model)
        self._settings.save()
        self._refresh_selected_status()
        self._save_btn.setText("Saved")

    def _request_close(self) -> None:
        if self._thread and self._thread.isRunning():
            self._set_status(
                self._server_status,
                "Please wait for the current Ollama check to finish.",
                None,
            )
            return
        self.reject()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._thread and self._thread.isRunning():
            self._set_status(
                self._server_status,
                "Please wait for the current Ollama check to finish.",
                None,
            )
            event.ignore()
            return
        super().closeEvent(event)

    def _accent_hex(self) -> str:
        accent = QColor(
            current_accent_hex(
                self._settings.get("editor.theme") or "default_dark",
                self._settings.get("editor.custom_theme.base") or "dark",
                self._settings.get("editor.custom_theme.accent"),
            )
        )
        if not accent.isValid():
            accent = QColor(current_accent_hex("default_dark"))
        return accent.name().upper()

    def _apply_link_accent(self, label: QLabel) -> None:
        accent_hex = self._accent_hex()
        accent = QColor(accent_hex)
        palette = label.palette()
        palette.setColor(QPalette.ColorRole.Link, accent)
        palette.setColor(QPalette.ColorRole.LinkVisited, accent)
        label.setPalette(palette)
        label.setText(
            '<a href="https://ollama.com/download" '
            f'style="color: {accent_hex};">Download Ollama</a>'
            " if it is not installed yet."
        )

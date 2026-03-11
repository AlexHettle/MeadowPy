"""Ollama connection manager — background health checks, model listing, and chat."""

import json
import urllib.request
import urllib.error

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal

from meadowpy.core.settings import Settings


# ── Chat streaming worker ───────────────────────────────────────────

class ChatWorker(QObject):
    """Streams a chat completion from the Ollama /api/chat endpoint."""

    chat_token = pyqtSignal(str)    # one token at a time
    chat_error = pyqtSignal(str)    # error description
    finished = pyqtSignal()         # always emitted at the end

    def __init__(self, api_url: str, model: str, messages: list[dict]):
        super().__init__()
        self._api_url = api_url.rstrip("/")
        self._model = model
        self._messages = messages
        self._cancelled = False
        self._response = None  # hold reference so cancel() can close it

    def cancel(self) -> None:
        """Request cancellation — closes the HTTP connection to unblock reads."""
        self._cancelled = True
        resp = self._response
        if resp is not None:
            try:
                resp.close()
            except Exception:
                pass

    def run(self) -> None:
        """POST /api/chat with streaming and emit tokens."""
        try:
            payload = json.dumps({
                "model": self._model,
                "messages": self._messages,
                "stream": True,
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{self._api_url}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            self._response = urllib.request.urlopen(req, timeout=120)
            try:
                for raw_line in self._response:
                    if self._cancelled:
                        break
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Extract token text
                    msg = chunk.get("message", {})
                    token = msg.get("content", "")
                    if token:
                        self.chat_token.emit(token)

                    if chunk.get("done", False):
                        break
            finally:
                try:
                    self._response.close()
                except Exception:
                    pass
                self._response = None

        except urllib.error.URLError as e:
            reason = getattr(e, "reason", str(e))
            self.chat_error.emit(f"Connection error: {reason}")
        except Exception as e:
            if not self._cancelled:
                self.chat_error.emit(str(e))
        finally:
            self.finished.emit()


# ── Health / model-list worker ──────────────────────────────────────

class OllamaWorker(QObject):
    """Runs Ollama HTTP requests in a background QThread."""

    health_checked = pyqtSignal(bool, str)   # (is_connected, status_message)
    models_fetched = pyqtSignal(list)         # list of model-name strings
    finished = pyqtSignal()                   # marks end of work

    def __init__(self, api_url: str):
        super().__init__()
        self._api_url = api_url.rstrip("/")

    def run(self) -> None:
        """Execute health check, then fetch models if healthy."""
        connected, message = self._do_health_check()
        self.health_checked.emit(connected, message)

        if connected:
            models = self._do_fetch_models()
            self.models_fetched.emit(models)
        else:
            self.models_fetched.emit([])

        self.finished.emit()

    def _do_health_check(self) -> tuple[bool, str]:
        """GET / — returns (True, status) or (False, error_description)."""
        try:
            req = urllib.request.Request(f"{self._api_url}/")
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = resp.read().decode("utf-8").strip()
                return True, body or "Connected"
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", str(e))
            return False, f"Cannot connect: {reason}"
        except Exception as e:
            return False, str(e)

    def _do_fetch_models(self) -> list[str]:
        """GET /api/tags — returns list of model name strings."""
        try:
            req = urllib.request.Request(f"{self._api_url}/api/tags")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = data.get("models", [])
                return [m["name"] for m in models if "name" in m]
        except Exception:
            return []


class OllamaClient(QObject):
    """Manages the Ollama connection lifecycle on the main thread.

    Follows the LintRunner pattern: spawns a worker in a QThread,
    keeps old threads alive until they finish, auto-checks on a timer.
    """

    connection_changed = pyqtSignal(bool, str)   # (is_connected, status_text)
    models_updated = pyqtSignal(list)             # list of model-name strings
    model_selected = pyqtSignal(str)              # emitted when user picks a model

    # Chat streaming signals
    chat_token = pyqtSignal(str)      # one token at a time
    chat_finished = pyqtSignal()      # stream completed
    chat_error = pyqtSignal(str)      # error message

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._connected = False
        self._status_text = "Offline"
        self._models: list[str] = []

        # Health-check worker thread management (mirrors LintRunner)
        self._thread: QThread | None = None
        self._worker: OllamaWorker | None = None
        self._old_threads: list[QThread] = []

        # Chat worker thread management (separate from health checks)
        self._chat_thread: QThread | None = None
        self._chat_worker: ChatWorker | None = None

        # Auto-check timer (30 seconds)
        self._auto_check_timer = QTimer(self)
        self._auto_check_timer.setInterval(30_000)
        self._auto_check_timer.timeout.connect(self.check_connection)

        # React to settings changes (e.g., api_url changed in preferences)
        self._settings.settings_changed.connect(self._on_setting_changed)

    # ── Properties ──────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def current_models(self) -> list[str]:
        return list(self._models)

    @property
    def selected_model(self) -> str:
        return self._settings.get("ollama.selected_model") or ""

    @property
    def api_url(self) -> str:
        return self._settings.get("ollama.api_url") or "http://localhost:11434"

    @property
    def is_chatting(self) -> bool:
        return self._chat_thread is not None and self._chat_thread.isRunning()

    # ── Public methods ──────────────────────────────────────────────

    def start(self) -> None:
        """Call once after construction. Starts auto-check if enabled."""
        if self._settings.get("ollama.auto_connect"):
            self._auto_check_timer.start()
            # Immediate first check
            self.check_connection()

    def stop(self) -> None:
        """Call during app shutdown. Stops timer and cancels running work."""
        self._auto_check_timer.stop()

        # Cancel running workers
        if self._chat_worker:
            self._chat_worker.cancel()
        if self._worker:
            pass  # health worker has no cancel — it's fast

        # Ask all threads to quit — short timeouts to avoid freezing the UI
        for thread in [self._chat_thread, self._thread] + self._old_threads:
            if thread and thread.isRunning():
                thread.quit()
                if not thread.wait(500):
                    thread.terminate()
                    thread.wait(500)

        self._chat_thread = None
        self._chat_worker = None
        self._thread = None
        self._worker = None
        self._old_threads.clear()

    def check_connection(self) -> None:
        """Spawn a background worker to check health + fetch models."""
        self._cancel_current()

        api_url = self.api_url
        self._thread = QThread()
        self._worker = OllamaWorker(api_url)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.health_checked.connect(self._on_health_result)
        self._worker.models_fetched.connect(self._on_models_result)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._on_health_thread_finished)
        self._thread.start()

    def select_model(self, model_name: str) -> None:
        """Set the selected model in settings and notify listeners."""
        self._settings.set("ollama.selected_model", model_name)
        self.model_selected.emit(model_name)

    def send_chat(self, messages: list[dict]) -> None:
        """Start a streaming chat completion in a background thread."""
        self.cancel_chat()

        model = self.selected_model
        if not model:
            self.chat_error.emit("No model selected. Click the AI status bar to choose one.")
            return
        if not self._connected:
            self.chat_error.emit("Ollama is not connected.")
            return

        self._chat_thread = QThread()
        self._chat_worker = ChatWorker(self.api_url, model, messages)
        self._chat_worker.moveToThread(self._chat_thread)

        self._chat_thread.started.connect(self._chat_worker.run)
        self._chat_worker.chat_token.connect(self._on_chat_token)
        self._chat_worker.chat_error.connect(self._on_chat_error)
        self._chat_worker.finished.connect(self._on_chat_worker_finished)
        self._chat_worker.finished.connect(self._chat_thread.quit)
        self._chat_thread.finished.connect(self._on_chat_thread_finished)
        self._chat_thread.start()

    def cancel_chat(self) -> None:
        """Cancel any in-progress chat stream."""
        if self._chat_worker:
            self._chat_worker.cancel()
        if self._chat_thread and self._chat_thread.isRunning():
            old_thread = self._chat_thread
            old_thread.quit()
            self._old_threads.append(old_thread)
            old_thread.finished.connect(
                lambda t=old_thread: self._cleanup_thread(t)
            )
        self._chat_thread = None
        self._chat_worker = None

    # ── Internal slots ──────────────────────────────────────────────

    def _on_health_result(self, connected: bool, message: str) -> None:
        """Handle health check result from the worker."""
        changed = (connected != self._connected)
        self._connected = connected
        self._status_text = message

        if not connected:
            # Clear models when disconnected
            self._models = []
            self.models_updated.emit([])

        if changed:
            self.connection_changed.emit(connected, message)

    def _on_models_result(self, models: list[str]) -> None:
        """Handle model list result from the worker."""
        self._models = models
        self.models_updated.emit(models)

        # If the currently selected model is no longer available, clear it
        selected = self.selected_model
        if selected and selected not in models:
            self._settings.set("ollama.selected_model", "")

    def _on_setting_changed(self, key: str, value: object) -> None:
        """React to relevant settings changes."""
        if key == "ollama.api_url":
            # URL changed — re-check immediately
            self.check_connection()
        elif key == "ollama.auto_connect":
            if value:
                self._auto_check_timer.start()
                self.check_connection()
            else:
                self._auto_check_timer.stop()

    # ── Chat slots ───────────────────────────────────────────────────

    def _on_chat_token(self, token: str) -> None:
        self.chat_token.emit(token)

    def _on_chat_error(self, message: str) -> None:
        self.chat_error.emit(message)

    def _on_chat_worker_finished(self) -> None:
        self.chat_finished.emit()

    def _on_chat_thread_finished(self) -> None:
        """Safe to drop chat thread/worker refs now."""
        self._chat_thread = None
        self._chat_worker = None

    def _on_health_thread_finished(self) -> None:
        """Safe to drop health-check thread/worker refs now."""
        self._thread = None
        self._worker = None

    # ── Thread lifecycle (mirrors LintRunner) ───────────────────────

    def _cancel_current(self) -> None:
        """Cancel any in-progress worker thread."""
        if self._thread and self._thread.isRunning():
            old_thread = self._thread
            old_thread.quit()
            # Keep a reference so it isn't GC'd while still running
            self._old_threads.append(old_thread)
            old_thread.finished.connect(
                lambda t=old_thread: self._cleanup_thread(t)
            )
        self._thread = None
        self._worker = None

    def _cleanup_thread(self, thread: QThread) -> None:
        """Remove finished thread from the keep-alive list."""
        try:
            self._old_threads.remove(thread)
        except ValueError:
            pass

"""Model selection popup for Ollama AI integration."""

from PyQt6.QtCore import QObject, QPoint, pyqtSignal
from PyQt6.QtWidgets import QMenu, QWidget


class ModelSelectorPopup(QObject):
    """A popup menu that lists available Ollama models for selection.

    Emits ``model_chosen`` with the model name when the user picks one,
    or the special sentinel ``"__retry__"`` / ``"__refresh__"`` to request
    a reconnection / model-list refresh.
    """

    model_chosen = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._parent = parent
        self._models: list[str] = []
        self._current_model: str = ""
        self._is_connected: bool = False

    # ── State setters (called by MainWindow) ────────────────────────

    def set_models(self, models: list[str]) -> None:
        self._models = list(models)

    def set_current_model(self, model: str) -> None:
        self._current_model = model

    def set_connected(self, connected: bool) -> None:
        self._is_connected = connected

    # ── Show the popup ──────────────────────────────────────────────

    def show_at(self, global_pos: QPoint) -> None:
        """Build and show the model selector popup at *global_pos*."""
        menu = QMenu(self._parent)
        menu.setObjectName("modelSelectorMenu")

        if not self._is_connected:
            self._build_offline_menu(menu)
        elif not self._models:
            self._build_no_models_menu(menu)
        else:
            self._build_model_list_menu(menu)

        menu.exec(global_pos)

    # ── Menu builders ───────────────────────────────────────────────

    def _build_offline_menu(self, menu: QMenu) -> None:
        """Ollama is not running."""
        offline = menu.addAction("Ollama is not running")
        offline.setEnabled(False)

        menu.addSeparator()

        retry = menu.addAction("Check connection...")
        retry.triggered.connect(lambda: self.model_chosen.emit("__retry__"))

    def _build_no_models_menu(self, menu: QMenu) -> None:
        """Connected but no models installed."""
        no_models = menu.addAction("No models installed")
        no_models.setEnabled(False)

        hint = menu.addAction("Run:  ollama pull llama3")
        hint.setEnabled(False)

        menu.addSeparator()

        refresh = menu.addAction("Refresh models...")
        refresh.triggered.connect(
            lambda: self.model_chosen.emit("__refresh__")
        )

    def _build_model_list_menu(self, menu: QMenu) -> None:
        """Connected and models are available."""
        header = menu.addAction("Select AI Model")
        header.setEnabled(False)
        menu.addSeparator()

        for model_name in self._models:
            action = menu.addAction(model_name)
            action.setCheckable(True)
            action.setChecked(model_name == self._current_model)
            action.triggered.connect(
                lambda checked, m=model_name: self.model_chosen.emit(m)
            )

        menu.addSeparator()

        refresh = menu.addAction("Refresh models...")
        refresh.triggered.connect(
            lambda: self.model_chosen.emit("__refresh__")
        )

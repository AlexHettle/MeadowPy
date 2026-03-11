"""JSON-based application settings with change notification signals."""

import json
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from meadowpy.constants import CONFIG_DIR_NAME, SETTINGS_FILENAME, DEFAULT_SETTINGS


class Settings(QObject):
    """JSON-based application settings with change notification signals."""

    settings_changed = pyqtSignal(str, object)  # key, new_value

    def __init__(self, config_dir: Path | None = None, parent=None):
        super().__init__(parent)
        if config_dir is None:
            config_dir = Path.home() / CONFIG_DIR_NAME
        self._config_dir = config_dir
        self._config_file = config_dir / SETTINGS_FILENAME
        self._data: dict[str, Any] = {}

    def get(self, key: str, default=None) -> Any:
        """Get a setting value. Falls back to DEFAULT_SETTINGS, then to default param."""
        if key in self._data:
            return self._data[key]
        if key in DEFAULT_SETTINGS:
            return DEFAULT_SETTINGS[key]
        return default

    def set(self, key: str, value: Any) -> None:
        """Set a value and emit settings_changed signal."""
        old_value = self._data.get(key)
        self._data[key] = value
        if old_value != value:
            self.settings_changed.emit(key, value)

    def load(self) -> None:
        """Load settings from JSON file. Missing keys get defaults."""
        if self._config_file.exists():
            try:
                with open(self._config_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    self._data = loaded
            except (json.JSONDecodeError, OSError):
                self._data = {}
        else:
            self._data = {}

    def save(self) -> None:
        """Persist current settings to JSON file."""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        merged = dict(DEFAULT_SETTINGS)
        merged.update(self._data)
        with open(self._config_file, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)

    def reset_to_defaults(self) -> None:
        """Restore all settings to their defaults."""
        self._data = {}
        self.save()

    @property
    def config_file_path(self) -> Path:
        """Return the path to settings.json."""
        return self._config_file

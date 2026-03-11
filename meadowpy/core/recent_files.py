"""Recent files list management."""

from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from meadowpy.constants import RECENT_FILES_MAX
from meadowpy.core.settings import Settings


class RecentFilesManager(QObject):
    """Manages the recent files list, stored in settings."""

    recent_files_changed = pyqtSignal(list)

    def __init__(self, settings: Settings, max_files: int = RECENT_FILES_MAX, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._max_files = max_files

    def add(self, file_path: str) -> None:
        """Add a file to the top of the recent list."""
        normalized = str(Path(file_path).resolve())
        files = self.get_files()

        # Remove if already present
        files = [f for f in files if f != normalized]

        # Insert at top
        files.insert(0, normalized)

        # Trim to max
        files = files[: self._max_files]

        self._settings.set("window.recent_files", files)
        self._settings.save()
        self.recent_files_changed.emit(files)

    def remove(self, file_path: str) -> None:
        """Remove a specific file from the list."""
        normalized = str(Path(file_path).resolve())
        files = self.get_files()
        files = [f for f in files if f != normalized]
        self._settings.set("window.recent_files", files)
        self._settings.save()
        self.recent_files_changed.emit(files)

    def clear(self) -> None:
        """Clear the entire recent files list."""
        self._settings.set("window.recent_files", [])
        self._settings.save()
        self.recent_files_changed.emit([])

    def get_files(self) -> list[str]:
        """Return the current recent files list."""
        files = self._settings.get("window.recent_files", [])
        return list(files) if files else []

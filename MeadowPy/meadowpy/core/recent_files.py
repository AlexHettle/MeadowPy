"""Recent files list management."""

import os
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from meadowpy.constants import RECENT_FILES_MAX
from meadowpy.core.settings import Settings


def _path_comparison_key(file_path: str) -> str:
    """Return a platform-aware key for comparing resolved file paths."""
    return os.path.normcase(str(Path(file_path).resolve()))


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
        normalized_key = _path_comparison_key(normalized)
        files = self.get_files()

        # Preserve the spelling already shown to the user when an equivalent
        # Windows path is added with different casing.
        display_path = next(
            (f for f in files if _path_comparison_key(f) == normalized_key),
            normalized,
        )
        files = [
            f for f in files if _path_comparison_key(f) != normalized_key
        ]

        # Insert at top
        files.insert(0, display_path)

        # Trim to max
        files = files[: self._max_files]

        self._store_files(files)

    def remove(self, file_path: str) -> None:
        """Remove a specific file from the list."""
        normalized_key = _path_comparison_key(file_path)
        files = self.get_files()
        files = [
            f for f in files if _path_comparison_key(f) != normalized_key
        ]
        self._store_files(files)

    def clear(self) -> None:
        """Clear the entire recent files list."""
        self._store_files([])

    def get_files(self) -> list[str]:
        """Return the current recent files list."""
        files = self._settings.get("window.recent_files", [])
        return list(files) if files else []

    def _store_files(self, files: list[str]) -> None:
        """Update the list, treating persistence as a best-effort operation."""
        self._settings.set("window.recent_files", files)
        try:
            self._settings.save()
        except OSError:
            pass
        self.recent_files_changed.emit(files)

"""File I/O operations: open, save, save-as."""

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QFileDialog

from meadowpy.core.settings import Settings
from meadowpy.core.recent_files import RecentFilesManager

FILE_FILTERS = "Python Files (*.py *.pyw);;All Files (*)"


class FileManager(QObject):
    """Handles file I/O operations."""

    file_opened = pyqtSignal(str, str)  # file_path, content
    file_saved = pyqtSignal(str)  # file_path

    def __init__(self, settings: Settings, recent_files: RecentFilesManager, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._recent_files = recent_files
        self.last_save_error: OSError | None = None
        self.last_save_error_path: str | None = None

    def open_file(self, file_path: str | None = None, parent=None) -> tuple[str, str] | None:
        """Open a file. If file_path is None, show QFileDialog. Returns (path, content) or None."""
        if file_path is None:
            file_path, _ = QFileDialog.getOpenFileName(
                parent, "Open File", "", FILE_FILTERS
            )
        if not file_path:
            return None

        content = self.read_file(file_path)
        self._recent_files.add(file_path)
        self.file_opened.emit(file_path, content)
        return file_path, content

    def save_file(self, file_path: str, content: str) -> bool:
        """Save content to file_path. Returns True on success."""
        self.last_save_error = None
        self.last_save_error_path = None
        try:
            self.write_file(file_path, content)
        except OSError as exc:
            self.last_save_error = exc
            self.last_save_error_path = file_path
            return False
        try:
            self._recent_files.add(file_path)
        except OSError:
            pass
        self.file_saved.emit(file_path)
        return True

    def save_file_as(self, content: str, parent=None) -> str | None:
        """Show Save As dialog. Returns new file_path or None if cancelled."""
        self.last_save_error = None
        self.last_save_error_path = None
        file_path, _ = QFileDialog.getSaveFileName(
            parent, "Save File As", "", FILE_FILTERS
        )
        if not file_path:
            return None

        if self.save_file(file_path, content):
            return file_path
        return None

    def read_file(self, file_path: str) -> str:
        """Read file content. UTF-8 with latin-1 fallback."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            with open(file_path, "r", encoding="latin-1") as f:
                return f.read()

    def write_file(self, file_path: str, content: str) -> None:
        """Write content to file with UTF-8 encoding."""
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            f.write(content)

"""File I/O operations: open, save, save-as."""

from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QFileDialog

from meadowpy.core.settings import Settings
from meadowpy.core.recent_files import RecentFilesManager

FILE_FILTERS = (
    "Editable Text Files (*.py *.pyw *.txt *.md *.csv *.json *.toml *.ini "
    "*.cfg *.yaml *.yml *.log);;Python Files (*.py *.pyw);;All Files (*)"
)
TEXT_SNIFF_BYTES = 8192
LARGE_FILE_WARNING_BYTES = 10 * 1024 * 1024
_ALLOWED_CONTROL_BYTES = {9, 10, 12, 13}
_BINARY_CONTROL_BYTES = set(range(32)) - _ALLOWED_CONTROL_BYTES
_UTF32_BOMS = (
    b"\xff\xfe\x00\x00",
    b"\x00\x00\xfe\xff",
)
_UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")
_UNICODE_TEXT_BOMS = _UTF32_BOMS + _UTF16_BOMS
_BINARY_FILE_SUFFIXES = {
    ".7z",
    ".bmp",
    ".class",
    ".dll",
    ".doc",
    ".docx",
    ".exe",
    ".gif",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".odp",
    ".ods",
    ".odt",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".pyc",
    ".pyd",
    ".rar",
    ".so",
    ".webp",
    ".xls",
    ".xlsx",
    ".zip",
}


def is_known_unsupported_editor_file(file_path: str | Path) -> bool:
    """Return True for file types MeadowPy's text editor should not open."""
    return Path(file_path).suffix.lower() in _BINARY_FILE_SUFFIXES


class UnsupportedFileError(OSError):
    """Raised when a file is not suitable for MeadowPy's text editor."""


class LargeFileError(OSError):
    """Raised when a text file is large enough to need user confirmation."""

    def __init__(
        self,
        file_path: str | Path,
        size_bytes: int,
        threshold_bytes: int = LARGE_FILE_WARNING_BYTES,
    ):
        self.file_path = str(file_path)
        self.size_bytes = size_bytes
        self.threshold_bytes = threshold_bytes
        name = Path(file_path).name
        super().__init__(
            f"{name} is {format_file_size(size_bytes)}, which is larger than "
            f"MeadowPy's {format_file_size(threshold_bytes)} large-file safeguard."
        )


def format_file_size(size_bytes: int) -> str:
    """Return a compact human-readable file size for dialogs and status text."""
    mb = size_bytes / (1024 * 1024)
    if mb >= 1:
        return f"{mb:.1f} MB"
    kb = size_bytes / 1024
    if kb >= 1:
        return f"{kb:.1f} KB"
    return f"{size_bytes} bytes"


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
        self.last_open_error: OSError | None = None
        self.last_open_error_path: str | None = None

    def open_file(
        self,
        file_path: str | None = None,
        parent=None,
        *,
        allow_large: bool = False,
    ) -> tuple[str, str] | None:
        """Open a file. If file_path is None, show QFileDialog. Returns (path, content) or None."""
        self.last_open_error = None
        self.last_open_error_path = None
        if file_path is None:
            file_path, _ = QFileDialog.getOpenFileName(
                parent, "Open File", "", FILE_FILTERS
            )
        if not file_path:
            return None

        try:
            content = self.read_file(file_path, allow_large=allow_large)
        except OSError as exc:
            self.last_open_error = exc
            self.last_open_error_path = file_path
            return None
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

    def read_file(self, file_path: str, *, allow_large: bool = False) -> str:
        """Read editor-safe text content with conservative binary rejection."""
        path = Path(file_path)
        if is_known_unsupported_editor_file(path):
            raise UnsupportedFileError(
                f"{path.name} is not a text file MeadowPy can edit."
            )

        with open(file_path, "rb") as f:
            sample = f.read(TEXT_SNIFF_BYTES)
            if self._looks_binary(sample):
                raise UnsupportedFileError(
                    f"{path.name} does not look like readable text."
                )
            size_bytes = path.stat().st_size
            if size_bytes > LARGE_FILE_WARNING_BYTES and not allow_large:
                raise LargeFileError(path, size_bytes)
            rest = f.read()
        data = sample + rest
        return self._decode_text(data, path.name)

    def write_file(self, file_path: str, content: str) -> None:
        """Write content to file with UTF-8 encoding."""
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            f.write(content)

    @staticmethod
    def _looks_binary(sample: bytes) -> bool:
        """Return True for byte samples that would render as unreadable text."""
        if not sample:
            return False
        if sample.startswith(_UNICODE_TEXT_BOMS):
            return False
        if b"\x00" in sample:
            return True

        control_count = sum(1 for byte in sample if byte in _BINARY_CONTROL_BYTES)
        return control_count / len(sample) > 0.03

    @staticmethod
    def _decode_text(data: bytes, filename: str) -> str:
        encodings = ["utf-8-sig"]
        if data.startswith(_UTF32_BOMS):
            encodings.append("utf-32")
        elif data.startswith(_UTF16_BOMS):
            encodings.append("utf-16")
        encodings.append("latin-1")

        for encoding in encodings:
            try:
                text = data.decode(encoding)
                return text.replace("\r\n", "\n").replace("\r", "\n")
            except UnicodeDecodeError:
                continue
        raise UnsupportedFileError(
            f"{filename} uses text encoding MeadowPy could not read."
        )

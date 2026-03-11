"""MeadowPy application controller."""

import sys
from pathlib import Path

from PyQt6.QtCore import QEvent, QObject, QRectF, Qt
from PyQt6.QtGui import QFont, QIcon, QPainterPath, QRegion
from PyQt6.QtWidgets import QApplication, QMenu, QWidget

from meadowpy.constants import APP_NAME, VERSION
from meadowpy.core.settings import Settings
from meadowpy.core.recent_files import RecentFilesManager
from meadowpy.core.file_manager import FileManager
from meadowpy.ui.main_window import MainWindow
from meadowpy.resources.resource_loader import get_icon_path, get_stylesheet

_MENU_RADIUS = 5  # must match QSS border-bottom-*-radius


def _rounded_bottom_region(rect: QRectF, r: int) -> QRegion:
    """Return a QRegion with sharp top corners and rounded bottom corners."""
    # Use a slightly larger radius for the mask so QSS anti-aliased
    # border paints fully inside the clipped area.
    mr = r + 1
    path = QPainterPath()
    path.moveTo(rect.topLeft())
    path.lineTo(rect.topRight())
    path.lineTo(rect.right(), rect.bottom() - mr)
    path.arcTo(rect.right() - 2 * mr, rect.bottom() - 2 * mr, 2 * mr, 2 * mr, 0, -90)
    path.lineTo(rect.left() + mr, rect.bottom())
    path.arcTo(rect.left(), rect.bottom() - 2 * mr, 2 * mr, 2 * mr, 270, -90)
    path.closeSubpath()
    return QRegion(path.toFillPolygon().toPolygon())


class _MenuRoundedMaskFilter(QObject):
    """App-level event filter that clips QMenu windows to rounded bottom corners.

    On every Resize / Show we apply a ``setMask()`` region so the OS-level
    window physically has rounded bottom corners instead of a sharp rectangle.
    """

    def eventFilter(self, obj, event):
        if isinstance(obj, QMenu):
            etype = event.type()
            if etype in (QEvent.Type.Show, QEvent.Type.Resize):
                region = _rounded_bottom_region(
                    QRectF(obj.rect()), _MENU_RADIUS
                )
                obj.setMask(region)
        return False


class MeadowPyApp:
    """Application controller. Sets up QApplication, loads settings, shows main window."""

    def __init__(self, argv: list[str]):
        self._qapp = QApplication(argv)
        self._qapp.setApplicationName(APP_NAME)
        self._qapp.setOrganizationName(APP_NAME)
        self._qapp.setApplicationVersion(VERSION)

        # Load UI font
        self._load_app_font()

        # Set app icon (prefer .ico on Windows for taskbar/title bar)
        self._set_app_icon()

        # Initialize core systems
        self._settings = Settings()
        self._settings.load()

        # Load stylesheet based on saved theme
        theme_name = self._settings.get("editor.theme")
        stylesheet = get_stylesheet(theme_name)
        if stylesheet:
            self._qapp.setStyleSheet(stylesheet)

        self._recent_files = RecentFilesManager(self._settings)
        self._file_manager = FileManager(self._settings, self._recent_files)

        # Create main window
        self._window = MainWindow(
            self._settings, self._file_manager, self._recent_files
        )

        # Clip menus to rounded bottom corners at the OS window level
        self._menu_filter = _MenuRoundedMaskFilter(self._qapp)
        self._qapp.installEventFilter(self._menu_filter)

        # Force Segoe UI on all widgets (QSS overrides QApplication.setFont)
        self._apply_font_to_all()

        # Handle files passed as command-line arguments
        for arg in argv[1:]:
            path = Path(arg)
            if path.is_file():
                content = self._file_manager.read_file(str(path))
                self._window.open_file_in_tab(str(path), content)

    def _set_app_icon(self) -> None:
        """Set the application window icon.

        Uses the .ico file on Windows (better taskbar rendering with
        multiple embedded sizes) and falls back to SVG otherwise.
        """
        import sys
        from pathlib import Path

        icons_dir = Path(__file__).parent / "resources" / "icons"

        # On Windows, prefer .ico for crisp taskbar / title-bar rendering
        if sys.platform == "win32":
            ico_path = icons_dir / "meadowpy.ico"
            if ico_path.exists():
                self._qapp.setWindowIcon(QIcon(str(ico_path)))
                # Set Windows AppUserModelID so the taskbar groups correctly
                try:
                    import ctypes
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                        "meadowpy.ide.meadowpy"
                    )
                except Exception:
                    pass
                return

        # Fallback: SVG / PNG via resource_loader
        icon_path = get_icon_path("meadowpy")
        if icon_path:
            self._qapp.setWindowIcon(QIcon(icon_path))

    def _load_app_font(self) -> None:
        """Set Segoe UI as the application default UI font."""
        self._app_font = QFont("Segoe UI", 10)
        self._qapp.setFont(self._app_font)

    def _apply_font_to_all(self) -> None:
        """Force Segoe UI onto every widget (overrides QSS font reset).

        QSS resets the font for any styled widget to the system default.
        We walk all children and explicitly set the font, skipping widgets
        that intentionally use a monospace font (output text, output input).
        """
        if self._app_font is None:
            return
        mono_names = {"outputText", "outputInput"}
        for widget in self._window.findChildren(QWidget):
            if widget.objectName() in mono_names:
                continue
            widget.setFont(self._app_font)

    def run(self) -> int:
        """Show main window and enter event loop."""
        self._window.show()
        return self._qapp.exec()

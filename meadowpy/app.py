"""MeadowPy application controller."""

import sys
from pathlib import Path

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtGui import QFont, QIcon, QKeyEvent, QKeySequence
from PyQt6.QtWidgets import QApplication, QMenu, QMenuBar, QWidget

from meadowpy.constants import APP_NAME, VERSION
from meadowpy.core.settings import Settings
from meadowpy.core.recent_files import RecentFilesManager
from meadowpy.core.file_manager import FileManager
from meadowpy.ui.main_window import MainWindow
from meadowpy.resources.resource_loader import get_icon_path, get_stylesheet

def _is_menubar_menu(menu: QMenu) -> bool:
    """Return True if *menu* is a direct dropdown of a QMenuBar."""
    parent = menu.parent()
    if isinstance(parent, QMenuBar):
        return True
    action = menu.menuAction()
    if action is not None:
        for widget in action.associatedObjects():
            if isinstance(widget, QMenuBar):
                return True
    return False


class _MenuRoundedMaskFilter(QObject):
    """App-level event filter that gives QMenu windows translucent backgrounds.

    This lets QSS border-radius paint smooth anti-aliased corners.
    Menubar dropdowns get a dynamic property so QSS can flatten the top corners.
    """

    def eventFilter(self, obj, event):
        if isinstance(obj, QMenu):
            if event.type() == QEvent.Type.Show:
                sharp_top = _is_menubar_menu(obj)
                obj.setProperty("menubarMenu", sharp_top)
                obj.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                obj.style().unpolish(obj)
                obj.style().polish(obj)
        return False


class _ClipboardShortcutFilter(QObject):
    """App-level event filter that routes clipboard shortcuts to the focused widget.

    QScintilla handles Ctrl+C/V/X/A internally, but other text widgets
    (QTextBrowser, QPlainTextEdit, QLineEdit) can have their clipboard
    shortcuts silently consumed by Qt's shortcut system.  This filter
    intercepts ShortcutOverride for those keys and accepts the event so
    the key press always reaches the focused widget's keyPressEvent.
    """

    _CLIPBOARD_KEYS = frozenset({
        QKeySequence.StandardKey.Copy,
        QKeySequence.StandardKey.Cut,
        QKeySequence.StandardKey.Paste,
        QKeySequence.StandardKey.SelectAll,
        QKeySequence.StandardKey.Undo,
        QKeySequence.StandardKey.Redo,
    })

    def eventFilter(self, obj, event):
        etype = event.type()
        if etype != QEvent.Type.ShortcutOverride:
            return False
        if not isinstance(event, QKeyEvent):
            return False

        # Only act when a non-QScintilla text widget has focus
        focus = QApplication.focusWidget()
        if focus is None:
            return False

        # Let QScintilla handle its own shortcuts
        from PyQt6.Qsci import QsciScintilla
        if isinstance(focus, QsciScintilla):
            return False

        # Check if this is a standard clipboard/edit key
        for key in self._CLIPBOARD_KEYS:
            if event.matches(key):
                event.accept()
                return True

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
        stylesheet = get_stylesheet(
            theme_name,
            custom_base=self._settings.get("editor.custom_theme.base"),
            custom_accent=self._settings.get("editor.custom_theme.accent"),
        )
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

        # Ensure clipboard shortcuts (Ctrl+C/V/X/A/Z/Y) always reach the
        # focused text widget instead of being consumed by QActions.
        self._clipboard_filter = _ClipboardShortcutFilter(self._qapp)
        self._qapp.installEventFilter(self._clipboard_filter)

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

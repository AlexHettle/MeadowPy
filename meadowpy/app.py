"""MeadowPy application controller."""

import sys
from time import perf_counter
from pathlib import Path

from PyQt6.QtCore import QEvent, QEventLoop, QObject, Qt, QTimer
from PyQt6.QtGui import QFont, QIcon, QKeyEvent, QKeySequence
from PyQt6.QtWidgets import QApplication, QMenu, QMenuBar, QWidget

from meadowpy.constants import APP_ID, APP_NAME, VERSION
from meadowpy.core.file_manager import FileManager
from meadowpy.core.recent_files import RecentFilesManager
from meadowpy.ui.main_window import MainWindow
from meadowpy.core.settings import Settings
from meadowpy.core.startup import remaining_delay_ms
from meadowpy.resources.resource_loader import get_icon_path, get_stylesheet
from meadowpy.ui.splash_screen import MeadowPySplashScreen

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

    _MINIMUM_SPLASH_SECONDS = 5.0

    def __init__(self, argv: list[str]):
        self._qapp = QApplication(argv)
        self._qapp.setApplicationName(APP_NAME)
        self._qapp.setOrganizationName(APP_NAME)
        self._qapp.setApplicationVersion(VERSION)

        # Load UI font
        self._load_app_font()

        # Set app icon (prefer .ico on Windows for taskbar/title bar)
        self._app_icon: QIcon | None = None
        self._set_app_icon()
        self._splash: MeadowPySplashScreen | None = None
        self._splash_started_at = perf_counter()
        self._show_splash("Initializing...")

        # Initialize core systems
        self._set_splash_status("Loading settings...")
        self._settings = Settings()
        self._settings.load()

        # Load stylesheet based on saved theme
        self._set_splash_status("Applying theme...")
        theme_name = self._settings.get("editor.theme")
        stylesheet = get_stylesheet(
            theme_name,
            custom_base=self._settings.get("editor.custom_theme.base"),
            custom_accent=self._settings.get("editor.custom_theme.accent"),
        )
        if stylesheet:
            self._qapp.setStyleSheet(stylesheet)

        self._set_splash_status("Preparing workspace...")
        self._recent_files = RecentFilesManager(self._settings)
        self._file_manager = FileManager(self._settings, self._recent_files)

        # Create main window
        self._set_splash_status("Building interface...")
        self._window = MainWindow(
            self._settings,
            self._file_manager,
            self._recent_files,
            app_icon=self._app_icon,
        )
        # Also set the icon on the window itself — on Windows the taskbar
        # entry sometimes uses the per-window icon rather than QApplication's.
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
        self._set_splash_status("Opening files...")
        for arg in argv[1:]:
            path = Path(arg)
            if path.is_file():
                content = self._file_manager.read_file(str(path))
                self._window.open_file_in_tab(str(path), content)

        self._set_splash_status("Finalizing startup...")

    def _set_app_icon(self) -> None:
        """Set the application window icon.

        Builds a multi-size QIcon from every available source so Windows can
        pick the best match for the taskbar, alt-tab, and title bar.
        """
        from pathlib import Path
        from PyQt6.QtGui import QPixmap

        icons_dir = Path(__file__).parent / "resources" / "icons"
        icon = QIcon()

        # Add the .ico (carries multiple embedded sizes — best for Windows)
        ico_path = icons_dir / "meadowpy.ico"
        if ico_path.exists():
            icon.addFile(str(ico_path))

        # Add the high-res PNG and explicitly register common sizes so Qt
        # always has a crisp source to scale from.
        png_path = icons_dir / "meadowpy_256.png"
        if png_path.exists():
            base = QPixmap(str(png_path))
            for size in (16, 24, 32, 48, 64, 128, 256):
                icon.addPixmap(base.scaled(
                    size, size,
                    aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio,
                    transformMode=Qt.TransformationMode.SmoothTransformation,
                ))

        # Fallback to SVG resource if neither file existed
        if icon.isNull():
            svg_path = get_icon_path("meadowpy")
            if svg_path:
                icon = QIcon(svg_path)

        if not icon.isNull():
            self._app_icon = icon
            self._qapp.setWindowIcon(icon)
            if sys.platform == "win32":
                try:
                    import ctypes
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                        APP_ID
                    )
                except Exception:
                    pass
        else:
            self._app_icon = None

    def _load_app_font(self) -> None:
        """Set Segoe UI as the application default UI font."""
        self._app_font = QFont("Segoe UI", 10)
        self._qapp.setFont(self._app_font)

    def _show_splash(self, message: str) -> None:
        """Create and display the startup splash screen."""
        self._splash = MeadowPySplashScreen(self._app_icon, VERSION)
        self._splash.set_status_text(message)
        self._splash.center_on_screen()
        self._splash.show()
        self._splash_started_at = perf_counter()
        self._process_pending_ui_events()

    def _set_splash_status(self, message: str) -> None:
        """Update the splash screen's loading message."""
        if self._splash is None:
            return
        self._splash.set_status_text(message)
        self._process_pending_ui_events()

    def _process_pending_ui_events(self) -> None:
        """Let Qt paint the splash screen during startup work."""
        self._qapp.processEvents()

    def _wait_for_minimum_splash_time(self) -> None:
        """Keep the splash visible until the minimum display time has elapsed."""
        if self._splash is None:
            return

        remaining_ms = remaining_delay_ms(
            self._splash_started_at,
            self._MINIMUM_SPLASH_SECONDS,
        )
        if remaining_ms <= 0:
            return

        loop = QEventLoop()
        QTimer.singleShot(remaining_ms, loop.quit)
        loop.exec()

    def _close_splash(self) -> None:
        """Close the splash screen once the main window is ready."""
        if self._splash is None:
            return
        self._splash.close()
        self._splash = None

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
        self._set_splash_status("Launching MeadowPy...")
        self._wait_for_minimum_splash_time()
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()
        self._process_pending_ui_events()
        self._close_splash()
        return self._qapp.exec()

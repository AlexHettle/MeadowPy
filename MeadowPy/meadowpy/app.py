"""MeadowPy application controller."""

import sys
from time import perf_counter
from pathlib import Path

from PyQt6.QtCore import (
    QEvent,
    QEventLoop,
    QObject,
    Qt,
    QtMsgType,
    QTimer,
    qInstallMessageHandler,
)
from PyQt6.QtGui import QFont, QIcon, QKeyEvent
from PyQt6.QtWidgets import QApplication, QMenu, QMenuBar, QWidget

from meadowpy.constants import APP_ID, APP_NAME, CONFIG_DIR_NAME, VERSION
from meadowpy.core.file_manager import FileManager
from meadowpy.core.process_runner import sweep_selection_temp_files
from meadowpy.core.recent_files import RecentFilesManager
from meadowpy.core.shortcuts import (
    STANDARD_EDIT_SHORTCUTS,
    event_matches_shortcut,
    get_default_shortcut,
    get_shortcut,
    shortcut_from_key_event,
)
from meadowpy.ui.main_window import MainWindow
from meadowpy.core.settings import Settings
from meadowpy.core.startup import remaining_delay_ms
from meadowpy.resources.resource_loader import get_icon_path, get_stylesheet
from meadowpy.ui.splash_screen import MeadowPySplashScreen


def _install_qt_message_logger():
    """Mirror native Qt warnings to MeadowPy's runtime log."""
    log_path = Path.home() / CONFIG_DIR_NAME / "meadowpy.log"

    def _handler(mode, context, message):
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            location = ""
            if context is not None and context.file:
                location = f" ({context.file}:{context.line})"
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n[qt:{mode.name}]{location} {message}\n")
        except Exception:
            pass

        if mode in {
            QtMsgType.QtWarningMsg,
            QtMsgType.QtCriticalMsg,
            QtMsgType.QtFatalMsg,
        }:
            print(message, file=sys.stderr)

    qInstallMessageHandler(_handler)
    return _handler


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
    """App-level event filter that prepares QMenu windows for styled popups.

    QSS menu surfaces render more predictably when the native popup background,
    hard masks, and rectangular window shadow stay out of the way. Menubar
    dropdowns get a dynamic property for theme-specific edge treatment.
    """

    def eventFilter(self, obj, event):
        if isinstance(obj, QMenu):
            if event.type() in (
                QEvent.Type.Polish,
                QEvent.Type.Show,
                QEvent.Type.Resize,
            ):
                sharp_top = _is_menubar_menu(obj)
                obj.setProperty("menubarMenu", sharp_top)
                if event.type() == QEvent.Type.Polish or not obj.isVisible():
                    obj.setWindowFlag(
                        Qt.WindowType.NoDropShadowWindowHint,
                        True,
                    )
                obj.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
                obj.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                obj.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
                obj.setAutoFillBackground(False)
                obj.clearMask()
                if event.type() == QEvent.Type.Show:
                    obj.style().unpolish(obj)
                    obj.style().polish(obj)
        return False


class _ClipboardShortcutFilter(QObject):
    """App-level event filter that routes edit shortcuts to the focused widget.

    QScintilla handles Ctrl+C/V/X/A internally, but other text widgets
    (QTextBrowser, QPlainTextEdit, QLineEdit) can have their clipboard
    shortcuts silently consumed by Qt's shortcut system. This filter also
    honors custom shortcuts for standard edit commands.
    """

    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        self._settings = settings

    def eventFilter(self, obj, event):
        etype = event.type()
        if etype not in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress):
            return False
        if not isinstance(event, QKeyEvent):
            return False

        # Only act when a text-like widget has focus.
        focus = QApplication.focusWidget()
        if focus is None:
            return False
        if not self._focused_widget_supports_edit_shortcuts(focus):
            return False

        if etype == QEvent.Type.ShortcutOverride:
            if self._event_matches_active_edit_shortcut(event):
                event.accept()
                return True
            return False

        shortcut_text = shortcut_from_key_event(event)
        if not shortcut_text:
            return False

        handled_id = self._edit_shortcut_id_for_event(event)
        if handled_id:
            method_name, _standard_key = STANDARD_EDIT_SHORTCUTS[handled_id]
            method = getattr(focus, method_name, None)
            if callable(method):
                method()
                return True

        if self._event_matches_reassigned_default(event):
            return True
        return False

    def _focused_widget_supports_edit_shortcuts(self, widget) -> bool:
        return any(
            hasattr(widget, method_name)
            for method_name, _standard_key in STANDARD_EDIT_SHORTCUTS.values()
        )

    def _event_matches_active_edit_shortcut(self, event: QKeyEvent) -> bool:
        return self._edit_shortcut_id_for_event(event) is not None

    def _edit_shortcut_id_for_event(self, event: QKeyEvent) -> str | None:
        for shortcut_id in STANDARD_EDIT_SHORTCUTS:
            if event_matches_shortcut(
                event,
                get_shortcut(self._settings, shortcut_id),
            ):
                return shortcut_id
        return None

    def _event_matches_reassigned_default(self, event: QKeyEvent) -> bool:
        """Block stale native defaults after users move them elsewhere."""
        for shortcut_id in STANDARD_EDIT_SHORTCUTS:
            default = get_default_shortcut(shortcut_id)
            active = get_shortcut(self._settings, shortcut_id)
            if active != default and event_matches_shortcut(event, default):
                return True
        return False


class MeadowPyApp:
    """Application controller. Sets up QApplication, loads settings, shows main window."""

    _MINIMUM_SPLASH_SECONDS = 1.5

    def __init__(self, argv: list[str]):
        self._qapp = QApplication(argv)
        self._qt_message_handler = _install_qt_message_logger()
        self._qapp.setApplicationName(APP_NAME)
        self._qapp.setOrganizationName(APP_NAME)
        self._qapp.setApplicationVersion(VERSION)

        # Load UI font
        self._load_app_font()

        # Set app icon (prefer .ico on Windows for taskbar/title bar)
        self._app_icon: QIcon | None = None
        self._app_icon_path: Path | None = None
        self._set_app_icon()
        self._splash: MeadowPySplashScreen | None = None
        self._splash_started_at = perf_counter()
        self._show_splash("Initializing...")

        # Initialize core systems
        self._set_splash_status("Loading settings...")
        self._settings = Settings()
        self._settings.load()
        sweep_selection_temp_files()

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
        self._clipboard_filter = _ClipboardShortcutFilter(
            self._settings,
            self._qapp,
        )
        self._qapp.installEventFilter(self._clipboard_filter)

        # Force Segoe UI on all widgets (QSS overrides QApplication.setFont)
        self._apply_font_to_all()

        # Handle files passed as command-line arguments
        self._set_splash_status("Opening files...")
        for arg in argv[1:]:
            path = Path(arg)
            if path.is_file():
                reader = getattr(self._window, "_read_editor_file", None)
                try:
                    if callable(reader):
                        read_result = reader(str(path))
                    else:
                        read_result = (
                            self._file_manager.read_file(str(path)),
                            False,
                        )
                except OSError:
                    continue
                if read_result is None:
                    continue
                content, large_file_mode = read_result
                self._window.open_file_in_tab(
                    str(path),
                    content,
                    large_file_mode=large_file_mode,
                )
                self._recent_files.add(str(path))

        self._set_splash_status("Finalizing startup...")

    def _set_app_icon(self) -> None:
        """Set the application window icon.

        Builds a multi-size QIcon from every available source so Windows can
        pick the best match for the taskbar, alt-tab, and title bar.
        """
        from PyQt6.QtGui import QPixmap

        icons_dir = Path(__file__).parent / "resources" / "icons"
        icon = QIcon()

        # Add the .ico (carries multiple embedded sizes — best for Windows)
        ico_path = icons_dir / "meadowpy.ico"
        if ico_path.exists():
            self._app_icon_path = ico_path
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

    def _apply_native_app_icon(self, widget: QWidget | None) -> None:
        """Push MeadowPy's .ico onto a native Windows window handle.

        Qt usually propagates QApplication/window icons correctly, but
        Windows can briefly associate a pythonw.exe window with a generic
        icon during first-run startup. Sending WM_SETICON after the HWND
        exists makes the taskbar/title-bar icon deterministic.
        """
        icon_path_obj = getattr(self, "_app_icon_path", None)
        if (
            sys.platform != "win32"
            or widget is None
            or icon_path_obj is None
        ):
            return

        try:
            import ctypes
            from ctypes import wintypes

            hwnd = int(widget.winId())
            if not hwnd:
                return

            user32 = ctypes.windll.user32
            user32.LoadImageW.argtypes = [
                wintypes.HINSTANCE,
                wintypes.LPCWSTR,
                wintypes.UINT,
                ctypes.c_int,
                ctypes.c_int,
                wintypes.UINT,
            ]
            user32.LoadImageW.restype = wintypes.HANDLE
            user32.SendMessageW.argtypes = [
                wintypes.HWND,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
            ]
            user32.SendMessageW.restype = wintypes.LPARAM

            image_icon = 1
            lr_load_from_file = 0x0010
            lr_shared = 0x8000
            wm_seticon = 0x0080
            icon_small = 0
            icon_big = 1
            icon_small2 = 2
            sm_cxicon = 11
            sm_cyicon = 12
            sm_cxsmicon = 49
            sm_cysmicon = 50
            flags = lr_load_from_file | lr_shared
            icon_path = str(icon_path_obj)

            big_icon = user32.LoadImageW(
                None,
                icon_path,
                image_icon,
                user32.GetSystemMetrics(sm_cxicon),
                user32.GetSystemMetrics(sm_cyicon),
                flags,
            )
            small_icon = user32.LoadImageW(
                None,
                icon_path,
                image_icon,
                user32.GetSystemMetrics(sm_cxsmicon),
                user32.GetSystemMetrics(sm_cysmicon),
                flags,
            )

            if big_icon:
                user32.SendMessageW(hwnd, wm_seticon, icon_big, int(big_icon))
            if small_icon:
                user32.SendMessageW(hwnd, wm_seticon, icon_small, int(small_icon))
                user32.SendMessageW(hwnd, wm_seticon, icon_small2, int(small_icon))
        except Exception:
            pass

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
        self._apply_native_app_icon(self._splash)
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
        mono_names = {"codeEditor", "outputText", "outputInput"}
        for widget in self._window.findChildren(QWidget):
            if widget.objectName() in mono_names:
                continue
            widget.setFont(self._app_font)

    def run(self) -> int:
        """Show main window and enter event loop."""
        self._set_splash_status("Launching MeadowPy...")
        self._wait_for_minimum_splash_time()
        self._window.show()
        self._apply_native_app_icon(self._window)
        self._window.raise_()
        self._window.activateWindow()
        self._process_pending_ui_events()
        self._close_splash()
        recover_unsaved_work = getattr(
            self._window,
            "recover_unsaved_work",
            None,
        )
        if callable(recover_unsaved_work):
            recover_unsaved_work()
        exit_code = self._qapp.exec()
        self._teardown_qt_objects()
        return exit_code

    def _teardown_qt_objects(self) -> None:
        """Destroy top-level Qt objects before Python interpreter shutdown."""
        try:
            qInstallMessageHandler(None)
        except Exception:
            pass
        self._qt_message_handler = None

        if self._splash is not None:
            try:
                self._splash.close()
                self._splash.deleteLater()
            except RuntimeError:
                pass
            self._splash = None

        window = getattr(self, "_window", None)
        if window is not None:
            try:
                if window.isVisible():
                    window.close()
            except RuntimeError:
                pass
            try:
                window.deleteLater()
            except RuntimeError:
                pass
            self._window = None

        for attr in ("_menu_filter", "_clipboard_filter"):
            event_filter = getattr(self, attr, None)
            if event_filter is not None:
                try:
                    self._qapp.removeEventFilter(event_filter)
                except RuntimeError:
                    pass
                setattr(self, attr, None)

        try:
            self._qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            self._qapp.processEvents()
        except RuntimeError:
            pass

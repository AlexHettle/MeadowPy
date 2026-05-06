"""MeadowPy IDE entry point."""

import faulthandler
import sys
from pathlib import Path

from meadowpy.constants import APP_ID, CONFIG_DIR_NAME


_CRASH_LOG_FILE = None


def _enable_crash_logging() -> None:
    """Write fatal native crash tracebacks to MeadowPy's runtime log."""
    global _CRASH_LOG_FILE
    try:
        log_path = Path.home() / CONFIG_DIR_NAME / "meadowpy.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        _CRASH_LOG_FILE = open(log_path, "a", encoding="utf-8", buffering=1)
        _CRASH_LOG_FILE.write("\n--- MeadowPy process started ---\n")
        faulthandler.enable(file=_CRASH_LOG_FILE, all_threads=True)
    except Exception:
        _CRASH_LOG_FILE = None


def _set_windows_app_id() -> None:
    # Must run before any Qt import so Windows associates the taskbar
    # entry with our app rather than the host python.exe.
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            APP_ID
        )
    except Exception:
        pass


_enable_crash_logging()
_set_windows_app_id()

from meadowpy.app import MeadowPyApp


def main():
    app = MeadowPyApp(sys.argv)
    exit_code = app.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

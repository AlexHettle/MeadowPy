"""MeadowPy IDE entry point."""

import sys

from meadowpy.constants import APP_ID


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


_set_windows_app_id()

from meadowpy.app import MeadowPyApp


def main():
    app = MeadowPyApp(sys.argv)
    exit_code = app.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

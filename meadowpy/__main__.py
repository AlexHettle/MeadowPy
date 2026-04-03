"""MeadowPy IDE entry point."""

import sys
from meadowpy.app import MeadowPyApp


def main():
    app = MeadowPyApp(sys.argv)
    exit_code = app.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

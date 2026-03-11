"""Python interpreter detection and virtual environment management."""

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class InterpreterInfo:
    """Describes a detected Python interpreter."""

    path: str       # Full path to python executable
    version: str    # e.g. "3.11.5"
    label: str      # Display name, e.g. "System Python 3.11.5"
    is_venv: bool


class InterpreterManager:
    """Detects Python interpreters and manages virtual environments."""

    # ------------------------------------------------------------------
    # Interpreter detection
    # ------------------------------------------------------------------

    def detect_interpreters(
        self, file_path: str | None = None
    ) -> list[InterpreterInfo]:
        """Return a list of available Python interpreters.

        Always includes the system Python (the one running MeadowPy).
        Also scans for .venv / venv directories near *file_path*.
        """
        found: list[InterpreterInfo] = []

        # 1. System Python (the interpreter running MeadowPy itself)
        system_py = sys.executable
        version = self._get_version(system_py)
        found.append(
            InterpreterInfo(
                path=system_py,
                version=version,
                label=f"System Python {version}",
                is_venv=False,
            )
        )

        # 2. Scan for venvs near the file
        if file_path:
            seen_paths: set[str] = {str(Path(system_py).resolve())}
            venv_names = [".venv", "venv", "env"]
            directory = Path(file_path).parent
            # Walk up to 3 parent levels
            for _ in range(4):
                for vname in venv_names:
                    venv_dir = directory / vname
                    py = self._venv_python(venv_dir)
                    if py and str(py.resolve()) not in seen_paths:
                        seen_paths.add(str(py.resolve()))
                        ver = self._get_version(str(py))
                        rel = self._relative_label(venv_dir, file_path)
                        found.append(
                            InterpreterInfo(
                                path=str(py),
                                version=ver,
                                label=f"venv ({rel}) Python {ver}",
                                is_venv=True,
                            )
                        )
                parent = directory.parent
                if parent == directory:
                    break
                directory = parent

        return found

    def get_interpreter(
        self, settings, file_path: str | None = None
    ) -> str:
        """Resolve the effective interpreter path from settings."""
        configured = settings.get("run.python_interpreter")
        if configured and Path(configured).is_file():
            return configured
        return sys.executable

    # ------------------------------------------------------------------
    # Virtual environment creation
    # ------------------------------------------------------------------

    def create_venv(
        self, base_dir: str, venv_name: str, interpreter: str
    ) -> str:
        """Create a virtual environment and return its path.

        Runs ``interpreter -m venv <base_dir>/<venv_name>``.
        Raises subprocess.CalledProcessError on failure.
        """
        venv_path = Path(base_dir) / venv_name
        subprocess.run(
            [interpreter, "-m", "venv", str(venv_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return str(venv_path)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _venv_python(venv_dir: Path) -> Path | None:
        """Return the python executable inside a venv, or None."""
        # Windows
        candidate = venv_dir / "Scripts" / "python.exe"
        if candidate.is_file():
            return candidate
        # Unix
        candidate = venv_dir / "bin" / "python"
        if candidate.is_file():
            return candidate
        return None

    @staticmethod
    def _get_version(interpreter_path: str) -> str:
        """Query the Python version string, e.g. '3.11.5'."""
        try:
            result = subprocess.run(
                [interpreter_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Output is "Python 3.11.5\n"
            parts = result.stdout.strip().split()
            if len(parts) >= 2:
                return parts[1]
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        return "unknown"

    @staticmethod
    def _relative_label(venv_dir: Path, file_path: str) -> str:
        """Create a short label like './.venv' relative to file."""
        try:
            rel = venv_dir.relative_to(Path(file_path).parent)
            return f"./{rel}"
        except ValueError:
            return str(venv_dir)

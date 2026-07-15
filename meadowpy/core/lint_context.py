"""Resolve safe, project-aware execution settings for source-code linting."""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SUPPORTED_LINTERS = frozenset({"flake8", "pylint"})
CONFIG_MODES = frozenset({"defaults", "auto", "explicit"})
INTERPRETER_MODES = frozenset({"selected", "meadowpy", "custom"})
WORKING_DIRECTORY_MODES = frozenset({"project", "file"})
MAX_CONFIG_BYTES = 1024 * 1024

_FLAKE8_CONFIG_NAMES = ("setup.cfg", "tox.ini", ".flake8")
_PYLINT_CONFIG_NAMES = (
    "pylintrc",
    "pylintrc.toml",
    ".pylintrc",
    ".pylintrc.toml",
    "pyproject.toml",
    "setup.cfg",
    "tox.ini",
)
_SECTION_PATTERN = re.compile(
    r"^\s*\[\s*([^\]]+?)\s*\]\s*(?:[#;].*)?$", re.MULTILINE
)
_PYLINT_RC_SECTIONS = frozenset(
    {
        "basic",
        "classes",
        "design",
        "exceptions",
        "format",
        "imports",
        "logging",
        "main",
        "master",
        "messages control",
        "miscellaneous",
        "refactoring",
        "reports",
        "similarities",
        "spelling",
        "string",
        "typecheck",
        "variables",
    }
)


class LintContextError(ValueError):
    """Raised when lint execution settings cannot be resolved safely."""


@dataclass(frozen=True, slots=True)
class LintExecutionContext:
    """Fully resolved, immutable context for one lint subprocess."""

    interpreter: str
    cwd: str
    display_name: str
    config_mode: str
    config_path: str | None
    isolated: bool
    trusted: bool
    timeout_seconds: int


def resolve_lint_context(
    settings: Any,
    interpreter_manager: Any,
    linter: str,
    file_path: str | None,
    project_root: str | None,
) -> LintExecutionContext:
    """Return the effective execution context for a Flake8 or Pylint run.

    Project interpreters, working directories, and configuration files are
    honored only when the effective project/file root is trusted. Untrusted
    files are linted with MeadowPy's interpreter from an application-owned
    working directory and with external configuration discovery disabled.
    """

    normalized_linter = str(linter).strip().lower()
    if normalized_linter not in SUPPORTED_LINTERS:
        raise LintContextError(
            f"Unsupported linter '{linter}'. Choose Flake8 or Pylint."
        )

    resolved_file = _canonical_file(file_path)
    resolved_project = _canonical_directory(project_root)
    effective_root = _effective_root(resolved_file, resolved_project)
    trusted_root = _matching_trusted_root(settings, effective_root)
    trusted = trusted_root is not None
    timeout_seconds = _resolve_timeout(settings, normalized_linter)

    if not trusted:
        cwd = _safe_runtime_directory()
        return LintExecutionContext(
            interpreter=sys.executable,
            cwd=str(cwd),
            display_name=_display_name(resolved_file, cwd),
            config_mode="defaults",
            config_path=None,
            isolated=True,
            trusted=False,
            timeout_seconds=timeout_seconds,
        )

    interpreter = _resolve_interpreter(
        settings, interpreter_manager, file_path
    )
    cwd = _resolve_working_directory(
        settings, resolved_file, effective_root
    )
    config_mode, config_path, isolated = _resolve_config(
        settings=settings,
        linter=normalized_linter,
        file_path=resolved_file,
        effective_root=effective_root,
        trusted_root=trusted_root,
    )

    return LintExecutionContext(
        interpreter=interpreter,
        cwd=str(cwd),
        display_name=_display_name(resolved_file, cwd),
        config_mode=config_mode,
        config_path=str(config_path) if config_path is not None else None,
        isolated=isolated,
        trusted=True,
        timeout_seconds=timeout_seconds,
    )


def _get_setting(settings: Any, key: str, default: Any) -> Any:
    getter = getattr(settings, "get", None)
    if not callable(getter):
        raise LintContextError("Lint settings are unavailable.")
    try:
        return getter(key, default)
    except TypeError:
        value = getter(key)
        return default if value is None else value


def _canonical_file(file_path: str | None) -> Path | None:
    if not file_path:
        return None
    try:
        return Path(file_path).expanduser().resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise LintContextError(
            f"Cannot resolve the file path '{file_path}': {exc}"
        ) from exc


def _canonical_directory(directory: str | None) -> Path | None:
    if not directory:
        return None
    try:
        resolved = Path(directory).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    return resolved if resolved.is_dir() else None


def _effective_root(
    file_path: Path | None, project_root: Path | None
) -> Path | None:
    if file_path is not None:
        if project_root is not None and _contains(project_root, file_path):
            return project_root
        return file_path.parent
    return project_root


def _matching_trusted_root(
    settings: Any, effective_root: Path | None
) -> Path | None:
    if effective_root is None:
        return None
    configured = _get_setting(settings, "security.trusted_lint_roots", [])
    if not isinstance(configured, (list, tuple)):
        return None

    matches: list[Path] = []
    for value in configured:
        if not isinstance(value, (str, os.PathLike)) or not value:
            continue
        trusted_root = _canonical_directory(str(value))
        if trusted_root is not None and _contains(
            trusted_root, effective_root
        ):
            matches.append(trusted_root)
    if not matches:
        return None
    return max(matches, key=lambda path: len(path.parts))


def _contains(root: Path, candidate: Path) -> bool:
    """Return whether canonical *candidate* is at or below canonical *root*."""

    normalized_root = os.path.normcase(os.path.normpath(str(root)))
    normalized_candidate = os.path.normcase(os.path.normpath(str(candidate)))
    try:
        return os.path.commonpath(
            [normalized_root, normalized_candidate]
        ) == normalized_root
    except ValueError:
        return False


def _safe_runtime_directory() -> Path:
    if sys.executable:
        try:
            executable_parent = Path(sys.executable).resolve(strict=False).parent
            if executable_parent.is_dir():
                return executable_parent
        except (OSError, RuntimeError):
            pass
    return Path(__file__).resolve().parent


def _resolve_interpreter(
    settings: Any, interpreter_manager: Any, file_path: str | None
) -> str:
    raw_mode = _get_setting(
        settings, "editor.lint_interpreter_mode", "selected"
    )
    mode = str(raw_mode).strip().lower()
    if mode not in INTERPRETER_MODES:
        raise LintContextError(
            "Invalid lint interpreter mode. Choose selected, MeadowPy, or "
            "custom."
        )
    if mode == "meadowpy":
        return sys.executable
    if mode == "selected":
        try:
            interpreter = interpreter_manager.get_interpreter(
                settings, file_path
            )
        except (
            AttributeError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
            raise LintContextError(
                f"Could not resolve the selected Python interpreter: {exc}"
            ) from exc
        if not interpreter:
            raise LintContextError(
                "No selected Python interpreter is available for linting."
            )
        return str(interpreter)

    configured = _get_setting(settings, "editor.lint_interpreter_path", "")
    if not isinstance(configured, (str, os.PathLike)) or not configured:
        raise LintContextError(
            "Choose an existing Python executable for the custom lint "
            "interpreter."
        )
    try:
        interpreter_path = Path(configured).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise LintContextError(
            f"The custom lint interpreter does not exist: {configured}"
        ) from exc
    if not interpreter_path.is_file():
        raise LintContextError(
            f"The custom lint interpreter is not a file: {interpreter_path}"
        )
    return str(interpreter_path)


def _resolve_working_directory(
    settings: Any, file_path: Path | None, effective_root: Path | None
) -> Path:
    raw_mode = _get_setting(
        settings, "editor.lint_working_directory", "project"
    )
    mode = str(raw_mode).strip().lower()
    if mode not in WORKING_DIRECTORY_MODES:
        raise LintContextError(
            "Invalid lint working directory. Choose project or file."
        )
    if mode == "file" and file_path is not None:
        return file_path.parent
    if effective_root is not None:
        return effective_root
    return _safe_runtime_directory()


def _resolve_timeout(settings: Any, linter: str) -> int:
    default = 10 if linter == "flake8" else 15
    raw_timeout = _get_setting(
        settings, f"editor.lint_{linter}_timeout_seconds", default
    )
    if isinstance(raw_timeout, bool):
        raise LintContextError("The lint timeout must be from 1 to 120 seconds.")
    if isinstance(raw_timeout, float) and not raw_timeout.is_integer():
        raise LintContextError(
            "The lint timeout must be a whole number from 1 to 120 seconds."
        )
    try:
        timeout = int(raw_timeout)
    except (TypeError, ValueError) as exc:
        raise LintContextError(
            "The lint timeout must be a whole number from 1 to 120 seconds."
        ) from exc
    if timeout < 1 or timeout > 120:
        raise LintContextError("The lint timeout must be from 1 to 120 seconds.")
    return timeout


def _resolve_config(
    *,
    settings: Any,
    linter: str,
    file_path: Path | None,
    effective_root: Path | None,
    trusted_root: Path,
) -> tuple[str, Path | None, bool]:
    raw_mode = _get_setting(
        settings, f"editor.lint_{linter}_config_mode", "defaults"
    )
    mode = str(raw_mode).strip().lower()
    if mode not in CONFIG_MODES:
        raise LintContextError(
            "Invalid lint configuration mode. Choose defaults, auto, or "
            "explicit."
        )
    if mode == "defaults":
        return mode, None, True
    if effective_root is None:
        return "defaults", None, True

    if mode == "auto":
        start_directory = file_path.parent if file_path else effective_root
        config_path = _discover_config(
            linter, start_directory, effective_root
        )
        return mode, config_path, config_path is None

    configured = _get_setting(
        settings, f"editor.lint_{linter}_config_path", ""
    )
    if not isinstance(configured, (str, os.PathLike)) or not configured:
        raise LintContextError(
            f"Choose an existing {linter.title()} configuration file."
        )
    configured_path = Path(configured).expanduser()
    if not configured_path.is_absolute():
        raise LintContextError(
            f"The {linter.title()} configuration path must be absolute."
        )
    try:
        config_path = configured_path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise LintContextError(
            f"The {linter.title()} configuration file does not exist: "
            f"{configured}"
        ) from exc
    if not config_path.is_file():
        raise LintContextError(
            f"The {linter.title()} configuration path is not a file: "
            f"{config_path}"
        )
    if not _contains(trusted_root, config_path):
        raise LintContextError(
            f"The {linter.title()} configuration must be inside a trusted "
            "project root."
        )
    return mode, config_path, False


def _discover_config(
    linter: str, start_directory: Path, boundary: Path
) -> Path | None:
    """Find a relevant config without walking above *boundary* or executing it."""

    if not _contains(boundary, start_directory):
        return None
    names = (
        _FLAKE8_CONFIG_NAMES
        if linter == "flake8"
        else _PYLINT_CONFIG_NAMES
    )
    current = start_directory
    while _contains(boundary, current):
        for name in names:
            candidate = current / name
            if _is_relevant_config(linter, candidate, boundary):
                return candidate.resolve(strict=True)
        if _same_path(current, boundary):
            break
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _is_relevant_config(linter: str, path: Path, boundary: Path) -> bool:
    try:
        resolved = path.resolve(strict=True)
        if not resolved.is_file() or not _contains(boundary, resolved):
            return False
        if resolved.stat().st_size > MAX_CONFIG_BYTES:
            return False
        text = resolved.read_text(encoding="utf-8")
    except (OSError, RuntimeError, UnicodeError):
        return False
    if linter == "pylint" and resolved.name.casefold() in {
        "pylintrc",
        ".pylintrc",
    }:
        # A sectionless rcfile is still meaningful: it stops Pylint from
        # inheriting a configuration found higher in the project tree.
        return True
    sections = {
        match.group(1).strip().casefold()
        for match in _SECTION_PATTERN.finditer(text)
    }
    if linter == "flake8":
        return bool(sections & {"flake8", "flake8:local-plugins"})
    return _has_pylint_section(resolved.name.casefold(), sections)


def _has_pylint_section(filename: str, sections: set[str]) -> bool:
    if filename in {"pyproject.toml", "pylintrc.toml", ".pylintrc.toml"}:
        return any(
            section == "tool.pylint" or section.startswith("tool.pylint.")
            for section in sections
        )
    if filename in {"setup.cfg", "tox.ini"}:
        return any(
            section == "pylint" or section.startswith("pylint.")
            for section in sections
        )
    normalized_sections = {
        section.replace("_", " ").replace("-", " ")
        for section in sections
    }
    return bool(normalized_sections & _PYLINT_RC_SECTIONS) or any(
        section == "pylint"
        or section.startswith("pylint.")
        or section == "tool.pylint"
        or section.startswith("tool.pylint.")
        for section in sections
    )


def _same_path(first: Path, second: Path) -> bool:
    return os.path.normcase(os.path.normpath(str(first))) == os.path.normcase(
        os.path.normpath(str(second))
    )


def _display_name(file_path: Path | None, cwd: Path) -> str:
    if file_path is None:
        return "untitled.py"
    if _contains(cwd, file_path):
        try:
            return str(file_path.relative_to(cwd))
        except ValueError:
            pass
    return str(file_path)

"""Linting integration — runs flake8 or pylint as a subprocess."""

import re
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from meadowpy.core.qt_threads import stop_qthread

if TYPE_CHECKING:
    from meadowpy.core.lint_context import LintExecutionContext


FLAKE8_NON_STYLE_CODES = frozenset({"E901", "E902", "E999"})
FLAKE8_OUTPUT_FORMAT = "%(path)s:%(row)d:%(col)d: %(code)s %(text)s"
FLAKE8_FAILURE_MARKERS = (
    "critical error during execution of flake8",
    "failedtoloadplugin",
    "flake8 failed to load plugin",
    "pluginexecutionfailed",
)
FLAKE8_OUTPUT_PATTERN = re.compile(
    r"^.+?:(\d+):(\d+):\s+(\w+)\s+(.+)$"
)
PYLINT_STYLE_WARNING_CODES = frozenset({"W0301", "W0311", "W0312", "W0313"})
LINTER_TEST_SOURCE = '"""MeadowPy linter settings test."""\n'


class _LintCancelled(Exception):
    """Internal signal used when a stale lint subprocess is stopped."""


def build_linter_config_args(
    linter: str, context: "LintExecutionContext | None"
) -> list[str]:
    """Return command-line arguments for the resolved config policy."""
    if context is None:
        return []
    if linter not in {"flake8", "pylint"}:
        raise ValueError(f"Unsupported linter: {linter}")
    if context.isolated:
        if linter == "flake8":
            return ["--isolated"]
        # An explicitly empty rcfile disables Pylint's native discovery.
        return ["--rcfile="]
    if not context.config_path:
        return []
    option = "--config" if linter == "flake8" else "--rcfile"
    return [option, context.config_path]


def build_linter_stdin_command(
    linter: str,
    context: "LintExecutionContext",
    *,
    smoke_test: bool = False,
) -> tuple[str, list[str], str]:
    """Build a stdin lint command from a fully resolved execution context."""
    args = ["-m", linter]
    args.extend(build_linter_config_args(linter, context))
    if linter == "flake8":
        args.append(f"--format={FLAKE8_OUTPUT_FORMAT}")
        if smoke_test:
            # Ordinary findings become success; startup/config failures do not.
            args.append("--exit-zero")
        args.extend(["--stdin-display-name", context.display_name, "-"])
    elif linter == "pylint":
        args.extend(
            [
                "--from-stdin",
                context.display_name,
                "--output-format=text",
                "--msg-template={line}:{column}: {msg_id} {msg}",
            ]
        )
    else:
        raise ValueError(f"Unsupported linter: {linter}")
    return context.interpreter, args, context.cwd


def lint_test_exit_succeeded(
    linter: str, exit_code: int, output: str = ""
) -> bool:
    """Return whether a smoke lint ran, regardless of ordinary findings."""
    if linter == "flake8":
        return (
            exit_code == 0
            and not _has_flake8_execution_failure(output)
        )
    if linter == "pylint":
        # Pylint combines status bits. Fatal (1) and usage (32) mean the
        # environment/config could not lint the known-good smoke source.
        return not exit_code & 33
    raise ValueError(f"Unsupported linter: {linter}")


def _has_flake8_execution_failure(output: str) -> bool:
    normalized = output.casefold()
    return any(marker in normalized for marker in FLAKE8_FAILURE_MARKERS)


def _is_missing_linter(stderr: str, linter: str) -> bool:
    pattern = (
        rf"no module named\s+['\"]?{re.escape(linter)}"
        rf"(?:\.__main__)?(?:['\";\s]|$)"
    )
    return re.search(pattern, stderr or "", re.IGNORECASE) is not None


def _flake8_run_succeeded(
    exit_code: int, stdout: str, stderr: str
) -> bool:
    """Distinguish ordinary rc=1 findings from Flake8 startup failures."""
    combined = "\n".join(part for part in (stdout, stderr) if part)
    if exit_code not in {0, 1} or _has_flake8_execution_failure(combined):
        return False
    if exit_code == 0:
        return True
    output_lines = [line for line in stdout.splitlines() if line.strip()]
    if output_lines:
        return any(FLAKE8_OUTPUT_PATTERN.match(line) for line in output_lines)
    return False


def _is_style_issue(linter: str, code: str) -> bool:
    """Return whether a linter code is style-only noise for the UI toggle."""
    normalized = code.upper()
    if linter == "flake8":
        return (
            normalized.startswith(("E", "W"))
            and normalized not in FLAKE8_NON_STYLE_CODES
        )
    if linter == "pylint":
        return (
            normalized.startswith(("C", "R"))
            or normalized in PYLINT_STYLE_WARNING_CODES
        )
    return False


@dataclass
class LintIssue:
    """A single lint issue from flake8 or pylint."""

    line: int  # 0-based line number
    column: int  # 0-based column
    code: str  # e.g. "E501", "W291", "C0301"
    message: str  # human-readable message
    severity: str  # "error" or "warning"


class LintWorker(QObject):
    """Runs linting in a background QThread."""

    finished = pyqtSignal(list)  # list[LintIssue]
    error_occurred = pyqtSignal(str)  # error message for UI

    def __init__(
        self,
        source_code: str,
        file_path: str | None,
        linter: str,
        include_style_issues: bool = True,
        *,
        execution_context: "LintExecutionContext | None" = None,
    ):
        super().__init__()
        self._source = source_code
        self._file_path = file_path
        self._linter = linter
        self._include_style_issues = include_style_issues
        self._execution_context = execution_context
        self._cancelled = threading.Event()
        self._process_lock = threading.Lock()
        self._process: subprocess.Popen | None = None

    def run(self) -> None:
        """Execute the linter and emit results."""
        issues = []
        try:
            if self._linter == "flake8":
                issues = self._run_flake8()
            elif self._linter == "pylint":
                issues = self._run_pylint()
            else:
                self.error_occurred.emit(
                    f"Unsupported linter: {self._linter}"
                )
        except FileNotFoundError:
            self.error_occurred.emit(self._missing_linter_message())
        except _LintCancelled:
            pass
        except subprocess.TimeoutExpired:
            self.error_occurred.emit(
                f"'{self._linter}' timed out while analysing this file."
            )
        except Exception as exc:
            self.error_occurred.emit(f"Linter error: {exc}")
        self.finished.emit(issues)

    def _interpreter(self) -> str:
        context = self._execution_context
        return context.interpreter if context is not None else sys.executable

    def _working_directory(self) -> str | None:
        context = self._execution_context
        return context.cwd if context is not None else None

    def _display_name(self) -> str:
        context = self._execution_context
        if context is not None:
            return context.display_name
        return self._file_path or "untitled.py"

    def _timeout(self, default: int) -> int:
        context = self._execution_context
        if context is None:
            return default
        timeout = getattr(context, "timeout_seconds", default)
        return timeout if isinstance(timeout, int) and timeout > 0 else default

    def _config_args(self) -> list[str]:
        return build_linter_config_args(
            self._linter, self._execution_context
        )

    def _subprocess_kwargs(self) -> dict:
        kwargs = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "encoding": "utf-8",
        }
        cwd = self._working_directory()
        if cwd is not None:
            kwargs["cwd"] = cwd
        return kwargs

    def _run_process(
        self, args: list[str], timeout: int
    ) -> subprocess.CompletedProcess:
        """Run one cancellable lint subprocess and collect its output."""

        if self._cancelled.is_set():
            raise _LintCancelled
        process = subprocess.Popen(args, **self._subprocess_kwargs())
        with self._process_lock:
            self._process = process
        if self._cancelled.is_set():
            self._kill_process(process)
        try:
            stdout, stderr = process.communicate(
                input=self._source,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            self._kill_process(process)
            stdout, stderr = process.communicate()
            if self._cancelled.is_set():
                raise _LintCancelled from exc
            raise subprocess.TimeoutExpired(
                args,
                timeout,
                output=stdout,
                stderr=stderr,
            ) from exc
        finally:
            with self._process_lock:
                if self._process is process:
                    self._process = None
        if self._cancelled.is_set():
            raise _LintCancelled
        return subprocess.CompletedProcess(
            args,
            process.returncode,
            stdout=stdout,
            stderr=stderr,
        )

    @staticmethod
    def _kill_process(process: subprocess.Popen) -> None:
        try:
            if process.poll() is None:
                process.kill()
        except (OSError, RuntimeError):
            pass

    def cancel(self) -> None:
        """Stop the active subprocess; late results are intentionally ignored."""

        self._cancelled.set()
        with self._process_lock:
            process = self._process
        if process is not None:
            self._kill_process(process)

    def _missing_linter_message(self) -> str:
        interpreter = self._interpreter()
        return (
            f"'{self._linter}' is not installed in the selected Python "
            f"environment. Install it with: \"{interpreter}\" -m pip install "
            f"{self._linter}"
        )

    def _emit_process_error(self, stderr: str) -> None:
        detail = (stderr or "").strip()
        if len(detail) > 1000:
            detail = detail[:997] + "..."
        self.error_occurred.emit(
            detail or f"{self._linter} could not run with the selected settings."
        )

    def _run_flake8(self) -> list[LintIssue]:
        """Run flake8 on stdin and parse output."""
        display_name = self._display_name()
        context = self._execution_context
        if context is None:
            args = [self._interpreter(), "-m", "flake8"]
            args.extend(
                [
                    f"--format={FLAKE8_OUTPUT_FORMAT}",
                    "--stdin-display-name",
                    display_name,
                    "-",
                ]
            )
        else:
            program, command_args, _ = build_linter_stdin_command(
                "flake8", context
            )
            args = [program, *command_args]
        result = self._run_process(args, self._timeout(10))
        if _is_missing_linter(result.stderr, "flake8"):
            self.error_occurred.emit(self._missing_linter_message())
            return []
        if not _flake8_run_succeeded(
            result.returncode, result.stdout, result.stderr
        ):
            self._emit_process_error(result.stderr or result.stdout)
            return []
        return self._parse_flake8_output(result.stdout)

    def _parse_flake8_output(self, output: str) -> list[LintIssue]:
        """Parse flake8 output: filename:line:col: CODE message"""
        issues = []
        for line in output.strip().splitlines():
            m = FLAKE8_OUTPUT_PATTERN.match(line)
            if m:
                line_num = int(m.group(1)) - 1  # convert to 0-based
                col = int(m.group(2)) - 1
                code = m.group(3)
                message = m.group(4)
                severity = "error" if code.startswith(("E", "F")) else "warning"
                if self._include_style_issues or not _is_style_issue(
                    self._linter, code
                ):
                    issues.append(LintIssue(line_num, col, code, message, severity))
        return issues

    def _run_pylint(self) -> list[LintIssue]:
        """Run pylint on stdin and parse output."""
        display_name = self._display_name()
        context = self._execution_context
        if context is None:
            args = [self._interpreter(), "-m", "pylint"]
            args.extend(
                [
                    "--from-stdin",
                    display_name,
                    "--output-format=text",
                    "--msg-template={line}:{column}: {msg_id} {msg}",
                ]
            )
        else:
            program, command_args, _ = build_linter_stdin_command(
                "pylint", context
            )
            args = [program, *command_args]
        result = self._run_process(args, self._timeout(15))
        if _is_missing_linter(result.stderr, "pylint"):
            self.error_occurred.emit(self._missing_linter_message())
            return []
        if result.returncode & 32:
            self._emit_process_error(result.stderr)
            return []
        issues = self._parse_pylint_output(result.stdout)
        if result.returncode & 1 and not issues:
            self._emit_process_error(result.stderr or result.stdout)
            return []
        return issues

    def _parse_pylint_output(self, output: str) -> list[LintIssue]:
        """Parse pylint output: line:col: CODE message"""
        issues = []
        pattern = re.compile(r"^(\d+):(\d+):\s+(\w+)\s+(.+)$")
        for line in output.strip().splitlines():
            m = pattern.match(line)
            if m:
                line_num = int(m.group(1)) - 1
                col = int(m.group(2))
                code = m.group(3)
                message = m.group(4)
                severity = "error" if code.startswith(("E", "F")) else "warning"
                if self._include_style_issues or not _is_style_issue(
                    self._linter, code
                ):
                    issues.append(LintIssue(line_num, col, code, message, severity))
        return issues


class LintRunner(QObject):
    """Manages asynchronous linting via a worker thread."""

    lint_finished = pyqtSignal(list)  # list[LintIssue]
    lint_error = pyqtSignal(str)  # error message for UI

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: LintWorker | None = None
        self._old_threads: list[QThread] = []
        self._old_workers: list[LintWorker] = []
        self._generation: int = 0
        self._failed_generations: set[int] = set()

    def run_lint(
        self,
        source_code: str,
        file_path: str | None,
        linter: str,
        include_style_issues: bool = True,
        *,
        execution_context: "LintExecutionContext | None" = None,
    ) -> None:
        """Start a lint run. Cancels any in-progress run."""
        self._cancel_current()
        self._generation += 1
        gen = self._generation
        self._failed_generations.discard(gen)

        self._thread = QThread()
        self._worker = LintWorker(
            source_code,
            file_path,
            linter,
            include_style_issues,
            execution_context=execution_context,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(
            lambda issues, g=gen: self._on_finished(issues, g)
        )
        self._worker.error_occurred.connect(
            lambda message, g=gen: self._on_error(message, g)
        )
        self._worker.finished.connect(self._thread.quit)
        self._thread.start()

    def _on_finished(self, issues: list, generation: int) -> None:
        failed = generation in self._failed_generations
        self._failed_generations.discard(generation)
        if generation == self._generation and not failed:
            self.lint_finished.emit(issues)

    def _on_error(self, message: str, generation: int) -> None:
        if generation == self._generation:
            self._failed_generations.add(generation)
            self.lint_error.emit(message)

    def cancel(self) -> None:
        """Cancel the active lint run and ignore any late results."""
        self._generation += 1
        self._cancel_current()

    def stop(self) -> None:
        """Shut down all threads cleanly (call during app close)."""
        self._cancel_current()
        for thread in list(self._old_threads):
            stop_qthread(thread, graceful_timeout_ms=16_000)
        self._old_threads.clear()
        self._old_workers.clear()
        self._failed_generations.clear()

    def _cancel_current(self) -> None:
        if self._thread and self._thread.isRunning():
            old_thread = self._thread
            old_worker = self._worker
            cancel = getattr(old_worker, "cancel", None)
            if callable(cancel):
                cancel()
            old_thread.quit()
            # Keep a reference so it isn't GC'd while still running
            self._old_threads.append(old_thread)
            if old_worker is not None:
                self._old_workers.append(old_worker)
            old_thread.finished.connect(
                lambda t=old_thread, w=old_worker: self._cleanup_thread(t, w)
            )
        self._thread = None
        self._worker = None

    def _cleanup_thread(
        self, thread: QThread, worker: LintWorker | None = None
    ) -> None:
        """Remove finished thread from the keep-alive list."""
        try:
            self._old_threads.remove(thread)
        except ValueError:
            pass
        if worker is not None:
            try:
                self._old_workers.remove(worker)
            except ValueError:
                pass

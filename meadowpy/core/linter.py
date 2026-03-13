"""Linting integration — runs flake8 or pylint as a subprocess."""

import re
import subprocess
import sys
from dataclasses import dataclass

from PyQt6.QtCore import QObject, QThread, pyqtSignal


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

    def __init__(self, source_code: str, file_path: str | None, linter: str):
        super().__init__()
        self._source = source_code
        self._file_path = file_path
        self._linter = linter

    def run(self) -> None:
        """Execute the linter and emit results."""
        issues = []
        try:
            if self._linter == "flake8":
                issues = self._run_flake8()
            elif self._linter == "pylint":
                issues = self._run_pylint()
        except FileNotFoundError:
            pass  # linter not installed — silently skip
        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass
        self.finished.emit(issues)

    def _run_flake8(self) -> list[LintIssue]:
        """Run flake8 on stdin and parse output."""
        display_name = self._file_path or "untitled.py"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "flake8",
                "--stdin-display-name",
                display_name,
                "-",
            ],
            input=self._source,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=10,
        )
        return self._parse_flake8_output(result.stdout)

    def _parse_flake8_output(self, output: str) -> list[LintIssue]:
        """Parse flake8 output: filename:line:col: CODE message"""
        issues = []
        pattern = re.compile(r"^.+?:(\d+):(\d+):\s+(\w+)\s+(.+)$")
        for line in output.strip().splitlines():
            m = pattern.match(line)
            if m:
                line_num = int(m.group(1)) - 1  # convert to 0-based
                col = int(m.group(2)) - 1
                code = m.group(3)
                message = m.group(4)
                severity = "error" if code.startswith(("E", "F")) else "warning"
                issues.append(LintIssue(line_num, col, code, message, severity))
        return issues

    def _run_pylint(self) -> list[LintIssue]:
        """Run pylint on stdin and parse output."""
        display_name = self._file_path or "untitled.py"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pylint",
                "--from-stdin",
                display_name,
                "--output-format=text",
                "--msg-template={line}:{column}: {msg_id} {msg}",
            ],
            input=self._source,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=15,
        )
        return self._parse_pylint_output(result.stdout)

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
                issues.append(LintIssue(line_num, col, code, message, severity))
        return issues


class LintRunner(QObject):
    """Manages asynchronous linting via a worker thread."""

    lint_finished = pyqtSignal(list)  # list[LintIssue]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: LintWorker | None = None
        self._old_threads: list[QThread] = []
        self._generation: int = 0

    def run_lint(
        self, source_code: str, file_path: str | None, linter: str
    ) -> None:
        """Start a lint run. Cancels any in-progress run."""
        self._cancel_current()
        self._generation += 1
        gen = self._generation

        self._thread = QThread()
        self._worker = LintWorker(source_code, file_path, linter)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(lambda issues, g=gen: self._on_finished(issues, g))
        self._worker.finished.connect(self._thread.quit)
        self._thread.start()

    def _on_finished(self, issues: list, generation: int) -> None:
        if generation == self._generation:
            self.lint_finished.emit(issues)

    def stop(self) -> None:
        """Shut down all threads cleanly (call during app close)."""
        self._cancel_current()
        for thread in self._old_threads:
            if thread.isRunning():
                thread.quit()
                if not thread.wait(500):
                    thread.terminate()
                    thread.wait(500)
        self._old_threads.clear()

    def _cancel_current(self) -> None:
        if self._thread and self._thread.isRunning():
            old_thread = self._thread
            old_thread.quit()
            # Keep a reference so it isn't GC'd while still running
            self._old_threads.append(old_thread)
            old_thread.finished.connect(lambda t=old_thread: self._cleanup_thread(t))
        self._thread = None
        self._worker = None

    def _cleanup_thread(self, thread: QThread) -> None:
        """Remove finished thread from the keep-alive list."""
        try:
            self._old_threads.remove(thread)
        except ValueError:
            pass

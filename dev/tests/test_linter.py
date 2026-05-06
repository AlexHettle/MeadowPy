import subprocess

import meadowpy.core.linter as linter_module
from meadowpy.core.linter import LintRunner, LintWorker
from tests.helpers import DummySignal, FakeThread, SignalRecorder


def test_parse_flake8_output_uses_zero_based_positions_and_severity():
    worker = LintWorker("print('x')\n", "demo.py", "flake8")

    issues = worker._parse_flake8_output(
        "demo.py:2:5: E225 missing whitespace around operator\n"
        "demo.py:3:1: W291 trailing whitespace\n"
    )

    assert [(issue.line, issue.column, issue.code, issue.severity) for issue in issues] == [
        (1, 4, "E225", "error"),
        (2, 0, "W291", "warning"),
    ]


def test_parse_pylint_output_uses_expected_columns():
    worker = LintWorker("print('x')\n", "demo.py", "pylint")

    issues = worker._parse_pylint_output(
        "4:2: C0114 missing-module-docstring\n"
        "7:0: E0602 undefined-variable\n"
    )

    assert [(issue.line, issue.column, issue.code, issue.severity) for issue in issues] == [
        (3, 2, "C0114", "warning"),
        (6, 0, "E0602", "error"),
    ]


def test_run_emits_install_error_when_flake8_module_is_missing(monkeypatch):
    worker = LintWorker("print('x')\n", "demo.py", "flake8")
    errors = SignalRecorder()
    finished = SignalRecorder()
    worker.error_occurred.connect(errors)
    worker.finished.connect(finished)

    monkeypatch.setattr(
        "meadowpy.core.linter.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, stdout="", stderr="No module named flake8"),
    )

    worker.run()

    assert errors.calls == [("'flake8' is not installed. Install it with: pip install flake8",)]
    assert finished.calls == [([],)]


def test_run_flake8_parses_successful_subprocess_output(monkeypatch):
    worker = LintWorker("x=1\n", "demo.py", "flake8")

    def fake_run(args, **kwargs):
        assert args[:3] == [linter_module.sys.executable, "-m", "flake8"]
        assert kwargs["input"] == "x=1\n"
        assert kwargs["timeout"] == 10
        return subprocess.CompletedProcess(
            args,
            1,
            stdout="demo.py:1:2: E225 missing whitespace around operator\n",
            stderr="",
        )

    monkeypatch.setattr("meadowpy.core.linter.subprocess.run", fake_run)

    issues = worker._run_flake8()

    assert [(issue.line, issue.column, issue.code) for issue in issues] == [
        (0, 1, "E225")
    ]


def test_run_pylint_parses_successful_subprocess_output(monkeypatch):
    worker = LintWorker("print(x)\n", "demo.py", "pylint")

    def fake_run(args, **kwargs):
        assert args[:3] == [linter_module.sys.executable, "-m", "pylint"]
        assert "--from-stdin" in args
        assert kwargs["input"] == "print(x)\n"
        assert kwargs["timeout"] == 15
        return subprocess.CompletedProcess(
            args,
            20,
            stdout="1:6: E0602 undefined-variable\n",
            stderr="",
        )

    monkeypatch.setattr("meadowpy.core.linter.subprocess.run", fake_run)

    issues = worker._run_pylint()

    assert [(issue.line, issue.column, issue.code) for issue in issues] == [
        (0, 6, "E0602")
    ]


def test_run_pylint_emits_install_error_when_module_is_missing(monkeypatch):
    worker = LintWorker("print('x')\n", "demo.py", "pylint")
    errors = SignalRecorder()
    worker.error_occurred.connect(errors)
    monkeypatch.setattr(
        "meadowpy.core.linter.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            1,
            stdout="",
            stderr="No module named pylint",
        ),
    )

    assert worker._run_pylint() == []
    assert errors.calls == [("'pylint' is not installed. Install it with: pip install pylint",)]


def test_run_emits_timeout_error(monkeypatch):
    worker = LintWorker("print('x')\n", "demo.py", "flake8")
    errors = SignalRecorder()
    worker.error_occurred.connect(errors)
    monkeypatch.setattr(worker, "_run_flake8", lambda: (_ for _ in ()).throw(subprocess.TimeoutExpired("flake8", 10)))

    worker.run()

    assert errors.calls == [("'flake8' timed out while analysing this file.",)]


def test_run_emits_unexpected_error(monkeypatch):
    worker = LintWorker("print('x')\n", "demo.py", "pylint")
    errors = SignalRecorder()
    worker.error_occurred.connect(errors)
    monkeypatch.setattr(worker, "_run_pylint", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    worker.run()

    assert errors.calls == [("Linter error: boom",)]


def test_lint_runner_only_emits_for_latest_generation():
    runner = LintRunner()
    finished = SignalRecorder()
    runner.lint_finished.connect(finished)
    runner._generation = 2

    runner._on_finished(["stale"], 1)
    runner._on_finished(["fresh"], 2)

    assert finished.calls == [(["fresh"],)]


class FakeLintWorker:
    def __init__(self, source_code, file_path, linter):
        self.args = (source_code, file_path, linter)
        self.finished = FlexibleSignal()
        self.error_occurred = DummySignal()
        self.moved_to = None

    def moveToThread(self, thread):
        self.moved_to = thread

    def run(self):
        self.finished.emit(["issue"])


class FlexibleSignal(DummySignal):
    def emit(self, *args):
        for callback in list(self._callbacks):
            try:
                callback(*args)
            except TypeError:
                callback()


def test_run_lint_starts_worker_thread_and_emits_latest_results(monkeypatch):
    threads = []
    workers = []

    def make_thread():
        thread = FakeThread(running=False)
        threads.append(thread)
        return thread

    def make_worker(source_code, file_path, linter):
        worker = FakeLintWorker(source_code, file_path, linter)
        workers.append(worker)
        return worker

    monkeypatch.setattr(linter_module, "QThread", make_thread)
    monkeypatch.setattr(linter_module, "LintWorker", make_worker)
    runner = LintRunner()
    finished = SignalRecorder()
    runner.lint_finished.connect(finished)

    runner.run_lint("x=1\n", "demo.py", "flake8")

    assert workers[0].args == ("x=1\n", "demo.py", "flake8")
    assert workers[0].moved_to is threads[0]
    assert threads[0].start_called == 1
    assert finished.calls == [(["issue"],)]


def test_cancel_current_moves_running_thread_to_keep_alive_list():
    runner = LintRunner()
    thread = FakeThread(running=True)
    worker = object()
    runner._thread = thread
    runner._worker = worker

    runner._cancel_current()

    assert runner._thread is None
    assert runner._worker is None
    assert runner._old_threads == [thread]
    assert runner._old_workers == [worker]
    assert thread.quit_called == 1


def test_stop_terminates_old_threads_when_needed():
    runner = LintRunner()
    stubborn = FakeThread(running=True, wait_result=False)
    runner._old_threads = [stubborn]
    runner._old_workers = [object()]

    runner.stop()

    assert stubborn.quit_called == 1
    assert stubborn.terminate_called == 1
    assert runner._old_threads == []
    assert runner._old_workers == []

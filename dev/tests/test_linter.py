import subprocess

from meadowpy.core.linter import LintRunner, LintWorker
from tests.helpers import FakeThread, SignalRecorder


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


def test_cancel_current_moves_running_thread_to_keep_alive_list():
    runner = LintRunner()
    thread = FakeThread(running=True)
    runner._thread = thread
    runner._worker = object()

    runner._cancel_current()

    assert runner._thread is None
    assert runner._worker is None
    assert runner._old_threads == [thread]
    assert thread.quit_called == 1


def test_stop_terminates_old_threads_when_needed():
    runner = LintRunner()
    stubborn = FakeThread(running=True, wait_result=False)
    runner._old_threads = [stubborn]

    runner.stop()

    assert stubborn.quit_called == 1
    assert stubborn.terminate_called == 1
    assert runner._old_threads == []

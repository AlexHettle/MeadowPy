import subprocess
from types import SimpleNamespace

import meadowpy.core.linter as linter_module
from meadowpy.core.linter import LintRunner, LintWorker
from tests.helpers import DummySignal, FakeThread, SignalRecorder


def test_is_style_issue_returns_false_for_unknown_linter():
    assert linter_module._is_style_issue("mypy", "E501") is False


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


def test_parse_flake8_output_can_hide_style_issues():
    worker = LintWorker(
        "print('x')\n", "demo.py", "flake8", include_style_issues=False
    )

    issues = worker._parse_flake8_output(
        "demo.py:1:2: E225 missing whitespace around operator\n"
        "demo.py:2:1: W291 trailing whitespace\n"
        "demo.py:3:7: F821 undefined name 'name'\n"
        "demo.py:4:1: E999 SyntaxError: invalid syntax\n"
    )

    assert [issue.code for issue in issues] == ["F821", "E999"]


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


def test_parse_pylint_output_can_hide_style_issues():
    worker = LintWorker(
        "print('x')\n", "demo.py", "pylint", include_style_issues=False
    )

    issues = worker._parse_pylint_output(
        "1:0: C0114 missing-module-docstring\n"
        "2:4: W0311 bad-indentation\n"
        "3:0: W0611 unused-import\n"
        "4:0: R0903 too-few-public-methods\n"
        "5:6: E0602 undefined-variable\n"
    )

    assert [issue.code for issue in issues] == ["W0611", "E0602"]


def test_run_emits_install_error_when_flake8_module_is_missing(monkeypatch):
    worker = LintWorker("print('x')\n", "demo.py", "flake8")
    errors = SignalRecorder()
    finished = SignalRecorder()
    worker.error_occurred.connect(errors)
    worker.finished.connect(finished)

    monkeypatch.setattr(
        worker,
        "_run_process",
        lambda args, timeout: subprocess.CompletedProcess(
            args, 1, stdout="", stderr="No module named flake8"
        ),
    )

    worker.run()

    assert len(errors.calls) == 1
    assert "not installed in the selected Python environment" in errors.calls[0][0]
    assert "-m pip install flake8" in errors.calls[0][0]
    assert finished.calls == [([],)]


def test_run_emits_install_error_when_linter_executable_is_missing(monkeypatch):
    worker = LintWorker("print('x')\n", "demo.py", "flake8")
    errors = SignalRecorder()
    finished = SignalRecorder()
    worker.error_occurred.connect(errors)
    worker.finished.connect(finished)
    monkeypatch.setattr(
        worker,
        "_run_flake8",
        lambda: (_ for _ in ()).throw(FileNotFoundError()),
    )

    worker.run()

    assert len(errors.calls) == 1
    assert "-m pip install flake8" in errors.calls[0][0]
    assert finished.calls == [([],)]


def test_run_flake8_parses_successful_subprocess_output(monkeypatch):
    worker = LintWorker("x=1\n", "demo.py", "flake8")

    def fake_run(args, timeout):
        assert args[:3] == [linter_module.sys.executable, "-m", "flake8"]
        assert worker._source == "x=1\n"
        assert timeout == 10
        return subprocess.CompletedProcess(
            args,
            1,
            stdout="demo.py:1:2: E225 missing whitespace around operator\n",
            stderr="",
        )

    monkeypatch.setattr(worker, "_run_process", fake_run)

    issues = worker._run_flake8()

    assert [(issue.line, issue.column, issue.code) for issue in issues] == [
        (0, 1, "E225")
    ]


def test_run_pylint_parses_successful_subprocess_output(monkeypatch):
    worker = LintWorker("print(x)\n", "demo.py", "pylint")

    def fake_run(args, timeout):
        assert args[:3] == [linter_module.sys.executable, "-m", "pylint"]
        assert "--from-stdin" in args
        assert worker._source == "print(x)\n"
        assert timeout == 15
        return subprocess.CompletedProcess(
            args,
            20,
            stdout="1:6: E0602 undefined-variable\n",
            stderr="",
        )

    monkeypatch.setattr(worker, "_run_process", fake_run)

    issues = worker._run_pylint()

    assert [(issue.line, issue.column, issue.code) for issue in issues] == [
        (0, 6, "E0602")
    ]


def test_run_pylint_emits_install_error_when_module_is_missing(monkeypatch):
    worker = LintWorker("print('x')\n", "demo.py", "pylint")
    errors = SignalRecorder()
    worker.error_occurred.connect(errors)
    monkeypatch.setattr(
        worker,
        "_run_process",
        lambda args, timeout: subprocess.CompletedProcess(
            args,
            1,
            stdout="",
            stderr="No module named pylint",
        ),
    )

    assert worker._run_pylint() == []
    assert len(errors.calls) == 1
    assert "-m pip install pylint" in errors.calls[0][0]


def test_run_emits_timeout_error(monkeypatch):
    worker = LintWorker("print('x')\n", "demo.py", "flake8")
    errors = SignalRecorder()
    worker.error_occurred.connect(errors)
    monkeypatch.setattr(worker, "_run_flake8", lambda: (_ for _ in ()).throw(subprocess.TimeoutExpired("flake8", 10)))

    worker.run()

    assert errors.calls == [("'flake8' timed out while analysing this file.",)]


def test_run_process_uses_popen_and_supplies_source_and_timeout(monkeypatch):
    context = SimpleNamespace(cwd="C:/project")
    worker = LintWorker(
        "x=1\n",
        "C:/project/demo.py",
        "flake8",
        execution_context=context,
    )
    observed = {}

    class FakeProcess:
        returncode = 0

        def communicate(self, *, input=None, timeout=None):
            observed["input"] = input
            observed["timeout"] = timeout
            return "clean", ""

        def poll(self):
            return self.returncode

    def fake_popen(args, **kwargs):
        observed["args"] = args
        observed["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(linter_module.subprocess, "Popen", fake_popen)

    result = worker._run_process(["python", "-m", "flake8"], 23)

    assert result.returncode == 0
    assert result.stdout == "clean"
    assert observed["input"] == "x=1\n"
    assert observed["timeout"] == 23
    assert observed["kwargs"]["cwd"] == context.cwd
    assert observed["kwargs"]["stdin"] is subprocess.PIPE
    assert worker._process is None


def test_run_process_kills_a_timed_out_linter(monkeypatch):
    worker = LintWorker("x=1\n", "demo.py", "flake8")

    class TimedOutProcess:
        returncode = -9

        def __init__(self):
            self.communicate_calls = 0
            self.killed = False

        def communicate(self, *, input=None, timeout=None):
            self.communicate_calls += 1
            if self.communicate_calls == 1:
                raise subprocess.TimeoutExpired("flake8", timeout)
            return "partial", "slow"

        def poll(self):
            return None if not self.killed else self.returncode

        def kill(self):
            self.killed = True

    process = TimedOutProcess()
    monkeypatch.setattr(
        linter_module.subprocess,
        "Popen",
        lambda args, **kwargs: process,
    )

    try:
        worker._run_process(["python", "-m", "flake8"], 5)
    except subprocess.TimeoutExpired as exc:
        assert exc.output == "partial"
        assert exc.stderr == "slow"
    else:
        raise AssertionError("Expected the lint process to time out")

    assert process.killed is True
    assert worker._process is None


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


def test_lint_runner_only_emits_errors_for_latest_generation():
    runner = LintRunner()
    errors = SignalRecorder()
    runner.lint_error.connect(errors)
    runner._generation = 2

    runner._on_error("stale", 1)
    runner._on_error("fresh", 2)

    assert errors.calls == [("fresh",)]


class FakeLintWorker:
    def __init__(
        self,
        source_code,
        file_path,
        linter,
        include_style_issues=True,
        *,
        execution_context=None,
    ):
        self.args = (source_code, file_path, linter, include_style_issues)
        self.execution_context = execution_context
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

    def make_worker(
        source_code,
        file_path,
        linter,
        include_style_issues=True,
        *,
        execution_context=None,
    ):
        worker = FakeLintWorker(
            source_code,
            file_path,
            linter,
            include_style_issues,
            execution_context=execution_context,
        )
        workers.append(worker)
        return worker

    monkeypatch.setattr(linter_module, "QThread", make_thread)
    monkeypatch.setattr(linter_module, "LintWorker", make_worker)
    runner = LintRunner()
    finished = SignalRecorder()
    runner.lint_finished.connect(finished)

    runner.run_lint("x=1\n", "demo.py", "flake8")

    assert workers[0].args == ("x=1\n", "demo.py", "flake8", True)
    assert workers[0].moved_to is threads[0]
    assert threads[0].start_called == 1
    assert finished.calls == [(["issue"],)]


def test_flake8_uses_resolved_context_for_command_and_timeout(monkeypatch):
    context = SimpleNamespace(
        interpreter="C:/project/.venv/python.exe",
        cwd="C:/project",
        display_name="src/demo.py",
        isolated=False,
        config_path="C:/project/.flake8",
        timeout_seconds=27,
    )
    worker = LintWorker(
        "x=1\n",
        "C:/project/src/demo.py",
        "flake8",
        execution_context=context,
    )

    def fake_run(args, timeout):
        assert args == [
            context.interpreter,
            "-m",
            "flake8",
            "--config",
            context.config_path,
            f"--format={linter_module.FLAKE8_OUTPUT_FORMAT}",
            "--stdin-display-name",
            context.display_name,
            "-",
        ]
        assert worker._working_directory() == context.cwd
        assert timeout == 27
        assert "shell" not in worker._subprocess_kwargs()
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(worker, "_run_process", fake_run)

    assert worker._run_flake8() == []


def test_flake8_reports_critical_execution_error_even_with_exit_code_one(
    monkeypatch,
):
    worker = LintWorker("x=1\n", "demo.py", "flake8")
    errors = SignalRecorder()
    worker.error_occurred.connect(errors)
    message = (
        "There was a critical error during execution of Flake8: "
        "plugin could not load"
    )
    monkeypatch.setattr(
        worker,
        "_run_process",
        lambda args, timeout: subprocess.CompletedProcess(
            args, 1, stdout=message, stderr=""
        ),
    )

    assert worker._run_flake8() == []
    assert errors.calls == [(message,)]


def test_flake8_preserves_plugin_dependency_error_instead_of_install_hint(
    monkeypatch,
):
    worker = LintWorker("x=1\n", "demo.py", "flake8")
    errors = SignalRecorder()
    worker.error_occurred.connect(errors)
    message = "FailedToLoadPlugin: No module named 'company_plugin_dep'"
    monkeypatch.setattr(
        worker,
        "_run_process",
        lambda args, timeout: subprocess.CompletedProcess(
            args, 1, stdout="", stderr=message
        ),
    )

    assert worker._run_flake8() == []
    assert errors.calls == [(message,)]


def test_flake8_reports_exit_one_when_config_suppresses_all_output(
    monkeypatch,
):
    worker = LintWorker("x=1\n", "demo.py", "flake8")
    errors = SignalRecorder()
    worker.error_occurred.connect(errors)
    monkeypatch.setattr(
        worker,
        "_run_process",
        lambda args, timeout: subprocess.CompletedProcess(
            args, 1, stdout="", stderr=""
        ),
    )

    assert worker._run_flake8() == []
    assert errors.calls == [
        ("flake8 could not run with the selected settings.",)
    ]


def test_pylint_uses_isolated_context_and_reports_usage_error(monkeypatch):
    context = SimpleNamespace(
        interpreter="C:/project/.venv/python.exe",
        cwd="C:/project",
        display_name="demo.py",
        isolated=True,
        config_path=None,
        timeout_seconds=22,
    )
    worker = LintWorker(
        "print('x')\n",
        "C:/project/demo.py",
        "pylint",
        execution_context=context,
    )
    errors = SignalRecorder()
    worker.error_occurred.connect(errors)

    def fake_run(args, timeout):
        assert args[:4] == [
            context.interpreter,
            "-m",
            "pylint",
            "--rcfile=",
        ]
        assert worker._working_directory() == context.cwd
        assert timeout == 22
        return subprocess.CompletedProcess(
            args, 32, stdout="", stderr="invalid configuration"
        )

    monkeypatch.setattr(worker, "_run_process", fake_run)

    assert worker._run_pylint() == []
    assert errors.calls == [("invalid configuration",)]


def test_stdin_command_reuses_the_resolved_config_policy():
    context = SimpleNamespace(
        interpreter="C:/project/.venv/python.exe",
        cwd="C:/project",
        display_name="src/demo.py",
        isolated=False,
        config_path="C:/project/.flake8",
    )

    program, arguments, cwd = linter_module.build_linter_stdin_command(
        "flake8", context
    )

    assert program == context.interpreter
    assert arguments == [
        "-m",
        "flake8",
        "--config",
        context.config_path,
        f"--format={linter_module.FLAKE8_OUTPUT_FORMAT}",
        "--stdin-display-name",
        context.display_name,
        "-",
    ]
    assert cwd == context.cwd
    assert linter_module.lint_test_exit_succeeded("flake8", 0) is True
    assert linter_module.lint_test_exit_succeeded("flake8", 1) is False
    assert (
        linter_module.lint_test_exit_succeeded(
            "flake8",
            0,
            "There was a critical error during execution of Flake8",
        )
        is False
    )
    assert linter_module.lint_test_exit_succeeded("pylint", 16) is True
    assert linter_module.lint_test_exit_succeeded("pylint", 32) is False


def test_cancel_current_moves_running_thread_to_keep_alive_list():
    runner = LintRunner()
    thread = FakeThread(running=True)
    worker = SimpleNamespace(cancel_calls=0)

    def cancel():
        worker.cancel_calls += 1

    worker.cancel = cancel
    runner._thread = thread
    runner._worker = worker

    runner._cancel_current()

    assert runner._thread is None
    assert runner._worker is None
    assert runner._old_threads == [thread]
    assert runner._old_workers == [worker]
    assert worker.cancel_calls == 1
    assert thread.quit_called == 1


def test_cancel_invalidates_late_results_and_cancels_current_thread():
    runner = LintRunner()
    finished = SignalRecorder()
    runner.lint_finished.connect(finished)
    thread = FakeThread(running=True)
    worker = SimpleNamespace(cancel_calls=0)

    def cancel():
        worker.cancel_calls += 1

    worker.cancel = cancel
    runner._generation = 3
    runner._thread = thread
    runner._worker = worker

    runner.cancel()
    runner._on_finished(["stale"], 3)

    assert runner._generation == 4
    assert runner._thread is None
    assert runner._worker is None
    assert runner._old_threads == [thread]
    assert runner._old_workers == [worker]
    assert worker.cancel_calls == 1
    assert thread.quit_called == 1
    assert finished.calls == []


def test_worker_cancel_kills_the_active_linter_process():
    worker = LintWorker("x=1\n", "demo.py", "flake8")

    class ActiveProcess:
        def __init__(self):
            self.killed = False

        def poll(self):
            return None

        def kill(self):
            self.killed = True

    process = ActiveProcess()
    worker._process = process

    worker.cancel()

    assert worker._cancelled.is_set()
    assert process.killed is True


def test_error_generation_does_not_emit_a_followup_empty_success():
    runner = LintRunner()
    errors = SignalRecorder()
    finished = SignalRecorder()
    runner.lint_error.connect(errors)
    runner.lint_finished.connect(finished)
    runner._generation = 7

    runner._on_error("bad linter configuration", 7)
    runner._on_finished([], 7)

    assert errors.calls == [("bad linter configuration",)]
    assert finished.calls == []
    assert runner._failed_generations == set()

    runner._generation = 8
    runner._on_finished(["issue"], 8)
    assert finished.calls == [(["issue"],)]


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


def test_cleanup_thread_removes_keep_alive_refs_and_tolerates_missing_refs():
    runner = LintRunner()
    thread = object()
    worker = object()
    runner._old_threads = [thread]
    runner._old_workers = [worker]

    runner._cleanup_thread(thread, worker)
    runner._cleanup_thread(thread, worker)

    assert runner._old_threads == []
    assert runner._old_workers == []

from PyQt6.QtCore import QProcess

import meadowpy.core.process_runner as process_module
from meadowpy.core.process_runner import ProcessRunner
from tests.helpers import FakeProcess, SignalRecorder


class FakeQProcess(FakeProcess):
    ProcessChannelMode = QProcess.ProcessChannelMode
    ProcessError = QProcess.ProcessError
    ProcessState = QProcess.ProcessState


def test_run_file_delegates_to_start_process_and_emits_description():
    runner = ProcessRunner()
    started = SignalRecorder()
    runner.process_started.connect(started)
    calls = []
    runner._start_process = lambda interpreter, args, working_dir: calls.append((interpreter, args, working_dir))

    runner.run_file("demo.py", "python.exe", "C:/work")

    assert calls == [("python.exe", ["-u", "demo.py"], "C:/work")]
    assert started.calls == [("Running: demo.py",)]


def test_run_code_writes_temp_file_and_starts_process(tmp_path, monkeypatch):
    runner = ProcessRunner()
    started_calls = []
    runner.process_started.connect(lambda text: started_calls.append(text))
    process_calls = []
    runner._start_process = lambda interpreter, args, working_dir: process_calls.append((interpreter, args, working_dir))
    monkeypatch.setattr("meadowpy.core.process_runner.Path.home", lambda: tmp_path)

    runner.run_code("print('hello')", "python.exe", str(tmp_path))

    assert runner._temp_file is not None
    assert process_calls[0][0] == "python.exe"
    assert process_calls[0][1][0] == "-u"
    assert started_calls == ["Running selection"]

    temp_file = runner._temp_file
    runner._cleanup_temp()
    assert temp_file is not None


def test_send_stdin_only_writes_when_process_is_running():
    runner = ProcessRunner()
    process = FakeProcess()
    process.state_value = QProcess.ProcessState.Running
    runner._process = process

    runner.send_stdin("hello")

    assert process.written == [b"hello"]


def test_stop_kills_active_process():
    runner = ProcessRunner()
    process = FakeProcess()
    process.state_value = QProcess.ProcessState.Running
    runner._process = process

    runner.stop()

    assert process.killed is True


def test_start_process_configures_qprocess_and_replaces_existing(monkeypatch):
    created = []

    class ProcessFactory(FakeQProcess):
        def __init__(self, parent=None):
            super().__init__(parent)
            created.append(self)

    monkeypatch.setattr(process_module, "QProcess", ProcessFactory)
    runner = ProcessRunner()

    runner._start_process("python.exe", ["-u", "demo.py"], "C:/work")
    first = created[0]
    first.state_value = QProcess.ProcessState.Running
    runner._start_process("python.exe", ["-u", "next.py"], "C:/work2")
    second = created[1]

    assert first.killed is True
    assert first.wait_calls == [1000]
    assert second.working_directory == "C:/work2"
    assert second.channel_mode == QProcess.ProcessChannelMode.SeparateChannels
    assert second.start_args == ("python.exe", ["-u", "next.py"])


def test_stop_waits_for_process_and_removes_temp_file(tmp_path):
    runner = ProcessRunner()
    process = FakeQProcess()
    process.state_value = QProcess.ProcessState.Running
    runner._process = process
    temp_file = tmp_path / "selection.py"
    temp_file.write_text("print('x')", encoding="utf-8")
    runner._temp_file = str(temp_file)

    runner.stop(timeout_ms=250)

    assert process.killed is True
    assert process.wait_calls == [250]
    assert runner._temp_file is None
    assert not temp_file.exists()


def test_stdout_and_stderr_are_forwarded():
    runner = ProcessRunner()
    process = FakeProcess()
    process.stdout_bytes = "alpha".encode("utf-8")
    process.stderr_bytes = "beta".encode("utf-8")
    runner._process = process
    output = SignalRecorder()
    runner.output_received.connect(output)

    runner._on_stdout()
    runner._on_stderr()

    assert output.calls == [("alpha", "stdout"), ("beta", "stderr")]


def test_finished_signal_uses_exit_status_and_cleans_temp(tmp_path):
    runner = ProcessRunner()
    finished = SignalRecorder()
    runner.process_finished.connect(finished)
    temp_file = tmp_path / "temp.py"
    temp_file.write_text("print('x')", encoding="utf-8")
    runner._temp_file = str(temp_file)

    runner._on_finished(0, QProcess.ExitStatus.NormalExit)
    runner._on_finished(3, QProcess.ExitStatus.NormalExit)
    runner._on_finished(1, QProcess.ExitStatus.CrashExit)

    assert finished.calls == [
        (0, "Process finished successfully"),
        (3, "Process exited with code 3"),
        (1, "Process was terminated"),
    ]
    assert runner._temp_file is None


def test_on_error_maps_known_process_errors():
    runner = ProcessRunner()
    output = SignalRecorder()
    runner.output_received.connect(output)

    runner._on_error(QProcess.ProcessError.FailedToStart)
    runner._on_error(QProcess.ProcessError.ReadError)

    assert output.calls[0][1] == "system"
    assert "Failed to start" in output.calls[0][0]
    assert output.calls[1] == ("Read error", "system")


def test_on_error_handles_unknown_process_error():
    runner = ProcessRunner()
    output = SignalRecorder()
    runner.output_received.connect(output)

    runner._on_error(object())

    assert output.calls[0][1] == "system"
    assert "Unknown error" in output.calls[0][0]

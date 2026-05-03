from PyQt6.QtCore import QProcess

from meadowpy.core.repl_manager import ReplManager
from tests.helpers import FakeProcess, SignalRecorder


def test_history_deduplicates_consecutive_entries_and_limits_size():
    manager = ReplManager()
    manager._max_history = 2

    manager.add_to_history("first")
    manager.add_to_history("first")
    manager.add_to_history("second")
    manager.add_to_history("third")

    assert manager._history == ["second", "third"]
    assert manager._history_index == 2


def test_history_navigation_moves_up_and_down():
    manager = ReplManager()
    manager.add_to_history("first")
    manager.add_to_history("second")

    assert manager.history_up() == "second"
    assert manager.history_up() == "first"
    assert manager.history_down() == "second"
    assert manager.history_down() == ""


def test_send_input_sends_each_line_when_running():
    manager = ReplManager()
    process = FakeProcess()
    process.state_value = QProcess.ProcessState.Running
    manager._process = process

    manager.send_input("print(1)\nprint(2)")

    assert process.written == [b"print(1)\n", b"print(2)\n"]


def test_process_stderr_buffer_emits_banner_prompt_and_errors():
    manager = ReplManager()
    output = SignalRecorder()
    prompts = SignalRecorder()
    manager.output_received.connect(output)
    manager.prompt_ready.connect(prompts)
    manager._stderr_buffer = "Python 3.11.0\n>>> Traceback\n"

    manager._process_stderr_buffer()

    assert output.calls[0] == ("Python 3.11.0\n", "system")
    assert prompts.calls == [(">>> ",)]
    assert output.calls[1] == ("Traceback\n", "stderr")


def test_process_stderr_buffer_keeps_partial_prompt_buffered():
    manager = ReplManager()
    manager._stderr_buffer = ">>"

    manager._process_stderr_buffer()

    assert manager._stderr_buffer == ">>"


def test_on_error_emits_known_system_messages():
    manager = ReplManager()
    output = SignalRecorder()
    manager.output_received.connect(output)

    manager._on_error(QProcess.ProcessError.FailedToStart)
    manager._on_error(QProcess.ProcessError.Crashed)

    assert output.calls[0][1] == "system"
    assert "Python console failed to start" in output.calls[0][0]
    assert output.calls[1] == ("Python console crashed", "system")


def test_stop_kills_running_process_and_emits_signal():
    manager = ReplManager()
    stopped = SignalRecorder()
    manager.repl_stopped.connect(stopped)
    process = FakeProcess()
    process.state_value = QProcess.ProcessState.Running
    manager._process = process

    manager.stop()

    assert process.killed is True
    assert stopped.calls == [()]
    assert manager._process is None


def test_is_running_property_reflects_process_state():
    manager = ReplManager()
    assert manager.is_running is False

    process = FakeProcess()
    process.state_value = QProcess.ProcessState.Running
    manager._process = process

    assert manager.is_running is True

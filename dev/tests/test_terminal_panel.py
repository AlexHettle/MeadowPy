import os

from PyQt6.QtCore import QEvent, QProcess, Qt
from PyQt6.QtGui import QKeyEvent

import meadowpy.ui.terminal_panel as terminal_panel_module
from meadowpy.ui.terminal_panel import TerminalPanel
from tests.helpers import DummySignal, FakeByteArray


class FakeSettings:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key, default=None):
        return self.values.get(key, default)


class FakeProcess:
    ProcessState = QProcess.ProcessState
    ProcessChannelMode = QProcess.ProcessChannelMode
    ProcessError = QProcess.ProcessError
    ExitStatus = QProcess.ExitStatus
    instances = []

    def __init__(self, parent=None):
        self.parent = parent
        self.state_value = self.ProcessState.NotRunning
        self.stdout_bytes = b""
        self.stderr_bytes = b""
        self.writes = []
        self.killed = False
        self.wait_calls = []
        self.started_program = None
        self.started_args = None
        self.working_directory = None
        self.channel_mode = None
        self.environment = None
        self.readyReadStandardOutput = DummySignal()
        self.readyReadStandardError = DummySignal()
        self.finished = DummySignal()
        self.errorOccurred = DummySignal()
        self.__class__.instances.append(self)

    def setWorkingDirectory(self, directory):
        self.working_directory = directory

    def setProcessChannelMode(self, mode):
        self.channel_mode = mode

    def setProcessEnvironment(self, environment):
        self.environment = environment

    def start(self, program, args):
        self.started_program = program
        self.started_args = args
        self.state_value = self.ProcessState.Running

    def state(self):
        return self.state_value

    def write(self, data):
        self.writes.append(data)

    def kill(self):
        self.killed = True
        self.state_value = self.ProcessState.NotRunning

    def waitForFinished(self, timeout):
        self.wait_calls.append(timeout)
        return True

    def readAllStandardOutput(self):
        data = self.stdout_bytes
        self.stdout_bytes = b""
        return FakeByteArray(data)

    def readAllStandardError(self):
        data = self.stderr_bytes
        self.stderr_bytes = b""
        return FakeByteArray(data)


def _key_event(key, modifiers=Qt.KeyboardModifier.NoModifier, text=""):
    return QKeyEvent(QEvent.Type.KeyPress, key, modifiers, text)


def test_terminal_panel_process_io_history_interrupt_and_clipboard(
    monkeypatch,
    qapp,
    tmp_path,
):
    FakeProcess.instances.clear()
    monkeypatch.setattr(terminal_panel_module, "QProcess", FakeProcess)
    panel = TerminalPanel(
        settings=FakeSettings({"editor.theme": "default_dark"}),
        auto_start_on_show=False,
    )
    panel.set_working_directory(str(tmp_path))

    panel.start_shell()
    process = FakeProcess.instances[-1]

    assert process.working_directory == str(tmp_path)
    assert process.channel_mode == QProcess.ProcessChannelMode.SeparateChannels
    assert process.started_program
    if os.name == "nt":
        assert process.started_program.lower() == "powershell.exe"
        assert "-NoExit" in process.started_args

    process.stdout_bytes = b"PS C:\\Users\\AlexH\\Documents> "
    process.readyReadStandardOutput.emit()
    assert panel._terminal_view.toPlainText() == "PS C:\\Users\\AlexH\\Documents> "

    process.stdout_bytes = b"ready \x1b[31mred\x1b[0m\r\n"
    process.readyReadStandardOutput.emit()
    assert "ready red\n" in panel._terminal_view.toPlainText()
    assert "\x1b[" not in panel._terminal_view.toPlainText()

    panel._terminal_view.set_current_input("echo hello")
    panel._terminal_view.keyPressEvent(
        _key_event(Qt.Key.Key_Return, text="\r")
    )

    assert process.writes[-1] == b"echo hello\n"

    process.stdout_bytes = b"echo hello\r\nhello\r\nPS C:\\Users\\AlexH\\Documents> "
    process.readyReadStandardOutput.emit()
    assert panel._terminal_view.toPlainText().count("echo hello") == 1
    assert "hello\nPS C:\\Users\\AlexH\\Documents> " in (
        panel._terminal_view.toPlainText()
    )

    panel._terminal_view.keyPressEvent(_key_event(Qt.Key.Key_Up))
    assert panel._terminal_view.current_input() == "echo hello"

    panel._terminal_view.keyPressEvent(
        _key_event(
            Qt.Key.Key_C,
            Qt.KeyboardModifier.ControlModifier,
            "c",
        )
    )
    assert process.writes[-1] == b"\x03"

    panel.copy_terminal()
    assert "ready red" in qapp.clipboard().text()

    panel.clear_terminal()
    assert panel._terminal_view.toPlainText() == "PS C:\\Users\\AlexH\\Documents> "
    assert panel._terminal_view.current_input() == ""

    panel.stop()
    assert process.killed is True
    assert process.wait_calls == [1000]

    panel.deleteLater()


def test_terminal_panel_reports_stderr_and_finished_state(monkeypatch, qapp):
    FakeProcess.instances.clear()
    monkeypatch.setattr(terminal_panel_module, "QProcess", FakeProcess)
    panel = TerminalPanel(
        settings=FakeSettings({"editor.theme": "default_dark"}),
        auto_start_on_show=False,
    )

    panel.start_shell()
    process = FakeProcess.instances[-1]
    process.stderr_bytes = b"problem\n"
    process.readyReadStandardError.emit()
    process.finished.emit(7, QProcess.ExitStatus.NormalExit)

    text = panel._terminal_view.toPlainText()
    assert "problem\n" in text
    assert "Terminal exited with code 7." in text
    assert panel.is_running() is False

    panel.deleteLater()


def test_terminal_panel_tab_completion_cycles_provider_matches(monkeypatch, qapp):
    panel = TerminalPanel(
        settings=FakeSettings({"editor.theme": "default_dark"}),
        auto_start_on_show=False,
    )

    def completion_result(line, cursor_column):
        assert line == "cd Doc"
        assert cursor_column == len("cd Doc")
        return terminal_panel_module._CompletionResult(
            3,
            3,
            ["Documents\\", "Downloads\\"],
        )

    monkeypatch.setattr(panel, "_powershell_completion_result", completion_result)

    panel._terminal_view.set_current_input("cd Doc")
    panel._terminal_view.keyPressEvent(_key_event(Qt.Key.Key_Tab, text="\t"))
    assert panel._terminal_view.current_input() == "cd Documents\\"

    panel._terminal_view.keyPressEvent(_key_event(Qt.Key.Key_Tab, text="\t"))
    assert panel._terminal_view.current_input() == "cd Downloads\\"

    panel._terminal_view.keyPressEvent(
        _key_event(
            Qt.Key.Key_Backtab,
            Qt.KeyboardModifier.ShiftModifier,
            "\t",
        )
    )
    assert panel._terminal_view.current_input() == "cd Documents\\"

    panel._terminal_view.set_current_input("cd Doc")
    panel._terminal_view.keyPressEvent(
        _key_event(
            Qt.Key.Key_Backtab,
            Qt.KeyboardModifier.ShiftModifier,
            "\t",
        )
    )
    assert panel._terminal_view.current_input() == "cd Downloads\\"

    panel.deleteLater()


def test_terminal_panel_tab_completion_falls_back_to_paths_and_commands(
    monkeypatch,
    qapp,
    tmp_path,
):
    (tmp_path / "Documents").mkdir()
    panel = TerminalPanel(
        settings=FakeSettings({"editor.theme": "default_dark"}),
        auto_start_on_show=False,
    )
    panel.set_working_directory(str(tmp_path))
    monkeypatch.setattr(
        panel,
        "_powershell_completion_result",
        lambda _line, _cursor_column: terminal_panel_module._CompletionResult(
            0,
            0,
            [],
        ),
    )

    panel._terminal_view.set_current_input("cd Doc")
    panel._terminal_view.keyPressEvent(_key_event(Qt.Key.Key_Tab, text="\t"))
    separator = "\\" if os.name == "nt" else "/"
    assert panel._terminal_view.current_input() == f"cd Documents{separator}"

    panel._terminal_view.set_current_input("Get-Ch")
    panel._terminal_view.keyPressEvent(_key_event(Qt.Key.Key_Tab, text="\t"))
    assert panel._terminal_view.current_input() == "Get-ChildItem"

    panel.deleteLater()

import os
import subprocess
from types import SimpleNamespace

from PyQt6.QtCore import QEvent, QProcess, Qt
from PyQt6.QtGui import QColor, QKeyEvent, QTextCharFormat, QTextCursor

import meadowpy.ui.terminal_panel as terminal_panel_module
from meadowpy.ui.terminal_panel import TerminalPanel, _TerminalView
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


def test_terminal_ansi_parser_handles_resets_invalid_codes_and_high_contrast():
    base = QTextCharFormat()
    base.setForeground(QColor("#123456"))

    segments = list(
        terminal_panel_module._ansi_segments(
            "plain\x1b[mreset\x1b[1;31;:mbold red\x1b[22;39mnormal",
            base,
            high_contrast=False,
        )
    )

    assert [text for text, _fmt in segments] == [
        "plain",
        "reset",
        "bold red",
        "normal",
    ]
    assert segments[2][1].fontWeight() == terminal_panel_module.QFont.Weight.Bold
    assert segments[2][1].foreground().color().name() == "#c62828"
    assert segments[3][1].foreground().color().name() == "#123456"

    high_contrast = terminal_panel_module._apply_sgr_code(
        QTextCharFormat(),
        32,
        base,
        high_contrast=True,
    )
    unchanged = terminal_panel_module._apply_sgr_code(
        high_contrast,
        999,
        base,
        high_contrast=True,
    )
    assert high_contrast.foreground().color().name() == "#ffffff"
    assert unchanged.foreground().color().name() == "#ffffff"


def test_terminal_view_protects_output_and_routes_navigation(qapp):
    view = _TerminalView()
    submitted = []
    history = []
    interrupts = []
    view.command_submitted.connect(submitted.append)
    view.history_previous_requested.connect(lambda: history.append("up"))
    view.history_next_requested.connect(lambda: history.append("down"))
    view.interrupt_requested.connect(lambda: interrupts.append(True))
    view.append_output("prompt> ", QTextCharFormat(), high_contrast=False)
    view.set_current_input("hello", cursor_column=0)

    view.keyPressEvent(_key_event(Qt.Key.Key_Left))
    view.keyPressEvent(_key_event(Qt.Key.Key_Backspace))
    assert view.current_input() == "hello"

    cursor = view.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(view._input_start + 1, QTextCursor.MoveMode.KeepAnchor)
    view.setTextCursor(cursor)
    assert view._selection_is_editable() is False
    view.keyPressEvent(_key_event(Qt.Key.Key_Delete))
    assert view.toPlainText().startswith("prompt> ")

    view._ensure_editable_cursor()
    assert view.textCursor().position() == view._document_end_position()
    view.keyPressEvent(_key_event(Qt.Key.Key_Home, Qt.KeyboardModifier.ShiftModifier))
    assert view.textCursor().hasSelection()

    view.keyPressEvent(_key_event(Qt.Key.Key_Up))
    view.keyPressEvent(_key_event(Qt.Key.Key_Down))
    cursor = view.textCursor()
    cursor.clearSelection()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    view.setTextCursor(cursor)
    view.keyPressEvent(_key_event(Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier))
    assert history == ["up", "down"]
    assert interrupts == [True]

    view.set_current_input("run")
    view.keyPressEvent(_key_event(Qt.Key.Key_Return, text="\r"))
    assert submitted == ["run"]
    view.deleteLater()


def test_terminal_powershell_completion_runs_encoded_script_and_parses_output(
    monkeypatch,
    qapp,
    tmp_path,
):
    panel = TerminalPanel(settings=FakeSettings(), auto_start_on_show=False)
    panel.set_working_directory(str(tmp_path))
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            stdout=(
                "noise\nMEADOWPY_COMPLETION\t3\t2\n"
                "Documents\\\n#< CLIXML\n<Objs ignored\nDownloads\\\n"
            )
        )

    monkeypatch.setattr(terminal_panel_module.os, "name", "nt")
    monkeypatch.setattr(terminal_panel_module.subprocess, "run", fake_run)

    result = panel._powershell_completion_result("cd Do", 5)

    assert result == terminal_panel_module._CompletionResult(
        3, 2, ["Documents\\", "Downloads\\"]
    )
    args, kwargs = calls[0]
    assert args[0] == "powershell.exe"
    assert "-EncodedCommand" in args
    assert kwargs["cwd"] == str(tmp_path)
    assert kwargs["timeout"] == 1.5

    monkeypatch.setattr(
        terminal_panel_module.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(subprocess.TimeoutExpired("pwsh", 1)),
    )
    assert panel._powershell_completion_result("cd Do", 5) is None

    assert panel._parse_powershell_completion("unrelated") is None
    assert panel._parse_powershell_completion("MEADOWPY_COMPLETION\tbad") is None
    assert panel._parse_powershell_completion(
        "MEADOWPY_COMPLETION\tx\t2"
    ) is None
    panel.deleteLater()


def test_terminal_completion_files_errors_history_and_status_branches(
    monkeypatch,
    qapp,
    tmp_path,
):
    panel = TerminalPanel(
        settings=FakeSettings({"editor.theme": "default_dark"}),
        auto_start_on_show=False,
    )
    panel.set_working_directory(str(tmp_path))
    executable_dir = tmp_path / "bin"
    executable_dir.mkdir()
    (executable_dir / "Alpha.EXE").write_text("", encoding="utf-8")
    (executable_dir / "Alpine.txt").write_text("", encoding="utf-8")
    monkeypatch.setenv(
        "PATH",
        os.pathsep.join((str(executable_dir), str(tmp_path / "missing"))),
    )
    monkeypatch.setenv("PATHEXT", ".EXE;.CMD")
    monkeypatch.setattr(terminal_panel_module.os, "name", "nt")

    candidates = panel._path_executable_candidates("Al")
    assert "Alpha.EXE" in candidates
    assert "Alpha" in candidates
    assert "Alpine.txt" in candidates
    assert panel._completion_search_dir("") == tmp_path
    assert panel._completion_search_dir("missing/") is None
    assert panel._split_path_token("folder/file") == ("folder/", "file")
    assert panel._format_path_completion("two words", "") == "'two words'"
    assert panel._format_path_completion("it's", "'") == "'it's"
    assert panel._token_looks_like_path("C:\\Temp") is True
    assert panel._token_looks_like_path("command") is False

    messages = []
    monkeypatch.setattr(
        panel._terminal_view,
        "append_output",
        lambda text, *args, **kwargs: messages.append(text),
    )
    panel._process = object()
    panel._on_finished(9, QProcess.ExitStatus.CrashExit)
    for error in (
        QProcess.ProcessError.FailedToStart,
        QProcess.ProcessError.Crashed,
        QProcess.ProcessError.Timedout,
        QProcess.ProcessError.WriteError,
        QProcess.ProcessError.ReadError,
        999,
    ):
        panel._on_error(error)
    assert messages[0] == "Terminal process was terminated.\n"
    assert messages[-1] == "Terminal error: 999\n"

    panel._history = [f"command-{index}" for index in range(500)]
    panel._add_history("command-500")
    assert len(panel._history) == 500
    panel._add_history("command-500")
    assert len(panel._history) == 500
    panel._history = []
    panel._on_history_previous()
    panel._on_history_next()
    panel.deleteLater()


def test_terminal_view_cut_paste_and_cursor_repair_branches(qapp):
    view = _TerminalView()
    view.append_output("output> ", QTextCharFormat(), high_contrast=False)
    view.set_current_input("edit")

    cursor = view.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(3, QTextCursor.MoveMode.KeepAnchor)
    view.setTextCursor(cursor)
    view.keyPressEvent(_key_event(Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier))
    assert view.toPlainText().startswith("output> ")

    cursor = view.textCursor()
    cursor.setPosition(0)
    view.setTextCursor(cursor)
    view.keyPressEvent(_key_event(Qt.Key.Key_A, text="a"))
    assert view.current_input().endswith("a")

    view.set_current_input("edit", cursor_column=2)
    cursor = view.textCursor()
    cursor.setPosition(view._input_start)
    cursor.setPosition(view._input_start + 2, QTextCursor.MoveMode.KeepAnchor)
    view.setTextCursor(cursor)
    view.keyPressEvent(_key_event(Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier))
    assert qapp.clipboard().text() == "ed"
    view.deleteLater()


def test_terminal_lifecycle_completion_and_theme_edge_branches(monkeypatch, qapp, tmp_path):
    class Process:
        ProcessState = QProcess.ProcessState
        ProcessChannelMode = QProcess.ProcessChannelMode

        def __init__(self, parent=None):
            self.readyReadStandardOutput = DummySignal()
            self.readyReadStandardError = DummySignal()
            self.finished = DummySignal()
            self.errorOccurred = DummySignal()
            self.state_value = self.ProcessState.NotRunning

        def setWorkingDirectory(self, path):
            self.path = path

        def setProcessChannelMode(self, mode):
            self.mode = mode

        def setProcessEnvironment(self, environment):
            self.environment = environment

        def start(self, program, args):
            self.state_value = self.ProcessState.Running

        def state(self):
            return self.state_value

        def kill(self):
            self.state_value = self.ProcessState.NotRunning

        def waitForFinished(self, timeout):
            return True

    monkeypatch.setattr(terminal_panel_module, "QProcess", Process)
    panel = TerminalPanel(settings=None, auto_start_on_show=False)
    panel.set_working_directory(str(tmp_path))
    panel.start_shell()
    first_process = panel._process
    panel.start_shell()
    assert panel._process is first_process

    panel.restart_shell()
    assert panel._process is not first_process
    panel.stop()
    panel.stop()

    panel._completion_candidates = ["A", "a", "B"]
    assert panel._unique_completion_candidates(panel._completion_candidates) == ["A", "B"]
    monkeypatch.setattr(panel, "_completion_result", lambda line, column: None)
    panel._on_completion_requested("missing", 999, -1)
    assert panel._completion_candidates == []
    panel._on_visibility_changed(False)
    panel._on_visibility_changed(True)
    assert panel._current_theme_name() == ""
    assert panel._is_high_contrast() is False
    panel.deleteLater()

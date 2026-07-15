from pathlib import Path
import sys
from types import SimpleNamespace

from PyQt6.QtWidgets import QMessageBox, QScrollArea

from meadowpy.core.settings import Settings
from meadowpy.ui.dialogs import preferences_dialog as preferences_module
from meadowpy.ui.dialogs.preferences_dialog import PreferencesDialog


def _set_combo_data(combo, value):
    index = combo.findData(value)
    assert index >= 0
    combo.setCurrentIndex(index)


def test_lint_preferences_expose_context_controls_and_preserve_provider_drafts(
    qapp, tmp_path
):
    settings = Settings(tmp_path)
    settings.set("editor.lint_flake8_config_mode", "auto")
    settings.set("editor.lint_flake8_config_path", "flake8-start.cfg")
    settings.set("editor.lint_flake8_timeout_seconds", 10)
    settings.set("editor.lint_pylint_config_mode", "defaults")
    settings.set("editor.lint_pylint_config_path", "pylint-start.toml")
    settings.set("editor.lint_pylint_timeout_seconds", 15)

    dialog = PreferencesDialog(settings)

    lint_page = dialog._pages.widget(2)
    assert isinstance(lint_page, QScrollArea)
    assert lint_page.objectName() == "lintPreferencesScroll"
    assert lint_page.widget().objectName() == "lintPreferencesContent"
    assert dialog._lint_while_typing.isChecked()
    assert dialog._lint_delay.minimum() == 100
    assert dialog._lint_delay.maximum() == 5000
    assert dialog._lint_interpreter_mode_combo.currentData() == "selected"
    assert dialog._lint_working_directory_combo.currentData() == "project"
    assert not hasattr(dialog, "_lint_enable_rules")
    assert not hasattr(dialog, "_lint_disable_rules")

    _set_combo_data(dialog._lint_config_mode_combo, "explicit")
    dialog._lint_config_path.setText("flake8-draft.cfg")
    dialog._lint_timeout.setValue(24)

    dialog._linter_combo.setCurrentText("pylint")
    assert dialog._lint_config_mode_combo.currentData() == "defaults"
    assert dialog._lint_config_path.text() == "pylint-start.toml"
    assert dialog._lint_timeout.value() == 15

    _set_combo_data(dialog._lint_config_mode_combo, "auto")
    dialog._lint_config_path.setText("pylint-draft.toml")
    dialog._lint_timeout.setValue(31)

    dialog._linter_combo.setCurrentText("flake8")
    assert dialog._lint_config_mode_combo.currentData() == "explicit"
    assert dialog._lint_config_path.text() == "flake8-draft.cfg"
    assert dialog._lint_timeout.value() == 24
    assert (
        dialog._pending_changes["editor.lint_pylint_config_path"]
        == "pylint-draft.toml"
    )
    assert dialog._pending_changes["editor.lint_pylint_timeout_seconds"] == 31

    dialog.deleteLater()


def test_lint_preferences_validate_before_any_setting_is_persisted(
    monkeypatch, qapp, tmp_path
):
    settings = Settings(tmp_path)
    dialog = PreferencesDialog(settings)
    warnings = []
    monkeypatch.setattr(
        preferences_module.QMessageBox,
        "warning",
        lambda parent, title, body: warnings.append((title, body)),
    )

    _set_combo_data(dialog._lint_interpreter_mode_combo, "custom")
    missing = tmp_path / "missing-python.exe"
    dialog._lint_interpreter_path.setText(str(missing))
    dialog._stage("editor.font_size", 19)

    assert dialog._apply() is False
    assert settings.get("editor.font_size") != 19
    assert dialog._pending_changes["editor.font_size"] == 19
    assert "does not exist" in warnings[-1][1]

    accepted = []
    monkeypatch.setattr(dialog, "accept", lambda: accepted.append(True))
    dialog._apply_and_close()
    assert accepted == []

    interpreter = tmp_path / "python.exe"
    interpreter.write_text("", encoding="utf-8")
    dialog._lint_interpreter_path.setText(str(interpreter))
    assert dialog._apply() is True
    assert settings.get("editor.font_size") == 19
    assert (
        settings.get("editor.lint_interpreter_path")
        == PreferencesDialog._canonical_path(interpreter)
    )

    dialog._stage("editor.font_size", 20)
    dialog._apply_and_close()
    assert accepted == [True]
    dialog.deleteLater()


def test_lint_preferences_trust_project_and_validate_explicit_config(
    monkeypatch, qapp, tmp_path
):
    project = tmp_path / "project"
    project.mkdir()
    config = project / ".flake8"
    config.write_text("[flake8]\nmax-line-length = 100\n", encoding="utf-8")

    settings = Settings(tmp_path / "settings")
    settings.set("general.project_folder", str(project))
    dialog = PreferencesDialog(settings)

    answers = iter(
        [QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes]
    )
    monkeypatch.setattr(
        preferences_module.QMessageBox,
        "question",
        lambda *args, **kwargs: next(answers),
    )

    dialog._trust_lint_project()
    assert "security.trusted_lint_roots" not in dialog._pending_changes
    dialog._trust_lint_project()

    canonical_project = PreferencesDialog._canonical_path(project)
    assert dialog._pending_changes["security.trusted_lint_roots"] == [
        canonical_project
    ]
    assert "Lint trust: Trusted" == dialog._lint_trust_status_label.text()

    _set_combo_data(dialog._lint_config_mode_combo, "explicit")
    dialog._lint_config_path.setText(str(config))
    assert dialog._apply() is True
    assert settings.get("security.trusted_lint_roots") == [canonical_project]
    assert (
        settings.get("editor.lint_flake8_config_path")
        == PreferencesDialog._canonical_path(config)
    )

    dialog._revoke_lint_project()
    assert dialog._pending_changes["security.trusted_lint_roots"] == []
    assert dialog._apply() is True
    assert settings.get("security.trusted_lint_roots") == []
    dialog.deleteLater()


def test_lint_preferences_reject_explicit_config_outside_trusted_root(
    monkeypatch, qapp, tmp_path
):
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside.cfg"
    outside.write_text("[flake8]\n", encoding="utf-8")

    settings = Settings(tmp_path / "settings")
    settings.set("general.project_folder", str(project))
    settings.set(
        "security.trusted_lint_roots",
        [PreferencesDialog._canonical_path(project)],
    )
    initial_mode = settings.get("editor.lint_flake8_config_mode", "auto")
    dialog = PreferencesDialog(settings)
    warnings = []
    monkeypatch.setattr(
        preferences_module.QMessageBox,
        "warning",
        lambda parent, title, body: warnings.append((title, body)),
    )

    _set_combo_data(dialog._lint_config_mode_combo, "explicit")
    dialog._lint_config_path.setText(str(outside))

    assert dialog._apply() is False
    assert "trusted project folder" in warnings[-1][1]
    assert settings.get("editor.lint_flake8_config_mode", "auto") == initial_mode
    dialog.deleteLater()


def test_lint_preferences_reject_config_from_a_different_trusted_project(
    monkeypatch, qapp, tmp_path
):
    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    project_a.mkdir()
    project_b.mkdir()
    config_b = project_b / ".flake8"
    config_b.write_text("[flake8]\n", encoding="utf-8")
    settings = Settings(tmp_path / "settings")
    settings.set("general.project_folder", str(project_a))
    settings.set(
        "security.trusted_lint_roots",
        [
            PreferencesDialog._canonical_path(project_a),
            PreferencesDialog._canonical_path(project_b),
        ],
    )
    dialog = PreferencesDialog(settings)
    warnings = []
    monkeypatch.setattr(
        preferences_module.QMessageBox,
        "warning",
        lambda parent, title, body: warnings.append((title, body)),
    )

    _set_combo_data(dialog._lint_config_mode_combo, "explicit")
    dialog._lint_config_path.setText(str(config_b))

    assert dialog._apply() is False
    assert "current target's trusted project folder" in warnings[-1][1]
    assert settings.get("editor.lint_flake8_config_path", "") == ""
    dialog.deleteLater()


def test_lint_preferences_show_and_open_auto_detected_effective_config(
    monkeypatch, qapp, tmp_path
):
    project = tmp_path / "project"
    project.mkdir()
    config = project / ".flake8"
    config.write_text("[flake8]\nignore = E203\n", encoding="utf-8")

    settings = Settings(tmp_path / "settings")
    settings.set("general.project_folder", str(project))
    settings.set(
        "security.trusted_lint_roots",
        [PreferencesDialog._canonical_path(project)],
    )
    settings.set("editor.lint_flake8_config_mode", "auto")
    dialog = PreferencesDialog(settings)

    canonical_config = PreferencesDialog._canonical_path(config)
    assert (
        canonical_config.casefold()
        in dialog._lint_effective_summary.text().casefold()
    )
    assert dialog._open_effective_config_btn.isEnabled()

    opened = []
    monkeypatch.setattr(
        preferences_module,
        "QDesktopServices",
        SimpleNamespace(openUrl=lambda url: opened.append(url) or True),
    )
    dialog._open_effective_lint_config()
    assert Path(opened[0].toLocalFile()).resolve() == config.resolve()

    _set_combo_data(dialog._lint_config_mode_combo, "defaults")
    assert not dialog._open_effective_config_btn.isEnabled()
    assert "Linter defaults only" in dialog._lint_effective_summary.text()
    dialog.deleteLater()


def test_lint_preferences_test_effective_settings_without_blocking(
    monkeypatch, qapp, tmp_path
):
    class FakeSignal:
        def __init__(self):
            self.callbacks = []

        def connect(self, callback):
            self.callbacks.append(callback)

        def emit(self, *args):
            for callback in list(self.callbacks):
                callback(*args)

    class FakeProcess:
        instances = []

        class ProcessChannelMode:
            MergedChannels = object()

        class ExitStatus:
            NormalExit = object()

        def __init__(self, parent):
            self.parent = parent
            self.started = FakeSignal()
            self.finished = FakeSignal()
            self.errorOccurred = FakeSignal()
            self.output = b""
            self.start_called = False
            self.deleted = False
            self.written = b""
            FakeProcess.instances.append(self)

        def setProcessChannelMode(self, mode):
            self.channel_mode = mode

        def setProgram(self, program):
            self.program = program

        def setArguments(self, arguments):
            self.arguments = arguments

        def setWorkingDirectory(self, cwd):
            self.cwd = cwd

        def start(self):
            self.start_called = True
            self.started.emit()

        def write(self, data):
            self.written += data

        def closeWriteChannel(self):
            self.write_channel_closed = True

        def readAllStandardOutput(self):
            return self.output

        def errorString(self):
            return "could not start"

        def kill(self):
            self.killed = True

        def deleteLater(self):
            self.deleted = True

    settings = Settings(tmp_path)
    dialog = PreferencesDialog(settings)
    monkeypatch.setattr(preferences_module, "QProcess", FakeProcess)

    dialog._test_linter_settings()

    process = FakeProcess.instances[0]
    assert process.start_called is True
    assert Path(process.program).resolve() == Path(sys.executable).resolve()
    assert process.arguments == [
        "-m",
        "flake8",
        "--isolated",
        "--format=%(path)s:%(row)d:%(col)d: %(code)s %(text)s",
        "--exit-zero",
        "--stdin-display-name",
        "untitled.py",
        "-",
    ]
    assert process.written == b'"""MeadowPy linter settings test."""\n'
    assert process.write_channel_closed is True
    assert not dialog._test_linter_btn.isEnabled()

    process.output = b"untitled.py:1:1: X100 custom finding\n"
    process.finished.emit(0, FakeProcess.ExitStatus.NormalExit)

    assert dialog._lint_test_result.text() == (
        "Test passed: flake8 loaded the effective settings. "
        "The smoke source produced lint findings."
    )
    assert dialog._test_linter_btn.isEnabled()
    assert dialog._lint_test_process is None
    assert process.deleted is True

    dialog._test_linter_settings()
    failed_process = FakeProcess.instances[1]
    failed_process.output = (
        b"There was a critical error during execution of Flake8: bad plugin"
    )
    failed_process.finished.emit(1, FakeProcess.ExitStatus.NormalExit)

    assert dialog._lint_test_result.text().startswith(
        "Test failed (exit code 1): There was a critical error"
    )

    dialog._test_linter_settings()
    stale_process = FakeProcess.instances[2]
    dialog._lint_timeout.setValue(dialog._lint_timeout.value() + 1)
    stale_process.finished.emit(0, FakeProcess.ExitStatus.NormalExit)

    assert dialog._lint_test_result.text().startswith(
        "Test result discarded because lint settings changed"
    )
    dialog.deleteLater()

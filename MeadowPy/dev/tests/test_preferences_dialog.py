from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QApplication, QMessageBox, QScrollArea, QWidget

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


def test_lint_page_value_controls_scroll_without_changing_values(
    qapp, tmp_path
):
    project = tmp_path / "project"
    project.mkdir()
    settings = Settings(tmp_path / "settings")
    settings.set("editor.linting_enabled", True)
    settings.set("general.project_folder", str(project))
    settings.set("security.trusted_lint_roots", [str(project)])
    dialog = PreferencesDialog(settings)
    dialog._category_list.setCurrentRow(2)
    dialog.show()
    qapp.processEvents()
    controls = [
        dialog._linter_combo,
        dialog._lint_delay,
        dialog._lint_interpreter_mode_combo,
        dialog._lint_working_directory_combo,
        dialog._lint_config_mode_combo,
        dialog._lint_timeout,
    ]
    before = [
        control.value() if hasattr(control, "value") else control.currentIndex()
        for control in controls
    ]

    lint_page = dialog._pages.widget(2)
    scroll_bar = lint_page.verticalScrollBar()
    assert scroll_bar.maximum() > 0
    for control in controls:
        scroll_bar.setValue(0)
        global_position = control.mapToGlobal(QPoint(5, 5))
        wheel_event = QWheelEvent(
            QPointF(5, 5),
            QPointF(global_position),
            QPoint(),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )
        QApplication.sendEvent(control, wheel_event)
        qapp.processEvents()
        assert scroll_bar.value() > 0

    after = [
        control.value() if hasattr(control, "value") else control.currentIndex()
        for control in controls
    ]
    assert after == before
    dialog.deleteLater()


def test_lint_preferences_infer_narrow_target_from_active_file(
    monkeypatch, qapp, tmp_path
):
    explorer_root = tmp_path / "Documents"
    project = explorer_root / "nested-project"
    source = project / "src" / "main.py"
    source.parent.mkdir(parents=True)
    (project / ".git").mkdir()
    source.write_text("print('hello')\n", encoding="utf-8")

    parent = QWidget()
    parent._tab_manager = SimpleNamespace(
        current_editor=lambda: SimpleNamespace(file_path=str(source))
    )
    parent._file_explorer = SimpleNamespace(root_path=str(explorer_root))
    dialog = PreferencesDialog(Settings(tmp_path / "settings"), parent)
    monkeypatch.setattr(
        preferences_module.QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

    canonical_project = PreferencesDialog._canonical_path(project)
    assert dialog._current_lint_project() == canonical_project
    assert canonical_project in dialog._lint_project_label.text()

    dialog._trust_lint_project()

    assert dialog._pending_changes["security.trusted_lint_roots"] == [
        canonical_project
    ]
    dialog.deleteLater()
    parent.deleteLater()


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


def test_wheel_forwarding_handles_orphan_controls_and_pixel_deltas(qapp):
    orphan = QWidget()
    orphan_event = QWheelEvent(
        QPointF(1, 1),
        QPointF(1, 1),
        QPoint(),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    preferences_module._forward_wheel_to_scroll_area(orphan, orphan_event)
    assert not orphan_event.isAccepted()

    area = QScrollArea()
    content = QWidget()
    content.resize(800, 800)
    control = QWidget(content)
    area.setWidget(content)
    area.resize(100, 100)
    area.show()
    qapp.processEvents()
    pixel_event = QWheelEvent(
        QPointF(1, 1),
        QPointF(1, 1),
        QPoint(-15, 0),
        QPoint(),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    preferences_module._forward_wheel_to_scroll_area(control, pixel_event)
    assert pixel_event.isAccepted()
    assert area.horizontalScrollBar().value() == 15
    area.deleteLater()
    orphan.deleteLater()


def test_lint_control_helpers_tolerate_corrupt_saved_values(qapp, tmp_path):
    settings = Settings(tmp_path)
    settings.set("editor.lint_delay_ms", True)
    dialog = PreferencesDialog(settings)

    assert dialog._bounded_int_setting("editor.lint_delay_ms", 750, 100, 5000) == 750
    settings.set("editor.lint_delay_ms", "invalid")
    assert dialog._bounded_int_setting("editor.lint_delay_ms", 750, 100, 5000) == 750
    dialog._set_combo_data(dialog._lint_config_mode_combo, "unknown", "defaults")
    assert dialog._lint_config_mode_combo.currentData() == "defaults"

    before = dialog._active_lint_provider
    dialog._on_linter_changed("ruff")
    assert dialog._active_lint_provider == before
    dialog._on_lint_working_directory_changed(-1)
    assert dialog._pending_changes["editor.lint_working_directory"] == "project"

    settings.set("editor.lint_flake8_config_mode", "broken")
    settings.set("editor.lint_flake8_timeout_seconds", True)
    dialog._load_lint_provider_controls("flake8")
    assert dialog._lint_config_mode_combo.currentData() == "defaults"
    assert dialog._lint_timeout.value() == 10
    settings.set("editor.lint_flake8_timeout_seconds", "broken")
    dialog._load_lint_provider_controls("flake8")
    assert dialog._lint_timeout.value() == 10
    dialog.deleteLater()


def test_lint_browse_actions_use_current_parent_and_stage_selected_paths(
    monkeypatch, qapp, tmp_path
):
    interpreter = tmp_path / "bin" / "python.exe"
    interpreter.parent.mkdir()
    interpreter.write_text("", encoding="utf-8")
    config = tmp_path / "quality" / ".flake8"
    config.parent.mkdir()
    config.write_text("[flake8]\n", encoding="utf-8")
    dialog = PreferencesDialog(Settings(tmp_path / "settings"))
    dialog._lint_interpreter_path.setText(str(interpreter))
    dialog._lint_config_path.setText(str(config))
    calls = []

    def choose(*args):
        calls.append(args)
        return (str(interpreter if len(calls) == 1 else config), "")

    monkeypatch.setattr(preferences_module.QFileDialog, "getOpenFileName", choose)
    dialog._browse_lint_interpreter()
    dialog._browse_lint_config()

    assert calls[0][2] == str(interpreter.parent)
    assert calls[1][2] == str(config.parent)
    assert dialog._lint_interpreter_path.text() == str(interpreter)
    assert dialog._lint_config_path.text() == str(config)
    dialog.deleteLater()


def test_lint_trust_actions_handle_missing_and_already_trusted_targets(
    monkeypatch, qapp, tmp_path
):
    dialog = PreferencesDialog(Settings(tmp_path))
    warnings = []
    monkeypatch.setattr(
        preferences_module.QMessageBox,
        "warning",
        lambda *args: warnings.append(args),
    )
    dialog._trust_lint_project()
    dialog._revoke_lint_project()
    assert warnings and "No Lint Target" in warnings[0][1]

    project = tmp_path / "project"
    project.mkdir()
    canonical = dialog._canonical_path(project)
    dialog._stage("general.project_folder", str(project))
    dialog._stage("security.trusted_lint_roots", [canonical])
    monkeypatch.setattr(
        preferences_module.QMessageBox,
        "question",
        lambda *args: (_ for _ in ()).throw(AssertionError("already trusted")),
    )
    dialog._trust_lint_project()
    assert dialog._pending_changes["security.trusted_lint_roots"] == [canonical]
    dialog.deleteLater()


def test_lint_path_and_project_helpers_ignore_invalid_inputs(monkeypatch, qapp, tmp_path):
    settings = Settings(tmp_path)
    settings.set("general.project_folder", 42)
    settings.set("security.trusted_lint_roots", "invalid")
    dialog = PreferencesDialog(settings)

    assert dialog._configured_lint_project() is None
    assert dialog._trusted_lint_roots() == []
    assert dialog._path_is_within("a", "b") in {True, False}

    original = PreferencesDialog._canonical_path
    monkeypatch.setattr(
        PreferencesDialog,
        "_canonical_path",
        staticmethod(lambda value: (_ for _ in ()).throw(OSError("bad path"))),
    )
    assert dialog._path_is_within("a", "b") is False
    settings.set("general.project_folder", "project")
    assert dialog._configured_lint_project() is None
    settings.set("security.trusted_lint_roots", ["", 3, "project"])
    assert dialog._trusted_lint_roots() == []

    monkeypatch.setattr(PreferencesDialog, "_canonical_path", staticmethod(original))
    repeated = str(tmp_path / "same")
    settings.set("security.trusted_lint_roots", [repeated, repeated])
    assert dialog._trusted_lint_roots() == [dialog._canonical_path(repeated)]
    dialog.deleteLater()


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"editor.linter": "ruff"}, "Flake8 or Pylint"),
        ({"editor.lint_delay_ms": True}, "whole number"),
        ({"editor.lint_delay_ms": 99}, "between 100"),
        ({"editor.lint_interpreter_mode": "invalid"}, "interpreter mode"),
        ({"editor.lint_working_directory": "cwd"}, "working directory"),
        ({"editor.lint_interpreter_path": 42}, "must be text"),
        ({"security.trusted_lint_roots": "root"}, "list of folders"),
        ({"security.trusted_lint_roots": [""]}, "invalid folder"),
        ({"editor.lint_flake8_config_mode": "invalid"}, "config mode"),
        ({"editor.lint_flake8_timeout_seconds": True}, "whole number"),
        ({"editor.lint_flake8_timeout_seconds": 121}, "between 1"),
        ({"editor.lint_flake8_config_path": 42}, "must be text"),
    ],
)
def test_pending_lint_validation_rejects_each_malformed_value(
    qapp, tmp_path, changes, message
):
    dialog = PreferencesDialog(Settings(tmp_path))
    dialog._pending_changes = dict(changes)
    validated, error = dialog._validate_pending_changes()
    assert validated is None
    assert message in error
    dialog.deleteLater()


def test_pending_lint_validation_normalizes_empty_and_duplicate_paths(qapp, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    dialog = PreferencesDialog(Settings(tmp_path / "settings"))
    dialog._pending_changes = {
        "editor.lint_interpreter_path": "   ",
        "editor.lint_flake8_config_path": "   ",
        "security.trusted_lint_roots": [str(project), str(project)],
    }

    validated, error = dialog._validate_pending_changes()

    assert error is None
    assert validated["editor.lint_interpreter_path"] == ""
    assert validated["editor.lint_flake8_config_path"] == ""
    assert validated["security.trusted_lint_roots"] == [
        dialog._canonical_path(project)
    ]
    dialog.deleteLater()


def test_lint_test_guard_errors_timeout_and_open_config_failures(
    monkeypatch, qapp, tmp_path
):
    dialog = PreferencesDialog(Settings(tmp_path))
    dialog._lint_test_process = object()
    dialog._test_linter_settings()

    dialog._lint_test_process = None
    monkeypatch.setattr(dialog, "_resolve_pending_lint_context", lambda: (None, "bad settings"))
    dialog._test_linter_settings()
    assert "bad settings" in dialog._lint_test_result.text()

    monkeypatch.setattr(dialog, "_resolve_pending_lint_context", lambda: (SimpleNamespace(config_path=None), None))
    infos = []
    monkeypatch.setattr(preferences_module.QMessageBox, "information", lambda *args: infos.append(args))
    dialog._open_effective_lint_config()
    assert infos

    class Process:
        def __init__(self, output=b""):
            self.output = output
            self.killed = False
            self.deleted = False

        def readAllStandardOutput(self):
            return self.output

        def errorString(self):
            return "launch failed"

        def kill(self):
            self.killed = True

        def deleteLater(self):
            self.deleted = True

    process = Process()
    dialog._lint_test_process = process
    dialog._lint_test_stale = False
    dialog._on_lint_test_timeout()
    assert process.killed is True
    assert "timed out" in dialog._lint_test_result.text()
    dialog._on_lint_test_error(None)
    assert dialog._lint_test_process is None

    dialog._write_lint_test_source()
    dialog._on_lint_test_finished(1, preferences_module.QProcess.ExitStatus.CrashExit)
    dialog._on_lint_test_error(None)
    dialog._on_lint_test_timeout()
    dialog._finish_lint_test()
    dialog.deleteLater()


def test_lint_context_helpers_surface_resolution_failures(monkeypatch, qapp, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    settings = Settings(tmp_path / "settings")
    settings.set("general.project_folder", str(project))
    dialog = PreferencesDialog(settings)

    monkeypatch.setattr(
        preferences_module,
        "resolve_lint_target_root",
        lambda *args: (_ for _ in ()).throw(preferences_module.LintContextError("bad target")),
    )
    assert dialog._current_lint_project() is None
    assert dialog._matching_lint_trust_boundary([str(project)]) is None

    monkeypatch.setattr(
        preferences_module,
        "resolve_lint_context",
        lambda **kwargs: (_ for _ in ()).throw(preferences_module.LintContextError("bad context")),
    )
    context, error = dialog._resolve_pending_lint_context()
    assert context is None
    assert error == "bad context"
    dialog.deleteLater()


def test_open_effective_config_warns_when_desktop_service_rejects_url(
    monkeypatch, qapp, tmp_path
):
    dialog = PreferencesDialog(Settings(tmp_path))
    config = tmp_path / ".flake8"
    config.write_text("[flake8]\n", encoding="utf-8")
    monkeypatch.setattr(dialog, "_effective_lint_config_path", lambda: str(config))
    monkeypatch.setattr(
        preferences_module,
        "QDesktopServices",
        SimpleNamespace(openUrl=lambda url: False),
    )
    warnings = []
    monkeypatch.setattr(preferences_module.QMessageBox, "warning", lambda *args: warnings.append(args))
    dialog._open_effective_lint_config()
    assert warnings and warnings[0][1] == "Could Not Open Configuration"
    dialog.deleteLater()


def test_linter_test_reports_command_build_and_process_outcome_variants(
    monkeypatch, qapp, tmp_path
):
    dialog = PreferencesDialog(Settings(tmp_path))
    context = SimpleNamespace(config_path=None, timeout_seconds=1)
    monkeypatch.setattr(dialog, "_resolve_pending_lint_context", lambda: (context, None))
    monkeypatch.setattr(
        preferences_module,
        "build_linter_stdin_command",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("bad command")),
    )
    dialog._test_linter_settings()
    assert "bad command" in dialog._lint_test_result.text()

    class Process:
        def __init__(self, output=b""):
            self.output = output
            self.deleted = False

        def readAllStandardOutput(self):
            return self.output

        def errorString(self):
            return "launch failed"

        def deleteLater(self):
            self.deleted = True

        def kill(self):
            self.killed = True

    process = Process()
    dialog._lint_test_process = process
    dialog._lint_test_provider = "flake8"
    dialog._lint_test_stale = False
    dialog._lint_test_timed_out = False
    dialog._on_lint_test_finished(0, preferences_module.QProcess.ExitStatus.NormalExit)
    assert dialog._lint_test_result.text() == "Test passed: flake8 loaded the effective settings."

    process = Process(b"plugin failed")
    dialog._lint_test_process = process
    dialog._lint_test_stale = False
    dialog._lint_test_timed_out = False
    dialog._on_lint_test_error(None)
    assert dialog._lint_test_result.text() == "Test failed: plugin failed"

    process = Process()
    dialog._lint_test_process = process
    dialog._lint_test_stale = True
    dialog._lint_test_timed_out = False
    dialog._on_lint_test_error(None)
    assert "discarded" in dialog._lint_test_result.text()

    process = Process()
    dialog._lint_test_process = process
    dialog._lint_test_stale = True
    dialog._on_lint_test_timeout()
    assert "discarded" in dialog._lint_test_result.text()
    assert process.killed is True
    dialog.deleteLater()

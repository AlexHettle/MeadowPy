import subprocess
import sys
from types import SimpleNamespace

from meadowpy.core.interpreter_manager import InterpreterManager


def test_get_interpreter_prefers_existing_configured_path(tmp_path):
    configured = tmp_path / "python.exe"
    configured.write_text("", encoding="utf-8")
    settings = SimpleNamespace(get=lambda key: str(configured))

    assert InterpreterManager().get_interpreter(settings) == str(configured)


def test_get_interpreter_falls_back_to_running_python():
    settings = SimpleNamespace(get=lambda key: "")

    assert InterpreterManager().get_interpreter(settings) == sys.executable


def test_venv_python_detects_windows_and_unix_layouts(tmp_path):
    win_venv = tmp_path / "win"
    unix_venv = tmp_path / "unix"
    (win_venv / "Scripts").mkdir(parents=True)
    (unix_venv / "bin").mkdir(parents=True)
    win_python = win_venv / "Scripts" / "python.exe"
    unix_python = unix_venv / "bin" / "python"
    win_python.write_text("", encoding="utf-8")
    unix_python.write_text("", encoding="utf-8")

    assert InterpreterManager._venv_python(win_venv) == win_python
    assert InterpreterManager._venv_python(unix_venv) == unix_python
    assert InterpreterManager._venv_python(tmp_path / "missing") is None


def test_detect_interpreters_finds_system_and_nearby_venvs(tmp_path, monkeypatch):
    project_dir = tmp_path / "project"
    src_dir = project_dir / "src"
    src_dir.mkdir(parents=True)
    script = src_dir / "main.py"
    script.write_text("print('hi')", encoding="utf-8")

    local_venv = src_dir / ".venv" / "Scripts"
    parent_venv = project_dir / "venv" / "Scripts"
    local_venv.mkdir(parents=True)
    parent_venv.mkdir(parents=True)
    local_python = local_venv / "python.exe"
    parent_python = parent_venv / "python.exe"
    local_python.write_text("", encoding="utf-8")
    parent_python.write_text("", encoding="utf-8")

    monkeypatch.setattr("meadowpy.core.interpreter_manager.sys.executable", str(tmp_path / "system.exe"))
    monkeypatch.setattr(
        InterpreterManager,
        "_get_version",
        staticmethod(lambda path: "3.12.1" if "system" in path else "3.11.9"),
    )

    interpreters = InterpreterManager().detect_interpreters(str(script))

    assert interpreters[0].label == "System Python 3.12.1"
    labels = {item.label for item in interpreters[1:]}
    assert "venv (./.venv) Python 3.11.9" in labels
    assert any(label.startswith("venv (") for label in labels)


def test_create_venv_runs_expected_command(tmp_path, monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("meadowpy.core.interpreter_manager.subprocess.run", fake_run)

    result = InterpreterManager().create_venv(str(tmp_path), "dev", "python.exe")

    assert result == str(tmp_path / "dev")
    command, kwargs = calls[0]
    assert command == ["python.exe", "-m", "venv", str(tmp_path / "dev")]
    assert kwargs["check"] is True
    assert kwargs["timeout"] == 60


def test_get_version_returns_unknown_when_subprocess_fails(monkeypatch):
    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="python", timeout=5)

    monkeypatch.setattr("meadowpy.core.interpreter_manager.subprocess.run", raise_timeout)

    assert InterpreterManager._get_version("python.exe") == "unknown"


def test_relative_label_uses_relative_path_when_possible(tmp_path):
    file_path = tmp_path / "pkg" / "main.py"
    venv_dir = file_path.parent / ".venv"
    venv_dir.mkdir(parents=True)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("", encoding="utf-8")

    assert InterpreterManager._relative_label(venv_dir, str(file_path)) == "./.venv"

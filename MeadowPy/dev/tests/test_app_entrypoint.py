from __future__ import annotations

import sys
import importlib
import pathlib
from types import SimpleNamespace

import pytest


@pytest.fixture
def main_module(monkeypatch, tmp_path):
    monkeypatch.setattr(pathlib.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(sys, "platform", "linux")
    sys.modules.pop("meadowpy.__main__", None)
    module = importlib.import_module("meadowpy.__main__")
    try:
        yield module
    finally:
        if module._CRASH_LOG_FILE is not None:
            module._CRASH_LOG_FILE.close()
            module._CRASH_LOG_FILE = None


def test_enable_crash_logging_writes_startup_banner(main_module, monkeypatch, tmp_path):
    enabled = []
    monkeypatch.setattr(main_module.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        main_module.faulthandler,
        "enable",
        lambda file, all_threads: enabled.append((file.name, all_threads)),
    )

    main_module._enable_crash_logging()

    try:
        assert (tmp_path / ".meadowpy" / "meadowpy.log").read_text(
            encoding="utf-8"
        ).endswith("--- MeadowPy process started ---\n")
        assert enabled == [(str(tmp_path / ".meadowpy" / "meadowpy.log"), True)]
    finally:
        if main_module._CRASH_LOG_FILE is not None:
            main_module._CRASH_LOG_FILE.close()
            main_module._CRASH_LOG_FILE = None


def test_enable_crash_logging_swallows_setup_errors(main_module, monkeypatch):
    monkeypatch.setattr(
        main_module.Path,
        "home",
        lambda: (_ for _ in ()).throw(OSError("no home")),
    )

    main_module._enable_crash_logging()

    assert main_module._CRASH_LOG_FILE is None


def test_set_windows_app_id_uses_ctypes_only_on_windows(main_module, monkeypatch):
    calls = []
    fake_ctypes = SimpleNamespace(
        windll=SimpleNamespace(
            shell32=SimpleNamespace(
                SetCurrentProcessExplicitAppUserModelID=lambda app_id: calls.append(app_id)
            )
        )
    )

    monkeypatch.setattr(main_module.sys, "platform", "linux")
    main_module._set_windows_app_id()
    assert calls == []

    monkeypatch.setattr(main_module.sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)
    main_module._set_windows_app_id()
    assert calls == [main_module.APP_ID]


def test_main_runs_app_and_exits_with_return_code(main_module, monkeypatch):
    created = []

    class FakeApp:
        def __init__(self, argv):
            created.append(argv)

        def run(self):
            return 11

    monkeypatch.setattr(main_module, "MeadowPyApp", FakeApp)
    monkeypatch.setattr(main_module.sys, "argv", ["meadowpy", "demo.py"])

    with pytest.raises(SystemExit) as exc:
        main_module.main()

    assert created == [["meadowpy", "demo.py"]]
    assert exc.value.code == 11

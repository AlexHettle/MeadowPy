from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import pytest


pytestmark = pytest.mark.skipif(
    os.name != "nt",
    reason="Windows batch files and shortcuts require Windows",
)

APP_SOURCE = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = APP_SOURCE.parent
SETUP_BATCH = REPOSITORY_ROOT / "setup.bat"
RUN_BATCH = APP_SOURCE / "Run MeadowPy.bat"
SHORTCUT_SCRIPT = APP_SOURCE / "meadowpy" / "resources" / "create_shortcut.ps1"
CMD_EXE = os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")


def _special_install_root(tmp_path: Path) -> Path:
    root = tmp_path / "MeadowPy QA's (fresh) & bang!"
    root.mkdir()
    return root


@pytest.fixture
def short_tmp_path():
    # WScript.Shell truncates IconLocation beyond the legacy MAX_PATH limit.
    with tempfile.TemporaryDirectory(prefix="meadowpy-") as directory:
        yield Path(directory)


def test_setup_resolves_special_character_install_path(tmp_path):
    install_root = _special_install_root(tmp_path)
    package_dir = install_root / "MeadowPy" / "meadowpy"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    shutil.copy2(SETUP_BATCH, install_root / "setup.bat")

    env = os.environ.copy()
    env["PATH"] = ""
    completed = subprocess.run(
        [
            CMD_EXE,
            "/d",
            "/v:on",
            "/c",
            "call setup.bat < nul",
        ],
        cwd=install_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=15,
        check=False,
    )

    assert completed.returncode == 1
    assert "[ERROR] Python was not found" in completed.stdout
    assert "application folder was not found" not in completed.stdout


def test_shortcut_helper_preserves_special_character_paths(short_tmp_path):
    install_root = _special_install_root(short_tmp_path)
    app_dir = install_root / "MeadowPy"
    pythonw_path = app_dir / ".venv" / "Scripts" / "pythonw.exe"
    icon_path = app_dir / "meadowpy" / "resources" / "icons" / "meadowpy.ico"
    shortcut_path = install_root / "MeadowPy.lnk"
    assert len(str(icon_path)) < 260
    pythonw_path.parent.mkdir(parents=True)
    icon_path.parent.mkdir(parents=True)
    pythonw_path.write_bytes(b"test executable placeholder")
    icon_path.write_bytes(b"test icon placeholder")

    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SHORTCUT_SCRIPT),
            "-ShortcutPath",
            str(shortcut_path),
            "-AppDirectory",
            str(app_dir),
        ],
        check=True,
        timeout=15,
    )

    env = os.environ.copy()
    env["MEADOWPY_TEST_SHORTCUT"] = str(shortcut_path)
    inspected = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            (
                "$s = (New-Object -ComObject WScript.Shell).CreateShortcut("
                "$env:MEADOWPY_TEST_SHORTCUT); "
                "[ordered]@{ TargetPath = $s.TargetPath; Arguments = $s.Arguments; "
                "WorkingDirectory = $s.WorkingDirectory; IconLocation = "
                "$s.IconLocation } | ConvertTo-Json -Compress"
            ),
        ],
        env=env,
        stdout=subprocess.PIPE,
        text=True,
        check=True,
        timeout=15,
    )
    shortcut = json.loads(inspected.stdout)

    assert set(shortcut) == {
        "TargetPath",
        "Arguments",
        "WorkingDirectory",
        "IconLocation",
    }
    assert shortcut["Arguments"] == "-m meadowpy"
    assert Path(shortcut["TargetPath"]).samefile(pythonw_path)
    assert Path(shortcut["WorkingDirectory"]).samefile(app_dir)

    shortcut_icon, shortcut_icon_index = shortcut["IconLocation"].rsplit(",", 1)
    assert Path(shortcut_icon).samefile(icon_path)
    assert shortcut_icon_index == "0"


def test_run_batch_launches_from_special_character_path(tmp_path):
    install_root = _special_install_root(tmp_path)
    app_dir = install_root / "MeadowPy"
    package_dir = app_dir / "meadowpy"
    package_dir.mkdir(parents=True)
    shutil.copy2(RUN_BATCH, app_dir / RUN_BATCH.name)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "__main__.py").write_text(
        "from pathlib import Path\n"
        'Path("launch-marker.txt").write_text("launched", encoding="utf-8")\n',
        encoding="utf-8",
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "venv",
            "--without-pip",
            str(app_dir / ".venv"),
        ],
        check=True,
        timeout=30,
    )

    user_profile = install_root / "User's (profile) & bang!"
    user_profile.mkdir()
    env = os.environ.copy()
    env["USERPROFILE"] = str(user_profile)
    completed = subprocess.run(
        f'"{CMD_EXE}" /d /v:on /c ""{RUN_BATCH.name}""',
        cwd=app_dir,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout
    assert (app_dir / "launch-marker.txt").read_text(encoding="utf-8") == "launched"
    assert "Launching MeadowPy" in (
        user_profile / ".meadowpy" / "meadowpy.log"
    ).read_text(encoding="utf-8")

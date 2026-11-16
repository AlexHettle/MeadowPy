"""Regression coverage for case-only file explorer renames."""

import os
from pathlib import PureWindowsPath
from types import SimpleNamespace

import pytest

from meadowpy.ui import file_explorer


def _rename_panel(monkeypatch, old_path, new_name):
    renamed, warnings, errors = [], [], []
    panel = SimpleNamespace(
        _fs_model=SimpleNamespace(filePath=lambda index: str(old_path)),
        file_renamed=SimpleNamespace(emit=lambda *args: renamed.append(args)),
    )
    monkeypatch.setattr(
        file_explorer.QInputDialog, "getText",
        lambda *args, **kwargs: (new_name, True),
    )
    monkeypatch.setattr(
        file_explorer.QMessageBox, "warning",
        lambda parent, title, body: warnings.append((title, body)),
    )
    monkeypatch.setattr(
        file_explorer.QMessageBox, "critical",
        lambda parent, title, body: errors.append((title, body)),
    )
    return panel, renamed, warnings, errors


@pytest.mark.parametrize(
    ("new_name", "same_file", "allowed"),
    [
        ("Notes.py", True, True),
        ("Notes.py", False, False),
        ("occupied.py", False, False),
        ("alias.py", True, False),
    ],
    ids=["case-only", "case-sensitive-collision", "occupied", "hardlink-alias"],
)
def test_rename_existing_target_checks_name_and_identity(
    monkeypatch, new_name, same_file, allowed
):
    moves = []

    class ExistingWindowsPath(PureWindowsPath):
        def exists(self):
            return True

        def samefile(self, other):
            return same_file

        def rename(self, target):
            moves.append((str(self), str(target)))

    old_path = ExistingWindowsPath("C:/project/notes.py")
    new_path = old_path.parent / new_name
    monkeypatch.setattr(file_explorer, "Path", ExistingWindowsPath)
    panel, renamed, warnings, errors = _rename_panel(
        monkeypatch, old_path, new_name
    )

    file_explorer.FileExplorerPanel._action_rename(panel, object())

    expected = [(str(old_path), str(new_path))] if allowed else []
    assert moves == expected
    assert renamed == expected
    assert warnings == (
        [] if allowed else [("Already Exists", f"'{new_name}' already exists.")]
    )
    assert errors == []


def test_rename_reports_identity_check_failure(monkeypatch):
    class UnreadableWindowsPath(PureWindowsPath):
        def exists(self):
            return True

        def samefile(self, other):
            raise OSError("identity unavailable")

        def rename(self, target):
            pytest.fail("A failed identity check must not rename the entry")

    old_path = UnreadableWindowsPath("C:/project/notes.py")
    monkeypatch.setattr(file_explorer, "Path", UnreadableWindowsPath)
    panel, renamed, warnings, errors = _rename_panel(
        monkeypatch, old_path, "Notes.py"
    )

    file_explorer.FileExplorerPanel._action_rename(panel, object())

    assert renamed == []
    assert warnings == []
    assert errors == [("Error", "Could not rename:\nidentity unavailable")]


@pytest.mark.skipif(os.name != "nt", reason="Windows paths ignore filename case")
@pytest.mark.parametrize("is_directory", [False, True], ids=["file", "folder"])
def test_case_only_rename_preserves_real_entry(monkeypatch, tmp_path, is_directory):
    old_path = tmp_path / "notes"
    new_path = tmp_path / "Notes"
    if is_directory:
        old_path.mkdir()
        (old_path / "child.txt").write_text("preserve me", encoding="utf-8")
    else:
        old_path.write_text("preserve me", encoding="utf-8")
    assert new_path.exists()
    panel, renamed, warnings, errors = _rename_panel(
        monkeypatch, old_path, new_path.name
    )

    file_explorer.FileExplorerPanel._action_rename(panel, object())

    assert [entry.name for entry in tmp_path.iterdir()] == ["Notes"]
    content_path = new_path / "child.txt" if is_directory else new_path
    assert content_path.read_text(encoding="utf-8") == "preserve me"
    assert renamed == [(str(old_path), str(new_path))]
    assert warnings == []
    assert errors == []

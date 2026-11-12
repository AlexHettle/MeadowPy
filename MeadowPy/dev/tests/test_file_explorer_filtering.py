"""Regression coverage for hidden names and bytecode in the file explorer."""

import os

import pytest
from PyQt6.QtGui import QStandardItem, QStandardItemModel

from meadowpy.ui.file_explorer import (
    _FilteredFileSystemModel,
    _directory_has_visible_entries,
)


class _NamedItemModel(QStandardItemModel):
    def fileName(self, index):
        return self.itemFromIndex(index).text()


@pytest.mark.parametrize(
    "filename",
    ["module.pyc", "module.PYC", "module.PyC",
     "module.pyo", "module.PYO", "module.PyO"],
)
def test_explorer_hides_bytecode_regardless_of_suffix_case(qapp, tmp_path, filename):
    (tmp_path / filename).write_bytes(b"bytecode")
    source = _NamedItemModel()
    source.appendRow(QStandardItem(filename))
    proxy = _FilteredFileSystemModel()
    proxy.setSourceModel(source)

    assert proxy.rowCount() == 0
    assert _directory_has_visible_entries(str(tmp_path)) is False

    (tmp_path / "source.PY").write_text("pass\n", encoding="utf-8")
    source.appendRow(QStandardItem("source.PY"))

    assert proxy.rowCount() == 1
    assert proxy.index(0, 0).data() == "source.PY"
    assert _directory_has_visible_entries(str(tmp_path)) is True


@pytest.mark.parametrize(
    "filename", ["module.py", "module.PYW", "module.PYC.txt", "pyc", "module.pyconfig"]
)
def test_explorer_preserves_names_without_bytecode_suffix(qapp, tmp_path, filename):
    (tmp_path / filename).write_text("text\n", encoding="utf-8")
    source = _NamedItemModel()
    source.appendRow(QStandardItem(filename))
    proxy = _FilteredFileSystemModel()
    proxy.setSourceModel(source)

    assert proxy.rowCount() == 1
    assert proxy.index(0, 0).data() == filename
    assert _directory_has_visible_entries(str(tmp_path)) is True


@pytest.mark.skipif(os.name != "nt", reason="Windows directory names ignore case")
@pytest.mark.parametrize(
    "directory_name",
    ["__pycache__", "__PYCACHE__", "Node_Modules", "NODE_MODULES",
     ".GIT", ".VENV", ".PyTest_Cache", ".VSCode"],
)
def test_explorer_hides_windows_generated_directories_regardless_of_case(
    qapp, tmp_path, directory_name
):
    (tmp_path / directory_name).mkdir()
    source = _NamedItemModel()
    source.appendRow(QStandardItem(directory_name))
    proxy = _FilteredFileSystemModel()
    proxy.setSourceModel(source)

    assert proxy.rowCount() == 0
    assert _directory_has_visible_entries(str(tmp_path)) is False

    # Match whole names, not prefixes that can belong to user directories.
    visible_name = directory_name + "_tools"
    (tmp_path / visible_name).mkdir()
    source.appendRow(QStandardItem(visible_name))

    assert proxy.rowCount() == 1
    assert proxy.index(0, 0).data() == visible_name
    assert _directory_has_visible_entries(str(tmp_path)) is True

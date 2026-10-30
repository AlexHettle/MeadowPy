"""Regression coverage for bytecode filtering in the file explorer."""

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

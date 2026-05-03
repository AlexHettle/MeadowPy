from unittest.mock import Mock

from meadowpy.core.file_manager import FileManager
from tests.helpers import SignalRecorder


def test_open_file_with_explicit_path_reads_and_emits(tmp_path):
    recent = Mock()
    manager = FileManager(settings=Mock(), recent_files=recent)
    recorder = SignalRecorder()
    manager.file_opened.connect(recorder)
    file_path = tmp_path / "hello.py"
    file_path.write_text("print('hello')", encoding="utf-8")

    result = manager.open_file(str(file_path))

    assert result == (str(file_path), "print('hello')")
    recent.add.assert_called_once_with(str(file_path))
    assert recorder.calls == [(str(file_path), "print('hello')")]


def test_open_file_returns_none_when_dialog_is_cancelled(monkeypatch):
    recent = Mock()
    manager = FileManager(settings=Mock(), recent_files=recent)

    monkeypatch.setattr(
        "meadowpy.core.file_manager.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: ("", ""),
    )

    assert manager.open_file() is None
    recent.add.assert_not_called()


def test_save_file_persists_content_and_emits(tmp_path):
    recent = Mock()
    manager = FileManager(settings=Mock(), recent_files=recent)
    recorder = SignalRecorder()
    manager.file_saved.connect(recorder)
    file_path = tmp_path / "saved.py"

    assert manager.save_file(str(file_path), "print('saved')") is True
    assert file_path.read_text(encoding="utf-8") == "print('saved')"
    recent.add.assert_called_once_with(str(file_path))
    assert recorder.calls == [(str(file_path),)]


def test_save_file_returns_false_on_oserror(monkeypatch):
    recent = Mock()
    manager = FileManager(settings=Mock(), recent_files=recent)

    def raise_oserror(*args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(manager, "write_file", raise_oserror)

    assert manager.save_file("bad.py", "data") is False
    recent.add.assert_not_called()


def test_save_file_as_uses_dialog_and_returns_path(monkeypatch):
    recent = Mock()
    manager = FileManager(settings=Mock(), recent_files=recent)
    monkeypatch.setattr(
        "meadowpy.core.file_manager.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: ("picked.py", ""),
    )
    monkeypatch.setattr(manager, "save_file", lambda file_path, content: file_path == "picked.py")

    assert manager.save_file_as("content") == "picked.py"


def test_read_file_falls_back_to_latin1(tmp_path):
    recent = Mock()
    manager = FileManager(settings=Mock(), recent_files=recent)
    file_path = tmp_path / "latin1.txt"
    file_path.write_bytes("caf\xe9".encode("latin-1"))

    assert manager.read_file(str(file_path)) == "café"


def test_write_file_preserves_newlines_without_translation(tmp_path):
    recent = Mock()
    manager = FileManager(settings=Mock(), recent_files=recent)
    file_path = tmp_path / "newlines.py"

    manager.write_file(str(file_path), "a\nb\n")

    assert file_path.read_text(encoding="utf-8") == "a\nb\n"

from unittest.mock import Mock

import pytest

from meadowpy.core.file_manager import (
    FileManager,
    LARGE_FILE_WARNING_BYTES,
    LargeFileError,
    UnsupportedFileError,
    format_file_size,
    is_known_unsupported_editor_file,
)
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
    assert str(manager.last_save_error) == "boom"
    assert manager.last_save_error_path == "bad.py"
    recent.add.assert_not_called()


def test_save_file_as_uses_dialog_and_returns_path(monkeypatch):
    recent = Mock()
    manager = FileManager(settings=Mock(), recent_files=recent)
    saved = []
    monkeypatch.setattr(
        "meadowpy.core.file_manager.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: ("picked.py", ""),
    )

    def fake_save_file(file_path, content):
        saved.append((file_path, content))
        return file_path == "picked.py"

    monkeypatch.setattr(manager, "save_file", fake_save_file)

    assert manager.save_file_as("content") == "picked.py"
    assert saved == [("picked.py", "content")]


def test_read_file_falls_back_to_latin1(tmp_path):
    recent = Mock()
    manager = FileManager(settings=Mock(), recent_files=recent)
    file_path = tmp_path / "latin1.txt"
    file_path.write_bytes("caf\xe9".encode("latin-1"))

    assert manager.read_file(str(file_path)) == "café"


@pytest.mark.parametrize("encoding", ["utf-16", "utf-32"])
def test_read_file_decodes_unicode_bom_text(tmp_path, encoding):
    recent = Mock()
    manager = FileManager(settings=Mock(), recent_files=recent)
    file_path = tmp_path / f"unicode-{encoding}.txt"
    file_path.write_bytes("first\r\nsecond".encode(encoding))

    assert manager.read_file(str(file_path)) == "first\nsecond"


def test_read_file_allows_non_python_text_files(tmp_path):
    recent = Mock()
    manager = FileManager(settings=Mock(), recent_files=recent)
    file_path = tmp_path / "notes.txt"
    file_path.write_text("plain notes\n", encoding="utf-8")

    assert manager.read_file(str(file_path)) == "plain notes\n"


def test_read_file_warns_before_loading_large_text_files(tmp_path):
    recent = Mock()
    manager = FileManager(settings=Mock(), recent_files=recent)
    file_path = tmp_path / "large.log"
    file_path.write_bytes(b"a" * (LARGE_FILE_WARNING_BYTES + 1))

    with pytest.raises(LargeFileError) as exc_info:
        manager.read_file(str(file_path))

    error = exc_info.value
    assert error.file_path == str(file_path)
    assert error.size_bytes == LARGE_FILE_WARNING_BYTES + 1
    assert error.threshold_bytes == LARGE_FILE_WARNING_BYTES
    assert "large-file safeguard" in str(error)

    content = manager.read_file(str(file_path), allow_large=True)
    assert len(content) == LARGE_FILE_WARNING_BYTES + 1


def test_open_file_tracks_large_file_error(tmp_path):
    recent = Mock()
    manager = FileManager(settings=Mock(), recent_files=recent)
    recorder = SignalRecorder()
    manager.file_opened.connect(recorder)
    file_path = tmp_path / "large.log"
    file_path.write_bytes(b"a" * (LARGE_FILE_WARNING_BYTES + 1))

    assert manager.open_file(str(file_path)) is None
    assert isinstance(manager.last_open_error, LargeFileError)
    assert manager.last_open_error_path == str(file_path)
    recent.add.assert_not_called()
    assert recorder.calls == []

    result = manager.open_file(str(file_path), allow_large=True)
    assert result is not None
    opened_path, opened_content = result
    assert opened_path == str(file_path)
    assert len(opened_content) == LARGE_FILE_WARNING_BYTES + 1
    assert manager.last_open_error is None
    assert manager.last_open_error_path is None
    recent.add.assert_called_once_with(str(file_path))
    assert len(recorder.calls) == 1
    emitted_path, emitted_content = recorder.calls[0]
    assert emitted_path == str(file_path)
    assert len(emitted_content) == LARGE_FILE_WARNING_BYTES + 1


def test_format_file_size_uses_compact_units():
    assert format_file_size(512) == "512 bytes"
    assert format_file_size(1536) == "1.5 KB"
    assert format_file_size(2 * 1024 * 1024) == "2.0 MB"


def test_read_file_rejects_office_documents(tmp_path):
    recent = Mock()
    manager = FileManager(settings=Mock(), recent_files=recent)
    file_path = tmp_path / "review.docx"
    file_path.write_bytes(b"PK\x03\x04\x14\x00\x00\x00word/document.xml")

    with pytest.raises(UnsupportedFileError, match="not a text file"):
        manager.read_file(str(file_path))


def test_known_unsupported_editor_file_helper_identifies_blocked_suffixes():
    assert is_known_unsupported_editor_file("review.docx") is True
    assert is_known_unsupported_editor_file("archive.zip") is True
    assert is_known_unsupported_editor_file("notes.txt") is False
    assert is_known_unsupported_editor_file("script.py") is False


def test_read_file_rejects_nul_heavy_payloads(tmp_path):
    recent = Mock()
    manager = FileManager(settings=Mock(), recent_files=recent)
    file_path = tmp_path / "unknown.data"
    file_path.write_bytes(b"hello\x00\x01\x02binary")

    with pytest.raises(UnsupportedFileError, match="readable text"):
        manager.read_file(str(file_path))


def test_open_file_tracks_open_error_for_unsupported_files(tmp_path):
    recent = Mock()
    manager = FileManager(settings=Mock(), recent_files=recent)
    recorder = SignalRecorder()
    manager.file_opened.connect(recorder)
    file_path = tmp_path / "review.docx"
    file_path.write_bytes(b"PK\x03\x04\x14\x00\x00\x00word/document.xml")

    assert manager.open_file(str(file_path)) is None
    assert isinstance(manager.last_open_error, UnsupportedFileError)
    assert manager.last_open_error_path == str(file_path)
    recent.add.assert_not_called()
    assert recorder.calls == []


def test_write_file_preserves_newlines_without_translation(tmp_path):
    recent = Mock()
    manager = FileManager(settings=Mock(), recent_files=recent)
    file_path = tmp_path / "newlines.py"

    manager.write_file(str(file_path), "a\nb\n")

    assert file_path.read_text(encoding="utf-8") == "a\nb\n"

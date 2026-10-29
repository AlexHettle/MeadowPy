"""Regression coverage for editor-supported encodings in project search."""

import pytest

from meadowpy.ui.search_panel import SearchWorker


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "latin-1", "utf-16", "utf-32"])
@pytest.mark.parametrize(
    ("pattern", "use_regex"),
    [("^needle", True), ("needle", False)],
    ids=["anchored-regex", "literal"],
)
def test_search_worker_matches_visible_text_with_or_without_bom(
    tmp_path, encoding, pattern, use_regex
):
    file_path = tmp_path / "notes.txt"
    file_path.write_bytes("needle caf\u00e9\nneedle second\n".encode(encoding))
    worker = SearchWorker(str(tmp_path), pattern, True, use_regex)
    matches = []
    totals = []
    worker.match_found.connect(matches.append)
    worker.finished.connect(totals.append)

    worker.run()

    assert totals == [2]
    assert [
        (match.file_path, match.line_num, match.column, match.line_text)
        for match in matches
    ] == [
        (str(file_path), 1, 0, "needle caf\u00e9"),
        (str(file_path), 2, 0, "needle second"),
    ]
    assert worker.large_files_skipped == 0


def test_search_worker_preserves_interior_bom_characters(tmp_path):
    file_path = tmp_path / "notes.txt"
    file_path.write_bytes("header\n\ufeffneedle\n".encode("utf-8-sig"))
    worker = SearchWorker(str(tmp_path), "^\ufeffneedle", True, True)
    matches = []
    totals = []
    worker.match_found.connect(matches.append)
    worker.finished.connect(totals.append)

    worker.run()

    assert totals == [1]
    assert [
        (match.file_path, match.line_num, match.column, match.line_text)
        for match in matches
    ] == [(str(file_path), 2, 0, "\ufeffneedle")]


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "latin-1", "utf-16", "utf-32"])
def test_search_worker_finds_non_ascii_text_at_visible_column(tmp_path, encoding):
    file_path = tmp_path / "notes.txt"
    file_path.write_bytes("header\r\n  d\u00e9j\u00e0 caf\u00e9\r\n".encode(encoding))
    worker = SearchWorker(str(tmp_path), "caf\u00e9", True, False)
    matches = []
    totals = []
    worker.match_found.connect(matches.append)
    worker.finished.connect(totals.append)

    worker.run()

    assert totals == [1]
    assert [
        (match.file_path, match.line_num, match.column, match.line_text)
        for match in matches
    ] == [(str(file_path), 2, 7, "  d\u00e9j\u00e0 caf\u00e9")]
    assert worker.large_files_skipped == 0


@pytest.mark.parametrize("filename", ["payload.dat", "payload", "payload.txt"])
@pytest.mark.parametrize(
    "payload",
    [b"needle\x00\n", b"\x01\x02needle\n"],
    ids=["nul-byte", "control-bytes"],
)
def test_search_worker_skips_binary_content_with_unlisted_extensions(
    tmp_path, filename, payload
):
    (tmp_path / filename).write_bytes(payload)
    text_path = tmp_path / "notes.txt"
    text_path.write_bytes(b"\tneedle text\r\n")
    worker = SearchWorker(str(tmp_path), "needle", True, False)
    matches = []
    totals = []
    worker.match_found.connect(matches.append)
    worker.finished.connect(totals.append)

    worker.run()

    assert totals == [1]
    assert [
        (match.file_path, match.line_num, match.column, match.line_text)
        for match in matches
    ] == [(str(text_path), 1, 1, "\tneedle text")]
    assert worker.large_files_skipped == 0

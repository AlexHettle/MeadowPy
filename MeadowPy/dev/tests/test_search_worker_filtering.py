"""Regression coverage for project-search directory filtering."""

import os

import pytest

from meadowpy.ui.search_panel import SearchWorker


@pytest.mark.skipif(os.name != "nt", reason="Windows directory names ignore case")
@pytest.mark.parametrize(
    "directory_name",
    ["venv", "VENV", "VeNv", "ENV", "__PYCACHE__", "Node_Modules"],
)
def test_search_worker_skips_windows_excluded_directories_regardless_of_case(
    tmp_path, directory_name
):
    project = tmp_path / "project"
    excluded = project / directory_name / "nested"
    excluded.mkdir(parents=True)
    (excluded / "dependency.py").write_text("needle dependency\n", encoding="utf-8")

    expected = []
    for directory in ("Src", "VENV_tools"):
        source_dir = project / directory
        source_dir.mkdir()
        source_path = source_dir / "main.py"
        source_path.write_text("header\n  needle source\n", encoding="utf-8")
        expected.append((str(source_path), 2, 2, "  needle source"))

    worker = SearchWorker(str(tmp_path), "needle", True, False)
    matches = []
    totals = []
    worker.match_found.connect(matches.append)
    worker.finished.connect(totals.append)

    worker.run()

    assert totals == [2]
    assert sorted(
        (match.file_path, match.line_num, match.column, match.line_text)
        for match in matches
    ) == sorted(expected)
    assert worker.large_files_skipped == 0

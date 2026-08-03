from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from example_expectations import EXAMPLE_EXPECTATIONS, ExampleExpectation
from meadowpy.resources import example_library


EXAMPLES_DIR = Path(example_library.__file__).with_name("examples")
CATALOG_PATH = EXAMPLES_DIR / "catalog.json"


def _load_catalog_paths() -> tuple[str, ...]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return tuple(
        example["code_file"]
        for category in catalog["categories"]
        for example in category["examples"]
    )


CATALOG_PATHS = _load_catalog_paths()


class _ExampleApiHandler(BaseHTTPRequestHandler):
    def _write_json(self, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self._write_json({
            "url": f"http://{self.headers['Host']}{self.path}",
            "origin": "127.0.0.1",
        })

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        self._write_json({"data": body})

    def log_message(self, _format: str, *args) -> None:
        pass


@pytest.fixture(scope="session")
def example_api_base_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ExampleApiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _assert_ordered_fragments(
    stream_name: str,
    output: str,
    fragments: tuple[str, ...],
) -> None:
    cursor = 0
    for fragment in fragments:
        position = output.find(fragment, cursor)
        assert position >= 0, (
            f"Expected {fragment!r} in {stream_name} after offset {cursor}.\n"
            f"Complete {stream_name}:\n{output}"
        )
        cursor = position + len(fragment)


def _assert_patterns(
    stream_name: str,
    output: str,
    patterns: tuple[str, ...],
) -> None:
    for pattern in patterns:
        assert re.search(pattern, output, re.MULTILINE), (
            f"Expected pattern {pattern!r} in {stream_name}.\n"
            f"Complete {stream_name}:\n{output}"
        )


def _validate_dice_roller(stdout: str) -> None:
    dice_match = re.search(r"You rolled: ([1-6]) and ([1-6])", stdout)
    total_match = re.search(r"^Total: (\d+)$", stdout, re.MULTILINE)
    assert dice_match and total_match
    dice = tuple(int(value) for value in dice_match.groups())
    assert int(total_match.group(1)) == sum(dice)

    rows = re.findall(
        r"^\s+(\d+)\s+(\d+)\s+(\d+\.\d)%\s+#+\s*$",
        stdout,
        re.MULTILINE,
    )
    assert [int(value) for value, _, _ in rows] == list(range(2, 13))
    assert sum(int(count) for _, count, _ in rows) == 1000
    for _, count, percentage in rows:
        assert abs(float(percentage) - int(count) / 10) <= 0.05


def _validate_password_generator(stdout: str) -> None:
    passwords = re.findall(r"^\s+\d+\. ([A-Za-z0-9]+)$", stdout, re.MULTILINE)
    assert len(passwords) == 2
    assert all(len(password) == 8 for password in passwords)


def _validate_rock_paper_scissors(stdout: str) -> None:
    computer = re.search(r"Computer chose: (rock|paper|scissors)", stdout)
    outcome = re.search(r"(It's a tie!|You win!|You lose!)", stdout)
    score = re.search(r"Final score: (\d+) wins, (\d+) losses", stdout)
    assert computer and outcome and score

    expected_score = {
        "It's a tie!": (0, 0),
        "You win!": (1, 0),
        "You lose!": (0, 1),
    }[outcome.group(1)]
    assert tuple(int(value) for value in score.groups()) == expected_score


VALIDATORS = {
    "dice_roller": _validate_dice_roller,
    "password_generator": _validate_password_generator,
    "rock_paper_scissors": _validate_rock_paper_scissors,
}


def test_example_catalog_has_complete_execution_contracts():
    catalog_set = set(CATALOG_PATHS)
    source_set = {
        path.relative_to(EXAMPLES_DIR).as_posix()
        for path in EXAMPLES_DIR.rglob("*.py")
    }
    expectation_set = set(EXAMPLE_EXPECTATIONS)

    assert len(CATALOG_PATHS) == len(catalog_set), (
        "Catalog paths must be unique"
    )
    assert source_set == catalog_set
    assert expectation_set == catalog_set

    for path, expectation in EXAMPLE_EXPECTATIONS.items():
        assert isinstance(expectation, ExampleExpectation), path
        has_behavior_assertion = any((
            expectation.stdout_contains,
            expectation.stdout_patterns,
            expectation.stderr_contains,
            expectation.stderr_patterns,
            expectation.expected_files,
            expectation.expected_json_files,
            expectation.validator,
        ))
        assert has_behavior_assertion, (
            f"No behavior assertion defined for {path}"
        )
        if expectation.validator:
            assert expectation.validator in VALIDATORS, path


@pytest.mark.parametrize("relative_path", CATALOG_PATHS, ids=CATALOG_PATHS)
def test_example_source_compiles(relative_path):
    path = EXAMPLES_DIR / relative_path
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")


@pytest.mark.parametrize("relative_path", CATALOG_PATHS, ids=CATALOG_PATHS)
def test_example_executes_expected_behavior(
    relative_path,
    tmp_path,
    example_api_base_url,
):
    expectation = EXAMPLE_EXPECTATIONS[relative_path]
    path = EXAMPLES_DIR / relative_path
    environment = os.environ.copy()
    environment.update({
        "PYTHONHASHSEED": "0",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
    })
    if expectation.uses_local_http:
        environment["MEADOWPY_EXAMPLE_API_BASE_URL"] = example_api_base_url
        environment["NO_PROXY"] = "127.0.0.1,localhost"
        environment["no_proxy"] = "127.0.0.1,localhost"

    try:
        completed = subprocess.run(
            [sys.executable, "-u", str(path)],
            cwd=tmp_path,
            input=expectation.stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            timeout=expectation.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(
            f"{relative_path} exceeded "
            f"{expectation.timeout_seconds} seconds.\n"
            f"stdout:\n{exc.stdout or ''}\n"
            f"stderr:\n{exc.stderr or ''}",
        )

    assert completed.returncode == 0, (
        f"{relative_path} exited with {completed.returncode}.\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
    assert "Traceback (most recent call last)" not in completed.stderr

    _assert_ordered_fragments(
        "stdout",
        completed.stdout,
        expectation.stdout_contains,
    )
    _assert_patterns("stdout", completed.stdout, expectation.stdout_patterns)

    if expectation.stderr_contains or expectation.stderr_patterns:
        _assert_ordered_fragments(
            "stderr",
            completed.stderr,
            expectation.stderr_contains,
        )
        _assert_patterns(
            "stderr",
            completed.stderr,
            expectation.stderr_patterns,
        )
    else:
        assert completed.stderr == "", (
            f"Unexpected stderr from {relative_path}:\n{completed.stderr}"
        )

    expected_paths = (
        set(expectation.expected_files)
        | set(expectation.expected_json_files)
    )
    actual_paths = {
        file.relative_to(tmp_path).as_posix()
        for file in tmp_path.rglob("*")
        if file.is_file()
    }
    assert actual_paths == expected_paths

    for filename, expected_content in expectation.expected_files.items():
        actual_content = (tmp_path / filename).read_text(encoding="utf-8")
        actual_content = actual_content.replace("\r\n", "\n")
        actual_content = actual_content.replace("\r", "\n")
        assert actual_content == expected_content

    for filename, expected_data in expectation.expected_json_files.items():
        file_content = (tmp_path / filename).read_text(encoding="utf-8")
        actual_data = json.loads(file_content)
        assert actual_data == expected_data

    if expectation.validator:
        VALIDATORS[expectation.validator](completed.stdout)

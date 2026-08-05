from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from meadowpy.ui.welcome_templates import TEMPLATES
from quick_start_expectations import (
    QUICK_START_SCENARIOS,
    QuickStartScenario,
)


EXPECTED_TEMPLATE_COUNT = 12
TEMPLATES_BY_NAME = {template["name"]: template for template in TEMPLATES}
TEMPLATE_NAMES = tuple(template["name"] for template in TEMPLATES)
SCENARIO_CASES = tuple(
    (template_name, scenario)
    for template_name, scenarios in QUICK_START_SCENARIOS.items()
    for scenario in scenarios
)

TURTLE_STUB_SOURCE = '''
import json
import os
from pathlib import Path


EVENTS = []


def _record(name, value=None):
    EVENTS.append([name, value])


class _Screen:
    def bgcolor(self, color):
        _record("bgcolor", color)

    def title(self, text):
        _record("title", text)

    def mainloop(self):
        _record("mainloop")
        output = Path(os.environ["MEADOWPY_TURTLE_CALLS"])
        output.write_text(json.dumps(EVENTS), encoding="utf-8")


def Screen():
    _record("Screen")
    return _Screen()


class Turtle:
    def __init__(self):
        _record("Turtle")

    def speed(self, value):
        _record("speed", value)

    def pencolor(self, color):
        _record("pencolor", color)

    def forward(self, distance):
        _record("forward", distance)

    def left(self, degrees):
        _record("left", degrees)

    def hideturtle(self):
        _record("hideturtle")
'''.lstrip()


def _assert_ordered_fragments(
    stream_name: str,
    output: str,
    fragments: tuple[str, ...],
) -> None:
    cursor = 0
    for fragment in fragments:
        position = output.find(fragment, cursor)
        assert position >= 0, (
            f"Expected {fragment!r} in {stream_name} after offset "
            f"{cursor}.\nComplete {stream_name}:\n{output}"
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


def _validate_guessing_game(stdout: str, _tmp_path: Path) -> None:
    result = re.search(
        r"Correct! You got it in (\d+) attempts!",
        stdout,
    )
    assert result
    attempts = int(result.group(1))
    assert 1 <= attempts <= 100
    assert stdout.count("Your guess: ") == attempts
    assert stdout.count("Too low! Try again.") == attempts - 1
    assert "Too high! Try again." not in stdout


def _validate_rock_paper_scissors(
    stdout: str,
    _tmp_path: Path,
) -> None:
    computer = re.search(
        r"Computer chose: (rock|paper|scissors)",
        stdout,
    )
    outcome = re.search(
        r"(It's a tie!|You win this round!|Computer wins this round!)",
        stdout,
    )
    score = re.search(
        r"Final score — You: (\d+)  Computer: (\d+)",
        stdout,
    )
    assert computer and outcome and score

    expected_score = {
        "It's a tie!": (0, 0),
        "You win this round!": (1, 0),
        "Computer wins this round!": (0, 1),
    }[outcome.group(1)]
    assert tuple(int(value) for value in score.groups()) == expected_score


def _validate_turtle_graphics(_stdout: str, tmp_path: Path) -> None:
    calls_path = tmp_path / "turtle_calls.json"
    events = json.loads(calls_path.read_text(encoding="utf-8"))

    assert events[:5] == [
        ["Screen", None],
        ["bgcolor", "white"],
        ["title", "Turtle Graphics"],
        ["Turtle", None],
        ["speed", 0],
    ]
    assert events[-2:] == [
        ["hideturtle", None],
        ["mainloop", None],
    ]

    colors = [value for name, value in events if name == "pencolor"]
    distances = [value for name, value in events if name == "forward"]
    turns = [value for name, value in events if name == "left"]
    palette = ["red", "orange", "yellow", "green", "blue", "purple"]

    assert colors == [palette[index % len(palette)] for index in range(60)]
    assert distances == [index * 3 for index in range(60)]
    assert turns == [61] * 60
    assert len(events) == 187


VALIDATORS = {
    "guessing_game": _validate_guessing_game,
    "rock_paper_scissors": _validate_rock_paper_scissors,
    "turtle_graphics": _validate_turtle_graphics,
}


def test_quick_start_templates_have_complete_contracts():
    required_keys = {"name", "desc", "icon", "code"}
    names = []

    assert len(TEMPLATES) == EXPECTED_TEMPLATE_COUNT
    for template in TEMPLATES:
        assert set(template) == required_keys
        for key in required_keys:
            assert isinstance(template[key], str)
            assert template[key].strip()
        names.append(template["name"])

    assert len(names) == len(set(names)), "Template names must be unique"
    assert set(QUICK_START_SCENARIOS) == set(names)

    for template_name, scenarios in QUICK_START_SCENARIOS.items():
        assert scenarios, f"No execution scenarios for {template_name}"
        scenario_names = [scenario.name for scenario in scenarios]
        assert len(scenario_names) == len(set(scenario_names))

        for scenario in scenarios:
            assert isinstance(scenario, QuickStartScenario)
            assert scenario.name
            has_behavior_assertion = any((
                scenario.stdout_contains,
                scenario.stdout_patterns,
                scenario.expected_files,
                scenario.expected_generated_files,
                scenario.validator,
            ))
            assert has_behavior_assertion, (
                f"No behavior assertion for {template_name}::"
                f"{scenario.name}"
            )
            if scenario.validator:
                assert scenario.validator in VALIDATORS


@pytest.mark.parametrize("template_name", TEMPLATE_NAMES, ids=TEMPLATE_NAMES)
def test_quick_start_template_compiles(template_name):
    code = TEMPLATES_BY_NAME[template_name]["code"]
    compile(code, f"<quick-start:{template_name}>", "exec")


@pytest.mark.parametrize(
    ("template_name", "scenario"),
    SCENARIO_CASES,
    ids=(
        f"{template_name}::{scenario.name}"
        for template_name, scenario in SCENARIO_CASES
    ),
)
def test_quick_start_template_executes_expected_behavior(
    template_name,
    scenario,
    tmp_path,
):
    code = TEMPLATES_BY_NAME[template_name]["code"]
    script_path = tmp_path / "_quick_start.py"
    script_path.write_text(code, encoding="utf-8")

    for filename, content in scenario.initial_files.items():
        initial_path = tmp_path / filename
        initial_path.parent.mkdir(parents=True, exist_ok=True)
        initial_path.write_text(content, encoding="utf-8")

    support_paths = {script_path.relative_to(tmp_path).as_posix()}
    environment = os.environ.copy()
    environment.update({
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
    })
    if scenario.use_turtle_stub:
        turtle_path = tmp_path / "turtle.py"
        turtle_path.write_text(TURTLE_STUB_SOURCE, encoding="utf-8")
        support_paths.add(turtle_path.relative_to(tmp_path).as_posix())
        environment["MEADOWPY_TURTLE_CALLS"] = str(
            tmp_path / "turtle_calls.json"
        )

    try:
        completed = subprocess.run(
            [sys.executable, "-u", str(script_path)],
            cwd=tmp_path,
            input=scenario.stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            timeout=scenario.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(
            f"{template_name}::{scenario.name} exceeded "
            f"{scenario.timeout_seconds} seconds.\n"
            f"stdout:\n{exc.stdout or ''}\n"
            f"stderr:\n{exc.stderr or ''}",
        )

    assert completed.returncode == 0, (
        f"{template_name}::{scenario.name} exited with "
        f"{completed.returncode}.\nstdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
    assert "Traceback (most recent call last)" not in completed.stderr
    assert completed.stderr == "", (
        f"Unexpected stderr from {template_name}::{scenario.name}:\n"
        f"{completed.stderr}"
    )

    _assert_ordered_fragments(
        "stdout",
        completed.stdout,
        scenario.stdout_contains,
    )
    _assert_patterns("stdout", completed.stdout, scenario.stdout_patterns)

    expected_paths = (
        set(scenario.expected_files)
        | set(scenario.expected_generated_files)
    )
    all_file_paths = {
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    actual_paths = all_file_paths - support_paths
    assert actual_paths == expected_paths

    for filename, expected_content in scenario.expected_files.items():
        actual_content = (tmp_path / filename).read_text(encoding="utf-8")
        actual_content = actual_content.replace("\r\n", "\n")
        actual_content = actual_content.replace("\r", "\n")
        assert actual_content == expected_content

    if scenario.validator:
        VALIDATORS[scenario.validator](completed.stdout, tmp_path)

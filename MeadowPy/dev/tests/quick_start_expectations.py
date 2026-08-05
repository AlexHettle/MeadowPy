from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class QuickStartScenario:
    """One user-visible execution path through a Quick Start template."""

    name: str
    stdin: str = ""
    stdout_contains: tuple[str, ...] = ()
    stdout_patterns: tuple[str, ...] = ()
    initial_files: Mapping[str, str] = field(default_factory=dict)
    expected_files: Mapping[str, str] = field(default_factory=dict)
    expected_generated_files: tuple[str, ...] = ()
    validator: str | None = None
    use_turtle_stub: bool = False
    timeout_seconds: float = 10.0


QUICK_START_SCENARIOS = {
    "Hello World": (
        QuickStartScenario(
            name="greets_user",
            stdin="Alex\n",
            stdout_contains=(
                "Hello, World!",
                "Welcome to Python programming!",
                "Nice to meet you, Alex!",
            ),
        ),
    ),
    "Simple Calculator": (
        QuickStartScenario(
            name="basic_arithmetic",
            stdin="8\n2\n",
            stdout_contains=(
                "=== Simple Calculator ===",
                "8.0 + 2.0 = 10.0",
                "8.0 - 2.0 = 6.0",
                "8.0 * 2.0 = 16.0",
                "8.0 / 2.0 = 4.0",
            ),
        ),
        QuickStartScenario(
            name="division_by_zero",
            stdin="8\n0\n",
            stdout_contains=(
                "8.0 + 0.0 = 8.0",
                "Cannot divide by zero!",
            ),
        ),
    ),
    "Guessing Game": (
        QuickStartScenario(
            name="finds_random_number",
            stdin="".join(f"{number}\n" for number in range(1, 101)),
            stdout_contains=(
                "I'm thinking of a number between 1 and 100.",
                "Correct! You got it in",
            ),
            validator="guessing_game",
        ),
    ),
    "Todo List": (
        QuickStartScenario(
            name="add_remove_and_quit",
            stdin="a\nWrite tests\nr\n1\nq\n",
            stdout_contains=(
                "  (empty)",
                "Added: Write tests",
                "  1. Write tests",
                "Removed: Write tests",
                "Goodbye!",
            ),
        ),
        QuickStartScenario(
            name="rejects_invalid_removal",
            stdin="r\n1\nq\n",
            stdout_contains=(
                "  (empty)",
                "Invalid number.",
                "Goodbye!",
            ),
        ),
    ),
    "Turtle Graphics": (
        QuickStartScenario(
            name="draws_spiral",
            expected_generated_files=("turtle_calls.json",),
            validator="turtle_graphics",
            use_turtle_stub=True,
        ),
    ),
    "Simple Quiz": (
        QuickStartScenario(
            name="perfect_score",
            stdin="paris\nblue\n8\nmercury\n",
            stdout_contains=(
                "=== Python Quiz ===",
                "Correct!",
                "Correct!",
                "Correct!",
                "Correct!",
                "You scored 4/4!",
                "Perfect score!",
            ),
        ),
        QuickStartScenario(
            name="mixed_answers",
            stdin="london\nblue\nseven\nearth\n",
            stdout_contains=(
                "Wrong! The answer was: paris",
                "Correct!",
                "Wrong! The answer was: 8",
                "Wrong! The answer was: mercury",
                "You scored 1/4!",
                "Keep practicing!",
            ),
        ),
    ),
    "Temperature Converter": (
        QuickStartScenario(
            name="freezing",
            stdin="-5\n",
            stdout_contains=(
                "-5.0°C is 23.0°F  (freezing)",
                "Quick reference table:",
            ),
        ),
        QuickStartScenario(
            name="cold",
            stdin="10\n",
            stdout_contains=(
                "10.0°C is 50.0°F  (cold)",
                "Quick reference table:",
            ),
        ),
        QuickStartScenario(
            name="mild",
            stdin="20\n",
            stdout_contains=(
                "20.0°C is 68.0°F  (mild)",
                "Quick reference table:",
            ),
        ),
        QuickStartScenario(
            name="hot",
            stdin="30\n",
            stdout_contains=(
                "30.0°C is 86.0°F  (hot)",
                "40°C = 104.0°F",
            ),
        ),
    ),
    "Word Counter": (
        QuickStartScenario(
            name="counts_repeated_words",
            stdin="red blue red\n",
            stdout_contains=(
                "Word counts:",
                "red: 2",
                "blue: 1",
                "Total words: 3",
                "Unique words: 2",
            ),
        ),
    ),
    "Notes Saver": (
        QuickStartScenario(
            name="creates_first_note",
            stdin="First note\n",
            stdout_contains=(
                "(No notes yet — let's create some!)",
                "Saved to notes.txt!",
                "=== Updated notes ===",
                "1. First note",
            ),
            expected_files={"notes.txt": "First note\n"},
        ),
        QuickStartScenario(
            name="loads_and_appends_note",
            stdin="Second note\n",
            stdout_contains=(
                "=== Your saved notes ===",
                "First note",
                "Saved to notes.txt!",
                "=== Updated notes ===",
                "1. First note",
                "2. Second note",
            ),
            initial_files={"notes.txt": "First note\n"},
            expected_files={
                "notes.txt": "First note\nSecond note\n",
            },
        ),
    ),
    "Bank Account": (
        QuickStartScenario(
            name="tracks_independent_accounts",
            stdout_contains=(
                "Not enough funds!",
                "Alice's account — balance: $120",
                "- Deposited $50",
                "- Withdrew $30",
                "Bob's account — balance: $200",
                "- Deposited $200",
            ),
        ),
    ),
    "Safe Input": (
        QuickStartScenario(
            name="recovers_from_invalid_integer",
            stdin="bad\n10\n2\n",
            stdout_contains=(
                "=== Safe Division ===",
                "That isn't a whole number. Try again.",
                "10 / 2 = 5.0",
                "Done!",
            ),
        ),
        QuickStartScenario(
            name="handles_zero_division",
            stdin="10\n0\n",
            stdout_contains=(
                "Cannot divide by zero.",
                "Done!",
            ),
        ),
    ),
    "Rock Paper Scissors": (
        QuickStartScenario(
            name="rejects_invalid_move_and_scores_round",
            stdin="invalid\nrock\nq\n",
            stdout_contains=(
                "=== Rock, Paper, Scissors ===",
                "Please type rock, paper, or scissors.",
                "Computer chose:",
                "Final score — You:",
            ),
            validator="rock_paper_scissors",
        ),
    ),
}

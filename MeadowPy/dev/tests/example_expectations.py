from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class ExampleExpectation:
    """Observable behavior required from one example-library script."""

    stdin: str = ""
    stdout_contains: tuple[str, ...] = ()
    stdout_patterns: tuple[str, ...] = ()
    stderr_contains: tuple[str, ...] = ()
    stderr_patterns: tuple[str, ...] = ()
    expected_files: Mapping[str, str] = field(default_factory=dict)
    expected_json_files: Mapping[str, Any] = field(default_factory=dict)
    validator: str | None = None
    uses_local_http: bool = False
    timeout_seconds: float = 10.0


EXAMPLE_EXPECTATIONS = {
    "basics/variables_and_types.py": ExampleExpectation(
        stdout_contains=(
            "name = Alice (type: str)",
            "likes_python = True (type: bool)",
            "Happy birthday! Now age = 15",
        ),
    ),
    "basics/string_formatting.py": ExampleExpectation(
        stdout_contains=(
            "Concatenation: Ada Lovelace",
            "f-string: Ada Lovelace",
            "Total: $29.97",
            "Strip: 'Hello, World!'",
        ),
    ),
    "basics/type_conversion.py": ExampleExpectation(
        stdin="42\n",
        stdout_contains=(
            "You typed: 42 (type: str)",
            "As integer: 42 (type: int)",
            "As float: 42.0 (type: float)",
            'bool("") = False',
        ),
    ),
    "basics/math_operations.py": ExampleExpectation(
        stdout_contains=(
            "17 + 5 = 22",
            "17 % 5 = 2",
            "round(pi, 4) = 3.1416",
            "math.sqrt(144) = 12.0",
        ),
    ),
    "basics/user_input.py": ExampleExpectation(
        stdin="Alex\nnope\n12\n5\n2\n",
        stdout_contains=(
            "Nice to meet you, Alex!",
            "That's not a number! Try again.",
            "Out of range! Must be 1-10.",
            "You picked 5!",
            "You chose: Blue",
        ),
    ),
    "basics/comments_and_readability.py": ExampleExpectation(
        stdout_contains=(
            "BMI for 70kg at 1.75m: 22.9",
            "Calculate Body Mass Index.",
        ),
    ),
    "basics/string_methods.py": ExampleExpectation(
        stdout_contains=(
            "Hello, World!",
            "HELLO WORLD",
            "The dog sat on the mat",
            "Python-is-fun",
            "True\nTrue\nTrue\nFalse",
        ),
    ),
    "basics/enumerate_and_zip.py": ExampleExpectation(
        stdout_contains=(
            "Shopping list:",
            "1. apple",
            "Student results:",
            "Task assignments:",
            "Dict from zip:",
        ),
    ),
    "control_flow/if_elif_else.py": ExampleExpectation(
        stdin="25\n",
        stdout_contains=(
            "You're an adult.",
            "You can enter the movie!",
        ),
    ),
    "control_flow/for_loops.py": ExampleExpectation(
        stdout_contains=(
            "I like apple!",
            "Counting to 5:",
            "Colors list:",
            "Multiplication table (1-5):",
        ),
    ),
    "control_flow/while_loops.py": ExampleExpectation(
        stdin="hello\n-4\nquit\n",
        stdout_contains=(
            "Countdown:",
            "Liftoff!",
            "That's not a number. Try again.",
            "-4 * 2 = -8",
            "Goodbye!",
        ),
    ),
    "control_flow/try_except.py": ExampleExpectation(
        stdin="hello\n",
        stdout_contains=(
            "That wasn't a valid number!",
            "10 / 3 = 3.3333333333333335",
            "Cannot divide by zero!",
            "Both arguments must be numbers!",
        ),
    ),
    "control_flow/logical_operators.py": ExampleExpectation(
        stdin="150\n14\nn\n",
        stdout_contains=(
            "Roller Coaster: Yes!",
            "Bumper Cars:    Yes!",
            "Haunted House:  Yes!",
            "List is empty or doesn't start with apple",
        ),
    ),
    "control_flow/pattern_matching.py": ExampleExpectation(
        stdout_contains=(
            "Goodbye!",
            "Point at (3, 7)",
            "Adult (25 years old)",
            "Moving north for 3 steps",
        ),
    ),
    "data_structures/lists.py": ExampleExpectation(
        stdout_contains=(
            "Original: ['red', 'green', 'blue']",
            "After adding:",
            "numbers[1:4] = [1, 2, 3]",
            "Min: 1, Max: 9",
        ),
    ),
    "data_structures/dictionaries.py": ExampleExpectation(
        stdout_contains=(
            "Name: Alice",
            "Email: not set",
            "Student name is Alice",
            "Keys:",
        ),
    ),
    "data_structures/tuples_and_sets.py": ExampleExpectation(
        stdout_contains=(
            "Point: (3, 7)",
            "Unpacked: x=3, y=7",
            "Union (a | b):",
            "Intersection (a & b): {3, 4}",
        ),
    ),
    "data_structures/nested_structures.py": ExampleExpectation(
        stdout_contains=(
            "All students:",
            "Math students: 3",
            "Top student:",
            "Class average:",
            "Grouped by subject:",
        ),
    ),
    "data_structures/stacks_and_queues.py": ExampleExpectation(
        stdout_contains=(
            "=== Stack (LIFO) ===",
            "Popping:",
            "=== Queue (FIFO) ===",
            "Serving:",
        ),
    ),
    "functions/defining_functions.py": ExampleExpectation(
        stdout_contains=(
            "Hello there!",
            "Hello, Alice!",
            "3 + 5 = 8",
            "power(2, 10) = 1024",
            "Min: 1, Max: 9",
        ),
    ),
    "functions/list_comprehensions.py": ExampleExpectation(
        stdout_contains=(
            "Squares (loop): [1, 4, 9, 16, 25]",
            "Squares (comp): [1, 4, 9, 16, 25]",
            "Evens 1-10: [2, 4, 6, 8, 10]",
            "Celsius:",
        ),
    ),
    "functions/recursion.py": ExampleExpectation(
        stdout_contains=(
            "5! = 120",
            "10! = 3628800",
            "fib(9) = 34",
            "Liftoff!",
        ),
    ),
    "functions/lambda_and_map_filter.py": ExampleExpectation(
        stdout_contains=(
            "double(5) = 10",
            "lambda(5) = 10",
            "Doubled:",
            "Evens:",
            "Ranked by score:",
        ),
    ),
    "functions/decorators.py": ExampleExpectation(
        stdout_contains=(
            "Result: 8",
            "Hello, Alice!",
        ),
        stdout_patterns=(r"slow_add took \d+\.\d{4} seconds",),
    ),
    "functions/generators_and_iterators.py": ExampleExpectation(
        stdout_contains=(
            "Countdown:",
            "First 10 Fibonacci: [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]",
            "Generator size:",
            "Sum of even numbers 0-100: 2550",
        ),
    ),
    "functions/type_hints.py": ExampleExpectation(
        stdout_contains=(
            "Hello, Alice.",
            "HI BOB!!!",
            "Found: Alice",
            "Found: None",
            "Average grade: 88.0",
        ),
    ),
    "file_i_o/reading_and_writing_files.py": ExampleExpectation(
        stdout_contains=(
            "File written!",
            "Line 3: Python is fun!",
            "File now has 4 lines.",
        ),
        expected_files={
            "example.txt": (
                "Hello, file!\n"
                "This is line 2.\n"
                "Python is fun!\n"
                "This line was appended!\n"
            ),
        },
    ),
    "file_i_o/csv_files.py": ExampleExpectation(
        stdout_contains=(
            "CSV file written!",
            "Columns: ['Name', 'Age', 'Grade']",
            "Alice is 14 and got A",
            "Charlie is 14 and got A-",
        ),
        expected_files={
            "students.csv": (
                "Name,Age,Grade\n"
                "Alice,14,A\n"
                "Bob,15,B+\n"
                "Charlie,14,A-\n"
            ),
        },
    ),
    "file_i_o/json_files.py": ExampleExpectation(
        stdout_contains=(
            "Game saved!",
            "Loaded save for: Hero123",
            "Items: sword, shield, potion",
            "Position: (42, 108)",
        ),
        expected_json_files={
            "savegame.json": {
                "player": "Hero123",
                "level": 7,
                "health": 85,
                "inventory": ["sword", "shield", "potion"],
                "position": {"x": 42, "y": 108},
            },
        },
    ),
    "classes_and_objects/basic_classes.py": ExampleExpectation(
        stdout_contains=(
            "Buddy the Golden Retriever",
            "Max the Beagle",
            "Buddy learned sit!",
            "Buddy knows: sit, shake",
            "Max knows: roll over",
        ),
    ),
    "classes_and_objects/inheritance.py": ExampleExpectation(
        stdout_contains=(
            "Whiskers says Meow!",
            "Rex says Woof!",
            "Whiskers purrs softly...",
            "Rex fetches the ball!",
            "Is whiskers an Animal? True",
        ),
    ),
    "classes_and_objects/magic_methods.py": ExampleExpectation(
        stdout_contains=(
            "a = Vector(3, 4)",
            "a + b = Vector(4, 6)",
            "a * 3 = Vector(9, 12)",
            "a == Vector(3, 4): True",
            "|a| = 5.00",
        ),
    ),
    "classes_and_objects/dataclass_examples.py": ExampleExpectation(
        stdout_contains=(
            "p1 = Point(x=3, y=4)",
            "p1 == p2: True",
            "p1 == p3: False",
            "Courses: ['Math', 'Science']",
            "Courses: []",
        ),
    ),
    "classes_and_objects/custom_exceptions.py": ExampleExpectation(
        stdout_contains=(
            "Withdrew $50. Balance: $50.00",
            "Tried: $200.00, Have: $50.00",
            "Invalid age: 200 is not a valid age",
        ),
    ),
    "fun_projects/rock_paper_scissors.py": ExampleExpectation(
        stdin="rock\nquit\n",
        stdout_contains=(
            "=== Rock Paper Scissors ===",
            "Final score:",
        ),
        validator="rock_paper_scissors",
    ),
    "fun_projects/password_generator.py": ExampleExpectation(
        stdin="8\n2\nn\n",
        stdout_contains=(
            "=== Password Generator ===",
            "Generated passwords (8 chars):",
        ),
        validator="password_generator",
    ),
    "fun_projects/word_counter.py": ExampleExpectation(
        stdout_contains=(
            "Total words: 23",
            "Unique words: 18",
            "Word frequencies:",
            "python        3 ###",
        ),
    ),
    "fun_projects/hangman.py": ExampleExpectation(
        stdin="z\nq\nx\nj\nk\nw\n",
        stdout_contains=(
            "=== Hangman ===",
            "Wrong guesses left: 6",
            "Game over! The word was",
        ),
        stdout_patterns=(
            r'Game over! The word was "'
            r'(python|coding|function|variable|string)"\.',
        ),
    ),
    "fun_projects/dice_roller.py": ExampleExpectation(
        stdout_contains=(
            "=== Dice Roller ===",
            "Rolling 2 dice 1000 times:",
            "7 is the most common total because there",
        ),
        validator="dice_roller",
    ),
    "modules_and_tools/modules_and_imports.py": ExampleExpectation(
        stdout_contains=(
            "Pi: 3.141592653589793",
            "Square root of 16: 4.0",
            "Current directory:",
            "Your username:",
            "Python version:",
            "Tip: Use 'import this' to see the Zen of Python!",
        ),
        stdout_patterns=(
            r"Random number 1-10: (?:[1-9]|10)",
            r"Random fruit: (?:apple|banana|cherry)",
        ),
    ),
    "modules_and_tools/regular_expressions.py": ExampleExpectation(
        stdout_contains=(
            "Phone numbers found:",
            "Emails found:",
            "Username validation:",
            'Cleaned: "too many spaces here"',
            "Split items: ['apple', 'banana', 'cherry', 'date']",
        ),
    ),
    "modules_and_tools/date_and_time.py": ExampleExpectation(
        stdout_contains=(
            "Right now:",
            "Birthday: 2000-06-15",
            "Day of week: Thursday",
            "Days until New Year:",
            "Parsed: 2024-03-15 14:30:00",
            "Hour: 14, Minute: 30",
        ),
        stdout_patterns=(
            r"Date only: \d{4}-\d{2}-\d{2}",
            r"Short:\s+\d{2}/\d{2}/\d{2}",
        ),
    ),
    "modules_and_tools/command_line_arguments.py": ExampleExpectation(
        stdout_contains=(
            "Number of args: 0",
            "Name:  Alice",
            "Count: 3",
            "Loud:  True",
            "HELLO, ALICE!",
        ),
    ),
    "modules_and_tools/virtual_environments.py": ExampleExpectation(
        stdout_contains=(
            "Common pip commands:",
            "pip install <package>",
            "Installed packages (",
        ),
    ),
    "web_and_data/apis_and_http.py": ExampleExpectation(
        stdout_contains=(
            "Response from httpbin.org:",
            "Origin: 127.0.0.1",
            "POST response:",
            'Sent: {"name": "Alice", "score": 95}',
            "Parsed JSON:",
            "Alice, age 30",
            "Bob, age 25",
        ),
        uses_local_http=True,
    ),
    "web_and_data/database_sqlite.py": ExampleExpectation(
        stdout_contains=(
            "Inserted 5 students",
            "All students:",
            "Math students with grade > 80:",
            "Stats: avg=",
            "Database closed. (In-memory DB is now gone)",
        ),
    ),
    "web_and_data/testing.py": ExampleExpectation(
        stdout_contains=("All assert tests passed!",),
        stderr_contains=(
            "Ran 6 tests",
            "OK",
        ),
    ),
}

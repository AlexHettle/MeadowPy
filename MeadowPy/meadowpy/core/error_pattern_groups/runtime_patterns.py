"""Runtime, import, filesystem, and system error explanation patterns."""

import re

from meadowpy.core.error_pattern_groups.types import ErrorPattern

RUNTIME_PATTERNS: list[ErrorPattern] = [
    # Import errors
    (
        re.compile(r"ModuleNotFoundError: No module named '(.+)'"),
        "Python can't find the module '{0}'. You may need to "
        "install it (pip install {0}) or check the spelling.",
    ),
    (
        re.compile(
            r"ImportError: cannot import name '(.+)' from '(.+)'"
        ),
        "The name '{0}' doesn't exist in the module '{1}'. Check "
        "for typos or verify what the module exports.",
    ),
    (
        re.compile(
            r"ImportError: attempted relative import with no known "
            r"parent package"
        ),
        "You're using a relative import (with a dot) but Python "
        "can't determine the package. Run the file as a module "
        "or use absolute imports.",
    ),

    # File / OS errors
    (
        re.compile(
            r"FileNotFoundError:.*No such file or directory: '(.+)'"
        ),
        "Python can't find the file '{0}'. Check the file path and "
        "make sure the file exists.",
    ),
    (
        re.compile(r"FileExistsError:.*File exists: '(.+)'"),
        "The file or directory '{0}' already exists. Check if it "
        "already exists before creating, or use a different name.",
    ),
    (
        re.compile(r"IsADirectoryError:.*Is a directory: '(.+)'"),
        "You're trying to open '{0}' as a file, but it's a "
        "directory. Check your file path.",
    ),
    (
        re.compile(r"PermissionError"),
        "Python doesn't have permission to access this file. Try "
        "running as administrator or check file permissions.",
    ),

    # Math / overflow / division errors
    (
        re.compile(r"ZeroDivisionError: division by zero"),
        "You can't divide by zero. Check that your denominator "
        "isn't 0 before dividing.",
    ),
    (
        re.compile(r"ZeroDivisionError: float division by zero"),
        "You can't divide a float by zero. Check that your "
        "denominator isn't 0.0 before dividing.",
    ),
    (
        re.compile(r"ZeroDivisionError: integer modulo by zero"),
        "You can't use the modulo (%%) operator with zero as the "
        "divisor. Check that the right side isn't 0.",
    ),
    (
        re.compile(r"OverflowError: math range error"),
        "The result of a math operation is too large. Check your "
        "input values — they may be unreasonably large.",
    ),
    (
        re.compile(
            r"OverflowError: int too large to convert to float"
        ),
        "Your integer is too large to be represented as a float. "
        "Consider using the decimal module for very large numbers.",
    ),
    (
        re.compile(r"OverflowError"),
        "A number in your code is too large for Python to handle "
        "in this context.",
    ),

    # Recursion
    (
        re.compile(r"RecursionError: maximum recursion depth exceeded"),
        "Your function keeps calling itself forever. Make sure your "
        "recursive function has a base case that stops the "
        "recursion.",
    ),

    # Scope errors
    (
        re.compile(
            r"UnboundLocalError: .*local variable '([^']+)' "
            r"(?:referenced before assignment|"
            r"where it is not associated with a value)"
        ),
        "You're using the variable '{0}' before giving it a value "
        "in this function. If it's a global variable, add "
        "'global {0}' at the top of the function.",
    ),

    # RuntimeError
    (
        re.compile(
            r"RuntimeError: dictionary changed size during iteration"
        ),
        "You're adding or removing dictionary keys while looping "
        "over it. Loop over a copy instead: "
        "for key in list(my_dict):",
    ),
    (
        re.compile(
            r"RuntimeError: Set changed size during iteration"
        ),
        "You're adding or removing items from a set while looping "
        "over it. Loop over a copy instead: "
        "for item in list(my_set):",
    ),
    (
        re.compile(r"RuntimeError: generator raised StopIteration"),
        "A generator function used next() without handling "
        "StopIteration. Use a for loop instead of manual next() "
        "calls, or add a try/except.",
    ),

    # StopIteration
    (
        re.compile(r"StopIteration"),
        "You called next() on an iterator that has no more items. "
        "Use a for loop instead, or pass a default to "
        "next(iterator, default).",
    ),

    # Unicode errors
    (
        re.compile(
            r"UnicodeDecodeError: '(.+)' codec can't decode byte"
        ),
        "The file or data contains characters that Python can't "
        "read with the '{0}' encoding. Try opening the file with "
        "encoding='utf-8'.",
    ),
    (
        re.compile(
            r"UnicodeEncodeError: '(.+)' codec can't encode character"
        ),
        "Python can't write this character using the '{0}' "
        "encoding. Try using encoding='utf-8' when writing.",
    ),

    # AssertionError
    (
        re.compile(r"AssertionError: (.+)"),
        "An assert statement failed: {0}. The condition was False "
        "when it was expected to be True.",
    ),
    (
        re.compile(r"AssertionError$"),
        "An assert statement failed — the condition you were "
        "checking turned out to be False. Check your assumptions "
        "about the data.",
    ),

    # EOFError
    (
        re.compile(r"EOFError: EOF when reading a line"),
        "Python expected input but reached the end of input. This "
        "happens when input() is called but there's no data to "
        "read.",
    ),

    # NotImplementedError
    (
        re.compile(r"NotImplementedError"),
        "This method hasn't been implemented yet. If you see this "
        "in a class you wrote, you need to override this method "
        "in your subclass.",
    ),

    # MemoryError
    (
        re.compile(r"MemoryError"),
        "Your program ran out of memory. You may be creating a very "
        "large list or loading too much data at once. Try "
        "processing data in smaller chunks.",
    ),

    # SystemExit
    (
        re.compile(r"SystemExit: (.+)"),
        "The program exited with code {0}. This was triggered by "
        "sys.exit() or exit().",
    ),
]

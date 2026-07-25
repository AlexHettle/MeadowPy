"""Name, syntax, and indentation error explanation patterns."""

import re

from meadowpy.core.error_pattern_groups.types import ErrorPattern

SYNTAX_PATTERNS: list[ErrorPattern] = [
    # NameError
    (
        re.compile(
            r"NameError: name '(.+)' is not defined\. "
            r"Did you mean: '(.+)'\?"
        ),
        "Python doesn't recognize '{0}'. Did you mean '{1}'? "
        "Check your spelling.",
    ),
    (
        re.compile(
            r"NameError: name '(.+)' is not defined\. "
            r"Did you forget to import '(.+)'\?"
        ),
        "Python doesn't recognize '{0}'. You may need to add "
        "'import {1}' at the top of your file.",
    ),
    (
        re.compile(r"NameError: name '(.+)' is not defined"),
        "Python doesn't recognize '{0}'. Check for typos, or make sure "
        "you defined it before using it.",
    ),

    # SyntaxError
    (
        re.compile(r"SyntaxError: Missing parentheses in call to 'print'"),
        "In Python 3, print is a function. Use print(\"text\") with "
        "parentheses instead of print \"text\".",
    ),
    (
        re.compile(r"SyntaxError: '(.+)' was never closed"),
        "You opened a {0} but never closed it. Find the matching "
        "closing bracket or parenthesis.",
    ),
    (
        re.compile(r"SyntaxError: unmatched '(.+)'"),
        "You have a closing {0} that doesn't match any opening "
        "bracket. Check for extra or misplaced brackets.",
    ),
    (
        re.compile(r"SyntaxError: expected ':'"),
        "Python expected a colon (:) here. Add a colon after your "
        "if, for, while, def, or class statement.",
    ),
    (
        re.compile(
            r"SyntaxError: invalid syntax\. Perhaps you forgot a comma\?"
        ),
        "Python found unexpected syntax. You probably forgot to put "
        "a comma between items.",
    ),
    (
        re.compile(
            r"SyntaxError: expression cannot contain assignment, "
            r"perhaps you meant \"==\"\?"
        ),
        "You used = (assignment) where you probably meant == "
        "(comparison). Use == to compare values.",
    ),
    (
        re.compile(r"SyntaxError: 'return' outside function"),
        "A return statement can only be used inside a function (def). "
        "Check your indentation or move it inside a function.",
    ),
    (
        re.compile(r"SyntaxError: 'break' outside loop"),
        "The break keyword can only be used inside a for or while "
        "loop. Check your indentation.",
    ),
    (
        re.compile(r"SyntaxError: 'continue' outside loop"),
        "The continue keyword can only be used inside a for or while "
        "loop. Check your indentation.",
    ),
    (
        re.compile(r"SyntaxError: 'yield' outside function"),
        "The yield keyword can only be used inside a function. "
        "Move it inside a def block.",
    ),
    (
        re.compile(r"SyntaxError: cannot assign to literal"),
        "You can't assign a value to a literal like a number or "
        "string. Put the variable name on the left side of the =.",
    ),
    (
        re.compile(r"SyntaxError: cannot assign to function call"),
        "You can't assign a value to a function call. The variable "
        "name goes on the left side of =, and the function call "
        "on the right.",
    ),
    (
        re.compile(r"SyntaxError: cannot assign to expression"),
        "The left side of = must be a variable name, not an "
        "expression. Check for typos or extra operators.",
    ),
    (
        re.compile(r"SyntaxError: invalid character .+ \(U\+.+\)"),
        "There's a special or invisible character in your code that "
        "Python doesn't recognize. This often happens when copying "
        "code from a website. Try retyping the line manually.",
    ),
    (
        re.compile(r"SyntaxError: f-string: expecting '}'"),
        "Your f-string has an unclosed {{ bracket. Make sure every "
        "{{ has a matching }}.",
    ),
    (
        re.compile(r"SyntaxError: invalid escape sequence '(.+)'"),
        "The backslash sequence '{0}' isn't recognized. Use a raw "
        "string r\"...\" or double the backslash \\\\.",
    ),
    (
        re.compile(r"SyntaxError: invalid decimal literal"),
        "You can't start a variable name with a number. Variable "
        "names must start with a letter or underscore.",
    ),
    (
        re.compile(r"SyntaxError: cannot use starred expression here"),
        "The * unpacking operator can't be used in this position. "
        "It's only valid in assignments, function calls, or "
        "list/tuple literals.",
    ),
    (
        re.compile(
            r"SyntaxError: positional argument follows keyword argument"
        ),
        "Once you use a named argument (like name=\"Alex\"), all "
        "following arguments must also be named. Rearrange your "
        "arguments.",
    ),
    (
        re.compile(
            r"SyntaxError: non-default argument follows default argument"
        ),
        "All parameters with default values must come after "
        "parameters without defaults. Rearrange your function "
        "parameters.",
    ),
    (
        re.compile(
            r"SyntaxError: Did you mean to use 'from \.\.\. import "
            r"\.\.\.' instead\?"
        ),
        "It looks like you swapped the import order. Use "
        "'from module import name' instead of "
        "'import name from module'.",
    ),
    (
        re.compile(r"SyntaxError: unexpected EOF while parsing"),
        "Python reached the end of your code but expected more. "
        "You're probably missing a closing ), ], or }}.",
    ),
    (
        re.compile(r"SyntaxError: EOL while scanning string literal"),
        "You have an unclosed string. Make sure every opening quote "
        "has a matching closing quote.",
    ),
    (
        re.compile(r"SyntaxError: unterminated string literal"),
        "You have an unclosed string. Make sure every opening quote "
        "has a matching closing quote.",
    ),
    # Generic SyntaxError — must be LAST among SyntaxErrors
    (
        re.compile(r"SyntaxError: invalid syntax"),
        "Python found something it doesn't understand. Check for "
        "missing colons, unmatched brackets, or typos.",
    ),

    # IndentationError / TabError
    (
        re.compile(
            r"IndentationError: expected an indented block after "
            r"'(.+)' statement"
        ),
        "Python expected indented code after your {0} statement. "
        "Add 4 spaces before the next line.",
    ),
    (
        re.compile(r"IndentationError: expected an indented block"),
        "Python expected indented code after a colon (:). Add 4 "
        "spaces before the next line (e.g. after if, for, def, "
        "class).",
    ),
    (
        re.compile(r"IndentationError: unexpected indent"),
        "This line has extra spaces or tabs at the start. Make sure "
        "it lines up with the code around it.",
    ),
    (
        re.compile(r"IndentationError: unindent does not match"),
        "The indentation on this line doesn't match any previous "
        "level. Check for mixed tabs and spaces.",
    ),
    (
        re.compile(r"TabError: inconsistent use of tabs and spaces"),
        "You're mixing tabs and spaces for indentation. Pick one "
        "(spaces are recommended) and use it everywhere.",
    ),
]

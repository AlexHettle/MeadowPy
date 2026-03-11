"""Beginner-friendly error explainer.

Matches common Python error messages against a hand-written dictionary of
regex patterns and returns plain-English explanations that help beginners
understand what went wrong and how to fix it.

~100 patterns covering the most frequent beginner mistakes.
"""

import re

# Each entry: (compiled_regex, explanation_template)
# Templates use {0}, {1}, etc. for captured regex groups.
# Patterns are tried in order — first match wins.
# IMPORTANT: more specific patterns must come before generic ones.
ERROR_PATTERNS: list[tuple[re.Pattern, str]] = [

    # ══════════════════════════════════════════════════════════════════
    # NameError
    # ══════════════════════════════════════════════════════════════════
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

    # ══════════════════════════════════════════════════════════════════
    # SyntaxError
    # ══════════════════════════════════════════════════════════════════
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

    # ══════════════════════════════════════════════════════════════════
    # IndentationError / TabError
    # ══════════════════════════════════════════════════════════════════
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

    # ══════════════════════════════════════════════════════════════════
    # TypeError
    # ══════════════════════════════════════════════════════════════════
    (
        re.compile(
            r"TypeError: unsupported operand type\(s\) for (.+): "
            r"'(.+)' and '(.+)'"
        ),
        "You can't use {0} between a {1} and a {2}. Convert one to "
        "match the other (e.g. str() or int()).",
    ),
    (
        re.compile(r"TypeError: can only concatenate (.+) .* to (.+)"),
        "You can't add a {0} to a {1}. Use str() to convert numbers "
        "to text, or int()/float() for the reverse.",
    ),
    (
        re.compile(
            r"TypeError: '(.+)' not supported between instances of "
            r"'(.+)' and '(.+)'"
        ),
        "You can't compare a {1} with a {2} using {0}. Make sure "
        "both values are the same type before comparing.",
    ),
    (
        re.compile(
            r"TypeError: (.+) not supported between instances of "
            r"'NoneType' and"
        ),
        "You're comparing None with another value. A variable is "
        "unexpectedly None — check for missing return statements.",
    ),
    (
        re.compile(r"TypeError: 'NoneType' object is not (.+)"),
        "You're trying to use None as if it were something else. "
        "A function probably returned nothing — check if you forgot "
        "a return statement.",
    ),
    (
        re.compile(r"TypeError: '(.+)' object is not callable"),
        "You're trying to call a {0} value like a function. Did you "
        "accidentally use parentheses () instead of brackets []?",
    ),
    (
        re.compile(r"TypeError: '(.+)' object is not subscriptable"),
        "You're trying to use brackets [] on a {0}, which doesn't "
        "support indexing.",
    ),
    (
        re.compile(r"TypeError: '(.+)' object is not iterable"),
        "You can't loop over a {0}. Make sure you're iterating over "
        "a list, string, range, or other sequence.",
    ),
    (
        re.compile(r"TypeError: cannot unpack non-iterable (.+) object"),
        "You're trying to assign multiple variables from a {0}, but "
        "it can't be unpacked. Make sure the right side is a list, "
        "tuple, or other sequence.",
    ),
    (
        re.compile(
            r"TypeError: '(.+)' object does not support item assignment"
        ),
        "You can't change individual items in a {0} because it's "
        "immutable. For strings, create a new string instead; for "
        "tuples, use a list.",
    ),
    (
        re.compile(r"TypeError: unhashable type: '(.+)'"),
        "A {0} can't be used as a dictionary key or in a set "
        "because it's mutable. Use a tuple instead of a list, or "
        "convert to a hashable type.",
    ),
    (
        re.compile(r"TypeError: object of type '(.+)' has no len\(\)"),
        "You can't use len() on a {0}. len() only works on "
        "sequences and collections like strings, lists, and dicts.",
    ),
    (
        re.compile(
            r"TypeError: .+\(\) takes (\d+) positional arguments? "
            r"but (\d+) (?:was|were) given"
        ),
        "The function expected {0} argument(s) but received {1}. "
        "Check how many values you're passing in.",
    ),
    (
        re.compile(
            r"TypeError: .+\(\) missing (\d+) required positional "
            r"argument"
        ),
        "You forgot to pass {0} required argument(s) to this "
        "function.",
    ),
    (
        re.compile(
            r"TypeError: .+\(\) missing (\d+) required keyword-only "
            r"argument"
        ),
        "You forgot to pass {0} required keyword argument(s). "
        "These must be provided by name.",
    ),
    (
        re.compile(
            r"TypeError: .+\(\) got an unexpected keyword argument "
            r"'(.+)'"
        ),
        "The function doesn't accept an argument named '{0}'. "
        "Check the function definition for valid parameter names.",
    ),
    (
        re.compile(
            r"TypeError: .+\(\) got multiple values for argument "
            r"'(.+)'"
        ),
        "The argument '{0}' was provided more than once. You may "
        "have passed it both positionally and as a keyword argument.",
    ),
    (
        re.compile(
            r"TypeError: descriptor '(.+)' requires a '(.+)' object "
            r"but received a '(.+)'"
        ),
        "You called {0} on the class itself instead of an instance. "
        "Create an object first, then call the method on it.",
    ),
    (
        re.compile(
            r"TypeError: '(.+)' object cannot be interpreted as an "
            r"integer"
        ),
        "Python expected a whole number but got a {0}. Use int() "
        "to convert it to an integer.",
    ),
    (
        re.compile(
            r"TypeError: a bytes-like object is required, not '(.+)'"
        ),
        "This function needs bytes, not a {0}. Use .encode() to "
        "convert a string to bytes.",
    ),
    (
        re.compile(
            r"TypeError: write\(\) argument must be str, not (.+)"
        ),
        "The write() method needs a string, not a {0}. Convert "
        "your data to a string with str() first.",
    ),
    (
        re.compile(r"TypeError: (.+) is not JSON serializable"),
        "Python can't convert {0} to JSON. Convert it to a basic "
        "type (dict, list, str, int, float, bool, None) first.",
    ),
    (
        re.compile(r"TypeError: string indices must be integers"),
        "You're using a non-integer value to index a string. Use "
        "an integer index like my_string[0], not a string key.",
    ),
    (
        re.compile(
            r"TypeError: list indices must be integers or slices, "
            r"not (.+)"
        ),
        "You're using a {0} to index a list. List indices must be "
        "integers (e.g., my_list[0]) or slices.",
    ),
    (
        re.compile(
            r"TypeError: bad operand type for unary (.+): '(.+)'"
        ),
        "You can't use the {0} operator on a {1}. Check that "
        "you're using the right variable.",
    ),
    (
        re.compile(
            r"TypeError: not all arguments converted during string "
            r"formatting"
        ),
        "You have a mismatch in string formatting. Check that the "
        "number of % placeholders matches the values, or switch "
        "to f-strings.",
    ),
    (
        re.compile(
            r"TypeError: object\.__init__\(\) takes exactly one "
            r"argument"
        ),
        "Your class __init__ method has a problem. Make sure you "
        "spelled __init__ with double underscores on each side.",
    ),

    # ══════════════════════════════════════════════════════════════════
    # ValueError
    # ══════════════════════════════════════════════════════════════════
    (
        re.compile(
            r"ValueError: invalid literal for int\(\) with base \d+: "
            r"'(.+)'"
        ),
        "Python can't convert '{0}' to a number. Make sure the "
        "string contains only digits.",
    ),
    (
        re.compile(
            r"ValueError: could not convert string to float: '(.+)'"
        ),
        "Python can't convert '{0}' to a decimal number. Make sure "
        "the string contains only numbers and at most one decimal "
        "point.",
    ),
    (
        re.compile(r"ValueError: math domain error"),
        "A math function received an invalid input (like taking "
        "the square root of a negative number). Check that your "
        "input is in the valid range.",
    ),
    (
        re.compile(r"ValueError: list\.remove\(x\): x not in list"),
        "The value you're trying to remove isn't in the list. "
        "Check that the item exists before removing it, or use "
        "a try/except.",
    ),
    (
        re.compile(r"ValueError: (.+) is not in list"),
        "The value you're looking for isn't in the list. Use "
        "'if value in my_list:' to check before accessing it.",
    ),
    (
        re.compile(r"ValueError: substring not found"),
        "The substring you searched for with .index() isn't in the "
        "string. Use .find() instead (returns -1 if not found) "
        "or check first.",
    ),
    (
        re.compile(r"ValueError: I/O operation on closed file"),
        "You're trying to read or write a file that has already "
        "been closed. Use a 'with' statement to keep files open "
        "automatically.",
    ),
    (
        re.compile(r"ValueError: not enough values to unpack"),
        "You're trying to assign to more variables than there are "
        "values. Check that both sides of the = have the same "
        "count.",
    ),
    (
        re.compile(r"ValueError: too many values to unpack"),
        "There are more values than variables to assign them to. "
        "Check that both sides of the = have the same count.",
    ),

    # ══════════════════════════════════════════════════════════════════
    # IndexError
    # ══════════════════════════════════════════════════════════════════
    (
        re.compile(r"IndexError: list index out of range"),
        "You're trying to access a position that doesn't exist in "
        "the list. Remember: indices start at 0, so a list of 3 "
        "items has indices 0, 1, 2.",
    ),
    (
        re.compile(r"IndexError: string index out of range"),
        "You're trying to access a character position that doesn't "
        "exist in the string. Remember: indices start at 0.",
    ),
    (
        re.compile(r"IndexError: tuple index out of range"),
        "You're trying to access a position that doesn't exist in "
        "the tuple. Remember: indices start at 0.",
    ),
    (
        re.compile(r"IndexError: pop index out of range"),
        "You're trying to pop an item at an index that doesn't "
        "exist. Check the list length before popping.",
    ),

    # ══════════════════════════════════════════════════════════════════
    # KeyError
    # ══════════════════════════════════════════════════════════════════
    (
        re.compile(r"KeyError: (.+)"),
        "The key {0} doesn't exist in the dictionary. Check for "
        "typos or use .get() to provide a default value.",
    ),

    # ══════════════════════════════════════════════════════════════════
    # AttributeError
    # ══════════════════════════════════════════════════════════════════
    (
        re.compile(
            r"AttributeError: 'NoneType' object has no attribute "
            r"'(.+)'"
        ),
        "You're calling .{0}() on a value that is None. A function "
        "probably returned nothing — check for missing return "
        "statements or in-place methods like .sort() that return "
        "None.",
    ),
    (
        re.compile(
            r"AttributeError: module '(.+)' has no attribute '(.+)'"
        ),
        "The module '{0}' doesn't have '{1}'. Check for typos in "
        "the attribute name, or make sure you're importing the "
        "right module.",
    ),
    (
        re.compile(
            r"AttributeError: '(.+)' object has no attribute '(.+)'\. "
            r"Did you mean: '(.+)'\?"
        ),
        "The {0} object doesn't have '{1}'. Did you mean '{2}'? "
        "Check your spelling.",
    ),
    (
        re.compile(
            r"AttributeError: '(.+)' object has no attribute '(.+)'"
        ),
        "The {0} object doesn't have a method or property called "
        "'{1}'. Check for typos or verify the object type.",
    ),

    # ══════════════════════════════════════════════════════════════════
    # Import errors
    # ══════════════════════════════════════════════════════════════════
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

    # ══════════════════════════════════════════════════════════════════
    # File / OS errors
    # ══════════════════════════════════════════════════════════════════
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

    # ══════════════════════════════════════════════════════════════════
    # Math / overflow / division errors
    # ══════════════════════════════════════════════════════════════════
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

    # ══════════════════════════════════════════════════════════════════
    # Recursion
    # ══════════════════════════════════════════════════════════════════
    (
        re.compile(r"RecursionError: maximum recursion depth exceeded"),
        "Your function keeps calling itself forever. Make sure your "
        "recursive function has a base case that stops the "
        "recursion.",
    ),

    # ══════════════════════════════════════════════════════════════════
    # Scope errors
    # ══════════════════════════════════════════════════════════════════
    (
        re.compile(
            r"UnboundLocalError: .*local variable '(.+)' "
            r"referenced before assignment"
        ),
        "You're using the variable '{0}' before giving it a value "
        "in this function. If it's a global variable, add "
        "'global {0}' at the top of the function.",
    ),

    # ══════════════════════════════════════════════════════════════════
    # RuntimeError
    # ══════════════════════════════════════════════════════════════════
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

    # ══════════════════════════════════════════════════════════════════
    # StopIteration
    # ══════════════════════════════════════════════════════════════════
    (
        re.compile(r"StopIteration"),
        "You called next() on an iterator that has no more items. "
        "Use a for loop instead, or pass a default to "
        "next(iterator, default).",
    ),

    # ══════════════════════════════════════════════════════════════════
    # Unicode errors
    # ══════════════════════════════════════════════════════════════════
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

    # ══════════════════════════════════════════════════════════════════
    # AssertionError
    # ══════════════════════════════════════════════════════════════════
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

    # ══════════════════════════════════════════════════════════════════
    # EOFError
    # ══════════════════════════════════════════════════════════════════
    (
        re.compile(r"EOFError: EOF when reading a line"),
        "Python expected input but reached the end of input. This "
        "happens when input() is called but there's no data to "
        "read.",
    ),

    # ══════════════════════════════════════════════════════════════════
    # NotImplementedError
    # ══════════════════════════════════════════════════════════════════
    (
        re.compile(r"NotImplementedError"),
        "This method hasn't been implemented yet. If you see this "
        "in a class you wrote, you need to override this method "
        "in your subclass.",
    ),

    # ══════════════════════════════════════════════════════════════════
    # MemoryError
    # ══════════════════════════════════════════════════════════════════
    (
        re.compile(r"MemoryError"),
        "Your program ran out of memory. You may be creating a very "
        "large list or loading too much data at once. Try "
        "processing data in smaller chunks.",
    ),

    # ══════════════════════════════════════════════════════════════════
    # SystemExit
    # ══════════════════════════════════════════════════════════════════
    (
        re.compile(r"SystemExit: (.+)"),
        "The program exited with code {0}. This was triggered by "
        "sys.exit() or exit().",
    ),
]


def explain_error(stderr_text: str) -> str | None:
    """Return a beginner-friendly explanation for a Python error, or None.

    Scans *stderr_text* for a line that matches one of the known error
    patterns and returns a short, plain-English hint.
    """
    for pattern, template in ERROR_PATTERNS:
        match = pattern.search(stderr_text)
        if match:
            # Fill in {0}, {1}, … from captured groups
            groups = match.groups()
            try:
                explanation = template.format(*groups)
            except (IndexError, KeyError):
                explanation = template
            return f"\U0001f4a1 {explanation}\n"
    return None

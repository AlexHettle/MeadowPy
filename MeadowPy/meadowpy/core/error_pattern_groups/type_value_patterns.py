"""Type, value, lookup, and attribute error explanation patterns."""

import re

from meadowpy.core.error_pattern_groups.types import ErrorPattern

TYPE_VALUE_PATTERNS: list[ErrorPattern] = [
    # TypeError
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

    # ValueError
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

    # IndexError
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

    # KeyError
    (
        re.compile(r"KeyError: (.+)"),
        "The key {0} doesn't exist in the dictionary. Check for "
        "typos or use .get() to provide a default value.",
    ),

    # AttributeError
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
]

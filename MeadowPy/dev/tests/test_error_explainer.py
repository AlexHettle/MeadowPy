import re
from collections import Counter
from string import Formatter

import pytest

from meadowpy.core import error_explainer
from meadowpy.core.error_explainer import explain_error
from meadowpy.core.error_pattern_groups.runtime_patterns import RUNTIME_PATTERNS
from meadowpy.core.error_pattern_groups.syntax_patterns import SYNTAX_PATTERNS
from meadowpy.core.error_pattern_groups.type_value_patterns import (
    TYPE_VALUE_PATTERNS,
)
from meadowpy.core.error_patterns import ERROR_PATTERNS


ERROR_PATTERN_CASES = tuple(ERROR_PATTERNS)


def assert_hint(message):
    explanation = explain_error(message)
    assert explanation is not None
    assert not explanation.startswith("\U0001f4a1 ")
    assert explanation.endswith("\n")
    return explanation


def test_error_pattern_catalog_preserves_family_order_and_unique_patterns():
    assert ERROR_PATTERNS == [
        *SYNTAX_PATTERNS,
        *TYPE_VALUE_PATTERNS,
        *RUNTIME_PATTERNS,
    ]

    pattern_keys = [
        (pattern.pattern, pattern.flags)
        for pattern, _template in ERROR_PATTERNS
    ]
    duplicates = [
        pattern
        for pattern, count in Counter(pattern_keys).items()
        if count > 1
    ]
    assert duplicates == []


@pytest.mark.parametrize(
    ("pattern", "template"),
    ERROR_PATTERN_CASES,
    ids=[f"pattern-{index:03d}" for index in range(len(ERROR_PATTERN_CASES))],
)
def test_error_pattern_templates_match_capture_groups(pattern, template):
    assert isinstance(pattern, re.Pattern)
    assert pattern.pattern
    assert isinstance(template, str)
    assert template.strip()

    fields = [
        field_name
        for _literal, field_name, _format_spec, _conversion in Formatter().parse(
            template
        )
        if field_name is not None
    ]
    for field_name in fields:
        assert field_name.isdecimal(), (
            f"{pattern.pattern!r} uses unsupported placeholder {field_name!r}"
        )
        assert int(field_name) < pattern.groups, (
            f"{pattern.pattern!r} has {pattern.groups} capture group(s), "
            f"but its template uses {{{field_name}}}"
        )

    template.format(*(["captured value"] * pattern.groups))


@pytest.mark.parametrize(
    ("message", "expected_fragments"),
    [
        pytest.param(
            "SyntaxError: invalid syntax. Perhaps you forgot a comma?",
            ("probably forgot to put a comma",),
            id="syntax-detail-before-generic-syntax-error",
        ),
        pytest.param(
            "IndentationError: expected an indented block after 'if' statement",
            ("after your if statement",),
            id="statement-detail-before-generic-indentation-error",
        ),
        pytest.param(
            "TypeError: '<' not supported between instances of "
            "'NoneType' and 'int'",
            ("comparing None", "missing return statements"),
            id="none-comparison-before-generic-comparison",
        ),
        pytest.param(
            "ValueError: list.remove(x): x not in list",
            ("value you're trying to remove",),
            id="list-remove-before-generic-list-lookup",
        ),
        pytest.param(
            "AttributeError: 'Widget' object has no attribute 'redner'. "
            "Did you mean: 'render'?",
            ("Widget object", "Did you mean 'render'?"),
            id="attribute-suggestion-before-generic-attribute-error",
        ),
        pytest.param(
            "OverflowError: math range error",
            ("result of a math operation is too large",),
            id="math-range-before-generic-overflow-error",
        ),
        pytest.param(
            "RuntimeError: generator raised StopIteration",
            ("generator function used next()",),
            id="generator-error-before-generic-stop-iteration",
        ),
    ],
)
def test_explain_error_prefers_specific_patterns(message, expected_fragments):
    explanation = assert_hint(message)

    for fragment in expected_fragments:
        assert fragment in explanation


def test_explain_error_matches_specific_name_error_pattern():
    message = "NameError: name 'pritn' is not defined. Did you mean: 'print'?"
    explanation = assert_hint(message)

    assert "Python doesn't recognize 'pritn'." in explanation
    assert "Did you mean 'print'?" in explanation


def test_explain_error_matches_error_line_inside_traceback():
    message = (
        "Traceback (most recent call last):\n"
        '  File "demo.py", line 1, in <module>\n'
        "    print(total)\n"
        "NameError: name 'total' is not defined\n"
    )
    explanation = assert_hint(message)

    assert "Python doesn't recognize 'total'." in explanation
    assert "Check for typos" in explanation


def test_explain_error_uses_generic_pattern_when_needed():
    message = "ZeroDivisionError: division by zero"
    explanation = assert_hint(message)

    assert "can't divide by zero" in explanation
    assert "denominator isn't 0" in explanation


def test_explain_error_matches_unbound_local_error_old_and_new_wording():
    old_message = "UnboundLocalError: local variable 'score' referenced before assignment"
    new_message = (
        "UnboundLocalError: cannot access local variable 'score' "
        "where it is not associated with a value"
    )

    old_explanation = assert_hint(old_message)
    new_explanation = assert_hint(new_message)

    assert old_explanation == new_explanation
    assert "variable 'score'" in old_explanation
    assert "global score" in old_explanation


def test_explain_error_returns_none_for_unknown_error():
    assert explain_error("TotallyUnknownError: no mapping") is None


def test_explain_error_falls_back_to_raw_template_for_bad_placeholders(monkeypatch):
    monkeypatch.setattr(
        error_explainer,
        "ERROR_PATTERNS",
        [(re.compile(r"ExampleError: (.+)"), "Broken placeholder {1}")],
    )

    explanation = explain_error("ExampleError: mismatched template")

    assert explanation == "Broken placeholder {1}\n"

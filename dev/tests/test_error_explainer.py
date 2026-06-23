import re

from meadowpy.core import error_explainer
from meadowpy.core.error_explainer import explain_error


def test_explain_error_matches_specific_name_error_pattern():
    message = "NameError: name 'pritn' is not defined. Did you mean: 'print'?"
    explanation = explain_error(message)

    assert explanation is not None
    assert "Did you mean 'print'?" in explanation


def test_explain_error_uses_generic_pattern_when_needed():
    message = "ZeroDivisionError: division by zero"
    explanation = explain_error(message)

    assert explanation is not None
    assert "can't divide by zero" in explanation


def test_explain_error_matches_unbound_local_error_old_and_new_wording():
    old_message = "UnboundLocalError: local variable 'score' referenced before assignment"
    new_message = (
        "UnboundLocalError: cannot access local variable 'score' "
        "where it is not associated with a value"
    )

    old_explanation = explain_error(old_message)
    new_explanation = explain_error(new_message)

    assert old_explanation is not None
    assert new_explanation is not None
    assert "variable 'score'" in old_explanation
    assert "variable 'score'" in new_explanation


def test_explain_error_returns_none_for_unknown_error():
    assert explain_error("TotallyUnknownError: no mapping") is None


def test_explain_error_falls_back_to_raw_template_for_bad_placeholders(monkeypatch):
    monkeypatch.setattr(
        error_explainer,
        "ERROR_PATTERNS",
        [(re.compile(r"ExampleError: (.+)"), "Broken placeholder {1}")],
    )

    explanation = explain_error("ExampleError: mismatched template")

    assert explanation == "\U0001f4a1 Broken placeholder {1}\n"

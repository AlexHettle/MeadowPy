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


def test_explain_error_returns_none_for_unknown_error():
    assert explain_error("TotallyUnknownError: no mapping") is None

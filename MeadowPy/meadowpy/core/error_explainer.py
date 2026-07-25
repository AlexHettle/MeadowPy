"""Beginner-friendly error explainer.

Matches common Python error messages against hand-written regex patterns and
returns plain-English explanations that help beginners understand what went
wrong and how to fix it.
"""

from meadowpy.core.error_patterns import ERROR_PATTERNS


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

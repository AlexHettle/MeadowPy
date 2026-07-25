"""Compiled beginner-friendly Python error explanation patterns."""

from meadowpy.core.error_pattern_groups.runtime_patterns import RUNTIME_PATTERNS
from meadowpy.core.error_pattern_groups.syntax_patterns import SYNTAX_PATTERNS
from meadowpy.core.error_pattern_groups.type_value_patterns import TYPE_VALUE_PATTERNS
from meadowpy.core.error_pattern_groups.types import ErrorPattern

# Each entry: (compiled_regex, explanation_template)
# Templates use {0}, {1}, etc. for captured regex groups.
# Patterns are tried in order - first match wins.
# IMPORTANT: more specific patterns must come before generic ones.
ERROR_PATTERNS: list[ErrorPattern] = [
    *SYNTAX_PATTERNS,
    *TYPE_VALUE_PATTERNS,
    *RUNTIME_PATTERNS,
]

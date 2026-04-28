"""Editor color themes for syntax highlighting."""

from dataclasses import dataclass, field


@dataclass
class EditorTheme:
    """Defines colors for the code editor."""
    name: str
    editor_background: str
    editor_foreground: str
    caret_line_background: str
    margin_background: str
    margin_foreground: str
    fold_margin_background: str
    foreground_colors: dict[int, str] = field(default_factory=dict)
    background_colors: dict[int, str] = field(default_factory=dict)


# QsciLexerPython style constants (numeric values for portability)
# 0=Default, 1=Comment, 2=Number, 3=DoubleQuotedString, 4=SingleQuotedString,
# 5=Keyword, 6=TripleSingleQuotedString, 7=TripleDoubleQuotedString,
# 8=ClassName, 9=FunctionMethodName, 10=Operator, 11=Identifier,
# 12=CommentBlock, 13=UnclosedString, 14=HighlightedIdentifier, 15=Decorator

DEFAULT_LIGHT = EditorTheme(
    name="default_light",
    editor_background="#FFFFFF",
    editor_foreground="#333333",
    caret_line_background="#E8F0FE",
    margin_background="#F5F5F5",
    margin_foreground="#999999",
    fold_margin_background="#F5F5F5",
    foreground_colors={
        0: "#333333",      # Default
        1: "#6A9955",      # Comment - green
        2: "#098658",      # Number - teal
        3: "#A31515",      # DoubleQuotedString - red-brown
        4: "#A31515",      # SingleQuotedString
        5: "#0000FF",      # Keyword - blue
        6: "#A31515",      # TripleSingleQuotedString
        7: "#A31515",      # TripleDoubleQuotedString
        8: "#267F99",      # ClassName - dark cyan
        9: "#795E26",      # FunctionMethodName - brown
        10: "#333333",     # Operator
        11: "#333333",     # Identifier
        12: "#6A9955",     # CommentBlock - green
        13: "#A31515",     # UnclosedString
        14: "#267F99",     # HighlightedIdentifier (built-ins)
        15: "#AF00DB",     # Decorator - purple
    },
)

DEFAULT_DARK = EditorTheme(
    name="default_dark",
    editor_background="#1E1E1E",
    editor_foreground="#D4D4D4",
    caret_line_background="#2A2D2E",
    margin_background="#252526",
    margin_foreground="#858585",
    fold_margin_background="#252526",
    foreground_colors={
        0: "#D4D4D4",      # Default
        1: "#6A9955",      # Comment - green
        2: "#B5CEA8",      # Number - light green
        3: "#CE9178",      # DoubleQuotedString - orange
        4: "#CE9178",      # SingleQuotedString
        5: "#569CD6",      # Keyword - blue
        6: "#CE9178",      # TripleSingleQuotedString
        7: "#CE9178",      # TripleDoubleQuotedString
        8: "#4EC9B0",      # ClassName - cyan
        9: "#DCDCAA",      # FunctionMethodName - yellow
        10: "#D4D4D4",     # Operator
        11: "#D4D4D4",     # Identifier
        12: "#6A9955",     # CommentBlock - green
        13: "#CE9178",     # UnclosedString
        14: "#4EC9B0",     # HighlightedIdentifier (built-ins)
        15: "#C586C0",     # Decorator - purple
    },
)

DEFAULT_HIGH_CONTRAST = EditorTheme(
    name="default_high_contrast",
    # Pure black + pure white maximises legibility for users with
    # low-vision / contrast-sensitivity needs (WCAG AAA). Everything
    # in the editor is monochrome — no syntax color cues — so the
    # theme is fully usable by people with any form of color blindness.
    editor_background="#000000",
    editor_foreground="#FFFFFF",
    caret_line_background="#2A2A2A",
    margin_background="#000000",
    margin_foreground="#FFFFFF",
    fold_margin_background="#000000",
    foreground_colors={
        0: "#FFFFFF",      # Default
        1: "#FFFFFF",      # Comment
        2: "#FFFFFF",      # Number
        3: "#FFFFFF",      # DoubleQuotedString
        4: "#FFFFFF",      # SingleQuotedString
        5: "#FFFFFF",      # Keyword
        6: "#FFFFFF",      # TripleSingleQuotedString
        7: "#FFFFFF",      # TripleDoubleQuotedString
        8: "#FFFFFF",      # ClassName
        9: "#FFFFFF",      # FunctionMethodName
        10: "#FFFFFF",     # Operator
        11: "#FFFFFF",     # Identifier
        12: "#FFFFFF",     # CommentBlock
        13: "#FFFFFF",     # UnclosedString
        14: "#FFFFFF",     # HighlightedIdentifier (built-ins)
        15: "#FFFFFF",     # Decorator
    },
)


THEMES: dict[str, EditorTheme] = {
    "default_light": DEFAULT_LIGHT,
    "default_dark": DEFAULT_DARK,
    "default_high_contrast": DEFAULT_HIGH_CONTRAST,
    # "custom" is registered so it appears in the Preferences combo.
    # Its actual editor colors are resolved at runtime via get_theme(),
    # which delegates to DEFAULT_DARK or DEFAULT_LIGHT based on the
    # user's `editor.custom_theme.base` setting.
    "custom": DEFAULT_DARK,
}


def get_theme(name: str, custom_base: str = "dark") -> EditorTheme:
    """Return the named theme, falling back to default_light.

    When ``name == "custom"`` the returned theme mirrors either
    ``DEFAULT_DARK`` or ``DEFAULT_LIGHT`` depending on ``custom_base``.
    """
    if name == "custom":
        return DEFAULT_DARK if (custom_base or "dark").lower() == "dark" else DEFAULT_LIGHT
    return THEMES.get(name, DEFAULT_LIGHT)

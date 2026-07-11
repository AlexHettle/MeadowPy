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


# QsciLexerPython style IDs, kept local so theme data does not import PyQt.
PY_STYLE_DEFAULT = 0
PY_STYLE_COMMENT = 1
PY_STYLE_NUMBER = 2
PY_STYLE_DOUBLE_QUOTED_STRING = 3
PY_STYLE_SINGLE_QUOTED_STRING = 4
PY_STYLE_KEYWORD = 5
PY_STYLE_TRIPLE_SINGLE_QUOTED_STRING = 6
PY_STYLE_TRIPLE_DOUBLE_QUOTED_STRING = 7
PY_STYLE_CLASS_NAME = 8
PY_STYLE_FUNCTION_METHOD_NAME = 9
PY_STYLE_OPERATOR = 10
PY_STYLE_IDENTIFIER = 11
PY_STYLE_COMMENT_BLOCK = 12
PY_STYLE_UNCLOSED_STRING = 13
PY_STYLE_HIGHLIGHTED_IDENTIFIER = 14
PY_STYLE_DECORATOR = 15
PY_STYLE_DOUBLE_QUOTED_FSTRING = 16
PY_STYLE_SINGLE_QUOTED_FSTRING = 17
PY_STYLE_TRIPLE_SINGLE_QUOTED_FSTRING = 18
PY_STYLE_TRIPLE_DOUBLE_QUOTED_FSTRING = 19

DEFAULT_LIGHT = EditorTheme(
    name="default_light",
    editor_background="#FFFFFF",
    editor_foreground="#333333",
    caret_line_background="#E8F0FE",
    margin_background="#F5F5F5",
    margin_foreground="#999999",
    fold_margin_background="#F5F5F5",
    foreground_colors={
        PY_STYLE_DEFAULT: "#333333",
        PY_STYLE_COMMENT: "#4B763C",
        PY_STYLE_NUMBER: "#087B50",
        PY_STYLE_DOUBLE_QUOTED_STRING: "#A31515",
        PY_STYLE_SINGLE_QUOTED_STRING: "#A31515",
        PY_STYLE_KEYWORD: "#0000FF",
        PY_STYLE_TRIPLE_SINGLE_QUOTED_STRING: "#A31515",
        PY_STYLE_TRIPLE_DOUBLE_QUOTED_STRING: "#A31515",
        PY_STYLE_CLASS_NAME: "#1F7188",
        PY_STYLE_FUNCTION_METHOD_NAME: "#795E26",
        PY_STYLE_OPERATOR: "#333333",
        PY_STYLE_IDENTIFIER: "#333333",
        PY_STYLE_COMMENT_BLOCK: "#4B763C",
        PY_STYLE_UNCLOSED_STRING: "#A31515",
        PY_STYLE_HIGHLIGHTED_IDENTIFIER: "#1F7188",
        PY_STYLE_DECORATOR: "#AF00DB",
        PY_STYLE_DOUBLE_QUOTED_FSTRING: "#A31515",
        PY_STYLE_SINGLE_QUOTED_FSTRING: "#A31515",
        PY_STYLE_TRIPLE_SINGLE_QUOTED_FSTRING: "#A31515",
        PY_STYLE_TRIPLE_DOUBLE_QUOTED_FSTRING: "#A31515",
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
        PY_STYLE_DEFAULT: "#D4D4D4",
        PY_STYLE_COMMENT: "#72A463",
        PY_STYLE_NUMBER: "#B5CEA8",
        PY_STYLE_DOUBLE_QUOTED_STRING: "#CE9178",
        PY_STYLE_SINGLE_QUOTED_STRING: "#CE9178",
        PY_STYLE_KEYWORD: "#569CD6",
        PY_STYLE_TRIPLE_SINGLE_QUOTED_STRING: "#CE9178",
        PY_STYLE_TRIPLE_DOUBLE_QUOTED_STRING: "#CE9178",
        PY_STYLE_CLASS_NAME: "#4EC9B0",
        PY_STYLE_FUNCTION_METHOD_NAME: "#DCDCAA",
        PY_STYLE_OPERATOR: "#D4D4D4",
        PY_STYLE_IDENTIFIER: "#D4D4D4",
        PY_STYLE_COMMENT_BLOCK: "#72A463",
        PY_STYLE_UNCLOSED_STRING: "#CE9178",
        PY_STYLE_HIGHLIGHTED_IDENTIFIER: "#4EC9B0",
        PY_STYLE_DECORATOR: "#C586C0",
        PY_STYLE_DOUBLE_QUOTED_FSTRING: "#CE9178",
        PY_STYLE_SINGLE_QUOTED_FSTRING: "#CE9178",
        PY_STYLE_TRIPLE_SINGLE_QUOTED_FSTRING: "#CE9178",
        PY_STYLE_TRIPLE_DOUBLE_QUOTED_FSTRING: "#CE9178",
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
        PY_STYLE_DEFAULT: "#FFFFFF",
        PY_STYLE_COMMENT: "#FFFFFF",
        PY_STYLE_NUMBER: "#FFFFFF",
        PY_STYLE_DOUBLE_QUOTED_STRING: "#FFFFFF",
        PY_STYLE_SINGLE_QUOTED_STRING: "#FFFFFF",
        PY_STYLE_KEYWORD: "#FFFFFF",
        PY_STYLE_TRIPLE_SINGLE_QUOTED_STRING: "#FFFFFF",
        PY_STYLE_TRIPLE_DOUBLE_QUOTED_STRING: "#FFFFFF",
        PY_STYLE_CLASS_NAME: "#FFFFFF",
        PY_STYLE_FUNCTION_METHOD_NAME: "#FFFFFF",
        PY_STYLE_OPERATOR: "#FFFFFF",
        PY_STYLE_IDENTIFIER: "#FFFFFF",
        PY_STYLE_COMMENT_BLOCK: "#FFFFFF",
        PY_STYLE_UNCLOSED_STRING: "#FFFFFF",
        PY_STYLE_HIGHLIGHTED_IDENTIFIER: "#FFFFFF",
        PY_STYLE_DECORATOR: "#FFFFFF",
        PY_STYLE_DOUBLE_QUOTED_FSTRING: "#FFFFFF",
        PY_STYLE_SINGLE_QUOTED_FSTRING: "#FFFFFF",
        PY_STYLE_TRIPLE_SINGLE_QUOTED_FSTRING: "#FFFFFF",
        PY_STYLE_TRIPLE_DOUBLE_QUOTED_FSTRING: "#FFFFFF",
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

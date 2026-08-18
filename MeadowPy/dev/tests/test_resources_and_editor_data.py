import json
import keyword
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from PyQt6.Qsci import QsciLexerPython

from meadowpy.constants import APP_NAME, DEFAULT_SETTINGS, DEFAULT_WINDOW_STATE
from meadowpy.editor import completion
from meadowpy.editor.themes import (
    DEFAULT_DARK,
    DEFAULT_HIGH_CONTRAST,
    DEFAULT_LIGHT,
    get_theme,
)
from meadowpy.resources import example_library
from meadowpy.resources.example_library import (
    EXAMPLE_CATEGORIES,
    load_example_categories,
)
from meadowpy.resources.keyword_help import KEYWORD_HELP


PYTHON_LEXER_STYLES = (
    QsciLexerPython.Default,
    QsciLexerPython.Comment,
    QsciLexerPython.Number,
    QsciLexerPython.DoubleQuotedString,
    QsciLexerPython.SingleQuotedString,
    QsciLexerPython.Keyword,
    QsciLexerPython.TripleSingleQuotedString,
    QsciLexerPython.TripleDoubleQuotedString,
    QsciLexerPython.ClassName,
    QsciLexerPython.FunctionMethodName,
    QsciLexerPython.Operator,
    QsciLexerPython.Identifier,
    QsciLexerPython.CommentBlock,
    QsciLexerPython.UnclosedString,
    QsciLexerPython.HighlightedIdentifier,
    QsciLexerPython.Decorator,
    QsciLexerPython.DoubleQuotedFString,
    QsciLexerPython.SingleQuotedFString,
    QsciLexerPython.TripleSingleQuotedFString,
    QsciLexerPython.TripleDoubleQuotedFString,
)


def _relative_luminance(hex_color: str) -> float:
    channels = [
        int(hex_color[index:index + 2], 16) / 255
        for index in (1, 3, 5)
    ]
    linear = [
        channel / 12.92
        if channel <= 0.04045
        else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(foreground: str, background: str) -> float:
    foreground_luminance = _relative_luminance(foreground)
    background_luminance = _relative_luminance(background)
    lighter = max(foreground_luminance, background_luminance)
    darker = min(foreground_luminance, background_luminance)
    return (lighter + 0.05) / (darker + 0.05)


class FakeApis:
    def __init__(self, lexer):
        self.lexer = lexer
        self.words = []
        self.prepared = False

    def add(self, word):
        self.words.append(word)

    def prepare(self):
        self.prepared = True


def test_keyword_help_covers_every_python_keyword():
    assert set(keyword.kwlist) <= set(KEYWORD_HELP)


@pytest.mark.parametrize("topic", KEYWORD_HELP)
def test_keyword_help_entries_are_complete_and_valid_python(topic):
    entry = KEYWORD_HELP[topic]

    assert isinstance(topic, str)
    assert topic.strip()
    assert isinstance(entry, dict)
    assert set(entry) == {"explanation", "example"}

    for field in ("explanation", "example"):
        assert isinstance(entry[field], str)
        assert entry[field].strip()

    compile(entry["example"], f"<keyword-help:{topic}>", "exec")


def test_example_library_has_categories_and_examples():
    assert EXAMPLE_CATEGORIES
    testing_examples = [
        example
        for category in EXAMPLE_CATEGORIES
        for example in category["examples"]
        if example["name"] == "Testing"
    ]

    assert testing_examples
    assert "unittest" in testing_examples[0]["code"]


def test_example_library_catalog_loads_from_resource_files():
    loaded = load_example_categories()
    total_examples = sum(len(category["examples"]) for category in loaded)

    assert loaded == EXAMPLE_CATEGORIES
    assert len(loaded) == 9
    assert total_examples == 47


def test_example_library_catalog_references_existing_files():
    examples_dir = Path(example_library.__file__).with_name("examples")
    catalog_path = examples_dir / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

    assert catalog["version"] == 1
    assert catalog["categories"]

    for category in catalog["categories"]:
        assert category["name"]
        assert category["icon"]
        assert category["examples"]
        for example in category["examples"]:
            code_path = examples_dir / example["code_file"]
            assert example["name"]
            assert example["desc"]
            assert code_path.is_file()


def test_example_library_loaded_entries_are_complete():
    for category in EXAMPLE_CATEGORIES:
        assert category["name"]
        assert category["icon"]
        assert category["examples"]
        for example in category["examples"]:
            assert example["name"]
            assert example["desc"]
            assert example["code"].strip()


def test_theme_lookup_supports_custom_base_and_fallback():
    assert get_theme("custom", custom_base="dark") is DEFAULT_DARK
    assert get_theme("custom", custom_base="light") is DEFAULT_LIGHT
    assert get_theme("missing").name == "default_light"


def test_python_themes_define_every_lexer_style():
    expected_styles = set(PYTHON_LEXER_STYLES)

    for theme in (DEFAULT_LIGHT, DEFAULT_DARK, DEFAULT_HIGH_CONTRAST):
        assert expected_styles <= set(theme.foreground_colors)


def test_python_theme_tokens_meet_normal_text_contrast_on_editor_surfaces():
    minimum_contrast = 4.5

    for theme in (DEFAULT_LIGHT, DEFAULT_DARK, DEFAULT_HIGH_CONTRAST):
        for style, foreground in theme.foreground_colors.items():
            for surface_name, background in (
                ("editor", theme.editor_background),
                ("caret line", theme.caret_line_background),
            ):
                contrast = _contrast_ratio(foreground, background)
                assert contrast >= minimum_contrast, (
                    f"{theme.name} style {style} has "
                    f"{contrast:.2f}:1 contrast "
                    f"on the {surface_name} background"
                )


def test_python_completions_are_cached_and_include_keywords(monkeypatch):
    monkeypatch.setattr(completion, "_CACHED_COMPLETIONS", None)

    first = completion.get_python_completions()
    second = completion.get_python_completions()

    assert first is second
    assert "print" in first
    assert "for" in first


def test_python_completions_fall_back_without_stdlib_module_names(monkeypatch):
    monkeypatch.setattr(completion, "_CACHED_COMPLETIONS", None)
    monkeypatch.setattr(completion, "sys", SimpleNamespace())

    completions = completion.get_python_completions()

    assert "for" in completions
    assert "print" in completions
    assert "asyncio" not in completions


def test_create_apis_populates_and_prepares(monkeypatch):
    monkeypatch.setattr(completion, "QsciAPIs", FakeApis)
    monkeypatch.setattr(completion, "get_python_completions", lambda: ["alpha", "beta"])

    apis = completion.create_apis(object())

    assert apis.words == ["alpha", "beta"]
    assert apis.prepared is True


def test_constants_expose_expected_app_metadata():
    assert APP_NAME == "MeadowPy"
    assert DEFAULT_SETTINGS["editor.theme"] == "default_dark"
    assert DEFAULT_SETTINGS["window.state"] == DEFAULT_WINDOW_STATE


def test_readme_coverage_badge_text_matches_svg():
    project_root = Path(__file__).resolve().parents[3]
    readme = (project_root / "README.md").read_text(encoding="utf-8")
    badge = (
        project_root / ".github" / "assets" / "readme-badges.svg"
    ).read_text(encoding="utf-8")

    readme_match = re.search(r"Coverage: (\d+)%", readme)
    badge_desc_match = re.search(
        r"(\d+) percent test coverage",
        badge,
    )
    badge_text_values = re.findall(r">(\d+)%</text>", badge)

    assert readme_match is not None
    assert badge_desc_match is not None
    assert badge_text_values
    expected = readme_match.group(1)
    assert badge_desc_match.group(1) == expected
    assert set(badge_text_values) == {expected}

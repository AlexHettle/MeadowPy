from meadowpy.constants import APP_NAME, DEFAULT_SETTINGS
from meadowpy.editor import completion
from meadowpy.editor.themes import DEFAULT_DARK, DEFAULT_LIGHT, get_theme
from meadowpy.resources.example_library import EXAMPLE_CATEGORIES
from meadowpy.resources.keyword_help import KEYWORD_HELP


class FakeApis:
    def __init__(self, lexer):
        self.lexer = lexer
        self.words = []
        self.prepared = False

    def add(self, word):
        self.words.append(word)

    def prepare(self):
        self.prepared = True


def test_keyword_help_entries_have_explanations_and_examples():
    assert "for" in KEYWORD_HELP
    assert KEYWORD_HELP["for"]["explanation"]
    assert "print" in KEYWORD_HELP
    assert "example" in KEYWORD_HELP["print"]


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


def test_theme_lookup_supports_custom_base_and_fallback():
    assert get_theme("custom", custom_base="dark") is DEFAULT_DARK
    assert get_theme("custom", custom_base="light") is DEFAULT_LIGHT
    assert get_theme("missing").name == "default_light"


def test_python_completions_are_cached_and_include_keywords(monkeypatch):
    monkeypatch.setattr(completion, "_CACHED_COMPLETIONS", None)

    first = completion.get_python_completions()
    second = completion.get_python_completions()

    assert first is second
    assert "print" in first
    assert "for" in first


def test_create_apis_populates_and_prepares(monkeypatch):
    monkeypatch.setattr(completion, "QsciAPIs", FakeApis)
    monkeypatch.setattr(completion, "get_python_completions", lambda: ["alpha", "beta"])

    apis = completion.create_apis(object())

    assert apis.words == ["alpha", "beta"]
    assert apis.prepared is True


def test_constants_expose_expected_app_metadata():
    assert APP_NAME == "MeadowPy"
    assert DEFAULT_SETTINGS["editor.theme"] == "default_dark"

import json
from pathlib import Path
from types import SimpleNamespace

from meadowpy.constants import APP_NAME, DEFAULT_SETTINGS, DEFAULT_WINDOW_STATE
from meadowpy.editor import completion
from meadowpy.editor.themes import DEFAULT_DARK, DEFAULT_LIGHT, get_theme
from meadowpy.resources import example_library
from meadowpy.resources.example_library import (
    EXAMPLE_CATEGORIES,
    load_example_categories,
)
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

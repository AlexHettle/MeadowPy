"""Built-in Python example library for beginners.

The library content lives under ``resources/examples`` so example source
files remain readable, editable, and syntax-checkable on their own.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_EXAMPLES_DIR = Path(__file__).with_name("examples")
_CATALOG_PATH = _EXAMPLES_DIR / "catalog.json"


def _read_code_file(path: Path) -> str:
    """Read an example source file and normalize line endings to LF."""
    return (
        path.read_text(encoding="utf-8")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )


def load_example_categories() -> list[dict[str, Any]]:
    """Load the example catalog in the shape expected by the UI."""
    catalog = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    categories: list[dict[str, Any]] = []

    for category in catalog["categories"]:
        examples = []
        for example in category["examples"]:
            code_path = _EXAMPLES_DIR / example["code_file"]
            examples.append({
                "name": example["name"],
                "desc": example["desc"],
                "code": _read_code_file(code_path),
            })

        categories.append({
            "name": category["name"],
            "icon": category["icon"],
            "examples": examples,
        })

    return categories


EXAMPLE_CATEGORIES = load_example_categories()

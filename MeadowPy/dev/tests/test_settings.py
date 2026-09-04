import ast
import json
from pathlib import Path

from meadowpy.constants import (
    CONFIG_DIR_NAME,
    DEFAULT_SETTINGS,
    DEFAULT_WINDOW_LAYOUT_VERSION,
    DEFAULT_WINDOW_STATE,
    LEGACY_DEFAULT_WINDOW_STATES,
    RESTORE_TABS_MIGRATION_VERSION,
    SETTINGS_FILENAME,
)
from meadowpy.core.settings import Settings
from tests.helpers import SignalRecorder


PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "meadowpy"
SETTINGS_RECEIVER_NAMES = {"settings", "_settings"}


def _settings_receiver_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def test_literal_setting_references_have_registered_defaults():
    references = []

    for source_path in PACKAGE_ROOT.rglob("*.py"):
        tree = ast.parse(
            source_path.read_text(encoding="utf-8"),
            filename=str(source_path),
        )
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in {"get", "set"} or not node.args:
                continue
            if (
                _settings_receiver_name(node.func.value)
                not in SETTINGS_RECEIVER_NAMES
            ):
                continue

            key_node = node.args[0]
            if not isinstance(key_node, ast.Constant):
                continue
            if not isinstance(key_node.value, str):
                continue

            location = source_path.relative_to(PACKAGE_ROOT.parent)
            references.append((key_node.value, f"{location}:{node.lineno}"))

    assert references
    unregistered = [
        f"{key!r} at {location}"
        for key, location in references
        if key not in DEFAULT_SETTINGS
    ]
    assert unregistered == []


def test_default_config_dir_uses_user_home(monkeypatch, tmp_path):
    monkeypatch.setattr("meadowpy.core.settings.Path.home", lambda: tmp_path)

    settings = Settings()

    assert settings.config_file_path == tmp_path / CONFIG_DIR_NAME / SETTINGS_FILENAME


def test_get_uses_saved_values_then_defaults(tmp_path):
    settings = Settings(tmp_path)

    assert settings.get("editor.font_size") == DEFAULT_SETTINGS["editor.font_size"]
    assert settings.get("missing.setting", "fallback") == "fallback"

    settings.set("custom.value", 123)
    assert settings.get("custom.value") == 123


def test_set_emits_only_when_value_changes(tmp_path):
    settings = Settings(tmp_path)
    recorder = SignalRecorder()
    settings.settings_changed.connect(recorder)

    settings.set("editor.font_size", 16)
    settings.set("editor.font_size", 16)
    settings.set("editor.font_size", 18)

    assert recorder.calls == [
        ("editor.font_size", 16),
        ("editor.font_size", 18),
    ]


def test_save_and_load_round_trip(tmp_path):
    settings = Settings(tmp_path)
    settings.set("editor.font_size", 20)
    settings.set("window.recent_files", ["alpha.py"])
    settings.save()

    reloaded = Settings(tmp_path)
    reloaded.load()

    assert reloaded.get("editor.font_size") == 20
    assert reloaded.get("window.recent_files") == ["alpha.py"]


def test_lint_style_issues_default_on_and_persists(tmp_path):
    settings = Settings(tmp_path)

    assert settings.get("editor.show_lint_style_issues") is True

    settings.set("editor.show_lint_style_issues", False)
    settings.save()

    reloaded = Settings(tmp_path)
    reloaded.load()

    assert reloaded.get("editor.show_lint_style_issues") is False


def test_restore_tabs_defaults_to_previous_session(tmp_path):
    settings = Settings(tmp_path)

    assert settings.get("general.restore_tabs_on_startup") is True
    assert settings.get("general.restore_tabs_on_startup_explicit") is False
    migration = settings.get("general.restore_tabs_migration_version")
    assert migration == RESTORE_TABS_MIGRATION_VERSION


def test_load_repairs_welcome_first_restore_tabs_migration(tmp_path):
    config_file = tmp_path / "settings.json"
    config_file.write_text(
        json.dumps({
            "general.restore_tabs_on_startup": False,
            "general.restore_tabs_on_startup_explicit": True,
            "general.open_files": ["Calculator.py"],
        }),
        encoding="utf-8",
    )

    settings = Settings(tmp_path)
    settings.load()

    assert settings.get("general.restore_tabs_on_startup") is True
    assert settings.get("general.restore_tabs_on_startup_explicit") is True
    migration = settings.get("general.restore_tabs_migration_version")
    assert migration == RESTORE_TABS_MIGRATION_VERSION
    assert settings.get("general.open_files") == ["Calculator.py"]


def test_load_preserves_explicit_restore_tabs_choice(tmp_path):
    config_file = tmp_path / "settings.json"
    config_file.write_text(
        json.dumps({
            "general.restore_tabs_on_startup": True,
            "general.restore_tabs_on_startup_explicit": True,
        }),
        encoding="utf-8",
    )

    settings = Settings(tmp_path)
    settings.load()

    assert settings.get("general.restore_tabs_on_startup") is True


def test_load_preserves_disabled_restore_choice_after_migration(tmp_path):
    config_file = tmp_path / "settings.json"
    config_file.write_text(
        json.dumps({
            "general.restore_tabs_on_startup": False,
            "general.restore_tabs_on_startup_explicit": True,
            "general.restore_tabs_migration_version": (
                RESTORE_TABS_MIGRATION_VERSION
            ),
        }),
        encoding="utf-8",
    )

    settings = Settings(tmp_path)
    settings.load()

    assert settings.get("general.restore_tabs_on_startup") is False


def test_load_invalid_json_resets_to_empty_data(tmp_path):
    config_file = tmp_path / "settings.json"
    config_file.write_text("{not json", encoding="utf-8")

    settings = Settings(tmp_path)
    settings.load()

    assert settings.get("custom.key") is None
    assert settings.get("editor.theme") == DEFAULT_SETTINGS["editor.theme"]


def test_load_invalid_utf8_resets_to_empty_data(tmp_path):
    config_file = tmp_path / "settings.json"
    config_file.write_bytes(b'{"editor.theme": "\xff"}')

    settings = Settings(tmp_path)
    settings.set("custom.key", "stale")
    settings.load()

    assert settings.get("custom.key") is None
    assert settings.get("editor.theme") == DEFAULT_SETTINGS["editor.theme"]


def test_load_ignores_non_object_json_and_uses_defaults(tmp_path):
    config_file = tmp_path / "settings.json"
    config_file.write_text(json.dumps(["editor.font_size", 20]), encoding="utf-8")

    settings = Settings(tmp_path)
    settings.load()

    assert settings.get("editor.font_size") == DEFAULT_SETTINGS["editor.font_size"]
    assert settings.get("custom.key") is None


def test_load_migrates_only_the_legacy_default_window_state(tmp_path):
    legacy_state = next(iter(LEGACY_DEFAULT_WINDOW_STATES))
    config_file = tmp_path / "settings.json"
    config_file.write_text(
        json.dumps({
            "window.state": legacy_state,
            "editor.font_size": 18,
        }),
        encoding="utf-8",
    )

    settings = Settings(tmp_path)
    settings.load()

    assert settings.get("window.state") == DEFAULT_WINDOW_STATE
    assert settings.get("window.layout_version") == DEFAULT_WINDOW_LAYOUT_VERSION
    assert settings.get("editor.font_size") == 18


def test_load_preserves_custom_window_state(tmp_path):
    config_file = tmp_path / "settings.json"
    config_file.write_text(
        json.dumps({"window.state": "custom-layout"}),
        encoding="utf-8",
    )

    settings = Settings(tmp_path)
    settings.load()

    assert settings.get("window.state") == "custom-layout"


def test_reset_to_defaults_clears_custom_values_and_writes_defaults(tmp_path):
    settings = Settings(tmp_path)
    settings.set("editor.font_size", 99)
    settings.set("custom.value", "kept only in memory")
    settings.reset_to_defaults()

    data = json.loads(settings.config_file_path.read_text(encoding="utf-8"))
    assert data["editor.font_size"] == DEFAULT_SETTINGS["editor.font_size"]
    assert "custom.value" not in data


def test_config_file_path_points_to_settings_json(tmp_path):
    settings = Settings(tmp_path)

    assert settings.config_file_path == tmp_path / "settings.json"

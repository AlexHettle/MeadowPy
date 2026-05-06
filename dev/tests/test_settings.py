import json

from meadowpy.constants import (
    DEFAULT_SETTINGS,
    DEFAULT_WINDOW_LAYOUT_VERSION,
    DEFAULT_WINDOW_STATE,
    LEGACY_DEFAULT_WINDOW_STATES,
)
from meadowpy.core.settings import Settings
from tests.helpers import SignalRecorder


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


def test_load_invalid_json_resets_to_empty_data(tmp_path):
    config_file = tmp_path / "settings.json"
    config_file.write_text("{not json", encoding="utf-8")

    settings = Settings(tmp_path)
    settings.load()

    assert settings.get("custom.key") is None
    assert settings.get("editor.theme") == DEFAULT_SETTINGS["editor.theme"]


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

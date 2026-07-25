from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent

from meadowpy.core.settings import Settings
from meadowpy.core.shortcuts import (
    SHORTCUT_OVERRIDES_KEY,
    all_shortcuts,
    event_matches_shortcut,
    find_shortcut_conflict,
    get_default_shortcut,
    get_shortcut,
    normalize_shortcut,
    reset_all_shortcuts,
    reset_shortcut,
    set_shortcut,
    shortcut_count,
    shortcut_from_key_event,
    shortcut_is_default,
    shortcut_overrides,
)


class MemorySettings:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


def test_shortcut_overrides_persist_reset_and_report_conflicts(tmp_path):
    settings = Settings(tmp_path)

    assert get_shortcut(settings, "file.save") == "Ctrl+S"
    assert get_default_shortcut("file.preferences") == "Ctrl+,"
    assert get_default_shortcut("run.linter") == "Ctrl+Alt+L"
    assert find_shortcut_conflict(
        settings, "run.linter", "Ctrl+Alt+L"
    ) is None

    set_shortcut(settings, "file.save", "Ctrl+Alt+S")
    assert get_shortcut(settings, "file.save") == "Ctrl+Alt+S"
    assert (
        find_shortcut_conflict(settings, "file.close_tab", "Ctrl+Alt+S").id
        == "file.save"
    )

    settings.save()
    reloaded = Settings(tmp_path)
    reloaded.load()
    assert get_shortcut(reloaded, "file.save") == "Ctrl+Alt+S"

    reset_shortcut(reloaded, "file.save")
    assert get_shortcut(reloaded, "file.save") == get_default_shortcut("file.save")

    set_shortcut(reloaded, "file.save", "Ctrl+Alt+S")
    reset_all_shortcuts(reloaded)
    assert get_shortcut(reloaded, "file.save") == "Ctrl+S"


def test_shortcut_from_key_event_uses_portable_text(qapp):
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_S,
        Qt.KeyboardModifier.ControlModifier,
        "s",
    )

    assert shortcut_from_key_event(event) == "Ctrl+S"


def test_shortcut_from_key_event_ignores_typing_keys_without_command_modifier(qapp):
    plain_letter = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_A,
        Qt.KeyboardModifier.NoModifier,
        "a",
    )
    shifted_letter = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_A,
        Qt.KeyboardModifier.ShiftModifier,
        "A",
    )
    function_key = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_F5,
        Qt.KeyboardModifier.NoModifier,
    )
    shifted_function_key = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_F5,
        Qt.KeyboardModifier.ShiftModifier,
    )
    unknown_command_key = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_unknown,
        Qt.KeyboardModifier.ControlModifier,
    )

    assert shortcut_from_key_event(plain_letter) == ""
    assert shortcut_from_key_event(shifted_letter) == ""
    assert shortcut_from_key_event(function_key) == "F5"
    assert shortcut_from_key_event(shifted_function_key) == "Shift+F5"
    assert shortcut_from_key_event(unknown_command_key) == ""


def test_normalize_shortcut_handles_empty_invalid_and_multi_step_text():
    assert normalize_shortcut(None) == ""
    assert normalize_shortcut("   ") == ""
    assert normalize_shortcut("\0") == ""
    assert normalize_shortcut("not a shortcut") == ""
    assert normalize_shortcut("Ctrl+,") == "Ctrl+,"
    assert normalize_shortcut("Ctrl+S, Ctrl+O") == "Ctrl+S"


def test_shortcut_events_match_exact_shortcuts(qapp):
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_S,
        Qt.KeyboardModifier.ControlModifier,
        "s",
    )
    plain_letter = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_S,
        Qt.KeyboardModifier.NoModifier,
        "s",
    )
    modifier_only = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Control,
        Qt.KeyboardModifier.ControlModifier,
    )

    assert event_matches_shortcut(event, "Ctrl+S") is True
    assert event_matches_shortcut(event, "S") is False
    assert event_matches_shortcut(event, "Ctrl+O") is False
    assert event_matches_shortcut(event, "") is False
    assert event_matches_shortcut(plain_letter, "S") is False
    assert shortcut_from_key_event(modifier_only) == ""
    assert event_matches_shortcut(modifier_only, "Ctrl+S") is False


def test_shortcut_overrides_sanitize_stored_settings():
    settings = MemorySettings({SHORTCUT_OVERRIDES_KEY: "bad storage"})
    assert shortcut_overrides(settings) == {}

    settings.values[SHORTCUT_OVERRIDES_KEY] = {
        "file.save": "Ctrl+Alt+S, Ctrl+O",
        "file.open": "A",
        "file.save_as": "Shift+A",
        "run.file": "F5",
        "unknown.shortcut": "Ctrl+Q",
    }

    assert shortcut_overrides(settings) == {
        "file.save": "Ctrl+Alt+S",
        "run.file": "F5",
    }
    assert get_shortcut(settings, "file.save") == "Ctrl+Alt+S"
    assert get_shortcut(settings, "file.open") == "Ctrl+O"


def test_set_shortcut_to_default_removes_custom_override():
    settings = MemorySettings(
        {
            SHORTCUT_OVERRIDES_KEY: {
                "file.save": "Ctrl+Alt+S",
                "file.open": "Ctrl+Alt+O",
            }
        }
    )

    set_shortcut(settings, "file.save", "Ctrl+S")

    assert settings.values[SHORTCUT_OVERRIDES_KEY] == {
        "file.open": "Ctrl+Alt+O"
    }
    assert shortcut_is_default(settings, "file.save") is True
    reset_shortcut(settings, "file.save_as")
    assert settings.values[SHORTCUT_OVERRIDES_KEY] == {
        "file.open": "Ctrl+Alt+O"
    }
    set_shortcut(None, "file.save", "Ctrl+Alt+S")
    reset_shortcut(None, "file.save")
    reset_all_shortcuts(None)


def test_set_shortcut_rejects_typing_keys_without_command_modifier():
    settings = MemorySettings()

    set_shortcut(settings, "file.save", "A")

    assert get_shortcut(settings, "file.save") == ""
    assert settings.values[SHORTCUT_OVERRIDES_KEY] == {"file.save": ""}

    set_shortcut(settings, "file.save", "Shift+A")
    assert get_shortcut(settings, "file.save") == ""

    set_shortcut(settings, "file.save", "Alt+A")
    assert get_shortcut(settings, "file.save") == "Alt+A"

    set_shortcut(settings, "file.save", "F5")
    assert get_shortcut(settings, "file.save") == "F5"


def test_shortcut_conflicts_ignore_empty_shortcuts_and_self_matches():
    settings = MemorySettings({SHORTCUT_OVERRIDES_KEY: {"file.save": "Ctrl+Alt+S"}})
    shortcuts_by_id = {
        definition.id: shortcut
        for definition, shortcut in all_shortcuts(settings)
    }

    assert find_shortcut_conflict(settings, "file.open", "") is None
    assert find_shortcut_conflict(settings, "file.save", "Ctrl+Alt+S") is None
    assert shortcut_count() == len(shortcuts_by_id)
    assert shortcuts_by_id["file.save"] == "Ctrl+Alt+S"

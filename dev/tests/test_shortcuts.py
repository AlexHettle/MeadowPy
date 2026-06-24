from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent

from meadowpy.core.settings import Settings
from meadowpy.core.shortcuts import (
    find_shortcut_conflict,
    get_default_shortcut,
    get_shortcut,
    reset_all_shortcuts,
    reset_shortcut,
    set_shortcut,
    shortcut_from_key_event,
)


def test_shortcut_overrides_persist_reset_and_report_conflicts(tmp_path):
    settings = Settings(tmp_path)

    assert get_shortcut(settings, "file.save") == "Ctrl+S"

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

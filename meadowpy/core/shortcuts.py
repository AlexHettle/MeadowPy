"""Shared shortcut definitions, persistence, and key-event helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent, QKeySequence


SHORTCUT_OVERRIDES_KEY = "shortcuts.custom"

_MODIFIER_KEYS = {
    Qt.Key.Key_Control.value,
    Qt.Key.Key_Shift.value,
    Qt.Key.Key_Alt.value,
    Qt.Key.Key_Meta.value,
}

_COMMAND_MODIFIERS = (
    Qt.KeyboardModifier.ControlModifier
    | Qt.KeyboardModifier.AltModifier
    | Qt.KeyboardModifier.MetaModifier
)


@dataclass(frozen=True, slots=True)
class ShortcutDefinition:
    """Metadata for one user-visible shortcut."""

    id: str
    category: str
    name: str
    default: str
    description: str
    scope: str = "Application"


SHORTCUTS: tuple[ShortcutDefinition, ...] = (
    ShortcutDefinition(
        "file.new",
        "File",
        "New File",
        "Ctrl+N",
        "Creates a blank Python file in a new editor tab.",
    ),
    ShortcutDefinition(
        "file.open",
        "File",
        "Open File",
        "Ctrl+O",
        "Opens an existing file from disk.",
    ),
    ShortcutDefinition(
        "file.open_folder",
        "File",
        "Open Folder",
        "Ctrl+Shift+K",
        "Opens a project folder in the File Explorer.",
    ),
    ShortcutDefinition(
        "file.save",
        "File",
        "Save",
        "Ctrl+S",
        "Writes the file you're working on to disk.",
    ),
    ShortcutDefinition(
        "file.save_as",
        "File",
        "Save As",
        "Ctrl+Shift+S",
        "Saves the current file to a new path.",
    ),
    ShortcutDefinition(
        "file.close_tab",
        "File",
        "Close Tab",
        "Ctrl+W",
        "Closes the current editor tab after checking for unsaved work.",
    ),
    ShortcutDefinition(
        "file.preferences",
        "File",
        "Preferences",
        "Ctrl+,",
        "Opens MeadowPy settings and editor preferences.",
    ),
    ShortcutDefinition(
        "file.exit",
        "File",
        "Exit",
        "Ctrl+Q",
        "Closes MeadowPy after checking for unsaved work.",
    ),
    ShortcutDefinition(
        "edit.undo",
        "Edit",
        "Undo",
        "Ctrl+Z",
        "Undoes the last change in the focused text field.",
        "Focused text field",
    ),
    ShortcutDefinition(
        "edit.redo",
        "Edit",
        "Redo",
        "Ctrl+Y",
        "Redoes the last undone change in the focused text field.",
        "Focused text field",
    ),
    ShortcutDefinition(
        "edit.cut",
        "Edit",
        "Cut",
        "Ctrl+X",
        "Cuts the selected text from the focused text field.",
        "Focused text field",
    ),
    ShortcutDefinition(
        "edit.copy",
        "Edit",
        "Copy",
        "Ctrl+C",
        "Copies the selected text from the focused text field.",
        "Focused text field",
    ),
    ShortcutDefinition(
        "edit.paste",
        "Edit",
        "Paste",
        "Ctrl+V",
        "Pastes clipboard text into the focused text field.",
        "Focused text field",
    ),
    ShortcutDefinition(
        "edit.select_all",
        "Edit",
        "Select All",
        "Ctrl+A",
        "Selects all text in the focused text field.",
        "Focused text field",
    ),
    ShortcutDefinition(
        "edit.find",
        "Edit",
        "Find",
        "Ctrl+F",
        "Opens the find bar for the current file.",
    ),
    ShortcutDefinition(
        "edit.replace",
        "Edit",
        "Replace",
        "Ctrl+H",
        "Opens find and replace for the current file.",
    ),
    ShortcutDefinition(
        "edit.search_files",
        "Edit",
        "Search in Files",
        "Ctrl+Shift+F",
        "Searches across files in the open project folder.",
    ),
    ShortcutDefinition(
        "edit.goto_line",
        "Edit",
        "Go to Line",
        "Ctrl+G",
        "Moves the cursor to a specific line in the current file.",
    ),
    ShortcutDefinition(
        "edit.toggle_comment",
        "Edit",
        "Toggle Comment",
        "Ctrl+/",
        "Comments or uncomments the current Python line or selection.",
        "Python editor",
    ),
    ShortcutDefinition(
        "view.zoom_in",
        "View",
        "Zoom In",
        "Ctrl+=",
        "Increases the editor font size.",
    ),
    ShortcutDefinition(
        "view.zoom_out",
        "View",
        "Zoom Out",
        "Ctrl+-",
        "Decreases the editor font size.",
    ),
    ShortcutDefinition(
        "view.reset_zoom",
        "View",
        "Reset Zoom",
        "Ctrl+0",
        "Restores the editor font size from preferences.",
    ),
    ShortcutDefinition(
        "view.file_explorer",
        "View",
        "File Explorer",
        "Ctrl+Shift+E",
        "Shows or hides the File Explorer panel.",
    ),
    ShortcutDefinition(
        "view.symbol_outline",
        "View",
        "Symbol Outline",
        "Ctrl+Shift+O",
        "Shows or hides the Symbol Outline panel.",
    ),
    ShortcutDefinition(
        "view.problems",
        "View",
        "Problems Panel",
        "Ctrl+Shift+M",
        "Shows or hides lint and code issue results.",
    ),
    ShortcutDefinition(
        "view.output",
        "View",
        "Output Panel",
        "Ctrl+`",
        "Shows or hides the Output and Python Console panel.",
    ),
    ShortcutDefinition(
        "view.search",
        "View",
        "Search Panel",
        "Ctrl+Shift+J",
        "Shows or hides project search results.",
    ),
    ShortcutDefinition(
        "view.terminal",
        "View",
        "Terminal Panel",
        "Ctrl+Shift+T",
        "Shows or hides the integrated shell terminal.",
    ),
    ShortcutDefinition(
        "run.file",
        "Run",
        "Run File",
        "F5",
        "Runs the current Python file.",
    ),
    ShortcutDefinition(
        "run.selection",
        "Run",
        "Run Selection / Line",
        "Shift+F5",
        "Runs selected Python code, or the current line when nothing is selected.",
    ),
    ShortcutDefinition(
        "run.stop",
        "Run",
        "Stop Process",
        "Ctrl+F5",
        "Stops the running Python process.",
    ),
    ShortcutDefinition(
        "debug.start",
        "Debug",
        "Start Debugging",
        "F6",
        "Runs the current file with the debugger attached.",
    ),
    ShortcutDefinition(
        "debug.continue",
        "Debug",
        "Continue",
        "Ctrl+F6",
        "Continues a paused debug session.",
    ),
    ShortcutDefinition(
        "debug.step_over",
        "Debug",
        "Step Over",
        "F10",
        "Runs the current line without stepping into function calls.",
    ),
    ShortcutDefinition(
        "debug.step_into",
        "Debug",
        "Step Into",
        "F11",
        "Steps into the next function call while debugging.",
    ),
    ShortcutDefinition(
        "debug.step_out",
        "Debug",
        "Step Out",
        "Shift+F11",
        "Runs until the current function returns.",
    ),
    ShortcutDefinition(
        "debug.stop",
        "Debug",
        "Stop Debugging",
        "Ctrl+Shift+F5",
        "Stops the current debug session.",
    ),
    ShortcutDefinition(
        "debug.toggle_breakpoint",
        "Debug",
        "Toggle Breakpoint",
        "F9",
        "Adds or removes a breakpoint on the current line.",
    ),
    ShortcutDefinition(
        "ai.review_file",
        "AI",
        "Review Current File",
        "Ctrl+Shift+R",
        "Asks the AI assistant to review the current file.",
    ),
    ShortcutDefinition(
        "ai.chat_panel",
        "AI",
        "AI Chat Panel",
        "Ctrl+Shift+A",
        "Shows or hides the AI Chat panel.",
    ),
    ShortcutDefinition(
        "help.example_library",
        "Help",
        "Example Library",
        "Ctrl+Shift+L",
        "Opens the Python example library.",
    ),
)

SHORTCUTS_BY_ID = {definition.id: definition for definition in SHORTCUTS}


STANDARD_EDIT_SHORTCUTS = {
    "edit.undo": ("undo", QKeySequence.StandardKey.Undo),
    "edit.redo": ("redo", QKeySequence.StandardKey.Redo),
    "edit.cut": ("cut", QKeySequence.StandardKey.Cut),
    "edit.copy": ("copy", QKeySequence.StandardKey.Copy),
    "edit.paste": ("paste", QKeySequence.StandardKey.Paste),
    "edit.select_all": ("selectAll", QKeySequence.StandardKey.SelectAll),
}


def normalize_shortcut(shortcut: str | None) -> str:
    """Return a stable portable-text representation for *shortcut*."""
    text = (shortcut or "").strip()
    if not text:
        return ""
    sequence = QKeySequence(text)
    if sequence.isEmpty():
        return ""
    normalized = sequence.toString(QKeySequence.SequenceFormat.PortableText)
    # MeadowPy only captures single-step shortcuts. Qt separates multi-step
    # sequences with ", "; keep comma keys like "Ctrl+," intact.
    return normalized.split(", ", 1)[0].strip()


def _shortcut_is_assignable(shortcut: str | None) -> bool:
    normalized = normalize_shortcut(shortcut)
    if not normalized:
        return False
    parts = [part for part in normalized.split("+") if part]
    if any(part in {"Ctrl", "Alt", "Meta"} for part in parts):
        return True
    key = parts[-1] if parts else normalized
    if not key.startswith("F") or not key[1:].isdigit():
        return False
    return 1 <= int(key[1:]) <= 35


def shortcut_from_key_event(event: QKeyEvent) -> str:
    """Convert a key event into portable shortcut text."""
    key = event.key()
    if key in _MODIFIER_KEYS:
        return ""
    modifiers = event.modifiers()
    is_function_key = Qt.Key.Key_F1.value <= key <= Qt.Key.Key_F35.value
    if not is_function_key and not (modifiers & _COMMAND_MODIFIERS):
        return ""
    sequence = QKeySequence(event.keyCombination())
    shortcut = normalize_shortcut(
        sequence.toString(QKeySequence.SequenceFormat.PortableText)
    )
    return shortcut if _shortcut_is_assignable(shortcut) else ""


def event_matches_shortcut(event: QKeyEvent, shortcut: str | None) -> bool:
    """Return True when *event* exactly matches *shortcut*."""
    expected = normalize_shortcut(shortcut)
    if not expected:
        return False
    actual = shortcut_from_key_event(event)
    if not actual:
        return False
    return (
        QKeySequence(actual).matches(QKeySequence(expected))
        == QKeySequence.SequenceMatch.ExactMatch
    )


def _raw_overrides(settings: Any) -> dict[str, str]:
    data = settings.get(SHORTCUT_OVERRIDES_KEY, {}) if settings is not None else {}
    if not isinstance(data, dict):
        return {}
    overrides = {}
    for shortcut_id, value in data.items():
        shortcut_id = str(shortcut_id)
        if shortcut_id not in SHORTCUTS_BY_ID:
            continue
        normalized = normalize_shortcut(value)
        if normalized and not _shortcut_is_assignable(normalized):
            continue
        overrides[shortcut_id] = normalized
    return overrides


def shortcut_overrides(settings: Any) -> dict[str, str]:
    """Return normalized shortcut overrides from settings."""
    return dict(_raw_overrides(settings))


def get_shortcut(settings: Any, shortcut_id: str) -> str:
    """Return the active shortcut for *shortcut_id*."""
    definition = SHORTCUTS_BY_ID[shortcut_id]
    overrides = _raw_overrides(settings)
    if shortcut_id in overrides:
        return overrides[shortcut_id]
    return normalize_shortcut(definition.default)


def get_default_shortcut(shortcut_id: str) -> str:
    """Return the default shortcut for *shortcut_id*."""
    return normalize_shortcut(SHORTCUTS_BY_ID[shortcut_id].default)


def shortcut_is_default(settings: Any, shortcut_id: str) -> bool:
    """Return True when *shortcut_id* has no effective custom override."""
    return get_shortcut(settings, shortcut_id) == get_default_shortcut(shortcut_id)


def set_shortcut(settings: Any, shortcut_id: str, shortcut: str | None) -> None:
    """Persist a shortcut override. An empty shortcut clears the binding."""
    if settings is None:
        return
    normalized = normalize_shortcut(shortcut)
    if normalized and not _shortcut_is_assignable(normalized):
        normalized = ""
    default = get_default_shortcut(shortcut_id)
    overrides = _raw_overrides(settings)
    if normalized == default:
        overrides.pop(shortcut_id, None)
    else:
        overrides[shortcut_id] = normalized
    settings.set(SHORTCUT_OVERRIDES_KEY, overrides)


def reset_shortcut(settings: Any, shortcut_id: str) -> None:
    """Remove a single shortcut override."""
    if settings is None:
        return
    overrides = _raw_overrides(settings)
    if shortcut_id in overrides:
        overrides.pop(shortcut_id, None)
        settings.set(SHORTCUT_OVERRIDES_KEY, overrides)


def reset_all_shortcuts(settings: Any) -> None:
    """Remove every custom shortcut override."""
    if settings is not None:
        settings.set(SHORTCUT_OVERRIDES_KEY, {})


def all_shortcuts(settings: Any) -> list[tuple[ShortcutDefinition, str]]:
    """Return definitions paired with their active shortcut text."""
    return [
        (definition, get_shortcut(settings, definition.id))
        for definition in SHORTCUTS
    ]


def find_shortcut_conflict(
    settings: Any,
    shortcut_id: str,
    shortcut: str | None,
) -> ShortcutDefinition | None:
    """Return the existing shortcut definition using *shortcut*, if any."""
    normalized = normalize_shortcut(shortcut)
    if not normalized:
        return None
    for definition in SHORTCUTS:
        if definition.id == shortcut_id:
            continue
        if get_shortcut(settings, definition.id) == normalized:
            return definition
    return None


def shortcut_count() -> int:
    """Return the number of user-visible shortcuts."""
    return len(SHORTCUTS)

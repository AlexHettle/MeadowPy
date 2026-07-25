"""Shared context and base class for MainWindow controllers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import QObject

from meadowpy.ui.controllers.run_eligibility import can_run_editor


@dataclass(slots=True)
class MainWindowContext:
    """References shared by the MainWindow controller layer."""

    window: Any
    settings: Any
    file_manager: Any
    recent_files: Any


class MainWindowController(QObject):
    """Base controller that can read shared MainWindow state.

    Controllers own behavior, while the real QMainWindow remains the parent
    widget for dialogs, dock widgets, and application-level UI state.
    """

    def __init__(self, context: MainWindowContext):
        parent = context.window if isinstance(context.window, QObject) else None
        super().__init__(parent)
        self.context = context

    @property
    def window(self):
        return self.context.window

    def __getattr__(self, name: str):
        return getattr(self.window, name)

    def _refresh_run_action_enabled(self) -> None:
        """Let the workspace controller reapply run/debug action eligibility."""
        refresh = getattr(self.window, "_update_run_action_enabled", None)
        if callable(refresh):
            refresh()

    def _prepare_editor_file_for_execution(
        self,
        editor,
        expected_type: type | tuple[type, ...] | None = None,
    ) -> str | None:
        """Save the editor if needed and return a runnable file path."""
        if self._settings.get("run.save_before_run") and editor.isModified():
            if self.action_save() is False:
                return None

        file_path = editor.file_path
        if not file_path:
            if self.action_save_as() is False:
                return None
            file_path = editor.file_path
            if not file_path:
                return None
            if not can_run_editor(editor, expected_type):
                return None
        return file_path

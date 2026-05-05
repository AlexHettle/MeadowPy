"""Shared context and base class for MainWindow controllers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import QObject


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

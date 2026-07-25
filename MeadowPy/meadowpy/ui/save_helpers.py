"""Shared save prompts and save failure messaging."""

from pathlib import Path

from PyQt6.QtWidgets import QMessageBox


def prompt_save_before_closing(parent, display_name: str):
    """Ask whether a modified document should be saved before closing."""
    return QMessageBox.question(
        parent,
        "Unsaved Changes",
        f"'{display_name}' has unsaved changes.\n\nSave before closing?",
        QMessageBox.StandardButton.Save
        | QMessageBox.StandardButton.Discard
        | QMessageBox.StandardButton.Cancel,
    )


def show_save_failed(
    parent,
    file_manager,
    file_path: str | None,
    *,
    status_bar=None,
) -> None:
    """Tell the user a save failed and optionally update the status bar."""
    error = getattr(file_manager, "last_save_error", None)
    details = str(error) if error else "Unknown error."
    path_text = file_path or "the selected file"
    name = Path(file_path).name if file_path else "file"

    if status_bar is not None:
        status_bar.show_message(f"Could not save: {name}", 7000)

    QMessageBox.critical(
        parent,
        "Could Not Save File",
        f"MeadowPy could not save this file:\n{path_text}\n\n{details}",
    )

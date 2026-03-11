"""Virtual environment creation dialog."""

from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QPushButton, QHBoxLayout, QDialogButtonBox, QFileDialog,
    QMessageBox, QLabel,
)

from meadowpy.core.interpreter_manager import InterpreterManager


class VenvDialog(QDialog):
    """Dialog for creating a new Python virtual environment."""

    def __init__(
        self,
        interpreter_manager: InterpreterManager,
        file_path: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._manager = interpreter_manager
        self._file_path = file_path

        self.setWindowTitle("Create Virtual Environment")
        self.setMinimumWidth(450)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()

        # Directory picker
        dir_layout = QHBoxLayout()
        self._dir_edit = QLineEdit()
        default_dir = str(Path(self._file_path).parent) if self._file_path else ""
        self._dir_edit.setText(default_dir)
        self._dir_edit.setPlaceholderText("Select parent directory...")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_directory)
        dir_layout.addWidget(self._dir_edit, 1)
        dir_layout.addWidget(browse_btn)
        form.addRow("Location:", dir_layout)

        # Venv name
        self._name_edit = QLineEdit(".venv")
        form.addRow("Name:", self._name_edit)

        # Base interpreter
        self._interp_combo = QComboBox()
        interpreters = self._manager.detect_interpreters(self._file_path)
        for info in interpreters:
            self._interp_combo.addItem(
                f"{info.label}  ({info.path})", info.path
            )
        form.addRow("Base Interpreter:", self._interp_combo)

        layout.addLayout(form)

        # Info label
        self._info_label = QLabel("")
        self._info_label.setWordWrap(True)
        layout.addWidget(self._info_label)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._create_venv)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Select Parent Directory", self._dir_edit.text()
        )
        if directory:
            self._dir_edit.setText(directory)

    def _create_venv(self) -> None:
        """Validate inputs and create the virtual environment."""
        base_dir = self._dir_edit.text().strip()
        venv_name = self._name_edit.text().strip()

        if not base_dir:
            QMessageBox.warning(self, "Missing Directory", "Please select a directory.")
            return
        if not venv_name:
            QMessageBox.warning(self, "Missing Name", "Please enter a name for the venv.")
            return

        target = Path(base_dir) / venv_name
        if target.exists():
            QMessageBox.warning(
                self, "Already Exists",
                f"Directory already exists:\n{target}",
            )
            return

        interpreter = self._interp_combo.currentData()
        if not interpreter:
            QMessageBox.warning(self, "No Interpreter", "No interpreter selected.")
            return

        self._info_label.setText("Creating virtual environment...")
        self._info_label.repaint()

        try:
            result_path = self._manager.create_venv(base_dir, venv_name, interpreter)
            QMessageBox.information(
                self, "Success",
                f"Virtual environment created at:\n{result_path}",
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(
                self, "Error",
                f"Failed to create virtual environment:\n{e}",
            )
            self._info_label.setText("")

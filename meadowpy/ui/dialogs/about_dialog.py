"""About MeadowPy dialog."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel

from meadowpy.constants import APP_NAME, VERSION
from meadowpy.resources.resource_loader import get_icon_path


class AboutDialog(QDialog):
    """Simple About dialog showing app name, version, and description."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setFixedSize(400, 300)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # App icon
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_path = get_icon_path("meadowpy_256")
        if icon_path:
            pixmap = QPixmap(icon_path).scaled(
                80, 80,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            icon_label.setPixmap(pixmap)

        title = QLabel(f"<h1>{APP_NAME}</h1>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        version_label = QLabel(f"<p>Version {VERSION}</p>")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        description = QLabel(
            "<p>A beginner-friendly Python IDE with AI assistance.</p>"
            "<p>Built with PyQt6 and QScintilla.</p>"
        )
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setWordWrap(True)

        layout.addStretch()
        layout.addWidget(icon_label)
        layout.addWidget(title)
        layout.addWidget(version_label)
        layout.addWidget(description)
        layout.addStretch()

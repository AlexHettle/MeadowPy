import os
import shutil
import tempfile
from pathlib import Path

import pytest
from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QApplication


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def tmp_path():
    root = Path(__file__).resolve().parents[1] / ".test-artifacts"
    root.mkdir(exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="pytest-", dir=root))
    try:
        yield path
    finally:
        # Let Qt-owned models release file watchers before deleting temp dirs.
        app = QApplication.instance()
        if app is not None:
            app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            app.processEvents()
        shutil.rmtree(path, ignore_errors=True)

from pathlib import Path
from unittest.mock import Mock

from meadowpy.core.recent_files import RecentFilesManager
from meadowpy.core.settings import Settings
from tests.helpers import SignalRecorder


def make_manager(tmp_path, max_files=3):
    settings = Settings(tmp_path)
    settings.load()
    return settings, RecentFilesManager(settings, max_files=max_files)


def test_add_normalizes_deduplicates_and_emits(tmp_path):
    settings, manager = make_manager(tmp_path, max_files=5)
    recorder = SignalRecorder()
    manager.recent_files_changed.connect(recorder)

    alpha = tmp_path / "alpha.py"
    alpha.write_text("print('alpha')", encoding="utf-8")

    manager.add(str(alpha))
    manager.add(str(alpha))

    normalized = str(alpha.resolve())
    assert manager.get_files() == [normalized]
    assert recorder.calls[-1] == ([normalized],)
    assert settings.get("window.recent_files") == [normalized]


def test_add_trims_to_max_files(tmp_path):
    _, manager = make_manager(tmp_path, max_files=2)
    files = []
    for name in ("a.py", "b.py", "c.py"):
        path = tmp_path / name
        path.write_text(name, encoding="utf-8")
        files.append(str(path.resolve()))
        manager.add(str(path))

    assert manager.get_files() == [files[2], files[1]]


def test_remove_and_clear_update_settings(tmp_path):
    settings, manager = make_manager(tmp_path, max_files=5)
    alpha = tmp_path / "alpha.py"
    beta = tmp_path / "beta.py"
    alpha.write_text("", encoding="utf-8")
    beta.write_text("", encoding="utf-8")

    manager.add(str(alpha))
    manager.add(str(beta))

    recorder = SignalRecorder()
    manager.recent_files_changed.connect(recorder)

    manager.remove(str(alpha))
    remaining = str(beta.resolve())
    assert manager.get_files() == [remaining]
    assert recorder.calls == [([remaining],)]

    manager.clear()
    assert manager.get_files() == []
    assert settings.get("window.recent_files") == []
    assert recorder.calls == [([remaining],), ([],)]


def test_get_files_returns_copy(tmp_path):
    settings, manager = make_manager(tmp_path)
    stored_files = [str(Path(tmp_path / "alpha.py"))]
    settings.set("window.recent_files", stored_files)

    files = manager.get_files()
    files.append("mutated")

    assert files == [stored_files[0], "mutated"]
    assert manager.get_files() == stored_files
    assert settings.get("window.recent_files") == stored_files


def test_updates_remain_usable_when_settings_cannot_be_saved(tmp_path):
    settings, manager = make_manager(tmp_path, max_files=5)
    settings.save = Mock(side_effect=OSError("settings are read-only"))
    recorder = SignalRecorder()
    manager.recent_files_changed.connect(recorder)

    alpha = str((tmp_path / "alpha.py").resolve())
    beta = str((tmp_path / "beta.py").resolve())

    manager.add(alpha)
    manager.remove(alpha)
    manager.add(beta)
    manager.clear()

    assert manager.get_files() == []
    assert recorder.calls == [([alpha],), ([],), ([beta],), ([],)]
    assert settings.save.call_count == 4

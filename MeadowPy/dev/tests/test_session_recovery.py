import json

import pytest

from meadowpy.core.settings import Settings
from meadowpy.ui.session_recovery import (
    RECOVERY_SCHEMA_VERSION,
    RecoveryDataError,
    RecoveryDocument,
    RecoverySnapshotStore,
    SessionRecoveryManager,
)
from meadowpy.ui.tab_manager import TabManager


def test_recovery_store_round_trips_and_removes_empty_snapshots(tmp_path):
    path = tmp_path / "unsaved-recovery.json"
    store = RecoverySnapshotStore(path)
    documents = (
        RecoveryDocument(
            file_path="C:/work/demo.py",
            display_name="demo.py",
            content="print('draft')\n",
            cursor_line=0,
            cursor_index=5,
            active=True,
        ),
        RecoveryDocument(
            file_path=None,
            display_name="Untitled-3",
            content="answer = 42\n",
        ),
    )

    store.save(documents)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == RECOVERY_SCHEMA_VERSION
    assert payload["saved_at"]
    assert store.load() == documents
    assert not list(tmp_path.glob(".unsaved-recovery.json.*.tmp"))

    store.save(())
    assert not path.exists()


def test_recovery_store_preserves_previous_snapshot_when_replace_fails(
    monkeypatch,
    tmp_path,
):
    path = tmp_path / "unsaved-recovery.json"
    store = RecoverySnapshotStore(path)
    original = RecoveryDocument(None, "Untitled-1", "safe draft")
    store.save((original,))

    def fail_replace(_source, _destination):
        raise OSError("replace blocked")

    monkeypatch.setattr(
        "meadowpy.ui.session_recovery.os.replace",
        fail_replace,
    )

    with pytest.raises(OSError, match="replace blocked"):
        store.save((RecoveryDocument(None, "Untitled-1", "new draft"),))

    assert store.load() == (original,)
    assert not list(tmp_path.glob(".unsaved-recovery.json.*.tmp"))


def test_recovery_store_rejects_and_quarantines_invalid_data(tmp_path):
    path = tmp_path / "unsaved-recovery.json"
    path.write_text('{"schema_version": 999, "documents": []}', encoding="utf-8")
    store = RecoverySnapshotStore(path)

    with pytest.raises(RecoveryDataError, match="unsupported version"):
        store.load()

    quarantined = store.quarantine_invalid()
    assert quarantined is not None
    assert quarantined.exists()
    assert not path.exists()
    assert "invalid-" in quarantined.name


def test_recovery_manager_quarantines_invalid_utf8_and_continues_startup(
    monkeypatch,
    qapp,
    tmp_path,
):
    path = tmp_path / "unsaved-recovery.json"
    invalid_bytes = b"\xff\xfe\x00invalid recovery"
    path.write_bytes(invalid_bytes)
    warnings = []
    monkeypatch.setattr(
        "meadowpy.ui.session_recovery.QMessageBox.warning",
        lambda parent, title, message: warnings.append((parent, title, message)),
    )
    tabs = TabManager(Settings(tmp_path))
    manager = SessionRecoveryManager(tabs, path)

    assert manager.recover_if_available() == 0

    quarantined = list(tmp_path.glob("unsaved-recovery.invalid-*.json"))
    assert len(quarantined) == 1
    assert quarantined[0].read_bytes() == invalid_bytes
    assert not path.exists()
    assert manager._periodic_timer.isActive() is True
    assert len(warnings) == 1
    assert warnings[0][1] == "Recovery Data Could Not Be Read"
    assert "Could not read recovery data" in warnings[0][2]

    manager.stop()
    tabs.deleteLater()


def test_recovery_manager_snapshots_only_modified_editors(qapp, tmp_path):
    settings = Settings(tmp_path)
    tabs = TabManager(settings)
    path = tmp_path / "unsaved-recovery.json"
    manager = SessionRecoveryManager(tabs, path)
    editor = tabs.new_tab(content="first\nsecond", untitled_name="Untitled-4")
    editor.setCursorPosition(1, 3)
    editor.setModified(True)

    assert manager.flush(force=True) is True

    documents = RecoverySnapshotStore(path).load()
    assert documents == (
        RecoveryDocument(
            file_path=None,
            display_name="Untitled-4",
            content="first\nsecond",
            cursor_line=1,
            cursor_index=3,
            active=True,
        ),
    )

    editor.setModified(False)
    assert manager.flush(force=True) is True
    assert not path.exists()

    manager.stop()
    tabs.deleteLater()


def test_recovery_manager_restores_saved_and_untitled_buffers(qapp, tmp_path):
    settings = Settings(tmp_path)
    tabs = TabManager(settings)
    saved_path = tmp_path / "lesson.py"
    saved_path.write_text("print('on disk')\n", encoding="utf-8")
    existing = tabs.open_file_in_tab(
        str(saved_path),
        saved_path.read_text(encoding="utf-8"),
    )
    recovery_path = tmp_path / "unsaved-recovery.json"
    store = RecoverySnapshotStore(recovery_path)
    store.save((
        RecoveryDocument(
            file_path=str(saved_path),
            display_name="lesson.py",
            content="print('recovered')\n",
            cursor_line=0,
            cursor_index=6,
        ),
        RecoveryDocument(
            file_path=None,
            display_name="Untitled-7",
            content="name = 'Meadow'\n",
            cursor_line=0,
            cursor_index=4,
            active=True,
        ),
    ))
    manager = SessionRecoveryManager(tabs, recovery_path)

    prompt_documents = []
    restored = manager.recover_if_available(
        prompt=lambda documents: prompt_documents.extend(documents) or True
    )

    assert restored == 2
    assert len(prompt_documents) == 2
    assert tabs.count() == 2
    assert existing.text() == "print('recovered')\n"
    assert existing.is_modified is True

    untitled = tabs.current_editor()
    assert untitled is not None
    assert untitled.display_name == "Untitled-7"
    assert untitled.text() == "name = 'Meadow'\n"
    assert untitled.is_modified is True
    assert untitled.getCursorPosition() == (0, 4)

    next_untitled = tabs.new_tab()
    assert next_untitled.display_name == "Untitled-8"
    assert recovery_path.exists()

    manager.stop_and_clear()
    tabs.deleteLater()


def test_recovery_manager_preserves_pending_snapshot_until_prompt_is_resolved(
    qapp,
    tmp_path,
):
    settings = Settings(tmp_path)
    tabs = TabManager(settings)
    recovery_path = tmp_path / "unsaved-recovery.json"
    original = RecoveryDocument(
        None,
        "Untitled-1",
        "irreplaceable draft",
        active=True,
    )
    store = RecoverySnapshotStore(recovery_path)
    store.save((original,))
    manager = SessionRecoveryManager(tabs, recovery_path)

    assert manager._periodic_timer.isActive() is False
    assert manager.flush(force=True) is False
    assert store.load() == (original,)

    def restore_after_attempted_timer_flush(documents):
        assert documents == (original,)
        assert manager.flush() is False
        assert store.load() == (original,)
        return True

    assert manager.recover_if_available(prompt=restore_after_attempted_timer_flush) == 1
    assert manager._periodic_timer.isActive() is True
    assert store.load() == (original,)

    manager.stop_and_clear()
    tabs.deleteLater()


def test_recovery_manager_discards_only_after_explicit_rejection(qapp, tmp_path):
    settings = Settings(tmp_path)
    tabs = TabManager(settings)
    recovery_path = tmp_path / "unsaved-recovery.json"
    RecoverySnapshotStore(recovery_path).save((
        RecoveryDocument(None, "Untitled-1", "do not restore"),
    ))
    manager = SessionRecoveryManager(tabs, recovery_path)

    restored = manager.recover_if_available(prompt=lambda _documents: False)

    assert restored == 0
    assert tabs.count() == 0
    assert not recovery_path.exists()
    assert manager._periodic_timer.isActive() is True

    manager.stop()
    tabs.deleteLater()

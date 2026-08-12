"""Crash-safe snapshots and startup recovery for unsaved editor buffers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Callable, Iterable, Mapping
import weakref

from PyQt6.QtCore import QObject, QTimer, qWarning
from PyQt6.QtWidgets import QMessageBox

from meadowpy.editor.code_editor import CodeEditor


RECOVERY_FILENAME = "unsaved-recovery.json"
RECOVERY_SCHEMA_VERSION = 1


class RecoveryDataError(ValueError):
    """Raised when an existing recovery snapshot is malformed or unsupported."""


@dataclass(frozen=True)
class RecoveryDocument:
    """Serializable state for one modified editor buffer."""

    file_path: str | None
    display_name: str
    content: str
    cursor_line: int = 0
    cursor_index: int = 0
    active: bool = False
    large_file_mode: bool = False

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "RecoveryDocument":
        """Validate and construct a document from decoded JSON."""
        file_path = value.get("file_path")
        display_name = value.get("display_name")
        content = value.get("content")
        cursor_line = value.get("cursor_line", 0)
        cursor_index = value.get("cursor_index", 0)
        active = value.get("active", False)
        large_file_mode = value.get("large_file_mode", False)

        if file_path is not None and not isinstance(file_path, str):
            raise RecoveryDataError("file_path must be a string or null")
        if not isinstance(display_name, str) or not display_name.strip():
            raise RecoveryDataError("display_name must be a non-empty string")
        if not isinstance(content, str):
            raise RecoveryDataError("content must be a string")
        if (
            not isinstance(cursor_line, int)
            or isinstance(cursor_line, bool)
            or cursor_line < 0
        ):
            raise RecoveryDataError("cursor_line must be a non-negative integer")
        if (
            not isinstance(cursor_index, int)
            or isinstance(cursor_index, bool)
            or cursor_index < 0
        ):
            raise RecoveryDataError("cursor_index must be a non-negative integer")
        if not isinstance(active, bool):
            raise RecoveryDataError("active must be a boolean")
        if not isinstance(large_file_mode, bool):
            raise RecoveryDataError("large_file_mode must be a boolean")

        return cls(
            file_path=file_path,
            display_name=display_name,
            content=content,
            cursor_line=cursor_line,
            cursor_index=cursor_index,
            active=active,
            large_file_mode=large_file_mode,
        )


class RecoverySnapshotStore:
    """Read and atomically replace the on-disk recovery snapshot."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> tuple[RecoveryDocument, ...]:
        """Return validated recovery documents, or an empty tuple if absent."""
        if not self.path.exists():
            return ()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RecoveryDataError(f"Could not read recovery data: {exc}") from exc

        if not isinstance(payload, dict):
            raise RecoveryDataError("Recovery data must contain a JSON object")
        if payload.get("schema_version") != RECOVERY_SCHEMA_VERSION:
            raise RecoveryDataError("Recovery data uses an unsupported version")
        raw_documents = payload.get("documents")
        if not isinstance(raw_documents, list):
            raise RecoveryDataError("Recovery data must contain a document list")

        documents = []
        for raw_document in raw_documents:
            if not isinstance(raw_document, dict):
                raise RecoveryDataError("Each recovered document must be an object")
            documents.append(RecoveryDocument.from_mapping(raw_document))
        return tuple(documents)

    def save(self, documents: Iterable[RecoveryDocument]) -> None:
        """Atomically persist documents, removing the snapshot when empty."""
        documents = tuple(documents)
        if not documents:
            self.clear()
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": RECOVERY_SCHEMA_VERSION,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "documents": [asdict(document) for document in documents],
        }
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=self.path.parent,
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
                json.dump(payload, file, indent=2, ensure_ascii=False)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, self.path)
        finally:
            temporary_path.unlink(missing_ok=True)

    def clear(self) -> None:
        """Remove any pending snapshot without failing when none exists."""
        self.path.unlink(missing_ok=True)

    def quarantine_invalid(self) -> Path | None:
        """Move unreadable recovery data aside for manual inspection."""
        if not self.path.exists():
            return None
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        destination = self.path.with_name(
            f"{self.path.stem}.invalid-{timestamp}{self.path.suffix}"
        )
        counter = 1
        while destination.exists():
            destination = self.path.with_name(
                f"{self.path.stem}.invalid-{timestamp}-{counter}{self.path.suffix}"
            )
            counter += 1
        os.replace(self.path, destination)
        return destination


class SessionRecoveryManager(QObject):
    """Monitor modified editors and recover their contents after a crash."""

    SNAPSHOT_DELAY_MS = 1_000
    PERIODIC_SNAPSHOT_MS = 30_000

    def __init__(self, tab_manager, recovery_path: Path, parent=None):
        super().__init__(parent)
        self._tab_manager = tab_manager
        self._store = RecoverySnapshotStore(recovery_path)
        self._enabled = True
        self._pending_recovery = self._store.path.exists()
        self._last_fingerprint: tuple | None = None
        self._watched_editors: weakref.WeakSet = weakref.WeakSet()

        self._snapshot_timer = QTimer(self)
        self._snapshot_timer.setSingleShot(True)
        self._snapshot_timer.setInterval(self.SNAPSHOT_DELAY_MS)
        self._snapshot_timer.timeout.connect(self.flush)

        self._periodic_timer = QTimer(self)
        self._periodic_timer.setInterval(self.PERIODIC_SNAPSHOT_MS)
        self._periodic_timer.timeout.connect(self.flush)
        if not self._pending_recovery:
            self._periodic_timer.start()

        editor_created = getattr(tab_manager, "editor_created", None)
        if editor_created is not None:
            editor_created.connect(self._watch_editor)
        editor_closed = getattr(tab_manager, "editor_closed", None)
        if editor_closed is not None:
            editor_closed.connect(self._on_editor_closed)

        for index in range(tab_manager.count()):
            self._watch_editor(tab_manager.widget(index))

    @property
    def recovery_path(self) -> Path:
        """Return the recovery file path for diagnostics and tests."""
        return self._store.path

    def _watch_editor(self, editor) -> None:
        if not isinstance(editor, CodeEditor) or editor in self._watched_editors:
            return
        self._watched_editors.add(editor)
        editor.textChanged.connect(self.schedule_snapshot)
        editor.modification_changed.connect(self.schedule_snapshot)

    def _on_editor_closed(self, _editor) -> None:
        self.schedule_snapshot()

    def schedule_snapshot(self, *_args) -> None:
        """Debounce a snapshot after editor content or state changes."""
        if self._enabled and not self._pending_recovery:
            self._snapshot_timer.start()

    def flush(self, *, force: bool = False) -> bool:
        """Persist all modified buffers now; return whether writing succeeded."""
        if not self._enabled or self._pending_recovery:
            return False
        documents = self._collect_documents()
        fingerprint = self._fingerprint(documents)
        snapshot_exists = self._store.path.exists()
        expected_exists = bool(documents)
        if (
            not force
            and fingerprint == self._last_fingerprint
            and snapshot_exists == expected_exists
        ):
            return True
        try:
            self._store.save(documents)
        except OSError as exc:
            qWarning(f"Could not write MeadowPy recovery snapshot: {exc}")
            return False
        self._last_fingerprint = fingerprint
        return True

    def _collect_documents(self) -> tuple[RecoveryDocument, ...]:
        documents = []
        current_editor = self._tab_manager.current_editor()
        for index in range(self._tab_manager.count()):
            editor = self._tab_manager.widget(index)
            if not isinstance(editor, CodeEditor) or not editor.is_modified:
                continue
            line, cursor_index = editor.getCursorPosition()
            documents.append(RecoveryDocument(
                file_path=editor.file_path,
                display_name=editor.display_name,
                content=editor.text(),
                cursor_line=max(0, line),
                cursor_index=max(0, cursor_index),
                active=editor is current_editor,
                large_file_mode=bool(editor.large_file_mode),
            ))
        return tuple(documents)

    @staticmethod
    def _fingerprint(documents: Iterable[RecoveryDocument]) -> tuple:
        return tuple(
            (
                document.file_path,
                document.display_name,
                hashlib.sha256(document.content.encode("utf-8")).digest(),
                document.cursor_line,
                document.cursor_index,
                document.active,
                document.large_file_mode,
            )
            for document in documents
        )

    def recover_if_available(
        self,
        parent=None,
        *,
        prompt: Callable[[tuple[RecoveryDocument, ...]], bool] | None = None,
    ) -> int:
        """Offer recovery for a previous snapshot and return restored count."""
        if not self._store.path.exists():
            self._resume_monitoring()
            return 0
        try:
            documents = self._store.load()
        except RecoveryDataError as exc:
            self._handle_invalid_snapshot(parent, exc)
            self._resume_monitoring(snapshot_current=True)
            return 0
        if not documents:
            self.discard_pending()
            self._resume_monitoring(snapshot_current=True)
            return 0

        should_restore = (
            prompt(documents)
            if prompt is not None
            else self._show_recovery_prompt(parent, documents)
        )
        if not should_restore:
            self.discard_pending()
            self._resume_monitoring(snapshot_current=True)
            return 0

        restored = self.restore_documents(documents)
        self._resume_monitoring(snapshot_current=True)
        return restored

    def _resume_monitoring(self, *, snapshot_current: bool = False) -> None:
        """Allow writes only after previous recovery data has been resolved."""
        self._pending_recovery = False
        if not self._enabled:
            return
        if not self._periodic_timer.isActive():
            self._periodic_timer.start()
        if snapshot_current:
            self.flush(force=True)

    def restore_documents(self, documents: Iterable[RecoveryDocument]) -> int:
        """Recreate recovered buffers and mark them modified for explicit save."""
        restored = 0
        active_editor = None
        for document in documents:
            editor = self._find_editor(document.file_path)
            if editor is None:
                editor = self._tab_manager.new_tab(
                    document.file_path,
                    document.content,
                    large_file_mode=document.large_file_mode,
                    untitled_name=(
                        document.display_name if document.file_path is None else None
                    ),
                )
            else:
                editor.large_file_mode = document.large_file_mode
                editor.setText(document.content)

            editor.setModified(True)
            tab_index = self._tab_manager.indexOf(editor)
            self._tab_manager.update_tab_title(tab_index)
            editor.setCursorPosition(document.cursor_line, document.cursor_index)
            if document.active:
                active_editor = editor
            restored += 1

        if active_editor is not None:
            self._tab_manager.setCurrentWidget(active_editor)
        return restored

    def _find_editor(self, file_path: str | None):
        if not file_path:
            return None
        for index in range(self._tab_manager.count()):
            editor = self._tab_manager.widget(index)
            if not isinstance(editor, CodeEditor) or not editor.file_path:
                continue
            try:
                if Path(editor.file_path).resolve(strict=False) == Path(
                    file_path
                ).resolve(strict=False):
                    return editor
            except (OSError, RuntimeError):
                if editor.file_path == file_path:
                    return editor
        return None

    def _show_recovery_prompt(
        self,
        parent,
        documents: tuple[RecoveryDocument, ...],
    ) -> bool:
        names = "\n".join(
            f"• {document.display_name}" for document in documents[:8]
        )
        if len(documents) > 8:
            names += f"\n• …and {len(documents) - 8} more"

        message = QMessageBox(parent)
        message.setIcon(QMessageBox.Icon.Warning)
        message.setWindowTitle("Recover Unsaved Work")
        message.setText(
            "MeadowPy found unsaved work from a previous session."
        )
        message.setInformativeText(
            "This can happen after a crash, power loss, or forced shutdown.\n\n"
            f"{names}\n\n"
            "Restore these buffers so you can review and save them?"
        )
        restore_button = message.addButton(
            "Restore Work",
            QMessageBox.ButtonRole.AcceptRole,
        )
        discard_button = message.addButton(
            "Discard Recovery",
            QMessageBox.ButtonRole.DestructiveRole,
        )
        message.setDefaultButton(restore_button)
        message.exec()
        # Closing the prompt is treated as recovery; only an explicit discard
        # is allowed to delete the user's snapshot.
        return message.clickedButton() is not discard_button

    def _handle_invalid_snapshot(self, parent, error: RecoveryDataError) -> None:
        try:
            quarantined = self._store.quarantine_invalid()
        except OSError as quarantine_error:
            qWarning(
                "Could not quarantine invalid MeadowPy recovery data: "
                f"{quarantine_error}"
            )
            quarantined = None

        details = (
            f"The damaged data was preserved at:\n{quarantined}"
            if quarantined is not None
            else f"Recovery file:\n{self._store.path}"
        )
        QMessageBox.warning(
            parent,
            "Recovery Data Could Not Be Read",
            "MeadowPy found unsaved-work recovery data, but it was damaged or "
            f"unsupported.\n\n{details}\n\nDetails: {error}",
        )

    def discard_pending(self) -> None:
        """Discard the current recovery file while keeping monitoring active."""
        try:
            self._store.clear()
        except OSError as exc:
            qWarning(f"Could not remove MeadowPy recovery snapshot: {exc}")
        self._last_fingerprint = None
        self._resume_monitoring()

    def stop(self) -> None:
        """Stop recovery timers without altering the on-disk snapshot."""
        self._enabled = False
        self._snapshot_timer.stop()
        self._periodic_timer.stop()

    def stop_and_clear(self) -> None:
        """Stop monitoring and remove recovery data after a clean shutdown."""
        self.stop()
        self.discard_pending()

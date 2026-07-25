"""Utilities for safe QThread shutdown."""

from __future__ import annotations

from typing import Any


def is_thread_running(thread: Any) -> bool:
    """Return False when a QThread wrapper is already gone."""
    if thread is None:
        return False
    try:
        return bool(thread.isRunning())
    except RuntimeError:
        return False


def _wait_for_thread(thread: Any, timeout_ms: int | None) -> bool:
    try:
        if timeout_ms is None:
            return bool(thread.wait())
        return bool(thread.wait(timeout_ms))
    except TypeError:
        timeout = 4_294_967_295 if timeout_ms is None else timeout_ms
        return bool(thread.wait(timeout))
    except RuntimeError:
        return True


def stop_qthread(
    thread: Any,
    *,
    graceful_timeout_ms: int = 5_000,
    terminate_timeout_ms: int | None = None,
) -> bool:
    """Stop a QThread before the Python wrapper can be destroyed."""
    if not is_thread_running(thread):
        return True

    try:
        thread.quit()
    except RuntimeError:
        return True

    if _wait_for_thread(thread, graceful_timeout_ms):
        return True

    try:
        thread.terminate()
    except RuntimeError:
        return True

    if _wait_for_thread(thread, terminate_timeout_ms):
        return True

    return not is_thread_running(thread)

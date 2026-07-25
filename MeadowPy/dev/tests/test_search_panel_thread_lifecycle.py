from types import SimpleNamespace

from meadowpy.ui.search_panel import SearchPanel


def test_old_search_thread_finish_does_not_clear_current_thread():
    old_thread = object()
    old_worker = object()
    current_thread = object()
    current_worker = object()
    panel = SimpleNamespace(
        _thread=current_thread,
        _worker=current_worker,
        _old_threads=[old_thread],
        _old_workers=[old_worker],
    )
    panel._cleanup_thread = lambda thread, worker=None: SearchPanel._cleanup_thread(
        panel, thread, worker
    )

    SearchPanel._on_thread_finished(panel, old_thread, old_worker)

    assert panel._thread is current_thread
    assert panel._worker is current_worker
    assert panel._old_threads == []
    assert panel._old_workers == []

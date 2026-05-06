from meadowpy.core.qt_threads import is_thread_running, stop_qthread


class ThreadDouble:
    def __init__(self, running=True, wait_results=None):
        self.running = running
        self.wait_results = list(wait_results or [])
        self.quit_called = 0
        self.terminate_called = 0
        self.wait_calls = []

    def isRunning(self):
        return self.running

    def quit(self):
        self.quit_called += 1

    def terminate(self):
        self.terminate_called += 1
        self.running = False

    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        if self.wait_results:
            return self.wait_results.pop(0)
        return not self.running


class DeletedThreadDouble:
    def isRunning(self):
        raise RuntimeError("wrapped C/C++ object has been deleted")


class RuntimeWaitThreadDouble(ThreadDouble):
    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        raise RuntimeError("wrapped C/C++ object has been deleted")


class RuntimeQuitThreadDouble(ThreadDouble):
    def quit(self):
        self.quit_called += 1
        raise RuntimeError("wrapped C/C++ object has been deleted")


class RuntimeTerminateThreadDouble(ThreadDouble):
    def terminate(self):
        self.terminate_called += 1
        raise RuntimeError("wrapped C/C++ object has been deleted")


def test_is_thread_running_handles_missing_or_deleted_thread():
    assert is_thread_running(None) is False
    assert is_thread_running(DeletedThreadDouble()) is False


def test_stop_qthread_quits_and_waits_for_graceful_stop():
    thread = ThreadDouble(wait_results=[True])

    assert stop_qthread(thread, graceful_timeout_ms=250) is True

    assert thread.quit_called == 1
    assert thread.terminate_called == 0
    assert thread.wait_calls == [250]


def test_stop_qthread_terminates_after_graceful_timeout():
    thread = ThreadDouble(wait_results=[False, True])

    assert stop_qthread(thread, graceful_timeout_ms=250) is True

    assert thread.quit_called == 1
    assert thread.terminate_called == 1
    assert thread.wait_calls == [250, None]


def test_stop_qthread_returns_false_when_thread_refuses_to_stop():
    thread = ThreadDouble(wait_results=[False, False])
    thread.terminate = lambda: setattr(thread, "terminate_called", 1)

    assert stop_qthread(thread, graceful_timeout_ms=250) is False

    assert thread.quit_called == 1
    assert thread.terminate_called == 1
    assert thread.wait_calls == [250, None]


def test_stop_qthread_treats_deleted_thread_during_wait_as_stopped():
    thread = RuntimeWaitThreadDouble()

    assert stop_qthread(thread, graceful_timeout_ms=250) is True

    assert thread.quit_called == 1
    assert thread.wait_calls == [250]


def test_stop_qthread_treats_deleted_thread_during_quit_as_stopped():
    thread = RuntimeQuitThreadDouble()

    assert stop_qthread(thread, graceful_timeout_ms=250) is True

    assert thread.quit_called == 1


def test_stop_qthread_treats_deleted_thread_during_terminate_as_stopped():
    thread = RuntimeTerminateThreadDouble(wait_results=[False])

    assert stop_qthread(thread, graceful_timeout_ms=250) is True

    assert thread.quit_called == 1
    assert thread.terminate_called == 1

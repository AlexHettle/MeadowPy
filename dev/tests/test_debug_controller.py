from types import SimpleNamespace

import meadowpy.ui.controllers.debug_controller as debug_module
from meadowpy.ui.controllers.debug_controller import DebugController
from meadowpy.ui.controllers.window_context import MainWindowContext


class FakeEditor:
    def __init__(self, file_path, breakpoints):
        self.file_path = file_path
        self._breakpoints = breakpoints
        self.cleared = False

    def get_breakpoints(self):
        return self._breakpoints

    def clear_current_line(self):
        self.cleared = True


class FakeTabManager:
    def __init__(self, widgets):
        self.widgets = widgets

    def count(self):
        return len(self.widgets)

    def widget(self, index):
        return self.widgets[index]


def test_collect_all_breakpoints_converts_to_protocol_lines(monkeypatch):
    monkeypatch.setattr(debug_module, "CodeEditor", FakeEditor)
    tabs = FakeTabManager([
        FakeEditor("a.py", {0, 2}),
        FakeEditor("b.py", set()),
    ])
    window = SimpleNamespace(_tab_manager=tabs)
    controller = DebugController(MainWindowContext(window, None, None, None))

    assert controller._collect_all_breakpoints() == {"a.py": [1, 3]}


def test_clear_debug_markers_clears_every_editor(monkeypatch):
    monkeypatch.setattr(debug_module, "CodeEditor", FakeEditor)
    editors = [FakeEditor("a.py", set()), FakeEditor("b.py", set())]
    window = SimpleNamespace(_tab_manager=FakeTabManager(editors))
    controller = DebugController(MainWindowContext(window, None, None, None))

    controller._clear_debug_markers()

    assert [editor.cleared for editor in editors] == [True, True]

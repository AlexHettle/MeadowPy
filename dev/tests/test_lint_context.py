import sys
from pathlib import Path
import pytest

from meadowpy.constants import DEFAULT_SETTINGS
from meadowpy.core import lint_context as lint_context_module
from meadowpy.core.lint_context import (
    LintContextError,
    resolve_lint_context,
    resolve_lint_target_root,
)


class StubSettings:
    def __init__(self, **overrides):
        self.values = dict(DEFAULT_SETTINGS)
        self.values.update(overrides)

    def get(self, key, default=None):
        return self.values.get(key, default)


class StubInterpreterManager:
    def __init__(self, interpreter="selected-python"):
        self.interpreter = interpreter
        self.calls = []

    def get_interpreter(self, settings, file_path=None):
        self.calls.append((settings, file_path))
        return self.interpreter


def trusted_project(tmp_path, **overrides):
    project = tmp_path / "project"
    source = project / "src" / "main.py"
    source.parent.mkdir(parents=True)
    source.write_text("print('hello')", encoding="utf-8")
    settings = StubSettings(
        **{"security.trusted_lint_roots": [str(project)], **overrides}
    )
    return project, source, settings


def test_new_lint_settings_have_safe_defaults():
    assert DEFAULT_SETTINGS["editor.lint_while_typing"] is True
    assert DEFAULT_SETTINGS["editor.lint_interpreter_mode"] == "selected"
    assert DEFAULT_SETTINGS["editor.lint_interpreter_path"] == ""
    assert DEFAULT_SETTINGS["editor.lint_working_directory"] == "project"
    assert DEFAULT_SETTINGS["editor.lint_flake8_config_mode"] == "defaults"
    assert DEFAULT_SETTINGS["editor.lint_flake8_config_path"] == ""
    assert DEFAULT_SETTINGS["editor.lint_flake8_timeout_seconds"] == 10
    assert DEFAULT_SETTINGS["editor.lint_pylint_config_mode"] == "defaults"
    assert DEFAULT_SETTINGS["editor.lint_pylint_config_path"] == ""
    assert DEFAULT_SETTINGS["editor.lint_pylint_timeout_seconds"] == 15
    assert DEFAULT_SETTINGS["security.trusted_lint_roots"] == []


def test_trusted_project_uses_selected_interpreter_and_project_cwd(tmp_path):
    project, source, settings = trusted_project(tmp_path)
    manager = StubInterpreterManager()

    context = resolve_lint_context(
        settings, manager, "flake8", str(source), str(project)
    )

    assert context.interpreter == "selected-python"
    assert context.cwd == str(project.resolve())
    assert context.display_name == str(Path("src") / "main.py")
    assert context.config_mode == "defaults"
    assert context.config_path is None
    assert context.isolated is True
    assert context.trusted is True
    assert context.timeout_seconds == 10
    assert manager.calls == [(settings, str(source))]


def test_file_working_directory_and_custom_interpreter(tmp_path):
    custom = tmp_path / "python.exe"
    custom.write_text("", encoding="utf-8")
    project, source, settings = trusted_project(
        tmp_path,
        **{
            "editor.lint_interpreter_mode": "custom",
            "editor.lint_interpreter_path": str(custom),
            "editor.lint_working_directory": "file",
        },
    )

    context = resolve_lint_context(
        settings, StubInterpreterManager(), "pylint", str(source), str(project)
    )

    assert context.interpreter == str(custom.resolve())
    assert context.cwd == str(source.parent.resolve())
    assert context.display_name == "main.py"
    assert context.timeout_seconds == 15


def test_meadowpy_interpreter_mode_uses_running_python(tmp_path):
    project, source, settings = trusted_project(
        tmp_path, **{"editor.lint_interpreter_mode": "meadowpy"}
    )

    context = resolve_lint_context(
        settings, StubInterpreterManager(), "flake8", str(source), str(project)
    )

    assert context.interpreter == sys.executable


def test_untrusted_project_forces_isolated_safe_context(tmp_path):
    project = tmp_path / "untrusted"
    project.mkdir()
    source = project / "main.py"
    source.write_text("", encoding="utf-8")
    custom = project / "python.exe"
    custom.write_text("", encoding="utf-8")
    settings = StubSettings(
        **{
            "editor.lint_interpreter_mode": "custom",
            "editor.lint_interpreter_path": str(custom),
            "editor.lint_flake8_config_mode": "explicit",
            "editor.lint_flake8_config_path": str(project / ".flake8"),
        }
    )
    manager = StubInterpreterManager()

    context = resolve_lint_context(
        settings, manager, "flake8", str(source), str(project)
    )

    assert context.interpreter == sys.executable
    assert context.cwd == str(Path(sys.executable).resolve().parent)
    assert context.config_mode == "defaults"
    assert context.config_path is None
    assert context.isolated is True
    assert context.trusted is False
    assert manager.calls == []


def test_untitled_file_uses_trusted_project_root(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    settings = StubSettings(
        **{"security.trusted_lint_roots": [str(project)]}
    )

    context = resolve_lint_context(
        settings, StubInterpreterManager(), "flake8", None, str(project)
    )

    assert context.cwd == str(project.resolve())
    assert context.display_name == "untitled.py"
    assert context.trusted is True


def test_file_outside_project_is_not_covered_by_project_trust(tmp_path):
    project = tmp_path / "project"
    outside = tmp_path / "outside" / "main.py"
    project.mkdir()
    outside.parent.mkdir()
    outside.write_text("", encoding="utf-8")
    settings = StubSettings(
        **{"security.trusted_lint_roots": [str(project)]}
    )

    context = resolve_lint_context(
        settings, StubInterpreterManager(), "flake8", str(outside), str(project)
    )

    assert context.trusted is False
    assert context.cwd != str(project.resolve())


def test_target_root_prefers_nearest_project_marker_inside_explorer_root(
    tmp_path,
):
    explorer_root = tmp_path / "Documents"
    project = explorer_root / "nested-project"
    source = project / "src" / "main.py"
    source.parent.mkdir(parents=True)
    (project / ".git").mkdir()
    source.write_text("print('hello')\n", encoding="utf-8")

    target = resolve_lint_target_root(str(source), str(explorer_root))

    assert target == str(project.resolve())


def test_saved_file_without_explorer_uses_nearest_marked_project(tmp_path):
    source = tmp_path / "standalone" / "main.py"
    source.parent.mkdir()
    source.write_text("print('hello')\n", encoding="utf-8")

    target = resolve_lint_target_root(str(source), None)

    repository_root = Path(__file__).resolve().parents[2]
    assert target == str(repository_root)


def test_trust_uses_path_boundaries_not_string_prefixes(tmp_path):
    trusted = tmp_path / "app"
    lookalike = tmp_path / "application"
    trusted.mkdir()
    lookalike.mkdir()
    source = lookalike / "main.py"
    source.write_text("", encoding="utf-8")
    settings = StubSettings(
        **{"security.trusted_lint_roots": [str(trusted)]}
    )

    context = resolve_lint_context(
        settings, StubInterpreterManager(), "flake8", str(source), str(lookalike)
    )

    assert context.trusted is False


def test_auto_discovers_nearest_relevant_flake8_config(tmp_path):
    project, source, settings = trusted_project(
        tmp_path, **{"editor.lint_flake8_config_mode": "auto"}
    )
    root_config = project / ".flake8"
    root_config.write_text("[flake8]\nmax-line-length = 100\n", encoding="utf-8")
    nearer_config = source.parent / "setup.cfg"
    nearer_config.write_text("[flake8:local-plugins]\n", encoding="utf-8")

    context = resolve_lint_context(
        settings, StubInterpreterManager(), "flake8", str(source), str(project)
    )

    assert context.config_mode == "auto"
    assert context.config_path == str(nearer_config.resolve())
    assert context.isolated is False


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("pylintrc", "[MAIN]\nignore = CVS\n"),
        ("pylintrc.toml", "[tool.pylint.main]\nignore = ['CVS']\n"),
        (".pylintrc", "[MESSAGES CONTROL]\ndisable = missing-docstring\n"),
        (".pylintrc.toml", "[tool.pylint.messages_control]\ndisable = []\n"),
        ("pyproject.toml", "[tool.pylint]\n"),
        ("setup.cfg", "[pylint.main]\nignore=CVS\n"),
        ("tox.ini", "[pylint]\n"),
    ],
)
def test_auto_discovers_supported_pylint_configs(tmp_path, filename, content):
    project, source, settings = trusted_project(
        tmp_path, **{"editor.lint_pylint_config_mode": "auto"}
    )
    config = project / filename
    config.write_text(content, encoding="utf-8")

    context = resolve_lint_context(
        settings, StubInterpreterManager(), "pylint", str(source), str(project)
    )

    assert context.config_path == str(config.resolve())
    assert context.isolated is False


def test_empty_nearby_pylintrc_stops_parent_config_inheritance(tmp_path):
    project, source, settings = trusted_project(
        tmp_path, **{"editor.lint_pylint_config_mode": "auto"}
    )
    (project / "pylintrc").write_text(
        "[MAIN]\nload-plugins=project_plugin\n", encoding="utf-8"
    )
    nearby = source.parent / ".pylintrc"
    nearby.write_text("# intentionally empty\n", encoding="utf-8")

    context = resolve_lint_context(
        settings, StubInterpreterManager(), "pylint", str(source), str(project)
    )

    assert context.config_path == str(nearby.resolve())
    assert context.isolated is False


def test_auto_skips_irrelevant_configs_and_does_not_walk_above_root(tmp_path):
    project, source, settings = trusted_project(
        tmp_path, **{"editor.lint_flake8_config_mode": "auto"}
    )
    (source.parent / "setup.cfg").write_text(
        "[metadata]\nname = example\n", encoding="utf-8"
    )
    above = project.parent / ".flake8"
    above.write_text("[flake8]\n", encoding="utf-8")

    context = resolve_lint_context(
        settings, StubInterpreterManager(), "flake8", str(source), str(project)
    )

    assert context.config_path is None
    assert context.isolated is True


def test_config_discovery_only_reads_text_and_never_imports_it(tmp_path):
    project, source, settings = trusted_project(
        tmp_path, **{"editor.lint_flake8_config_mode": "auto"}
    )
    marker = tmp_path / "executed"
    config = project / ".flake8"
    config.write_text(
        "[flake8:local-plugins]\n"
        "extension = X = package.module:Checker\n"
        f"# __import__('pathlib').Path({str(marker)!r}).touch()\n",
        encoding="utf-8",
    )

    context = resolve_lint_context(
        settings, StubInterpreterManager(), "flake8", str(source), str(project)
    )

    assert context.config_path == str(config.resolve())
    assert marker.exists() is False


def test_explicit_config_must_exist_and_be_inside_trusted_root(tmp_path):
    project, source, settings = trusted_project(
        tmp_path,
        **{
            "editor.lint_flake8_config_mode": "explicit",
            "editor.lint_flake8_config_path": str(tmp_path / "outside.cfg"),
        },
    )
    outside = tmp_path / "outside.cfg"
    outside.write_text("[flake8]\n", encoding="utf-8")

    with pytest.raises(LintContextError, match="inside a trusted project root"):
        resolve_lint_context(
            settings, StubInterpreterManager(), "flake8", str(source), str(project)
        )

    settings.values["editor.lint_flake8_config_path"] = str(project / "missing")
    with pytest.raises(LintContextError, match="does not exist"):
        resolve_lint_context(
            settings, StubInterpreterManager(), "flake8", str(source), str(project)
        )


def test_explicit_config_is_resolved_for_trusted_project(tmp_path):
    project, source, settings = trusted_project(tmp_path)
    config = project / "quality" / "flake8.ini"
    config.parent.mkdir()
    config.write_text("[flake8]\n", encoding="utf-8")
    settings.values.update(
        {
            "editor.lint_flake8_config_mode": "explicit",
            "editor.lint_flake8_config_path": str(config),
        }
    )

    context = resolve_lint_context(
        settings, StubInterpreterManager(), "flake8", str(source), str(project)
    )

    assert context.config_mode == "explicit"
    assert context.config_path == str(config.resolve())
    assert context.isolated is False


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"editor.lint_interpreter_mode": "invalid"}, "interpreter mode"),
        ({"editor.lint_working_directory": "invalid"}, "working directory"),
        ({"editor.lint_flake8_config_mode": "invalid"}, "configuration mode"),
        ({"editor.lint_flake8_timeout_seconds": 0}, "timeout"),
        ({"editor.lint_flake8_timeout_seconds": 121}, "timeout"),
        ({"editor.lint_flake8_timeout_seconds": 1.5}, "whole number"),
    ],
)
def test_invalid_trusted_settings_raise_actionable_errors(
    tmp_path, overrides, message
):
    project, source, settings = trusted_project(tmp_path, **overrides)

    with pytest.raises(LintContextError, match=message):
        resolve_lint_context(
            settings, StubInterpreterManager(), "flake8", str(source), str(project)
        )


def test_invalid_custom_interpreter_has_actionable_error(tmp_path):
    project, source, settings = trusted_project(
        tmp_path,
        **{
            "editor.lint_interpreter_mode": "custom",
            "editor.lint_interpreter_path": str(tmp_path / "missing-python"),
        },
    )

    with pytest.raises(LintContextError, match="does not exist"):
        resolve_lint_context(
            settings, StubInterpreterManager(), "pylint", str(source), str(project)
        )


def test_unsupported_linter_has_actionable_error():
    with pytest.raises(LintContextError, match="Choose Flake8 or Pylint"):
        resolve_lint_context(
            StubSettings(), StubInterpreterManager(), "ruff", None, None
        )


def test_setting_reader_supports_legacy_getters_and_rejects_missing_getter():
    class LegacySettings:
        def get(self, key):
            return None if key == "missing" else "configured"

    assert lint_context_module._get_setting(LegacySettings(), "value", "fallback") == "configured"
    assert lint_context_module._get_setting(LegacySettings(), "missing", "fallback") == "fallback"
    with pytest.raises(LintContextError, match="settings are unavailable"):
        lint_context_module._get_setting(object(), "value", "fallback")


def test_path_helpers_cover_invalid_boundaries_and_files_without_projects(
    monkeypatch, tmp_path
):
    source = tmp_path / "plain" / "main.py"
    source.parent.mkdir()
    source.write_text("", encoding="utf-8")

    monkeypatch.setattr(lint_context_module, "_nearest_project_root", lambda *args: None)
    assert lint_context_module._effective_root(source, None) == source.parent
    assert lint_context_module._canonical_directory(str(source)) is None
    assert lint_context_module._canonical_directory(str(tmp_path / "missing")) is None
    assert lint_context_module._matching_trusted_root(
        StubSettings(**{"security.trusted_lint_roots": "not-a-list"}), source.parent
    ) is None
    assert lint_context_module._matching_trusted_root(
        StubSettings(**{"security.trusted_lint_roots": [None, "", tmp_path / "missing"]}),
        source.parent,
    ) is None

    monkeypatch.setattr(
        lint_context_module.os.path,
        "commonpath",
        lambda paths: (_ for _ in ()).throw(ValueError("different drives")),
    )
    assert lint_context_module._contains(tmp_path, source) is False


def test_runtime_directory_falls_back_when_executable_path_cannot_resolve(monkeypatch):
    original_path = lint_context_module.Path

    class FailingExecutablePath:
        def __init__(self, value):
            if value == "broken-python":
                raise OSError("unavailable")
            self._path = original_path(value)

        def resolve(self, *args, **kwargs):
            return self._path.resolve(*args, **kwargs)

    monkeypatch.setattr(lint_context_module.sys, "executable", "broken-python")
    monkeypatch.setattr(lint_context_module, "Path", FailingExecutablePath)
    assert lint_context_module._safe_runtime_directory() == original_path(
        lint_context_module.__file__
    ).resolve().parent


@pytest.mark.parametrize(
    ("manager", "message"),
    [
        (StubInterpreterManager(interpreter=None), "No selected Python interpreter"),
        (
            type(
                "BrokenManager",
                (),
                {"get_interpreter": lambda self, *args: (_ for _ in ()).throw(OSError("boom"))},
            )(),
            "Could not resolve the selected Python interpreter",
        ),
    ],
)
def test_selected_interpreter_failures_are_wrapped(tmp_path, manager, message):
    project, source, settings = trusted_project(tmp_path)
    with pytest.raises(LintContextError, match=message):
        resolve_lint_context(settings, manager, "flake8", str(source), str(project))


def test_custom_interpreter_must_be_configured_as_a_file(tmp_path):
    project, source, settings = trusted_project(
        tmp_path,
        **{
            "editor.lint_interpreter_mode": "custom",
            "editor.lint_interpreter_path": None,
        },
    )
    with pytest.raises(LintContextError, match="Choose an existing Python executable"):
        resolve_lint_context(
            settings, StubInterpreterManager(), "flake8", str(source), str(project)
        )

    settings.values["editor.lint_interpreter_path"] = str(project)
    with pytest.raises(LintContextError, match="is not a file"):
        resolve_lint_context(
            settings, StubInterpreterManager(), "flake8", str(source), str(project)
        )


@pytest.mark.parametrize("timeout", [True, "not-a-number"])
def test_non_numeric_timeouts_are_rejected(tmp_path, timeout):
    project, source, settings = trusted_project(
        tmp_path, **{"editor.lint_flake8_timeout_seconds": timeout}
    )
    with pytest.raises(LintContextError, match="timeout"):
        resolve_lint_context(
            settings, StubInterpreterManager(), "flake8", str(source), str(project)
        )


def test_explicit_config_rejects_empty_relative_and_directory_paths(tmp_path):
    project, source, settings = trusted_project(
        tmp_path, **{"editor.lint_flake8_config_mode": "explicit"}
    )
    for configured, message in [
        (None, "Choose an existing"),
        ("relative.ini", "must be absolute"),
        (str(project), "is not a file"),
    ]:
        settings.values["editor.lint_flake8_config_path"] = configured
        with pytest.raises(LintContextError, match=message):
            resolve_lint_context(
                settings,
                StubInterpreterManager(),
                "flake8",
                str(source),
                str(project),
            )


def test_config_helpers_reject_outside_oversized_and_unreadable_candidates(
    monkeypatch, tmp_path
):
    boundary = tmp_path / "project"
    boundary.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    config = boundary / ".flake8"
    config.write_text("[flake8]\n", encoding="utf-8")

    assert lint_context_module._discover_config("flake8", outside, boundary) is None
    assert lint_context_module._is_relevant_config("flake8", boundary, boundary) is False

    monkeypatch.setattr(lint_context_module, "MAX_CONFIG_BYTES", 1)
    assert lint_context_module._is_relevant_config("flake8", config, boundary) is False
    monkeypatch.setattr(lint_context_module, "MAX_CONFIG_BYTES", 1024)
    monkeypatch.setattr(
        lint_context_module.Path,
        "read_text",
        lambda self, **kwargs: (_ for _ in ()).throw(UnicodeError("bad text")),
    )
    assert lint_context_module._is_relevant_config("flake8", config, boundary) is False


def test_pylint_section_matching_and_display_name_fallback(monkeypatch, tmp_path):
    assert lint_context_module._has_pylint_section("pylintrc", {"messages_control"})
    assert lint_context_module._has_pylint_section("custom.cfg", {"tool.pylint.main"})

    source = tmp_path / "main.py"
    source.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        lint_context_module.Path,
        "relative_to",
        lambda self, other: (_ for _ in ()).throw(ValueError("not relative")),
    )
    assert lint_context_module._display_name(source, tmp_path) == str(source)

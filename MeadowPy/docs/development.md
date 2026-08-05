# Development Guide

This guide is for people working on MeadowPy itself.

Related docs:

- [Testing](testing.md)
- [Architecture](architecture.md)
- [Release Process](release-process.md)
- [Contributing](../../.github/CONTRIBUTING.md)

## Supported Development Environment

MeadowPy is currently developed and set up for Windows.

Expected tools:

- Windows 10 or Windows 11.
- Python 3.11 or newer.
- A terminal that can run `.bat` files.
- Internet access for dependency installation.

The app may contain some cross-platform helper logic, such as Unix virtual
environment detection, but the setup and documented user workflow are Windows
first.

## Repository Layout

```text
.
|-- .agents/
|-- .git/
|-- .github/
|   |-- README.md
|   |-- CONTRIBUTING.md
|   |-- SECURITY.md
|-- .gitignore
|-- MeadowPy.lnk
|-- setup.bat
|-- MeadowPy/
|   |-- LICENSE
|   |-- meadowpy/
|   |   |-- app.py
|   |   |-- __main__.py
|   |   |-- constants.py
|   |   |-- requirements.txt
|   |   |-- core/
|   |   |-- editor/
|   |   |-- resources/
|   |   |-- ui/
|   |-- dev/
|   |   |-- setup-dev.bat
|   |   |-- Run Tests.bat
|   |   |-- pytest.ini
|   |   |-- requirements-dev.txt
|   |   |-- tests/
|   |-- docs/
|   |-- Run MeadowPy.bat
```

The `.agents/` folder is managed by the local development workspace and may be
absent in other checkouts.

The repository's runnable application is contained in `MeadowPy/`. All paths
below are relative to that application directory.

Important areas:

- `meadowpy/__main__.py`: module entry point for `python -m meadowpy`.
- `meadowpy/app.py`: creates `QApplication`, loads settings, shows splash,
  builds the main window, and enters the event loop.
- `meadowpy/ui/main_window.py`: constructs the main window, panels, managers,
  actions, menus, toolbar, status bar, and controllers.
- `meadowpy/ui/controllers/`: focused controller classes that own main window
  behavior.
- `meadowpy/core/`: non-visual services such as settings, file I/O, process
  running, debugging, linting, Ollama, interpreter discovery, and REPL.
- `meadowpy/editor/`: code editor widget, editor settings, completion, smart
  indent, themes, fonts, and auto-close behavior.
- `meadowpy/ui/`: widgets, panels, dialogs, menu and toolbar builders.
- `meadowpy/resources/`: icons, stylesheets, fonts, screenshots, example
  catalog, example files, and resource loading helpers.
- `dev/tests/`: automated tests.

## Runtime Files

MeadowPy writes user-specific runtime files under:

```text
%USERPROFILE%\.meadowpy
```

Common files:

| Path | Purpose |
| --- | --- |
| `%USERPROFILE%\.meadowpy\settings.json` | Saved settings |
| `%USERPROFILE%\.meadowpy\meadowpy.log` | Startup, Qt, crash, and shutdown logs |
| `%USERPROFILE%\.meadowpy\tmp` | Temporary files for Run Selection / Line |

Tests should avoid relying on the user's real runtime state.

## Development Setup

From the `MeadowPy` application directory, run:

```bat
dev\setup-dev.bat
```

This calls:

```bat
..\setup.bat --dev
```

Development setup installs:

- App dependencies from `meadowpy/requirements.txt`.
- Test dependencies from `dev/requirements-dev.txt`.

The development dependency file currently adds:

- `pytest`
- `pytest-cov`

## Launch From Source

After setup, launch MeadowPy from the `MeadowPy` application directory:

```bat
.venv\Scripts\python.exe -m meadowpy
```

This runs `meadowpy/__main__.py`, which:

1. Enables crash logging.
2. Sets the Windows app ID when possible.
3. Imports `MeadowPyApp`.
4. Creates and runs the application.

You can also use:

```text
Run MeadowPy.bat
```

## App Startup Flow

At a high level:

1. `meadowpy/__main__.py` enables crash logging and Windows app identity.
2. `MeadowPyApp` creates the `QApplication`.
3. App font and icon are loaded.
4. Splash screen is shown.
5. Settings are loaded from `%USERPROFILE%\.meadowpy\settings.json`.
6. Stylesheet is applied.
7. `RecentFilesManager` and `FileManager` are created.
8. `MainWindow` is created.
9. Startup files passed on the command line are opened.
10. The main window is shown and the event loop starts.

See [Architecture](architecture.md) for a deeper map.

## Main Window Controllers

`MainWindow` delegates behavior to controller classes in
`meadowpy/ui/controllers/`.

Current controllers:

| Controller | Main responsibility |
| --- | --- |
| `WorkspaceController` | Files, tabs, welcome screen, preferences, layout, explorer, search navigation |
| `CodeQualityController` | Symbol outline and linting |
| `ExecutionController` | Run file, run selection, process output, interpreter selection, REPL |
| `DebugController` | Debug session lifecycle, breakpoints, stepping, debug panels |
| `AIAssistantController` | Ollama connection, model selection, AI prompts, chat actions |

`MainWindow.__getattr__` resolves moved behavior on these controllers so menu
and toolbar callbacks can still call methods through the main window.

When adding behavior, prefer placing it in the controller that already owns the
related workflow.

## Settings

Settings are defined in:

```text
meadowpy/constants.py
```

and managed by:

```text
meadowpy/core/settings.py
```

`Settings.get()` reads from saved data first, then falls back to
`DEFAULT_SETTINGS`.

`Settings.set()` updates a key and emits `settings_changed`.

`Settings.save()` writes merged defaults and current values to:

```text
%USERPROFILE%\.meadowpy\settings.json
```

When adding a new user preference:

1. Add a default in `DEFAULT_SETTINGS`.
2. Add UI in `PreferencesDialog` if the user should control it.
3. Handle `settings_changed` if live updates are needed.
4. Add or update tests.
5. Document the setting if it affects user workflows.

## Adding UI Features

Before adding a UI feature:

1. Find the existing owner module.
2. Prefer extending an existing panel, dialog, controller, or builder.
3. Keep long-running work off the UI thread.
4. Use Qt signals to communicate between workers and UI widgets.
5. Update tests for controller behavior and widget state.
6. Update user documentation when the workflow changes.

Common UI owners:

| Area | Files |
| --- | --- |
| Menus | `meadowpy/ui/menu_bar.py` |
| Toolbar | `meadowpy/ui/tool_bar.py` |
| Status bar | `meadowpy/ui/status_bar.py` |
| Preferences | `meadowpy/ui/dialogs/preferences_dialog.py` |
| File explorer | `meadowpy/ui/file_explorer.py` |
| Output panel | `meadowpy/ui/output_panel.py` |
| Problems panel | `meadowpy/ui/problems_panel.py` |
| Search panel | `meadowpy/ui/search_panel.py` |
| Terminal panel | `meadowpy/ui/terminal_panel.py` |
| AI chat | `meadowpy/ui/ai_chat_panel.py`, `meadowpy/ui/ai_chat_widgets.py` |
| Debug panels | `meadowpy/ui/variable_inspector.py`, `call_stack_panel.py`, `watch_panel.py` |

## Adding Menu Actions Or Shortcuts

Menu actions are created in:

```text
meadowpy/ui/menu_bar.py
```

Toolbar actions are created in:

```text
meadowpy/ui/tool_bar.py
```

The in-app keyboard shortcut editor is driven by shared shortcut metadata in:

```text
meadowpy/core/shortcuts.py
```

When adding a shortcut:

1. Add the shortcut definition to `meadowpy/core/shortcuts.py`.
2. Register the related `QAction` with `MainWindow.register_shortcut_action`
   or `MenuBarBuilder._set_shortcut`.
3. For editor-owned shortcuts, read the active key with
   `get_shortcut(settings, shortcut_id)`.
4. Update [Shortcuts](shortcuts.md).
5. Add or update tests if the shortcut affects behavior.

## Adding Preferences

`PreferencesDialog` has six pages:

- Editor
- Appearance
- Linting
- Execution
- General
- AI

Preferences are staged before being applied. The dialog stores pending changes
in `_pending_changes`, then writes them to `Settings` on Apply or OK.

When a preference should update open editors immediately, handle it in
`WorkspaceController._on_settings_changed()`.

## Adding Quick Start Templates

Welcome-screen Quick Start templates are defined in:

```text
meadowpy/ui/welcome_templates.py
```

Every template must have one or more execution scenarios in:

```text
dev/tests/quick_start_expectations.py
```

Scenarios provide scripted input and verify meaningful output, generated
files, error recovery, or other observable behavior. Run the focused suite
after adding or changing a template:

```bat
.venv\Scripts\python.exe -m pytest -c dev\pytest.ini --no-cov dev\tests\test_quick_start_templates.py -q
```

The suite validates template metadata, compiles every embedded code string,
and executes each scenario in an isolated temporary directory. Turtle Graphics
uses a headless turtle stub so CI never opens or waits on a real window.

## Adding Example Library Entries

The example library is driven by:

```text
meadowpy/resources/examples/catalog.json
```

Example files live under:

```text
meadowpy/resources/examples/
```

To add an example:

1. Create a readable `.py` example file in the appropriate category folder.
2. Add an entry to `catalog.json`.
3. Add its execution contract to
   `dev/tests/example_expectations.py`, including scripted input and expected
   output or files.
4. Keep example code beginner-friendly and well-commented.
5. Run the focused example tests:

   ```bat
   .venv\Scripts\python.exe -m pytest -c dev\pytest.ini --no-cov dev\tests\test_example_library_execution.py -q
   ```

6. Run the full test suite.
7. If the category or behavior changes, update [User Guide](user-guide.md).

The execution suite compiles every cataloged source file and runs each example
in an isolated temporary directory. It does not permit missing contracts,
unexpected files, uncontrolled network access, tracebacks, or nonzero exits.

## Adding Resources

Resources live under:

```text
meadowpy/resources/
```

Common resource areas:

- `icons/`
- `styles/`
- `fonts/`
- `Images/`
- `examples/`

Use the resource helpers instead of hardcoding paths:

- `meadowpy/resources/resource_loader.py`
- `meadowpy/resources/resource_paths.py`
- `meadowpy/resources/resource_icons.py`
- `meadowpy/resources/stylesheet_loader.py`

## Running Tests

Use:

```bat
dev\Run Tests.bat
```

For more testing details, see [Testing](testing.md).

## Coding Expectations

General expectations:

- Keep behavior near the module that already owns it.
- Prefer Qt signals over direct cross-thread UI updates.
- Avoid blocking the UI thread with I/O, HTTP, subprocess, lint, search, or AI
  work.
- Keep user-facing text beginner-friendly.
- Keep tests focused on behavior.
- Update docs when user workflows, setup, shortcuts, or architecture change.

## Before Calling Work Finished

For most changes:

1. Run focused tests while developing.
2. Run the full test suite before finishing.
3. Launch the app for a smoke test if UI behavior changed.
4. Update relevant docs.
5. Check for unintended changes before committing.

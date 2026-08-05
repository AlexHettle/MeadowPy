# Testing

This guide explains how to run and understand MeadowPy's automated tests.

Related docs:

- [Development Guide](development.md)
- [Architecture](architecture.md)
- [Contributing](../../.github/CONTRIBUTING.md)

## Test Location

Tests live under:

```text
dev\tests
```

Test configuration lives in:

```text
dev\pytest.ini
```

Development test dependencies live in:

```text
dev\requirements-dev.txt
```

## Development Setup

Before running tests, install development dependencies:

```bat
dev\setup-dev.bat
```

or:

```bat
..\setup.bat --dev
```

This installs the normal app dependencies plus `pytest` and `pytest-cov`.

## Run All Tests

From the `MeadowPy` application directory:

```bat
dev\Run Tests.bat
```

The test runner:

1. Verifies `.venv\Scripts\python.exe` exists.
2. Verifies `pytest` is installed.
3. Sets `QT_QPA_PLATFORM=offscreen`.
4. Runs pytest with `dev\pytest.ini`.
5. Writes HTML coverage to `dev\htmlcov\index.html`.
6. Writes XML coverage to `dev\coverage.xml`.
7. Pauses at the end unless `MEADOWPY_NO_PAUSE` is set.

## Run Without Pause

In Command Prompt:

```bat
set MEADOWPY_NO_PAUSE=1
dev\Run Tests.bat
```

In PowerShell:

```powershell
$env:MEADOWPY_NO_PAUSE = "1"
& "dev\Run Tests.bat"
```

## Run A Targeted Test

The test runner forwards extra arguments to pytest.

Example:

```bat
dev\Run Tests.bat dev\tests\test_settings.py -q
```

Because coverage is measured against the full `meadowpy` package, a tiny
targeted run can pass its tests but fail the overall coverage threshold.

For quick focused checks, disable coverage:

```bat
.venv\Scripts\python.exe -m pytest -c dev\pytest.ini --no-cov dev\tests\test_settings.py -q
```

Run the full suite again before finishing work.

## Pytest Configuration

`dev\pytest.ini` currently sets:

```ini
[pytest]
testpaths = tests
pythonpath = .. .
addopts = -ra --strict-markers -p no:cacheprovider --cov=meadowpy --cov-config=dev/.coveragerc --cov-report=term-missing --cov-report=xml:dev/coverage.xml
```

Because the config file is under `dev`, `testpaths = tests` resolves to
`dev\tests` when pytest is run with:

```bat
.venv\Scripts\python.exe -m pytest -c dev\pytest.ini
```

## Coverage Outputs

The normal test runner adds:

```bat
--cov-report=html:dev\htmlcov
```

Coverage outputs:

| Output | Path |
| --- | --- |
| Terminal missing-lines report | Console output |
| HTML report | `dev\htmlcov\index.html` |
| XML report | `dev\coverage.xml` |

Generated coverage files should not be treated as source documentation.

## UI Tests

MeadowPy is a PyQt6 application. Many tests exercise widgets and controllers
without showing real windows.

The test runner sets:

```text
QT_QPA_PLATFORM=offscreen
```

That allows Qt widget tests to run in a headless test environment.

When writing UI tests:

- Use existing fixtures from `dev\tests\conftest.py`.
- Reuse helpers from `dev\tests\helpers.py`.
- Prefer focused widget/controller assertions over broad end-to-end tests.
- Avoid depending on the user's real settings file.
- Avoid leaving QThreads, QProcesses, or timers running after the test.

## Current Test Areas

The suite includes coverage for:

- App startup and entry point behavior.
- Settings.
- Recent files.
- File manager behavior.
- Editor widget behavior.
- Smart indentation.
- Auto-close behavior.
- Tab manager.
- Main window wiring.
- Workspace controller.
- Execution controller.
- Process runner.
- REPL manager.
- Debug manager and debug helper.
- Debug controller.
- Linter.
- Code quality controller.
- Error explainer.
- AI assistant controller.
- Ollama client and setup dialog.
- Output panel.
- Terminal panel.
- Search panel lifecycle.
- UI panels and dialogs.
- Resource loading.
- Quick Start template syntax and isolated execution behavior.
- Example-library syntax and isolated execution behavior.
- Startup helpers.
- Qt thread helpers.

## Example Library Tests

Every example listed in `meadowpy/resources/examples/catalog.json` has an
execution contract in `dev/tests/example_expectations.py`. The tests compile
the source, execute it with the active test interpreter, provide scripted
input where needed, and verify output and generated files.

Run only these contracts with:

```bat
.venv\Scripts\python.exe -m pytest -c dev\pytest.ini --no-cov dev\tests\test_example_library_execution.py -q
```

The HTTP example uses a local test server. The suite does not require access
to a public API.

## Quick Start Template Tests

Every template in `meadowpy/ui/welcome_templates.py` has one or more execution
scenarios in `dev/tests/quick_start_expectations.py`. The suite validates the
template fields, compiles each embedded code string, supplies scripted input,
and checks output and file side effects in an isolated temporary directory.

Run only the Quick Start contracts with:

```bat
.venv\Scripts\python.exe -m pytest -c dev\pytest.ini --no-cov dev\tests\test_quick_start_templates.py -q
```

Random templates use invariant-based assertions. Turtle Graphics uses a fake
turtle module that records drawing calls instead of opening a GUI.

## When To Add Tests

Add or update tests when a change:

- Changes user-visible behavior.
- Fixes a bug.
- Adds a setting.
- Changes file I/O.
- Changes startup or shutdown behavior.
- Changes run, debug, lint, search, AI, or REPL behavior.
- Touches shared helper logic.
- Changes error handling.

Small visual-only changes may not need new automated tests, but should still be
smoke-tested in the app.

## Common Test Failures

### Missing Development Dependencies

Symptom:

```text
Test dependencies are missing.
```

Fix:

```bat
dev\setup-dev.bat
```

### Qt Platform Plugin Issues

Symptom:

- Qt fails before tests run.
- Tests work locally only when a display is available.

Fix:

Use the test runner, which sets:

```text
QT_QPA_PLATFORM=offscreen
```

### Coverage Fails On Targeted Runs

Symptom:

- A targeted file passes.
- The command still fails because total package coverage is too low.

Fix:

Use `--no-cov` for targeted development runs, then run the full suite before
finishing.

### Hanging Tests

Likely causes:

- A `QThread` was not stopped.
- A `QProcess` was not killed or allowed to finish.
- A modal dialog was opened without being handled.
- A timer or worker is still active.

Fix:

- Use existing shutdown helpers and patterns.
- Stop worker threads explicitly.
- Prefer fake workers for controller tests.
- Keep tests narrow.

## Manual Smoke Tests

For UI changes, run a short manual smoke test after automated tests:

1. Launch MeadowPy:

```bat
.venv\Scripts\python.exe -m meadowpy
```

2. Open or create a Python file.
3. Run it with `F5`.
4. Try `input()` through the Output panel.
5. Open the Terminal panel and run a simple command such as `dir`.
6. Toggle a breakpoint and start debug with `F6`.
7. Open Preferences if settings changed.
8. Open AI setup if AI behavior changed.
9. Close MeadowPy and confirm shutdown is clean.

Use the runtime log if startup or shutdown behaves strangely:

```text
%USERPROFILE%\.meadowpy\meadowpy.log
```

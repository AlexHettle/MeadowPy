# Contributing To MeadowPy

Thanks for helping improve MeadowPy. The project is designed to be friendly to
beginners, so contributions should preserve that spirit in both code and user
experience.

Useful docs:

- [Development Guide](../MeadowPy/docs/development.md)
- [Testing](../MeadowPy/docs/testing.md)
- [Architecture](../MeadowPy/docs/architecture.md)
- [User Guide](../MeadowPy/docs/user-guide.md)
- [Troubleshooting](../MeadowPy/docs/troubleshooting.md)
- [Security](SECURITY.md)

## Ways To Contribute

Good contribution areas include:

- Bug reports.
- Reproduction steps for confusing behavior.
- Beginner-focused feature ideas.
- Documentation improvements.
- Example library additions.
- Tests for existing behavior.
- UI polish that makes the app easier to understand.
- Bug fixes.

## Before Changing Code

1. Read [Development Guide](../MeadowPy/docs/development.md).
2. Read [Architecture](../MeadowPy/docs/architecture.md) for the area you are changing.
3. From the repository root, enter the application directory:

```bat
cd MeadowPy
```

4. Set up development dependencies:

```bat
dev\setup-dev.bat
```

5. Run the full test suite once:

```bat
dev\Run Tests.bat
```

This confirms your environment is working before you start editing.

## Development Setup

From the `MeadowPy` application directory:

```bat
dev\setup-dev.bat
```

This calls:

```bat
..\setup.bat --dev
```

It creates or repairs `.venv`, installs app dependencies, and installs test
dependencies.

## Running MeadowPy From Source

From the `MeadowPy` application directory:

```bat
.venv\Scripts\python.exe -m meadowpy
```

## Running Tests

Run the full suite:

```bat
dev\Run Tests.bat
```

Run a targeted test without coverage:

```bat
.venv\Scripts\python.exe -m pytest -c dev\pytest.ini --no-cov dev\tests\test_settings.py -q
```

See [Testing](../MeadowPy/docs/testing.md) for the full testing workflow.

## Pull Request Expectations

A good pull request should:

- Explain what changed and why.
- Keep the scope focused.
- Include tests for behavior changes.
- Update docs for setup, workflow, shortcut, AI, architecture, or testing
  changes.
- Avoid unrelated formatting churn.
- Avoid changing generated coverage output.
- Preserve beginner-friendly wording in user-facing text.

Before submitting:

1. Run relevant targeted tests.
2. Run the full test suite.
3. Launch the app if UI behavior changed.
4. Check changed files for accidental edits.

## Bug Reports

Useful bug reports include:

- What you were trying to do.
- What happened.
- What you expected.
- Steps to reproduce.
- MeadowPy version, if known.
- Windows version.
- Python version.
- Whether Ollama was involved.
- Any relevant log details from:

```text
%USERPROFILE%\.meadowpy\meadowpy.log
```

Avoid posting private code, secrets, API keys, or personal files in public bug
reports.

If this repository is hosted on GitHub, use the bug report issue template so
the environment and reproduction details are captured consistently.

## Feature Requests

Helpful feature requests explain:

- The beginner problem being solved.
- The workflow where the feature would appear.
- What a user should be able to do after the feature exists.
- Any examples from other tools, if relevant.

MeadowPy should stay approachable. Features that add power should also protect
clarity.

If this repository is hosted on GitHub, use the feature request issue template
for feature ideas.

## Documentation Contributions

Documentation changes are welcome.

When editing docs:

- Keep commands exact.
- Keep paths exact.
- Prefer short sections with clear headings.
- Link to related docs instead of repeating large sections.
- Keep beginner-facing instructions concrete.
- Update [Shortcuts](../MeadowPy/docs/shortcuts.md) when shortcuts change.
- Update [Architecture](../MeadowPy/docs/architecture.md) when ownership or flow changes.

If this repository is hosted on GitHub, use the documentation issue template
for stale, missing, confusing, or incorrect docs.

## Example Library Contributions

Examples should be:

- Beginner-friendly.
- Safe to run.
- Well-commented.
- Focused on one concept or small project.
- Free of secrets, network requirements, and destructive file operations.

Add examples under:

```text
meadowpy\resources\examples
```

Then add the example to:

```text
meadowpy\resources\examples\catalog.json
```

## Coding Guidelines

General guidelines:

- Follow existing patterns before adding new abstractions.
- Keep UI work on the UI thread.
- Use Qt signals for worker-to-UI communication.
- Keep long-running work in background workers or subprocesses.
- Keep user-facing messages clear and beginner-friendly.
- Prefer small, testable changes.
- Update tests near the behavior you changed.

## Security Issues

Do not report security-sensitive issues publicly if they include exploit
details, private data, or a way to harm users.

Use the guidance in [Security](SECURITY.md).

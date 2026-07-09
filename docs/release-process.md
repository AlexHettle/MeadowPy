# Release Process

This guide describes a practical release checklist for MeadowPy.

Related docs:

- [Development Guide](development.md)
- [Testing](testing.md)
- [Architecture](architecture.md)

## Release Goals

A MeadowPy release should be:

- Installable from a clean checkout or downloaded folder.
- Runnable through the normal launcher flow.
- Covered by the full test suite.
- Accompanied by clear release notes.
- Clear about user-visible changes.

## Pre-Release Checklist

Before preparing a release:

1. Confirm the working tree is clean except intentional release edits.
2. Run development setup if dependencies may be stale:

```bat
dev\setup-dev.bat
```

3. Run the full test suite:

```bat
dev\Run Tests.bat
```

4. Launch the app from source:

```bat
.venv\Scripts\python.exe -m meadowpy
```

5. Smoke test key workflows:

- App starts cleanly.
- Welcome screen or restored tabs appear.
- New Python file can be saved.
- `F5` runs a Python file.
- Output panel accepts `input()`.
- Terminal panel opens and runs a simple command such as `dir`.
- `Shift+F5` runs selected code or current line.
- `F9` toggles a breakpoint.
- `F6` starts debugging.
- Problems panel shows lint results.
- Search in files works after opening a folder.
- Preferences open and save.
- AI setup dialog opens, even if Ollama is not installed.

## Version Number

The application version is defined in:

```text
meadowpy/constants.py
```

Update:

```python
VERSION = "x.y.z"
```

Use a simple semantic version style:

```text
MAJOR.MINOR.PATCH
```

Suggested meaning:

- **MAJOR**: large breaking or identity-changing release.
- **MINOR**: new user-facing features.
- **PATCH**: bug fixes, polish, documentation, or maintenance.

## Prepare Release Notes

Summarize meaningful user-visible changes for the release.

Useful categories include:

- Added
- Changed
- Fixed
- Removed
- Documentation

Keep the summary concise and include setup or migration notes when needed.

## Verify Setup From A Clean State

When possible, test setup in a clean copy of the project.

Minimum setup verification:

1. Remove or rename `.venv` in the clean copy.
2. Run:

```bat
setup.bat
```

3. Confirm setup creates `.venv`.
4. Confirm dependencies install.
5. Confirm `MeadowPy.lnk` is created when Windows allows it.
6. Launch:

```text
Run MeadowPy.bat
```

or:

```bat
.venv\Scripts\python.exe -m meadowpy
```

Do not delete a user's real working virtual environment unless you are testing
in a disposable copy.

## Verify Developer Setup

In a clean or disposable copy:

```bat
dev\setup-dev.bat
```

Then:

```bat
dev\Run Tests.bat
```

Confirm coverage outputs are generated:

```text
dev\htmlcov\index.html
dev\coverage.xml
```

## Documentation Check

Before release, verify the docs still match the app:

- [Getting Started](getting-started.md): setup and launch commands.
- [Documentation Index](index.md): doc navigation and maintenance map.
- [User Guide](user-guide.md): visible features and workflows.
- [AI Setup](ai-setup.md): Ollama settings and model-selection behavior.
- [Troubleshooting](troubleshooting.md): common errors and fixes.
- [Shortcuts](shortcuts.md): shortcuts from menus and contextual widgets.
- [Development Guide](development.md): repo layout and development workflow.
- [Testing](testing.md): test commands and coverage paths.
- [Architecture](architecture.md): module ownership and flows.
- [Contributing](../CONTRIBUTING.md): contribution expectations.
- [Security](../SECURITY.md): reporting and local AI notes.
- `.github/ISSUE_TEMPLATE/`: issue templates still match project support
  needs.
- `.github/pull_request_template.md`: pull request checklist still matches
  development expectations.

## Manual Release Notes Pass

Before tagging or distributing, write a short release summary:

- What is new?
- What changed?
- What was fixed?
- Are there setup or migration notes?
- Are there known limitations?

Avoid overpromising. If a feature is planned but not present, keep it out of
release notes for the current release.

## Git Checklist

If using Git tags:

1. Confirm status:

```bat
git status
```

2. Review changes:

```bat
git diff
```

3. Commit release changes:

```bat
git add meadowpy\constants.py CONTRIBUTING.md SECURITY.md docs .github
git commit -m "Release vX.Y.Z"
```

4. Tag the release:

```bat
git tag vX.Y.Z
```

5. Push the branch and tag:

```bat
git push
git push origin vX.Y.Z
```

Adjust commands to match the actual branch and remote workflow.

## Post-Release

After release:

1. Confirm the release can be downloaded or checked out.
2. Run a quick setup and launch check from the released source.
3. Record any release follow-up tasks as issues or notes.

## Rollback Notes

If a release has a serious problem:

1. Mark the release as problematic wherever it was announced.
2. Identify whether the issue is setup, runtime, data loss, security, or docs.
3. Prepare a patch release.
4. Explain the fix in the patch release notes.
5. Keep the previous tag intact unless your hosting workflow explicitly
   requires removing it.

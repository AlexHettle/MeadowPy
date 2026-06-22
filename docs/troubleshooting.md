# Troubleshooting

This guide collects common MeadowPy setup, launch, editor, run, debug, lint,
and AI problems.

Related docs:

- [Getting Started](getting-started.md)
- [User Guide](user-guide.md)
- [AI Setup](ai-setup.md)
- [Testing](testing.md)

## Where To Find Logs

MeadowPy writes startup, Qt, and shutdown errors to:

```text
%USERPROFILE%\.meadowpy\meadowpy.log
```

If the window closes immediately, launch MeadowPy from a terminal so you can
see terminal output too:

```bat
.venv\Scripts\python.exe -m meadowpy
```

## Python Not Found

Symptoms:

- `setup.bat` says Python was not found.
- `python --version` is not recognized.
- `py -3 --version` is not recognized.

Fix:

1. Install Python 3.11 or newer.
2. Enable **Add Python to PATH** in the installer.
3. Close and reopen Command Prompt or PowerShell.
4. Run:

```bat
python --version
```

or:

```bat
py -3 --version
```

Then run `setup.bat` again.

## Python Version Too Old

Symptoms:

- `setup.bat` finds Python but says MeadowPy requires 3.11 or newer.

Fix:

1. Install Python 3.11 or newer.
2. Confirm the new version:

```bat
py -3 --version
```

3. Run `setup.bat` again.

## Setup Fails While Creating The Virtual Environment

Symptoms:

- Setup reports `Failed to create virtual environment`.
- `.venv` is missing or incomplete.

Fix:

1. Confirm Python itself works:

```bat
py -3 -c "import sys; print(sys.version)"
```

2. Make sure the MeadowPy folder is in a writable location.
3. Run `setup.bat` again.

If the folder is in a protected location, move it somewhere like Documents and
retry.

## Setup Fails While Installing Dependencies

Symptoms:

- Setup reports `Failed to install dependencies`.
- Dependency installation stops during `pip install`.

Fix:

1. Check your internet connection.
2. Make sure antivirus or firewall software is not blocking Python.
3. Run:

```bat
.venv\Scripts\python.exe -m pip install --upgrade pip
```

4. Run setup again:

```bat
setup.bat
```

If the problem continues, try installing dependencies manually to see the full
error:

```bat
.venv\Scripts\python.exe -m pip install -r meadowpy\requirements.txt
```

## Virtual Environment Looks Broken

Symptoms:

- The `.venv` folder exists but MeadowPy will not start.
- Setup says it found a broken virtual environment.
- The project folder was moved after setup.
- The Python version used to create `.venv` was removed.

Fix:

Run:

```bat
setup.bat
```

The setup script checks `.venv\Scripts\python.exe` and recreates `.venv` if it
cannot import `sys`.

## Shortcut Was Not Created

Symptoms:

- `MeadowPy.lnk` is missing after setup.
- Setup reports that shortcut creation failed.

Fix:

Launch MeadowPy with:

```text
Run MeadowPy.bat
```

or from a terminal:

```bat
.venv\Scripts\python.exe -m meadowpy
```

Shortcut creation uses PowerShell and Windows Script Host. If either is blocked
by policy, the app can still run without the shortcut.

## MeadowPy Will Not Start

Symptoms:

- Double-clicking the shortcut does nothing.
- The window flashes and disappears.
- `Run MeadowPy.bat` closes quickly.

Fix:

1. Open Command Prompt or PowerShell in the project folder.
2. Run:

```bat
.venv\Scripts\python.exe -m meadowpy
```

3. Read the terminal output.
4. Check:

```text
%USERPROFILE%\.meadowpy\meadowpy.log
```

5. Run `setup.bat` again if dependencies appear missing.

## Window Opens But Looks Wrong

Symptoms:

- Panels are missing.
- Docks are in strange positions.
- Layout does not match expected defaults.

Fix:

Use:

```text
View > Reset Layout
```

MeadowPy restores its default dock layout without closing open files.

## File Will Not Open

Symptoms:

- MeadowPy says a file cannot be opened in the text editor.
- A file appears disabled or blocked in the File Explorer.

Cause:

MeadowPy's editor is for readable text files. It rejects known binary and
office document types such as images, executables, PDFs, Word documents,
PowerPoint files, Excel files, archives, and compiled Python files.

Fix:

- Open text files such as `.py`, `.txt`, `.md`, `.csv`, `.json`, `.toml`,
  `.ini`, `.yaml`, `.yml`, or `.log`.
- Use the original application for binary or office document files.

## Large File Warning

Symptoms:

- MeadowPy warns that a file is larger than the 10 MB safeguard.

Cause:

Large text files can slow editing, linting, symbol parsing, and AI context.

Fix:

- Choose **Cancel** if you opened the wrong file.
- Choose **Open Anyway** if you only need basic text editing.

Large-file mode disables heavier analysis for that tab.

## Run Button Is Disabled

Symptoms:

- The Run button cannot be clicked.
- Run menu items are disabled.

Likely causes:

- No editor tab is active.
- The active tab is not a code editor.
- The saved file extension is not `.py` or `.pyw`.
- A process or debug session is already running.

Fix:

1. Open or save the file as `.py`.
2. Stop any running process with `Ctrl+F5`.
3. Try `F5` again.

Unsaved tabs are treated as Python until saved with a different extension.

## Program Asks For Input But Appears Stuck

Symptoms:

- The program is waiting at `input()`.
- No new output appears.

Fix:

1. Click the input line in the Output panel.
2. Type the requested input.
3. Press Enter.

When a script is running, the Output input line sends text to the running
process's stdin.

## Process Failed To Start

Symptoms:

- Output panel reports `Failed to start - check interpreter path`.

Fix:

1. Open **File > Preferences > Execution**.
2. Clear the interpreter path to let MeadowPy auto-detect Python, or enter a
   valid `python.exe` path.
3. Save preferences.
4. Run again.

You can also use **Run > Select Interpreter...**.

## Linting Does Not Work

Symptoms:

- The Problems panel shows a linter install error.
- No lint results appear for Python files.

Fix:

1. Run setup again:

```bat
setup.bat
```

2. Confirm dependencies:

```bat
.venv\Scripts\python.exe -m pip show flake8 pylint
```

3. Check **File > Preferences > Linting**.
4. Make sure linting is enabled.
5. Make sure the current file is a `.py` or `.pyw` file.

Linting is disabled for large-file mode.

## Debugger Does Not Stop At Breakpoints

Symptoms:

- Debugging starts, but breakpoints are ignored.

Checklist:

1. Save the file as `.py` or `.pyw`.
2. Put the breakpoint on an executable line.
3. Start debugging with `F6`, not normal run with `F5`.
4. Make sure the breakpoint marker is visible before starting.
5. If breakpoints changed during a live session, MeadowPy sends updated
   breakpoints to the active debug helper automatically.

Some non-code lines may snap to the next valid statement in the editor.

## Debugger Or Console Fails To Start

Symptoms:

- Debug output reports that the debug process failed to start.
- Python console reports that it failed to start.

Fix:

1. Check the selected interpreter in **File > Preferences > Execution**.
2. Clear the interpreter path to use auto-detection.
3. Confirm the interpreter exists and runs:

```bat
"C:\Path\To\python.exe" --version
```

4. Restart MeadowPy.

## Project Search Finds Nothing

Symptoms:

- Search panel says to open a folder.
- Search returns no matches you expected.

Fix:

1. Open a folder with `Ctrl+Shift+K`.
2. Confirm the Search panel scope label points to the expected folder.
3. Disable regex if you are searching plain text.
4. Disable Match Case if casing may differ.
5. Remember that search skips hidden/build folders, binary-like suffixes, and
   files larger than 2 MB.

## AI Says No Model Selected

Symptoms:

- AI chat reports no model is selected.

Fix:

1. Open **AI > Setup/check Ollama...**.
2. Click **Check Now**.
3. Select a model.
4. Click **Use Selected Model** or **Save Settings**.

## AI Says Ollama Is Not Connected

Symptoms:

- AI chat reports `Ollama is not connected`.
- Status bar shows Ollama offline.

Fix:

1. Start Ollama.
2. Confirm the API URL:

```text
http://localhost:11434
```

3. Open **AI > Setup/check Ollama...**.
4. Click **Check Now**.

If you intentionally use a remote Ollama-compatible endpoint, verify that the
custom URL is reachable from this machine.

## Ollama Is Connected But No Models Appear

Symptoms:

- The setup dialog can reach Ollama.
- The model list is empty.

Fix:

Install a model with Ollama:

```bat
ollama pull <model-name>
```

Then return to MeadowPy and click **Check Now**.

## Full-File AI Review Is Disabled

Symptoms:

- MeadowPy says full-file AI review is disabled for large files.

Cause:

The file was opened in large-file mode.

Fix:

- Select a smaller section and use **Explain this code**.
- Open a smaller file for full-file review.

## Tests Cannot Run

Symptoms:

- `dev\Run Tests.bat` says MeadowPy has not been set up for development.
- `pytest` is missing.

Fix:

Run:

```bat
dev\setup-dev.bat
```

or:

```bat
setup.bat --dev
```

Then run:

```bat
dev\Run Tests.bat
```

See [Testing](testing.md) for details.

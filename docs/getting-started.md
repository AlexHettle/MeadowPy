# Getting Started

This guide takes a new Windows user from a downloaded copy of MeadowPy to a
running Python program.

For AI setup, see [AI Setup](ai-setup.md). For common setup problems, see
[Troubleshooting](troubleshooting.md).

## Requirements

MeadowPy currently targets:

- Windows 10 or Windows 11.
- Python 3.11 or newer.
- Internet access during setup, because `setup.bat` installs Python packages.
- Ollama, only if you want local AI features.

The application dependencies are listed in
[`meadowpy/requirements.txt`](../meadowpy/requirements.txt):

- `PyQt6`
- `PyQt6-Qt6`
- `PyQt6-QScintilla`
- `flake8`
- `pylint`

## Install Python

1. Install Python 3.11 or newer from the official Python installer.
2. During installation, enable **Add Python to PATH**.
3. Open Command Prompt or PowerShell.
4. Run one of these commands:

```bat
python --version
```

```bat
py -3 --version
```

If either command prints Python 3.11 or newer, MeadowPy can use it.

## Download MeadowPy

If you downloaded MeadowPy as a ZIP file:

1. Right-click the ZIP file.
2. Choose **Extract All**.
3. Open the extracted MeadowPy folder.

Keep the extracted folder somewhere you can write to, such as Documents. Avoid
running directly from inside the ZIP viewer.

## Run Setup

In the MeadowPy project folder, double-click:

```text
setup.bat
```

The setup script:

1. Finds Python by trying `py -3`, then `python`, then `python3`.
2. Verifies that Python is 3.11 or newer.
3. Creates or repairs the local `.venv` virtual environment.
4. Upgrades `pip`.
5. Installs dependencies from `meadowpy/requirements.txt`.
6. Verifies that PyQt6 can be imported.
7. Creates a `MeadowPy.lnk` shortcut when possible.

If setup reports that Python was not found, reinstall Python and make sure
**Add Python to PATH** is enabled.

If setup reports that dependency installation failed, check your internet
connection and run `setup.bat` again.

## Launch MeadowPy

After setup finishes, launch MeadowPy with either:

```text
MeadowPy.lnk
```

or:

```text
Run MeadowPy.bat
```

You can also launch from a terminal:

```bat
.venv\Scripts\python.exe -m meadowpy
```

The app writes runtime logs to:

```text
%USERPROFILE%\.meadowpy\meadowpy.log
```

That log is useful when the window closes immediately or startup fails before
you can read the error.

## First Run

When MeadowPy opens for the first time, you will see the Welcome screen.

To run your first program:

1. Choose a Welcome screen template, such as **Hello World**.
2. Press `F5`, or click the Run button in the toolbar.
3. Watch the Output panel at the bottom of the window.
4. If the program asks for input, type into the Output panel input line and
   press Enter.

To create your own file:

1. Press `Ctrl+N` or choose **File > New File**.
2. Type:

```python
print("Hello from MeadowPy!")
```

3. Press `Ctrl+S`.
4. Save the file with a `.py` extension, such as `hello.py`.
5. Press `F5` to run it.

Run and debug actions are enabled for Python files. Unsaved tabs are treated as
Python until saved with a different extension.

## Open A Folder

Open a project folder when you want the File Explorer and Search panel to work
against a folder of files.

1. Press `Ctrl+Shift+K`, or choose **File > Open Folder**.
2. Select a folder.
3. The File Explorer panel shows the folder contents.
4. Double-click a file to open it.

The File Explorer hides common generated folders such as `.git`, `.venv`,
`__pycache__`, `.pytest_cache`, and `node_modules`.

## Save And Restore

MeadowPy stores user settings in:

```text
%USERPROFILE%\.meadowpy\settings.json
```

By default, MeadowPy restores editor tabs from the previous session. On the
first launch, or when there are no restorable files, it opens the Welcome
screen. You can disable tab restoration in **File > Preferences > General**.

## Next Steps

- Read [User Guide](user-guide.md) for the main editor, run, debug, search,
  and settings workflows.
- Read [AI Setup](ai-setup.md) to enable local AI features with Ollama.
- Read [Shortcuts](shortcuts.md) for keyboard commands.
- Read [Troubleshooting](troubleshooting.md) if setup or launch fails.

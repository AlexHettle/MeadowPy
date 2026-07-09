# User Guide

This guide explains MeadowPy from the user's point of view. It focuses on the
features visible in the application, not on how the code is implemented.

Related docs:

- [Getting Started](getting-started.md)
- [AI Setup](ai-setup.md)
- [Shortcuts](shortcuts.md)
- [Troubleshooting](troubleshooting.md)

## Main Window

MeadowPy is organized around a central tabbed editor with dockable panels:

- **File Explorer** on the left.
- **Symbol Outline**, **AI Chat**, and debug panels on the right.
- **Output**, **Problems**, **Search**, and **Terminal** along the bottom.
- A toolbar and menu bar at the top.
- A status bar at the bottom edge.

Dock panels can be shown, hidden, moved, and reset with **View > Reset Layout**.

## Welcome Screen

By default, MeadowPy restores editor tabs from the previous session. On the
first launch, or when there are no restorable files, the Welcome screen opens
instead. You can disable startup tab restore in Preferences.
The Welcome screen lets you:

- Create a blank file.
- Open a file.
- Open a folder.
- Start from a beginner template.

Current starter templates include:

- Hello World
- Simple Calculator
- Guessing Game
- Todo List
- Turtle Graphics
- Simple Quiz
- Temperature Converter
- Word Counter
- Notes Saver
- Bank Account
- Safe Input
- Rock Paper Scissors

Choosing a template opens an untitled editor tab with ready-to-run code.

You can reopen the Welcome screen from **Help > Welcome Screen**.

## Editing Files

Use the editor for Python and other readable text files.

Common actions:

| Action | Shortcut |
| --- | --- |
| New file | `Ctrl+N` |
| Open file | `Ctrl+O` |
| Save | `Ctrl+S` |
| Save As | `Ctrl+Shift+S` |
| Close tab | `Ctrl+W` |

Editor features include:

- Python syntax highlighting.
- Line numbers.
- Current-line highlighting.
- Smart indentation.
- Auto-closing brackets and quotes.
- Python keyword and built-in completion.
- Comment and uncomment selected Python lines with `Ctrl+/`.
- Code folding.
- Brace matching.
- Word wrap.
- Find and replace.
- Drag-and-drop file opening.

Most editor behavior can be changed in **File > Preferences > Editor** and
**File > Preferences > Appearance**.

## Open Files

MeadowPy can open readable text files, including:

- `.py`
- `.pyw`
- `.txt`
- `.md`
- `.csv`
- `.json`
- `.toml`
- `.ini`
- `.cfg`
- `.yaml`
- `.yml`
- `.log`

It blocks common binary or office document types from opening in the text
editor, such as `.exe`, `.dll`, `.png`, `.jpg`, `.pdf`, `.docx`, `.xlsx`,
`.pptx`, and `.zip`.

Large text files above 10 MB trigger a warning. If you choose **Open Anyway**,
MeadowPy opens the file in large-file mode and disables heavier analysis such
as linting, symbol outline parsing, and full-file AI review for that tab.

## File Explorer

Open a project folder with `Ctrl+Shift+K` or **File > Open Folder**.

The File Explorer lets you:

- Double-click files to open them.
- Press Enter on files to open them.
- Press Enter on folders to expand or collapse them.
- Create files and folders from the title bar or context menu.
- Rename files and folders.
- Delete files and folders after confirmation.
- Collapse all folders.
- Refresh the file tree.
- Click the project folder badge to switch folders.

The explorer hides common generated or internal folders such as `.git`,
`.venv`, `__pycache__`, `.pytest_cache`, `.idea`, `.vscode`, and
`node_modules`.

## Find And Replace

Use `Ctrl+F` to open Find.

Use `Ctrl+H` to open Find and Replace.

The find bar supports:

- Match case.
- Match whole word.
- Regular expression search.
- Next match with Enter.
- Previous match with `Shift+Enter`.
- Close with Escape.
- Replace current match.
- Replace all matches in the current file.

If text is selected before opening Find, MeadowPy pre-fills the find field with
that selection when it is a single line.

## Search In Files

Use `Ctrl+Shift+F` or **Edit > Search in Files** to search across the open
project folder.

The Search panel supports:

- Plain text search.
- Case-sensitive search.
- Regular expression search.
- Grouped results by file.
- Double-click navigation to a result line.

Search skips common generated folders and binary files. It also skips files
larger than 2 MB during project search.

If you try to search a broad folder, such as a home or Documents folder,
MeadowPy asks for confirmation before scanning it.

## Symbol Outline

The Symbol Outline panel shows symbols parsed from the current Python file.
Use it to jump between classes and functions.

The outline refreshes after edits and when you switch tabs. It is disabled for
large-file mode.

Show or hide it with:

```text
View > Symbol Outline
```

or:

```text
Ctrl+Shift+O
```

## Running Python

Run the current file with `F5` or the toolbar Run button.

When you run a file, MeadowPy:

1. Checks that the current tab can be run as Python.
2. Saves the file first if **Save file before running** is enabled.
3. Resolves the Python interpreter.
4. Resolves the working directory.
5. Clears the Output panel if configured.
6. Starts the program with `python -u`.
7. Streams stdout and stderr to the Output panel.

If your program calls `input()`, type into the Output panel input field and
press Enter.

Stop a running program with `Ctrl+F5` or the Stop button.

## Run Selection Or Current Line

Use `Shift+F5` to run selected Python code.

If no text is selected, MeadowPy runs the current line.

Selection runs are written to a temporary `.py` file under:

```text
%USERPROFILE%\.meadowpy\tmp
```

The temporary file is removed when the process finishes.

## Python Console

The Output panel also includes a persistent Python console.

By default, MeadowPy starts the console automatically after startup. Type
Python into the Output panel input line and press Enter.

Console behavior:

- The console runs `python -u -i`.
- The working directory is the open project folder when one exists.
- Otherwise, it uses the current file's folder.
- If neither exists, it uses the user's home folder.
- Up and Down browse command history.
- The restart button starts a fresh console.

When a script or debug session is running, the Output input switches from
console mode to stdin mode.

## Terminal Panel

Open the Terminal panel with:

```text
View > Terminal Panel
```

or:

```text
Ctrl+Shift+T
```

The Terminal panel starts an operating-system shell inside MeadowPy. On
Windows, it uses PowerShell by default. When a project folder is open, new
terminal sessions start in that folder. Otherwise, they start in your home
folder.

Terminal behavior:

- Type a command and press Enter to run it.
- Tab completes commands, parameters, and paths. Press Tab again to cycle
  forward, or Shift+Tab to cycle backward.
- Up and Down browse terminal command history.
- Ctrl+C copies selected text, or sends an interrupt when no text is selected.
- The title bar can clear the visible terminal output.
- Terminal output understands common ANSI color sequences.

## Debugging

Start debugging with `F6`.

Basic debug workflow:

1. Open a Python file.
2. Click in a line and press `F9` to toggle a breakpoint.
3. Press `F6` to start debugging.
4. When execution pauses, inspect variables and the call stack.
5. Continue or step through the program.

Debug shortcuts:

| Action | Shortcut |
| --- | --- |
| Start debugging | `F6` |
| Toggle breakpoint | `F9` |
| Continue | `Ctrl+F6` |
| Step over | `F10` |
| Step into | `F11` |
| Step out | `Shift+F11` |
| Stop debugging | `Ctrl+Shift+F5` |

When paused, MeadowPy shows:

- **Variable Inspector** for locals and globals.
- **Call Stack** for the current stack frames.
- **Watch** for expressions you want to evaluate repeatedly.

The Run button becomes Continue while the debugger is paused.

## Problems And Linting

MeadowPy can lint Python code with either `flake8` or `pylint`.

Preferences are under **File > Preferences > Linting**:

- Choose `flake8` or `pylint`.
- Enable or disable linting.
- Enable or disable lint-on-save.
- Show or hide style issues.

Lint results appear in the Problems panel. Click a problem to jump to the
reported line and column.

If AI is configured, the Problems panel can request AI analysis for a lint
issue.

## Error Explanations

When a Python program writes an error traceback to stderr, MeadowPy checks it
against beginner-friendly error patterns. If it recognizes the error, it adds a
plain-English hint in the Output panel.

Traceback file lines in the Output panel are clickable. Click a traceback line
to open the file and jump to the reported line.

If AI is configured, the Output panel shows **AI Analysis** after an error.
That sends the last error text, and current editor code when available, to the
AI chat.

## Example Library

Open the Example Library with:

```text
Help > Example Library
```

or:

```text
Ctrl+Shift+L
```

The example library is catalog-driven and includes examples in these
categories:

- Basics
- Control Flow
- Data Structures
- Functions
- File I/O
- Classes & Objects
- Fun Projects
- Modules & Tools
- Web & Data

Selecting an example opens it as an untitled editor tab so you can run or edit
it without changing the bundled example file.

## AI Features

MeadowPy's AI features use Ollama through the local HTTP API, usually:

```text
http://localhost:11434
```

AI features include:

- AI Chat panel.
- Explain selected code.
- Review and improve selected Python code.
- Generate docstrings for functions and classes.
- Review current file with `Ctrl+Shift+R`.
- Analyze runtime errors from the Output panel.
- Analyze lint issues from the Problems panel.

The AI Chat panel receives current editor context when available, including the
filename, cursor line, enclosing function or class, and file text. Full-file AI
context and review are disabled for large-file mode.

See [AI Setup](ai-setup.md) for installation and troubleshooting.

## Preferences

Open Preferences with:

```text
File > Preferences
```

or:

```text
Ctrl+,
```

Preference categories:

- **Editor**: font, size, tab width, indentation, auto-close, completion,
  word wrap, brace matching, and code folding.
- **Appearance**: theme, custom theme base, accent color, line numbers,
  current-line highlight, whitespace, and symbol outline.
- **Linting**: linter choice and lint display options.
- **Execution**: interpreter path, working directory, save before run, output
  behavior, and maximum output lines.
- **General**: restore tabs on startup.
- **AI**: Ollama API URL and auto-connect behavior.

Settings are saved to:

```text
%USERPROFILE%\.meadowpy\settings.json
```

## Keyboard Shortcuts

Open the in-app shortcut editor from:

```text
Help > Keyboard Shortcuts
```

Use it to search, change, and reset shortcuts. For the default written list,
see [Shortcuts](shortcuts.md).

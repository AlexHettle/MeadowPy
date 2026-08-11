# Architecture

This document gives a high-level map of MeadowPy's codebase. It is meant to
help maintainers understand where behavior lives before opening many files.

Related docs:

- [Development Guide](development.md)
- [Testing](testing.md)
- [User Guide](user-guide.md)

## Big Picture

MeadowPy is a PyQt6 desktop IDE with:

- A `QApplication` wrapper in `meadowpy/app.py`.
- A `QMainWindow` in `meadowpy/ui/main_window.py`.
- Focused controllers in `meadowpy/ui/controllers/`.
- Core services in `meadowpy/core/`.
- A QScintilla-based editor in `meadowpy/editor/`.
- Dockable panels and dialogs in `meadowpy/ui/`.
- Bundled icons, styles, fonts, screenshots, and examples in
  `meadowpy/resources/`.

The application is not structured as a public library API. Most code exists to
support the desktop app.

## Startup Flow

```text
python -m meadowpy
  -> meadowpy/__main__.py
    -> enable crash logging
    -> set Windows app ID
    -> MeadowPyApp(sys.argv)
      -> create QApplication
      -> install Qt message logger
      -> load app font and icon
      -> show splash screen
      -> load settings
      -> apply stylesheet
      -> create RecentFilesManager
      -> create FileManager
      -> create MainWindow
      -> open command-line files
      -> show main window
      -> run QApplication event loop
```

Crash and Qt logs are written to:

```text
%USERPROFILE%\.meadowpy\meadowpy.log
```

## Unsaved-Work Recovery

`SessionRecoveryManager` in `meadowpy/ui/session_recovery.py` monitors every
`CodeEditor` created by `TabManager`. Modified buffers are collected after a
short debounce and at a periodic safety interval. `RecoverySnapshotStore`
writes the complete document set to a temporary file, flushes it to disk, and
atomically replaces:

```text
%USERPROFILE%\.meadowpy\unsaved-recovery.json
```

Snapshots include saved and untitled buffers, cursor positions, active-tab
state, and large-file mode. On startup, normal saved tabs are restored first;
the recovery manager then offers to overlay recovered saved buffers and reopen
untitled buffers. All restored editors remain marked modified so recovery can
never silently overwrite a source file.

At shutdown, MeadowPy flushes recovery before displaying ordinary save
prompts. A cancelled close leaves recovery active. Once every save prompt is
resolved and shutdown is accepted, the recovery timers stop and the snapshot
is removed.

## Main Window Composition

`MainWindow` creates and wires the primary UI:

- `TabManager`
- `FileExplorerPanel`
- `SymbolOutlinePanel`
- `ProblemsPanel`
- `OutputPanel`
- `SearchPanel`
- `TerminalPanel`
- `VariableInspectorPanel`
- `CallStackPanel`
- `WatchPanel`
- `AIChatPanel`
- Menu bar
- Toolbar
- Status bar
- Find/replace bar

It also creates service managers:

- `LintRunner`
- `ProcessRunner`
- `ReplManager`
- `DebugManager`
- `OllamaClient`
- `InterpreterManager`

The main window owns the objects, while controller classes own much of the
behavior.

## Controller Pattern

Controllers live in:

```text
meadowpy/ui/controllers/
```

They receive a `MainWindowContext`, which gives access to:

- The main window.
- Settings.
- File manager.
- Recent files manager.

Current controllers:

| Controller | Responsibility |
| --- | --- |
| `WorkspaceController` | Welcome screen, tabs, file open/save, explorer, preferences, layout, search navigation |
| `CodeQualityController` | Outline refresh, lint scheduling, lint results, Problems panel state |
| `ExecutionController` | Run file, run selection, process lifecycle, stdin, interpreter selection, REPL |
| `DebugController` | Breakpoints, debug start/stop, stepping, debug panels, debug UI state |
| `AIAssistantController` | Ollama lifecycle, model selector, AI prompts, chat integration |

`MainWindow.__getattr__` delegates missing attributes to controllers. This
allows existing menu and toolbar code to call `self._window.action_*` methods
even when those methods are implemented by a controller.

## Settings Flow

Defaults live in:

```text
meadowpy/constants.py
```

Settings are managed by:

```text
meadowpy/core/settings.py
```

Flow:

```text
Settings.load()
  -> read %USERPROFILE%\.meadowpy\settings.json when present
  -> fall back to DEFAULT_SETTINGS for missing keys

Settings.set(key, value)
  -> update in-memory data
  -> emit settings_changed(key, value)

Settings.save()
  -> merge DEFAULT_SETTINGS with in-memory values
  -> write settings.json
```

`WorkspaceController._on_settings_changed()` handles live updates for many
settings, especially theme, editor, lint, and explorer visibility settings.

## Resource Loading

Resources live in:

```text
meadowpy/resources/
```

Important helpers:

| File | Purpose |
| --- | --- |
| `resource_paths.py` | Resolve icon and font paths |
| `resource_loader.py` | Load icons, stylesheets, fonts, and themed resources |
| `resource_icons.py` | Load themed or tinted icons |
| `stylesheet_loader.py` | Build the active QSS stylesheet |
| `theme_colors.py` | Theme color helpers |

Stylesheets live under:

```text
meadowpy/resources/styles/
```

Icons live under:

```text
meadowpy/resources/icons/
```

## Editor Layer

The editor code lives in:

```text
meadowpy/editor/
```

Key modules:

| File | Purpose |
| --- | --- |
| `code_editor.py` | Main code editor widget |
| `editor_config.py` | Applies settings to editor widgets |
| `completion.py` | Completion behavior |
| `smart_indent.py` | Smart indentation and dedent behavior |
| `auto_close.py` | Bracket and quote auto-close behavior |
| `themes.py` | Editor theme definitions |
| `editor_fonts.py` | Editor font fallback helpers |

The editor emits signals used by controllers for:

- Text changes.
- Cursor moves.
- AI context menu requests.
- Breakpoint state.
- Lint marker updates.

## File Workflow

File I/O is handled by:

```text
meadowpy/core/file_manager.py
```

High-level flow:

```text
Open file action
  -> FileManager.open_file()
  -> FileManager.read_file()
  -> reject known unsupported suffixes
  -> sniff for binary-looking data
  -> warn for files above 10 MB
  -> decode as utf-8-sig, utf-32, utf-16, then latin-1 fallback
  -> TabManager.open_file_in_tab()
```

Save flow:

```text
Save action
  -> FileManager.save_file()
  -> write UTF-8 with newline preservation
  -> add recent file
  -> emit file_saved
  -> update tab title and run button
```

Large files can be opened in large-file mode, which disables heavier analysis.

## Run Flow

Run behavior is owned by:

```text
meadowpy/ui/controllers/execution_controller.py
meadowpy/core/process_runner.py
```

Run file flow:

```text
F5 / Run File
  -> ensure current editor can run as Python
  -> stop previous process if user confirms
  -> save file when configured
  -> resolve interpreter
  -> resolve working directory
  -> clear and show Output panel when configured
  -> ProcessRunner.run_file()
  -> QProcess starts python -u <file>
  -> stdout/stderr stream to Output panel
  -> stderr may produce beginner-friendly error explanation
```

Run selection flow:

```text
Shift+F5
  -> use selected text, or current line if selection is empty
  -> write code to %USERPROFILE%\.meadowpy\tmp\<temp>.py
  -> run temp file with python -u
  -> delete temp file when process finishes
```

## REPL Flow

REPL behavior is owned by:

```text
meadowpy/core/repl_manager.py
meadowpy/ui/output_panel.py
```

Flow:

```text
Startup initial refresh
  -> if repl.auto_start is true
  -> ExecutionController._start_repl()
  -> ReplManager.start(interpreter, working_dir)
  -> QProcess starts python -u -i
  -> OutputPanel input sends commands
  -> Up/Down browse history
```

The Output panel has two modes:

- REPL mode when no script/debug session is running.
- stdin mode while a script or debug session is running.

## Terminal Flow

The integrated shell terminal is implemented in:

```text
meadowpy/ui/terminal_panel.py
```

Flow:

```text
View > Terminal Panel / Ctrl+Shift+T
  -> TerminalPanel is shown and focused
  -> QProcess starts the default operating-system shell
  -> commands are written to shell stdin
  -> stdout/stderr stream into the terminal view
  -> Tab asks the shell completion engine for matches, with a local fallback
  -> Up/Down browse terminal command history
  -> Ctrl+C sends interrupt when no text is selected
```

The terminal starts in the open project folder when one exists. Otherwise it
uses the user's home folder. It is tabified with the other bottom panels and
is stopped during main-window shutdown.

## Debug Flow

Debug behavior is owned by:

```text
meadowpy/ui/controllers/debug_controller.py
meadowpy/core/debug_manager.py
meadowpy/core/debug_helper.py
```

High-level flow:

```text
F6 / Start Debugging
  -> save current Python file when configured
  -> collect breakpoints from all open tabs
  -> DebugManager.start_debug()
  -> start local TCP server on localhost
  -> launch python -u debug_helper.py <port> <script>
  -> debug helper connects back to IDE
  -> IDE sends breakpoints
  -> helper sends paused/eval/finished events as JSON lines
  -> IDE updates editor markers and debug panels
```

Debug state values:

- `IDLE`
- `STARTING`
- `RUNNING`
- `PAUSED`
- `STOPPING`

When paused, the UI shows:

- Variable Inspector.
- Call Stack.
- Watch panel.
- Inline step actions.

## Linting Flow

Linting behavior is owned by:

```text
meadowpy/ui/controllers/code_quality_controller.py
meadowpy/core/lint_context.py
meadowpy/core/linter.py
meadowpy/ui/problems_panel.py
```

Flow:

```text
Editor text changes (when while-typing lint is enabled)
  -> configured debounce timer starts
File save (when lint-on-save is enabled)
  -> saved path is associated with its editor
  -> lint starts for that editor
Run > Run Linter / Ctrl+Alt+L
  -> lint starts on demand
Any lint trigger
  -> CodeQualityController._do_lint()
  -> resolve interpreter, working directory, configuration, and trust state
  -> LintRunner.run_lint() with the resolved execution context and timeout
  -> background lint worker runs flake8 or pylint in that context
  -> a replacement request terminates the stale linter subprocess
  -> results parsed into LintIssue objects
  -> editor markers updated
  -> Problems panel updated
  -> status bar counts updated
```

The two automatic triggers are independent. With both disabled, linting is
manual only. Settings changes are coalesced so applying several lint
preferences starts no more than one replacement lint run.

Preferences resolves the same staged execution context for its Effective
Settings summary and asynchronous **Test Linter** action. The test invokes the
selected linter through `QProcess` with a known-good in-memory Python source,
applies the resolved configuration policy and working folder, and enforces the
selected timeout without persisting the staged values.

`lint_context.py` resolves the effective environment once per run. It supports
the interpreter selected for Run, MeadowPy's interpreter, or an explicit
interpreter; project-root or file-directory working folders; and automatic,
explicit, or isolated-default configuration. Configuration discovery is a
bounded scan that stops at the trusted target root. The target resolver prefers
the nearest project marker inside a broader explorer root and otherwise uses a
saved file's folder. The selected timeout is passed to the worker rather than
being fixed by the UI.

Target trust is part of context resolution. An untrusted target cannot
automatically supply an interpreter, working directory, linter configuration,
hook, or local plugin. MeadowPy instead uses its own interpreter, a safe
working directory, and isolated/default configuration until the root is
trusted. Explicit configuration paths must resolve inside a trusted root.

Linting is skipped when:

- Linting is disabled.
- The current tab is not a Python editor.
- The editor is in large-file mode.

## Symbol Outline Flow

The symbol outline is updated by `CodeQualityController`.

Flow:

```text
Editor text changes
  -> outline debounce timer starts
  -> current editor text is parsed
  -> SymbolOutlinePanel updates tree
```

The outline is cleared for non-editor tabs and large-file mode.

## Search Flow

Project search is implemented in:

```text
meadowpy/ui/search_panel.py
```

Flow:

```text
Ctrl+Shift+F
  -> SearchPanel.focus_search()
  -> user enters query
  -> SearchWorker runs in QThread
  -> os.walk scans project folder
  -> skip generated dirs, binary suffixes, and files over 2 MB
  -> emit matches
  -> Search panel groups results by file
  -> double-click opens file and line
```

Broad roots such as home, Documents, Downloads, Desktop, and OneDrive roots
require confirmation before scanning.

## AI Flow

AI behavior is owned by:

```text
meadowpy/ui/controllers/ai_assistant_controller.py
meadowpy/core/ollama_client.py
meadowpy/ui/ai_chat_panel.py
meadowpy/ui/dialogs/ollama_setup_dialog.py
```

Ollama connection flow:

```text
OllamaClient.start()
  -> if ollama.auto_connect is true
  -> start periodic timer
  -> check_connection()
  -> OllamaWorker in QThread
  -> GET /
  -> GET /api/tags
  -> update status bar and model selector
```

Chat flow:

```text
AI chat request
  -> AIAssistantController forwards messages
  -> OllamaClient.send_chat()
  -> ChatWorker in QThread
  -> POST /api/chat with stream=true
  -> parse JSON lines
  -> emit tokens
  -> AIChatPanel appends streamed response
```

Prompt sources:

- User chat messages.
- Explain selected code.
- Review selected Python code.
- Generate docstring.
- Review current file.
- Analyze Output panel error.
- Analyze Problems panel lint issue.

## Threading And Processes

MeadowPy uses background work for:

- Linting.
- Search.
- Ollama health checks.
- Ollama chat streaming.
- Debug subprocess communication.
- Python process execution.
- REPL subprocess execution.
- Terminal shell subprocess execution.

Important rule:

Do not update Qt UI widgets directly from worker threads. Use signals.

Shutdown paths should stop:

- AI chat workers.
- Ollama workers.
- Lint workers.
- Search workers.
- Debug sessions.
- Running processes.
- REPL processes.
- Terminal processes.

`MainWindow._shutdown_background_work()` coordinates shutdown cleanup.

## Where To Start For Common Changes

| Change | Start here |
| --- | --- |
| Add a menu item | `meadowpy/ui/menu_bar.py` |
| Add a toolbar button | `meadowpy/ui/tool_bar.py` |
| Add a preference | `meadowpy/ui/dialogs/preferences_dialog.py`, `meadowpy/constants.py` |
| Change file opening rules | `meadowpy/core/file_manager.py` |
| Change run behavior | `meadowpy/ui/controllers/execution_controller.py`, `meadowpy/core/process_runner.py` |
| Change debug behavior | `meadowpy/ui/controllers/debug_controller.py`, `meadowpy/core/debug_manager.py`, `meadowpy/core/debug_helper.py` |
| Change lint behavior | `meadowpy/core/linter.py`, `meadowpy/ui/controllers/code_quality_controller.py` |
| Change AI behavior | `meadowpy/ui/controllers/ai_assistant_controller.py`, `meadowpy/core/ollama_client.py` |
| Change example library | `meadowpy/resources/examples/catalog.json` |
| Change styles | `meadowpy/resources/styles/` |
| Change icons | `meadowpy/resources/icons/`, resource loader helpers |

## Documentation Ownership

When behavior changes, update the matching docs:

- User workflows: [User Guide](user-guide.md)
- Setup or launch: [Getting Started](getting-started.md)
- AI behavior: [AI Setup](ai-setup.md)
- Commands and tests: [Testing](testing.md)
- Internal structure: this architecture document
- Release workflow: [Release Process](release-process.md)
- Contribution expectations: [Contributing](../../.github/CONTRIBUTING.md)

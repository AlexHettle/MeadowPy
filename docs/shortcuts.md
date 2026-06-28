# Shortcuts

This page lists MeadowPy default keyboard shortcuts and contextual editor
shortcuts. Application shortcuts can be customized in MeadowPy.

The in-app shortcut editor is available from:

```text
Help > Keyboard Shortcuts
```

Select a command, click **Change**, then press the new keys. MeadowPy warns
when a key combination is already assigned and lets you either pick another
combination or move the shortcut to the selected command. Use **Reset to
default** for one command, or **Reset all to defaults** to restore every
shortcut.

Related docs:

- [User Guide](user-guide.md)
- [AI Setup](ai-setup.md)
- [Getting Started](getting-started.md)

## File

| Action | Shortcut |
| --- | --- |
| New File | `Ctrl+N` |
| Open File | `Ctrl+O` |
| Open Folder | `Ctrl+Shift+K` |
| Save | `Ctrl+S` |
| Save As | `Ctrl+Shift+S` |
| Close Tab | `Ctrl+W` |
| Preferences | `Ctrl+,` |
| Exit | `Ctrl+Q` |

## Edit

| Action | Shortcut |
| --- | --- |
| Undo | `Ctrl+Z` |
| Redo | `Ctrl+Y` |
| Cut | `Ctrl+X` |
| Copy | `Ctrl+C` |
| Paste | `Ctrl+V` |
| Select All | `Ctrl+A` |
| Find | `Ctrl+F` |
| Replace | `Ctrl+H` |
| Search in Files | `Ctrl+Shift+F` |
| Go to Line | `Ctrl+G` |
| Toggle Comment | `Ctrl+/` |

Clipboard and standard edit shortcuts are handled by the focused text widget,
so they work in the editor, Output panel, AI chat, and other text fields.

`Ctrl+/` comments or uncomments the selected Python lines. If no text is
selected, it comments or uncomments the current line.

## View

| Action | Shortcut |
| --- | --- |
| Zoom In | `Ctrl+=` |
| Zoom Out | `Ctrl+-` |
| Reset Zoom | `Ctrl+0` |
| File Explorer | `Ctrl+Shift+E` |
| Symbol Outline | `Ctrl+Shift+O` |
| Problems Panel | `Ctrl+Shift+M` |
| Output Panel | `` Ctrl+` `` |
| Search Panel | `Ctrl+Shift+J` |
| Terminal Panel | `Ctrl+Shift+T` |

## Run

| Action | Shortcut |
| --- | --- |
| Run File | `F5` |
| Run Selection / Line | `Shift+F5` |
| Stop Process | `Ctrl+F5` |

When the debugger is paused, the toolbar Run button switches to Continue.

## Debug

| Action | Shortcut |
| --- | --- |
| Start Debugging | `F6` |
| Continue | `Ctrl+F6` |
| Step Over | `F10` |
| Step Into | `F11` |
| Step Out | `Shift+F11` |
| Stop Debugging | `Ctrl+Shift+F5` |
| Toggle Breakpoint | `F9` |

## AI

| Action | Shortcut |
| --- | --- |
| Review Current File | `Ctrl+Shift+R` |
| AI Chat Panel | `Ctrl+Shift+A` |

Additional AI actions are available from editor context menus, the Output
panel, and the Problems panel:

- Explain selected code.
- Review and improve selected Python code.
- Generate docstring.
- Analyze the last runtime error.
- Analyze a lint issue.

## Help

| Action | Shortcut |
| --- | --- |
| Example Library | `Ctrl+Shift+L` |

## Find And Replace Bar

These shortcuts apply when the Find/Replace bar is focused:

| Action | Shortcut |
| --- | --- |
| Next match | `Enter` |
| Previous match | `Shift+Enter` |
| Close find bar | `Escape` |

The Find/Replace bar also includes toggles for:

- Match Case.
- Match Whole Word.
- Use Regular Expression.

## Output Panel And Python Console

These shortcuts apply inside the Output panel input line:

| Action | Shortcut |
| --- | --- |
| Run console command or send stdin | `Enter` |
| Previous console command | `Up` |
| Next console command | `Down` |

Up and Down browse command history only while the Output panel is in REPL
mode. During a running script, the input line sends stdin to the script.

## Terminal Panel

These shortcuts apply inside the Terminal panel:

| Action | Shortcut |
| --- | --- |
| Send command | `Enter` |
| Complete command, parameter, or path | `Tab` |
| Previous completion match | `Shift+Tab` |
| Previous terminal command | `Up` |
| Next terminal command | `Down` |
| Copy selected text, or interrupt with no selection | `Ctrl+C` |

## AI Chat Input

These shortcuts apply when the AI Chat input box is focused:

| Action | Shortcut |
| --- | --- |
| Send message | `Enter` |
| Insert newline | `Shift+Enter` |

## File Explorer

These shortcuts apply when the File Explorer tree is focused:

| Action | Shortcut |
| --- | --- |
| Open selected file | `Enter` |
| Expand selected folder | `Enter` |
| Collapse selected folder | `Enter` |

Double-clicking a file also opens it.

## Menus Without Shortcuts

The following actions are menu or button actions without dedicated keyboard
shortcuts:

- Recent Files.
- Clear Recent Files.
- Word Wrap.
- Reset Layout.
- Restart Python Console.
- Clear All Breakpoints.
- Select Interpreter.
- Create Virtual Environment.
- Setup/check Ollama.
- Welcome Screen.
- Keyboard Shortcuts.
- About MeadowPy.

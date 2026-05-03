<p align="center">
  <img src="meadowpy/resources/icons/meadowpy_256.png" alt="MeadowPy logo" width="300"><br>
  <strong>MeadowPy</strong>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white">
  <img alt="Platform" src="https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D4?logo=windows&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green">
  <img alt="AI" src="https://img.shields.io/badge/AI-Ollama%20powered-orange">
  <img alt="Active Development" src="https://img.shields.io/badge/Status-Active%20Development-brightgreen">
</p>

A beginner-friendly Python IDE with built-in AI assistance, a step-through debugger, and everything you need to start coding — no experience required.

![MeadowPy main interface showing the code editor, file explorer, and output panel](meadowpy/resources/Images/full%20screenshot.png)


## In 30 seconds after setup, you can:

- Run your first Python program
- Understand errors in plain English
- Ask questions about your code (with local AI)

No setup headaches. No confusing interface. Just start coding.

---

## Table of Contents

- [Why MeadowPy?](#why-meadowpy)
- [How is MeadowPy Different?](#how-is-meadowpy-different)
- [Requirements](#requirements)
- [Getting Started](#getting-started)
- [Development Testing](#development-testing)
- [AI Assistant](#ai-assistant)
- [Built for Beginners](#built-for-beginners)
- [Features](#features)
  - [Code Editor](#code-editor)
  - [Run & Debug](#run--debug)
  - [Code Quality](#code-quality)
  - [Project Management](#project-management)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [Contributing & Feedback](#contributing--feedback)
- [License](#license)

---

## Why MeadowPy?

Most code editors are built for professional developers. They're powerful, but for someone just starting out they can be overwhelming — cluttered interfaces, cryptic error messages, and no guidance when something goes wrong.

MeadowPy is different. It's built specifically for beginners, with three core ideas:

**Everything is explained, not just shown.** When your code errors, MeadowPy tells you what went wrong in plain English. When you don't know what a keyword means, you can right-click and find out instantly. The IDE teaches you as you use it.

**AI that stays on your machine.** MeadowPy's AI assistant runs entirely locally via Ollama — no account, no subscription, no data sent anywhere. It knows the context of what you're writing and answers questions like a knowledgeable friend sitting next to you.

**Zero friction to get started.** Six ready-to-run starter projects, one-click setup, and a full example library mean you can go from download to running code in minutes — no configuration required.

If you're learning Python and want an environment that supports you rather than gets in your way, MeadowPy is for you.

---

## How is MeadowPy different?

Most popular tools like VS Code and PyCharm are designed for flexibility and professional workflows. MeadowPy is designed for learning.

| Feature | MeadowPy | VS Code | PyCharm |
|--------|--------|--------|--------|
| Beginner-focused UI | ✅ | ❌ (general-purpose) | ❌ (pro-focused) |
| Setup required | Minimal | Moderate (extensions) | Moderate |
| Error explanations | Plain English | Raw tracebacks | Raw tracebacks |
| Built-in learning tools | ✅ | ❌ | ❌ |
| AI assistant | Local (offline) | Extension-based | Limited / cloud |

If you're just starting out, MeadowPy removes the friction so you can focus on learning Python, and gives you the tools to accelerate your growth as a developer.

---

## Requirements

- **Windows 10 or 11** (macOS compatibility coming soon)
- **Python 3.11 or newer** — [Download Python](https://www.python.org/downloads/)
  > During installation, make sure to check **"Add Python to PATH"**.
- **Ollama** (optional, for AI features) — [Download Ollama](https://ollama.com/download)

## Getting Started

1. **Download** — Click the green **Code** button on GitHub, then **Download ZIP**.
2. **Extract** — Right-click the ZIP and choose **Extract All**. Pick any folder you like.
3. **Setup** — Open the extracted folder and double-click **`setup.bat`**. This creates a virtual environment and installs everything MeadowPy needs. You only need to do this once.
4. **Launch** — Double-click the **MeadowPy** shortcut (created by setup) to start the IDE.

## AI Assistant

MeadowPy has a built-in AI assistant powered by [Ollama](https://ollama.com) that runs entirely on your computer — no accounts, no internet, and no data leaves your machine.

**AI Chat Panel** — Open the chat sidebar and ask questions in plain English. The AI knows which file you're editing and what function you're in, so it gives relevant answers. Responses stream in token-by-token so you don't have to wait.

![AI chat sidebar open alongside the code editor, showing a conversation about a Python function](meadowpy/resources/Images/AI%20chat.png)

**Right-click any code** to:
- **Explain this code** — Get a plain-English breakdown of what selected code does
- **Review & improve** — Get suggestions for cleaner, better code
- **Generate docstring** — Automatically write a docstring for any function or class

![Right-click context menu showing the Explain, Review, and Generate Docstring options](meadowpy/resources/Images/explain,%20review,%20and%20improve%20code.png)

**Review Current File** (Ctrl+Shift+R) — The AI reviews your entire file and gives feedback on structure, readability, naming, potential bugs, and performance.

Works with any model you have installed in Ollama — Llama, CodeLlama, DeepSeek Coder, and more. MeadowPy auto-connects when Ollama is running and lets you switch models from the status bar.

![AI file review panel displaying structured feedback on code quality and suggestions](meadowpy/resources/Images/AI%20file%20review.png)

## Built for Beginners

MeadowPy is designed from the ground up for people learning to code.

**Welcome screen with templates** — When you first open MeadowPy, you'll see six ready-to-run projects to get started with: Hello World, Simple Calculator, Guessing Game, Todo List, Turtle Graphics, and Simple Quiz. One click and you're coding.

![MeadowPy welcome screen showing six starter project templates](meadowpy/resources/Images/Welcome%20screen.png)

**Error messages you can actually understand** — When your code hits an error, MeadowPy translates the traceback into plain English. Over 100 common error patterns are covered, from `NameError` typos to `IndentationError` mix-ups. Each explanation tells you what went wrong and how to fix it.

![Beginner-friendly error panel translating a Python traceback into a plain-English explanation](meadowpy/resources/Images/beginner-friendly%20errors.png)

**"What does this mean?" on any keyword** — Right-click any Python keyword (`for`, `def`, `class`, `try`, etc.) and MeadowPy explains it in simple terms with a code example. Over 50 keywords are documented this way.

![Keyword explanation popup showing a definition and example for the 'for' keyword](meadowpy/resources/Images/Keyword%20explanations.png)

**Example library** — Browse a categorized collection of fully-commented code examples covering basics, lists, dictionaries, functions, objects, file I/O, and more. Preview the code and open it in a new tab with one click.

![Example library panel showing categories of code samples with a preview pane](meadowpy/resources/Images/example%20library.png)

**Keyboard shortcut reference** — Available under Help, a full table of every shortcut organized by category.

## Features

### Code Editor
MeadowPy's editor is built to feel familiar from day one — tabbed files, colour-coded syntax, and smart helpers that reduce the small frustrations that slow beginners down.

- Tabbed editing with Python syntax highlighting
- Auto-completion for Python keywords and built-ins
- Smart indentation and auto-closing brackets
- Code folding for functions, classes, and blocks
- Symbol outline panel for quick navigation
- Find & replace with search across files
- Light and dark themes
- Configurable font, tab width, and word wrap

### Run & Debug
Running your code is one keypress away. When something goes wrong, the debugger lets you slow everything down and watch your program think — line by line, variable by variable.

- **Run** your script with F5, or the dedicated run button
- **Interactive REPL** with stdin support
- **Step-through debugger** — set breakpoints (F9), then step over (F10), step into (F11), or step out (Shift+F11)
- **Variable inspector** — see all local and global variables update in real time as you step through code
- **Watch expressions** — monitor custom expressions like `len(my_list)` or `x + y`
- **Call stack viewer** — click any frame to inspect variables at that level

### Code Quality
MeadowPy catches mistakes before you run your code, and explains them in terms you can actually act on.

- Real-time linting with flake8 and pylint
- Lint-on-save option
- Problems panel with click-to-jump-to-line
- Beginner-friendly error explanations for every issue
- AI explanations for more complicated problems

![Problems panel showing a linting error with an AI-powered explanation and fix suggestion](meadowpy/resources/Images/Error%20AI%20tool.png)

### Project Management
Whether you're working on a single script or a folder full of files, MeadowPy keeps everything within reach.

- File explorer sidebar with create, rename, and delete
- Drag and drop file opening
- Open entire project folders
- Search across all files in a project

## Troubleshooting

**Python not found**
Make sure Python 3.11+ is installed and that you checked "Add Python to PATH" during installation. You can verify by opening Command Prompt and typing `python --version`.

**"Please run setup.bat first"**
You need to run `setup.bat` once before launching the IDE. Double-click it and wait for it to finish.

**Virtual environment looks broken**
If MeadowPy or the test runner says the virtual environment is broken, rerun `setup.bat` (or `dev\setup-dev.bat` for development). This usually happens after moving the project folder or uninstalling the Python version that originally created `.venv`.

**MeadowPy won't start**
Try running `setup.bat` again to reinstall dependencies. If the problem persists, make sure no antivirus software is blocking Python.

**Window closes immediately**
Open Command Prompt, navigate to the MeadowPy folder, and run `.venv\Scripts\python.exe main.py` to see the error message.

**AI features not working**
Make sure [Ollama](https://ollama.com/download) is installed and running. MeadowPy connects to it automatically at `localhost:11434`. You need at least one model installed.

## Roadmap

MeadowPy is actively developed. Here's what's coming next:

| Feature                                            | Status         |
| -------------------------------------------------- | -------------- |
| More example library entries and library UI rework | ✅ Completed    |
| Improved app setup & first-run experience          | ✅ Completed    |
| More starter project templates                     | ✅ Completed    |
| Custom theming options                             | ✅ Completed    |
| Comment / uncomment toggle (Ctrl+/)                | ✅ Completed    |
| High Contrast mode for visually impaired                       |  ✅ Completed     |
| macOS support                                      | 🔄 In progress |
| LM Studio integration                              | 🔄 In progress |
| Integrated terminal panel                          | 🔄 In progress |
| Improved styling cohesion                          | 🔄 In progress |
| Global search and replace                          | 🔄 In progress |
| Keyboard shortcut editor                           | 🔄 In progress |
| Add splash screen                           | 🔄 In progress |
| UI overhaul                       | 🔄 In progress     |
| Improved syntax highlighting                       | 📋 Planned     |
| Plot / output preview                              | 📋 Planned     |
| Git basics panel                                   | 📋 Planned     |
| Claude API integration                             | 📋 Planned     |
| Enhanced AI features/capabilities                  | 📋 Planned     |
| Multi-cursor editing                               | 📋 Planned     |
| Snippet / template expansion (e.g. `for`+Tab)      | 📋 Planned     |
| Clickable tracebacks in output panel               | 📋 Planned     |
| Hover docstring & signature tooltips               | 📋 Planned     |
| Quick-fix lightbulb (auto-import, unused var, …)   | 📋 Planned     |
| Breadcrumb navigation bar (file › class › method)  | 📋 Planned     |
| Inline rename refactoring                          | 📋 Planned     |
| Inline debug variable values                       | 📋 Planned     |
| Large-file safeguard (warn / lazy-load >10 MB)     | 📋 Planned     |
| Panel jump shortcuts (Ctrl+1/2/3 …)                | 📋 Planned     |



## Contributing & Feedback

MeadowPy is a solo project, but feedback from real users is what shapes it.

- **Found a bug?** [Open an issue](../../issues) with what you were doing and what went wrong.
- **Have a feature idea?** Open an issue and describe what you'd find useful — especially if you're a beginner who ran into a gap.
- **Want to contribute code?** Interested in being part of MeadowPy's development? Feel free to contact me (ahettle@depaul.edu) and we can talk about contribution.

If MeadowPy helped you learn something or is something you find useful, a ⭐ on the repo goes a long way.

## Development Testing

If you're working on MeadowPy itself, use the developer setup path so the test tools are installed too:

1. Run **`dev\setup-dev.bat`** once. This installs the app dependencies plus `pytest` and coverage reporting tools.
2. Run **`dev\Run Tests.bat`** to execute the full automated test suite with coverage.
3. If you prefer the terminal, you can also run `.venv\Scripts\python.exe -m pytest -c dev\pytest.ini`.

`dev\Run Tests.bat` forwards extra pytest arguments, so targeted runs like `dev\Run Tests.bat dev\tests\test_settings.py -q` work too.
It generates coverage outputs under the `dev\` folder:
- `dev\htmlcov\index.html` for the HTML report
- `dev\coverage.xml` for the XML report
When launched by double-click, `dev\Run Tests.bat` now stays open after the run so you can read the results. If you're running it from an existing terminal and want it to close immediately afterward, set `MEADOWPY_NO_PAUSE=1` first.

To keep the project root cleaner, the internal test suite, dev-only config, test launcher scripts, and generated coverage outputs now live under the `dev\` folder.

If you ever move the project folder or remove the Python install that created `.venv`, rerun `setup.bat` or `dev\setup-dev.bat`. MeadowPy now detects broken virtual environments and recreates them automatically.

## License

This project is licensed under the [MIT License](LICENSE).

You're free to use, modify, and distribute MeadowPy for personal or commercial purposes. See the `LICENSE` file for full details.

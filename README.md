
<p align="center">
  <img src="meadowpy/resources/icons/meadowpy_256.png" alt="MeadowPy main window" width="300"><br>
  <strong>MeadowPy</strong>
</p>

A beginner-friendly Python IDE with built-in AI assistance, a step-through debugger, and everything you need to start coding — no experience required.

## Requirements

- **Windows 10 or 11**
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
![MeadowPy Welcome window](meadowpy/resources/Images/AI%20chat.png)

**Right-click any code** to:
- **Explain this code** — Get a plain-English breakdown of what selected code does
- **Review & improve** — Get suggestions for cleaner, better code
- **Generate docstring** — Automatically write a docstring for any function or class
- ![MeadowPy Welcome window](meadowpy/resources/Images/explain,%20review,%20and%20improve%20code.png)


**Review Current File** (Ctrl+Shift+R) — The AI reviews your entire file and gives feedback on structure, readability, naming, potential bugs, and performance.

Works with any model you have installed in Ollama — Llama, CodeLlama, DeepSeek Coder, and more. MeadowPy auto-connects when Ollama is running and lets you switch models from the status bar.

![MeadowPy Welcome window](meadowpy/resources/Images/AI%20file%20review.png)


## Built for Beginners

MeadowPy is designed from the ground up for people learning to code.

**Welcome screen with templates** — When you first open MeadowPy, you'll see six ready-to-run projects to get started with: Hello World, Simple Calculator, Guessing Game, Todo List, Turtle Graphics, and Simple Quiz. One click and you're coding.

![MeadowPy Welcome window](meadowpy/resources/Images/Welcome%20screen.png)

**Error messages you can actually understand** — When your code hits an error, MeadowPy translates the traceback into plain English. Over 100 common error patterns are covered, from `NameError` typos to `IndentationError` mix-ups. Each explanation tells you what went wrong and how to fix it.

![MeadowPy Welcome window](meadowpy/resources/Images/beginner-friendly%20errors.png)

**"What does this mean?" on any keyword** — Right-click any Python keyword (`for`, `def`, `class`, `try`, etc.) and MeadowPy explains it in simple terms with a code example. Over 50 keywords are documented this way.

![MeadowPy Welcome window](meadowpy/resources/Images/Keyword%20explanations.png)


**Example library** — Browse a categorized collection of fully-commented code examples covering basics, lists, dictionaries, functions, objects, file I/O, and more. Preview the code and open it in a new tab with one click.

![MeadowPy Welcome window](meadowpy/resources/Images/example%20library.png)


**Keyboard shortcut reference** — Available under Help, a full table of every shortcut organized by category.

## Features

### Code Editor
- Tabbed editing with Python syntax highlighting
- Auto-completion for Python keywords and built-ins
- Smart indentation and auto-closing brackets
- Code folding for functions, classes, and blocks
- Symbol outline panel for quick navigation
- Find & replace with search across files
- Light and dark themes
- Configurable font, tab width, and word wrap

### Run & Debug
- **Run** your script with F5, or dedicated run button
- **Interactive REPL** with stdin support
- **Step-through debugger** — set breakpoints (F9), then step over (F10), step into (F11), or step out (Shift+F11)
- **Variable inspector** — see all local and global variables update in real time as you step through code
- **Watch expressions** — monitor custom expressions like `len(my_list)` or `x + y`
- **Call stack viewer** — click any frame to inspect variables at that level

### Code Quality
- Real-time linting with flake8 and pylint
- Lint-on-save option
- Problems panel with click-to-jump-to-line
- Beginner-friendly error explanations for every issue
- AI explanations for more complicated problems

### Project Management
- File explorer sidebar with create, rename, and delete
- Drag and drop file opening
- Open entire project folders
- Search across all files in a project

## Troubleshooting

**Python not found**
Make sure Python 3.11+ is installed and that you checked "Add Python to PATH" during installation. You can verify by opening Command Prompt and typing `python --version`.

**"Please run setup.bat first"**
You need to run `setup.bat` once before launching the IDE. Double-click it and wait for it to finish.

**MeadowPy won't start**
Try running `setup.bat` again to reinstall dependencies. If the problem persists, make sure no antivirus software is blocking Python.

**Window closes immediately**
Open Command Prompt, navigate to the MeadowPy folder, and run `.venv\Scripts\python.exe main.py` to see the error message.

**AI features not working**
Make sure [Ollama](https://ollama.com/download) is installed and running. MeadowPy connects to it automatically at `localhost:11434`. You need at least one model installed 

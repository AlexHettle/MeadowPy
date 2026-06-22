# AI Setup

MeadowPy uses Ollama for local AI features. Ollama runs on your computer and
serves models through a local HTTP API.

Related docs:

- [User Guide](user-guide.md)
- [Troubleshooting](troubleshooting.md)
- [Shortcuts](shortcuts.md)

## What MeadowPy Uses

MeadowPy talks to Ollama at this default API URL:

```text
http://localhost:11434
```

The app checks:

- `GET /` for server health.
- `GET /api/tags` for installed model names.
- `POST /api/chat` for streaming chat responses.

Chat responses stream into MeadowPy token by token.

## Install Ollama

1. Install Ollama from the official Ollama website.
2. Start Ollama.
3. Install at least one model.
4. Open MeadowPy.
5. Choose **AI > Setup/check Ollama...**.
6. Click **Check Now**.
7. Select a model.
8. Click **Use Selected Model** or **Save Settings**.

The setup dialog checks four things:

- Whether the `ollama` command is available on PATH.
- Whether the Ollama server is reachable.
- Whether at least one model is installed.
- Which model MeadowPy will use.

## Install A Model

MeadowPy does not install models directly. Use Ollama to install a model, then
return to MeadowPy and refresh the model list.

The general Ollama command shape is:

```bat
ollama pull <model-name>
```

Then verify that Ollama can see installed models:

```bat
ollama list
```

In MeadowPy, open **AI > Setup/check Ollama...** and click **Check Now**.

## Select A Model

You can select a model in either place:

- **AI > Setup/check Ollama...**
- The Ollama/model label in the MeadowPy status bar.

When you select a model, MeadowPy saves it under:

```text
ollama.selected_model
```

inside:

```text
%USERPROFILE%\.meadowpy\settings.json
```

If the selected model is no longer returned by Ollama, MeadowPy clears the
saved selection.

## Auto Connect

By default, MeadowPy automatically checks Ollama on startup. The check repeats
periodically while the app is open.

You can change this in:

```text
File > Preferences > AI
```

or in:

```text
AI > Setup/check Ollama...
```

The setting is:

```text
ollama.auto_connect
```

## AI Chat Panel

Open the AI Chat panel with:

```text
AI > AI Chat Panel
```

or:

```text
Ctrl+Shift+A
```

The chat panel can use editor context when available:

- Current filename.
- Current cursor line.
- Enclosing function or class.
- Current file text, unless the file is in large-file mode.

If no model is selected, MeadowPy reports:

```text
No model selected. Click the AI status bar to choose one.
```

If Ollama is offline, MeadowPy reports:

```text
Ollama is not connected.
```

## Explain Selected Code

Select code in the editor, right-click, and choose **Explain this code**.

For Python files, MeadowPy sends a Python-specific explanation prompt. For
other text files, it sends a general text explanation prompt.

## Review And Improve Code

Select Python code, right-click, and choose **Review & improve**.

MeadowPy asks the AI to consider:

- Readability.
- Best practices.
- Potential bugs.
- Performance.
- Structure.
- Beginner-friendly explanations.

This action is only available for Python-mode editors.

## Generate Docstrings

Right-click a Python function or class and choose **Generate docstring**.

MeadowPy asks the AI to return only a triple-quoted Python docstring inside a
fenced code block. When you insert the result at the cursor, MeadowPy tries to
place and indent the docstring correctly under the function or class.

## Review Current File

Use:

```text
AI > Review Current File
```

or:

```text
Ctrl+Shift+R
```

For Python files, MeadowPy asks for feedback on:

- Code structure and organization.
- Readability and naming.
- Potential bugs or issues.
- Best practices and improvements.
- Performance considerations.

For other text files, MeadowPy asks for feedback on clarity, organization,
tone, wording, and consistency.

Full-file review is disabled for large-file mode. Select a smaller section and
use **Explain this code** instead.

## AI Analysis For Errors

When a Python program writes an error to stderr, the Output panel stores the
last error text and shows **AI Analysis**.

Clicking **AI Analysis** sends:

- The current editor text, if available.
- The last error text.

The AI prompt asks what went wrong and how to fix it.

## AI Analysis For Lint Issues

The Problems panel can request AI help for lint issues.

MeadowPy sends:

- The linter code.
- The linter message.
- The affected line.
- One nearby non-blank line above and below when available.

The AI prompt asks what the issue means and how to fix it.

## Privacy Notes

MeadowPy's built-in AI integration is designed for a local Ollama server. With
the default URL, prompts are sent to:

```text
http://localhost:11434
```

That means MeadowPy sends prompt text to the local Ollama process on your
machine, not directly to a cloud API.

Important limits:

- Installed Ollama models are managed by the user.
- MeadowPy cannot guarantee what a custom Ollama-compatible endpoint does.
- If you change the API URL to a remote server, prompts may leave your machine.
- AI responses can be wrong; review generated code before running it.

## Troubleshooting AI

If AI features do not work:

1. Open **AI > Setup/check Ollama...**.
2. Confirm the API URL is `http://localhost:11434` unless you intentionally
   changed it.
3. Click **Check Now**.
4. If the command check fails, reinstall Ollama or reopen your terminal after
   installation.
5. If the server check fails, start Ollama.
6. If the model list is empty, install a model with Ollama.
7. If a model is installed but not selected, choose it and save settings.

See [Troubleshooting](troubleshooting.md) for more detailed fixes.

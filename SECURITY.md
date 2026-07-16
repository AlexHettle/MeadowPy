# Security Policy

This document explains how to report security issues and what users should know
about MeadowPy's local AI behavior.

Related docs:

- [AI Setup](docs/ai-setup.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Contributing](CONTRIBUTING.md)

## Supported Versions

MeadowPy is under active development. Security fixes should target the current
active codebase unless a specific older version is being maintained.

If you are unsure whether your version is supported, report the issue with the
version or source snapshot you are using.

## Reporting A Security Issue

Do not post sensitive security details publicly if the issue could put users at
risk.

When reporting a security issue, include:

- A clear summary of the issue.
- Steps to reproduce, if safe to share.
- The affected MeadowPy version or commit.
- Windows version.
- Python version.
- Whether Ollama or AI features are involved.
- Whether the issue can expose, modify, or delete user files.
- Whether the issue requires opening a malicious file or project.

Avoid including:

- Private source code.
- API keys.
- Credentials.
- Personal files.
- Full logs if they contain private paths or code.

## Local AI And Privacy

MeadowPy's built-in AI integration is designed to use a local Ollama server.
The default API URL is:

```text
http://localhost:11434
```

With the default URL, MeadowPy sends prompts to the Ollama process running on
the user's own machine.

Prompts may include:

- Selected code.
- Current file text for full-file review.
- Current filename.
- Cursor line.
- Enclosing function or class name.
- Runtime error text.
- Lint issue text and nearby code context.

Important limits:

- MeadowPy cannot verify what a custom Ollama-compatible endpoint does.
- If the Ollama API URL is changed to a remote server, prompt text may leave
  the user's machine.
- Installed Ollama models are managed outside MeadowPy.
- AI-generated code should be reviewed before it is run.

## File Handling

MeadowPy is a text editor for readable text files. It blocks many common binary
and office document types from opening in the editor.

Large text files above the built-in safeguard are opened only after user
confirmation. Large-file mode disables heavier analysis such as linting,
symbol outline parsing, and full-file AI review.

## Linter Target Trust

Linter configuration is not always passive. Pylint configuration can use
initialization hooks and load plugins, and Flake8 can load local plugins. A
project-controlled Python environment can also contain executable linter
extensions. Treat linting an unfamiliar project as running project-supplied
code.

MeadowPy therefore requires a lint target to be trusted before linting may use
its Python interpreter, working directory, configuration files, hooks, or
local plugins. For an untrusted target, MeadowPy uses its own interpreter, a
safe working directory, and isolated/default linter configuration. Automatic
configuration discovery stops at the trusted target boundary, and an explicit
configuration file must resolve inside that boundary.

MeadowPy infers a narrow target from the active file and nearby project markers
instead of automatically trusting a broader explorer folder. Trust only
targets whose contents and origin you understand. Target trust can be revoked
from **File > Preferences > Linting**. Revoking trust returns future lint
checks to the isolated behavior described above.

## Logs

Runtime logs are written to:

```text
%USERPROFILE%\.meadowpy\meadowpy.log
```

Logs may include local file paths, startup errors, Qt warnings, crash details,
or shutdown errors. Review logs before sharing them publicly.

## Dependency Security

MeadowPy installs dependencies from:

```text
meadowpy\requirements.txt
```

Development setup also installs:

```text
dev\requirements-dev.txt
```

Users and contributors should install dependencies in the project virtual
environment created by setup, not into a global Python environment.

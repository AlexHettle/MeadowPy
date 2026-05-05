from __future__ import annotations

from meadowpy.core.ollama_client import OllamaClient
from meadowpy.ui.model_selector import ModelSelectorPopup
from meadowpy.ui.controllers.window_context import MainWindowController


class AIAssistantController(MainWindowController):
    """Owns a focused slice of MainWindow behavior."""

    def _create_ollama_client(self) -> None:
        """Create the Ollama connection manager and model selector popup."""
        self._ollama_client = OllamaClient(self._settings, self)
        self._model_selector = ModelSelectorPopup(self.window)

        # Wire signals
        self._ollama_client.connection_changed.connect(
            self._on_ollama_connection_changed
        )
        self._ollama_client.models_updated.connect(
            self._on_ollama_models_updated
        )
        self._model_selector.model_chosen.connect(self._on_model_chosen)

    def _on_ollama_connection_changed(self, connected: bool, message: str) -> None:
        """Update the status bar when Ollama connection state changes."""
        model = self._settings.get("ollama.selected_model") if connected else ""
        self._status_bar_manager.update_ollama_status(connected, model)
        self._model_selector.set_connected(connected)

    def _on_ollama_models_updated(self, models: list) -> None:
        """Update the model selector when the model list is refreshed."""
        self._model_selector.set_models(models)
        # Update status bar in case the selected model was invalidated
        connected = self._ollama_client.is_connected
        model = self._settings.get("ollama.selected_model")
        self._status_bar_manager.update_ollama_status(connected, model)

    def _on_model_chosen(self, model_name: str) -> None:
        """Handle model selection from the popup menu."""
        if model_name in ("__retry__", "__refresh__"):
            self._ollama_client.check_connection()
        else:
            self._ollama_client.select_model(model_name)
            self._status_bar_manager.update_ollama_status(True, model_name)
            self._model_selector.set_current_model(model_name)

    def _on_ollama_status_clicked(self) -> None:
        """Show the model selector popup when the status bar label is clicked."""
        label = self._status_bar_manager.ollama_label
        # Position the menu just above the label
        pos = label.mapToGlobal(label.rect().topLeft())
        self._model_selector.set_current_model(
            self._settings.get("ollama.selected_model") or ""
        )
        self._model_selector.show_at(pos)

    def _on_chat_requested(self, messages: list) -> None:
        """Forward a chat request from the panel to the Ollama client."""
        self._ollama_client.send_chat(messages)

    def _on_ai_explain_requested(self, code: str) -> None:
        """Handle 'Explain this code' from the editor context menu."""
        # Build a user-friendly prompt with the selected code
        prompt = (
            "Please explain the following Python code in simple terms:\n\n"
            f"```python\n{code}\n```"
        )
        # Send it through the chat panel as if the user typed it
        self._ai_chat_panel.send_message_programmatic(prompt)

    def _on_ai_improve_requested(self, code: str) -> None:
        """Handle 'Review & improve' from the editor context menu."""
        prompt = (
            "Please review the following Python code and suggest improvements. "
            "Consider readability, best practices, potential bugs, performance, "
            "and structure. If the code could benefit from refactoring "
            "(reducing duplication, extracting functions, etc.), show the "
            "improved version. Keep your suggestions beginner-friendly:\n\n"
            f"```python\n{code}\n```"
        )
        self._ai_chat_panel.send_message_programmatic(prompt)

    def action_ai_review_file(self) -> None:
        """Send the entire current file to the AI for a code review."""
        editor = self._tab_manager.current_editor()
        if not editor:
            return
        code = editor.text()
        if not code.strip():
            return

        filename = editor.display_name
        prompt = (
            f"Please review the entire Python file \"{filename}\" below. "
            "Give feedback on:\n"
            "- Code structure and organization\n"
            "- Readability and naming\n"
            "- Potential bugs or issues\n"
            "- Best practices and improvements\n"
            "- Performance considerations\n\n"
            "Keep your review beginner-friendly and constructive:\n\n"
            f"```python\n{code}\n```"
        )
        self._ai_chat_panel.send_message_programmatic(prompt)

    def _on_ai_docstring_requested(self, code: str, insert_line: int) -> None:
        """Handle 'Generate docstring' from the editor context menu."""
        prompt = (
            "Generate a Python docstring for the function or class below.\n\n"
            "IMPORTANT rules for your response:\n"
            "1. Wrap your docstring in a fenced code block using "
            "triple backticks (```python ... ```).\n"
            "2. The code block must contain ONLY the docstring "
            'itself (the \"\"\"...\"\"\" triple-quoted string).\n'
            "3. Do NOT include the def/class line or any other code.\n"
            "4. The opening \"\"\" must be on the SAME line as the "
            "first sentence, with NO extra indentation before it — "
            "just the body-level indent.\n"
            "5. Keep every line under 79 characters (including indent) "
            "to avoid linter warnings.\n"
            "6. Do NOT put blank lines between sections of the "
            "docstring (no blank line between summary, Args, Returns, "
            "etc.) — blank lines inside docstrings cause linter "
            "warnings.\n"
            "7. Keep it beginner-friendly.\n\n"
            f"```python\n{code}\n```"
        )
        # Position cursor at the insertion point so "Insert at Cursor
        # Position" places the docstring in the right place.
        editor = self._tab_manager.current_editor()
        if editor and insert_line >= 0:
            # Figure out the body indentation (def indent + one level)
            line_text = editor.text(insert_line) if insert_line < editor.lines() else ""
            body_indent = len(line_text) - len(line_text.lstrip())
            if body_indent == 0:
                # Fallback: use def indent + 4 spaces
                def_text = editor.text(max(insert_line - 1, 0))
                def_indent = len(def_text) - len(def_text.lstrip())
                body_indent = def_indent + 4
            editor.setCursorPosition(insert_line, 0)

        self._ai_chat_panel.send_message_programmatic(prompt)

    def _on_output_ai_fix_requested(self, error_text: str) -> None:
        """Handle 'Fix with AI' from the output panel (runtime errors)."""
        # Include the current editor's code for context
        code_context = ""
        editor = self._tab_manager.current_editor()
        if editor:
            code_context = editor.text()

        if code_context:
            prompt = (
                "I got the following error when running my Python code. "
                "Please explain what went wrong and how to fix it.\n\n"
                "**My code:**\n"
                f"```python\n{code_context}\n```\n\n"
                "**Error:**\n"
                f"```\n{error_text}\n```"
            )
        else:
            prompt = (
                "I got the following Python error. "
                "Please explain what went wrong and how to fix it.\n\n"
                f"```\n{error_text}\n```"
            )
        self._ai_chat_panel.send_message_programmatic(prompt)

    def _on_lint_ai_fix_requested(
        self, code: str, line: int, message: str
    ) -> None:
        """Handle 'AI Analysis' from the problems panel (lint issues)."""
        # Get the relevant line plus surrounding context from the editor
        editor = self._tab_manager.current_editor()
        snippet_lines: list[str] = []
        if editor and line >= 1:
            total_lines = editor.lines()
            error_line_idx = line - 1  # convert to 0-based

            # Find first non-blank line above the error line
            above_idx = error_line_idx - 1
            while above_idx >= 0:
                text = editor.text(above_idx).rstrip("\n\r")
                if text.strip():
                    snippet_lines.append(f"{above_idx + 1}: {text}")
                    break
                above_idx -= 1

            # The error line itself
            error_text = editor.text(error_line_idx).rstrip("\n\r")
            snippet_lines.append(
                f"{line}: {error_text}  # <-- issue here"
            )

            # Find first non-blank line below the error line
            below_idx = error_line_idx + 1
            while below_idx < total_lines:
                text = editor.text(below_idx).rstrip("\n\r")
                if text.strip():
                    snippet_lines.append(f"{below_idx + 1}: {text}")
                    break
                below_idx += 1

        prompt = (
            f"My linter reported the following issue on line {line}:\n\n"
            f"**{code}**: {message}\n\n"
        )
        if snippet_lines:
            snippet = "\n".join(snippet_lines)
            prompt += (
                f"Here is the relevant code with surrounding context:\n"
                f"```python\n{snippet}\n```\n\n"
            )
        prompt += "Please explain what this means and how to fix it."
        self._ai_chat_panel.send_message_programmatic(prompt)

    def _on_code_insert_requested(self, code: str) -> None:
        """Insert AI-generated code at the current cursor position."""
        editor = self._tab_manager.current_editor()
        if not editor:
            return

        # If the cursor sits right after a def/class line (docstring
        # insertion), extract only the """...""" block from whatever the
        # AI returned, and re-indent it to match the function body.
        import re as _re
        line, _ = editor.getCursorPosition()
        if line > 0:
            prev_line = editor.text(line - 1)
            if prev_line.strip().startswith(("def ", "class ")):
                m = _re.search(r'([ \t]*""".*?""")', code, _re.DOTALL)
                if m:
                    docstring = m.group(1)
                    # Determine the correct body indentation
                    def_indent = len(prev_line) - len(prev_line.lstrip())
                    body_indent = " " * (def_indent + 4)
                    # Strip existing indentation and re-indent
                    lines = docstring.split("\n")
                    stripped = [l.lstrip() for l in lines]
                    code = "\n".join(
                        body_indent + s if s else "" for s in stripped
                    ).rstrip() + "\n"
                    # Force cursor to column 0 so our indent is exact
                    editor.setCursorPosition(line, 0)
                    # Insert and clean up
                    editor.insert(code)
                    # Remove blank line after insertion if one was created
                    inserted_lines = code.count("\n")
                    next_line = line + inserted_lines
                    if next_line < editor.lines():
                        if editor.text(next_line).strip() == "":
                            editor.setCursorPosition(next_line, 0)
                            editor.setSelection(
                                next_line, 0,
                                next_line + 1, 0,
                            )
                            editor.removeSelectedText()
                    editor.setFocus()
                    return

        # Ensure code ends with a newline for clean insertion
        if not code.endswith("\n"):
            code += "\n"
        line, col = editor.getCursorPosition()
        editor.insert(code)
        # Move cursor to end of inserted code
        inserted_lines = code.count("\n")
        last_line_text = code.rsplit("\n", 1)[-1] if "\n" in code else code
        new_line = line + inserted_lines
        new_col = len(last_line_text) if inserted_lines > 0 else col + len(code)
        editor.setCursorPosition(new_line, new_col)
        editor.setFocus()

    # --- Context-aware AI help ---

    def _update_ai_context(
        self, editor: CodeEditor, *, line: int | None = None
    ) -> None:
        """Push current editor context to the AI chat panel."""
        filename = editor.display_name or ""
        if line is None:
            line, _ = editor.getCursorPosition()

        # Try to find the enclosing function/class name
        func_name = ""
        if line >= 0:
            import re as _re
            for scan in range(line, -1, -1):
                text = editor.text(scan).rstrip()
                m = _re.match(r'^(\s*)(def|class)\s+(\w+)', text)
                if m:
                    func_name = f"{m.group(2)} {m.group(3)}"
                    break

        self._ai_chat_panel.update_editor_context(
            filename=filename,
            function_name=func_name,
            cursor_line=line,
            file_text=editor.text(),
        )

    # --- Window events ---

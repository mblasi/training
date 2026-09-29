#!/usr/bin/env python3
"""
Core agent functionality shared by issue_agent and take_agent.
Provides LLM client, tool sandbox, interview loop, session management.
"""
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from urllib import request
from urllib.error import HTTPError


class LLMClient:
    """OpenAI-compatible LLM client using urllib."""
    
    def __init__(self, base_url: str, api_key: str, model: str, max_tokens: int = 16000, timeout: int = 300):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
    
    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """
        Send chat completion request with optional tool calling.
        Returns: {"role": "assistant", "content": str, "tool_calls": [...], "finish_reason": str} or error dict
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
        }
        
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        req = request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST"
        )
        
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
                message = result["choices"][0]["message"]
                # Add finish_reason to message
                message["finish_reason"] = result["choices"][0].get("finish_reason", "stop")
                return message
        except HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            return {"error": f"HTTP {e.code}: {error_body}"}
        except Exception as e:
            return {"error": str(e)}


class ToolSandbox:
    """Read-only tools restricted to repo directory."""
    
    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root).resolve()
    
    def _validate_path(self, path: str) -> Path:
        """Validate path is within repo."""
        full_path = (self.repo_root / path).resolve()
        if not full_path.is_relative_to(self.repo_root):
            raise ValueError(f"Path outside repo: {path}")
        return full_path
    
    def read_file(self, path: str) -> str:
        """Read a file from the repo."""
        try:
            full_path = self._validate_path(path)
            if not full_path.is_file():
                return f"Error: {path} is not a file"
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Truncate large files
                if len(content) > 50000:
                    return content[:50000] + f"\n\n... (truncated, {len(content)} total chars)"
                return content
        except ValueError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Error reading {path}: {e}"
    
    def search(self, pattern: str) -> str:
        """Search for pattern in repo files using git grep."""
        try:
            result = subprocess.run(
                ["git", "grep", "-n", "-i", pattern],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            output = result.stdout[:5000]  # Truncate
            if not output:
                return f"No matches found for '{pattern}'"
            lines = output.split("\n")
            if len(lines) > 100:
                return "\n".join(lines[:100]) + f"\n\n... ({len(lines)} total matches)"
            return output
        except Exception as e:
            return f"Error searching: {e}"
    
    def list_issues(self) -> str:
        """List open GitHub issues."""
        try:
            result = subprocess.run(
                ["gh", "issue", "list", "--limit", "100", "--json", "number,title,labels,state"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                return f"Error: {result.stderr}"
            
            issues = json.loads(result.stdout)
            lines = ["# Open issues:"]
            for issue in issues:
                labels = [l["name"] for l in issue.get("labels", [])]
                lines.append(f"#{issue['number']}: {issue['title']} [{', '.join(labels)}]")
            return "\n".join(lines)
        except Exception as e:
            return f"Error listing issues: {e}"
    
    def view_issue(self, number: int) -> str:
        """View a specific issue."""
        try:
            result = subprocess.run(
                ["gh", "issue", "view", str(number), "--json", "number,title,body,labels,state"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                return f"Error: {result.stderr}"
            
            issue = json.loads(result.stdout)
            return f"# Issue #{issue['number']}: {issue['title']}\n\n{issue.get('body', '(no body)')}"
        except Exception as e:
            return f"Error viewing issue: {e}"
    
    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return OpenAI tool definitions."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file from the repository",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Path relative to repo root"}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "Search for a pattern in repository files (git grep)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {"type": "string", "description": "Search pattern"}
                        },
                        "required": ["pattern"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_issues",
                    "description": "List open GitHub issues",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "view_issue",
                    "description": "View details of a specific issue",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "number": {"type": "integer", "description": "Issue number"}
                        },
                        "required": ["number"]
                    }
                }
            }
        ]
    
    def execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool and return result. Returns error string instead of raising."""
        try:
            if name == "read_file":
                if "path" not in arguments:
                    return "Error: missing 'path' argument"
                return self.read_file(arguments["path"])
            elif name == "search":
                if "pattern" not in arguments:
                    return "Error: missing 'pattern' argument"
                return self.search(arguments["pattern"])
            elif name == "list_issues":
                return self.list_issues()
            elif name == "view_issue":
                if "number" not in arguments:
                    return "Error: missing 'number' argument"
                return self.view_issue(arguments["number"])
            else:
                return f"Error: unknown tool '{name}'"
        except ValueError as e:
            # Path validation errors
            return f"Error: {e}"
        except Exception as e:
            return f"Error executing {name}: {e}"


def parse_final_spec(text: str) -> dict[str, Any] | None:
    """
    Extract JSON spec from agent response.
    Requires /SPEC marker followed by a ```json fenced block.
    """
    # Look for /SPEC marker followed by json fence
    pattern = r"/SPEC\s*\n\s*```json\s*\n(.*?)\n\s*```"
    match = re.search(pattern, text, re.DOTALL)
    
    if not match:
        return None
    
    json_text = match.group(1)
    
    try:
        data = json.loads(json_text)
        return data
    except json.JSONDecodeError:
        return None


def edit_in_editor(initial_content: str) -> str | None:
    """Open $EDITOR to edit content. Returns edited content or None if cancelled."""
    editor = os.environ.get("EDITOR", "nano")
    
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".md", delete=False) as f:
        f.write(initial_content)
        temp_path = f.name
    
    try:
        subprocess.run([editor, temp_path], check=True)
        with open(temp_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None
    finally:
        os.unlink(temp_path)


def get_llm_config() -> tuple[str, str, str, int, int]:
    """
    Get LLM configuration from environment.
    Returns (base_url, api_key, model, max_tokens, timeout).
    """
    base_url = os.environ.get("BACKLOG_LLM_BASE_URL", "https://inference-api.nousresearch.com/v1")
    model = os.environ.get("BACKLOG_LLM_MODEL", "anthropic/claude-sonnet-4.6")
    max_tokens = int(os.environ.get("BACKLOG_LLM_MAX_TOKENS", "16000"))
    timeout = int(os.environ.get("BACKLOG_LLM_TIMEOUT", "300"))
    
    # Try NOUS_API_KEY first, fallback to loading from config
    api_key = os.environ.get("NOUS_API_KEY")
    
    if not api_key:
        # Try to read from ~/.config/model-keys.env
        keys_file = Path.home() / ".config" / "model-keys.env"
        if keys_file.exists():
            with open(keys_file, "r") as f:
                for line in f:
                    line = line.strip()
                    # Handle both "NOUS_API_KEY=..." and "export NOUS_API_KEY=..."
                    if line.startswith("export "):
                        line = line[7:].strip()
                    if line.startswith("NOUS_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"\'')
                        break
    
    if not api_key:
        raise ValueError(
            "NOUS_API_KEY not found. Set it in environment or ~/.config/model-keys.env"
        )
    
    return base_url, api_key, model, max_tokens, timeout


def save_session(repo_root: str, messages: list[dict[str, Any]], session_id: str | None = None, issue_num: int | None = None) -> tuple[str, str]:
    """
    Save interview transcript to .backlog/sessions/.
    Returns (json_path, md_path).
    If session_id is provided, reuses that filename; otherwise creates new timestamped files.
    If issue_num is provided, it's stored in metadata for resuming.
    """
    sessions_dir = Path(repo_root) / ".backlog" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    
    if session_id is None:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    json_path = sessions_dir / f"{session_id}.json"
    md_path = sessions_dir / f"{session_id}.md"
    
    # Save JSON (machine-readable, for resume)
    session_data = {
        "messages": messages,
        "timestamp": datetime.now().isoformat()
    }
    if issue_num is not None:
        session_data["issue"] = issue_num
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=2)
    
    # Save markdown (human-readable)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Interview Transcript\n\n")
        f.write(f"Date: {datetime.now().isoformat()}\n\n")
        
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            
            if role == "system":
                f.write("## System Prompt\n\n```\n")
                f.write(content[:1000] + "..." if len(content) > 1000 else content)
                f.write("\n```\n\n")
            elif role == "user":
                f.write(f"**User**: {content}\n\n")
            elif role == "assistant":
                if msg.get("tool_calls"):
                    f.write("**Assistant**: [tool calls]\n\n")
                else:
                    f.write(f"**Assistant**: {content}\n\n")
            elif role == "tool":
                result_preview = content[:500] + "..." if len(content) > 500 else content
                f.write(f"**Tool result**: {result_preview}\n\n")
    
    return str(json_path), str(md_path)


def load_session(session_path: str) -> tuple[list[dict[str, Any]], str]:
    """
    Load a saved session from JSON file.
    Returns (messages, session_id).
    """
    with open(session_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    messages = data["messages"]
    # Extract session_id from filename
    session_id = Path(session_path).stem
    
    return messages, session_id


def get_last_session(repo_root: str) -> str | None:
    """
    Get the path to the most recent session file.
    Returns None if no sessions exist.
    """
    sessions_dir = Path(repo_root) / ".backlog" / "sessions"
    if not sessions_dir.exists():
        return None
    
    json_files = list(sessions_dir.glob("*.json"))
    if not json_files:
        return None
    
    # Sort by modification time, most recent first
    json_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return str(json_files[0])


def find_session_for_issue(repo_root: str, issue_num: int) -> str | None:
    """
    Find the most recent session file for a given issue number.
    Returns path to session file or None if not found.
    """
    sessions_dir = Path(repo_root) / ".backlog" / "sessions"
    if not sessions_dir.exists():
        return None
    
    json_files = list(sessions_dir.glob("*.json"))
    if not json_files:
        return None
    
    # Filter sessions for this issue and sort by mtime (most recent first)
    matching_sessions = []
    for json_file in json_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("issue") == issue_num:
                    matching_sessions.append(json_file)
        except (json.JSONDecodeError, KeyError, IOError):
            # Skip corrupted or old-format session files
            continue
    
    if not matching_sessions:
        return None
    
    # Sort by mtime and return most recent
    matching_sessions.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return str(matching_sessions[0])


def run_generic_interview(
    client: LLMClient,
    sandbox: ToolSandbox,
    repo_root: str,
    system_prompt: str,
    initial_user_message: str,
    spec_validator: Callable[[dict[str, Any]], tuple[bool, str]],
    existing_messages: list[dict[str, Any]] | None = None,
    session_id: str | None = None,
    issue_num: int | None = None,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str]:
    """
    Generic interview loop for agents.
    
    Args:
        client: LLM client
        sandbox: Tool sandbox
        repo_root: Repository root path
        system_prompt: System prompt for agent
        initial_user_message: Initial user message if starting fresh
        spec_validator: Function to validate final spec, returns (valid, error_message)
        existing_messages: Optional existing conversation to continue
        session_id: Optional session ID for saving
        input_fn: Input function (for testing)
        print_fn: Print function (for testing)
    
    Returns (spec, messages, session_id).
    """
    if existing_messages:
        messages = existing_messages
        # Show the last assistant message to remind the user where we left off
        for msg in reversed(messages):
            if msg.get("role") == "assistant" and msg.get("content"):
                print_fn(f"\n[Continuando desde sesión anterior]\n")
                print_fn(f"{msg['content']}\n")
                break
        # Check if we need to wait for user input before calling LLM
        # If last message is from assistant, we should NOT call LLM immediately
        last_message_is_assistant = messages[-1].get("role") == "assistant"
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": initial_user_message}
        ]
        last_message_is_assistant = False
    
    # Generate session ID if not provided
    if session_id is None:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Print session path
    sessions_dir = Path(repo_root) / ".backlog" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    print_fn(f"Sesión: {sessions_dir / session_id}.json\n")
    
    # Interview loop
    max_turns = 30
    max_consecutive_tool_calls = 8
    consecutive_tool_calls = 0
    spec_fix_attempts = 0
    max_spec_fix_attempts = 2
    truncation_auto_retries = 0
    max_truncation_auto_retries = 1
    
    for turn in range(max_turns):
        # Skip LLM call if resuming and last message was from assistant
        if turn == 0 and last_message_is_assistant:
            # Don't call LLM, go directly to user input at the end of this iteration
            response = None
        else:
            # Call LLM with retry logic
            response = None
            while response is None:
                try:
                    response = client.chat(messages, tools=sandbox.get_tool_definitions())
                    
                    if "error" in response:
                        print_fn(f"\nError del LLM: {response['error']}")
                        print_fn("Presiona Enter para reintentar o escribe /cancelar para salir.")
                        user_choice = input_fn("> ").strip().lower()
                        if user_choice in ["/cancelar", "/cancel"]:
                            return None, messages, session_id
                        response = None  # Retry
                except Exception as e:
                    print_fn(f"\nError de red: {e}")
                    print_fn("Presiona Enter para reintentar o escribe /cancelar para salir.")
                    try:
                        user_choice = input_fn("> ").strip().lower()
                        if user_choice in ["/cancelar", "/cancel"]:
                            return None, messages, session_id
                    except (EOFError, KeyboardInterrupt):
                        print_fn("\nEntrevista cancelada.")
                        return None, messages, session_id
                    # Save messages before retry
                    save_session(repo_root, messages, session_id, issue_num)
        
        # Only process response if we got one (not skipped)
        if response is not None:
            messages.append(response)
            
            # Handle tool calls
            if response.get("tool_calls"):
                consecutive_tool_calls += 1
                
                # Bounded tool-call loop
                if consecutive_tool_calls > max_consecutive_tool_calls:
                    print_fn(f"\n[Límite de llamadas consecutivas a herramientas alcanzado. Solicitando al agente que continúe sin herramientas.]\n")
                    messages.append({
                        "role": "user",
                        "content": "Has usado muchas herramientas. Por favor continúa con la entrevista sin usar más herramientas por ahora."
                    })
                    consecutive_tool_calls = 0
                    # Save transcript
                    save_session(repo_root, messages, session_id, issue_num)
                    continue
                
                for tool_call in response["tool_calls"]:
                    func = tool_call["function"]
                    name = func["name"]
                    
                    # Parse arguments with error handling
                    try:
                        args = json.loads(func["arguments"])
                    except json.JSONDecodeError as e:
                        result = f"Error: malformed JSON arguments: {e}"
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": result
                        })
                        continue
                    
                    # Execute tool (returns error string instead of raising)
                    result = sandbox.execute_tool(name, args)
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": result
                    })
                
                # Save transcript after tool calls
                save_session(repo_root, messages, session_id, issue_num)
                # Continue loop to let agent process tool results
                continue
            
            # Reset tool call counter when assistant produces text
            consecutive_tool_calls = 0
            
            # Show agent response
            content = response.get("content", "")
            if content:
                print_fn(f"\n{content}\n")
            
            # Check if agent is signaling completion with /SPEC
            if "/SPEC" in content:
                # Try to parse spec
                spec = parse_final_spec(content)
                if spec:
                    valid, error = spec_validator(spec)
                    if valid:
                        # Save final transcript
                        save_session(repo_root, messages, session_id, issue_num)
                        return spec, messages, session_id
                    else:
                        # Reset truncation counter on valid spec attempt
                        truncation_auto_retries = 0
                        spec_fix_attempts += 1
                        if spec_fix_attempts <= max_spec_fix_attempts:
                            print_fn(f"Especificación inválida: {error}")
                            print_fn(f"Solicitando corrección (intento {spec_fix_attempts}/{max_spec_fix_attempts})...\n")
                            messages.append({"role": "user", "content": f"La especificación tiene un error: {error}. Por favor corregila."})
                            save_session(repo_root, messages, session_id, issue_num)
                            continue
                        else:
                            print_fn(f"Especificación inválida después de {max_spec_fix_attempts} intentos: {error}")
                            print_fn("Continúa la entrevista para ajustar.\n")
                            spec_fix_attempts = 0
                else:
                    # Failed to parse spec
                    finish_reason = response.get("finish_reason", "stop")
                    if finish_reason == "length":
                        # Spec was truncated due to output limit
                        print_fn(f"\n⚠️  La especificación fue truncada por el límite de salida del modelo.")
                        print_fn(f"Aumentá BACKLOG_LLM_MAX_TOKENS (actualmente: {os.environ.get('BACKLOG_LLM_MAX_TOKENS', '16000')}) o pedí una spec más compacta.\n")
                        
                        if truncation_auto_retries < max_truncation_auto_retries:
                            truncation_auto_retries += 1
                            print_fn("Solicitando que el modelo re-emita la spec de forma más compacta...\n")
                            messages.append({
                                "role": "user",
                                "content": "La especificación fue truncada. Por favor re-emití la especificación completa de forma MÁS COMPACTA: descripciones de una línea, rationales breves, sin detalles innecesarios."
                            })
                            save_session(repo_root, messages, session_id, issue_num)
                            continue
                        else:
                            print_fn("Ya se intentó re-emitir automáticamente. Por favor ajustá manualmente.\n")
                            # Reset counter for future valid spec attempts
                            truncation_auto_retries = 0
                    else:
                        print_fn("No se pudo parsear la especificación. Continúa la entrevista.\n")
        
        # Get user input
        try:
            user_input = input_fn("> ")
        except (EOFError, KeyboardInterrupt):
            print_fn("\nEntrevista cancelada.")
            save_session(repo_root, messages, session_id, issue_num)
            return None, messages, session_id
        
        user_input = user_input.strip()
        
        if user_input.lower() in ["/cancelar", "/cancel"]:
            print_fn("Entrevista cancelada.")
            save_session(repo_root, messages, session_id, issue_num)
            return None, messages, session_id
        
        if user_input.lower() == "/listo":
            messages.append({"role": "user", "content": "/listo - por favor genera la especificación final en formato /SPEC con ```json."})
        elif user_input.lower() == "/borrador":
            messages.append({"role": "user", "content": "/borrador - mostra el borrador actual de lo que llevamos hasta ahora."})
        elif user_input:
            messages.append({"role": "user", "content": user_input})
        else:
            # Empty input, skip
            continue
        
        # Save transcript after user turn
        save_session(repo_root, messages, session_id, issue_num)
    
    print_fn("Alcanzado límite de turnos.")
    save_session(repo_root, messages, session_id, issue_num)
    return None, messages, session_id

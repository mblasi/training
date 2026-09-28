#!/usr/bin/env python3
"""
Issue interviewer agent for backlog.py - stdlib only.
Conducts interactive interviews to create comprehensive issue specifications.
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
    
    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
    
    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """
        Send chat completion request with optional tool calling.
        Returns: {"role": "assistant", "content": str, "tool_calls": [...]} or error dict
        """
        payload = {
            "model": self.model,
            "messages": messages,
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
            with request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result["choices"][0]["message"]
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
        full_path = self._validate_path(path)
        if not full_path.is_file():
            return f"Error: {path} is not a file"
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Truncate large files
                if len(content) > 50000:
                    return content[:50000] + f"\n\n... (truncated, {len(content)} total chars)"
                return content
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
        """Execute a tool and return result."""
        if name == "read_file":
            return self.read_file(arguments["path"])
        elif name == "search":
            return self.search(arguments["pattern"])
        elif name == "list_issues":
            return self.list_issues()
        elif name == "view_issue":
            return self.view_issue(arguments["number"])
        else:
            return f"Unknown tool: {name}"


def load_prompt(repo_root: str) -> str:
    """Load the interviewer prompt."""
    prompt_path = Path(repo_root) / "scripts" / "agents" / "issue_interviewer.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_path}")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def get_repo_context(repo_root: str) -> str:
    """Gather repo context for the agent."""
    lines = ["# Contexto del repositorio\n"]
    
    # Design doc
    design_path = Path(repo_root) / "docs" / "DESIGN.md"
    if design_path.exists():
        with open(design_path, "r", encoding="utf-8") as f:
            lines.append("## DESIGN.md\n")
            content = f.read()
            if len(content) > 10000:
                content = content[:10000] + "\n... (truncated)"
            lines.append(content)
    
    # AGENTS.md
    agents_path = Path(repo_root) / "AGENTS.md"
    if agents_path.exists():
        with open(agents_path, "r", encoding="utf-8") as f:
            lines.append("\n## AGENTS.md\n")
            content = f.read()
            if len(content) > 5000:
                content = content[:5000] + "\n... (truncated)"
            lines.append(content)
    
    # File tree
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5
        )
        files = result.stdout.strip().split("\n")
        if len(files) > 200:
            files = files[:200] + ["... (truncated)"]
        lines.append("\n## Estructura de archivos\n```\n")
        lines.append("\n".join(files))
        lines.append("\n```\n")
    except Exception:
        pass
    
    # Open issues
    try:
        result = subprocess.run(
            ["gh", "issue", "list", "--limit", "50", "--json", "number,title,labels"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            issues = json.loads(result.stdout)
            lines.append("\n## Issues abiertos\n")
            for issue in issues[:30]:
                labels = [l["name"] for l in issue.get("labels", [])]
                lines.append(f"- #{issue['number']}: {issue['title']} [{', '.join(labels)}]")
    except Exception:
        pass
    
    return "\n".join(lines)


def parse_final_spec(text: str) -> dict[str, Any] | None:
    """
    Extract JSON spec from agent response.
    Handles markdown code fences and tries to parse robustly.
    """
    # Try to extract from code fence
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    
    # Try direct parse
    try:
        data = json.loads(text)
        return data
    except json.JSONDecodeError:
        # Try to find JSON object in text
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    
    return None


def validate_issue_spec(spec: dict[str, Any]) -> tuple[bool, str]:
    """
    Validate the final issue specification.
    Returns (valid, error_message).
    """
    if "issues" not in spec or not isinstance(spec["issues"], list):
        return False, "Missing or invalid 'issues' array"
    
    if len(spec["issues"]) == 0:
        return False, "No issues in spec"
    
    for i, issue in enumerate(spec["issues"]):
        if not isinstance(issue, dict):
            return False, f"Issue {i} is not an object"
        
        if "title" not in issue or not isinstance(issue["title"], str) or not issue["title"].strip():
            return False, f"Issue {i} missing valid title"
        
        if "type" not in issue or issue["type"] not in ["feat", "fix", "chore", "docs", "infra"]:
            return False, f"Issue {i} has invalid type (must be feat/fix/chore/docs/infra)"
        
        if "body" not in issue or not isinstance(issue["body"], str) or not issue["body"].strip():
            return False, f"Issue {i} missing body"
        
        areas = issue.get("areas", [])
        if areas is not None and not isinstance(areas, list):
            return False, f"Issue {i} areas must be a list or null"
        
        if areas:
            valid_areas = {"web", "api", "agents", "admin", "infra"}
            for area in areas:
                if area not in valid_areas:
                    return False, f"Issue {i} has invalid area '{area}'"
        
        phase = issue.get("phase")
        if phase is not None and (not isinstance(phase, int) or phase not in [0, 1, 2, 3]):
            return False, f"Issue {i} phase must be 0-3 or null"
    
    return True, ""


def run_interview(
    client: LLMClient,
    sandbox: ToolSandbox,
    repo_root: str,
    initial_idea: str = "",
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print
) -> dict[str, Any] | None:
    """
    Run the interactive interview loop.
    Returns the validated spec or None if cancelled.
    """
    prompt_template = load_prompt(repo_root)
    context = get_repo_context(repo_root)
    
    system_message = prompt_template.replace("{{REPO_CONTEXT}}", context)
    
    messages = [{"role": "system", "content": system_message}]
    
    if initial_idea:
        messages.append({"role": "user", "content": f"Idea inicial: {initial_idea}"})
    else:
        messages.append({"role": "user", "content": "Hola, necesito ayuda para especificar un nuevo issue."})
    
    # Interview loop
    max_turns = 30
    for turn in range(max_turns):
        # Call LLM
        response = client.chat(messages, tools=sandbox.get_tool_definitions())
        
        if "error" in response:
            print_fn(f"Error del LLM: {response['error']}")
            return None
        
        messages.append(response)
        
        # Handle tool calls
        if response.get("tool_calls"):
            for tool_call in response["tool_calls"]:
                func = tool_call["function"]
                name = func["name"]
                args = json.loads(func["arguments"])
                
                result = sandbox.execute_tool(name, args)
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result
                })
            
            # Continue loop to let agent process tool results
            continue
        
        # Show agent response
        content = response.get("content", "")
        if content:
            print_fn(f"\n{content}\n")
        
        # Check if agent is signaling completion
        if "/SPEC:" in content or '"issues":' in content:
            # Try to parse spec
            spec = parse_final_spec(content)
            if spec:
                valid, error = validate_issue_spec(spec)
                if valid:
                    return spec
                else:
                    print_fn(f"Especificación inválida: {error}")
                    # Give agent one chance to fix
                    messages.append({"role": "user", "content": f"La especificación tiene un error: {error}. Por favor corregila."})
                    continue
        
        # Get user input
        try:
            user_input = input_fn("> ")
        except (EOFError, KeyboardInterrupt):
            print_fn("\nEntrevista cancelada.")
            return None
        
        user_input = user_input.strip()
        
        if user_input.lower() in ["/cancelar", "/cancel"]:
            print_fn("Entrevista cancelada.")
            return None
        
        if user_input.lower() == "/listo":
            messages.append({"role": "user", "content": "/listo - por favor genera la especificación final en JSON."})
        elif user_input.lower() == "/borrador":
            messages.append({"role": "user", "content": "/borrador - mostra el borrador actual de lo que llevamos hasta ahora."})
        elif user_input:
            messages.append({"role": "user", "content": user_input})
        else:
            # Empty input, skip
            continue
    
    print_fn("Alcanzado límite de turnos.")
    return None


def save_transcript(repo_root: str, messages: list[dict[str, Any]]) -> str:
    """Save interview transcript to .backlog/sessions/."""
    sessions_dir = Path(repo_root) / ".backlog" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = sessions_dir / f"{timestamp}.md"
    
    with open(filepath, "w", encoding="utf-8") as f:
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
                f.write(f"**Tool result**: {content[:500]}...\n\n")
    
    return str(filepath)


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


def get_llm_config() -> tuple[str, str, str]:
    """
    Get LLM configuration from environment.
    Returns (base_url, api_key, model).
    """
    base_url = os.environ.get("BACKLOG_LLM_BASE_URL", "https://inference-api.nousresearch.com/v1")
    model = os.environ.get("BACKLOG_LLM_MODEL", "anthropic/claude-sonnet-4.6")
    
    # Try NOUS_API_KEY first, fallback to loading from config
    api_key = os.environ.get("NOUS_API_KEY")
    
    if not api_key:
        # Try to read from ~/.config/model-keys.env
        keys_file = Path.home() / ".config" / "model-keys.env"
        if keys_file.exists():
            with open(keys_file, "r") as f:
                for line in f:
                    if line.startswith("NOUS_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"\'')
                        break
    
    if not api_key:
        raise ValueError(
            "NOUS_API_KEY not found. Set it in environment or ~/.config/model-keys.env"
        )
    
    return base_url, api_key, model

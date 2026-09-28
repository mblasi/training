#!/usr/bin/env python3
"""
Issue interviewer agent for backlog.py - stdlib only.
Conducts interactive interviews to create comprehensive issue specifications.
"""
import json
import subprocess
from pathlib import Path
from typing import Any, Callable

# Import core agent functionality
from agent_core import (
    LLMClient,
    ToolSandbox,
    parse_final_spec,
    edit_in_editor,
    get_llm_config,
    save_session,
    load_session,
    get_last_session,
    run_generic_interview,
)


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


# parse_final_spec is imported from agent_core


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
    existing_messages: list[dict[str, Any]] | None = None,
    session_id: str | None = None,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str]:
    """
    Run the interactive interview loop for issue creation.
    Returns (spec, messages, session_id).
    
    If existing_messages is provided, continues from that state.
    If session_id is provided, reuses that ID for saving transcripts.
    """
    # If continuing from existing messages, use them
    if not existing_messages:
        # Build initial prompt
        prompt_template = load_prompt(repo_root)
        context = get_repo_context(repo_root)
        system_prompt = prompt_template.replace("{{REPO_CONTEXT}}", context)
        
        if initial_idea:
            initial_user_message = f"Idea inicial: {initial_idea}"
        else:
            initial_user_message = "Hola, necesito ayuda para especificar un nuevo issue."
    else:
        # Use existing messages as-is
        system_prompt = ""
        initial_user_message = ""
    
    return run_generic_interview(
        client=client,
        sandbox=sandbox,
        repo_root=repo_root,
        system_prompt=system_prompt,
        initial_user_message=initial_user_message,
        spec_validator=validate_issue_spec,
        existing_messages=existing_messages,
        session_id=session_id,
        input_fn=input_fn,
        print_fn=print_fn
    )


# save_transcript, load_session, get_last_session, edit_in_editor, get_llm_config
# are imported from agent_core

# Alias for backwards compatibility
save_transcript = save_session

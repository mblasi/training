#!/usr/bin/env python3
"""
Tech lead design phase for backlog.py take command.
Conducts interactive design interview and produces implementation spec.
"""
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from agent_core import (
    LLMClient,
    ToolSandbox,
    parse_final_spec,
    edit_in_editor,
    run_generic_interview,
    save_session,
)


def _escape_cell(text: str) -> str:
    """
    Escape text for a Markdown table cell.
    
    Converts:
    1. Backslash -> double backslash
    2. Pipe -> backslash-pipe
    3. Any newline (LF, CRLF, CR) -> space
    
    Order is critical: backslash must be escaped before pipe to avoid
    re-escaping the backslash of the escaped pipe.
    
    Args:
        text: Raw text to escape
    
    Returns:
        Escaped text safe for Markdown table cell
    """
    # Step 1: Escape backslashes
    result = text.replace("\\", "\\\\")
    
    # Step 2: Escape pipes
    result = result.replace("|", "\\|")
    
    # Step 3: Normalize newlines to space
    # First replace CRLF with a single newline
    result = result.replace("\r\n", "\n")
    # Then replace remaining CR with newline
    result = result.replace("\r", "\n")
    # Finally replace all newlines with space
    result = result.replace("\n", " ")
    
    return result


def _split_row(row: str) -> list[str]:
    """
    Split a Markdown table row into cells, handling escaped pipes.
    
    Tokenizes character by character:
    - Backslash-backslash -> single backslash
    - Backslash-pipe -> literal pipe (not a separator)
    - Backslash followed by any other char -> conserve backslash literal
    - Pipe -> cell separator
    - All other chars -> copy as-is
    
    Removes exactly one space of padding from start and end of each cell
    (Markdown table format convention). Discards empty initial and final
    cells (border pipes).
    
    Args:
        row: Markdown table row string (e.g. "| foo | bar |")
    
    Returns:
        List of unescaped cell contents
    """
    cells = []
    current_cell = []
    i = 0
    
    while i < len(row):
        char = row[i]
        
        if char == "\\":
            # Check next char
            if i + 1 < len(row):
                next_char = row[i + 1]
                if next_char == "\\":
                    # Backslash-backslash -> single backslash
                    current_cell.append("\\")
                    i += 2
                    continue
                elif next_char == "|":
                    # Backslash-pipe -> literal pipe
                    current_cell.append("|")
                    i += 2
                    continue
            # Backslash followed by anything else (or end of string)
            # -> conserve backslash literal
            current_cell.append("\\")
            i += 1
        elif char == "|":
            # Pipe is cell separator
            cell_content = "".join(current_cell)
            # Remove exactly one space of padding from start and end
            if cell_content.startswith(" "):
                cell_content = cell_content[1:]
            if cell_content.endswith(" "):
                cell_content = cell_content[:-1]
            cells.append(cell_content)
            current_cell = []
            i += 1
        else:
            # Regular character
            current_cell.append(char)
            i += 1
    
    # Add last cell if any
    if current_cell or cells:
        cell_content = "".join(current_cell)
        # Remove exactly one space of padding from start and end
        if cell_content.startswith(" "):
            cell_content = cell_content[1:]
        if cell_content.endswith(" "):
            cell_content = cell_content[:-1]
        cells.append(cell_content)
    
    # Discard empty initial and final cells (border pipes)
    if cells and not cells[0]:
        cells = cells[1:]
    if cells and not cells[-1]:
        cells = cells[:-1]
    
    return cells


def load_issue(issue_num: int, runner: Callable[[list[str]], subprocess.CompletedProcess] | None = None) -> dict[str, Any]:
    """
    Load full issue details from GitHub.
    
    Args:
        issue_num: Issue number
        runner: Optional command runner for testing (defaults to subprocess.run)
    
    Returns dict with: number, title, body, labels, comments, milestone
    """
    if runner is None:
        runner = lambda cmd: subprocess.run(cmd, capture_output=True, text=True, check=True)
    
    result = runner([
        "gh", "issue", "view", str(issue_num),
        "--json", "number,title,body,labels,comments,milestone"
    ])
    
    return json.loads(result.stdout)


def build_context(repo_root: str, issue: dict[str, Any]) -> str:
    """
    Build context for Tech Lead agent: issue + DESIGN.md + AGENTS.md + file tree.
    """
    lines = [f"# Issue #{issue['number']}: {issue['title']}\n"]
    
    # Issue body
    lines.append("## Descripción del issue\n")
    lines.append(issue.get("body", "(sin descripción)"))
    lines.append("\n")
    
    # Labels
    labels = [l["name"] for l in issue.get("labels", [])]
    lines.append(f"**Labels**: {', '.join(labels)}\n")
    
    # Milestone
    if milestone := issue.get("milestone"):
        lines.append(f"**Milestone**: {milestone['title']}\n")
    
    # Comments
    if comments := issue.get("comments", []):
        lines.append("\n## Comentarios\n")
        for comment in comments[:10]:  # Limit to 10 most recent
            author = comment.get("author", {}).get("login", "unknown")
            body = comment.get("body", "")
            lines.append(f"**{author}**: {body[:500]}\n")
    
    lines.append("\n---\n\n")
    
    # DESIGN.md
    design_path = Path(repo_root) / "docs" / "DESIGN.md"
    if design_path.exists():
        with open(design_path, "r", encoding="utf-8") as f:
            lines.append("# DESIGN.md\n\n")
            content = f.read()
            if len(content) > 15000:
                content = content[:15000] + "\n... (truncated)"
            lines.append(content)
            lines.append("\n")
    
    # AGENTS.md
    agents_path = Path(repo_root) / "AGENTS.md"
    if agents_path.exists():
        with open(agents_path, "r", encoding="utf-8") as f:
            lines.append("# AGENTS.md\n\n")
            content = f.read()
            if len(content) > 5000:
                content = content[:5000] + "\n... (truncated)"
            lines.append(content)
            lines.append("\n")
    
    # File tree (limited)
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
        lines.append("# Estructura de archivos\n```\n")
        lines.append("\n".join(files))
        lines.append("\n```\n")
    except Exception:
        pass
    
    return "\n".join(lines)


def validate_impl_spec(spec: dict[str, Any]) -> tuple[bool, str]:
    """
    Validate implementation spec from Tech Lead.
    
    Required fields:
    - summary: str
    - decisions: list[dict] (non-empty)
    - files: list[dict]
    - test_command: str (non-empty)
    - tasks: list[dict] (non-empty, each with at least 1 test)
    - out_of_scope: list[str]
    - risks: list[str]
    """
    if "summary" not in spec or not isinstance(spec["summary"], str):
        return False, "Missing or invalid 'summary'"
    
    if "decisions" not in spec or not isinstance(spec["decisions"], list):
        return False, "Missing or invalid 'decisions' array"
    
    if len(spec["decisions"]) == 0:
        return False, "'decisions' array is empty (todas las decisiones deben estar acordadas)"
    
    for i, decision in enumerate(spec["decisions"]):
        if not isinstance(decision, dict):
            return False, f"Decision {i} is not an object"
        required_keys = ["id", "topic", "options", "chosen", "rationale"]
        for key in required_keys:
            if key not in decision:
                return False, f"Decision {i} missing '{key}'"
    
    if "files" not in spec or not isinstance(spec["files"], list):
        return False, "Missing or invalid 'files' array"
    
    for i, file_spec in enumerate(spec["files"]):
        if not isinstance(file_spec, dict):
            return False, f"File {i} is not an object"
        if "path" not in file_spec or "action" not in file_spec:
            return False, f"File {i} missing 'path' or 'action'"
        if file_spec["action"] not in ["create", "modify", "delete"]:
            return False, f"File {i} has invalid action (must be create/modify/delete)"
    
    if "test_command" not in spec or not isinstance(spec["test_command"], str) or not spec["test_command"].strip():
        return False, "'test_command' is missing or empty"
    
    if "tasks" not in spec or not isinstance(spec["tasks"], list):
        return False, "Missing or invalid 'tasks' array"
    
    if len(spec["tasks"]) == 0:
        return False, "'tasks' array is empty"
    
    for i, task in enumerate(spec["tasks"]):
        if not isinstance(task, dict):
            return False, f"Task {i} is not an object"
        required_keys = ["id", "title", "description", "tests", "impl_files"]
        for key in required_keys:
            if key not in task:
                return False, f"Task {i} missing '{key}'"
        
        # test_support_files is optional
        if "test_support_files" in task and not isinstance(task.get("test_support_files"), list):
            return False, f"Task {i} 'test_support_files' must be a list if provided"
        
        # tests_to_remove is optional
        if "tests_to_remove" in task:
            if not isinstance(task["tests_to_remove"], list):
                return False, f"Task {i} 'tests_to_remove' must be a list if provided"
            for j, removal in enumerate(task["tests_to_remove"]):
                if not isinstance(removal, dict):
                    return False, f"Task {i}, tests_to_remove[{j}] is not an object"
                if "file" not in removal or not removal["file"]:
                    return False, f"Task {i}, tests_to_remove[{j}] missing or empty 'file'"
                if "name" not in removal or not removal["name"]:
                    return False, f"Task {i}, tests_to_remove[{j}] missing or empty 'name'"
                if "reason" not in removal or not removal["reason"]:
                    return False, f"Task {i}, tests_to_remove[{j}] missing or empty 'reason'"
        
        if not isinstance(task["tests"], list) or len(task["tests"]) == 0:
            return False, f"Task {i} has no tests (cada tarea debe tener al menos 1 test)"
        
        for j, test in enumerate(task["tests"]):
            if not isinstance(test, dict):
                return False, f"Task {i}, test {j} is not an object"
            if "file" not in test or "name" not in test or "asserts" not in test:
                return False, f"Task {i}, test {j} missing 'file', 'name', or 'asserts'"
    
    if "out_of_scope" not in spec or not isinstance(spec["out_of_scope"], list):
        return False, "Missing or invalid 'out_of_scope' array"
    
    if "risks" not in spec or not isinstance(spec["risks"], list):
        return False, "Missing or invalid 'risks' array"
    
    return True, ""


def render_spec_markdown(spec: dict[str, Any], issue: dict[str, Any]) -> str:
    """
    Render spec as deterministic markdown with front matter and checkboxes.
    
    Front matter:
      issue: N
      status: draft|approved|implementing|done
      test_command: <command>
    
    Body:
      - Summary
      - Decisions table
      - Files
      - Tasks with RED/GREEN/REFACTOR checkboxes
      - Out of scope
      - Risks
    """
    lines = ["---"]
    lines.append(f"issue: {issue['number']}")
    lines.append("status: draft")
    lines.append(f"test_command: {spec['test_command']}")
    lines.append("---")
    lines.append("")
    lines.append(f"# Spec de implementación: {issue['title']}")
    lines.append("")
    lines.append("## Resumen")
    lines.append("")
    lines.append(spec["summary"])
    lines.append("")
    
    # Decisions
    lines.append("## Decisiones de diseño")
    lines.append("")
    lines.append("| ID | Topic | Opciones | Elegida | Rationale |")
    lines.append("|----|-------|----------|---------|-----------|")
    for decision in spec["decisions"]:
        id_str = decision["id"]
        topic = _escape_cell(decision["topic"])
        options_str = _escape_cell(", ".join(decision["options"]))
        chosen = _escape_cell(decision["chosen"])
        rationale = _escape_cell(decision["rationale"])
        lines.append(f"| {id_str} | {topic} | {options_str} | {chosen} | {rationale} |")
    lines.append("")
    
    # Files
    lines.append("## Archivos afectados")
    lines.append("")
    for file_spec in spec["files"]:
        action = file_spec["action"]
        path = file_spec["path"]
        purpose = file_spec.get("purpose", "")
        lines.append(f"- **{action}** `{path}`: {purpose}")
    lines.append("")
    
    # Tasks
    lines.append("## Tareas")
    lines.append("")
    for task in spec["tasks"]:
        lines.append(f"### {task['id']}: {task['title']}")
        lines.append("")
        lines.append(task["description"])
        lines.append("")
        lines.append("**Tests:**")
        for test in task["tests"]:
            lines.append(f"- `{test['file']}::{test['name']}`: {test['asserts']}")
        lines.append("")
        if task.get("tests_to_remove"):
            lines.append("**Tests a eliminar:**")
            for removal in task["tests_to_remove"]:
                lines.append(f"- `{removal['file']}::{removal['name']}`: {removal['reason']}")
            lines.append("")
        if task.get("test_support_files"):
            lines.append("**Archivos de soporte de tests:**")
            for support_file in task["test_support_files"]:
                lines.append(f"- `{support_file}`")
            lines.append("")
        lines.append("**Archivos de implementación:**")
        for impl_file in task["impl_files"]:
            lines.append(f"- `{impl_file}`")
        lines.append("")
        lines.append("**Progreso:**")
        lines.append("- [ ] RED: tests escritos y fallan")
        lines.append("- [ ] GREEN: tests pasan")
        lines.append("- [ ] REFACTOR: código limpio")
        lines.append("")
    
    # Out of scope
    lines.append("## Fuera de alcance")
    lines.append("")
    if spec["out_of_scope"]:
        for item in spec["out_of_scope"]:
            lines.append(f"- {item}")
    else:
        lines.append("_(ninguno)_")
    lines.append("")
    
    # Risks
    lines.append("## Riesgos")
    lines.append("")
    if spec["risks"]:
        for risk in spec["risks"]:
            lines.append(f"- {risk}")
    else:
        lines.append("_(ninguno)_")
    lines.append("")
    
    return "\n".join(lines)


def parse_spec_markdown(md: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """
    Parse spec markdown back into (metadata, spec, progress).
    
    Returns:
        - metadata: {issue: int, status: str, test_command: str}
        - spec: {summary, decisions, files, tasks, out_of_scope, risks}
        - progress: {task_id: {red: bool, green: bool, refactor: bool}}
    """
    # Parse front matter
    metadata = {}
    front_matter_match = re.search(r"^---\s*\n(.*?)\n---", md, re.DOTALL | re.MULTILINE)
    if front_matter_match:
        fm_text = front_matter_match.group(1)
        for line in fm_text.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                if key == "issue":
                    metadata["issue"] = int(value)
                elif key == "status":
                    metadata["status"] = value
                elif key == "test_command":
                    metadata["test_command"] = value
    
    # Extract sections (simplified parser)
    spec = {
        "summary": "",
        "decisions": [],
        "files": [],
        "tasks": [],
        "out_of_scope": [],
        "risks": []
    }
    
    progress = {}
    
    # Summary
    summary_match = re.search(r"## Resumen\s*\n\s*\n(.*?)\n\n##", md, re.DOTALL)
    if summary_match:
        spec["summary"] = summary_match.group(1).strip()
    
    # Decisions (parse table)
    decisions_match = re.search(r"## Decisiones de diseño\s*\n\s*\n\|.*?\n\|.*?\n(.*?)\n\n##", md, re.DOTALL)
    if decisions_match:
        table_rows = decisions_match.group(1).strip().split("\n")
        for row in table_rows:
            if row.strip():
                parts = _split_row(row)
                if len(parts) >= 5:  # ID | Topic | Opciones | Elegida | Rationale
                    spec["decisions"].append({
                        "id": parts[0],
                        "topic": parts[1],
                        "options": [o.strip() for o in parts[2].split(",")],
                        "chosen": parts[3],
                        "rationale": parts[4]
                    })
    
    # Tasks (parse ### headings and checkboxes)
    task_pattern = r"### ([A-Z0-9]+): (.*?)\n\n(.*?)(?=\n###|\Z)"
    for match in re.finditer(task_pattern, md, re.DOTALL):
        task_id = match.group(1)
        title = match.group(2)
        body = match.group(3)
        
        # Extract tests (only from **Tests:** section)
        tests = []
        test_section_pattern = r"\*\*Tests:\*\*\s*\n(.*?)(?:\n\n\*\*|\n\n$|\Z)"
        test_section_match = re.search(test_section_pattern, body, re.DOTALL)
        if test_section_match:
            test_section = test_section_match.group(1)
            test_pattern = r"- `([^:]+)::([^`]+)`: (.*)"
            for test_match in re.finditer(test_pattern, test_section):
                tests.append({
                    "file": test_match.group(1),
                    "name": test_match.group(2),
                    "asserts": test_match.group(3)
                })
        
        # Extract tests_to_remove (only from **Tests a eliminar:** section)
        tests_to_remove = []
        removal_section_pattern = r"\*\*Tests a eliminar:\*\*\s*\n(.*?)(?:\n\n\*\*|\n\n$|\Z)"
        removal_section_match = re.search(removal_section_pattern, body, re.DOTALL)
        if removal_section_match:
            removal_section = removal_section_match.group(1)
            removal_pattern = r"- `([^:]+)::([^`]+)`: (.*)"
            for removal_match in re.finditer(removal_pattern, removal_section):
                tests_to_remove.append({
                    "file": removal_match.group(1),
                    "name": removal_match.group(2),
                    "reason": removal_match.group(3)
                })
        
        # Extract test_support_files
        test_support_files = []
        support_pattern = r"\*\*Archivos de soporte de tests:\*\*\s*\n(.*?)\n\n"
        support_match = re.search(support_pattern, body, re.DOTALL)
        if support_match:
            for line in support_match.group(1).split("\n"):
                if line.strip().startswith("- `"):
                    file_path = line.strip()[3:-1]  # Remove '- `' and '`'
                    test_support_files.append(file_path)
        
        # Extract impl_files
        impl_files = []
        impl_pattern = r"\*\*Archivos de implementación:\*\*\s*\n(.*?)\n\n"
        impl_match = re.search(impl_pattern, body, re.DOTALL)
        if impl_match:
            for line in impl_match.group(1).split("\n"):
                if line.strip().startswith("- `"):
                    file_path = line.strip()[3:-1]  # Remove '- `' and '`'
                    impl_files.append(file_path)
        
        # Description (before **Tests:**)
        desc_match = re.match(r"(.*?)\n\n\*\*Tests:\*\*", body, re.DOTALL)
        description = desc_match.group(1).strip() if desc_match else ""
        
        task_dict = {
            "id": task_id,
            "title": title,
            "description": description,
            "tests": tests,
            "impl_files": impl_files
        }
        if tests_to_remove:
            task_dict["tests_to_remove"] = tests_to_remove
        if test_support_files:
            task_dict["test_support_files"] = test_support_files
        
        spec["tasks"].append(task_dict)
        
        # Extract progress checkboxes
        red_checked = re.search(r"- \[x\] RED:", body) is not None
        green_checked = re.search(r"- \[x\] GREEN:", body) is not None
        refactor_checked = re.search(r"- \[x\] REFACTOR:", body) is not None
        
        progress[task_id] = {
            "red": red_checked,
            "green": green_checked,
            "refactor": refactor_checked
        }
    
    return metadata, spec, progress


def set_status(spec_path: str, status: str) -> None:
    """Update the status field in spec front matter."""
    with open(spec_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Replace status line
    content = re.sub(r"^status: \w+$", f"status: {status}", content, flags=re.MULTILINE)
    
    with open(spec_path, "w", encoding="utf-8") as f:
        f.write(content)


def mark_progress(spec_path: str, task_id: str, phase: str) -> None:
    """
    Mark a phase (red/green/refactor) as done for a task.
    
    Args:
        spec_path: Path to spec file
        task_id: Task ID (e.g. "T1")
        phase: "red", "green", or "refactor"
    """
    with open(spec_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Find the task section
    task_pattern = rf"(### {task_id}:.*?- \[)( )\] ({phase.upper()}:)"
    content = re.sub(task_pattern, r"\1x] \3", content, flags=re.IGNORECASE | re.DOTALL)
    
    with open(spec_path, "w", encoding="utf-8") as f:
        f.write(content)


def unmark_progress(spec_path: str, task_id: str, phase: str) -> None:
    """
    Unmark a phase (red/green/refactor) for a task (inverse of mark_progress).
    
    Args:
        spec_path: Path to spec file
        task_id: Task ID (e.g. "T1")
        phase: "red", "green", or "refactor"
    """
    with open(spec_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Find the task section and uncheck
    task_pattern = rf"(### {task_id}:.*?- \[)(x)\] ({phase.upper()}:)"
    content = re.sub(task_pattern, r"\1 ] \3", content, flags=re.IGNORECASE | re.DOTALL)
    
    with open(spec_path, "w", encoding="utf-8") as f:
        f.write(content)


def run_design_phase(
    client: LLMClient,
    sandbox: ToolSandbox,
    repo_root: str,
    issue: dict[str, Any],
    existing_messages: list[dict[str, Any]] | None = None,
    session_id: str | None = None,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str]:
    """
    Run the Tech Lead design interview.
    
    Returns (spec, messages, session_id).
    """
    # Load Tech Lead prompt
    prompt_path = Path(repo_root) / "scripts" / "agents" / "tech_lead.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Tech Lead prompt not found: {prompt_path}")
    
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_template = f.read()
    
    # Build context
    context = build_context(repo_root, issue)
    system_prompt = prompt_template.replace("{{CONTEXT}}", context)
    
    initial_user_message = f"Hola, necesito diseñar la implementación para el issue #{issue['number']}. Leé el contexto y proponé un diseño."
    
    return run_generic_interview(
        client=client,
        sandbox=sandbox,
        repo_root=repo_root,
        system_prompt=system_prompt,
        initial_user_message=initial_user_message,
        spec_validator=validate_impl_spec,
        existing_messages=existing_messages,
        session_id=session_id,
        issue_num=issue['number'],
        input_fn=input_fn,
        print_fn=print_fn
    )


def review_and_approve(
    spec: dict[str, Any],
    issue: dict[str, Any],
    spec_file: Path,
    branch_name: str,
    repo_root: str,
    run_command: Callable[[list[str]], subprocess.CompletedProcess],
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
    edit_fn: Callable[[str], str | None] = edit_in_editor,
    continue_fn: Callable[
        [LLMClient, ToolSandbox, str, dict[str, Any], list[dict[str, Any]], str],
        tuple[dict[str, Any] | None, list[dict[str, Any]], str]
    ] | None = None
) -> tuple[dict[str, Any], str]:
    """
    Review and approve spec with interactive loop.
    
    Args:
        spec: Implementation spec dict
        issue: Full issue dict
        spec_file: Path where spec will be saved
        branch_name: Current git branch name
        repo_root: Repository root path
        run_command: Function to run shell commands
        input_fn: Function to get user input (for testing)
        print_fn: Function to print output (for testing)
        edit_fn: Function to edit text in editor (for testing)
        continue_fn: Function to continue design conversation (for testing)
    
    Returns:
        (final_spec, status) where status is "approved", "draft", or "cancelled"
    """
    issue_num = issue["number"]
    
    while True:
        print_fn("\n" + "=" * 80)
        print_fn("PREVIEW DE LA ESPECIFICACIÓN")
        print_fn("=" * 80)
        print_fn("")
        
        spec_md = render_spec_markdown(spec, issue)
        print_fn(spec_md)
        
        print_fn("\n" + "=" * 80)
        print_fn("Opciones:")
        print_fn("  [a]probar - guardar spec y commitear")
        print_fn("  [e]ditar - editar en $EDITOR")
        print_fn("  [s]eguir - continuar conversando con el agente")
        print_fn("  [x] salir - guardar como draft")
        print_fn("=" * 80)
        
        choice = input_fn("\n> ").strip().lower()
        
        if choice == "a":
            # Approve: save file, commit, post comment with decisions table
            with open(spec_file, "w", encoding="utf-8") as f:
                f.write(spec_md)
            
            set_status(str(spec_file), "approved")
            
            # Commit
            run_command(["git", "add", str(spec_file)])
            run_command(["git", "commit", "-m", f"docs: spec de implementación (#{issue_num})"])
            
            # Build comment with decisions table
            summary = spec["summary"]
            decisions = spec["decisions"]
            tasks = spec["tasks"]
            test_command = spec["test_command"]
            
            # Build decisions table
            decisions_table = "| ID | Tema | Elegida | Por qué |\n|---|---|---|---|\n"
            for dec in decisions:
                decisions_table += f"| {dec['id']} | {dec['topic']} | {dec['chosen']} | {dec['rationale']} |\n"
            
            # Build tasks list
            tasks_list = "\n".join([f"- {task['description']}" for task in tasks])
            
            comment_body = f"""📋 **Especificación de implementación aprobada**

**Resumen**: {summary}

**Decisiones de diseño**:
{decisions_table}

**Tareas** ({len(tasks)}):
{tasks_list}

**Test command**: `{test_command}`

Ver especificación completa en `docs/specs/issue-{issue_num}.md` (rama `{branch_name}`).
"""
            
            run_command([
                "gh", "issue", "comment", str(issue_num),
                "--body", comment_body
            ])
            
            print_fn(f"\n✓ Spec guardada en {spec_file}")
            print_fn(f"✓ Commiteada")
            print_fn(f"✓ Comentario publicado en issue #{issue_num}")
            
            return (spec, "approved")
        
        elif choice == "e":
            # Edit in $EDITOR
            edited = edit_fn(spec_md)
            if edited:
                try:
                    metadata, new_spec, progress = parse_spec_markdown(edited)
                    # Validate
                    valid, error = validate_impl_spec(new_spec)
                    if valid:
                        spec = new_spec
                        print_fn("Especificación actualizada.")
                    else:
                        print_fn(f"Error de validación: {error}")
                        print_fn("Cambios descartados.")
                except Exception as e:
                    print_fn(f"Error parseando: {e}")
                    print_fn("Cambios descartados.")
            else:
                print_fn("Edición cancelada.")
        
        elif choice == "s":
            # Continue conversation
            if continue_fn is None:
                print_fn("Error: continue_fn no provista.")
                continue
            
            print_fn("\nContinuando diseño. Escribí tu pregunta o ajuste:\n")
            user_msg = input_fn("> ").strip()
            if not user_msg:
                print_fn("Cancelado.")
                continue
            
            # Call continue_fn which should return (new_spec, messages, session_id)
            # If continuation fails or is cancelled, it returns (None, messages, session_id)
            try:
                new_spec, new_messages, new_session_id = continue_fn(user_msg)
                if new_spec:
                    # Update spec to the new one
                    spec = new_spec
                    print_fn("\nEspecificación actualizada. Mostrando preview...\n")
                else:
                    print_fn("\nContinuación cancelada o sin resultado. Manteniendo spec anterior.\n")
            except Exception as e:
                print_fn(f"\nError durante continuación: {e}")
                print_fn("Manteniendo spec anterior.\n")
        
        elif choice == "x":
            # Save as draft
            with open(spec_file, "w", encoding="utf-8") as f:
                f.write(spec_md)
            
            print_fn(f"\n✓ Spec guardada como draft en {spec_file}")
            print_fn(f"Para continuar: python3 scripts/backlog.py take {issue_num}")
            
            return (spec, "draft")
        
        else:
            print_fn("Opción inválida. Usá a/e/s/x.")

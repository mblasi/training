#!/usr/bin/env python3
"""
Issue management harness for GitHub-backed backlog workflow.
Requires: git, gh CLI authenticated.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


def run_command(cmd: list[str], cwd: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Execute a command safely using argument list (never shell=True)."""
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)


def git_toplevel() -> str:
    """Get the repository root directory."""
    result = run_command(["git", "rev-parse", "--show-toplevel"])
    return result.stdout.strip()


def get_repo_slug() -> str:
    """Get repository slug (owner/repo) from gh or env."""
    if slug := os.environ.get("BACKLOG_REPO"):
        return slug
    result = run_command(["gh", "repo", "view", "--json", "nameWithOwner"])
    data = json.loads(result.stdout)
    return data["nameWithOwner"]


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:50]


def parse_issue_number_from_branch(branch: str) -> int | None:
    """Extract issue number from branch name like 'issue/123-foo-bar'."""
    if match := re.match(r"^issue/(\d+)", branch):
        return int(match.group(1))
    return None


def current_branch() -> str:
    """Get current git branch name."""
    result = run_command(["git", "branch", "--show-current"])
    return result.stdout.strip()


def is_working_tree_clean() -> bool:
    """Check if git working tree is clean."""
    result = run_command(["git", "status", "--porcelain"])
    return result.stdout.strip() == ""


def get_default_branch() -> str:
    """Get default branch name (typically 'main')."""
    result = run_command(["gh", "repo", "view", "--json", "defaultBranchRef", "-q", ".defaultBranchRef.name"])
    return result.stdout.strip()


def cmd_init(args):
    """Initialize labels and milestones (idempotent)."""
    labels = [
        ("status:todo", "ededed", "Issue is queued"),
        ("status:wip", "fbca04", "Work in progress"),
        ("status:review", "0e8a16", "In review"),
        ("blocked", "d73a4a", "Blocked by dependency"),
        ("type:feat", "a2eeef", "New feature"),
        ("type:fix", "d73a4a", "Bug fix"),
        ("type:chore", "fef2c0", "Maintenance task"),
        ("type:docs", "0075ca", "Documentation"),
        ("type:infra", "5319e7", "Infrastructure"),
        ("area:web", "c5def5", "Web frontend"),
        ("area:api", "c5def5", "API backend"),
        ("area:agents", "c5def5", "AI agents"),
        ("area:admin", "c5def5", "Admin tools"),
        ("area:infra", "c5def5", "Infrastructure"),
    ]
    
    print("Creating labels...")
    for name, color, description in labels:
        result = run_command(
            ["gh", "label", "create", name, "--color", color, "--description", description, "--force"],
            check=False
        )
        if result.returncode == 0:
            print(f"  ✓ {name}")
    
    milestones = [
        ("Fase 0 - Fundaciones", "Infrastructure and core setup"),
        ("Fase 1 - MVP individual", "Individual user MVP"),
        ("Fase 2 - Retención y comunidad", "Retention and community features"),
        ("Fase 3 - Calidad y escala", "Quality and scale improvements"),
    ]
    
    print("\nCreating milestones...")
    # Fetch existing milestones
    result = run_command(["gh", "api", "/repos/{owner}/{repo}/milestones", "--paginate"], check=False)
    existing = {m["title"] for m in json.loads(result.stdout)} if result.returncode == 0 else set()
    
    for title, description in milestones:
        if title in existing:
            print(f"  ~ {title} (already exists)")
            continue
        
        payload = json.dumps({"title": title, "description": description})
        result = run_command(
            ["gh", "api", "/repos/{owner}/{repo}/milestones", "-X", "POST", "-f", f"title={title}", "-f", f"description={description}"],
            check=False
        )
        if result.returncode == 0:
            print(f"  ✓ {title}")
        else:
            print(f"  ✗ {title}: {result.stderr}", file=sys.stderr)
    
    print("\nInitialization complete.")


def create_issue_from_spec(title: str, type_label: str, areas: list[str] | None, phase: int | None, body: str) -> int:
    """
    Create a single issue with given parameters.
    Returns the issue number.
    """
    labels = [f"type:{type_label}", "status:todo"]
    
    if areas:
        labels.extend(f"area:{a}" for a in areas)
    
    milestone_map = {
        0: "Fase 0 - Fundaciones",
        1: "Fase 1 - MVP individual",
        2: "Fase 2 - Retención y comunidad",
        3: "Fase 3 - Calidad y escala",
    }
    
    cmd = ["gh", "issue", "create", "--title", title, "--body", body]
    for label in labels:
        cmd.extend(["--label", label])
    
    if phase is not None:
        milestone = milestone_map[phase]
        cmd.extend(["--milestone", milestone])
    
    result = run_command(cmd)
    url = result.stdout.strip()
    
    if match := re.search(r"/issues/(\d+)", url):
        return int(match.group(1))
    else:
        raise ValueError(f"Could not parse issue number from: {url}")


def show_preview(issues: list[dict[str, Any]]) -> None:
    """Show issue preview, using pager if output is long and stdout is TTY."""
    lines = []
    lines.append("=" * 80)
    lines.append("PREVIEW DE ISSUE(S):")
    lines.append("=" * 80)
    
    for i, issue_spec in enumerate(issues, 1):
        lines.append(f"\n--- Issue {i}/{len(issues)} ---")
        lines.append(f"Título: {issue_spec['title']}")
        lines.append(f"Tipo: {issue_spec['type']}")
        lines.append(f"Áreas: {', '.join(issue_spec.get('areas', []) or []) or 'ninguna'}")
        lines.append(f"Fase: {issue_spec.get('phase', 'ninguna')}")
        lines.append(f"\nCuerpo:")
        lines.append(issue_spec['body'])
    
    lines.append("\n" + "=" * 80)
    
    output = "\n".join(lines)
    
    # Use pager if TTY and output is long
    if sys.stdout.isatty():
        try:
            term_height = int(subprocess.run(["tput", "lines"], capture_output=True, text=True).stdout.strip())
        except:
            term_height = 24
        
        if len(lines) > term_height:
            pager = os.environ.get("PAGER", "less -R")
            try:
                subprocess.run(pager.split(), input=output, text=True, check=True)
                return
            except:
                pass
    
    # Fallback: just print
    print(output)


def parse_issue_frontmatter(content: str) -> dict[str, Any]:
    """
    Parse issue from frontmatter + body format.
    Format:
    ---
    title: Issue title
    type: feat
    areas: web, api
    phase: 1
    ---
    Body content here
    """
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError("Invalid format: expected --- frontmatter ---")
    
    frontmatter_text = parts[1].strip()
    body = parts[2].strip()
    
    # Parse frontmatter (simple key: value format)
    issue_spec = {"body": body}
    for line in frontmatter_text.split("\n"):
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        
        if key == "title":
            issue_spec["title"] = value
        elif key == "type":
            issue_spec["type"] = value
        elif key == "areas":
            issue_spec["areas"] = [a.strip() for a in value.split(",") if a.strip()] if value else []
        elif key == "phase":
            issue_spec["phase"] = int(value) if value and value != "ninguna" else None
    
    return issue_spec


def format_issue_frontmatter(issue_spec: dict[str, Any]) -> str:
    """Format issue spec as frontmatter + body for editing."""
    lines = ["---"]
    lines.append(f"title: {issue_spec['title']}")
    lines.append(f"type: {issue_spec['type']}")
    areas = issue_spec.get('areas', [])
    lines.append(f"areas: {', '.join(areas) if areas else ''}")
    phase = issue_spec.get('phase')
    lines.append(f"phase: {phase if phase is not None else 'ninguna'}")
    lines.append("---")
    lines.append(issue_spec['body'])
    return "\n".join(lines)


def cmd_new(args):
    """Create a new issue (interactive or direct)."""
    # Non-interactive mode: direct creation
    if args.no_interview or (args.type and (args.body or args.body_file)):
        if not args.title:
            print("Error: title required for non-interactive mode", file=sys.stderr)
            sys.exit(1)
        
        title = args.title
        type_label = args.type
        
        body = args.body
        if args.body_file:
            with open(args.body_file, "r", encoding="utf-8") as f:
                body = f.read()
        elif not body:
            body = "## Contexto\n\n(Describir el problema o necesidad)\n\n## Criterios de aceptación\n\n- [ ] \n"
        
        number = create_issue_from_spec(title, type_label, args.area, args.phase, body)
        print(f"Created issue #{number}")
        return
    
    # Interactive mode: run interview
    try:
        import issue_agent
    except ImportError:
        # Add scripts dir to path
        scripts_dir = Path(__file__).parent
        sys.path.insert(0, str(scripts_dir))
        import issue_agent
    
    repo_root = git_toplevel()
    
    # Get LLM config
    try:
        base_url, api_key, model = issue_agent.get_llm_config()
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    client = issue_agent.LLMClient(base_url, api_key, model)
    sandbox = issue_agent.ToolSandbox(repo_root)
    
    # Handle --resume
    existing_messages = None
    session_id = None
    
    if args.resume:
        if args.resume == "last":
            session_path = issue_agent.get_last_session(repo_root)
            if not session_path:
                print("Error: No hay sesiones guardadas.", file=sys.stderr)
                sys.exit(1)
        else:
            session_path = args.resume
            if not os.path.exists(session_path):
                print(f"Error: Sesión no encontrada: {session_path}", file=sys.stderr)
                sys.exit(1)
        
        print(f"Cargando sesión desde {session_path}...")
        existing_messages, session_id = issue_agent.load_session(session_path)
    else:
        print("Iniciando entrevista interactiva para crear issue(s)...")
        print("Comandos disponibles: /listo, /borrador, /cancelar")
        print()
    
    initial_idea = args.title if args.title else ""
    spec, messages, session_id = issue_agent.run_interview(
        client, sandbox, repo_root, initial_idea,
        existing_messages=existing_messages,
        session_id=session_id
    )
    
    if not spec:
        print("Entrevista cancelada o sin resultado.")
        sys.exit(1)
    
    # Show preview and options loop
    while True:
        issues = spec["issues"]
        
        print("\n")
        show_preview(issues)
        
        print("\nOpciones:")
        print("  [c] Crear issue(s)")
        print("  [e] Editar")
        print("  [s] Seguir entrevistando")
        print("  [x] Cancelar")
        
        choice = input("\n> ").strip().lower()
        
        if choice == "c":
            # Create issues
            created = []
            for issue_spec in issues:
                number = create_issue_from_spec(
                    issue_spec["title"],
                    issue_spec["type"],
                    issue_spec.get("areas"),
                    issue_spec.get("phase"),
                    issue_spec["body"]
                )
                created.append(number)
                print(f"Created issue #{number}: {issue_spec['title']}")
            
            # Add cross-references if multiple issues
            if len(created) > 1:
                refs = ", ".join(f"#{n}" for n in created)
                for number in created:
                    result = run_command(["gh", "issue", "view", str(number), "--json", "body"])
                    issue_data = json.loads(result.stdout)
                    updated_body = issue_data["body"] + f"\n\n**Relacionado**: {refs}\n"
                    run_command(["gh", "issue", "edit", str(number), "--body", updated_body])
                print(f"\nAdded cross-references to all {len(created)} issues.")
            
            break
        
        elif choice == "e":
            # Edit
            if len(issues) == 1:
                # Single issue: edit with frontmatter
                content = format_issue_frontmatter(issues[0])
                edited = issue_agent.edit_in_editor(content)
                if edited:
                    try:
                        issues[0] = parse_issue_frontmatter(edited)
                        # Update spec
                        spec["issues"][0] = issues[0]
                        print("Issue actualizado.")
                    except ValueError as e:
                        print(f"Error parseando: {e}")
                else:
                    print("Edición cancelada.")
            else:
                # Multiple issues: choose which to edit
                print("\nSeleccioná qué issue editar (1-{}), o 0 para cancelar:".format(len(issues)))
                for i, iss in enumerate(issues, 1):
                    print(f"  [{i}] {iss['title']}")
                
                try:
                    idx = int(input("> ").strip())
                    if idx == 0:
                        continue
                    if idx < 1 or idx > len(issues):
                        print("Número inválido.")
                        continue
                    
                    content = format_issue_frontmatter(issues[idx - 1])
                    edited = issue_agent.edit_in_editor(content)
                    if edited:
                        try:
                            issues[idx - 1] = parse_issue_frontmatter(edited)
                            spec["issues"][idx - 1] = issues[idx - 1]
                            print("Issue actualizado.")
                        except ValueError as e:
                            print(f"Error parseando: {e}")
                    else:
                        print("Edición cancelada.")
                except ValueError:
                    print("Entrada inválida.")
        
        elif choice == "s":
            # Continue interview
            print("\nContinuando entrevista. Escribí tu pregunta o ajuste:\n")
            user_msg = input("> ").strip()
            if not user_msg:
                print("Cancelado.")
                continue
            
            # Append user message and continue interview
            messages.append({"role": "user", "content": user_msg})
            
            new_spec, messages, session_id = issue_agent.run_interview(
                client, sandbox, repo_root, "",
                existing_messages=messages,
                session_id=session_id
            )
            
            if new_spec:
                spec = new_spec
            else:
                print("No se obtuvo nueva especificación.")
        
        elif choice == "x":
            print("Cancelado.")
            sys.exit(0)
        
        else:
            print("Opción inválida. Usá c/e/s/x.")


def cmd_list(args):
    """List open issues."""
    state = "all" if args.all else "open"
    result = run_command([
        "gh", "issue", "list",
        "--state", state,
        "--limit", "500",
        "--json", "number,title,state,labels,milestone,assignees"
    ])
    
    issues = json.loads(result.stdout)
    
    if not issues:
        print("No issues found.")
        return
    
    # Table header
    print(f"{'#':<6} {'Status':<12} {'Type':<10} {'Milestone':<25} {'Title'}")
    print("-" * 100)
    
    for issue in issues:
        num = issue["number"]
        labels = {l["name"] for l in issue["labels"]}
        
        status = next((l for l in labels if l.startswith("status:")), "")
        status = status.replace("status:", "") if status else "-"
        
        type_label = next((l for l in labels if l.startswith("type:")), "")
        type_label = type_label.replace("type:", "") if type_label else "-"
        
        milestone = issue["milestone"]["title"] if issue.get("milestone") else "-"
        title = issue["title"][:50]
        
        print(f"#{num:<5} {status:<12} {type_label:<10} {milestone:<25} {title}")


def cmd_take(args):
    """Take an issue: create branch, assign, mark WIP."""
    issue_num = args.issue
    
    if not is_working_tree_clean():
        print("Error: Working tree is dirty. Commit or stash changes first.", file=sys.stderr)
        sys.exit(1)
    
    # Fetch issue details
    result = run_command([
        "gh", "issue", "view", str(issue_num),
        "--json", "number,title,state,labels,assignees"
    ])
    issue = json.loads(result.stdout)
    
    if issue["state"] == "CLOSED":
        print(f"Error: Issue #{issue_num} is already closed.", file=sys.stderr)
        sys.exit(1)
    
    labels = {l["name"] for l in issue["labels"]}
    assignees = [a["login"] for a in issue["assignees"]]
    
    # Check if already WIP by someone else
    result = run_command(["gh", "api", "user", "-q", ".login"])
    current_user = result.stdout.strip()
    
    if "status:wip" in labels and assignees and current_user not in assignees:
        print(f"Error: Issue #{issue_num} is already WIP by {assignees[0]}.", file=sys.stderr)
        sys.exit(1)
    
    # Update to main
    default_branch = get_default_branch()
    run_command(["git", "fetch"])
    run_command(["git", "checkout", default_branch])
    run_command(["git", "pull", "--ff-only"])
    
    # Create or checkout branch
    branch_name = f"issue/{issue_num}-{slugify(issue['title'])}"
    result = run_command(["git", "show-ref", "--verify", f"refs/heads/{branch_name}"], check=False)
    
    if result.returncode == 0:
        # Branch exists, just checkout
        run_command(["git", "checkout", branch_name])
        print(f"Checked out existing branch: {branch_name}")
    else:
        # Create new branch
        run_command(["git", "checkout", "-b", branch_name])
        run_command(["git", "push", "-u", "origin", branch_name])
        print(f"Created branch: {branch_name}")
    
    # Assign to me
    run_command(["gh", "issue", "edit", str(issue_num), "--add-assignee", "@me"])
    
    # Update labels: remove status:todo, add status:wip
    if "status:todo" in labels:
        run_command(["gh", "issue", "edit", str(issue_num), "--remove-label", "status:todo"])
    if "status:wip" not in labels:
        run_command(["gh", "issue", "edit", str(issue_num), "--add-label", "status:wip"])
    
    # Comment on issue
    run_command([
        "gh", "issue", "comment", str(issue_num),
        "--body", f"🚧 Tomado. Rama: `{branch_name}`"
    ])
    
    print(f"Issue #{issue_num} is now WIP on branch {branch_name}")


def cmd_pr(args):
    """Create PR for current issue branch."""
    issue_num = args.issue
    branch = current_branch()
    default_branch = get_default_branch()
    
    if branch == default_branch:
        print(f"Error: Cannot create PR from {default_branch} branch.", file=sys.stderr)
        sys.exit(1)
    
    # Verify we have commits ahead of main
    result = run_command(["git", "rev-list", f"{default_branch}..HEAD", "--count"])
    ahead = int(result.stdout.strip())
    
    if ahead == 0:
        print(f"Error: No commits ahead of {default_branch}.", file=sys.stderr)
        sys.exit(1)
    
    # Push branch
    run_command(["git", "push", "-u", "origin", branch])
    
    # Get issue details
    result = run_command([
        "gh", "issue", "view", str(issue_num),
        "--json", "title"
    ])
    issue = json.loads(result.stdout)
    pr_title = f"{issue['title']} (#{issue_num})"
    
    # Get commit summary
    result = run_command(["git", "log", f"{default_branch}..HEAD", "--oneline"])
    commit_summary = result.stdout.strip()
    
    pr_body = f"Closes #{issue_num}\n\n## Commits\n```\n{commit_summary}\n```"
    
    # Check if PR already exists
    result = run_command([
        "gh", "pr", "list",
        "--head", branch,
        "--json", "url"
    ], check=False)
    
    if result.returncode == 0:
        existing_prs = json.loads(result.stdout)
        if existing_prs:
            print(f"PR already exists: {existing_prs[0]['url']}")
            return
    
    # Create PR
    cmd = [
        "gh", "pr", "create",
        "--title", pr_title,
        "--body", pr_body,
        "--base", default_branch
    ]
    
    if args.draft:
        cmd.append("--draft")
    
    result = run_command(cmd)
    pr_url = result.stdout.strip()
    
    # Update issue labels
    run_command(["gh", "issue", "edit", str(issue_num), "--remove-label", "status:wip"])
    run_command(["gh", "issue", "edit", str(issue_num), "--add-label", "status:review"])
    
    print(f"PR created: {pr_url}")


def cmd_merge(args):
    """Merge PR for an issue."""
    issue_num = args.issue
    default_branch = get_default_branch()
    
    # Find PR for issue
    result = run_command([
        "gh", "pr", "list",
        "--search", f"#{issue_num} in:title",
        "--json", "number,url,headRefName",
        "--state", "open"
    ])
    prs = json.loads(result.stdout)
    
    if not prs:
        print(f"Error: No open PR found for issue #{issue_num}.", file=sys.stderr)
        sys.exit(1)
    
    pr = prs[0]
    pr_number = pr["number"]
    
    # Check PR checks
    result = run_command(["gh", "pr", "checks", str(pr_number)], check=False)
    if "fail" in result.stdout.lower():
        print(f"Warning: PR #{pr_number} has failing checks:", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        response = input("Continue anyway? [y/N] ")
        if response.lower() != "y":
            sys.exit(1)
    
    # Merge PR
    run_command(["gh", "pr", "merge", str(pr_number), "--squash", "--delete-branch"])
    
    # Checkout and update main
    run_command(["git", "checkout", default_branch])
    run_command(["git", "pull", "--ff-only"])
    
    print(f"PR #{pr_number} merged successfully. Issue #{issue_num} closed.")


def render_backlog(issues: list[dict[str, Any]]) -> str:
    """Pure function to render backlog.md from issues list."""
    lines = [
        "# Backlog",
        "",
        "> Generado automáticamente desde GitHub Issues por `scripts/backlog.py render`. No editar a mano.",
        "",
    ]
    
    # Categorize issues
    wip = []
    review = []
    todo_by_milestone = {}
    done = []
    
    for issue in issues:
        labels = {l["name"] for l in issue["labels"]}
        is_blocked = "blocked" in labels
        
        status = None
        for label in labels:
            if label.startswith("status:"):
                status = label.replace("status:", "")
                break
        
        type_label = next((l.replace("type:", "") for l in labels if l.startswith("type:")), "")
        assignees = issue.get("assignees", [])
        assignee_str = f"@{assignees[0]['login']}" if assignees else ""
        
        milestone = issue.get("milestone")
        milestone_title = milestone["title"] if milestone else "Sin fase"
        
        checkbox = "x" if issue["state"] == "CLOSED" else " "
        blocked_marker = "⛔ " if is_blocked else ""
        
        item = f"- [{checkbox}] {blocked_marker}[#{issue['number']}]({issue['url']}) {issue['title']}"
        if type_label:
            item += f" · {type_label}"
        if assignee_str:
            item += f" · {assignee_str}"
        
        if issue["state"] == "CLOSED":
            done.append((issue.get("closedAt", ""), item))
        elif status == "wip":
            wip.append(item)
        elif status == "review":
            review.append(item)
        else:
            if milestone_title not in todo_by_milestone:
                todo_by_milestone[milestone_title] = []
            todo_by_milestone[milestone_title].append(item)
    
    # WIP section
    lines.append("## 🚧 En curso (WIP)")
    lines.append("")
    if wip:
        lines.extend(wip)
    else:
        lines.append("_Nada por ahora._")
    lines.append("")
    
    # Review section
    lines.append("## 👀 En revisión")
    lines.append("")
    if review:
        lines.extend(review)
    else:
        lines.append("_Nada por ahora._")
    lines.append("")
    
    # Todo section
    lines.append("## 📋 Pendiente")
    lines.append("")
    
    # Order milestones
    milestone_order = [
        "Fase 0 - Fundaciones",
        "Fase 1 - MVP individual",
        "Fase 2 - Retención y comunidad",
        "Fase 3 - Calidad y escala",
        "Sin fase",
    ]
    
    has_todo = False
    for milestone_title in milestone_order:
        if milestone_title in todo_by_milestone:
            has_todo = True
            lines.append(f"### {milestone_title}")
            lines.append("")
            lines.extend(todo_by_milestone[milestone_title])
            lines.append("")
    
    if not has_todo:
        lines.append("_Nada por ahora._")
        lines.append("")
    
    # Done section (most recent first, max 50)
    lines.append("## ✅ Hecho")
    lines.append("")
    if done:
        done.sort(key=lambda x: x[0], reverse=True)
        for _, item in done[:50]:
            lines.append(item)
    else:
        lines.append("_Nada por ahora._")
    lines.append("")
    
    return "\n".join(lines)


def cmd_render(args):
    """Render backlog.md from GitHub issues."""
    result = run_command([
        "gh", "issue", "list",
        "--state", "all",
        "--limit", "500",
        "--json", "number,title,state,labels,milestone,assignees,closedAt,url"
    ])
    
    issues = json.loads(result.stdout)
    content = render_backlog(issues)
    
    repo_root = git_toplevel()
    backlog_path = os.path.join(repo_root, "backlog.md")
    
    if args.check:
        # Check if file would change
        try:
            with open(backlog_path, "r", encoding="utf-8") as f:
                existing = f.read()
            if existing != content:
                print("backlog.md would change.", file=sys.stderr)
                sys.exit(1)
            else:
                print("backlog.md is up to date.")
        except FileNotFoundError:
            print("backlog.md does not exist yet.", file=sys.stderr)
            sys.exit(1)
    else:
        # Write file
        with open(backlog_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Rendered backlog.md ({len(issues)} issues)")


def cmd_sync(args):
    """Sync backlog.md and commit if changed (on main only)."""
    branch = current_branch()
    default_branch = get_default_branch()
    
    if branch != default_branch:
        print(f"Error: sync can only run on {default_branch} branch.", file=sys.stderr)
        sys.exit(1)
    
    # Render
    cmd_render(argparse.Namespace(check=False))
    
    # Check if changed
    result = run_command(["git", "status", "--porcelain", "backlog.md"])
    if not result.stdout.strip():
        print("backlog.md is already up to date.")
        return
    
    # Commit and push
    run_command(["git", "add", "backlog.md"])
    run_command(["git", "commit", "-m", "docs: sync backlog.md [skip ci]"])
    run_command(["git", "push"])
    print("backlog.md synchronized and pushed.")


def cmd_status(args):
    """Show current branch and linked issue status."""
    branch = current_branch()
    print(f"Branch: {branch}")
    
    issue_num = parse_issue_number_from_branch(branch)
    if not issue_num:
        print("No linked issue (not an issue branch)")
        return
    
    print(f"Issue: #{issue_num}")
    
    result = run_command([
        "gh", "issue", "view", str(issue_num),
        "--json", "title,state,labels,url"
    ], check=False)
    
    if result.returncode != 0:
        print("(Issue not found)")
        return
    
    issue = json.loads(result.stdout)
    print(f"Title: {issue['title']}")
    print(f"State: {issue['state']}")
    
    labels = [l["name"] for l in issue["labels"]]
    if labels:
        print(f"Labels: {', '.join(labels)}")
    
    print(f"URL: {issue['url']}")


def main():
    parser = argparse.ArgumentParser(description="Issue management harness")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # init
    subparsers.add_parser("init", help="Initialize labels and milestones")
    
    # new
    new_parser = subparsers.add_parser("new", help="Create new issue")
    new_parser.add_argument("title", nargs="?", help="Issue title or initial idea (optional for interactive mode)")
    new_parser.add_argument("--type", choices=["feat", "fix", "chore", "docs", "infra"], help="Issue type (required for non-interactive)")
    new_parser.add_argument("--area", action="append", help="Area label(s)")
    new_parser.add_argument("--phase", type=int, choices=[0, 1, 2, 3], help="Phase milestone")
    new_parser.add_argument("--body", help="Issue body text")
    new_parser.add_argument("--body-file", help="Read body from file")
    new_parser.add_argument("--no-interview", action="store_true", help="Skip interactive interview")
    new_parser.add_argument("--resume", help="Resume from saved session: path to .json file or 'last' for most recent")
    
    # list
    list_parser = subparsers.add_parser("list", help="List issues")
    list_parser.add_argument("--all", action="store_true", help="Include closed issues")
    
    # take
    take_parser = subparsers.add_parser("take", help="Take an issue")
    take_parser.add_argument("issue", type=int, help="Issue number")
    
    # pr
    pr_parser = subparsers.add_parser("pr", help="Create PR for issue")
    pr_parser.add_argument("issue", type=int, help="Issue number")
    pr_parser.add_argument("--draft", action="store_true", help="Create as draft PR")
    
    # merge
    merge_parser = subparsers.add_parser("merge", help="Merge PR for issue")
    merge_parser.add_argument("issue", type=int, help="Issue number")
    
    # render
    render_parser = subparsers.add_parser("render", help="Render backlog.md")
    render_parser.add_argument("--check", action="store_true", help="Exit 1 if file would change")
    
    # sync
    subparsers.add_parser("sync", help="Sync backlog.md and commit if changed")
    
    # status
    subparsers.add_parser("status", help="Show current branch and issue status")
    
    args = parser.parse_args()
    
    # Dispatch to command handler
    cmd_map = {
        "init": cmd_init,
        "new": cmd_new,
        "list": cmd_list,
        "take": cmd_take,
        "pr": cmd_pr,
        "merge": cmd_merge,
        "render": cmd_render,
        "sync": cmd_sync,
        "status": cmd_status,
    }
    
    cmd_map[args.command](args)


if __name__ == "__main__":
    main()

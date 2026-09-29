#!/usr/bin/env python3
"""
TDD implementation runner controlled by the harness.
Executes RED → GREEN → REFACTOR phases with verification and rollback.
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

# Add scripts dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from take_agent import parse_spec_markdown, set_status, mark_progress


# Empty run detection patterns (compiled regexes, anchored at line start)
EMPTY_RUN_SIGNALS = [
    re.compile(r"^\s*No projects matched the filters", re.MULTILINE),
    re.compile(r"^\s*No test files found", re.MULTILINE),
    re.compile(r"^\s*Ran 0 tests\b", re.MULTILINE),
]

# Dependency infrastructure filenames (allowed in RED, always allowed in GREEN)
DEPENDENCY_INFRA_FILENAMES = {
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
    "package-lock.json",
    "yarn.lock",
    "poetry.lock",
    "uv.lock",
}

# Maximum /DESVIOs allowed per phase before stopping
MAX_DESVIOS_PER_PHASE = 3


def is_dependency_infra_file(path: str) -> bool:
    """
    Check if a file is a dependency infrastructure file (lockfile, requirements.txt).
    
    These files are always allowed in RED (not counted as production code).
    
    Matches:
    - Known lockfiles (basename match): pnpm-lock.yaml, package-lock.json, yarn.lock, 
      poetry.lock, uv.lock, pnpm-workspace.yaml
    - requirements*.txt pattern (e.g. requirements.txt, requirements-dev.txt)
    
    Args:
        path: File path (relative or absolute)
    
    Returns:
        True if the file is a dependency infra file, False otherwise.
    """
    basename = Path(path).name
    
    # Check known lockfiles
    if basename in DEPENDENCY_INFRA_FILENAMES:
        return True
    
    # Check requirements*.txt pattern
    if basename.startswith("requirements") and basename.endswith(".txt"):
        return True
    
    return False


def build_coder_cmd(prompt: str, env: dict[str, str] | None = None) -> list[str]:
    """
    Build coder command from environment configuration.
    
    Args:
        prompt: The prompt to pass to the coder
        env: Environment dict (defaults to os.environ)
    
    Returns list of command parts ready for subprocess.run()
    """
    if env is None:
        env = os.environ
    
    # Get base command (default: ~/.local/bin/oc run)
    coder_cmd = env.get("BACKLOG_CODER_CMD", "~/.local/bin/oc run")
    
    # Expand ~ and split with shlex
    coder_cmd = os.path.expanduser(coder_cmd)
    cmd_parts = shlex.split(coder_cmd)
    
    # Add model if specified
    model = env.get("BACKLOG_CODER_MODEL", "nous/anthropic/claude-sonnet-4.5")
    if model.strip():
        cmd_parts.extend(["--model", model])
    
    # Add prompt
    cmd_parts.append(prompt)
    
    return cmd_parts


def build_test_cmd(test_command: str) -> list[str]:
    """
    Build test command for execution.
    
    Returns ["sh", "-c", test_command] if the command contains shell operators
    (&&, ||, |, ;, >, <, $(), or backticks), otherwise shlex.split(test_command).
    
    Args:
        test_command: The test command string
    
    Returns:
        List of command arguments for subprocess.run
    """
    shell_operators = ["&&", "||", "|", ";", ">", "<", "$(", "`"]
    
    if any(op in test_command for op in shell_operators):
        return ["sh", "-c", test_command]
    else:
        return shlex.split(test_command)


def is_test_file(path: str) -> bool:
    """
    Check if a path is a test file.
    
    Matches Python and JS/TS test files:
    - Python: starts with tests/, contains /test_, or ends with _test.py/.test.py/.spec.py
    - JS/TS: ends with .test.{ts,tsx,js,jsx,mjs,cjs} or .spec.{ts,tsx,js,jsx,mjs,cjs}
    - Any path containing a segment "test", "tests" or "__tests__"
      (e.g. apps/api/test/health.test.ts, packages/shared/__tests__/x.ts)
    
    Does NOT match things like "src/contest.ts" or "latest/foo.ts"
    (must be a full path segment).
    """
    path_lower = path.lower()
    
    # Python patterns
    if (path.startswith("tests/") or
        "/test_" in path or
        path_lower.endswith("_test.py") or
        path_lower.endswith(".test.py") or
        path_lower.endswith(".spec.py")):
        return True
    
    # JS/TS test file extensions
    js_ts_test_exts = [
        ".test.ts", ".test.tsx", ".test.js", ".test.jsx", ".test.mjs", ".test.cjs",
        ".spec.ts", ".spec.tsx", ".spec.js", ".spec.jsx", ".spec.mjs", ".spec.cjs"
    ]
    if any(path_lower.endswith(ext) for ext in js_ts_test_exts):
        return True
    
    # Check if path contains a full segment "test", "tests", or "__tests__"
    # Split by / and check each segment
    segments = path.split("/")
    test_segments = {"test", "tests", "__tests__"}
    if any(seg.lower() in test_segments for seg in segments):
        return True
    
    return False


def get_changed_files(repo_root: str, run_cmd: Callable) -> list[str]:
    """
    Get list of changed files from git status --porcelain.
    
    Uses --untracked-files=all to list individual files in new directories.
    Handles renames (R  old -> new) by taking the new path.
    Handles quoted paths with escapes.
    """
    result = run_cmd(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=repo_root,
        timeout=5
    )
    
    if result.returncode != 0:
        return []
    
    changed = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        
        # Format: "XY path" or "XY old -> new" for renames
        # Paths may be quoted if they contain special chars
        status = line[:2]
        path_part = line[3:]  # Skip "XY "
        
        # Handle renames: "R  old -> new"
        if status.strip().startswith("R"):
            if " -> " in path_part:
                # Take the new path
                path_part = path_part.split(" -> ", 1)[1]
        
        # Handle quoted paths: git quotes paths with special chars and escapes spaces/quotes
        if path_part.startswith('"') and path_part.endswith('"'):
            # Remove quotes and unescape (simple: just remove backslashes before common chars)
            path_part = path_part[1:-1].replace('\\"', '"').replace('\\\\', '\\')
        
        changed.append(path_part)
    
    return changed


def get_file_hashes(repo_root: str, files: list[str], run_cmd: Callable) -> dict[str, str]:
    """Get git hash-object for a list of files."""
    hashes = {}
    for file_path in files:
        full_path = Path(repo_root) / file_path
        if full_path.exists():
            result = run_cmd(
                ["git", "hash-object", str(full_path)],
                cwd=repo_root,
                timeout=5
            )
            if result.returncode == 0:
                hashes[file_path] = result.stdout.strip()
    return hashes


def revert_files(repo_root: str, files: list[str], run_cmd: Callable) -> None:
    """Revert specific files to HEAD."""
    if not files:
        return
    
    # Revert tracked changes
    run_cmd(
        ["git", "checkout", "--"] + files,
        cwd=repo_root,
        timeout=10
    )
    
    # Clean untracked files in those paths
    for file_path in files:
        full_path = Path(repo_root) / file_path
        if full_path.exists():
            result = run_cmd(
                ["git", "ls-files", file_path],
                cwd=repo_root,
                timeout=5
            )
            # If file is not tracked, remove it
            if not result.stdout.strip():
                if full_path.is_dir():
                    shutil.rmtree(full_path, ignore_errors=True)
                else:
                    full_path.unlink(missing_ok=True)


def detect_desvio(output: str) -> str | None:
    """Detect /DESVIO marker in coder output. Returns the explanation or None."""
    match = re.search(r"/DESVIO\s+(.+)", output, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def detect_empty_run(output: str) -> str | None:
    """
    Detect if test run was empty (no tests executed).
    
    Strips ANSI escape sequences from output and matches against line-anchored
    regex patterns. Returns the matched line (stripped) if empty run detected,
    None otherwise.
    """
    # Strip ANSI escape sequences
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    clean_output = ansi_escape.sub('', output)
    
    for pattern in EMPTY_RUN_SIGNALS:
        match = pattern.search(clean_output)
        if match:
            return match.group(0).strip()
    return None


def append_decision_to_spec(
    spec_path: str,
    topic: str,
    chosen: str,
    run_cmd: Callable
) -> None:
    """
    Append a new decision to the spec file.
    
    Finds the highest existing decision ID (D1, D2, ...) and adds Dx+1.
    Re-renders the decisions table deterministically.
    """
    with open(spec_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Parse existing spec
    metadata, spec, progress = parse_spec_markdown(content)
    
    # Find highest decision ID
    max_id = 0
    for decision in spec["decisions"]:
        match = re.match(r"D(\d+)", decision["id"])
        if match:
            max_id = max(max_id, int(match.group(1)))
    
    new_id = f"D{max_id + 1}"
    
    # Add new decision
    spec["decisions"].append({
        "id": new_id,
        "topic": topic,
        "options": [chosen],
        "chosen": chosen,
        "rationale": "Decisión tomada durante implementación"
    })
    
    # Re-render decisions table
    # Find the table in content and replace it
    table_pattern = r"(## Decisiones de diseño\s*\n\s*\n\|.*?\n\|.*?\n)(.*?)(\n\n##)"
    
    new_rows = []
    for decision in spec["decisions"]:
        id_str = decision["id"]
        topic = decision["topic"].replace("|", "\\|")
        options_str = ", ".join(decision["options"]).replace("|", "\\|")
        chosen = decision["chosen"].replace("|", "\\|")
        rationale = decision["rationale"].replace("|", "\\|")
        new_rows.append(f"| {id_str} | {topic} | {options_str} | {chosen} | {rationale} |")
    
    new_table = "\n".join(new_rows)
    
    content = re.sub(
        table_pattern,
        rf"\1{new_table}\3",
        content,
        flags=re.DOTALL
    )
    
    with open(spec_path, "w", encoding="utf-8") as f:
        f.write(content)


def run_tdd_implementation(
    repo_root: str,
    issue_num: int,
    coder: Callable[[str, str], tuple[int, str]] | None = None,
    run_cmd: Callable[[list[str], str, int], subprocess.CompletedProcess] | None = None,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print
) -> bool:
    """
    Run TDD implementation for an issue.
    
    Args:
        repo_root: Repository root path
        issue_num: Issue number
        coder: Coder function (prompt, log_path) -> (exit_code, output)
               If None, uses build_coder_cmd to construct command
        run_cmd: Command runner (cmd, cwd, timeout) -> CompletedProcess
                 If None, uses subprocess.run
        input_fn: Input function (for testing)
        print_fn: Print function (for testing)
    
    Returns True if implementation completes successfully, False otherwise.
    """
    if run_cmd is None:
        def default_run_cmd(cmd: list[str], cwd: str = None, timeout: int = None) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd,
                cwd=cwd or repo_root,
                capture_output=True,
                text=True,
                timeout=timeout
            )
        run_cmd = default_run_cmd
    
    if coder is None:
        # Build default coder from env
        def default_coder(prompt: str, log_path: str) -> tuple[int, str]:
            cmd = build_coder_cmd(prompt)
            timeout = int(os.environ.get("BACKLOG_CODER_TIMEOUT", "1800"))
            
            # Ensure log directory exists
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            
            result = run_cmd(cmd, cwd=repo_root, timeout=timeout)
            
            # Write log
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"Command: {' '.join(cmd)}\n")
                f.write(f"Exit code: {result.returncode}\n")
                f.write(f"Stdout:\n{result.stdout}\n")
                f.write(f"Stderr:\n{result.stderr}\n")
            
            return result.returncode, result.stdout
        
        coder = default_coder
    
    # Load spec
    spec_path = Path(repo_root) / "docs" / "specs" / f"issue-{issue_num}.md"
    if not spec_path.exists():
        print_fn(f"Error: spec no encontrada en {spec_path}")
        return False
    
    with open(spec_path, "r", encoding="utf-8") as f:
        spec_content = f.read()
    
    metadata, spec, progress = parse_spec_markdown(spec_content)
    
    # Verify status
    status = metadata.get("status", "")
    if status not in ["approved", "implementing"]:
        print_fn(f"Error: spec debe estar en estado 'approved' o 'implementing', está en '{status}'")
        return False
    
    # Set status to implementing if not already
    if status == "approved":
        set_status(str(spec_path), "implementing")
        run_cmd(["git", "add", str(spec_path)], cwd=repo_root, timeout=5)
        run_cmd(
            ["git", "commit", "-m", f"docs: iniciando implementación (#{issue_num})"],
            cwd=repo_root,
            timeout=10
        )
    
    test_command = metadata.get("test_command", "")
    if not test_command:
        print_fn("Error: test_command vacío en spec")
        return False
    
    test_cmd = build_test_cmd(test_command)
    
    # Create logs directory
    logs_dir = Path(repo_root) / ".backlog" / "runs" / f"issue-{issue_num}"
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Find first pending task
    for task in spec["tasks"]:
        task_id = task["id"]
        task_progress = progress.get(task_id, {"red": False, "green": False, "refactor": False})
        
        # Determine which phase to resume from
        if not task_progress["red"]:
            phases_to_run = ["red", "green", "refactor"]
        elif not task_progress["green"]:
            phases_to_run = ["green", "refactor"]
        elif not task_progress["refactor"]:
            phases_to_run = ["refactor"]
        else:
            # Task complete, skip
            continue
        
        print_fn(f"\n=== Tarea {task_id}: {task['title']} ===\n")
        
        for phase in phases_to_run:
            print_fn(f"--- Fase {phase.upper()} ---\n")
            
            # Check working tree is clean
            result = run_cmd(["git", "status", "--porcelain"], cwd=repo_root, timeout=5)
            if result.stdout.strip():
                print_fn("Error: working tree sucio. Commitea o stashea los cambios.")
                return False
            
            if phase == "red":
                success = run_red_phase(
                    repo_root, issue_num, task, spec, spec_path,
                    test_cmd, logs_dir, coder, run_cmd, input_fn, print_fn
                )
                if not success:
                    return False
            
            elif phase == "green":
                success = run_green_phase(
                    repo_root, issue_num, task, spec, spec_path,
                    test_cmd, logs_dir, coder, run_cmd, input_fn, print_fn
                )
                if not success:
                    return False
            
            elif phase == "refactor":
                success = run_refactor_phase(
                    repo_root, issue_num, task, spec, spec_path,
                    test_cmd, logs_dir, coder, run_cmd, input_fn, print_fn
                )
                if not success:
                    return False
    
    # All tasks complete
    print_fn("\n=== Implementación completa ===\n")
    
    # Set status to done
    set_status(str(spec_path), "done")
    run_cmd(["git", "add", str(spec_path)], cwd=repo_root, timeout=5)
    run_cmd(
        ["git", "commit", "-m", f"docs: spec completada (#{issue_num})"],
        cwd=repo_root,
        timeout=10
    )
    
    print_fn(f"Siguiente paso: python3 scripts/backlog.py pr {issue_num}")
    
    return True


def run_red_phase(
    repo_root: str,
    issue_num: int,
    task: dict[str, Any],
    spec: dict[str, Any],
    spec_path: Path,
    test_cmd: list[str],
    logs_dir: Path,
    coder: Callable,
    run_cmd: Callable,
    input_fn: Callable,
    print_fn: Callable
) -> bool:
    """
    Run RED phase: write tests that fail.
    
    Returns True if successful, False otherwise.
    """
    task_id = task["id"]
    max_attempts = 2  # Initial + 1 retry
    last_feedback = None
    last_decision = None  # Decision from last /DESVIO
    desvio_count = 0  # Track /DESVIO count for cap
    
    attempt = 0
    while attempt < max_attempts:
        # Build prompt
        prompt = build_red_prompt(spec, task)
        
        # Append decision from last /DESVIO if any
        if last_decision:
            prompt += f"\n\n**Decisión tomada para tu /DESVIO:** {last_decision}\n"
        
        # Append feedback from previous attempt if any
        if last_feedback:
            prompt += f"\n\n**Feedback del intento anterior:**\n\n{last_feedback}\n"
        
        # Call coder
        log_path = logs_dir / f"{task_id}-red-{attempt + 1}.log"
        print_fn(f"Invocando coder (intento {attempt + 1}/{max_attempts})...")
        
        exit_code, output = coder(prompt, str(log_path))
        
        if exit_code != 0:
            print_fn(f"Error: coder falló con código {exit_code}")
            user_choice = input_fn("Reintentar o abortar? (r/abortar): ").strip().lower()
            if user_choice != "reintentar":
                return False
            attempt += 1
            continue
        
        # Check for /DESVIO
        if desvio := detect_desvio(output):
            desvio_count += 1
            
            # Check cap
            if desvio_count > MAX_DESVIOS_PER_PHASE:
                print_fn(f"\nError: se alcanzó el límite de {MAX_DESVIOS_PER_PHASE} desvíos por fase.")
                print_fn("La fase RED no puede completarse con tantas decisiones adicionales.")
                return False
            
            print_fn(f"\n/DESVIO detectado: {desvio}\n")
            print_fn("¿Cuál es tu decisión?")
            decision = input_fn("> ").strip()
            
            # Revert uncommitted changes
            changed = get_changed_files(repo_root, run_cmd)
            if changed:
                revert_files(repo_root, changed, run_cmd)
            
            # Append decision to spec
            append_decision_to_spec(str(spec_path), desvio, decision, run_cmd)
            
            # Commit decision
            run_cmd(["git", "add", str(spec_path)], cwd=repo_root, timeout=5)
            run_cmd(
                ["git", "commit", "-m", f"docs: decisión durante implementación (#{issue_num})"],
                cwd=repo_root,
                timeout=10
            )
            
            print_fn("Decisión registrada. Reintentando fase RED...\n")
            
            # Store decision for next prompt, DO NOT consume attempt
            last_decision = decision
            continue
        
        # Clear last_decision and last_feedback after successful non-/DESVIO call
        last_decision = None
        
        # Verify only test files were changed
        changed = get_changed_files(repo_root, run_cmd)
        
        if not changed:
            print_fn("Advertencia: coder no modificó ningún archivo.")
            if attempt < max_attempts - 1:
                print_fn("Reintentando...\n")
                attempt += 1
                continue
            else:
                user_choice = input_fn("Continuar o abortar? (continuar/abortar): ").strip().lower()
                if user_choice != "reintentar":
                    return False
                break
        
        # Check if non-test files were modified
        # Allowed in RED: test files (by pattern or listed in tests[].file), test_support_files,
        # and dependency infra files (lockfiles, requirements.txt)
        test_files_in_task = [t["file"] for t in task["tests"]]
        test_support_files = task.get("test_support_files", [])
        impl_files = task.get("impl_files", [])
        allowed_in_red = set(test_files_in_task + test_support_files)
        
        non_test_changes = []
        for f in changed:
            # Skip if it's a test file (by pattern or in task.tests)
            if is_test_file(f) or f in allowed_in_red:
                continue
            # Skip if it's a dependency infra file
            if is_dependency_infra_file(f):
                continue
            # Reject if it's in impl_files (explicitly forbidden)
            if f in impl_files:
                non_test_changes.append(f)
                continue
            # Otherwise it's a non-test, non-allowed file
            non_test_changes.append(f)
        
        if non_test_changes:
            print_fn(f"Error: se modificaron archivos de producción en RED: {non_test_changes}")
            print_fn("Revirtiendo cambios de producción...")
            revert_files(repo_root, non_test_changes, run_cmd)
            
            if attempt < max_attempts - 1:
                print_fn("Reintentando RED...\n")
                attempt += 1
                continue
            else:
                user_choice = input_fn("Continuar o abortar? (continuar/abortar): ").strip().lower()
                if user_choice != "reintentar":
                    return False
                break
        
        # Run tests (must FAIL)
        print_fn("Ejecutando tests...")
        test_result = run_cmd(test_cmd, cwd=repo_root, timeout=300)
        
        # Check for empty run (no tests executed)
        combined_output = test_result.stdout + "\n" + test_result.stderr
        empty_signal = detect_empty_run(combined_output)
        
        if empty_signal:
            print_fn(f"Error: no se ejecutó ningún test: {empty_signal}")
            print_fn("Los archivos de soporte de tests deben permitir que el runner encuentre los tests.")
            
            # Revert and retry with feedback
            if changed:
                revert_files(repo_root, changed, run_cmd)
            
            if attempt < max_attempts - 1:
                print_fn("Reintentando RED con feedback...\n")
                last_feedback = f"No se ejecutó ningún test: {empty_signal}\n\nCreá los test_support_files necesarios para que el runner encuentre los tests."
                attempt += 1
                continue
            else:
                user_choice = input_fn("Continuar o abortar? (continuar/abortar): ").strip().lower()
                if user_choice != "reintentar":
                    return False
                break
        
        if test_result.returncode == 0:
            print_fn("Error: tests pasaron en fase RED (deberían fallar)")
            
            # First RED of the run: ask user if it's infrastructure error
            if attempt == 0:
                print_fn("\nOutput de tests:\n")
                print_fn(test_result.stdout[-1000:] if len(test_result.stdout) > 1000 else test_result.stdout)
                print_fn("\n¿Es esto un error de infraestructura (no un assert)? (y/n)")
                is_infra = input_fn("> ").strip().lower()
                
                if is_infra == "y":
                    print_fn("Error de infraestructura detectado. Abortando.")
                    return False
            
            # Revert and retry
            if changed:
                revert_files(repo_root, changed, run_cmd)
            
            if attempt < max_attempts - 1:
                print_fn("Reintentando RED...\n")
                attempt += 1
                continue
            else:
                user_choice = input_fn("Continuar o abortar? (continuar/abortar): ").strip().lower()
                if user_choice != "reintentar":
                    return False
                break
        
        # Tests failed as expected - commit
        print_fn("Tests fallan correctamente. Commiteando...")
        
        # Mark RED in spec
        mark_progress(str(spec_path), task_id, "red")
        
        run_cmd(["git", "add", "."], cwd=repo_root, timeout=10)
        run_cmd(
            ["git", "commit", "-m", f"test: {task['title']} (#{issue_num})"],
            cwd=repo_root,
            timeout=10
        )
        
        print_fn("RED completo.\n")
        return True
    
    # Exhausted attempts
    print_fn("No se pudo completar RED después de múltiples intentos.")
    return False


def run_green_phase(
    repo_root: str,
    issue_num: int,
    task: dict[str, Any],
    spec: dict[str, Any],
    spec_path: Path,
    test_cmd: list[str],
    logs_dir: Path,
    coder: Callable,
    run_cmd: Callable,
    input_fn: Callable,
    print_fn: Callable
) -> bool:
    """
    Run GREEN phase: implement minimum to pass tests.
    
    Returns True if successful, False otherwise.
    """
    task_id = task["id"]
    max_attempts = 3
    last_decision = None  # Decision from last /DESVIO
    desvio_count = 0  # Track /DESVIO count for cap
    
    # Record test file hashes after RED
    test_files = [t["file"] for t in task["tests"]]
    test_hashes = get_file_hashes(repo_root, test_files, run_cmd)
    
    attempt = 0
    while attempt < max_attempts:
        # Build prompt
        prompt = build_green_prompt(spec, task, attempt)
        
        # Append decision from last /DESVIO if any
        if last_decision:
            prompt += f"\n\n**Decisión tomada para tu /DESVIO:** {last_decision}\n"
        
        # If not first attempt, include last test output
        if attempt > 0:
            # Get last test output
            last_result = run_cmd(test_cmd, cwd=repo_root, timeout=300)
            prompt += f"\n\nÚltima salida de tests:\n```\n{last_result.stdout}\n{last_result.stderr}\n```"
        
        # Call coder
        log_path = logs_dir / f"{task_id}-green-{attempt + 1}.log"
        print_fn(f"Invocando coder (intento {attempt + 1}/{max_attempts})...")
        
        exit_code, output = coder(prompt, str(log_path))
        
        if exit_code != 0:
            print_fn(f"Error: coder falló con código {exit_code}")
            if attempt < max_attempts - 1:
                attempt += 1
                continue
            else:
                user_choice = input_fn("Reintentar o abortar? (reintentar/abortar): ").strip().lower()
                if user_choice == "reintentar":
                    # Increment BOTH to maintain the "last attempt" state
                    max_attempts += 1
                    attempt += 1
                    continue
                else:
                    return False
        
        # Check for /DESVIO
        if desvio := detect_desvio(output):
            desvio_count += 1
            
            # Check cap
            if desvio_count > MAX_DESVIOS_PER_PHASE:
                print_fn(f"\nError: se alcanzó el límite de {MAX_DESVIOS_PER_PHASE} desvíos por fase.")
                print_fn("La fase GREEN no puede completarse con tantas decisiones adicionales.")
                return False
            
            print_fn(f"\n/DESVIO detectado: {desvio}\n")
            print_fn("¿Cuál es tu decisión?")
            decision = input_fn("> ").strip()
            
            # Revert uncommitted changes
            changed = get_changed_files(repo_root, run_cmd)
            if changed:
                revert_files(repo_root, changed, run_cmd)
            
            # Append decision to spec
            append_decision_to_spec(str(spec_path), desvio, decision, run_cmd)
            
            # Commit decision
            run_cmd(["git", "add", str(spec_path)], cwd=repo_root, timeout=5)
            run_cmd(
                ["git", "commit", "-m", f"docs: decisión durante implementación (#{issue_num})"],
                cwd=repo_root,
                timeout=10
            )
            
            print_fn("Decisión registrada. Reintentando fase GREEN...\n")
            
            # Store decision for next prompt, DO NOT consume attempt
            last_decision = decision
            continue
        
        # Clear last_decision after successful non-/DESVIO call
        last_decision = None
        
        # Verify test files unchanged
        new_hashes = get_file_hashes(repo_root, test_files, run_cmd)
        
        if new_hashes != test_hashes:
            print_fn("Error: archivos de test fueron modificados en GREEN")
            # Revert test files
            revert_files(repo_root, test_files, run_cmd)
            
            if attempt < max_attempts - 1:
                print_fn("Reintentando GREEN...\n")
                attempt += 1
                continue
            else:
                user_choice = input_fn("Reintentar o abortar? (reintentar/abortar): ").strip().lower()
                if user_choice != "reintentar":
                    return False
                max_attempts += 1
                # Increment BOTH to maintain "last attempt" state
                attempt += 1
                continue
        
        # Run tests (must PASS)
        print_fn("Ejecutando tests...")
        test_result = run_cmd(test_cmd, cwd=repo_root, timeout=300)
        
        # Check for empty run
        combined_output = test_result.stdout + "\n" + test_result.stderr
        empty_signal = detect_empty_run(combined_output)
        
        if empty_signal:
            print_fn(f"Error: no se ejecutó ningún test: {empty_signal}")
            # Empty run counts as failed attempt
            
            if attempt < max_attempts - 1:
                print_fn("Reintentando GREEN...\n")
                attempt += 1
                continue
            else:
                user_choice = input_fn("Reintentar o abortar? (reintentar/abortar): ").strip().lower()
                if user_choice != "reintentar":
                    return False
                max_attempts += 1
                # Increment BOTH to maintain "last attempt" state
                attempt += 1
                continue
        
        if test_result.returncode != 0:
            print_fn(f"Tests fallaron (intento {attempt + 1}/{max_attempts})")
            
            if attempt < max_attempts - 1:
                print_fn("Reintentando GREEN...\n")
                attempt += 1
                continue
            else:
                user_choice = input_fn("Reintentar o abortar? (reintentar/abortar): ").strip().lower()
                if user_choice != "reintentar":
                    return False
                # Increment BOTH to maintain the "last attempt" state
                max_attempts += 1
                attempt += 1
                continue
        
        # Tests passed - commit
        print_fn("Tests pasan. Commiteando...")
        
        # Determine commit type from issue
        issue_labels = spec.get("labels", [])
        commit_type = "feat"  # Default
        if any("fix" in label.lower() for label in issue_labels):
            commit_type = "fix"
        
        # Mark GREEN in spec
        mark_progress(str(spec_path), task_id, "green")
        
        run_cmd(["git", "add", "."], cwd=repo_root, timeout=10)
        run_cmd(
            ["git", "commit", "-m", f"{commit_type}: {task['title']} (#{issue_num})"],
            cwd=repo_root,
            timeout=10
        )
        
        print_fn("GREEN completo.\n")
        return True
    
    # Exhausted attempts
    print_fn("No se pudo completar GREEN después de múltiples intentos.")
    return False


def run_refactor_phase(
    repo_root: str,
    issue_num: int,
    task: dict[str, Any],
    spec: dict[str, Any],
    spec_path: Path,
    test_cmd: list[str],
    logs_dir: Path,
    coder: Callable,
    run_cmd: Callable,
    input_fn: Callable,
    print_fn: Callable
) -> bool:
    """
    Run REFACTOR phase: optional cleanup keeping tests green.
    
    Returns True (always succeeds, reverts on failure).
    """
    task_id = task["id"]
    
    # Build prompt
    prompt = build_refactor_prompt(spec, task)
    
    # Call coder
    log_path = logs_dir / f"{task_id}-refactor-1.log"
    print_fn("Invocando coder para refactor opcional...")
    
    exit_code, output = coder(prompt, str(log_path))
    
    if exit_code != 0:
        print_fn("Coder falló en refactor. Marcando como completo sin refactor.")
        mark_progress(str(spec_path), task_id, "refactor")
        run_cmd(["git", "add", str(spec_path)], cwd=repo_root, timeout=5)
        run_cmd(
            ["git", "commit", "-m", f"docs: refactor omitido para {task_id} (#{issue_num})"],
            cwd=repo_root,
            timeout=10
        )
        return True
    
    # Check if coder signaled no refactor needed
    if "SIN_REFACTOR" in output:
        print_fn("Coder indica que no se necesita refactor.")
        mark_progress(str(spec_path), task_id, "refactor")
        run_cmd(["git", "add", str(spec_path)], cwd=repo_root, timeout=5)
        run_cmd(
            ["git", "commit", "-m", f"docs: refactor no necesario para {task_id} (#{issue_num})"],
            cwd=repo_root,
            timeout=10
        )
        return True
    
    # Check if any files changed
    changed = get_changed_files(repo_root, run_cmd)
    
    if not changed:
        print_fn("No hay cambios en refactor.")
        mark_progress(str(spec_path), task_id, "refactor")
        run_cmd(["git", "add", str(spec_path)], cwd=repo_root, timeout=5)
        run_cmd(
            ["git", "commit", "-m", f"docs: refactor sin cambios para {task_id} (#{issue_num})"],
            cwd=repo_root,
            timeout=10
        )
        return True
    
    # Run tests (must still PASS)
    print_fn("Ejecutando tests después de refactor...")
    test_result = run_cmd(test_cmd, cwd=repo_root, timeout=300)
    
    # Check for empty run
    combined_output = test_result.stdout + "\n" + test_result.stderr
    empty_signal = detect_empty_run(combined_output)
    
    if empty_signal or test_result.returncode != 0:
        if empty_signal:
            print_fn(f"Refactor causó corrida vacía: {empty_signal}. Revirtiendo...")
        else:
            print_fn("Refactor rompió los tests. Revirtiendo...")
        
        revert_files(repo_root, changed, run_cmd)
        
        # Mark as done with note
        mark_progress(str(spec_path), task_id, "refactor")
        run_cmd(["git", "add", str(spec_path)], cwd=repo_root, timeout=5)
        run_cmd(
            ["git", "commit", "-m", f"docs: refactor revertido para {task_id} (#{issue_num})"],
            cwd=repo_root,
            timeout=10
        )
        return True
    
    # Tests still pass - commit refactor
    print_fn("Refactor exitoso. Commiteando...")
    
    mark_progress(str(spec_path), task_id, "refactor")
    
    run_cmd(["git", "add", "."], cwd=repo_root, timeout=10)
    run_cmd(
        ["git", "commit", "-m", f"refactor: {task['title']} (#{issue_num})"],
        cwd=repo_root,
        timeout=10
    )
    
    print_fn("REFACTOR completo.\n")
    return True


def build_red_prompt(spec: dict[str, Any], task: dict[str, Any]) -> str:
    """Build prompt for RED phase."""
    lines = [
        "# Fase RED: Escribir tests que fallan",
        "",
        "## Contexto",
        "",
        f"**Issue**: {spec.get('summary', '')}",
        "",
        "## Decisiones acordadas",
        ""
    ]
    
    for decision in spec.get("decisions", []):
        lines.append(f"- **{decision['topic']}**: {decision['chosen']} ({decision['rationale']})")
    
    lines.append("")
    lines.append("## Tarea actual")
    lines.append("")
    lines.append(f"**{task['id']}: {task['title']}**")
    lines.append("")
    lines.append(task['description'])
    lines.append("")
    lines.append("## Tests a escribir")
    lines.append("")
    
    for test in task["tests"]:
        lines.append(f"- `{test['file']}::{test['name']}`: {test['asserts']}")
    
    lines.append("")
    
    # Add test_support_files section if present
    test_support_files = task.get("test_support_files", [])
    if test_support_files:
        lines.append("## Archivos de soporte de tests")
        lines.append("")
        for support_file in test_support_files:
            lines.append(f"- `{support_file}`")
        lines.append("")
        lines.append("Creá o ajustá estos archivos con el mínimo necesario para que los tests se EJECUTEN y fallen por un assert o import faltante del código de producción, nunca porque falta infraestructura de tests (ej: el workspace debe tener package.json, tsconfig, vitest config necesarios para que el runner descubra los tests).")
        lines.append("")
    
    lines.append("## REGLAS ESTRICTAS")
    lines.append("")
    lines.append("1. Escribí SOLO los tests de esta tarea")
    lines.append("2. NO toques código de producción")
    
    # List impl_files explicitly as forbidden if test_support_files present
    if test_support_files:
        impl_files = task.get("impl_files", [])
        if impl_files:
            lines.append("3. Los siguientes archivos de implementación están PROHIBIDOS en RED:")
            for impl_file in impl_files:
                lines.append(f"   - `{impl_file}`")
            lines.append("4. Los tests deben FALLAR (assert o NotImplementedError)")
            lines.append("5. Si necesitás tomar una decisión no prevista, escribí una línea `/DESVIO <explicación>` y frená")
        else:
            lines.append("3. Los tests deben FALLAR (assert o NotImplementedError)")
            lines.append("4. Si necesitás tomar una decisión no prevista, escribí una línea `/DESVIO <explicación>` y frená")
    else:
        lines.append("3. Los tests deben FALLAR (assert o NotImplementedError)")
        lines.append("4. Si necesitás tomar una decisión no prevista, escribí una línea `/DESVIO <explicación>` y frená")
    
    lines.append("")
    
    return "\n".join(lines)


def build_green_prompt(spec: dict[str, Any], task: dict[str, Any], attempt: int) -> str:
    """Build prompt for GREEN phase."""
    lines = [
        "# Fase GREEN: Implementar mínimo para pasar tests",
        "",
        "## Contexto",
        "",
        f"**Issue**: {spec.get('summary', '')}",
        "",
        "## Decisiones acordadas",
        ""
    ]
    
    for decision in spec.get("decisions", []):
        lines.append(f"- **{decision['topic']}**: {decision['chosen']} ({decision['rationale']})")
    
    lines.append("")
    lines.append("## Tarea actual")
    lines.append("")
    lines.append(f"**{task['id']}: {task['title']}**")
    lines.append("")
    lines.append(task['description'])
    lines.append("")
    
    # Include test_support_files if present (may be modified in GREEN)
    test_support_files = task.get("test_support_files", [])
    if test_support_files:
        lines.append("## Archivos de soporte de tests (pueden modificarse si es necesario)")
        lines.append("")
        for support_file in test_support_files:
            lines.append(f"- `{support_file}`")
        lines.append("")
    
    lines.append("## Archivos de implementación")
    lines.append("")
    
    for impl_file in task["impl_files"]:
        lines.append(f"- `{impl_file}`")
    
    lines.append("")
    lines.append("## REGLAS ESTRICTAS")
    lines.append("")
    lines.append("1. Implementá lo mínimo para que pasen los tests")
    lines.append("2. NO modifiques los archivos de test")
    lines.append("3. Si necesitás tomar una decisión no prevista, escribí `/DESVIO <explicación>` y frená")
    lines.append("")
    
    if attempt > 0:
        lines.append(f"(Intento {attempt + 1} - los tests siguen fallando)")
        lines.append("")
    
    return "\n".join(lines)


def build_refactor_prompt(spec: dict[str, Any], task: dict[str, Any]) -> str:
    """Build prompt for REFACTOR phase."""
    lines = [
        "# Fase REFACTOR: Limpiar código (opcional)",
        "",
        "## Contexto",
        "",
        f"**Issue**: {spec.get('summary', '')}",
        "",
        f"**Tarea**: {task['title']}",
        "",
        "Los tests ya pasan. Podés hacer refactoring opcional para mejorar la calidad del código.",
        "",
        "## Opciones",
        "",
        "1. Si no hay nada que mejorar, respondé con una línea que contenga `SIN_REFACTOR`",
        "2. Si querés refactorizar, hacelo manteniendo los tests verdes",
        "",
        "## REGLAS",
        "",
        "- NO cambies la funcionalidad",
        "- Los tests deben seguir pasando",
        "- Si hay dudas, mejor no refactorizar",
        ""
    ]
    
    return "\n".join(lines)

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

from take_agent import parse_spec_markdown, set_status, mark_progress, unmark_progress


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

# Sentinel value to signal back-to-RED from GREEN
BACK_TO_RED = "back_to_red"


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


def extract_ts_error_type_name(error_code: str, error_message: str) -> str | None:
    """
    Extract the named type from a TypeScript error message.
    
    For TS2353: extracts type name from "in type X" pattern
    For TS2345: extracts type name from "parameter of type X" pattern
    For other codes (TS2554, TS2339, TS2551, TS2741, TS2307, etc.): returns None
    
    Args:
        error_code: The TypeScript error code (e.g. "TS2353")
        error_message: The error message text
    
    Returns:
        The type name if found, None otherwise
    """
    patterns = {
        "TS2353": r"\bin type '([^']+)'",
        "TS2345": r"\bparameter of type '([^']+)'",
    }
    
    if pattern := patterns.get(error_code):
        if match := re.search(pattern, error_message):
            return match.group(1)
    
    return None


def test_imports_impl_file(test_file: str, impl_files: list[str], repo_root: str) -> bool:
    """
    Check if a test file imports a module that resolves to any impl_file.
    
    Parses static and dynamic import statements, resolves relative paths,
    and matches against impl_files with extension resolution (.js -> .ts, no ext -> .ts).
    
    Args:
        test_file: Test file path (relative to repo_root)
        impl_files: List of implementation file paths (relative to repo_root)
        repo_root: Absolute path to repository root
    
    Returns:
        True if test file imports any impl_file, False otherwise
    """
    test_path = Path(repo_root) / test_file
    
    if not test_path.exists():
        return False
    
    try:
        content = test_path.read_text(encoding="utf-8")
    except Exception:
        return False
    
    # Find all import specifiers (static and dynamic)
    # Static: import { x } from 'path' or import 'path'
    # Dynamic: import('path')
    import_pattern = re.compile(
        r"""
        (?:
            (?:import\s+(?:\{[^}]*\}|\*\s+as\s+\w+|\w+)\s+from\s+['"]([^'"]+)['"])  # static import with specifier
            |(?:import\s+['"]([^'"]+)['"])  # side-effect import
            |(?:import\s*\(\s*['"]([^'"]+)['"]\s*\))  # dynamic import
        )
        """,
        re.VERBOSE | re.MULTILINE
    )
    
    matches = import_pattern.findall(content)
    
    # Flatten match groups (each match is a tuple of 3 groups, only one is non-empty)
    import_paths = [m for group in matches for m in group if m]
    
    # Resolve each import path
    test_dir = test_path.parent
    
    for import_path in import_paths:
        # Skip non-relative imports (node_modules)
        if not import_path.startswith('.'):
            continue
        
        # Resolve relative path
        resolved = (test_dir / import_path).resolve()
        
        # Try multiple extensions for extension resolution
        # .js -> .ts, no ext -> .ts
        candidates = []
        
        if resolved.suffix == ".js":
            # Try replacing .js with .ts
            candidates.append(resolved.with_suffix(".ts"))
        elif resolved.suffix == "":
            # Try adding .ts extension
            candidates.append(resolved.with_suffix(".ts"))
        else:
            # Use as-is
            candidates.append(resolved)
        
        # Check if any candidate matches an impl_file
        for candidate in candidates:
            # Normalize path to be relative to repo_root
            try:
                rel_path = candidate.relative_to(Path(repo_root))
                normalized = str(rel_path).replace("\\", "/")
                
                if normalized in impl_files:
                    return True
            except ValueError:
                # Not relative to repo_root, skip
                continue
    
    return False


def type_declared_in_impl_files(type_name: str, impl_files: list[str], repo_root: str) -> bool:
    """
    Check if a type name is declared in any of the impl_files.
    
    Searches for interface, type alias, or class declarations matching the type name.
    Matches both with and without export keyword.
    
    Args:
        type_name: The type name to search for
        impl_files: List of implementation file paths (relative to repo_root)
        repo_root: Absolute path to repository root
    
    Returns:
        True if the type is declared in any impl_file, False otherwise
    """
    if not impl_files:
        return False
    
    # Pattern to match interface, type, or class declarations
    # Matches: interface X, export interface X, type X, export type X, class X, export class X
    pattern = re.compile(
        rf"^\s*(export\s+)?(interface|type|class)\s+{re.escape(type_name)}\b",
        re.MULTILINE
    )
    
    for file_path in impl_files:
        full_path = Path(repo_root) / file_path
        if not full_path.exists():
            continue
        
        try:
            content = full_path.read_text(encoding="utf-8")
            if pattern.search(content):
                return True
        except Exception:
            # Skip files that can't be read
            continue
    
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


def find_workspace_root(repo_root: str, file_path: str) -> str | None:
    """
    Find the nearest parent directory containing package.json.
    
    Searches upward from file_path until finding a package.json inside repo_root.
    Returns the workspace root path (absolute) or None if not found.
    """
    repo_path = Path(repo_root)
    file_abs = repo_path / file_path
    
    # Start from file's parent and walk up
    current = file_abs.parent
    
    while current != repo_path.parent and current.is_relative_to(repo_path):
        package_json = current / "package.json"
        if package_json.exists():
            return str(current)
        current = current.parent
    
    return None


# TS error codes that are acceptable in test files (missing production code)
ACCEPTABLE_TS_ERRORS = {
    "TS2307",  # Cannot find module
    "TS2305",  # Module has no exported member
    "TS2724",  # Module has no exported member (newer TS)
    "TS2614",  # Module has no default export
}


def is_signature_error_acceptable(error_code: str, error_line: str, test_file: str, impl_files: list[str], repo_root: str) -> bool:
    """
    Check if a TypeScript signature error should be accepted.
    
    Extended acceptance for signature-related errors (D1):
    - TS2353, TS2345: accepted if the named type is declared in any impl_file
    - TS2554, TS2339, TS2551, TS2741: accepted if the test file imports any impl_file
    
    Args:
        error_code: The TypeScript error code (e.g. "TS2353")
        error_line: The full error line from tsc output
        test_file: Test file path (relative to repo_root)
        impl_files: List of implementation file paths (relative to repo_root)
        repo_root: Repository root path
    
    Returns:
        True if error should be accepted, False otherwise
    """
    # Codes with named types: extract type and check if declared in impl_files
    if error_code in ("TS2353", "TS2345"):
        type_name = extract_ts_error_type_name(error_code, error_line)
        if type_name:
            return type_declared_in_impl_files(type_name, impl_files, repo_root)
        return False
    
    # Codes without named types: check if test imports any impl_file
    if error_code in ("TS2554", "TS2339", "TS2551", "TS2741"):
        return test_imports_impl_file(test_file, impl_files, repo_root)
    
    return False


def check_test_files_static(repo_root: str, test_files: list[str], run_cmd: Callable, impl_files: list[str] | None = None) -> str | None:
    """
    Check test files for static errors (lint, typecheck, syntax).
    
    For TS/JS test files: runs ESLint and TypeScript compiler in their workspace.
    For Python test files: runs py_compile.
    
    With impl_files parameter: extends acceptable TS errors to include signature errors
    (TS2353, TS2345, TS2554, TS2339, TS2551, TS2741) when the type is declared in impl_files
    or the test imports an impl_file.
    
    Returns None if all checks pass, or a feedback string with tool output if checks fail.
    
    Args:
        repo_root: Repository root path
        test_files: List of test file paths (relative to repo_root)
        run_cmd: Command runner function
        impl_files: Optional list of implementation file paths (relative to repo_root)
                   for extended error acceptance logic
    
    Returns:
        None if valid, or feedback string with exact tool output if invalid
    """
    # Separate files by language
    ts_js_files = []
    py_files = []
    
    for f in test_files:
        lower = f.lower()
        if any(lower.endswith(ext) for ext in [".ts", ".tsx", ".js", ".jsx", ".mts", ".cts"]):
            ts_js_files.append(f)
        elif lower.endswith(".py"):
            py_files.append(f)
    
    # Check TS/JS files grouped by workspace
    if ts_js_files:
        # Group by workspace
        by_workspace = {}
        for f in ts_js_files:
            workspace = find_workspace_root(repo_root, f)
            if workspace:
                if workspace not in by_workspace:
                    by_workspace[workspace] = []
                by_workspace[workspace].append(f)
        
        for workspace, files in by_workspace.items():
            workspace_path = Path(workspace)
            repo_path = Path(repo_root)
            
            # Make file paths relative to workspace
            files_rel = []
            for f in files:
                file_abs = repo_path / f
                try:
                    file_rel = file_abs.relative_to(workspace_path)
                    files_rel.append(str(file_rel))
                except ValueError:
                    # File not under workspace? Skip
                    pass
            
            if not files_rel:
                continue
            
            # Check for eslint config (search from workspace upward to repo_root)
            has_eslint = False
            eslint_flat_configs = [
                "eslint.config.js", "eslint.config.mjs", "eslint.config.cjs",
                "eslint.config.ts", "eslint.config.mts", "eslint.config.cts"
            ]
            eslint_legacy_configs = [
                ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json", ".eslintrc.yml", ".eslintrc.yaml"
            ]
            
            # Search upward from workspace to repo_root (inclusive)
            current = workspace_path
            while current.is_relative_to(repo_path) or current == repo_path:
                # Check flat configs
                for cfg in eslint_flat_configs:
                    if (current / cfg).exists():
                        has_eslint = True
                        break
                
                # Check legacy configs
                if not has_eslint:
                    for cfg in eslint_legacy_configs:
                        if (current / cfg).exists():
                            has_eslint = True
                            break
                
                # Check package.json for eslintConfig field
                if not has_eslint:
                    package_json_path = current / "package.json"
                    if package_json_path.exists():
                        try:
                            import json as json_mod
                            with open(package_json_path) as pj:
                                data = json_mod.load(pj)
                                if "eslintConfig" in data:
                                    has_eslint = True
                        except Exception:
                            pass
                
                if has_eslint or current == repo_path:
                    break
                
                current = current.parent
            
            if has_eslint:
                # Run eslint
                cmd = ["corepack", "pnpm", "--dir", workspace, "exec", "eslint"] + files_rel
                result = run_cmd(cmd, cwd=repo_root, timeout=30)
                
                if result.returncode != 0:
                    # ESLint failed
                    return f"ESLint errors in test files:\n{result.stdout}\n{result.stderr}"
            
            # Check for tsconfig
            has_tsconfig = (workspace_path / "tsconfig.json").exists()
            
            if has_tsconfig:
                # Run tsc
                cmd = ["corepack", "pnpm", "--dir", workspace, "exec", "tsc", "--noEmit", "--pretty", "false"]
                result = run_cmd(cmd, cwd=repo_root, timeout=60)
                
                if result.returncode != 0:
                    # Parse tsc output for errors in our test files
                    # Format: path(line,col): error TSxxxx: message
                    invalid_errors = []
                    found_any_parseable_error = False
                    
                    for line in result.stdout.splitlines():
                        # Match error line format
                        match = re.match(r"^(.+?)\(\d+,\d+\): error (TS\d+):", line)
                        if not match:
                            continue
                        
                        found_any_parseable_error = True
                        error_file = match.group(1)
                        error_code = match.group(2)
                        
                        # Normalize path separators
                        error_file_normalized = error_file.replace("\\", "/")
                        
                        # Check if error is in one of our changed test files
                        is_in_changed_test = any(
                            error_file_normalized.endswith(f.replace("\\", "/")) or
                            error_file_normalized == f.replace("\\", "/")
                            for f in files_rel
                        )
                        
                        if is_in_changed_test:
                            # Error in changed test file
                            if error_code in ACCEPTABLE_TS_ERRORS:
                                # Always acceptable (missing module/export)
                                continue
                            
                            # Extended acceptance logic when impl_files is provided
                            if impl_files is not None:
                                # Reconstruct full path relative to repo_root
                                # error_file_normalized is relative to workspace, need to make it relative to repo_root
                                try:
                                    workspace_rel_to_repo = str(Path(workspace).relative_to(Path(repo_root)))
                                    full_test_file = str(Path(workspace_rel_to_repo) / error_file_normalized)
                                except ValueError:
                                    # workspace not relative to repo_root, shouldn't happen
                                    full_test_file = error_file_normalized
                                
                                # Check if error is signature-related and should be accepted
                                if is_signature_error_acceptable(error_code, line, full_test_file, impl_files, repo_root):
                                    continue
                            
                            # Not acceptable - add to invalid list
                            invalid_errors.append(line)
                    
                    if invalid_errors:
                        return f"TypeScript errors in test files:\n" + "\n".join(invalid_errors)
                    
                    # If tsc failed but no parseable errors found, return raw output
                    if not found_any_parseable_error:
                        return f"TypeScript compiler failed with unparseable output:\n{result.stdout}\n{result.stderr}"
    
    # Check Python files
    for py_file in py_files:
        file_path = Path(repo_root) / py_file
        if not file_path.exists():
            continue
        
        # Use py_compile to check syntax
        import tempfile as tf
        import py_compile
        
        try:
            # Create a temp file for compilation (to avoid cache pollution)
            with tf.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
                tmp.write(file_path.read_text())
                tmp_path = tmp.name
            
            try:
                py_compile.compile(tmp_path, doraise=True)
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        except py_compile.PyCompileError as e:
            return f"Python syntax error in {py_file}:\n{e}"
    
    return None


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


def find_red_commit(repo_root: str, task: dict[str, Any], issue_num: int, run_cmd: Callable) -> str | None:
    """
    Find RED commit SHA for a task by searching git log.
    
    Searches for commit with message: "test: {task['title']} (#{issue_num})"
    
    Args:
        repo_root: Repository root path
        task: Task dict with 'title' field
        issue_num: Issue number
        run_cmd: Command runner function
    
    Returns:
        SHA string (40 chars) if found, None otherwise
    """
    # Build expected commit message
    expected_msg = f"test: {task['title']} (#{issue_num})"
    
    # Use --fixed-strings to avoid regex interpretation
    result = run_cmd(
        ["git", "log", "--format=%H", "-1", "--fixed-strings", "--grep", expected_msg],
        cwd=repo_root,
        timeout=5
    )
    
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    
    return None


def find_unremoved_tests(repo_root: str, task: dict[str, Any]) -> list[str]:
    """
    Find tests from task's tests_to_remove that still exist in their files.
    
    Args:
        repo_root: Repository root path
        task: Task dict with optional tests_to_remove field
    
    Returns:
        List of "file::name" strings for tests that were not removed
    """
    tests_to_remove = task.get("tests_to_remove", [])
    if not tests_to_remove:
        return []
    
    unremoved = []
    for removal in tests_to_remove:
        file_path = Path(repo_root) / removal["file"]
        test_name = removal["name"]
        
        # If file doesn't exist, test is removed
        if not file_path.exists():
            continue
        
        # Check if test name appears in file content
        try:
            content = file_path.read_text()
            if test_name in content:
                unremoved.append(f"{removal['file']}::{test_name}")
        except Exception:
            # If we can't read the file, assume it's removed
            pass
    
    return unremoved


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
    
    # Track back-to-RED per task (cap at 1 per run)
    back_to_red_count = {}
    
    # Track RED commit SHAs for tasks (in-memory, filled when run_red_phase commits)
    red_commits = {}
    
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
                
                # Record RED commit SHA after successful RED
                sha_result = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_root, timeout=5)
                if sha_result.returncode == 0:
                    red_commits[task_id] = sha_result.stdout.strip()
            
            elif phase == "green":
                back_to_red_info = {}
                success = run_green_phase(
                    repo_root, issue_num, task, spec, spec_path,
                    test_cmd, logs_dir, coder, run_cmd, input_fn, print_fn,
                    back_to_red_info
                )
                
                # Check if back-to-RED was triggered
                if success == BACK_TO_RED:
                    # Check cap
                    if back_to_red_count.get(task_id, 0) >= 1:
                        print_fn(f"\nError: la tarea {task_id} ya volvió a RED una vez en este run.")
                        print_fn("No se puede volver a RED de nuevo para la misma tarea.")
                        return False
                    
                    # Find RED commit
                    red_sha = red_commits.get(task_id)
                    if not red_sha:
                        red_sha = find_red_commit(repo_root, task, issue_num, run_cmd)
                    
                    if not red_sha:
                        print_fn(f"\nError: No encontré el commit de RED de {task_id}; no puedo volver a RED")
                        return False
                    
                    # Revert RED commit
                    print_fn(f"Revirtiendo commit de RED {red_sha[:8]}...")
                    revert_result = run_cmd(["git", "revert", "--no-edit", red_sha], cwd=repo_root, timeout=10)
                    
                    if revert_result.returncode != 0:
                        print_fn(f"Error al revertir RED commit:")
                        print_fn(revert_result.stderr)
                        return False
                    
                    # Unmark RED in spec
                    unmark_progress(str(spec_path), task_id, "red")
                    run_cmd(["git", "add", str(spec_path)], cwd=repo_root, timeout=5)
                    run_cmd(
                        ["git", "commit", "-m", f"docs: vuelta a RED de {task_id} (#{issue_num})"],
                        cwd=repo_root,
                        timeout=10
                    )
                    
                    # Increment back-to-RED count
                    back_to_red_count[task_id] = back_to_red_count.get(task_id, 0) + 1
                    
                    # Build feedback for RED
                    desvio = back_to_red_info.get("desvio", "")
                    decision = back_to_red_info.get("decision", "")
                    feedback = f"Volviendo a RED por /DESVIO en GREEN:\n\n/DESVIO: {desvio}\n\nDecisión tomada: {decision}"
                    
                    # Rerun RED with feedback
                    print_fn("\n=== Volviendo a RED ===\n")
                    success = run_red_phase(
                        repo_root, issue_num, task, spec, spec_path,
                        test_cmd, logs_dir, coder, run_cmd, input_fn, print_fn,
                        initial_feedback=feedback
                    )
                    if not success:
                        return False
                    
                    # Record new RED commit SHA
                    sha_result = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_root, timeout=5)
                    if sha_result.returncode == 0:
                        red_commits[task_id] = sha_result.stdout.strip()
                    
                    # Continue with GREEN and REFACTOR
                    # GREEN phase
                    print_fn("\n--- Fase GREEN (después de vuelta a RED) ---\n")
                    back_to_red_info_2 = {}
                    success = run_green_phase(
                        repo_root, issue_num, task, spec, spec_path,
                        test_cmd, logs_dir, coder, run_cmd, input_fn, print_fn,
                        back_to_red_info_2
                    )
                    
                    # After back-to-RED, no second back-to-RED allowed
                    if success == BACK_TO_RED:
                        print_fn(f"\nError: la tarea {task_id} ya volvió a RED una vez en este run.")
                        print_fn("No se puede volver a RED de nuevo para la misma tarea.")
                        return False
                    
                    if success is not True:
                        return False
                    
                    # REFACTOR phase
                    print_fn("\n--- Fase REFACTOR ---\n")
                    success = run_refactor_phase(
                        repo_root, issue_num, task, spec, spec_path,
                        test_cmd, logs_dir, coder, run_cmd, input_fn, print_fn
                    )
                    if not success:
                        return False
                    
                    # Task complete after back-to-RED flow
                    break
                
                elif success is True:
                    # GREEN succeeded normally, continue to REFACTOR
                    pass
                else:
                    # GREEN failed
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
    print_fn: Callable,
    initial_feedback: str | None = None
) -> bool:
    """
    Run RED phase: write tests that fail.
    
    Args:
        initial_feedback: Optional feedback to include in first attempt (e.g. from back-to-RED)
    
    Returns True if successful, False otherwise.
    """
    task_id = task["id"]
    max_attempts = 2  # Initial + 1 retry
    last_feedback = initial_feedback  # Start with initial feedback if provided
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
            if user_choice == "abortar":
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
        
        # Verify tests_to_remove were actually removed
        unremoved = find_unremoved_tests(repo_root, task)
        if unremoved:
            print_fn(f"Error: los siguientes tests deben ser eliminados pero siguen presentes:")
            for test_name in unremoved:
                print_fn(f"  - {test_name}")
            
            # Revert uncommitted changes
            changed = get_changed_files(repo_root, run_cmd)
            if changed:
                revert_files(repo_root, changed, run_cmd)
            
            if attempt < max_attempts - 1:
                print_fn("Reintentando RED...\n")
                last_feedback = "Los siguientes tests NO fueron eliminados pero deben serlo:\n"
                for test_name in unremoved:
                    last_feedback += f"  - {test_name}\n"
                last_feedback += "\nEliminá completamente estos tests de sus archivos."
                attempt += 1
                continue
            else:
                user_choice = input_fn("Continuar o abortar? (continuar/abortar): ").strip().lower()
                if user_choice == "abortar":
                    return False
                break
        
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
                if user_choice == "abortar":
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
                if user_choice == "abortar":
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
                if user_choice == "abortar":
                    return False
                break
        
        if test_result.returncode == 0:
            print_fn("Error: tests pasaron en fase RED (deberían fallar)")
            
            # First RED of the run: ask user if it's infrastructure error or test problem
            if attempt == 0:
                print_fn("\nOutput de tests:\n")
                print_fn(test_result.stdout[-1000:] if len(test_result.stdout) > 1000 else test_result.stdout)
                print_fn("\n¿Es un error de infraestructura o de los propios tests? (a=abortar por infraestructura / t=reintentar RED con comentario / n=no)")
                is_infra = input_fn("> ").strip().lower()
                
                if is_infra in ("a", "y"):
                    # Abort: backwards compatible with 'y' from main
                    print_fn("Error de infraestructura detectado. Abortando.")
                    return False
                elif is_infra == "t":
                    # Ask for optional comment and retry
                    comment = input_fn("Comentario para el coder (opcional): ").strip()
                    if comment:
                        last_feedback = comment
                    print_fn("Reintentando RED con feedback...")
                    # Revert and retry
                    if changed:
                        revert_files(repo_root, changed, run_cmd)
                    attempt += 1
                    continue
            
            # Revert and retry
            if changed:
                revert_files(repo_root, changed, run_cmd)
            
            if attempt < max_attempts - 1:
                print_fn("Reintentando RED...\n")
                attempt += 1
                continue
            else:
                user_choice = input_fn("Continuar o abortar? (continuar/abortar): ").strip().lower()
                if user_choice == "abortar":
                    return False
                break
        
        # Tests failed as expected - now check static validity of test files
        print_fn("Tests fallan correctamente. Verificando lint/typecheck de tests...")
        
        # Get changed test files only
        changed_test_files = [f for f in changed if is_test_file(f)]
        
        if changed_test_files:
            static_feedback = check_test_files_static(repo_root, changed_test_files, run_cmd, impl_files)
            
            if static_feedback:
                print_fn("Los tests de RED no pasan lint/typecheck por sí mismos:")
                print_fn(static_feedback)
                
                # Do NOT revert between attempts (D2-A)
                # Only revert on abort or exhausted attempts
                
                if attempt < max_attempts - 1:
                    print_fn("\nReintentando RED con feedback...\n")
                    last_feedback = f"Los tests no pasan lint/typecheck:\n\n{static_feedback}\n\nArreglá los errores en los archivos de test."
                    attempt += 1
                    continue
                else:
                    user_choice = input_fn("Continuar o abortar? (continuar/abortar): ").strip().lower()
                    if user_choice == "abortar":
                        # Revert all changed files on abort
                        if changed:
                            revert_files(repo_root, changed, run_cmd)
                        return False
                    # user chose 'continuar': commit with warning
                    print_fn("\n⚠️  ADVERTENCIA: Los tests NO pasan lint/typecheck por sí mismos.")
                    print_fn("Commiteando de todas formas según tu decisión de continuar.\n")
                    break
        
        # All checks passed - commit
        print_fn("Commiteando...")
        
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
    print_fn: Callable,
    back_to_red_info: dict[str, Any] | None = None
) -> bool | str:
    """
    Run GREEN phase: implement minimum to pass tests.
    
    Args:
        back_to_red_info: Dict to fill with {desvio, decision} if back-to-RED triggered
    
    Returns:
        True if successful
        False if failed
        BACK_TO_RED (str) if user wants to go back to RED
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
            
            print_fn("Decisión registrada.")
            
            # Ask if problem is in RED tests
            back_to_red_response = input_fn("¿El problema está en los tests de RED? (volver-a-red/no): ").strip().lower()
            
            if back_to_red_response == "volver-a-red":
                # Store info for caller
                if back_to_red_info is not None:
                    back_to_red_info["desvio"] = desvio
                    back_to_red_info["decision"] = decision
                
                return BACK_TO_RED
            
            # Otherwise retry GREEN with decision
            print_fn("Reintentando fase GREEN...\n")
            
            # Store decision for next prompt, DO NOT consume attempt
            last_decision = decision
            continue
        
        # Clear last_decision after successful non-/DESVIO call
        last_decision = None
        
        # Verify removed tests were not re-added
        unremoved = find_unremoved_tests(repo_root, task)
        if unremoved:
            print_fn(f"Error: tests eliminados en RED fueron re-agregados:")
            for test_name in unremoved:
                print_fn(f"  - {test_name}")
            
            # Revert files that re-added tests
            changed = get_changed_files(repo_root, run_cmd)
            if changed:
                revert_files(repo_root, changed, run_cmd)
            
            if attempt < max_attempts - 1:
                print_fn("Reintentando GREEN...\n")
                attempt += 1
                continue
            else:
                user_choice = input_fn("Reintentar o abortar? (reintentar/abortar): ").strip().lower()
                if user_choice == "abortar":
                    return False
                max_attempts += 1
                attempt += 1
                continue
        
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
                if user_choice == "abortar":
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
                if user_choice == "abortar":
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
                if user_choice == "abortar":
                    return False
                max_attempts += 1
                # Increment BOTH to maintain "last attempt" state
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
    
    # Add tests_to_remove section if present
    tests_to_remove = task.get("tests_to_remove", [])
    if tests_to_remove:
        lines.append("## Tests existentes a ELIMINAR")
        lines.append("")
        for removal in tests_to_remove:
            lines.append(f"- `{removal['file']}::{removal['name']}`: {removal['reason']}")
        lines.append("")
        lines.append("Eliminá estos tests completamente del archivo.")
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
    
    rule_num = 3
    
    # List impl_files explicitly as forbidden if test_support_files present
    if test_support_files:
        impl_files = task.get("impl_files", [])
        if impl_files:
            lines.append(f"{rule_num}. Los siguientes archivos de implementación están PROHIBIDOS en RED:")
            for impl_file in impl_files:
                lines.append(f"   - `{impl_file}`")
            rule_num += 1
    
    lines.append(f"{rule_num}. Los archivos de test deben pasar lint y typecheck por sí mismos, excepto por el import/export faltante del código de producción. NO uses `any`, parámetros sin tipo, variables sin usar, etc.")
    rule_num += 1
    lines.append(f"{rule_num}. Los mocks/fakes NO deben reproducir la lógica bajo test: assertá sobre lo que la función le pasa a sus dependencias (ej: argumentos dados a db.insert/values/set) y devolvé datos con la forma real (nombres reales de columnas del schema).")
    rule_num += 1
    lines.append(f"{rule_num}. Los tests deben fallar PORQUE FALTA el código de producción de esta tarea (import o assert sobre ese código), nunca por usar mal la API de una librería, del framework de tests o por errores del propio test.")
    rule_num += 1
    lines.append(f"{rule_num}. Antes de escribir asserts sobre una librería, verificá su API real en la versión instalada (tipos .d.ts en node_modules, o el código fuente) — no asumas la forma de los objetos.")
    rule_num += 1
    lines.append(f"{rule_num}. Si un test de la lista ya existe en el archivo, modificalo para que cumpla lo indicado (no dupliques)")
    rule_num += 1
    lines.append(f"{rule_num}. Leé los tests existentes de los archivos que tocás: si alguno NO listado contradice esta tarea o las decisiones acordadas, escribí `/DESVIO <test y contradicción>` y frená; no lo cambies en silencio ni lo dejes")
    rule_num += 1
    lines.append(f"{rule_num}. Si necesitás tomar una decisión no prevista, escribí una línea `/DESVIO <explicación>` y frená")
    
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
    
    # Mention removed tests if present
    tests_to_remove = task.get("tests_to_remove", [])
    if tests_to_remove:
        lines.append("3. Los siguientes tests ya fueron eliminados en RED y NO deben ser re-agregados:")
        for removal in tests_to_remove:
            lines.append(f"   - `{removal['file']}::{removal['name']}`")
        lines.append("4. Si necesitás tomar una decisión no prevista, escribí `/DESVIO <explicación>` y frená")
    else:
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

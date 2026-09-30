#!/usr/bin/env python3
"""
Tests for issue #28: back-to-RED from GREEN when tests are wrong.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Import modules to test
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "scripts"))
import take_agent
import tdd_runner


class TestFindRedCommit(unittest.TestCase):
    """Test find_red_commit helper."""
    
    def setUp(self):
        """Create temp git repo."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_find_red_")
        self.repo = Path(self.temp_dir)
        
        # Initialize git
        self._run(["git", "init"])
        self._run(["git", "config", "user.email", "test@test.com"])
        self._run(["git", "config", "user.name", "Test"])
        
        # Initial commit
        (self.repo / "README.md").write_text("# Test\n")
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "initial"])
    
    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _run(self, cmd, **kwargs):
        """Run command."""
        return subprocess.run(
            cmd,
            cwd=kwargs.get("cwd") or self.repo,
            capture_output=True,
            text=True,
            timeout=kwargs.get("timeout", 5),
            check=False
        )
    
    def test_finds_red_commit_by_message(self):
        """Test finds RED commit by exact message match."""
        # Create RED commit
        (self.repo / "test.py").write_text("# test\n")
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "test: implementar suma (#5)"])
        
        # Create another commit
        (self.repo / "impl.py").write_text("# impl\n")
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "feat: implementar suma (#5)"])
        
        task = {"id": "T1", "title": "implementar suma"}
        
        sha = tdd_runner.find_red_commit(str(self.repo), task, 5, self._run)
        
        self.assertIsNotNone(sha)
        self.assertEqual(len(sha), 40)  # Git SHA
        
        # Verify it's the right commit
        result = self._run(["git", "log", "--format=%s", "-1", sha])
        self.assertEqual(result.stdout.strip(), "test: implementar suma (#5)")
    
    def test_returns_none_when_not_found(self):
        """Test returns None when RED commit doesn't exist."""
        task = {"id": "T1", "title": "nonexistent task"}
        
        sha = tdd_runner.find_red_commit(str(self.repo), task, 5, self._run)
        
        self.assertIsNone(sha)
    
    def test_handles_regex_metachars_in_title(self):
        """Test handles titles with regex metacharacters."""
        # Create RED commit with special chars
        (self.repo / "test.py").write_text("# test\n")
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "test: Schema Drizzle: tablas (users) (#10)"])
        
        task = {"id": "T1", "title": "Schema Drizzle: tablas (users)"}
        
        sha = tdd_runner.find_red_commit(str(self.repo), task, 10, self._run)
        
        self.assertIsNotNone(sha)


class TestUnmarkProgress(unittest.TestCase):
    """Test unmark_progress helper."""
    
    def test_unmarks_red_checkbox(self):
        """Test unmarks only RED checkbox for target task."""
        spec_md = """---
issue: 5
status: implementing
test_command: pytest
---

# Spec

## Resumen

Test

## Decisiones de diseño

| ID | Topic | Opciones | Elegida | Rationale |
|----|-------|----------|---------|-----------|
| D1 | T | A | A | R |

## Archivos afectados

## Tareas

### T1: Task 1

Desc

**Tests:**
- `test.py::test_one`: assert x

**Archivos de implementación:**
- `foo.py`

**Progreso:**
- [x] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

### T2: Task 2

Desc

**Tests:**
- `test.py::test_two`: assert y

**Archivos de implementación:**
- `bar.py`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [ ] REFACTOR: código limpio

## Fuera de alcance

_(ninguno)_

## Riesgos

_(ninguno)_
"""
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(spec_md)
            spec_path = f.name
        
        try:
            take_agent.unmark_progress(spec_path, "T1", "red")
            
            with open(spec_path, "r") as f:
                result = f.read()
            
            # T1 RED should be unchecked
            self.assertIn("### T1: Task 1", result)
            # Find T1 section and check RED is unchecked
            t1_section = result.split("### T1: Task 1")[1].split("### T2:")[0]
            self.assertIn("- [ ] RED:", t1_section)
            
            # T2 should be unchanged
            t2_section = result.split("### T2: Task 2")[1].split("## Fuera de alcance")[0]
            self.assertIn("- [x] RED:", t2_section)
            self.assertIn("- [x] GREEN:", t2_section)
        finally:
            Path(spec_path).unlink(missing_ok=True)
    
    def test_roundtrip_with_mark_progress(self):
        """Test unmark + mark returns to original state."""
        spec_md = """---
issue: 5
status: implementing
test_command: pytest
---

# Spec

## Resumen

Test

## Decisiones de diseño

| ID | Topic | Opciones | Elegida | Rationale |
|----|-------|----------|---------|-----------|
| D1 | T | A | A | R |

## Archivos afectados

## Tareas

### T1: Task 1

Desc

**Tests:**
- `test.py::test_one`: assert x

**Archivos de implementación:**
- `foo.py`

**Progreso:**
- [x] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

## Fuera de alcance

_(ninguno)_

## Riesgos

_(ninguno)_
"""
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(spec_md)
            spec_path = f.name
        
        try:
            # Unmark
            take_agent.unmark_progress(spec_path, "T1", "red")
            
            with open(spec_path, "r") as f:
                after_unmark = f.read()
            
            self.assertIn("- [ ] RED:", after_unmark.split("### T1:")[1].split("## Fuera")[0])
            
            # Mark again
            take_agent.mark_progress(spec_path, "T1", "red")
            
            with open(spec_path, "r") as f:
                after_mark = f.read()
            
            self.assertIn("- [x] RED:", after_mark.split("### T1:")[1].split("## Fuera")[0])
        finally:
            Path(spec_path).unlink(missing_ok=True)


class TestBackToRedEndToEnd(unittest.TestCase):
    """Test full back-to-RED flow from GREEN."""
    
    def setUp(self):
        """Create temp git repo."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_back_to_red_")
        self.repo = Path(self.temp_dir)
        
        # Initialize git
        self._run(["git", "init"])
        self._run(["git", "config", "user.email", "test@test.com"])
        self._run(["git", "config", "user.name", "Test"])
        
        # Create structure
        (self.repo / "tests").mkdir()
        (self.repo / "src").mkdir()
        (self.repo / "docs" / "specs").mkdir(parents=True)
        (self.repo / ".backlog" / "runs").mkdir(parents=True)
        
        # Initial commit
        (self.repo / "tests" / "__init__.py").write_text("")
        (self.repo / "src" / "__init__.py").write_text("")
        (self.repo / "src" / "calc.py").write_text("def add(a, b):\n    raise NotImplementedError()\n")
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "initial"])
        
        # Create spec
        self._create_spec()
    
    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _run(self, cmd, **kwargs):
        """Run command."""
        return subprocess.run(
            cmd,
            cwd=kwargs.get("cwd") or self.repo,
            capture_output=True,
            text=True,
            timeout=kwargs.get("timeout", 10),
            check=False
        )
    
    def _create_spec(self):
        """Create spec."""
        spec = {
            "summary": "Add function",
            "decisions": [{"id": "D1", "topic": "Impl", "options": ["func"], "chosen": "func", "rationale": "Simple"}],
            "files": [],
            "test_command": "python3 -m unittest discover -s tests -v",
            "tasks": [
                {
                    "id": "T1",
                    "title": "implementar suma",
                    "description": "Suma dos números",
                    "tests": [
                        {"file": "tests/test_calc.py", "name": "test_add", "asserts": "add(2, 3) == 5"}
                    ],
                    "impl_files": ["src/calc.py"]
                }
            ],
            "out_of_scope": [],
            "risks": []
        }
        
        issue = {"number": 5, "title": "Calc"}
        rendered = take_agent.render_spec_markdown(spec, issue)
        
        # Set status to approved
        rendered = rendered.replace("status: draft", "status: approved")
        
        spec_path = self.repo / "docs" / "specs" / "issue-5.md"
        spec_path.write_text(rendered)
        self._run(["git", "add", str(spec_path)])
        self._run(["git", "commit", "-m", "docs: spec (#5)"])
    
    def test_back_to_red_full_flow(self):
        """Test RED commits wrong test, GREEN /DESVIO + back-to-RED, then success."""
        # Use phase markers instead of simple counters
        phase_calls = []
        
        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            # Branch ONLY on prompt content, not on file existence
            if "Fase RED" in prompt:
                red_num = len([p for p in phase_calls if p == "red"]) + 1
                phase_calls.append("red")
                
                if red_num == 1:
                    # First RED: write test that expects 999 (wrong)
                    (self.repo / "tests" / "test_calc.py").write_text(
                        "import unittest\n"
                        "from src.calc import add\n\n"
                        "class TestCalc(unittest.TestCase):\n"
                        "    def test_add(self):\n"
                        "        self.assertEqual(add(2, 3), 999)  # Wrong!\n"
                    )
                    return 0, "Tests written (wrong)"
                elif red_num == 2:
                    # Second RED (after back-to-RED): verify feedback present
                    if "/DESVIO" not in prompt or "el test está mal" not in prompt:
                        return 1, "ERROR: Second RED prompt missing /DESVIO feedback"
                    
                    # Write correct test
                    (self.repo / "tests" / "test_calc.py").write_text(
                        "import unittest\n"
                        "from src.calc import add\n\n"
                        "class TestCalc(unittest.TestCase):\n"
                        "    def test_add(self):\n"
                        "        self.assertEqual(add(2, 3), 5)  # Correct\n"
                    )
                    return 0, "Tests written (correct)"
                else:
                    return 1, f"ERROR: Unexpected RED call #{red_num}"
            
            elif "Fase GREEN" in prompt:
                green_num = len([p for p in phase_calls if p == "green"]) + 1
                phase_calls.append("green")
                
                if green_num == 1:
                    # First GREEN: detect wrong test and return /DESVIO
                    return 0, "/DESVIO el test está mal, espera 999 pero debería esperar 5"
                elif green_num == 2:
                    # Second GREEN (after back-to-RED): implement correctly
                    (self.repo / "src" / "calc.py").write_text(
                        "def add(a, b):\n    return a + b\n"
                    )
                    return 0, "Implementation done"
                else:
                    return 1, f"ERROR: Unexpected GREEN call #{green_num}"
            
            elif "Fase REFACTOR" in prompt or "refactorizá" in prompt.lower():
                phase_calls.append("refactor")
                return 0, "SIN_REFACTOR"
            
            else:
                return 1, f"ERROR: Unknown phase in prompt: {prompt[:100]}"
        
        inputs = [
            "el test está mal, debería esperar 5 no 999",  # Decision for /DESVIO in GREEN #1
            "volver-a-red",  # Back to RED
            "y"  # Confirm second RED failure (if tests pass erroneously)
        ]
        input_idx = [0]
        prompts_seen = []
        
        def mock_input(prompt_text: str) -> str:
            prompts_seen.append(prompt_text)
            if input_idx[0] < len(inputs):
                result = inputs[input_idx[0]]
                input_idx[0] += 1
                return result
            raise AssertionError(f"Unexpected input request #{len(prompts_seen)}: {prompt_text}")
        
        outputs = []
        def mock_print(msg: str) -> None:
            outputs.append(msg)
        
        result = tdd_runner.run_tdd_implementation(
            repo_root=str(self.repo),
            issue_num=5,
            coder=fake_coder,
            run_cmd=self._run,
            input_fn=mock_input,
            print_fn=mock_print
        )
        
        if not result:
            print("=== OUTPUTS ===")
            print("\n".join(outputs[-30:]))  # Last 30 lines
            red_c = len([p for p in phase_calls if p == "red"])
            green_c = len([p for p in phase_calls if p == "green"])
            refactor_c = len([p for p in phase_calls if p == "refactor"])
            print(f"=== CODER CALLS === RED:{red_c} GREEN:{green_c} REFACTOR:{refactor_c}")
            print(f"=== PHASE CALLS === {phase_calls}")
            print(f"=== PROMPTS SEEN ===")
            for i, p in enumerate(prompts_seen):
                print(f"{i+1}. {p[:80]}")
        
        self.assertTrue(result, "Should complete successfully")
        
        # Verify Revert commit exists
        log_result = self._run(["git", "log", "--format=%s", "--no-decorate"])
        commit_messages = log_result.stdout.strip().split("\n")
        
        revert_commits = [c for c in commit_messages if "revert \"test:" in c.lower() or "revert 'test:" in c.lower()]
        self.assertGreater(len(revert_commits), 0, "Should have Revert commit")
        
        # Verify there are 2 RED commits (one reverted, one after back-to-RED)
        red_test_commits = [c for c in commit_messages if c.startswith("test: implementar suma")]
        self.assertEqual(len(red_test_commits), 2, f"Should have 2 RED commits. Got: {red_test_commits}")
        
        # Verify second RED prompt contained /DESVIO feedback (verified in fake_coder)
        red_count = len([p for p in phase_calls if p == "red"])
        green_count = len([p for p in phase_calls if p == "green"])
        refactor_count = len([p for p in phase_calls if p == "refactor"])
        
        self.assertEqual(red_count, 2, "Should have 2 RED calls")
        self.assertEqual(green_count, 2, "Should have 2 GREEN calls")
        self.assertEqual(refactor_count, 1, "Should have 1 REFACTOR call")
        
        # Verify final spec is done with all checkboxes
        spec_path = self.repo / "docs" / "specs" / "issue-5.md"
        spec_content = spec_path.read_text()
        self.assertIn("status: done", spec_content)
        self.assertIn("- [x] RED:", spec_content)
        self.assertIn("- [x] GREEN:", spec_content)
        self.assertIn("- [x] REFACTOR:", spec_content)


class TestBackToRedUserAnswersNo(unittest.TestCase):
    """Test user answers 'no' to back-to-RED."""
    
    def setUp(self):
        """Create temp git repo."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_no_back_")
        self.repo = Path(self.temp_dir)
        
        # Initialize git
        self._run(["git", "init"])
        self._run(["git", "config", "user.email", "test@test.com"])
        self._run(["git", "config", "user.name", "Test"])
        
        # Create structure
        (self.repo / "tests").mkdir()
        (self.repo / "src").mkdir()
        (self.repo / "docs" / "specs").mkdir(parents=True)
        (self.repo / ".backlog" / "runs").mkdir(parents=True)
        
        # Initial commit
        (self.repo / "tests" / "__init__.py").write_text("")
        (self.repo / "src" / "__init__.py").write_text("")
        (self.repo / "src" / "calc.py").write_text("def add(a, b):\n    raise NotImplementedError()\n")
        (self.repo / "tests" / "test_calc.py").write_text(
            "import unittest\n"
            "from src.calc import add\n\n"
            "class TestCalc(unittest.TestCase):\n"
            "    def test_add(self):\n"
            "        self.assertEqual(add(2, 3), 5)\n"
        )
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "initial"])
        
        # Create RED commit
        self._run(["git", "commit", "--allow-empty", "-m", "test: suma (#5)"])
        
        # Create spec with RED done
        self._create_spec()
    
    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _run(self, cmd, **kwargs):
        """Run command."""
        return subprocess.run(
            cmd,
            cwd=kwargs.get("cwd") or self.repo,
            capture_output=True,
            text=True,
            timeout=kwargs.get("timeout", 10),
            check=False
        )
    
    def _create_spec(self):
        """Create spec with RED marked."""
        spec = {
            "summary": "Add",
            "decisions": [{"id": "D1", "topic": "I", "options": ["f"], "chosen": "f", "rationale": "S"}],
            "files": [],
            "test_command": "python3 -m unittest discover -s tests -v",
            "tasks": [
                {
                    "id": "T1",
                    "title": "suma",
                    "description": "Add",
                    "tests": [{"file": "tests/test_calc.py", "name": "test_add", "asserts": "x"}],
                    "impl_files": ["src/calc.py"]
                }
            ],
            "out_of_scope": [],
            "risks": []
        }
        
        issue = {"number": 5, "title": "C"}
        rendered = take_agent.render_spec_markdown(spec, issue)
        rendered = rendered.replace("status: draft", "status: implementing")
        rendered = rendered.replace("- [ ] RED:", "- [x] RED:")
        
        spec_path = self.repo / "docs" / "specs" / "issue-5.md"
        spec_path.write_text(rendered)
        self._run(["git", "add", str(spec_path)])
        self._run(["git", "commit", "-m", "docs: spec (#5)"])
    
    def test_no_back_to_red_retries_green(self):
        """Test answering 'no' retries GREEN without revert."""
        call_count = {"green": 0}
        
        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            if "Fase GREEN" in prompt:
                call_count["green"] += 1
                
                if call_count["green"] == 1:
                    return 0, "/DESVIO problema con el assert"
                elif call_count["green"] == 2:
                    # After user says "no", retry with decision
                    if "Decisión tomada" not in prompt:
                        return 1, "ERROR: Expected decision in retry prompt"
                    (self.repo / "src" / "calc.py").write_text("def add(a, b):\n    return a + b\n")
                    return 0, "Done"
                else:
                    return 1, "Too many calls"
            elif "refactorizá" in prompt.lower():
                return 0, "SIN_REFACTOR"
            else:
                return 1, f"ERROR: Unknown phase: {prompt[:100]}"
        
        inputs = [
            "usar assertEqual",  # Decision
            "no"  # Don't go back to RED
        ]
        input_idx = [0]
        
        def mock_input(prompt_text: str) -> str:
            if input_idx[0] < len(inputs):
                result = inputs[input_idx[0]]
                input_idx[0] += 1
                return result
            raise AssertionError(f"Unexpected input: {prompt_text}")
        
        outputs = []
        result = tdd_runner.run_tdd_implementation(
            repo_root=str(self.repo),
            issue_num=5,
            coder=fake_coder,
            run_cmd=self._run,
            input_fn=mock_input,
            print_fn=lambda m: outputs.append(m)
        )
        
        self.assertTrue(result)
        
        # Should NOT have Revert commit
        log_result = self._run(["git", "log", "--oneline", "--no-decorate"])
        commits = log_result.stdout.lower()
        self.assertNotIn("revert", commits, "Should not have revert commit when user answers 'no'")


class TestBackToRedSecondAttemptBlocked(unittest.TestCase):
    """Test second back-to-RED on same task is blocked."""
    
    def test_second_back_to_red_returns_false(self):
        """Test trying to go back to RED twice returns False with message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            
            # Setup minimal repo
            (repo / "tests").mkdir()
            (repo / "docs" / "specs").mkdir(parents=True)
            (repo / ".backlog" / "runs").mkdir(parents=True)
            
            subprocess.run(["git", "init"], cwd=repo, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, capture_output=True)
            subprocess.run(["git", "config", "user.name", "T"], cwd=repo, capture_output=True)
            
            (repo / "tests" / "__init__.py").write_text("")
            (repo / "i.py").write_text("def foo():\n    raise NotImplementedError()\n")
            subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True)
            
            # Create spec - use simple test command that works
            spec = {
                "summary": "T",
                "decisions": [{"id": "D1", "topic": "T", "options": ["A"], "chosen": "A", "rationale": "R"}],
                "files": [],
                "test_command": "python3 -m pytest tests/t.py -v || python3 -m unittest tests.t 2>&1",
                "tasks": [
                    {
                        "id": "T1",
                        "title": "task",
                        "description": "D",
                        "tests": [{"file": "tests/t.py", "name": "test_t", "asserts": "x"}],
                        "impl_files": ["i.py"]
                    }
                ],
                "out_of_scope": [],
                "risks": []
            }
            
            issue = {"number": 1, "title": "T"}
            rendered = take_agent.render_spec_markdown(spec, issue)
            rendered = rendered.replace("status: draft", "status: approved")
            
            spec_path = repo / "docs" / "specs" / "issue-1.md"
            spec_path.write_text(rendered)
            subprocess.run(["git", "add", str(spec_path)], cwd=repo, capture_output=True)
            subprocess.run(["git", "commit", "-m", "spec"], cwd=repo, capture_output=True)
            
            # Fake coder: RED #1 wrong, GREEN #1 /DESVIO, RED #2 still wrong, GREEN #2 /DESVIO
            phase_calls = []
            
            def fake_coder(prompt, log):
                if "Fase RED" in prompt:
                    phase_calls.append("red")
                    # Write test that fails (expects 999 from NotImplementedError function)
                    (repo / "tests" / "t.py").write_text(
                        "import unittest\n"
                        "import sys\n"
                        "sys.path.insert(0, '.')\n"
                        "from i import foo\n\n"
                        "class TestT(unittest.TestCase):\n"
                        "    def test_t(self):\n"
                        "        self.assertEqual(foo(), 999)\n"
                    )
                    return 0, "ok"
                elif "Fase GREEN" in prompt:
                    phase_calls.append("green")
                    return 0, f"/DESVIO el test está mal"
                else:
                    return 0, "SIN_REFACTOR"
            
            inputs = [
                "decisión 1", "volver-a-red",  # First back-to-RED
                "decisión 2", "volver-a-red"  # Second back-to-RED (should be blocked)
            ]
            input_idx = [0]
            
            def mock_input(p):
                if input_idx[0] < len(inputs):
                    result = inputs[input_idx[0]]
                    input_idx[0] += 1
                    return result
                raise AssertionError(f"Unexpected input: {p}")
            
            outputs = []
            
            def run_cmd(cmd, **kwargs):
                return subprocess.run(cmd, cwd=kwargs.get("cwd") or repo, capture_output=True, text=True, timeout=5)
            
            result = tdd_runner.run_tdd_implementation(
                repo_root=str(repo),
                issue_num=1,
                coder=fake_coder,
                run_cmd=run_cmd,
                input_fn=mock_input,
                print_fn=lambda m: outputs.append(m)
            )
            
            self.assertFalse(result, "Should fail on second back-to-RED")
            
            output_text = " ".join(outputs).lower()
            self.assertIn("ya volvió a red", output_text, f"Should mention task already went back. Output: {output_text[-500:]}")


class TestFindRedCommitNotFound(unittest.TestCase):
    """Test back-to-RED when RED commit not found."""
    
    def test_red_commit_not_found_returns_false(self):
        """Test returns False with clear message when RED commit not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            
            # Setup
            (repo / "tests").mkdir()
            (repo / "docs" / "specs").mkdir(parents=True)
            (repo / ".backlog" / "runs").mkdir(parents=True)
            
            subprocess.run(["git", "init"], cwd=repo, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, capture_output=True)
            subprocess.run(["git", "config", "user.name", "T"], cwd=repo, capture_output=True)
            
            (repo / "tests" / "__init__.py").write_text("")
            subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True)
            
            # Create spec
            spec = {
                "summary": "T",
                "decisions": [{"id": "D1", "topic": "T", "options": ["A"], "chosen": "A", "rationale": "R"}],
                "files": [],
                "test_command": "python3 -m unittest discover -s tests -v",
                "tasks": [
                    {
                        "id": "T1",
                        "title": "task",
                        "description": "D",
                        "tests": [{"file": "tests/t.py", "name": "test_t", "asserts": "x"}],
                        "impl_files": ["i.py"]
                    }
                ],
                "out_of_scope": [],
                "risks": []
            }
            
            issue = {"number": 1, "title": "T"}
            rendered = take_agent.render_spec_markdown(spec, issue)
            rendered = rendered.replace("status: draft", "status: implementing")
            rendered = rendered.replace("- [ ] RED:", "- [x] RED:")  # Mark RED as done but no commit
            
            spec_path = repo / "docs" / "specs" / "issue-1.md"
            spec_path.write_text(rendered)
            subprocess.run(["git", "add", str(spec_path)], cwd=repo, capture_output=True)
            subprocess.run(["git", "commit", "-m", "spec"], cwd=repo, capture_output=True)
            
            def fake_coder(prompt, log):
                if "Fase GREEN" in prompt:
                    return 0, "/DESVIO problema"
                return 0, "ok"
            
            inputs = ["decisión", "volver-a-red"]
            input_idx = [0]
            
            def mock_input(p):
                if input_idx[0] < len(inputs):
                    result = inputs[input_idx[0]]
                    input_idx[0] += 1
                    return result
                raise AssertionError(f"Unexpected input: {p}")
            
            outputs = []
            
            def run_cmd(cmd, **kwargs):
                return subprocess.run(cmd, cwd=kwargs.get("cwd") or repo, capture_output=True, text=True, timeout=5)
            
            result = tdd_runner.run_tdd_implementation(
                repo_root=str(repo),
                issue_num=1,
                coder=fake_coder,
                run_cmd=run_cmd,
                input_fn=mock_input,
                print_fn=lambda m: outputs.append(m)
            )
            
            self.assertFalse(result, "Should fail when RED commit not found")
            
            output_text = " ".join(outputs).lower()
            self.assertIn("no encontré", output_text, "Should say 'no encontré'")
            self.assertIn("commit de red", output_text, "Should mention RED commit")


class TestBackToRedUsesInMemoryCommitMap(unittest.TestCase):
    """Test back-to-RED uses in-memory red_commits map, not find_red_commit."""
    
    def test_find_red_commit_not_called_when_sha_known(self):
        """Test find_red_commit is NOT called when SHA is already in red_commits map."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            
            # Setup
            (repo / "tests").mkdir()
            (repo / "src").mkdir()
            (repo / "docs" / "specs").mkdir(parents=True)
            (repo / ".backlog" / "runs").mkdir(parents=True)
            
            subprocess.run(["git", "init"], cwd=repo, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, capture_output=True)
            subprocess.run(["git", "config", "user.name", "T"], cwd=repo, capture_output=True)
            
            (repo / "tests" / "__init__.py").write_text("")
            (repo / "src" / "__init__.py").write_text("")
            (repo / "src" / "calc.py").write_text("def add(a, b):\n    raise NotImplementedError()\n")
            subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True)
            
            # Create spec
            spec = {
                "summary": "Add",
                "decisions": [{"id": "D1", "topic": "I", "options": ["f"], "chosen": "f", "rationale": "S"}],
                "files": [],
                "test_command": "python3 -m unittest discover -s tests -v",
                "tasks": [
                    {
                        "id": "T1",
                        "title": "suma",
                        "description": "Add",
                        "tests": [{"file": "tests/test_calc.py", "name": "test_add", "asserts": "x"}],
                        "impl_files": ["src/calc.py"]
                    }
                ],
                "out_of_scope": [],
                "risks": []
            }
            
            issue = {"number": 5, "title": "C"}
            rendered = take_agent.render_spec_markdown(spec, issue)
            rendered = rendered.replace("status: draft", "status: approved")
            
            spec_path = repo / "docs" / "specs" / "issue-5.md"
            spec_path.write_text(rendered)
            subprocess.run(["git", "add", str(spec_path)], cwd=repo, capture_output=True)
            subprocess.run(["git", "commit", "-m", "spec"], cwd=repo, capture_output=True)
            
            # Fake coder
            phase_calls = []
            
            def fake_coder(prompt, log):
                if "Fase RED" in prompt:
                    red_num = len([p for p in phase_calls if p == "red"]) + 1
                    phase_calls.append("red")
                    if red_num == 1:
                        (repo / "tests" / "test_calc.py").write_text(
                            "import unittest\n"
                            "from src.calc import add\n\n"
                            "class TestCalc(unittest.TestCase):\n"
                            "    def test_add(self):\n"
                            "        self.assertEqual(add(2, 3), 999)\n"
                        )
                    else:
                        (repo / "tests" / "test_calc.py").write_text(
                            "import unittest\n"
                            "from src.calc import add\n\n"
                            "class TestCalc(unittest.TestCase):\n"
                            "    def test_add(self):\n"
                            "        self.assertEqual(add(2, 3), 5)\n"
                        )
                    return 0, "ok"
                elif "Fase GREEN" in prompt:
                    green_num = len([p for p in phase_calls if p == "green"]) + 1
                    phase_calls.append("green")
                    if green_num == 1:
                        return 0, "/DESVIO test malo"
                    else:
                        (repo / "src" / "calc.py").write_text("def add(a, b):\n    return a + b\n")
                        return 0, "ok"
                else:
                    phase_calls.append("refactor")
                    return 0, "SIN_REFACTOR"
            
            inputs = ["fix test", "volver-a-red"]
            input_idx = [0]
            
            def mock_input(p):
                if input_idx[0] < len(inputs):
                    result = inputs[input_idx[0]]
                    input_idx[0] += 1
                    return result
                raise AssertionError(f"Unexpected input: {p}")
            
            def run_cmd(cmd, **kwargs):
                return subprocess.run(cmd, cwd=kwargs.get("cwd") or repo, capture_output=True, text=True, timeout=5)
            
            # Patch find_red_commit to raise AssertionError if called
            from unittest.mock import patch
            with patch.object(tdd_runner, "find_red_commit", side_effect=AssertionError("find_red_commit should NOT be called")):
                result = tdd_runner.run_tdd_implementation(
                    repo_root=str(repo),
                    issue_num=5,
                    coder=fake_coder,
                    run_cmd=run_cmd,
                    input_fn=mock_input,
                    print_fn=lambda m: None
                )
                
                self.assertTrue(result, "Should succeed without calling find_red_commit")


class TestBuildRedPromptHardening(unittest.TestCase):
    """Test RED prompt contains hardening rules."""
    
    def test_red_prompt_has_both_hardening_rules(self):
        """Test RED prompt contains both new hardening rules."""
        spec = {"summary": "S", "decisions": []}
        task = {
            "id": "T1",
            "title": "Task",
            "description": "D",
            "tests": [{"file": "t.py", "name": "test", "asserts": "x"}],
            "impl_files": ["i.py"]
        }
        
        prompt = tdd_runner.build_red_prompt(spec, task)
        
        # Rule 1: tests must fail because production code is missing
        self.assertIn("Los tests deben fallar PORQUE FALTA el código de producción", prompt)
        self.assertIn("nunca por usar mal la API de una librería", prompt)
        
        # Rule 2: verify library API before using
        self.assertIn("Antes de escribir asserts sobre una librería", prompt)
        self.assertIn("verificá su API real", prompt)
        self.assertIn("no asumas la forma de los objetos", prompt)


class TestFirstRedConfirmationMentionsTests(unittest.TestCase):
    """Test first RED confirmation question mentions 'propios tests'."""
    
    def test_first_red_confirmation_question_text(self):
        """Test first RED confirmation asks about infrastructure or tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            
            # Setup
            (repo / "tests").mkdir()
            (repo / "src").mkdir()
            (repo / "docs" / "specs").mkdir(parents=True)
            (repo / ".backlog" / "runs").mkdir(parents=True)
            
            subprocess.run(["git", "init"], cwd=repo, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, capture_output=True)
            subprocess.run(["git", "config", "user.name", "T"], cwd=repo, capture_output=True)
            
            (repo / "tests" / "__init__.py").write_text("")
            (repo / "src" / "__init__.py").write_text("")
            subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True)
            
            # Create spec
            spec = {
                "summary": "T",
                "decisions": [{"id": "D1", "topic": "T", "options": ["A"], "chosen": "A", "rationale": "R"}],
                "files": [],
                "test_command": "python3 -m unittest discover -s tests -v",
                "tasks": [
                    {
                        "id": "T1",
                        "title": "task",
                        "description": "D",
                        "tests": [{"file": "tests/t.py", "name": "test_x", "asserts": "x"}],
                        "impl_files": ["src/i.py"]
                    }
                ],
                "out_of_scope": [],
                "risks": []
            }
            
            issue = {"number": 1, "title": "T"}
            rendered = take_agent.render_spec_markdown(spec, issue)
            rendered = rendered.replace("status: draft", "status: approved")
            
            spec_path = repo / "docs" / "specs" / "issue-1.md"
            spec_path.write_text(rendered)
            subprocess.run(["git", "add", str(spec_path)], cwd=repo, capture_output=True)
            subprocess.run(["git", "commit", "-m", "spec"], cwd=repo, capture_output=True)
            
            # Fake coder that writes passing test first, then failing test
            call_count = [0]
            def fake_coder(prompt, log):
                if "red" in log.lower():
                    call_count[0] += 1
                    if call_count[0] == 1:
                        # First call: write passing test
                        (repo / "tests" / "test_t.py").write_text(
                            "import unittest\n\n"
                            "class TestX(unittest.TestCase):\n"
                            "    def test_x(self):\n"
                            "        self.assertTrue(True)\n"
                        )
                    else:
                        # Second call: write failing test
                        (repo / "tests" / "test_t.py").write_text(
                            "import unittest\n"
                            "from src.i import foo\n\n"
                            "class TestX(unittest.TestCase):\n"
                            "    def test_x(self):\n"
                            "        self.assertEqual(foo(), 5)\n"
                        )
                return 0, "ok"
            
            prompts_seen = []
            
            def mock_input(p):
                prompts_seen.append(p)
                # Answer "y" to infrastructure question, then provide comment, then abort
                if "infraestructura" in p.lower():
                    return "y"
                if "comentario" in p.lower():
                    return ""  # No comment
                return "abortar"
            
            def run_cmd(cmd, **kwargs):
                return subprocess.run(cmd, cwd=kwargs.get("cwd") or repo, capture_output=True, text=True, timeout=5)
            
            outputs = []
            tdd_runner.run_tdd_implementation(
                repo_root=str(repo),
                issue_num=1,
                coder=fake_coder,
                run_cmd=run_cmd,
                input_fn=mock_input,
                print_fn=lambda m: outputs.append(m)
            )
            
            # Find the confirmation prompt (in outputs, not prompts_seen)
            output_text = "\n".join(outputs)
            self.assertIn("infraestructura", output_text.lower(), "Should ask about infrastructure")
            self.assertIn("propios tests", output_text.lower(), "Should mention 'propios tests'")
    
    def test_first_red_confirmation_with_comment(self):
        """Test answering 'y' then providing comment includes it in retry feedback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            
            # Setup
            (repo / "tests").mkdir()
            (repo / "src").mkdir()
            (repo / "docs" / "specs").mkdir(parents=True)
            (repo / ".backlog" / "runs").mkdir(parents=True)
            
            subprocess.run(["git", "init"], cwd=repo, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, capture_output=True)
            subprocess.run(["git", "config", "user.name", "T"], cwd=repo, capture_output=True)
            
            (repo / "tests" / "__init__.py").write_text("")
            (repo / "src" / "__init__.py").write_text("")
            subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True)
            
            # Create spec
            spec = {
                "summary": "T",
                "decisions": [{"id": "D1", "topic": "T", "options": ["A"], "chosen": "A", "rationale": "R"}],
                "files": [],
                "test_command": "python3 -m unittest discover -s tests -v",
                "tasks": [
                    {
                        "id": "T1",
                        "title": "task",
                        "description": "D",
                        "tests": [{"file": "tests/t.py", "name": "test_x", "asserts": "x"}],
                        "impl_files": ["src/i.py"]
                    }
                ],
                "out_of_scope": [],
                "risks": []
            }
            
            issue = {"number": 1, "title": "T"}
            rendered = take_agent.render_spec_markdown(spec, issue)
            rendered = rendered.replace("status: draft", "status: approved")
            
            spec_path = repo / "docs" / "specs" / "issue-1.md"
            spec_path.write_text(rendered)
            subprocess.run(["git", "add", str(spec_path)], cwd=repo, capture_output=True)
            subprocess.run(["git", "commit", "-m", "spec"], cwd=repo, capture_output=True)
            
            # Track RED prompts
            red_prompts = []
            
            def fake_coder(prompt, log):
                if "red" in log.lower():
                    red_prompts.append(prompt)
                    if len(red_prompts) == 1:
                        # First RED: write passing test
                        (repo / "tests" / "test_t.py").write_text(
                            "import unittest\n\n"
                            "class TestX(unittest.TestCase):\n"
                            "    def test_x(self):\n"
                            "        self.assertTrue(True)\n"
                        )
                    else:
                        # Second RED: write failing test
                        (repo / "tests" / "test_t.py").write_text(
                            "import unittest\n"
                            "from src.i import foo\n\n"
                            "class TestX(unittest.TestCase):\n"
                            "    def test_x(self):\n"
                            "        self.assertEqual(foo(), 5)\n"
                        )
                return 0, "ok"
            
            inputs = ["y", "el test no debe usar assertTrue(True)", "y"]
            input_idx = [0]
            
            def mock_input(p):
                if input_idx[0] < len(inputs):
                    result = inputs[input_idx[0]]
                    input_idx[0] += 1
                    return result
                return "abortar"
            
            def run_cmd(cmd, **kwargs):
                return subprocess.run(cmd, cwd=kwargs.get("cwd") or repo, capture_output=True, text=True, timeout=5)
            
            tdd_runner.run_tdd_implementation(
                repo_root=str(repo),
                issue_num=1,
                coder=fake_coder,
                run_cmd=run_cmd,
                input_fn=mock_input,
                print_fn=lambda m: None
            )
            
            # Verify second RED prompt contains the comment
            self.assertGreaterEqual(len(red_prompts), 2, "Should have at least 2 RED calls")
            second_prompt = red_prompts[1]
            self.assertIn("el test no debe usar assertTrue(True)", second_prompt)


if __name__ == "__main__":
    unittest.main()

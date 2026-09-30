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
        call_count = {"red": 0, "green": 0}
        
        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            # Debug: print log_path
            outputs.append(f"DEBUG: fake_coder called with log_path={log_path}")
            
            if "red" in log_path.lower():
                call_count["red"] += 1
                
                # Check if test file exists and read it
                test_file = self.repo / "tests" / "test_calc.py"
                current_test = test_file.read_text() if test_file.exists() else ""
                
                if "999" not in current_test:
                    # First RED: write test that can never pass (wrong)
                    test_file.write_text(
                        "import unittest\n"
                        "from src.calc import add\n\n"
                        "class TestCalc(unittest.TestCase):\n"
                        "    def test_add(self):\n"
                        "        self.assertEqual(add(2, 3), 999)  # Wrong!\n"
                    )
                    return 0, "Tests written (wrong)"
                else:
                    # Second RED (after back-to-RED): write correct test
                    feedback_present = "/DESVIO" in prompt and "el test está mal" in prompt
                    if not feedback_present:
                        return 1, "ERROR: Second RED prompt missing /DESVIO feedback"
                    
                    test_file.write_text(
                        "import unittest\n"
                        "from src.calc import add\n\n"
                        "class TestCalc(unittest.TestCase):\n"
                        "    def test_add(self):\n"
                        "        self.assertEqual(add(2, 3), 5)  # Correct\n"
                    )
                    return 0, "Tests written (correct)"
            
            elif "green" in log_path.lower():
                # Check if test expects 999 or 5
                test_file = self.repo / "tests" / "test_calc.py"
                if not test_file.exists():
                    call_count["green"] += 1
                    return 1, f"ERROR: Test file doesn't exist in GREEN #{call_count['green']}, repo={self.repo}"
                
                current_test = test_file.read_text()
                call_count["green"] += 1
                
                if "999" in current_test:
                    # Test still expects 999 - return /DESVIO
                    return 0, "/DESVIO el test está mal, espera 999 pero debería esperar 5"
                else:
                    # Test expects 5 (after back-to-RED) - implement
                    (self.repo / "src" / "calc.py").write_text(
                        "def add(a, b):\n    return a + b\n"
                    )
                    return 0, "Implementation done"
            
            else:
                # REFACTOR
                return 0, "SIN_REFACTOR"
        
        inputs = [
            "y",  # Confirm first RED failure
            "el test está mal, debería esperar 5 no 999",  # Decision for /DESVIO
            "volver-a-red",  # Back to RED
            "y"  # Confirm second RED failure
        ]
        input_idx = [0]
        
        def mock_input(prompt: str) -> str:
            if input_idx[0] < len(inputs):
                result = inputs[input_idx[0]]
                input_idx[0] += 1
                return result
            return ""
        
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
            print(f"=== CODER CALLS === RED:{call_count['red']} GREEN:{call_count['green']}")
        
        self.assertTrue(result, "Should complete successfully")
        
        # Verify Revert commit exists
        log_result = self._run(["git", "log", "--oneline", "--no-decorate"])
        commits = log_result.stdout.strip().split("\n")
        
        revert_commits = [c for c in commits if c.lower().startswith("revert \"test:")]
        self.assertGreater(len(revert_commits), 0, "Should have Revert commit")
        
        # Verify "vuelta a RED" commit exists
        vuelta_commits = [c for c in commits if "vuelta a red" in c.lower()]
        self.assertGreater(len(vuelta_commits), 0, "Should have 'vuelta a RED' commit")
        
        # Verify second RED prompt contained /DESVIO feedback
        self.assertEqual(call_count["red"], 2, "Should have 2 RED calls")
        self.assertEqual(call_count["green"], 2, "Should have 2 GREEN calls")
        
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
        call_count = [0]
        
        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            if "green" in log_path.lower():
                call_count[0] += 1
                
                if call_count[0] == 1:
                    return 0, "/DESVIO problema con el assert"
                elif call_count[0] == 2:
                    # After user says "no", retry with decision
                    if "Decisión tomada" not in prompt:
                        return 1, "ERROR: Expected decision in retry prompt"
                    (self.repo / "src" / "calc.py").write_text("def add(a, b):\n    return a + b\n")
                    return 0, "Done"
                else:
                    return 1, "Too many calls"
            else:
                return 0, "SIN_REFACTOR"
        
        inputs = [
            "usar assertEqual",  # Decision
            "no"  # Don't go back to RED
        ]
        input_idx = [0]
        
        def mock_input(prompt: str) -> str:
            if input_idx[0] < len(inputs):
                result = inputs[input_idx[0]]
                input_idx[0] += 1
                return result
            return ""
        
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
        self.assertNotIn("revert", commits)


class TestBackToRedSecondAttemptBlocked(unittest.TestCase):
    """Test second back-to-RED on same task is blocked."""
    
    def test_second_back_to_red_returns_false(self):
        """Test trying to go back to RED twice returns False with message."""
        # This test verifies the cap logic in run_tdd_implementation
        # We'll use a minimal setup and mock to reach the cap
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            
            # Setup minimal repo
            (repo / "docs" / "specs").mkdir(parents=True)
            (repo / ".backlog" / "runs").mkdir(parents=True)
            
            subprocess.run(["git", "init"], cwd=repo, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, capture_output=True)
            subprocess.run(["git", "config", "user.name", "T"], cwd=repo, capture_output=True)
            
            (repo / "README.md").write_text("x\n")
            subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True)
            
            # Create spec
            spec = {
                "summary": "T",
                "decisions": [{"id": "D1", "topic": "T", "options": ["A"], "chosen": "A", "rationale": "R"}],
                "files": [],
                "test_command": "true",
                "tasks": [
                    {
                        "id": "T1",
                        "title": "task",
                        "description": "D",
                        "tests": [{"file": "t.py", "name": "t", "asserts": "x"}],
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
            
            # Fake coder that triggers back-to-RED twice
            desvio_count = [0]
            
            def fake_coder(prompt, log):
                if "green" in log.lower():
                    desvio_count[0] += 1
                    return 0, f"/DESVIO problema {desvio_count[0]}"
                else:
                    (repo / "t.py").write_text("test\n")
                    return 0, "ok"
            
            inputs = [
                "y",  # Confirm RED
                "decisión 1", "volver-a-red",  # First back-to-RED
                "y",  # Confirm second RED
                "decisión 2", "volver-a-red"  # Second back-to-RED (should be blocked)
            ]
            input_idx = [0]
            
            def mock_input(p):
                if input_idx[0] < len(inputs):
                    result = inputs[input_idx[0]]
                    input_idx[0] += 1
                    return result
                return "abortar"
            
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
            self.assertIn("ya", output_text, "Should mention task already went back")


class TestFindRedCommitNotFound(unittest.TestCase):
    """Test back-to-RED when RED commit not found."""
    
    def test_red_commit_not_found_returns_false(self):
        """Test returns False with clear message when RED commit not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            
            # Setup
            (repo / "docs" / "specs").mkdir(parents=True)
            (repo / ".backlog" / "runs").mkdir(parents=True)
            
            subprocess.run(["git", "init"], cwd=repo, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, capture_output=True)
            subprocess.run(["git", "config", "user.name", "T"], cwd=repo, capture_output=True)
            
            (repo / "README.md").write_text("x\n")
            subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True)
            
            # Create spec
            spec = {
                "summary": "T",
                "decisions": [{"id": "D1", "topic": "T", "options": ["A"], "chosen": "A", "rationale": "R"}],
                "files": [],
                "test_command": "true",
                "tasks": [
                    {
                        "id": "T1",
                        "title": "task",
                        "description": "D",
                        "tests": [{"file": "t.py", "name": "t", "asserts": "x"}],
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
                if "green" in log.lower():
                    return 0, "/DESVIO problema"
                return 0, "ok"
            
            inputs = ["decisión", "volver-a-red"]
            input_idx = [0]
            
            def mock_input(p):
                if input_idx[0] < len(inputs):
                    result = inputs[input_idx[0]]
                    input_idx[0] += 1
                    return result
                return "abortar"
            
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
            
            self.assertFalse(result)
            
            output_text = " ".join(outputs).lower()
            self.assertIn("no encontré", output_text)
            self.assertIn("red", output_text)


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

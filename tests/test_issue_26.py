#!/usr/bin/env python3
"""
Tests for issue #26: tests_to_remove field in spec and RED phase validation.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Import modules to test
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "scripts"))
import take_agent
import tdd_runner


class TestValidateSpecWithTestsToRemove(unittest.TestCase):
    """Test validate_spec accepts and rejects tests_to_remove field."""
    
    def test_valid_spec_with_tests_to_remove(self):
        """Test validation accepts valid tests_to_remove."""
        spec = {
            "summary": "Test feature",
            "decisions": [{"id": "D1", "topic": "T", "options": ["A"], "chosen": "A", "rationale": "R"}],
            "files": [],
            "test_command": "pytest",
            "tasks": [
                {
                    "id": "T1",
                    "title": "Task",
                    "description": "Desc",
                    "tests": [{"file": "tests/test.py", "name": "test_new", "asserts": "x"}],
                    "tests_to_remove": [
                        {"file": "tests/test.py", "name": "test_old", "reason": "Contradicts new contract"}
                    ],
                    "impl_files": ["foo.py"]
                }
            ],
            "out_of_scope": [],
            "risks": []
        }
        valid, error = take_agent.validate_impl_spec(spec)
        self.assertTrue(valid, f"Should accept valid tests_to_remove: {error}")
    
    def test_rejects_tests_to_remove_not_list(self):
        """Test validation rejects tests_to_remove that is not a list."""
        spec = {
            "summary": "Test",
            "decisions": [{"id": "D1", "topic": "T", "options": ["A"], "chosen": "A", "rationale": "R"}],
            "files": [],
            "test_command": "pytest",
            "tasks": [
                {
                    "id": "T1",
                    "title": "Task",
                    "description": "Desc",
                    "tests": [{"file": "test.py", "name": "test", "asserts": "x"}],
                    "tests_to_remove": "not a list",
                    "impl_files": ["foo.py"]
                }
            ],
            "out_of_scope": [],
            "risks": []
        }
        valid, error = take_agent.validate_impl_spec(spec)
        self.assertFalse(valid)
        self.assertIn("tests_to_remove", error.lower())
        self.assertIn("must be a list", error.lower())
    
    def test_rejects_removal_missing_reason(self):
        """Test validation rejects removal item with missing reason."""
        spec = {
            "summary": "Test",
            "decisions": [{"id": "D1", "topic": "T", "options": ["A"], "chosen": "A", "rationale": "R"}],
            "files": [],
            "test_command": "pytest",
            "tasks": [
                {
                    "id": "T1",
                    "title": "Task",
                    "description": "Desc",
                    "tests": [{"file": "test.py", "name": "test", "asserts": "x"}],
                    "tests_to_remove": [
                        {"file": "test.py", "name": "test_old", "reason": ""}  # Empty reason
                    ],
                    "impl_files": ["foo.py"]
                }
            ],
            "out_of_scope": [],
            "risks": []
        }
        valid, error = take_agent.validate_impl_spec(spec)
        self.assertFalse(valid)
        self.assertIn("reason", error.lower())
    
    def test_rejects_removal_empty_name(self):
        """Test validation rejects removal item with empty name."""
        spec = {
            "summary": "Test",
            "decisions": [{"id": "D1", "topic": "T", "options": ["A"], "chosen": "A", "rationale": "R"}],
            "files": [],
            "test_command": "pytest",
            "tasks": [
                {
                    "id": "T1",
                    "title": "Task",
                    "description": "Desc",
                    "tests": [{"file": "test.py", "name": "test", "asserts": "x"}],
                    "tests_to_remove": [
                        {"file": "test.py", "name": "", "reason": "Old"}
                    ],
                    "impl_files": ["foo.py"]
                }
            ],
            "out_of_scope": [],
            "risks": []
        }
        valid, error = take_agent.validate_impl_spec(spec)
        self.assertFalse(valid)
        self.assertIn("name", error.lower())


class TestRenderParseRoundtrip(unittest.TestCase):
    """Test render→parse round trip preserves tests_to_remove."""
    
    def test_roundtrip_with_tests_to_remove(self):
        """Test render→parse preserves tests_to_remove and doesn't mix with tests[]."""
        spec = {
            "summary": "Feature",
            "decisions": [{"id": "D1", "topic": "T", "options": ["A"], "chosen": "A", "rationale": "R"}],
            "files": [],
            "test_command": "pytest",
            "tasks": [
                {
                    "id": "T1",
                    "title": "Task 1",
                    "description": "Implement feature",
                    "tests": [
                        {"file": "tests/test_foo.py", "name": "test_new_behavior", "asserts": "x == y"}
                    ],
                    "tests_to_remove": [
                        {"file": "tests/test_foo.py", "name": "test_old_behavior", "reason": "Contradicts new contract"}
                    ],
                    "impl_files": ["foo.py"]
                }
            ],
            "out_of_scope": [],
            "risks": []
        }
        
        issue = {"number": 1, "title": "Test"}
        
        # Render
        rendered = take_agent.render_spec_markdown(spec, issue)
        
        # Verify rendered contains both sections
        self.assertIn("**Tests:**", rendered)
        self.assertIn("test_new_behavior", rendered)
        self.assertIn("**Tests a eliminar:**", rendered)
        self.assertIn("test_old_behavior", rendered)
        self.assertIn("Contradicts new contract", rendered)
        
        # Parse
        metadata, parsed_spec, progress = take_agent.parse_spec_markdown(rendered)
        
        # Verify parsed spec has both arrays and they're separate
        task = parsed_spec["tasks"][0]
        self.assertEqual(len(task["tests"]), 1)
        self.assertEqual(task["tests"][0]["name"], "test_new_behavior")
        
        self.assertIn("tests_to_remove", task)
        self.assertEqual(len(task["tests_to_remove"]), 1)
        self.assertEqual(task["tests_to_remove"][0]["name"], "test_old_behavior")
        self.assertEqual(task["tests_to_remove"][0]["reason"], "Contradicts new contract")
    
    def test_render_without_field_omits_section(self):
        """Test spec without tests_to_remove doesn't render the section."""
        spec = {
            "summary": "Feature",
            "decisions": [{"id": "D1", "topic": "T", "options": ["A"], "chosen": "A", "rationale": "R"}],
            "files": [],
            "test_command": "pytest",
            "tasks": [
                {
                    "id": "T1",
                    "title": "Task 1",
                    "description": "Implement",
                    "tests": [{"file": "test.py", "name": "test", "asserts": "x"}],
                    "impl_files": ["foo.py"]
                }
            ],
            "out_of_scope": [],
            "risks": []
        }
        
        issue = {"number": 1, "title": "Test"}
        rendered = take_agent.render_spec_markdown(spec, issue)
        
        # Should NOT contain the removal section
        self.assertNotIn("**Tests a eliminar:**", rendered)


class TestBuildRedPromptWithRemovals(unittest.TestCase):
    """Test build_red_prompt includes removal section and new rules."""
    
    def test_prompt_with_tests_to_remove(self):
        """Test RED prompt with tests_to_remove contains ELIMINAR section."""
        spec = {
            "summary": "Feature",
            "decisions": []
        }
        task = {
            "id": "T1",
            "title": "Task",
            "description": "Desc",
            "tests": [{"file": "test.py", "name": "test_new", "asserts": "x"}],
            "tests_to_remove": [
                {"file": "test.py", "name": "test_old", "reason": "Old contract"}
            ],
            "impl_files": ["foo.py"]
        }
        
        prompt = tdd_runner.build_red_prompt(spec, task)
        
        self.assertIn("Tests existentes a ELIMINAR", prompt)
        self.assertIn("test.py::test_old", prompt)
        self.assertIn("Old contract", prompt)
    
    def test_prompt_always_has_new_rules(self):
        """Test RED prompt always contains the two new rules."""
        spec = {"summary": "Feature", "decisions": []}
        task = {
            "id": "T1",
            "title": "Task",
            "description": "Desc",
            "tests": [{"file": "test.py", "name": "test", "asserts": "x"}],
            "impl_files": ["foo.py"]
        }
        
        prompt = tdd_runner.build_red_prompt(spec, task)
        
        # Rule about modifying existing tests with same name
        self.assertIn("ya existe en el archivo, modificalo", prompt)
        # Rule about /DESVIO for contradicting tests
        self.assertIn("/DESVIO", prompt)
        self.assertIn("contradice", prompt.lower())


class TestFindUnremovedTests(unittest.TestCase):
    """Test find_unremoved_tests helper."""
    
    def test_finds_unremoved_test(self):
        """Test finds test that still exists in file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def test_old():\n    pass\n")
            
            task = {
                "tests_to_remove": [
                    {"file": "test.py", "name": "test_old", "reason": "Old"}
                ]
            }
            
            unremoved = tdd_runner.find_unremoved_tests(tmpdir, task)
            
            self.assertEqual(unremoved, ["test.py::test_old"])
    
    def test_returns_empty_when_removed(self):
        """Test returns empty when test was removed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def test_new():\n    pass\n")  # test_old not present
            
            task = {
                "tests_to_remove": [
                    {"file": "test.py", "name": "test_old", "reason": "Old"}
                ]
            }
            
            unremoved = tdd_runner.find_unremoved_tests(tmpdir, task)
            
            self.assertEqual(unremoved, [])
    
    def test_returns_empty_when_file_missing(self):
        """Test returns empty when file doesn't exist (fully removed)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            task = {
                "tests_to_remove": [
                    {"file": "test.py", "name": "test_old", "reason": "Old"}
                ]
            }
            
            unremoved = tdd_runner.find_unremoved_tests(tmpdir, task)
            
            self.assertEqual(unremoved, [])


class TestRunRedPhaseWithRemovals(unittest.TestCase):
    """Test run_red_phase integration with tests_to_remove."""
    
    def setUp(self):
        """Create temp git repo."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_red_removal_")
        self.repo = Path(self.temp_dir)
        
        # Initialize git
        self._run(["git", "init"])
        self._run(["git", "config", "user.email", "test@test.com"])
        self._run(["git", "config", "user.name", "Test"])
        
        # Create structure
        (self.repo / "tests").mkdir()
        (self.repo / "docs" / "specs").mkdir(parents=True)
        (self.repo / ".backlog" / "runs").mkdir(parents=True)
        
        # Create existing test file with old test
        (self.repo / "tests" / "test_foo.py").write_text(
            "import unittest\n\n"
            "class TestFoo(unittest.TestCase):\n"
            "    def test_old_behavior(self):\n"
            "        self.assertTrue(True)\n"
        )
        
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "initial"])
        
        # Create spec
        self._create_spec()
    
    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _run(self, cmd, **kwargs):
        """Run command in repo."""
        return subprocess.run(
            cmd,
            cwd=kwargs.get("cwd") or self.repo,
            capture_output=True,
            text=True,
            timeout=kwargs.get("timeout", 5),
            check=False
        )
    
    def _create_spec(self):
        """Create spec file with tests_to_remove."""
        spec_content = """---
issue: 1
status: approved
test_command: python3 -m unittest discover -s tests -v
---

# Spec

## Resumen

Test removal

## Decisiones de diseño

| ID | Topic | Opciones | Elegida | Rationale |
|----|-------|----------|---------|-----------|
| D1 | Test | A | A | R |

## Archivos afectados

## Tareas

### T1: Update behavior

Change contract

**Tests:**
- `tests/test_foo.py::test_new_behavior`: assert new

**Tests a eliminar:**
- `tests/test_foo.py::test_old_behavior`: Contradicts new contract

**Archivos de implementación:**
- `foo.py`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

## Fuera de alcance

_(ninguno)_

## Riesgos

_(ninguno)_
"""
        spec_path = self.repo / "docs" / "specs" / "issue-1.md"
        spec_path.write_text(spec_content)
        self._run(["git", "add", str(spec_path)])
        self._run(["git", "commit", "-m", "spec"])
    
    def test_red_phase_retries_when_test_not_removed(self):
        """Test RED phase retries when coder doesn't remove test."""
        from take_agent import parse_spec_markdown
        
        # Parse spec
        spec_path = self.repo / "docs" / "specs" / "issue-1.md"
        metadata, spec, progress = parse_spec_markdown(spec_path.read_text())
        task = spec["tasks"][0]
        
        test_cmd = tdd_runner.build_test_cmd(metadata["test_command"])
        logs_dir = self.repo / ".backlog" / "runs" / "issue-1"
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Fake coder: attempt 1 doesn't remove, attempt 2 removes
        attempts = []
        
        def fake_coder(prompt, log_path):
            attempts.append(log_path)
            
            if len(attempts) == 1:
                # First attempt: add new test but leave old one
                (self.repo / "tests" / "test_foo.py").write_text(
                    "import unittest\n\n"
                    "class TestFoo(unittest.TestCase):\n"
                    "    def test_old_behavior(self):  # NOT REMOVED!\n"
                    "        self.assertTrue(True)\n"
                    "    def test_new_behavior(self):\n"
                    "        self.fail('Not implemented')\n"
                )
            else:
                # Second attempt: remove old test
                (self.repo / "tests" / "test_foo.py").write_text(
                    "import unittest\n\n"
                    "class TestFoo(unittest.TestCase):\n"
                    "    def test_new_behavior(self):\n"
                    "        self.fail('Not implemented')\n"
                )
            
            return 0, "Done"
        
        outputs = []
        
        result = tdd_runner.run_red_phase(
            repo_root=str(self.repo),
            issue_num=1,
            task=task,
            spec=spec,
            spec_path=spec_path,
            test_cmd=test_cmd,
            logs_dir=logs_dir,
            coder=fake_coder,
            run_cmd=self._run,
            input_fn=lambda p: "y",  # Confirm RED failure
            print_fn=lambda msg: outputs.append(msg)
        )
        
        # Should succeed after retry
        self.assertTrue(result)
        
        # Should have called coder twice
        self.assertEqual(len(attempts), 2)
        
        # Output should mention unremoved test
        output_text = " ".join(outputs)
        self.assertIn("test_old_behavior", output_text)


class TestRunGreenPhaseRejectsReadd(unittest.TestCase):
    """Test run_green_phase detects and rejects re-added removed tests."""
    
    def setUp(self):
        """Create temp git repo."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_green_readd_")
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
        
        # Create test file after RED (old test removed)
        (self.repo / "tests" / "test_foo.py").write_text(
            "import unittest\n\n"
            "class TestFoo(unittest.TestCase):\n"
            "    def test_new_behavior(self):\n"
            "        from src.foo import foo\n"
            "        self.assertEqual(foo(), 'bar')\n"
        )
        
        # Create impl stub
        (self.repo / "src" / "foo.py").write_text(
            "def foo():\n    raise NotImplementedError()\n"
        )
        
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "after RED"])
        
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
            timeout=kwargs.get("timeout", 5),
            check=False
        )
    
    def _create_spec(self):
        """Create spec."""
        spec_content = """---
issue: 1
status: implementing
test_command: python3 -c "import sys; from pathlib import Path; sys.path.insert(0, str(Path('.'))); from tests.test_foo import *; import unittest; suite = unittest.TestLoader().loadTestsFromModule(sys.modules['tests.test_foo']); runner = unittest.TextTestRunner(); result = runner.run(suite); sys.exit(0 if result.wasSuccessful() else 1)"
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

### T1: Update

Desc

**Tests:**
- `tests/test_foo.py::test_new_behavior`: assert foo() == 'bar'

**Tests a eliminar:**
- `tests/test_foo.py::test_old_behavior`: Old contract

**Archivos de implementación:**
- `src/foo.py`

**Progreso:**
- [x] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

## Fuera de alcance

_(ninguno)_

## Riesgos

_(ninguno)_
"""
        spec_path = self.repo / "docs" / "specs" / "issue-1.md"
        spec_path.write_text(spec_content)
        self._run(["git", "add", str(spec_path)])
        self._run(["git", "commit", "-m", "spec"])
    
    def test_green_rejects_readded_test(self):
        """Test GREEN reverts if removed test is re-added."""
        from take_agent import parse_spec_markdown
        
        spec_path = self.repo / "docs" / "specs" / "issue-1.md"
        metadata, spec, progress = parse_spec_markdown(spec_path.read_text())
        task = spec["tasks"][0]
        
        test_cmd = tdd_runner.build_test_cmd(metadata["test_command"])
        logs_dir = self.repo / ".backlog" / "runs" / "issue-1"
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        def fake_coder(prompt, log_path):
            # GREEN implementation but re-adds old test
            (self.repo / "tests" / "test_foo.py").write_text(
                "import unittest\n\n"
                "class TestFoo(unittest.TestCase):\n"
                "    def test_new_behavior(self):\n"
                "        from src.foo import foo\n"
                "        self.assertEqual(foo(), 'bar')\n"
                "    def test_old_behavior(self):  # RE-ADDED!\n"
                "        self.assertTrue(True)\n"
            )
            (self.repo / "src" / "foo.py").write_text(
                "def foo():\n    return 'bar'\n"
            )
            return 0, "Done"
        
        outputs = []
        
        result = tdd_runner.run_green_phase(
            repo_root=str(self.repo),
            issue_num=1,
            task=task,
            spec=spec,
            spec_path=spec_path,
            test_cmd=test_cmd,
            logs_dir=logs_dir,
            coder=fake_coder,
            run_cmd=self._run,
            input_fn=lambda p: "abortar",
            print_fn=lambda msg: outputs.append(msg)
        )
        
        self.assertFalse(result)
        
        # Output should mention re-added test
        output_text = " ".join(outputs)
        self.assertIn("test_old_behavior", output_text)


if __name__ == "__main__":
    unittest.main()

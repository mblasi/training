#!/usr/bin/env python3
"""
Unit tests for take_agent module
"""
import json
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Import take_agent module
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "scripts"))
import take_agent


class TestValidateImplSpec(unittest.TestCase):
    """Test implementation spec validation."""
    
    def test_valid_spec(self):
        """Test validation of valid spec."""
        spec = {
            "summary": "Add foo feature",
            "decisions": [
                {
                    "id": "D1",
                    "topic": "Architecture",
                    "options": ["Option A", "Option B"],
                    "chosen": "Option A",
                    "rationale": "Better performance"
                }
            ],
            "files": [
                {
                    "path": "scripts/foo.py",
                    "action": "create",
                    "purpose": "Implement foo"
                }
            ],
            "test_command": "python3 -m unittest discover -s tests -v",
            "tasks": [
                {
                    "id": "T1",
                    "title": "Implement foo",
                    "description": "Add foo function",
                    "tests": [
                        {
                            "file": "tests/test_foo.py",
                            "name": "test_foo_returns_bar",
                            "asserts": "assert foo() == 'bar'"
                        }
                    ],
                    "impl_files": ["scripts/foo.py"]
                }
            ],
            "out_of_scope": ["Feature X"],
            "risks": ["Risk Y"]
        }
        valid, error = take_agent.validate_impl_spec(spec)
        self.assertTrue(valid, f"Validation failed: {error}")
    
    def test_missing_summary(self):
        """Test validation fails for missing summary."""
        spec = {
            "decisions": [],
            "files": [],
            "test_command": "pytest",
            "tasks": [],
            "out_of_scope": [],
            "risks": []
        }
        valid, error = take_agent.validate_impl_spec(spec)
        self.assertFalse(valid)
        self.assertIn("summary", error.lower())
    
    def test_empty_decisions(self):
        """Test validation fails for empty decisions."""
        spec = {
            "summary": "Test",
            "decisions": [],
            "files": [],
            "test_command": "pytest",
            "tasks": [
                {
                    "id": "T1",
                    "title": "Task",
                    "description": "Desc",
                    "tests": [{"file": "test.py", "name": "test", "asserts": "x"}],
                    "impl_files": ["foo.py"]
                }
            ],
            "out_of_scope": [],
            "risks": []
        }
        valid, error = take_agent.validate_impl_spec(spec)
        self.assertFalse(valid)
        self.assertIn("decisions", error.lower())
        self.assertIn("empty", error.lower())
    
    def test_empty_test_command(self):
        """Test validation fails for empty test_command."""
        spec = {
            "summary": "Test",
            "decisions": [{"id": "D1", "topic": "T", "options": ["A"], "chosen": "A", "rationale": "R"}],
            "files": [],
            "test_command": "",
            "tasks": [
                {
                    "id": "T1",
                    "title": "Task",
                    "description": "Desc",
                    "tests": [{"file": "test.py", "name": "test", "asserts": "x"}],
                    "impl_files": ["foo.py"]
                }
            ],
            "out_of_scope": [],
            "risks": []
        }
        valid, error = take_agent.validate_impl_spec(spec)
        self.assertFalse(valid)
        self.assertIn("test_command", error.lower())
    
    def test_task_without_tests(self):
        """Test validation fails for task without tests."""
        spec = {
            "summary": "Test",
            "decisions": [{"id": "D1", "topic": "T", "options": ["A"], "chosen": "A", "rationale": "R"}],
            "files": [],
            "test_command": "pytest",
            "tasks": [
                {
                    "id": "T1",
                    "title": "Task without tests",
                    "description": "Desc",
                    "tests": [],
                    "impl_files": ["foo.py"]
                }
            ],
            "out_of_scope": [],
            "risks": []
        }
        valid, error = take_agent.validate_impl_spec(spec)
        self.assertFalse(valid)
        self.assertIn("no tests", error.lower())
    
    def test_invalid_file_action(self):
        """Test validation fails for invalid file action."""
        spec = {
            "summary": "Test",
            "decisions": [{"id": "D1", "topic": "T", "options": ["A"], "chosen": "A", "rationale": "R"}],
            "files": [
                {
                    "path": "foo.py",
                    "action": "invalid_action",
                    "purpose": "Test"
                }
            ],
            "test_command": "pytest",
            "tasks": [
                {
                    "id": "T1",
                    "title": "Task",
                    "description": "Desc",
                    "tests": [{"file": "test.py", "name": "test", "asserts": "x"}],
                    "impl_files": ["foo.py"]
                }
            ],
            "out_of_scope": [],
            "risks": []
        }
        valid, error = take_agent.validate_impl_spec(spec)
        self.assertFalse(valid)
        self.assertIn("invalid action", error.lower())


class TestRenderSpecMarkdown(unittest.TestCase):
    """Test spec markdown rendering."""
    
    def test_render_deterministic(self):
        """Test that rendering is deterministic."""
        spec = {
            "summary": "Test summary",
            "decisions": [
                {
                    "id": "D1",
                    "topic": "Architecture",
                    "options": ["A", "B"],
                    "chosen": "A",
                    "rationale": "Best"
                }
            ],
            "files": [
                {"path": "foo.py", "action": "create", "purpose": "Test"}
            ],
            "test_command": "pytest",
            "tasks": [
                {
                    "id": "T1",
                    "title": "Task 1",
                    "description": "Do something",
                    "tests": [
                        {"file": "test.py", "name": "test_foo", "asserts": "assert x"}
                    ],
                    "impl_files": ["foo.py"]
                }
            ],
            "out_of_scope": ["Feature X"],
            "risks": ["Risk Y"]
        }
        
        issue = {"number": 42, "title": "Test Issue"}
        
        result1 = take_agent.render_spec_markdown(spec, issue)
        result2 = take_agent.render_spec_markdown(spec, issue)
        
        self.assertEqual(result1, result2, "Rendering should be deterministic")
    
    def test_render_contains_front_matter(self):
        """Test that rendered markdown contains front matter."""
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
                    "impl_files": ["foo.py"]
                }
            ],
            "out_of_scope": [],
            "risks": []
        }
        
        issue = {"number": 5, "title": "Test Issue"}
        result = take_agent.render_spec_markdown(spec, issue)
        
        self.assertIn("---", result)
        self.assertIn("issue: 5", result)
        self.assertIn("status: draft", result)
        self.assertIn("test_command: pytest", result)
    
    def test_render_contains_checkboxes(self):
        """Test that tasks have RED/GREEN/REFACTOR checkboxes."""
        spec = {
            "summary": "Test",
            "decisions": [{"id": "D1", "topic": "T", "options": ["A"], "chosen": "A", "rationale": "R"}],
            "files": [],
            "test_command": "pytest",
            "tasks": [
                {
                    "id": "T1",
                    "title": "Task 1",
                    "description": "Do something",
                    "tests": [{"file": "test.py", "name": "test", "asserts": "x"}],
                    "impl_files": ["foo.py"]
                }
            ],
            "out_of_scope": [],
            "risks": []
        }
        
        issue = {"number": 1, "title": "Test"}
        result = take_agent.render_spec_markdown(spec, issue)
        
        self.assertIn("- [ ] RED:", result)
        self.assertIn("- [ ] GREEN:", result)
        self.assertIn("- [ ] REFACTOR:", result)


class TestParseSpecMarkdown(unittest.TestCase):
    """Test spec markdown parsing."""
    
    def test_parse_front_matter(self):
        """Test parsing front matter."""
        md = """---
issue: 42
status: draft
test_command: pytest
---

# Spec

## Resumen

Test summary

## Decisiones de diseño

| ID | Topic | Opciones | Elegida | Rationale |
|----|-------|----------|---------|-----------|
| D1 | Test | A, B | A | Best |

## Archivos afectados

## Tareas

### T1: Task 1

Description here

**Tests:**
- `test.py::test_foo`: assert x

**Archivos de implementación:**
- `foo.py`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

## Fuera de alcance

## Riesgos
"""
        
        metadata, spec, progress = take_agent.parse_spec_markdown(md)
        
        self.assertEqual(metadata["issue"], 42)
        self.assertEqual(metadata["status"], "draft")
        self.assertEqual(metadata["test_command"], "pytest")
    
    def test_render_parse_roundtrip(self):
        """Test that render -> parse is a round trip for core data."""
        original_spec = {
            "summary": "Test summary",
            "decisions": [
                {
                    "id": "D1",
                    "topic": "Architecture",
                    "options": ["Option A", "Option B"],
                    "chosen": "Option A",
                    "rationale": "Better"
                }
            ],
            "files": [
                {"path": "foo.py", "action": "create", "purpose": "Test"}
            ],
            "test_command": "pytest -v",
            "tasks": [
                {
                    "id": "T1",
                    "title": "Task 1",
                    "description": "Do something",
                    "tests": [
                        {"file": "tests/test_foo.py", "name": "test_bar", "asserts": "assert x == y"}
                    ],
                    "impl_files": ["scripts/foo.py"]
                }
            ],
            "out_of_scope": ["Feature X"],
            "risks": ["Risk Y"]
        }
        
        issue = {"number": 10, "title": "Test Issue"}
        
        # Render
        rendered = take_agent.render_spec_markdown(original_spec, issue)
        
        # Parse
        metadata, parsed_spec, progress = take_agent.parse_spec_markdown(rendered)
        
        # Verify metadata
        self.assertEqual(metadata["issue"], 10)
        self.assertEqual(metadata["status"], "draft")
        self.assertEqual(metadata["test_command"], "pytest -v")
        
        # Verify spec (core fields)
        self.assertEqual(parsed_spec["summary"], original_spec["summary"])
        self.assertEqual(len(parsed_spec["decisions"]), 1)
        self.assertEqual(parsed_spec["decisions"][0]["id"], "D1")
        
        self.assertEqual(len(parsed_spec["tasks"]), 1)
        self.assertEqual(parsed_spec["tasks"][0]["id"], "T1")
        self.assertEqual(parsed_spec["tasks"][0]["title"], "Task 1")
        self.assertEqual(len(parsed_spec["tasks"][0]["tests"]), 1)
        self.assertEqual(parsed_spec["tasks"][0]["tests"][0]["file"], "tests/test_foo.py")
    
    def test_parse_progress_checkboxes(self):
        """Test parsing progress checkboxes."""
        md = """---
issue: 1
status: implementing
test_command: pytest
---

### T1: Task 1

Desc

**Tests:**
- `test.py::test`: x

**Archivos de implementación:**
- `foo.py`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [ ] REFACTOR: código limpio

### T2: Task 2

Desc

**Tests:**
- `test.py::test2`: y

**Archivos de implementación:**
- `bar.py`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio
"""
        
        metadata, spec, progress = take_agent.parse_spec_markdown(md)
        
        self.assertTrue(progress["T1"]["red"])
        self.assertTrue(progress["T1"]["green"])
        self.assertFalse(progress["T1"]["refactor"])
        
        self.assertFalse(progress["T2"]["red"])
        self.assertFalse(progress["T2"]["green"])
        self.assertFalse(progress["T2"]["refactor"])


class TestStatusHelpers(unittest.TestCase):
    """Test status and progress helpers."""
    
    def test_set_status(self):
        """Test updating status in spec file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("""---
issue: 1
status: draft
test_command: pytest
---

# Content
""")
            temp_path = f.name
        
        try:
            take_agent.set_status(temp_path, "approved")
            
            with open(temp_path, 'r') as f:
                content = f.read()
            
            self.assertIn("status: approved", content)
            self.assertNotIn("status: draft", content)
        finally:
            Path(temp_path).unlink()
    
    def test_mark_progress(self):
        """Test marking progress for a task."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("""---
issue: 1
status: implementing
test_command: pytest
---

### T1: Task 1

Desc

**Tests:**
- `test.py::test`: x

**Archivos de implementación:**
- `foo.py`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio
""")
            temp_path = f.name
        
        try:
            take_agent.mark_progress(temp_path, "T1", "red")
            
            with open(temp_path, 'r') as f:
                content = f.read()
            
            self.assertIn("- [x] RED:", content)
            # GREEN and REFACTOR should still be unchecked
            self.assertIn("- [ ] GREEN:", content)
            self.assertIn("- [ ] REFACTOR:", content)
        finally:
            Path(temp_path).unlink()


class TestLoadIssue(unittest.TestCase):
    """Test loading issue from GitHub."""
    
    def test_load_issue_with_mock_runner(self):
        """Test load_issue with mocked gh command."""
        fake_issue_data = {
            "number": 5,
            "title": "Test Issue",
            "body": "Issue body",
            "labels": [{"name": "type:feat"}],
            "comments": [],
            "milestone": {"title": "Phase 1"}
        }
        
        def mock_runner(cmd):
            result = MagicMock()
            result.stdout = json.dumps(fake_issue_data)
            return result
        
        issue = take_agent.load_issue(5, runner=mock_runner)
        
        self.assertEqual(issue["number"], 5)
        self.assertEqual(issue["title"], "Test Issue")
        self.assertEqual(issue["body"], "Issue body")


class TestBuildContext(unittest.TestCase):
    """Test building context for Tech Lead."""
    
    def test_build_context_includes_issue(self):
        """Test that context includes issue details."""
        with tempfile.TemporaryDirectory() as tmpdir:
            issue = {
                "number": 1,
                "title": "Test Issue",
                "body": "Issue body",
                "labels": [{"name": "type:feat"}],
                "comments": [],
                "milestone": None
            }
            
            context = take_agent.build_context(tmpdir, issue)
            
            self.assertIn("Issue #1", context)
            self.assertIn("Test Issue", context)
            self.assertIn("Issue body", context)


class TestReviewAndApprove(unittest.TestCase):
    """Test review_and_approve function."""
    
    def _make_mock_spec(self):
        """Create a valid spec for testing."""
        return {
            "summary": "Test implementation",
            "decisions": [
                {
                    "id": "D1",
                    "topic": "Architecture",
                    "options": ["A", "B"],
                    "chosen": "A",
                    "rationale": "Better"
                }
            ],
            "files": [
                {
                    "path": "scripts/test.py",
                    "action": "create",
                    "purpose": "Test"
                }
            ],
            "test_command": "python3 -m unittest",
            "tasks": [
                {
                    "id": "T1",
                    "title": "Task 1",
                    "description": "Do something",
                    "tests": [
                        {
                            "file": "tests/test_foo.py",
                            "name": "test_foo_works",
                            "asserts": "assert foo() == 'bar'"
                        }
                    ],
                    "impl_files": ["scripts/foo.py"]
                }
            ],
            "risks": ["None"],
            "out_of_scope": ["Other features"]
        }
    
    def test_approve_writes_file_and_commits(self):
        """Test that approving saves file with status approved, commits, and posts comment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_file = Path(tmpdir) / "test-spec.md"
            spec = self._make_mock_spec()
            issue = {
                "number": 42,
                "title": "Test Issue",
                "body": "Test body",
                "labels": [],
                "comments": [],
                "milestone": None
            }
            
            commands_run = []
            def mock_run_command(cmd):
                commands_run.append(cmd)
                return MagicMock()
            
            inputs = ["a"]  # Approve
            def mock_input(prompt):
                return inputs.pop(0)
            
            outputs = []
            def mock_print(msg):
                outputs.append(msg)
            
            final_spec, status = take_agent.review_and_approve(
                spec=spec,
                issue=issue,
                spec_file=spec_file,
                branch_name="issue/42-test",
                repo_root=tmpdir,
                run_command=mock_run_command,
                input_fn=mock_input,
                print_fn=mock_print
            )
            
            # Check status
            self.assertEqual(status, "approved")
            
            # Check file was written
            self.assertTrue(spec_file.exists())
            content = spec_file.read_text()
            self.assertIn("status: approved", content)
            self.assertIn("Test implementation", content)
            
            # Check git add and commit were called
            self.assertEqual(len(commands_run), 3)
            self.assertEqual(commands_run[0], ["git", "add", str(spec_file)])
            self.assertEqual(commands_run[1], ["git", "commit", "-m", "docs: spec de implementación (#42)"])
            
            # Check gh comment was called with decisions table
            self.assertEqual(commands_run[2][0:3], ["gh", "issue", "comment"])
            self.assertEqual(commands_run[2][3], "42")
            comment_body = commands_run[2][5]
            self.assertIn("Especificación de implementación aprobada", comment_body)
            self.assertIn("| ID | Tema | Elegida | Por qué |", comment_body)
            self.assertIn("| D1 | Architecture | A | Better |", comment_body)
            self.assertIn("- Do something", comment_body)
            self.assertIn("python3 -m unittest", comment_body)
    
    def test_exit_saves_draft(self):
        """Test that exiting saves spec as draft."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_file = Path(tmpdir) / "test-spec.md"
            spec = self._make_mock_spec()
            issue = {
                "number": 42,
                "title": "Test Issue",
                "body": "",
                "labels": [],
                "comments": [],
                "milestone": None
            }
            
            inputs = ["x"]  # Exit
            def mock_input(prompt):
                return inputs.pop(0)
            
            outputs = []
            def mock_print(msg):
                outputs.append(msg)
            
            final_spec, status = take_agent.review_and_approve(
                spec=spec,
                issue=issue,
                spec_file=spec_file,
                branch_name="issue/42-test",
                repo_root=tmpdir,
                run_command=lambda cmd: MagicMock(),
                input_fn=mock_input,
                print_fn=mock_print
            )
            
            # Check status
            self.assertEqual(status, "draft")
            
            # Check file was written
            self.assertTrue(spec_file.exists())
            content = spec_file.read_text()
            # Status should be draft (default when parsing)
            self.assertIn("Test implementation", content)
    
    def test_edit_with_invalid_spec_discards(self):
        """Test that editing with invalid spec discards changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_file = Path(tmpdir) / "test-spec.md"
            spec = self._make_mock_spec()
            issue = {
                "number": 42,
                "title": "Test",
                "body": "",
                "labels": [],
                "comments": [],
                "milestone": None
            }
            
            invalid_edited = "---\nissue: 42\nstatus: draft\n---\n# Invalid spec without required fields"
            
            inputs = ["e", "x"]  # Edit, then exit
            def mock_input(prompt):
                return inputs.pop(0)
            
            outputs = []
            def mock_print(msg):
                outputs.append(msg)
            
            def mock_edit(text):
                return invalid_edited
            
            final_spec, status = take_agent.review_and_approve(
                spec=spec,
                issue=issue,
                spec_file=spec_file,
                branch_name="issue/42-test",
                repo_root=tmpdir,
                run_command=lambda cmd: MagicMock(),
                input_fn=mock_input,
                print_fn=mock_print,
                edit_fn=mock_edit
            )
            
            # Check that error message was printed
            error_msgs = [msg for msg in outputs if "Error" in msg or "descartados" in msg]
            self.assertTrue(len(error_msgs) > 0, "Should have printed error/discard message")
            
            # Original spec should be unchanged
            self.assertEqual(final_spec["summary"], "Test implementation")
            self.assertEqual(status, "draft")


if __name__ == "__main__":
    unittest.main()

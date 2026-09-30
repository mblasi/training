#!/usr/bin/env python3
"""
Unit tests for backlog.py
"""
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock


# Import backlog.py module
repo_root = Path(__file__).parent.parent
backlog_path = repo_root / "scripts" / "backlog.py"
spec = importlib.util.spec_from_file_location("backlog", backlog_path)
backlog = importlib.util.module_from_spec(spec)
sys.modules["backlog"] = backlog
spec.loader.exec_module(backlog)

# Import issue_agent module
sys.path.insert(0, str(repo_root / "scripts"))
import issue_agent


class TestSlugify(unittest.TestCase):
    """Test slug generation."""
    
    def test_basic_slug(self):
        self.assertEqual(backlog.slugify("Hello World"), "hello-world")
    
    def test_special_characters(self):
        self.assertEqual(backlog.slugify("Foo & Bar!"), "foo-bar")
    
    def test_multiple_spaces(self):
        self.assertEqual(backlog.slugify("Too   Many    Spaces"), "too-many-spaces")
    
    def test_trailing_hyphens(self):
        self.assertEqual(backlog.slugify("-Leading and Trailing-"), "leading-and-trailing")
    
    def test_max_length(self):
        long_title = "A" * 100
        result = backlog.slugify(long_title)
        self.assertLessEqual(len(result), 50)
    
    def test_non_ascii(self):
        self.assertEqual(backlog.slugify("Configuración"), "configuraci-n")


class TestParseIssueNumber(unittest.TestCase):
    """Test issue number extraction from branch names."""
    
    def test_valid_issue_branch(self):
        self.assertEqual(backlog.parse_issue_number_from_branch("issue/123-foo-bar"), 123)
    
    def test_issue_branch_no_slug(self):
        self.assertEqual(backlog.parse_issue_number_from_branch("issue/42"), 42)
    
    def test_non_issue_branch(self):
        self.assertIsNone(backlog.parse_issue_number_from_branch("main"))
        self.assertIsNone(backlog.parse_issue_number_from_branch("feature/foo"))
        self.assertIsNone(backlog.parse_issue_number_from_branch("bugfix/something"))


class TestRenderBacklog(unittest.TestCase):
    """Test backlog rendering function."""
    
    def setUp(self):
        """Setup test fixtures."""
        self.maxDiff = None
    
    def test_empty_backlog(self):
        """Test rendering with no issues."""
        result = backlog.render_backlog([])
        self.assertIn("# Backlog", result)
        self.assertIn("_Nada por ahora._", result)
    
    def test_wip_issues(self):
        """Test WIP section rendering."""
        issues = [
            {
                "number": 1,
                "title": "Test WIP issue",
                "state": "OPEN",
                "labels": [{"name": "status:wip"}, {"name": "type:feat"}],
                "assignees": [{"login": "user1"}],
                "url": "https://github.com/owner/repo/issues/1",
                "milestone": None,
            }
        ]
        result = backlog.render_backlog(issues)
        self.assertIn("## 🚧 En curso (WIP)", result)
        self.assertIn("- [ ] [#1](https://github.com/owner/repo/issues/1) Test WIP issue · feat · @user1", result)
    
    def test_review_issues(self):
        """Test review section rendering."""
        issues = [
            {
                "number": 2,
                "title": "Test review issue",
                "state": "OPEN",
                "labels": [{"name": "status:review"}, {"name": "type:fix"}],
                "assignees": [{"login": "user2"}],
                "url": "https://github.com/owner/repo/issues/2",
                "milestone": None,
            }
        ]
        result = backlog.render_backlog(issues)
        self.assertIn("## 👀 En revisión", result)
        self.assertIn("- [ ] [#2](https://github.com/owner/repo/issues/2) Test review issue · fix · @user2", result)
    
    def test_todo_by_milestone(self):
        """Test todo section with milestones."""
        issues = [
            {
                "number": 3,
                "title": "Phase 0 task",
                "state": "OPEN",
                "labels": [{"name": "status:todo"}, {"name": "type:chore"}],
                "assignees": [],
                "url": "https://github.com/owner/repo/issues/3",
                "milestone": {"title": "Fase 0 - Fundaciones"},
            },
            {
                "number": 4,
                "title": "Phase 1 task",
                "state": "OPEN",
                "labels": [{"name": "status:todo"}, {"name": "type:feat"}],
                "assignees": [],
                "url": "https://github.com/owner/repo/issues/4",
                "milestone": {"title": "Fase 1 - MVP individual"},
            },
            {
                "number": 5,
                "title": "No phase task",
                "state": "OPEN",
                "labels": [{"name": "status:todo"}],
                "assignees": [],
                "url": "https://github.com/owner/repo/issues/5",
                "milestone": None,
            }
        ]
        result = backlog.render_backlog(issues)
        self.assertIn("## 📋 Pendiente", result)
        self.assertIn("### Fase 0 - Fundaciones", result)
        self.assertIn("### Fase 1 - MVP individual", result)
        self.assertIn("### Sin fase", result)
        
        # Verify ordering
        phase0_idx = result.index("### Fase 0 - Fundaciones")
        phase1_idx = result.index("### Fase 1 - MVP individual")
        no_phase_idx = result.index("### Sin fase")
        self.assertLess(phase0_idx, phase1_idx)
        self.assertLess(phase1_idx, no_phase_idx)
    
    def test_done_section(self):
        """Test done section with closed issues."""
        issues = [
            {
                "number": 10,
                "title": "Old completed",
                "state": "CLOSED",
                "labels": [{"name": "type:feat"}],
                "assignees": [],
                "url": "https://github.com/owner/repo/issues/10",
                "milestone": None,
                "closedAt": "2026-01-01T00:00:00Z",
            },
            {
                "number": 11,
                "title": "Recently completed",
                "state": "CLOSED",
                "labels": [{"name": "type:fix"}],
                "assignees": [],
                "url": "https://github.com/owner/repo/issues/11",
                "milestone": None,
                "closedAt": "2026-12-31T23:59:59Z",
            }
        ]
        result = backlog.render_backlog(issues)
        self.assertIn("## ✅ Hecho", result)
        self.assertIn("- [x] [#10]", result)
        self.assertIn("- [x] [#11]", result)
        
        # Verify most recent first
        recent_idx = result.index("- [x] [#11]")
        old_idx = result.index("- [x] [#10]")
        self.assertLess(recent_idx, old_idx)
    
    def test_blocked_marker(self):
        """Test blocked issue marker."""
        issues = [
            {
                "number": 20,
                "title": "Blocked task",
                "state": "OPEN",
                "labels": [{"name": "status:todo"}, {"name": "blocked"}],
                "assignees": [],
                "url": "https://github.com/owner/repo/issues/20",
                "milestone": None,
            }
        ]
        result = backlog.render_backlog(issues)
        self.assertIn("⛔", result)
        self.assertIn("- [ ] ⛔ [#20]", result)
    
    def test_determinism(self):
        """Test that rendering is deterministic."""
        issues = [
            {
                "number": 1,
                "title": "Issue 1",
                "state": "OPEN",
                "labels": [{"name": "status:todo"}],
                "assignees": [],
                "url": "https://github.com/owner/repo/issues/1",
                "milestone": None,
            },
            {
                "number": 2,
                "title": "Issue 2",
                "state": "OPEN",
                "labels": [{"name": "status:wip"}],
                "assignees": [],
                "url": "https://github.com/owner/repo/issues/2",
                "milestone": None,
            }
        ]
        
        result1 = backlog.render_backlog(issues)
        result2 = backlog.render_backlog(issues)
        self.assertEqual(result1, result2)
    
    def test_done_limit(self):
        """Test that done section is limited to 50 items."""
        issues = [
            {
                "number": i,
                "title": f"Completed {i}",
                "state": "CLOSED",
                "labels": [],
                "assignees": [],
                "url": f"https://github.com/owner/repo/issues/{i}",
                "milestone": None,
                "closedAt": f"2026-01-{i:02d}T00:00:00Z",
            }
            for i in range(1, 101)
        ]
        
        result = backlog.render_backlog(issues)
        
        # Count checkbox items in done section
        done_section = result.split("## ✅ Hecho")[1]
        done_count = done_section.count("- [x]")
        self.assertLessEqual(done_count, 50)
    
    def test_mixed_scenario(self):
        """Test complex scenario with all sections."""
        issues = [
            {
                "number": 1,
                "title": "WIP feature",
                "state": "OPEN",
                "labels": [{"name": "status:wip"}, {"name": "type:feat"}],
                "assignees": [{"login": "alice"}],
                "url": "https://github.com/owner/repo/issues/1",
                "milestone": {"title": "Fase 1 - MVP individual"},
            },
            {
                "number": 2,
                "title": "In review",
                "state": "OPEN",
                "labels": [{"name": "status:review"}, {"name": "type:fix"}],
                "assignees": [{"login": "bob"}],
                "url": "https://github.com/owner/repo/issues/2",
                "milestone": None,
            },
            {
                "number": 3,
                "title": "Blocked todo",
                "state": "OPEN",
                "labels": [{"name": "status:todo"}, {"name": "blocked"}],
                "assignees": [],
                "url": "https://github.com/owner/repo/issues/3",
                "milestone": {"title": "Fase 0 - Fundaciones"},
            },
            {
                "number": 4,
                "title": "Completed",
                "state": "CLOSED",
                "labels": [{"name": "type:docs"}],
                "assignees": [],
                "url": "https://github.com/owner/repo/issues/4",
                "milestone": None,
                "closedAt": "2026-09-01T00:00:00Z",
            }
        ]
        
        result = backlog.render_backlog(issues)
        
        # All sections present
        self.assertIn("## 🚧 En curso (WIP)", result)
        self.assertIn("## 👀 En revisión", result)
        self.assertIn("## 📋 Pendiente", result)
        self.assertIn("## ✅ Hecho", result)
        
        # Correct content
        self.assertIn("WIP feature", result)
        self.assertIn("In review", result)
        self.assertIn("⛔ [#3]", result)
        self.assertIn("- [x] [#4]", result)


class TestIssueAgent(unittest.TestCase):
    """Test issue_agent module functionality."""
    
    def test_parse_final_spec_json(self):
        """Test JSON parsing from agent response with /SPEC marker."""
        text = '''/SPEC
```json
{"issues": [{"title": "Test", "type": "feat", "body": "Body"}]}
```'''
        result = issue_agent.parse_final_spec(text)
        self.assertIsNotNone(result)
        self.assertEqual(len(result["issues"]), 1)
        self.assertEqual(result["issues"][0]["title"], "Test")
    
    def test_parse_final_spec_with_fence(self):
        """Test JSON parsing from markdown code fence with /SPEC."""
        text = '''Here is the spec:
/SPEC
```json
{"issues": [{"title": "Test", "type": "feat", "body": "Body"}]}
```
'''
        result = issue_agent.parse_final_spec(text)
        self.assertIsNotNone(result)
        self.assertEqual(len(result["issues"]), 1)
    
    def test_validate_issue_spec_valid(self):
        """Test validation of valid spec."""
        spec = {
            "issues": [
                {
                    "title": "Test issue",
                    "type": "feat",
                    "body": "## Context\n\nTest body",
                    "areas": ["web"],
                    "phase": 1
                }
            ]
        }
        valid, error = issue_agent.validate_issue_spec(spec)
        self.assertTrue(valid, f"Validation failed: {error}")
    
    def test_validate_issue_spec_missing_title(self):
        """Test validation fails for missing title."""
        spec = {"issues": [{"type": "feat", "body": "Body"}]}
        valid, error = issue_agent.validate_issue_spec(spec)
        self.assertFalse(valid)
        self.assertIn("title", error.lower())
    
    def test_validate_issue_spec_invalid_type(self):
        """Test validation fails for invalid type."""
        spec = {"issues": [{"title": "Test", "type": "invalid", "body": "Body"}]}
        valid, error = issue_agent.validate_issue_spec(spec)
        self.assertFalse(valid)
        self.assertIn("type", error.lower())
    
    def test_validate_issue_spec_invalid_area(self):
        """Test validation fails for invalid area."""
        spec = {"issues": [{"title": "Test", "type": "feat", "body": "Body", "areas": ["invalid"]}]}
        valid, error = issue_agent.validate_issue_spec(spec)
        self.assertFalse(valid)
        self.assertIn("area", error.lower())
    
    def test_validate_issue_spec_invalid_phase(self):
        """Test validation fails for invalid phase."""
        spec = {"issues": [{"title": "Test", "type": "feat", "body": "Body", "phase": 5}]}
        valid, error = issue_agent.validate_issue_spec(spec)
        self.assertFalse(valid)
        self.assertIn("phase", error.lower())
    
    def test_tool_sandbox_path_validation(self):
        """Test that ToolSandbox rejects paths outside repo."""
        sandbox = issue_agent.ToolSandbox(str(repo_root))
        
        # Valid path (relative)
        try:
            sandbox._validate_path("some_file.txt")
        except ValueError:
            self.fail("Valid path rejected")
        
        # Invalid path (outside repo)
        with self.assertRaises(ValueError):
            sandbox._validate_path("../../etc/passwd")
        
        with self.assertRaises(ValueError):
            sandbox._validate_path("/etc/passwd")
    
    def test_tool_sandbox_read_file(self):
        """Test reading a file through sandbox."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello from sandbox test")
            
            sandbox = issue_agent.ToolSandbox(tmpdir)
            content = sandbox.read_file("test.txt")
            self.assertIn("Hello from sandbox test", content)
            self.assertNotIn("Error", content)
    
    def test_tool_sandbox_read_nonexistent(self):
        """Test reading nonexistent file returns error."""
        sandbox = issue_agent.ToolSandbox(str(repo_root))
        content = sandbox.read_file("nonexistent.txt")
        self.assertIn("Error", content)
    
    def test_llm_client_mock(self):
        """Test LLMClient with mock (no real network call)."""
        # Create a mock client
        client = issue_agent.LLMClient("http://fake.url", "fake-key", "fake-model")
        
        # We don't test actual network calls in unit tests
        # Just verify instantiation works
        self.assertEqual(client.model, "fake-model")
        self.assertEqual(client.api_key, "fake-key")
    
    def test_run_interview_mock(self):
        """Test interview loop with mocked LLM client."""
        # Create mock client that returns a valid spec
        mock_client = MagicMock()
        mock_client.chat.return_value = {
            "role": "assistant",
            "content": '''Perfecto, aquí está la especificación:

/SPEC
```json
{
  "issues": [
    {
      "title": "Test issue from interview",
      "type": "feat",
      "body": "## Contexto\\n\\nTest context",
      "areas": ["web"],
      "phase": 1
    }
  ]
}
```
'''
        }
        
        # Mock input to send /listo immediately
        inputs = ["/listo"]
        input_idx = [0]
        
        def mock_input(prompt):
            idx = input_idx[0]
            input_idx[0] += 1
            if idx < len(inputs):
                return inputs[idx]
            raise EOFError
        
        outputs = []
        def mock_print(text):
            outputs.append(text)
        
        sandbox = issue_agent.ToolSandbox(str(repo_root))
        
        spec, messages, session_id = issue_agent.run_interview(
            mock_client,
            sandbox,
            str(repo_root),
            "Test idea",
            input_fn=mock_input,
            print_fn=mock_print
        )
        
        self.assertIsNotNone(spec)
        self.assertEqual(len(spec["issues"]), 1)
        self.assertEqual(spec["issues"][0]["title"], "Test issue from interview")


class TestCreateIssueFromSpec(unittest.TestCase):
    """Test the new create_issue_from_spec function."""
    
    def test_function_exists(self):
        """Test that create_issue_from_spec function exists."""
        self.assertTrue(hasattr(backlog, "create_issue_from_spec"))


class TestScriptsSyntax(unittest.TestCase):
    """Test that all scripts/*.py files are syntactically valid."""
    
    def test_all_scripts_compile(self):
        """Test that all Python scripts in scripts/ directory compile without syntax errors."""
        import py_compile
        
        scripts_dir = repo_root / "scripts"
        script_files = list(scripts_dir.glob("*.py"))
        
        self.assertGreater(len(script_files), 0, "Should find at least one .py file in scripts/")
        
        for script_file in script_files:
            with self.subTest(script=script_file.name):
                try:
                    py_compile.compile(str(script_file), doraise=True)
                except py_compile.PyCompileError as e:
                    self.fail(f"Syntax error in {script_file.name}: {e}")


class TestAskHelper(unittest.TestCase):
    """Test the ask() helper function for EOF-safe input."""
    
    def test_ask_normal_input(self):
        """Test that ask() returns stripped input in normal case."""
        with unittest.mock.patch('builtins.input', return_value="  hello  "):
            result = backlog.ask("prompt> ")
            self.assertEqual(result, "hello")
    
    def test_ask_eof_returns_default(self):
        """Test that ask() returns default on EOF."""
        with unittest.mock.patch('builtins.input', side_effect=EOFError):
            result = backlog.ask("prompt> ", default="default_value")
            self.assertEqual(result, "default_value")
    
    def test_ask_keyboard_interrupt_returns_default(self):
        """Test that ask() returns default on KeyboardInterrupt."""
        with unittest.mock.patch('builtins.input', side_effect=KeyboardInterrupt):
            result = backlog.ask("prompt> ", default="no")
            self.assertEqual(result, "no")
    
    def test_ask_eof_empty_default(self):
        """Test that ask() returns empty string when no default provided."""
        with unittest.mock.patch('builtins.input', side_effect=EOFError):
            result = backlog.ask("prompt> ")
            self.assertEqual(result, "")


class TestMergeAbort(unittest.TestCase):
    """Test that cmd_merge aborts cleanly on EOF when checks fail."""
    
    def test_merge_abort_on_eof(self):
        """Test that cmd_merge exits with code 1 when user confirms 'no' via EOF."""
        # Mock all the run_command calls and ask()
        with unittest.mock.patch.object(backlog, 'run_command') as mock_run:
            with unittest.mock.patch.object(backlog, 'ask', return_value='n') as mock_ask:
                with unittest.mock.patch.object(backlog, 'get_default_branch', return_value='main'):
                    # Setup mocks
                    pr_result = unittest.mock.MagicMock()
                    pr_result.stdout = '[{"number": 42, "url": "http://test", "headRefName": "issue/7-test"}]'
                    
                    checks_result = unittest.mock.MagicMock()
                    checks_result.stdout = 'Some checks failed\nFAIL: test'
                    
                    mock_run.side_effect = [pr_result, checks_result]
                    
                    # Create mock args
                    args = unittest.mock.MagicMock()
                    args.issue = 7
                    args.force = False
                    
                    # Should exit with code 1
                    with self.assertRaises(SystemExit) as cm:
                        backlog.cmd_merge(args)
                    
                    self.assertEqual(cm.exception.code, 1)
                    mock_ask.assert_called_once()
    
    def test_merge_force_skips_prompt(self):
        """Test that cmd_merge with --force skips prompt even when checks fail."""
        with unittest.mock.patch.object(backlog, 'run_command') as mock_run:
            with unittest.mock.patch.object(backlog, 'ask') as mock_ask:
                with unittest.mock.patch.object(backlog, 'get_default_branch', return_value='main'):
                    with unittest.mock.patch('builtins.print'):
                        # Setup mocks with proper result objects
                        pr_result = unittest.mock.MagicMock()
                        pr_result.stdout = '[{"number": 42, "url": "http://test", "headRefName": "issue/7-test"}]'
                        
                        checks_result = unittest.mock.MagicMock()
                        checks_result.stdout = 'Some checks failed\nFAIL: test'
                        
                        merge_result = unittest.mock.MagicMock()
                        merge_result.stdout = ''
                        
                        # New: gh issue view (from finalize_issue_after_merge)
                        issue_view_result = unittest.mock.MagicMock()
                        issue_view_result.stdout = '{"state": "CLOSED", "labels": [{"name": "status:review"}]}'
                        
                        # New: gh issue edit --remove-label (from finalize_issue_after_merge)
                        issue_edit_result = unittest.mock.MagicMock()
                        issue_edit_result.stdout = ''
                        
                        checkout_result = unittest.mock.MagicMock()
                        checkout_result.stdout = ''
                        
                        pull_result = unittest.mock.MagicMock()
                        pull_result.stdout = ''
                        
                        mock_run.side_effect = [
                            pr_result,
                            checks_result,
                            merge_result,
                            issue_view_result,
                            issue_edit_result,
                            checkout_result,
                            pull_result
                        ]
                        
                        args = unittest.mock.MagicMock()
                        args.issue = 7
                        args.force = True
                        
                        # Should NOT exit, should proceed with merge
                        backlog.cmd_merge(args)
                        
                        # ask() should NOT have been called
                        mock_ask.assert_not_called()


if __name__ == "__main__":
    unittest.main()

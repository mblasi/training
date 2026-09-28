#!/usr/bin/env python3
"""
Unit tests for backlog.py
"""
import importlib.util
import sys
import unittest
from pathlib import Path


# Import backlog.py module
repo_root = Path(__file__).parent.parent
backlog_path = repo_root / "scripts" / "backlog.py"
spec = importlib.util.spec_from_file_location("backlog", backlog_path)
backlog = importlib.util.module_from_spec(spec)
sys.modules["backlog"] = backlog
spec.loader.exec_module(backlog)


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


if __name__ == "__main__":
    unittest.main()

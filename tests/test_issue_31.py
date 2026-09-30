#!/usr/bin/env python3
"""
Tests for issue #31: merge should remove status labels and close issue.
"""
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

# Import backlog.py module
repo_root = Path(__file__).parent.parent
backlog_path = repo_root / "scripts" / "backlog.py"
spec = importlib.util.spec_from_file_location("backlog", backlog_path)
backlog = importlib.util.module_from_spec(spec)
sys.modules["backlog"] = backlog
spec.loader.exec_module(backlog)


class TestFinalizeIssueAfterMerge(unittest.TestCase):
    """Test finalize_issue_after_merge helper function."""
    
    def _make_run_command_side_effect(self, issue_data, close_called=False):
        """
        Create a side_effect function that dispatches on the command.
        
        Args:
            issue_data: dict with 'state' and 'labels' (list of label names)
            close_called: whether we expect a close call
        """
        calls_log = []
        
        def side_effect(cmd, **kwargs):
            calls_log.append(cmd)
            result = mock.MagicMock()
            result.returncode = 0
            
            # gh issue view ... --json state,labels
            if cmd[0] == "gh" and cmd[1] == "issue" and cmd[2] == "view":
                labels_obj = [{"name": name} for name in issue_data["labels"]]
                output = {
                    "state": issue_data["state"],
                    "labels": labels_obj
                }
                result.stdout = json.dumps(output)
                return result
            
            # gh issue edit ... --remove-label ...
            elif cmd[0] == "gh" and cmd[1] == "issue" and cmd[2] == "edit" and "--remove-label" in cmd:
                result.stdout = ""
                return result
            
            # gh issue close ... --reason completed
            elif cmd[0] == "gh" and cmd[1] == "issue" and cmd[2] == "close":
                if not close_called:
                    raise AssertionError(f"Unexpected gh issue close call: {cmd}")
                result.stdout = ""
                return result
            
            else:
                raise AssertionError(f"Unexpected command: {cmd}")
        
        side_effect.calls_log = calls_log
        return side_effect
    
    def test_removes_status_and_blocked_labels(self):
        """Test that status:review and blocked are removed, other labels are kept."""
        issue_data = {
            "state": "CLOSED",
            "labels": ["status:review", "blocked", "type:fix", "area:agents"]
        }
        
        side_effect = self._make_run_command_side_effect(issue_data)
        
        with mock.patch.object(backlog, 'run_command', side_effect=side_effect):
            removed_labels, closed_by_harness = backlog.finalize_issue_after_merge(31)
        
        # Should return the removed labels in order
        self.assertEqual(removed_labels, ["status:review", "blocked"])
        self.assertEqual(closed_by_harness, False)
        
        # Verify calls
        calls = side_effect.calls_log
        # First call: gh issue view
        self.assertEqual(calls[0][:3], ["gh", "issue", "view"])
        
        # Second call: gh issue edit with --remove-label
        edit_call = calls[1]
        self.assertEqual(edit_call[:4], ["gh", "issue", "edit", "31"])
        self.assertIn("--remove-label", edit_call)
        remove_idx = edit_call.index("--remove-label")
        removed = edit_call[remove_idx + 1]
        # Labels should be comma-separated in constant order
        self.assertEqual(removed, "status:review,blocked")
        
        # No close call since state was CLOSED
        self.assertEqual(len(calls), 2)
    
    def test_no_labels_to_remove(self):
        """Test that no gh issue edit call is made when no status labels are present."""
        issue_data = {
            "state": "CLOSED",
            "labels": ["type:fix", "area:agents"]
        }
        
        calls_log = []
        
        def side_effect(cmd, **kwargs):
            calls_log.append(cmd)
            result = mock.MagicMock()
            result.returncode = 0
            
            if cmd[0] == "gh" and cmd[1] == "issue" and cmd[2] == "view":
                labels_obj = [{"name": name} for name in issue_data["labels"]]
                output = {
                    "state": issue_data["state"],
                    "labels": labels_obj
                }
                result.stdout = json.dumps(output)
                return result
            else:
                raise AssertionError(f"Unexpected command: {cmd}")
        
        with mock.patch.object(backlog, 'run_command', side_effect=side_effect):
            removed_labels, closed_by_harness = backlog.finalize_issue_after_merge(31)
        
        self.assertEqual(removed_labels, [])
        self.assertEqual(closed_by_harness, False)
        
        # Only the view call should have been made
        self.assertEqual(len(calls_log), 1)
    
    def test_closes_open_issue(self):
        """Test that an OPEN issue is closed with --reason completed."""
        issue_data = {
            "state": "OPEN",
            "labels": ["status:wip", "type:feat"]
        }
        
        calls_log = []
        
        def side_effect(cmd, **kwargs):
            calls_log.append(cmd)
            result = mock.MagicMock()
            result.returncode = 0
            
            if cmd[0] == "gh" and cmd[1] == "issue" and cmd[2] == "view":
                labels_obj = [{"name": name} for name in issue_data["labels"]]
                output = {
                    "state": issue_data["state"],
                    "labels": labels_obj
                }
                result.stdout = json.dumps(output)
                return result
            
            elif cmd[0] == "gh" and cmd[1] == "issue" and cmd[2] == "edit":
                result.stdout = ""
                return result
            
            elif cmd[0] == "gh" and cmd[1] == "issue" and cmd[2] == "close":
                # Verify --reason completed
                self.assertIn("--reason", cmd)
                reason_idx = cmd.index("--reason")
                self.assertEqual(cmd[reason_idx + 1], "completed")
                result.stdout = ""
                return result
            
            else:
                raise AssertionError(f"Unexpected command: {cmd}")
        
        with mock.patch.object(backlog, 'run_command', side_effect=side_effect):
            removed_labels, closed_by_harness = backlog.finalize_issue_after_merge(31)
        
        self.assertEqual(removed_labels, ["status:wip"])
        self.assertEqual(closed_by_harness, True)
        
        # Should have 3 calls: view, edit (remove label), close
        self.assertEqual(len(calls_log), 3)
        self.assertEqual(calls_log[0][1:3], ["issue", "view"])
        self.assertEqual(calls_log[1][1:3], ["issue", "edit"])
        self.assertEqual(calls_log[2][1:3], ["issue", "close"])


class TestCmdMergeIntegration(unittest.TestCase):
    """Test cmd_merge with finalize_issue_after_merge integration."""
    
    def test_merge_happy_path_finalizes_issue(self):
        """Test that successful merge calls finalize_issue_after_merge and prints result."""
        calls_log = []
        
        def side_effect(cmd, **kwargs):
            calls_log.append(cmd)
            result = mock.MagicMock()
            result.returncode = 0
            result.stdout = ""
            
            # gh pr list
            if cmd[0] == "gh" and cmd[1] == "pr" and cmd[2] == "list":
                result.stdout = json.dumps([{
                    "number": 42,
                    "url": "https://github.com/test/repo/pull/42",
                    "headRefName": "issue/31-test"
                }])
                return result
            
            # gh pr checks
            elif cmd[0] == "gh" and cmd[1] == "pr" and cmd[2] == "checks":
                result.stdout = "All checks passed"
                return result
            
            # gh pr merge
            elif cmd[0] == "gh" and cmd[1] == "pr" and cmd[2] == "merge":
                # This is the merge call, should come BEFORE finalize
                result.stdout = ""
                return result
            
            # gh issue view (from finalize)
            elif cmd[0] == "gh" and cmd[1] == "issue" and cmd[2] == "view":
                result.stdout = json.dumps({
                    "state": "CLOSED",
                    "labels": [{"name": "status:review"}, {"name": "type:fix"}]
                })
                return result
            
            # gh issue edit --remove-label
            elif cmd[0] == "gh" and cmd[1] == "issue" and cmd[2] == "edit" and "--remove-label" in cmd:
                result.stdout = ""
                return result
            
            # git checkout / pull
            elif cmd[0] == "git":
                result.stdout = ""
                return result
            
            else:
                raise AssertionError(f"Unexpected command: {cmd}")
        
        outputs = []
        def mock_print(text, **kwargs):
            outputs.append(text)
        
        with mock.patch.object(backlog, 'run_command', side_effect=side_effect):
            with mock.patch.object(backlog, 'get_default_branch', return_value='main'):
                with mock.patch('builtins.print', side_effect=mock_print):
                    args = mock.MagicMock()
                    args.issue = 31
                    args.force = False
                    
                    backlog.cmd_merge(args)
        
        # Verify gh pr merge comes before gh issue edit
        merge_idx = None
        edit_idx = None
        for i, cmd in enumerate(calls_log):
            if cmd[0] == "gh" and cmd[1] == "pr" and cmd[2] == "merge":
                merge_idx = i
            if cmd[0] == "gh" and cmd[1] == "issue" and cmd[2] == "edit":
                edit_idx = i
        
        self.assertIsNotNone(merge_idx, "gh pr merge should be called")
        self.assertIsNotNone(edit_idx, "gh issue edit should be called")
        self.assertLess(merge_idx, edit_idx, "merge should come before issue edit")
        
        # Verify final message
        final_output = "\n".join(outputs)
        self.assertIn("PR #42 merged successfully. Issue #31 closed.", final_output)
        self.assertIn("Labels quitados: status:review", final_output)
    
    def test_merge_fails_no_finalize(self):
        """Test that if merge fails (checks fail, user says no), finalize is NOT called."""
        calls_log = []
        
        def side_effect(cmd, **kwargs):
            calls_log.append(cmd)
            result = mock.MagicMock()
            result.returncode = 0
            
            # gh pr list
            if cmd[0] == "gh" and cmd[1] == "pr" and cmd[2] == "list":
                result.stdout = json.dumps([{
                    "number": 42,
                    "url": "https://github.com/test/repo/pull/42",
                    "headRefName": "issue/31-test"
                }])
                return result
            
            # gh pr checks - fail
            elif cmd[0] == "gh" and cmd[1] == "pr" and cmd[2] == "checks":
                result.stdout = "FAIL: some test"
                return result
            
            else:
                # Should not reach any other gh commands
                raise AssertionError(f"Unexpected command after abort: {cmd}")
        
        with mock.patch.object(backlog, 'run_command', side_effect=side_effect):
            with mock.patch.object(backlog, 'get_default_branch', return_value='main'):
                with mock.patch.object(backlog, 'ask', return_value='n'):
                    args = mock.MagicMock()
                    args.issue = 31
                    args.force = False
                    
                    with self.assertRaises(SystemExit) as cm:
                        backlog.cmd_merge(args)
                    
                    self.assertEqual(cm.exception.code, 1)
        
        # Verify no gh issue edit or gh issue close calls
        for cmd in calls_log:
            if cmd[0] == "gh" and cmd[1] == "issue":
                self.assertNotIn(cmd[2], ["edit", "close"], "Should not call gh issue edit/close after abort")


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""
Tests for new features in issue #15:
- is_test_file JS/TS patterns
- build_test_cmd with shell detection
- test_support_files in specs
- LLM max_tokens and timeout
- Session issue tracking
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Import modules
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "scripts"))

import tdd_runner
import take_agent
import agent_core


class TestIsTestFile(unittest.TestCase):
    """Test is_test_file with Python and JS/TS patterns."""
    
    def test_python_patterns(self):
        """Test existing Python test file patterns."""
        self.assertTrue(tdd_runner.is_test_file("tests/test_foo.py"))
        self.assertTrue(tdd_runner.is_test_file("src/test_bar.py"))
        self.assertTrue(tdd_runner.is_test_file("pkg/module_test.py"))
        self.assertTrue(tdd_runner.is_test_file("foo.test.py"))
        self.assertTrue(tdd_runner.is_test_file("bar.spec.py"))
    
    def test_js_ts_extensions(self):
        """Test JS/TS test file extensions."""
        # .test.* patterns
        self.assertTrue(tdd_runner.is_test_file("src/component.test.ts"))
        self.assertTrue(tdd_runner.is_test_file("src/component.test.tsx"))
        self.assertTrue(tdd_runner.is_test_file("src/utils.test.js"))
        self.assertTrue(tdd_runner.is_test_file("src/utils.test.jsx"))
        self.assertTrue(tdd_runner.is_test_file("src/utils.test.mjs"))
        self.assertTrue(tdd_runner.is_test_file("src/utils.test.cjs"))
        
        # .spec.* patterns
        self.assertTrue(tdd_runner.is_test_file("src/component.spec.ts"))
        self.assertTrue(tdd_runner.is_test_file("src/component.spec.tsx"))
        self.assertTrue(tdd_runner.is_test_file("src/utils.spec.js"))
        self.assertTrue(tdd_runner.is_test_file("src/utils.spec.jsx"))
        self.assertTrue(tdd_runner.is_test_file("src/utils.spec.mjs"))
        self.assertTrue(tdd_runner.is_test_file("src/utils.spec.cjs"))
    
    def test_test_directory_segments(self):
        """Test paths containing test/tests/__tests__ segments."""
        self.assertTrue(tdd_runner.is_test_file("apps/api/test/health.test.ts"))
        self.assertTrue(tdd_runner.is_test_file("packages/shared/__tests__/x.ts"))
        self.assertTrue(tdd_runner.is_test_file("src/tests/integration.py"))
        self.assertTrue(tdd_runner.is_test_file("module/test/unit.js"))
    
    def test_negatives(self):
        """Test files that should NOT match."""
        # Should not match partial substrings
        self.assertFalse(tdd_runner.is_test_file("src/contest.ts"))
        self.assertFalse(tdd_runner.is_test_file("latest/foo.ts"))
        self.assertFalse(tdd_runner.is_test_file("fastest_algorithm.py"))
        self.assertFalse(tdd_runner.is_test_file("protest.js"))
        
        # Normal production files
        self.assertFalse(tdd_runner.is_test_file("src/index.ts"))
        self.assertFalse(tdd_runner.is_test_file("lib/utils.py"))
        self.assertFalse(tdd_runner.is_test_file("components/Button.tsx"))


class TestBuildTestCmd(unittest.TestCase):
    """Test build_test_cmd with shell operators detection."""
    
    def test_simple_command_split(self):
        """Test simple command without shell operators."""
        cmd = tdd_runner.build_test_cmd("python3 -m unittest discover -s tests -v")
        self.assertIsInstance(cmd, list)
        self.assertIn("python3", cmd)
        self.assertIn("-m", cmd)
        self.assertIn("unittest", cmd)
        self.assertNotIn("sh", cmd)
    
    def test_command_with_and_operator(self):
        """Test command with && operator."""
        cmd = tdd_runner.build_test_cmd("npm install && npm test")
        self.assertEqual(cmd, ["sh", "-c", "npm install && npm test"])
    
    def test_command_with_or_operator(self):
        """Test command with || operator."""
        cmd = tdd_runner.build_test_cmd("command1 || command2")
        self.assertEqual(cmd, ["sh", "-c", "command1 || command2"])
    
    def test_command_with_pipe(self):
        """Test command with pipe operator."""
        cmd = tdd_runner.build_test_cmd("cat file.txt | grep pattern")
        self.assertEqual(cmd, ["sh", "-c", "cat file.txt | grep pattern"])
    
    def test_command_with_redirect(self):
        """Test command with redirect operators."""
        cmd = tdd_runner.build_test_cmd("echo test > output.txt")
        self.assertEqual(cmd, ["sh", "-c", "echo test > output.txt"])
        
        cmd = tdd_runner.build_test_cmd("sort < input.txt")
        self.assertEqual(cmd, ["sh", "-c", "sort < input.txt"])
    
    def test_command_with_semicolon(self):
        """Test command with semicolon."""
        cmd = tdd_runner.build_test_cmd("cd dir; make test")
        self.assertEqual(cmd, ["sh", "-c", "cd dir; make test"])
    
    def test_command_with_subshell(self):
        """Test command with $(command) or backticks."""
        cmd = tdd_runner.build_test_cmd("echo $(date)")
        self.assertEqual(cmd, ["sh", "-c", "echo $(date)"])
        
        cmd = tdd_runner.build_test_cmd("echo `date`")
        self.assertEqual(cmd, ["sh", "-c", "echo `date`"])
    
    def test_complex_monorepo_command(self):
        """Test complex multi-language test command."""
        cmd_str = "python3 -m unittest discover -s tests -v && corepack pnpm test"
        cmd = tdd_runner.build_test_cmd(cmd_str)
        self.assertEqual(cmd, ["sh", "-c", cmd_str])


class TestTestSupportFiles(unittest.TestCase):
    """Test test_support_files field in specs."""
    
    def test_validate_spec_with_support_files(self):
        """Test validation accepts test_support_files."""
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
                    "impl_files": ["foo.py"],
                    "test_support_files": ["vitest.config.ts", "fixtures/data.json"]
                }
            ],
            "out_of_scope": [],
            "risks": []
        }
        valid, error = take_agent.validate_impl_spec(spec)
        self.assertTrue(valid, f"Validation failed: {error}")
    
    def test_validate_spec_without_support_files(self):
        """Test validation works without test_support_files."""
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
        valid, error = take_agent.validate_impl_spec(spec)
        self.assertTrue(valid, f"Validation failed: {error}")
    
    def test_render_and_parse_roundtrip_with_support_files(self):
        """Test render -> parse roundtrip with test_support_files."""
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
                    "impl_files": ["foo.py"],
                    "test_support_files": ["vitest.config.ts", "pytest.ini"]
                }
            ],
            "out_of_scope": [],
            "risks": []
        }
        
        issue = {"number": 1, "title": "Test"}
        rendered = take_agent.render_spec_markdown(spec, issue)
        
        # Check rendered includes support files section
        self.assertIn("**Archivos de soporte de tests:**", rendered)
        self.assertIn("`vitest.config.ts`", rendered)
        self.assertIn("`pytest.ini`", rendered)
        
        # Parse back
        metadata, parsed_spec, progress = take_agent.parse_spec_markdown(rendered)
        
        # Verify test_support_files survived roundtrip
        self.assertIn("test_support_files", parsed_spec["tasks"][0])
        self.assertEqual(
            parsed_spec["tasks"][0]["test_support_files"],
            ["vitest.config.ts", "pytest.ini"]
        )


class TestLLMClientMaxTokensTimeout(unittest.TestCase):
    """Test LLMClient with max_tokens and timeout."""
    
    def test_llm_client_init_with_defaults(self):
        """Test LLMClient initialization with default params."""
        client = agent_core.LLMClient("https://api.example.com", "key", "model")
        self.assertEqual(client.max_tokens, 16000)
        self.assertEqual(client.timeout, 300)
    
    def test_llm_client_init_with_custom_values(self):
        """Test LLMClient initialization with custom params."""
        client = agent_core.LLMClient("https://api.example.com", "key", "model", 
                                      max_tokens=8000, timeout=120)
        self.assertEqual(client.max_tokens, 8000)
        self.assertEqual(client.timeout, 120)
    
    @patch('agent_core.request.urlopen')
    def test_chat_includes_max_tokens(self, mock_urlopen):
        """Test that chat() includes max_tokens in payload."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [{
                "message": {"role": "assistant", "content": "test"},
                "finish_reason": "stop"
            }]
        }).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        client = agent_core.LLMClient("https://api.example.com", "key", "model", 
                                      max_tokens=10000, timeout=200)
        
        messages = [{"role": "user", "content": "hello"}]
        result = client.chat(messages)
        
        # Verify urlopen was called
        self.assertEqual(mock_urlopen.call_count, 1)
        
        # Check the request payload included max_tokens
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        payload = json.loads(req.data.decode())
        self.assertEqual(payload["max_tokens"], 10000)
    
    @patch('agent_core.request.urlopen')
    def test_chat_returns_finish_reason(self, mock_urlopen):
        """Test that chat() returns finish_reason in message."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "choices": [{
                "message": {"role": "assistant", "content": "test"},
                "finish_reason": "length"
            }]
        }).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        client = agent_core.LLMClient("https://api.example.com", "key", "model")
        messages = [{"role": "user", "content": "hello"}]
        result = client.chat(messages)
        
        self.assertEqual(result["finish_reason"], "length")
    
    def test_get_llm_config_returns_all_params(self):
        """Test get_llm_config returns max_tokens and timeout."""
        with patch.dict(os.environ, {
            "BACKLOG_LLM_MAX_TOKENS": "20000",
            "BACKLOG_LLM_TIMEOUT": "600",
            "NOUS_API_KEY": "test_key"
        }):
            base_url, api_key, model, max_tokens, timeout = agent_core.get_llm_config()
            self.assertEqual(max_tokens, 20000)
            self.assertEqual(timeout, 600)


class TestSessionIssueTracking(unittest.TestCase):
    """Test session management with issue numbers."""
    
    def test_save_session_with_issue_num(self):
        """Test save_session stores issue number in metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            messages = [{"role": "user", "content": "test"}]
            json_path, md_path = agent_core.save_session(tmpdir, messages, "test_session", issue_num=42)
            
            # Load and verify
            with open(json_path, "r") as f:
                data = json.load(f)
            
            self.assertEqual(data["issue"], 42)
            self.assertEqual(data["messages"], messages)
    
    def test_save_session_without_issue_num(self):
        """Test save_session works without issue number (backward compat)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            messages = [{"role": "user", "content": "test"}]
            json_path, md_path = agent_core.save_session(tmpdir, messages, "test_session")
            
            # Load and verify
            with open(json_path, "r") as f:
                data = json.load(f)
            
            self.assertNotIn("issue", data)
            self.assertEqual(data["messages"], messages)
    
    def test_find_session_for_issue(self):
        """Test find_session_for_issue finds correct session."""
        import time
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create sessions for different issues (with small delays for different mtimes)
            agent_core.save_session(tmpdir, [{"role": "user", "content": "issue 10"}], "session1", issue_num=10)
            time.sleep(0.01)
            agent_core.save_session(tmpdir, [{"role": "user", "content": "issue 20"}], "session2", issue_num=20)
            time.sleep(0.01)
            agent_core.save_session(tmpdir, [{"role": "user", "content": "issue 10 again"}], "session3", issue_num=10)
            
            # Find session for issue 10 (should return most recent)
            found = agent_core.find_session_for_issue(tmpdir, 10)
            self.assertIsNotNone(found)
            self.assertIn("session3", found)
            
            # Find session for issue 20
            found = agent_core.find_session_for_issue(tmpdir, 20)
            self.assertIsNotNone(found)
            self.assertIn("session2", found)
            
            # Find session for non-existent issue
            found = agent_core.find_session_for_issue(tmpdir, 999)
            self.assertIsNone(found)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""
Unit tests for issue_agent module
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Import issue_agent module
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "scripts"))
import issue_agent


class TestParseSpec(unittest.TestCase):
    """Test /SPEC detection and parsing."""
    
    def test_parse_spec_with_marker(self):
        """Test parsing spec with /SPEC marker."""
        text = '''Aquí está la especificación final:

/SPEC
```json
{
  "issues": [
    {
      "title": "Test issue",
      "type": "feat",
      "body": "Test body",
      "areas": ["web"],
      "phase": 1
    }
  ]
}
```
'''
        result = issue_agent.parse_final_spec(text)
        self.assertIsNotNone(result)
        self.assertEqual(len(result["issues"]), 1)
        self.assertEqual(result["issues"][0]["title"], "Test issue")
    
    def test_parse_spec_without_marker(self):
        """Test that spec without /SPEC marker is rejected."""
        text = '''```json
{"issues": [{"title": "Test", "type": "feat", "body": "Body"}]}
```'''
        result = issue_agent.parse_final_spec(text)
        self.assertIsNone(result)
    
    def test_parse_spec_malformed_json(self):
        """Test that malformed JSON returns None."""
        text = '''/SPEC
```json
{invalid json}
```'''
        result = issue_agent.parse_final_spec(text)
        self.assertIsNone(result)


class TestToolSandboxRobustness(unittest.TestCase):
    """Test tool sandbox error handling."""
    
    def setUp(self):
        self.sandbox = issue_agent.ToolSandbox(str(repo_root))
    
    def test_path_traversal_returns_error(self):
        """Test that path traversal returns error string instead of raising."""
        result = self.sandbox.execute_tool("read_file", {"path": "../../etc/passwd"})
        self.assertIn("Error", result)
        self.assertIn("outside repo", result.lower())
    
    def test_unknown_tool_returns_error(self):
        """Test that unknown tool returns error string."""
        result = self.sandbox.execute_tool("unknown_tool", {})
        self.assertIn("Error", result)
        self.assertIn("unknown tool", result.lower())
    
    def test_missing_argument_returns_error(self):
        """Test that missing required argument returns error."""
        result = self.sandbox.execute_tool("read_file", {})
        self.assertIn("Error", result)
        self.assertIn("missing", result.lower())
    
    def test_malformed_path_returns_error(self):
        """Test that invalid path returns error instead of raising."""
        result = self.sandbox.read_file("/absolute/path/outside")
        self.assertIn("Error", result)


class TestLLMConfigExportHandling(unittest.TestCase):
    """Test get_llm_config handles export lines."""
    
    def test_parse_export_line(self):
        """Test that export lines are parsed correctly."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("export NOUS_API_KEY=test-key-123\n")
            f.write("OTHER_VAR=value\n")
            temp_path = f.name
        
        try:
            # Mock Path.home() to return temp dir
            import issue_agent
            original_home = Path.home
            
            def mock_home():
                return Path(temp_path).parent
            
            # Create .config dir
            config_dir = Path(temp_path).parent / ".config"
            config_dir.mkdir(exist_ok=True)
            keys_file = config_dir / "model-keys.env"
            
            with open(keys_file, 'w') as f:
                f.write("export NOUS_API_KEY=test-key-export\n")
            
            # Temporarily unset env var
            import os
            old_key = os.environ.get("NOUS_API_KEY")
            if "NOUS_API_KEY" in os.environ:
                del os.environ["NOUS_API_KEY"]
            
            try:
                Path.home = mock_home
                base_url, api_key, model, max_tokens, timeout = issue_agent.get_llm_config()
                self.assertEqual(api_key, "test-key-export")
            finally:
                Path.home = original_home
                if old_key:
                    os.environ["NOUS_API_KEY"] = old_key
                keys_file.unlink(missing_ok=True)
                config_dir.rmdir()
        finally:
            Path(temp_path).unlink()


class TestSessionPersistence(unittest.TestCase):
    """Test session save/load functionality."""
    
    def test_save_and_load_session(self):
        """Test that session can be saved and loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            messages = [
                {"role": "system", "content": "System prompt"},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"}
            ]
            
            json_path, md_path = issue_agent.save_transcript(tmpdir, messages, "test_session")
            
            # Check files exist
            self.assertTrue(Path(json_path).exists())
            self.assertTrue(Path(md_path).exists())
            
            # Load and verify
            loaded_messages, session_id = issue_agent.load_session(json_path)
            self.assertEqual(len(loaded_messages), 3)
            self.assertEqual(loaded_messages[0]["role"], "system")
            self.assertEqual(loaded_messages[2]["content"], "Hi there")
            self.assertEqual(session_id, "test_session")
    
    def test_get_last_session(self):
        """Test getting the most recent session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple sessions
            sessions_dir = Path(tmpdir) / ".backlog" / "sessions"
            sessions_dir.mkdir(parents=True)
            
            import time
            
            # Session 1 (older)
            s1 = sessions_dir / "20260101_120000.json"
            s1.write_text(json.dumps({"messages": [], "timestamp": "2026-01-01T12:00:00"}))
            time.sleep(0.01)
            
            # Session 2 (newer)
            s2 = sessions_dir / "20260101_130000.json"
            s2.write_text(json.dumps({"messages": [], "timestamp": "2026-01-01T13:00:00"}))
            
            last = issue_agent.get_last_session(tmpdir)
            self.assertIsNotNone(last)
            self.assertIn("20260101_130000.json", last)
    
    def test_get_last_session_empty(self):
        """Test get_last_session returns None when no sessions exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = issue_agent.get_last_session(tmpdir)
            self.assertIsNone(result)


class TestInterviewResume(unittest.TestCase):
    """Test interview resume functionality."""
    
    def test_resume_continues_messages(self):
        """Test that resume continues from existing messages."""
        mock_client = MagicMock()
        
        call_count = [0]
        
        def mock_chat(messages, tools=None):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call after /listo: ask for clarification
                return {
                    "role": "assistant",
                    "content": "OK, tell me more about X"
                }
            else:
                # Second call: return spec
                return {
                    "role": "assistant",
                    "content": '''/SPEC
```json
{
  "issues": [
    {
      "title": "Resumed issue",
      "type": "feat",
      "body": "## Context\\n\\nResumed",
      "areas": [],
      "phase": null
    }
  ]
}
```
'''
                }
        
        mock_client.chat = mock_chat
        
        existing_messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Initial idea"},
            {"role": "assistant", "content": "Tell me more..."}
        ]
        
        inputs = ["/listo", "More details"]
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
        
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = issue_agent.ToolSandbox(tmpdir)
            
            spec, messages, session_id = issue_agent.run_interview(
                mock_client,
                sandbox,
                tmpdir,
                "",
                existing_messages=existing_messages,
                session_id="test_resume",
                input_fn=mock_input,
                print_fn=mock_print
            )
            
            self.assertIsNotNone(spec)
            self.assertEqual(spec["issues"][0]["title"], "Resumed issue")
            # Messages should include the existing ones plus new ones
            # existing: 3, + user "/listo", + assistant, + user "more", + assistant = 7
            self.assertGreaterEqual(len(messages), 6)


class TestBoundedToolLoop(unittest.TestCase):
    """Test bounded tool-call loop."""
    
    def test_tool_loop_bounded(self):
        """Test that excessive consecutive tool calls are bounded."""
        # Fake client that always returns tool calls
        call_count = [0]
        
        def mock_chat(messages, tools=None):
            call_count[0] += 1
            
            # First few calls: return tool calls
            if call_count[0] <= 15:
                return {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": f"call_{call_count[0]}",
                            "type": "function",
                            "function": {
                                "name": "read_file",
                                "arguments": '{"path": "README.md"}'
                            }
                        }
                    ]
                }
            else:
                # After the intervention message, return text
                return {
                    "role": "assistant",
                    "content": "OK, continuando con preguntas."
                }
        
        mock_client = MagicMock()
        mock_client.chat = mock_chat
        
        # Use existing_messages to avoid load_prompt
        existing_messages = [
            {"role": "system", "content": "You are an interviewer."},
            {"role": "user", "content": "Start interview"}
        ]
        
        outputs = []
        def mock_print(text):
            outputs.append(text)
        
        def mock_input(prompt):
            # After the loop is bounded, user cancels
            return "/cancelar"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = issue_agent.ToolSandbox(tmpdir)
            
            # Create a dummy README.md so tool calls succeed
            readme = Path(tmpdir) / "README.md"
            readme.write_text("# Test repo")
            
            spec, messages, session_id = issue_agent.run_interview(
                mock_client,
                sandbox,
                tmpdir,
                "",
                existing_messages=existing_messages,
                session_id="test_bounded",
                input_fn=mock_input,
                print_fn=mock_print
            )
            
            # Verify that the loop injected the "stop using tools" message
            intervention_messages = [
                m for m in messages 
                if m.get("role") == "user" and "herramientas" in m.get("content", "").lower()
            ]
            self.assertGreater(len(intervention_messages), 0, 
                             "Should inject a message to stop using tools")
            
            # Verify chat was called enough times to hit the limit
            # Max is 8, so we should see at least 9 tool-call responses before intervention
            self.assertGreaterEqual(call_count[0], 9, 
                                  "Should call chat multiple times before limiting")


class TestSpecValidationAutoFix(unittest.TestCase):
    """Test spec validation and auto-fix limit."""
    
    def test_invalid_spec_fix_limit(self):
        """Test that invalid spec auto-fix is limited to 2 attempts."""
        call_count = [0]
        
        def mock_chat(messages, tools=None):
            call_count[0] += 1
            
            # Always return invalid spec (missing required field)
            return {
                "role": "assistant",
                "content": '''/SPEC
```json
{
  "issues": [
    {
      "type": "feat",
      "body": "Test body"
    }
  ]
}
```
'''
            }
        
        mock_client = MagicMock()
        mock_client.chat = mock_chat
        
        existing_messages = [
            {"role": "system", "content": "You are an interviewer."},
            {"role": "user", "content": "/listo"}
        ]
        
        outputs = []
        def mock_print(text):
            outputs.append(text)
        
        input_calls = [0]
        def mock_input(prompt):
            input_calls[0] += 1
            # After the fix limit is reached, user is asked for input
            return "/cancelar"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox = issue_agent.ToolSandbox(tmpdir)
            
            spec, messages, session_id = issue_agent.run_interview(
                mock_client,
                sandbox,
                tmpdir,
                "",
                existing_messages=existing_messages,
                session_id="test_fix_limit",
                input_fn=mock_input,
                print_fn=mock_print
            )
            
            # Spec should be None (interview cancelled)
            self.assertIsNone(spec)
            
            # Should have made exactly 2 auto-fix requests
            auto_fix_messages = [
                m for m in messages
                if m.get("role") == "user" and "error" in m.get("content", "").lower()
            ]
            self.assertEqual(len(auto_fix_messages), 2, 
                           "Should make exactly 2 auto-fix requests")
            
            # After 2 failed fixes, error should be shown to user (in outputs)
            error_outputs = [
                o for o in outputs
                if "inválida" in o.lower() and "intentos" in o.lower()
            ]
            self.assertGreater(len(error_outputs), 0,
                             "Should print error message after fix limit")
            
            # Input function should be called (to continue interview)
            self.assertGreater(input_calls[0], 0,
                             "Should call input_fn after fix limit reached")


class TestFrontmatterParsing(unittest.TestCase):
    """Test frontmatter parsing for issue edit."""
    
    def test_parse_issue_frontmatter(self):
        """Test parsing issue from frontmatter format."""
        import backlog
        
        content = """---
title: Test Issue
type: feat
areas: web, api
phase: 1
---
## Context

This is the body."""
        
        result = backlog.parse_issue_frontmatter(content)
        self.assertEqual(result["title"], "Test Issue")
        self.assertEqual(result["type"], "feat")
        self.assertEqual(result["areas"], ["web", "api"])
        self.assertEqual(result["phase"], 1)
        self.assertIn("## Context", result["body"])
    
    def test_format_and_parse_roundtrip(self):
        """Test that format -> parse is a round trip."""
        import backlog
        
        original = {
            "title": "Round Trip Test",
            "type": "fix",
            "areas": ["agents"],
            "phase": 2,
            "body": "## Test\n\nContent here"
        }
        
        formatted = backlog.format_issue_frontmatter(original)
        parsed = backlog.parse_issue_frontmatter(formatted)
        
        self.assertEqual(parsed["title"], original["title"])
        self.assertEqual(parsed["type"], original["type"])
        self.assertEqual(parsed["areas"], original["areas"])
        self.assertEqual(parsed["phase"], original["phase"])
        self.assertEqual(parsed["body"], original["body"])
    
    def test_parse_no_phase(self):
        """Test parsing issue with no phase."""
        import backlog
        
        content = """---
title: No Phase
type: chore
areas:
phase: ninguna
---
Body"""
        
        result = backlog.parse_issue_frontmatter(content)
        self.assertIsNone(result["phase"])
        self.assertEqual(result["areas"], [])


if __name__ == "__main__":
    unittest.main()

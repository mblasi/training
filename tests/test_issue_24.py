#!/usr/bin/env python3
"""
Tests for issue #24: repair tool_calls/tool_result pairing when hitting cap.
"""
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add scripts dir to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "scripts"))

import agent_core


class TestRepairToolPairs(unittest.TestCase):
    """Test repair_tool_pairs function."""
    
    def test_insert_missing_tool_results(self):
        """Test that missing tool results are inserted after tool_calls."""
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "hello"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "call_a", "function": {"name": "read_file", "arguments": "{}"}},
                    {"id": "call_b", "function": {"name": "search", "arguments": "{}"}}
                ]
            },
            {"role": "user", "content": "Has usado muchas herramientas."}
        ]
        
        # Make a copy to verify original is not mutated
        original = copy.deepcopy(messages)
        
        result = agent_core.repair_tool_pairs(messages)
        
        # Original should not be mutated
        self.assertEqual(messages, original)
        
        # Result should have tool messages inserted
        self.assertEqual(len(result), 6)
        self.assertEqual(result[0]["role"], "system")
        self.assertEqual(result[1]["role"], "user")
        self.assertEqual(result[2]["role"], "assistant")
        
        # Check tool results are inserted in order
        self.assertEqual(result[3]["role"], "tool")
        self.assertEqual(result[3]["tool_call_id"], "call_a")
        self.assertIn("límite", result[3]["content"].lower())
        
        self.assertEqual(result[4]["role"], "tool")
        self.assertEqual(result[4]["tool_call_id"], "call_b")
        self.assertIn("límite", result[4]["content"].lower())
        
        self.assertEqual(result[5]["role"], "user")
        self.assertEqual(result[5]["content"], "Has usado muchas herramientas.")
    
    def test_partial_tool_results_filled(self):
        """Test that partial tool results are completed."""
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "hello"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "call_a", "function": {"name": "read_file", "arguments": "{}"}},
                    {"id": "call_b", "function": {"name": "search", "arguments": "{}"}}
                ]
            },
            {"role": "tool", "tool_call_id": "call_a", "content": "file content"},
            {"role": "user", "content": "continue"}
        ]
        
        result = agent_core.repair_tool_pairs(messages)
        
        # Should insert only call_b
        self.assertEqual(len(result), 6)
        self.assertEqual(result[3]["role"], "tool")
        self.assertEqual(result[3]["tool_call_id"], "call_a")
        self.assertEqual(result[3]["content"], "file content")
        
        self.assertEqual(result[4]["role"], "tool")
        self.assertEqual(result[4]["tool_call_id"], "call_b")
        self.assertIn("límite", result[4]["content"].lower())
        
        self.assertEqual(result[5]["role"], "user")
    
    def test_valid_history_unchanged(self):
        """Test that valid histories are returned unchanged."""
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "hello"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "call_a", "function": {"name": "read_file", "arguments": "{}"}}
                ]
            },
            {"role": "tool", "tool_call_id": "call_a", "content": "result"},
            {"role": "assistant", "content": "response"},
            {"role": "user", "content": "next"}
        ]
        
        result = agent_core.repair_tool_pairs(messages)
        
        # Should be identical
        self.assertEqual(result, messages)
    
    def test_idempotency(self):
        """Test that repair(repair(x)) == repair(x)."""
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "hello"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "call_a", "function": {"name": "read_file", "arguments": "{}"}},
                    {"id": "call_b", "function": {"name": "search", "arguments": "{}"}}
                ]
            },
            {"role": "user", "content": "Has usado muchas herramientas."}
        ]
        
        first_repair = agent_core.repair_tool_pairs(messages)
        second_repair = agent_core.repair_tool_pairs(first_repair)
        
        self.assertEqual(first_repair, second_repair)


class TestToolCapIntegration(unittest.TestCase):
    """Test run_generic_interview with tool call cap."""
    
    def test_cap_triggers_synthetic_results(self):
        """Test that hitting cap inserts synthetic tool results."""
        # Track all messages sent to chat()
        chat_calls = []
        call_count = [0]
        
        def fake_chat(messages, tools=None):
            # Deep copy to capture state at call time
            chat_calls.append(copy.deepcopy(messages))
            call_count[0] += 1
            
            # First 4 calls: return tool_calls
            if call_count[0] <= 4:
                return {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"id": f"call_{call_count[0]}", "function": {"name": "read_file", "arguments": '{"path": "test.py"}'}}
                    ],
                    "finish_reason": "tool_calls"
                }
            else:
                # After cap, return text
                return {
                    "role": "assistant",
                    "content": "continuing without tools",
                    "finish_reason": "stop"
                }
        
        client = MagicMock()
        client.chat = fake_chat
        
        # Mock sandbox execute_tool to track calls
        execute_calls = []
        original_execute = agent_core.ToolSandbox.execute_tool
        
        def tracked_execute(self, name, args):
            execute_calls.append((name, args))
            return "mocked result"
        
        with patch.object(agent_core.ToolSandbox, 'execute_tool', tracked_execute):
            with tempfile.TemporaryDirectory() as tmpdir:
                sandbox = agent_core.ToolSandbox(tmpdir)
                
                # Set cap to 3
                with patch.dict(os.environ, {"BACKLOG_LLM_MAX_TOOL_ROUNDS": "3"}):
                    outputs = []
                    inputs_queue = ["/cancelar"]
                    
                    spec, messages, sid = agent_core.run_generic_interview(
                        client=client,
                        sandbox=sandbox,
                        repo_root=tmpdir,
                        system_prompt="system",
                        initial_user_message="start",
                        spec_validator=lambda s: (True, ""),
                        input_fn=lambda p: inputs_queue.pop(0) if inputs_queue else "/cancelar",
                        print_fn=lambda m: outputs.append(m)
                    )
        
        # Verify invariant on ALL chat calls
        for i, call_messages in enumerate(chat_calls):
            self._assert_tool_pairs_valid(call_messages, f"call #{i+1}")
        
        # Check that warning appeared
        output_text = " ".join(outputs)
        self.assertIn("límite", output_text.lower())
        
        # Check that execute_tool was called for first 3 rounds but NOT 4th
        self.assertEqual(len(execute_calls), 3)
        
        # Check that synthetic tool result is present for 4th round
        # Find the 4th assistant message with tool_calls in final messages
        fourth_assistant = None
        for i, msg in enumerate(messages):
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                fourth_assistant = msg
        
        if fourth_assistant:
            # Next message should be synthetic tool result
            idx = messages.index(fourth_assistant)
            next_msg = messages[idx + 1]
            self.assertEqual(next_msg["role"], "tool")
            self.assertIn("límite", next_msg["content"].lower())
    
    def _assert_tool_pairs_valid(self, messages, context=""):
        """Helper to assert tool_calls/tool_result invariant."""
        for i, msg in enumerate(messages):
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                tool_call_ids = {tc["id"] for tc in msg["tool_calls"]}
                
                # Collect tool messages immediately following
                j = i + 1
                found_ids = set()
                while j < len(messages) and messages[j].get("role") == "tool":
                    found_ids.add(messages[j]["tool_call_id"])
                    j += 1
                
                # All tool_call_ids must have corresponding tool results
                missing = tool_call_ids - found_ids
                self.assertEqual(
                    missing, set(),
                    f"{context}: assistant at index {i} has tool_calls {tool_call_ids} but missing tool results for {missing}"
                )


class TestToolCapConfig(unittest.TestCase):
    """Test configurable tool cap via environment."""
    
    def test_default_cap_is_20(self):
        """Test that default cap is 20 rounds."""
        call_count = [0]
        
        def fake_chat(messages, tools=None):
            call_count[0] += 1
            if call_count[0] <= 21:
                return {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"id": f"call_{call_count[0]}", "function": {"name": "read_file", "arguments": '{"path": "test.py"}'}}
                    ],
                    "finish_reason": "tool_calls"
                }
            else:
                return {
                    "role": "assistant",
                    "content": "done",
                    "finish_reason": "stop"
                }
        
        client = MagicMock()
        client.chat = fake_chat
        
        execute_count = [0]
        
        def counted_execute(self, name, args):
            execute_count[0] += 1
            return "result"
        
        with patch.object(agent_core.ToolSandbox, 'execute_tool', counted_execute):
            with tempfile.TemporaryDirectory() as tmpdir:
                sandbox = agent_core.ToolSandbox(tmpdir)
                
                # No env var set
                with patch.dict(os.environ, {}, clear=False):
                    if "BACKLOG_LLM_MAX_TOOL_ROUNDS" in os.environ:
                        del os.environ["BACKLOG_LLM_MAX_TOOL_ROUNDS"]
                    
                    outputs = []
                    
                    spec, messages, sid = agent_core.run_generic_interview(
                        client=client,
                        sandbox=sandbox,
                        repo_root=tmpdir,
                        system_prompt="system",
                        initial_user_message="start",
                        spec_validator=lambda s: (True, ""),
                        input_fn=lambda p: "/cancelar",
                        print_fn=lambda m: outputs.append(m)
                    )
                    
                    # Should execute 20 times, then hit cap on 21st
                    self.assertEqual(execute_count[0], 20)
                    
                    output_text = " ".join(outputs)
                    self.assertIn("límite", output_text.lower())
    
    def test_custom_cap_from_env(self):
        """Test that BACKLOG_LLM_MAX_TOOL_ROUNDS is respected."""
        call_count = [0]
        warning_seen = [False]
        
        def fake_chat(messages, tools=None):
            # Check if warning was issued in previous messages
            for msg in messages:
                if msg.get("role") == "user" and "muchas herramientas" in msg.get("content", "").lower():
                    warning_seen[0] = True
            
            call_count[0] += 1
            
            # Return tool_calls for first 4 calls (rounds 1-3 execute, round 4 hits cap)
            # After warning is seen, stop returning tool_calls
            if call_count[0] <= 4 and not warning_seen[0]:
                return {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"id": f"call_{call_count[0]}", "function": {"name": "read_file", "arguments": '{"path": "test.py"}'}}
                    ],
                    "finish_reason": "tool_calls"
                }
            else:
                return {
                    "role": "assistant",
                    "content": "done without tools",
                    "finish_reason": "stop"
                }
        
        client = MagicMock()
        client.chat = fake_chat
        
        execute_count = [0]
        
        def counted_execute(self, name, args):
            execute_count[0] += 1
            return "result"
        
        with patch.object(agent_core.ToolSandbox, 'execute_tool', counted_execute):
            with tempfile.TemporaryDirectory() as tmpdir:
                sandbox = agent_core.ToolSandbox(tmpdir)
                
                # Set cap to 3
                with patch.dict(os.environ, {"BACKLOG_LLM_MAX_TOOL_ROUNDS": "3"}):
                    outputs = []
                    
                    spec, messages, sid = agent_core.run_generic_interview(
                        client=client,
                        sandbox=sandbox,
                        repo_root=tmpdir,
                        system_prompt="system",
                        initial_user_message="start",
                        spec_validator=lambda s: (False, "not done"),
                        input_fn=lambda p: "/cancelar",
                        print_fn=lambda m: outputs.append(m)
                    )
                    
                    # Should execute 3 times (rounds 1-3), then hit cap on round 4
                    self.assertEqual(execute_count[0], 3)
                    
                    output_text = " ".join(outputs)
                    self.assertIn("límite", output_text.lower())
    
    def test_invalid_cap_uses_default(self):
        """Test that invalid cap value falls back to default 20."""
        call_count = [0]
        
        def fake_chat(messages, tools=None):
            call_count[0] += 1
            if call_count[0] <= 21:
                return {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"id": f"call_{call_count[0]}", "function": {"name": "read_file", "arguments": '{"path": "test.py"}'}}
                    ],
                    "finish_reason": "tool_calls"
                }
            else:
                return {
                    "role": "assistant",
                    "content": "done",
                    "finish_reason": "stop"
                }
        
        client = MagicMock()
        client.chat = fake_chat
        
        execute_count = [0]
        
        def counted_execute(self, name, args):
            execute_count[0] += 1
            return "result"
        
        with patch.object(agent_core.ToolSandbox, 'execute_tool', counted_execute):
            with tempfile.TemporaryDirectory() as tmpdir:
                sandbox = agent_core.ToolSandbox(tmpdir)
                
                # Set invalid value
                with patch.dict(os.environ, {"BACKLOG_LLM_MAX_TOOL_ROUNDS": "abc"}):
                    outputs = []
                    
                    spec, messages, sid = agent_core.run_generic_interview(
                        client=client,
                        sandbox=sandbox,
                        repo_root=tmpdir,
                        system_prompt="system",
                        initial_user_message="start",
                        spec_validator=lambda s: (True, ""),
                        input_fn=lambda p: "/cancelar",
                        print_fn=lambda m: outputs.append(m)
                    )
                    
                    # Should use default 20
                    self.assertEqual(execute_count[0], 20)


class TestResumeCorruptedSession(unittest.TestCase):
    """Test resuming from corrupted session with missing tool results."""
    
    def test_resume_repairs_corrupted_history(self):
        """Test that resuming repairs corrupted session on first LLM call."""
        # Build corrupted session
        with tempfile.TemporaryDirectory() as tmpdir:
            sessions_dir = Path(tmpdir) / ".backlog" / "sessions"
            sessions_dir.mkdir(parents=True, exist_ok=True)
            
            corrupted_messages = [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "hello"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"id": "call_1", "function": {"name": "read_file", "arguments": '{"path": "test.py"}'}},
                        {"id": "call_2", "function": {"name": "search", "arguments": '{"pattern": "foo"}'}}
                    ]
                },
                {"role": "tool", "tool_call_id": "call_1", "content": "result 1"},
                {"role": "tool", "tool_call_id": "call_2", "content": "result 2"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"id": "call_X", "function": {"name": "read_file", "arguments": '{"path": "other.py"}'}},
                        {"id": "call_Y", "function": {"name": "list_issues", "arguments": '{}'}}
                    ]
                },
                {"role": "user", "content": "Has usado muchas herramientas."}
            ]
            
            session_file = sessions_dir / "corrupted.json"
            with open(session_file, "w") as f:
                json.dump({"messages": corrupted_messages, "timestamp": "2026-01-01T00:00:00"}, f)
            
            # Load and resume
            existing, session_id = agent_core.load_session(str(session_file))
            
            # Track chat calls
            chat_calls = []
            
            def fake_chat(messages, tools=None):
                chat_calls.append(copy.deepcopy(messages))
                return {
                    "role": "assistant",
                    "content": "continuing",
                    "finish_reason": "stop"
                }
            
            client = MagicMock()
            client.chat = fake_chat
            
            sandbox = agent_core.ToolSandbox(tmpdir)
            
            outputs = []
            spec, messages, sid = agent_core.run_generic_interview(
                client=client,
                sandbox=sandbox,
                repo_root=tmpdir,
                system_prompt="system",
                initial_user_message="start",
                spec_validator=lambda s: (True, ""),
                existing_messages=existing,
                session_id=session_id,
                input_fn=lambda p: "/cancelar",
                print_fn=lambda m: outputs.append(m)
            )
            
            # First chat call should have repaired messages
            first_call = chat_calls[0]
            
            # Find the assistant message with call_X and call_Y
            found_x = False
            found_y = False
            for i, msg in enumerate(first_call):
                if msg.get("role") == "assistant" and msg.get("tool_calls"):
                    ids = {tc["id"] for tc in msg["tool_calls"]}
                    if "call_X" in ids or "call_Y" in ids:
                        # Next two messages should be tool results
                        self.assertGreater(len(first_call), i + 2)
                        self.assertEqual(first_call[i + 1]["role"], "tool")
                        self.assertEqual(first_call[i + 2]["role"], "tool")
                        
                        result_ids = {first_call[i + 1]["tool_call_id"], first_call[i + 2]["tool_call_id"]}
                        self.assertEqual(result_ids, {"call_X", "call_Y"})
                        found_x = True
                        found_y = True
                        break
            
            self.assertTrue(found_x and found_y, "Repaired tool results for call_X and call_Y not found")


if __name__ == "__main__":
    unittest.main()

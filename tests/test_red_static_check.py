#!/usr/bin/env python3
"""
Tests for RED static checking (lint/typecheck validation).
"""
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestCheckTestFilesStatic(unittest.TestCase):
    """Unit tests for check_test_files_static function."""
    
    def setUp(self):
        """Create a temporary git repo for testing."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_static_check_")
        self.repo = Path(self.temp_dir)
        
        # Initialize git repo
        self._run(["git", "init", "-q"])
        self._run(["git", "config", "user.email", "test@test.com"])
        self._run(["git", "config", "user.name", "Test User"])
        
        # Create workspace structure
        (self.repo / "apps" / "api").mkdir(parents=True)
        (self.repo / "apps" / "api" / "test").mkdir()
        
        # Initial commit
        (self.repo / "README.md").write_text("# Test\n")
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-qm", "initial"])
    
    def tearDown(self):
        """Clean up temporary repo."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _run(self, cmd: list[str], cwd: str = None, timeout: int = None) -> subprocess.CompletedProcess:
        """Run a command in the temp repo."""
        return subprocess.run(
            cmd,
            cwd=cwd or self.repo,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )
    
    def test_no_ts_files_returns_none(self):
        """Test check_test_files_static with no TS files returns None (OK)."""
        from scripts.tdd_runner import check_test_files_static
        
        # Only Python files
        result = check_test_files_static(str(self.repo), ["tests/test_foo.py"], self._run)
        self.assertIsNone(result)
    
    def test_workspace_resolution(self):
        """Test that files are grouped by workspace (nearest package.json)."""
        from scripts.tdd_runner import check_test_files_static
        
        # Create package.json in workspace
        (self.repo / "apps" / "api" / "package.json").write_text('{"name": "api"}\n')
        
        # Create test file in workspace
        test_file = "apps/api/test/x.test.ts"
        (self.repo / test_file).write_text("const x = 1;\n")
        
        # Mock run_cmd that expects eslint to be called with correct workspace
        def mock_run_cmd(cmd: list[str], cwd: str = None, timeout: int = None) -> subprocess.CompletedProcess:
            # Verify eslint is called with workspace directory
            if "eslint" in cmd:
                # Extract --dir argument
                dir_idx = cmd.index("--dir") if "--dir" in cmd else -1
                if dir_idx >= 0:
                    workspace_dir = cmd[dir_idx + 1]
                    # Should be apps/api
                    assert "apps/api" in workspace_dir, f"Expected workspace apps/api, got {workspace_dir}"
                
                # Return success
                return subprocess.CompletedProcess(cmd, 0, "", "")
            
            return subprocess.CompletedProcess(cmd, 0, "", "")
        
        result = check_test_files_static(str(self.repo), [test_file], mock_run_cmd)
        # Should be None (OK) since mock returns success
        self.assertIsNone(result)
    
    def test_eslint_failure_returns_feedback(self):
        """Test that eslint failure returns feedback with tool output."""
        from scripts.tdd_runner import check_test_files_static
        
        # Create package.json with eslint config
        (self.repo / "package.json").write_text('{"name": "test"}\n')
        (self.repo / ".eslintrc.json").write_text('{"rules": {}}\n')
        
        test_file = "test/x.test.ts"
        (self.repo / "test").mkdir(exist_ok=True)
        (self.repo / test_file).write_text("const x = 1;\n")
        
        # Mock run_cmd that returns eslint failure
        def mock_run_cmd(cmd: list[str], cwd: str = None, timeout: int = None) -> subprocess.CompletedProcess:
            if "eslint" in cmd:
                return subprocess.CompletedProcess(
                    cmd, 1,
                    "test/x.test.ts:1:7: 'x' is assigned a value but never used.\n",
                    ""
                )
            return subprocess.CompletedProcess(cmd, 0, "", "")
        
        result = check_test_files_static(str(self.repo), [test_file], mock_run_cmd)
        
        # Should return feedback with eslint output
        self.assertIsNotNone(result)
        self.assertIn("test/x.test.ts", result)
        self.assertIn("never used", result)
    
    def test_tsc_ts2307_is_accepted(self):
        """Test that TS2307 (missing module) in changed test file is accepted."""
        from scripts.tdd_runner import check_test_files_static
        
        # Create package.json and tsconfig
        (self.repo / "package.json").write_text('{"name": "test"}\n')
        (self.repo / "tsconfig.json").write_text('{"compilerOptions": {}}\n')
        
        test_file = "test/x.test.ts"
        (self.repo / "test").mkdir(exist_ok=True)
        (self.repo / test_file).write_text("import { foo } from './missing';\n")
        
        # Mock run_cmd that returns TS2307 error in test file
        def mock_run_cmd(cmd: list[str], cwd: str = None, timeout: int = None) -> subprocess.CompletedProcess:
            if "tsc" in cmd:
                return subprocess.CompletedProcess(
                    cmd, 2,
                    f"{test_file}(1,23): error TS2307: Cannot find module './missing'.\n",
                    ""
                )
            if "eslint" in cmd:
                return subprocess.CompletedProcess(cmd, 0, "", "")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        
        result = check_test_files_static(str(self.repo), [test_file], mock_run_cmd)
        
        # Should be None (accepted) since TS2307 is allowed
        self.assertIsNone(result)
    
    def test_tsc_ts6133_is_rejected(self):
        """Test that TS6133 (unused parameter) in changed test file is rejected."""
        from scripts.tdd_runner import check_test_files_static
        
        # Create package.json and tsconfig
        (self.repo / "package.json").write_text('{"name": "test"}\n')
        (self.repo / "tsconfig.json").write_text('{"compilerOptions": {}}\n')
        
        test_file = "test/x.test.ts"
        (self.repo / "test").mkdir(exist_ok=True)
        (self.repo / test_file).write_text("function f(unused: number) {}\n")
        
        # Mock run_cmd that returns TS6133 error in test file
        def mock_run_cmd(cmd: list[str], cwd: str = None, timeout: int = None) -> subprocess.CompletedProcess:
            if "tsc" in cmd:
                return subprocess.CompletedProcess(
                    cmd, 2,
                    f"{test_file}(1,12): error TS6133: 'unused' is declared but never used.\n",
                    ""
                )
            if "eslint" in cmd:
                return subprocess.CompletedProcess(cmd, 0, "", "")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        
        result = check_test_files_static(str(self.repo), [test_file], mock_run_cmd)
        
        # Should return feedback with TS6133 error
        self.assertIsNotNone(result)
        self.assertIn("TS6133", result)
        self.assertIn(test_file, result)
    
    def test_tsc_error_in_non_test_file_ignored(self):
        """Test that tsc errors in non-test files are ignored."""
        from scripts.tdd_runner import check_test_files_static
        
        # Create package.json and tsconfig
        (self.repo / "package.json").write_text('{"name": "test"}\n')
        (self.repo / "tsconfig.json").write_text('{"compilerOptions": {}}\n')
        
        test_file = "test/x.test.ts"
        (self.repo / "test").mkdir(exist_ok=True)
        (self.repo / test_file).write_text("export const x = 1;\n")
        
        # Mock run_cmd that returns error in a different file
        def mock_run_cmd(cmd: list[str], cwd: str = None, timeout: int = None) -> subprocess.CompletedProcess:
            if "tsc" in cmd:
                # Error in src/foo.ts, not in test file
                return subprocess.CompletedProcess(
                    cmd, 2,
                    "src/foo.ts(5,10): error TS6133: 'bar' is declared but never used.\n",
                    ""
                )
            if "eslint" in cmd:
                return subprocess.CompletedProcess(cmd, 0, "", "")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        
        result = check_test_files_static(str(self.repo), [test_file], mock_run_cmd)
        
        # Should be None (OK) since error is not in changed test file
        self.assertIsNone(result)
    
    def test_python_syntax_error_rejected(self):
        """Test that Python syntax error in test file is rejected."""
        from scripts.tdd_runner import check_test_files_static
        
        test_file = "tests/test_foo.py"
        
        # Create actual file with syntax error
        (self.repo / "tests").mkdir(exist_ok=True)
        (self.repo / test_file).write_text("def foo(\n")  # Syntax error
        
        # Use real run_cmd since py_compile will run on actual file
        result = check_test_files_static(str(self.repo), [test_file], self._run)
        
        # Should return feedback about syntax error
        self.assertIsNotNone(result)
        self.assertIn("test_foo.py", result)
    
    def test_python_valid_file_accepted(self):
        """Test that valid Python test file is accepted."""
        from scripts.tdd_runner import check_test_files_static
        
        test_file = "tests/test_foo.py"
        
        # Create valid Python file
        (self.repo / "tests").mkdir(exist_ok=True)
        (self.repo / test_file).write_text("def test_foo():\n    assert True\n")
        
        result = check_test_files_static(str(self.repo), [test_file], self._run)
        
        # Should be None (OK)
        self.assertIsNone(result)
    
    def test_no_eslint_config_skips_check(self):
        """Test that missing eslint config skips eslint check."""
        from scripts.tdd_runner import check_test_files_static
        
        # Create package.json but NO eslint config
        (self.repo / "package.json").write_text('{"name": "test"}\n')
        
        test_file = "test/x.test.ts"
        (self.repo / "test").mkdir(exist_ok=True)
        (self.repo / test_file).write_text("const x = 1;\n")
        
        # Mock run_cmd that would fail if eslint were called
        def mock_run_cmd(cmd: list[str], cwd: str = None, timeout: int = None) -> subprocess.CompletedProcess:
            if "eslint" in cmd:
                raise AssertionError("eslint should not be called without config")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        
        result = check_test_files_static(str(self.repo), [test_file], mock_run_cmd)
        
        # Should be None (skipped check silently)
        self.assertIsNone(result)
    
    def test_no_tsconfig_skips_typecheck(self):
        """Test that missing tsconfig skips typecheck."""
        from scripts.tdd_runner import check_test_files_static
        
        # Create package.json and eslint config, but NO tsconfig
        (self.repo / "package.json").write_text('{"name": "test"}\n')
        (self.repo / ".eslintrc.json").write_text('{"rules": {}}\n')
        
        test_file = "test/x.test.ts"
        (self.repo / "test").mkdir(exist_ok=True)
        (self.repo / test_file).write_text("const x = 1;\n")
        
        # Mock run_cmd that would fail if tsc were called
        def mock_run_cmd(cmd: list[str], cwd: str = None, timeout: int = None) -> subprocess.CompletedProcess:
            if "tsc" in cmd:
                raise AssertionError("tsc should not be called without tsconfig")
            if "eslint" in cmd:
                return subprocess.CompletedProcess(cmd, 0, "", "")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        
        result = check_test_files_static(str(self.repo), [test_file], mock_run_cmd)
        
        # Should be None (typecheck skipped, only eslint ran)
        self.assertIsNone(result)
    
    def test_all_allowed_ts_error_codes(self):
        """Test that all allowed TS error codes (TS2307, TS2305, TS2724, TS2614) are accepted."""
        from scripts.tdd_runner import check_test_files_static
        
        (self.repo / "package.json").write_text('{"name": "test"}\n')
        (self.repo / "tsconfig.json").write_text('{"compilerOptions": {}}\n')
        
        test_file = "test/x.test.ts"
        (self.repo / "test").mkdir(exist_ok=True)
        (self.repo / test_file).write_text("import { foo } from './missing';\n")
        
        allowed_codes = ["TS2307", "TS2305", "TS2724", "TS2614"]
        
        for code in allowed_codes:
            with self.subTest(code=code):
                def mock_run_cmd(cmd: list[str], cwd: str = None, timeout: int = None) -> subprocess.CompletedProcess:
                    if "tsc" in cmd:
                        return subprocess.CompletedProcess(
                            cmd, 2,
                            f"{test_file}(1,23): error {code}: Missing module.\n",
                            ""
                        )
                    if "eslint" in cmd:
                        return subprocess.CompletedProcess(cmd, 0, "", "")
                    return subprocess.CompletedProcess(cmd, 0, "", "")
                
                result = check_test_files_static(str(self.repo), [test_file], mock_run_cmd)
                self.assertIsNone(result, f"{code} should be accepted")


class TestREDPhaseWithStaticCheck(unittest.TestCase):
    """Integration tests for RED phase with static checking."""
    
    def setUp(self):
        """Create a temporary git repo."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_red_static_")
        self.repo = Path(self.temp_dir)
        
        # Initialize git repo
        self._run(["git", "init", "-q"])
        self._run(["git", "config", "user.email", "test@test.com"])
        self._run(["git", "config", "user.name", "Test User"])
        
        # Create minimal structure
        (self.repo / "docs" / "specs").mkdir(parents=True)
        (self.repo / "tests").mkdir()
        (self.repo / "src").mkdir()
        
        # Initial commit
        (self.repo / "README.md").write_text("# Test\n")
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-qm", "initial"])
    
    def tearDown(self):
        """Clean up temporary repo."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _run(self, cmd: list[str], cwd: str = None, timeout: int = None) -> subprocess.CompletedProcess:
        """Run a command in the temp repo."""
        return subprocess.run(
            cmd,
            cwd=cwd or self.repo,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )
    
    def test_red_eslint_failure_triggers_retry(self):
        """Test that eslint failure in RED triggers revert and retry."""
        from scripts.tdd_runner import run_red_phase
        from pathlib import Path
        
        # Create spec
        spec = {
            "summary": "Test feature",
            "decisions": [],
            "tasks": [
                {
                    "id": "T1",
                    "title": "Test task",
                    "description": "Test description",
                    "tests": [{"file": "tests/test_foo.py", "name": "test_foo", "asserts": "assert True"}],
                    "impl_files": ["src/foo.py"]
                }
            ]
        }
        
        task = spec["tasks"][0]
        
        # Create spec file
        spec_path = self.repo / "docs" / "specs" / "issue-1.md"
        spec_content = """---
issue: 1
status: approved
test_command: python3 -m unittest discover -s tests -v
---

# Test spec

## Decisiones de diseño

| ID | Topic | Opciones | Elegida | Rationale |
|----|-------|----------|---------|-----------|

## Tareas

### T1: Test task

Test description

**Tests:**
- `tests/test_foo.py::test_foo`: assert True

**Archivos de implementación:**
- `src/foo.py`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio
"""
        spec_path.write_text(spec_content)
        self._run(["git", "add", str(spec_path)])
        self._run(["git", "commit", "-qm", "docs: spec"])
        
        # Track coder calls
        coder_calls = []
        
        # Fake coder that writes invalid Python on first call, valid on second
        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            call_num = len(coder_calls)
            coder_calls.append({"prompt": prompt, "log_path": log_path})
            
            if call_num == 0:
                # First call: write test with syntax error
                (self.repo / "tests" / "test_foo.py").write_text("def test_foo(\n")  # Syntax error
                return 0, "Tests written"
            else:
                # Second call: write valid test
                (self.repo / "tests" / "test_foo.py").write_text(
                    "import unittest\n"
                    "class TestFoo(unittest.TestCase):\n"
                    "    def test_foo(self):\n"
                    "        assert False\n"  # Fails as expected
                )
                return 0, "Tests written (fixed)"
        
        logs_dir = self.repo / ".backlog" / "runs" / "issue-1"
        logs_dir.mkdir(parents=True)
        
        # Run RED phase
        result = run_red_phase(
            repo_root=str(self.repo),
            issue_num=1,
            task=task,
            spec=spec,
            spec_path=spec_path,
            test_cmd=["python3", "-m", "unittest", "discover", "-s", "tests", "-v"],
            logs_dir=logs_dir,
            coder=fake_coder,
            run_cmd=self._run,
            input_fn=lambda p: "",
            print_fn=lambda m: None
        )
        
        # Should succeed after retry
        self.assertTrue(result)
        
        # Should have made 2 coder calls
        self.assertEqual(len(coder_calls), 2)
        
        # Second call should have feedback about syntax error
        self.assertIn("Feedback", coder_calls[1]["prompt"])


class TestBuildRedPrompt(unittest.TestCase):
    """Tests for build_red_prompt function."""
    
    def test_prompt_contains_lint_rule(self):
        """Test that RED prompt contains lint/typecheck rule."""
        from scripts.tdd_runner import build_red_prompt
        
        spec = {
            "summary": "Test feature",
            "decisions": []
        }
        
        task = {
            "id": "T1",
            "title": "Test task",
            "description": "Test description",
            "tests": [{"file": "test.ts", "name": "test_foo", "asserts": "assert true"}],
            "impl_files": ["src/foo.ts"]
        }
        
        prompt = build_red_prompt(spec, task)
        
        # Should contain rule about lint/typecheck
        self.assertIn("lint", prompt.lower())
        self.assertIn("typecheck", prompt.lower())
    
    def test_prompt_contains_mock_rule(self):
        """Test that RED prompt contains rule about mocks."""
        from scripts.tdd_runner import build_red_prompt
        
        spec = {
            "summary": "Test feature",
            "decisions": []
        }
        
        task = {
            "id": "T1",
            "title": "Test task",
            "description": "Test description",
            "tests": [{"file": "test.ts", "name": "test_foo", "asserts": "assert true"}],
            "impl_files": ["src/foo.ts"]
        }
        
        prompt = build_red_prompt(spec, task)
        
        # Should contain rule about mocks
        self.assertIn("mock", prompt.lower())
        self.assertIn("fake", prompt.lower())


if __name__ == "__main__":
    unittest.main()

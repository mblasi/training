#!/usr/bin/env python3
"""
Tests for issue #17: test_support_files in RED/GREEN prompts and empty run detection.
"""
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestBuildRedPromptWithSupportFiles(unittest.TestCase):
    """Test build_red_prompt includes test_support_files section."""
    
    def test_red_prompt_with_test_support_files(self):
        """Test build_red_prompt includes test_support_files section when present."""
        from scripts.tdd_runner import build_red_prompt
        
        spec = {
            "summary": "Test feature",
            "decisions": [
                {"id": "D1", "topic": "Framework", "chosen": "vitest", "rationale": "Fast"}
            ]
        }
        
        task = {
            "id": "T1",
            "title": "Implement feature",
            "description": "Add feature X",
            "tests": [
                {"file": "pkg/test/x.test.ts", "name": "test_feature", "asserts": "x === y"}
            ],
            "test_support_files": [
                "pkg/vitest.config.ts",
                "pkg/tsconfig.test.json"
            ],
            "impl_files": ["pkg/src/index.ts"]
        }
        
        prompt = build_red_prompt(spec, task)
        
        # Should include test_support_files section
        self.assertIn("Archivos de soporte de tests", prompt)
        self.assertIn("pkg/vitest.config.ts", prompt)
        self.assertIn("pkg/tsconfig.test.json", prompt)
        
        # Should include instruction about creating them
        self.assertIn("cre", prompt.lower())  # "creá" o "crear"
        self.assertIn("ajust", prompt.lower())  # "ajustá" o "ajustar"
        
        # Should mention tests should RUN and fail
        self.assertIn("ejecuten", prompt.lower())
        self.assertIn("fallen", prompt.lower())
        
        # Should explicitly state impl_files are forbidden in RED
        self.assertIn("prohibido", prompt.lower())
        self.assertIn("pkg/src/index.ts", prompt)
    
    def test_red_prompt_without_test_support_files(self):
        """Test build_red_prompt omits test_support_files section when absent."""
        from scripts.tdd_runner import build_red_prompt
        
        spec = {
            "summary": "Test feature",
            "decisions": []
        }
        
        task = {
            "id": "T1",
            "title": "Implement feature",
            "description": "Add feature X",
            "tests": [
                {"file": "tests/test_feature.py", "name": "test_x", "asserts": "x == 5"}
            ],
            "impl_files": ["src/feature.py"]
        }
        
        prompt = build_red_prompt(spec, task)
        
        # Should NOT include test_support_files section
        self.assertNotIn("Archivos de soporte de tests", prompt)
    
    def test_red_prompt_with_empty_test_support_files(self):
        """Test build_red_prompt omits section when test_support_files is empty list."""
        from scripts.tdd_runner import build_red_prompt
        
        spec = {"summary": "Test", "decisions": []}
        task = {
            "id": "T1",
            "title": "Test",
            "description": "Desc",
            "tests": [{"file": "tests/test.py", "name": "test", "asserts": "True"}],
            "test_support_files": [],
            "impl_files": ["src/x.py"]
        }
        
        prompt = build_red_prompt(spec, task)
        self.assertNotIn("Archivos de soporte de tests", prompt)


class TestBuildGreenPromptWithSupportFiles(unittest.TestCase):
    """Test build_green_prompt includes test_support_files section."""
    
    def test_green_prompt_with_test_support_files(self):
        """Test build_green_prompt lists test_support_files and impl_files."""
        from scripts.tdd_runner import build_green_prompt
        
        spec = {
            "summary": "Test feature",
            "decisions": []
        }
        
        task = {
            "id": "T1",
            "title": "Implement feature",
            "description": "Add feature X",
            "tests": [{"file": "pkg/test/x.test.ts", "name": "test", "asserts": "x"}],
            "test_support_files": ["pkg/vitest.config.ts"],
            "impl_files": ["pkg/src/index.ts", "pkg/src/util.ts"]
        }
        
        prompt = build_green_prompt(spec, task, attempt=0)
        
        # Should list test_support_files
        self.assertIn("pkg/vitest.config.ts", prompt)
        
        # Should list impl_files
        self.assertIn("pkg/src/index.ts", prompt)
        self.assertIn("pkg/src/util.ts", prompt)
        
        # Should have both sections
        self.assertIn("Archivos", prompt)
    
    def test_green_prompt_without_test_support_files(self):
        """Test build_green_prompt works without test_support_files."""
        from scripts.tdd_runner import build_green_prompt
        
        spec = {"summary": "Test", "decisions": []}
        task = {
            "id": "T1",
            "title": "Test",
            "description": "Desc",
            "tests": [{"file": "tests/test.py", "name": "test", "asserts": "True"}],
            "impl_files": ["src/x.py"]
        }
        
        prompt = build_green_prompt(spec, task, attempt=0)
        
        # Should still include impl_files
        self.assertIn("src/x.py", prompt)


class TestDetectEmptyRun(unittest.TestCase):
    """Test detect_empty_run helper function."""
    
    def test_detects_no_projects_matched(self):
        """Test detect_empty_run detects 'No projects matched the filters'."""
        from scripts.tdd_runner import detect_empty_run
        
        output = "Running tests...\nNo projects matched the filters\n"
        result = detect_empty_run(output)
        
        self.assertIsNotNone(result)
        self.assertIn("No projects matched", result)
    
    def test_detects_no_test_files_found(self):
        """Test detect_empty_run detects 'No test files found'."""
        from scripts.tdd_runner import detect_empty_run
        
        output = "Searching for tests...\nNo test files found\nExiting.\n"
        result = detect_empty_run(output)
        
        self.assertIsNotNone(result)
        self.assertIn("No test files found", result)
    
    def test_detects_ran_0_tests(self):
        """Test detect_empty_run detects 'Ran 0 tests'."""
        from scripts.tdd_runner import detect_empty_run
        
        output = "Starting test run...\n\n----------------------------------------------------------------------\nRan 0 tests in 0.001s\n\nOK\n"
        result = detect_empty_run(output)
        
        self.assertIsNotNone(result)
        self.assertIn("Ran 0 tests", result)
    
    def test_no_detection_on_normal_failure(self):
        """Test detect_empty_run returns None for normal test failures."""
        from scripts.tdd_runner import detect_empty_run
        
        output = """
Running tests...
test_add (tests.test_calc.TestCalc) ... FAIL

======================================================================
FAIL: test_add (tests.test_calc.TestCalc)
----------------------------------------------------------------------
AssertionError: 5 != 0

----------------------------------------------------------------------
Ran 1 test in 0.002s

FAILED (failures=1)
"""
        result = detect_empty_run(output)
        self.assertIsNone(result)
    
    def test_no_detection_on_passing_tests(self):
        """Test detect_empty_run returns None when tests pass."""
        from scripts.tdd_runner import detect_empty_run
        
        output = "Ran 5 tests in 0.123s\n\nOK\n"
        result = detect_empty_run(output)
        self.assertIsNone(result)


class TestRedPhaseEmptyRunDetection(unittest.TestCase):
    """Test RED phase detects and handles empty test runs."""
    
    def setUp(self):
        """Create a temporary git repo."""
        self.temp_dir = tempfile.mkdtemp(prefix="red_empty_test_")
        self.repo = Path(self.temp_dir)
        
        # Initialize git repo
        self._run(["git", "init"])
        self._run(["git", "config", "user.email", "test@test.com"])
        self._run(["git", "config", "user.name", "Test User"])
        
        # Create structure
        (self.repo / "tests").mkdir()
        (self.repo / "docs" / "specs").mkdir(parents=True)
        (self.repo / ".backlog" / "runs" / "issue-1").mkdir(parents=True)
        (self.repo / ".gitignore").write_text("__pycache__/\n.backlog/\n")
        
        # Initial commit
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "initial"])
        
        # Create spec
        self._create_spec()
    
    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _run(self, cmd: list[str], cwd: str = None, timeout: int = None) -> subprocess.CompletedProcess:
        """Run command."""
        return subprocess.run(
            cmd,
            cwd=cwd or self.repo,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )
    
    def _create_spec(self):
        """Create spec with test_command that signals empty run."""
        # Create a test script that outputs empty run signal
        script_path = self.repo / "run_tests.sh"
        script_path.write_text('#!/bin/sh\necho "No test files found"\nexit 0\n')
        script_path.chmod(0o755)
        
        from take_agent import render_spec_markdown, set_status
        
        spec_dict = {
            "summary": "Test empty run detection",
            "decisions": [{"id": "D1", "topic": "Test", "options": ["pytest", "unittest"], "chosen": "pytest", "rationale": "Standard"}],
            "files": [],
            "test_command": "./run_tests.sh",
            "tasks": [
                {
                    "id": "T1",
                    "title": "Implement feature",
                    "description": "Add feature",
                    "tests": [{"file": "tests/test_x.py", "name": "test_x", "asserts": "x"}],
                    "test_support_files": ["pytest.ini"],
                    "impl_files": ["src/x.py"]
                }
            ],
            "out_of_scope": [],
            "risks": []
        }
        
        issue_dict = {"number": 1, "title": "Test Issue"}
        spec_md = render_spec_markdown(spec_dict, issue_dict)
        spec_path = self.repo / "docs" / "specs" / "issue-1.md"
        spec_path.write_text(spec_md)
        
        set_status(str(spec_path), "approved")
        
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "docs: spec"])
    
    def test_red_empty_run_retries_with_feedback(self):
        """Test RED detects empty run, retries with feedback, then asks user."""
        from scripts.tdd_runner import run_tdd_implementation
        
        coder_calls = []
        
        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            """Fake coder that creates test file but no support files."""
            coder_calls.append({"prompt": prompt, "log_path": log_path})
            
            if "red" in log_path.lower():
                # Create test file without support file
                test_file = self.repo / "tests" / "test_x.py"
                test_file.write_text("# test\n")
                return 0, "Tests written"
            
            return 1, "Not implemented"
        
        inputs = ["abortar"]  # User aborts after retries
        input_idx = [0]
        
        def mock_input(prompt: str) -> str:
            if input_idx[0] < len(inputs):
                result = inputs[input_idx[0]]
                input_idx[0] += 1
                return result
            return "abortar"
        
        outputs = []
        def mock_print(msg: str) -> None:
            outputs.append(msg)
        
        result = run_tdd_implementation(
            repo_root=str(self.repo),
            issue_num=1,
            coder=fake_coder,
            run_cmd=self._run,
            input_fn=mock_input,
            print_fn=mock_print
        )
        
        self.assertFalse(result, "Should fail when empty run detected")
        
        # Should have called coder multiple times for RED
        red_calls = [c for c in coder_calls if "red" in c["log_path"].lower()]
        self.assertGreater(len(red_calls), 1, "Should retry RED after empty run")
        
        # Second call should mention the empty run signal in prompt
        if len(red_calls) > 1:
            second_prompt = red_calls[1]["prompt"]
            self.assertIn("No test files found", second_prompt)
            self.assertIn("no se ejecutó ningún test", second_prompt.lower())
        
        # Should NOT have committed "test:"
        log = self._run(["git", "log", "--oneline"])
        self.assertNotIn("test:", log.stdout.lower())
        
        # Output should mention empty run as infrastructure problem
        output_text = " ".join(outputs).lower()
        self.assertIn("no se ejecutó ningún test", output_text)


class TestGreenPhaseEmptyRunDetection(unittest.TestCase):
    """Test GREEN phase detects and handles empty test runs."""
    
    def setUp(self):
        """Create a temporary git repo."""
        self.temp_dir = tempfile.mkdtemp(prefix="green_empty_test_")
        self.repo = Path(self.temp_dir)
        
        # Initialize git repo
        self._run(["git", "init"])
        self._run(["git", "config", "user.email", "test@test.com"])
        self._run(["git", "config", "user.name", "Test User"])
        
        # Create structure
        (self.repo / "tests").mkdir()
        (self.repo / "src").mkdir()
        (self.repo / "docs" / "specs").mkdir(parents=True)
        (self.repo / ".backlog" / "runs" / "issue-1").mkdir(parents=True)
        (self.repo / ".gitignore").write_text("__pycache__/\n.backlog/\n")
        
        # Initial commit
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "initial"])
        
        # Create spec and do RED commit
        self._create_spec_and_red_commit()
    
    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _run(self, cmd: list[str], cwd: str = None, timeout: int = None) -> subprocess.CompletedProcess:
        """Run command."""
        return subprocess.run(
            cmd,
            cwd=cwd or self.repo,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )
    
    def _create_spec_and_red_commit(self):
        """Create spec and simulate RED commit."""
        # Create test script that signals empty run
        script_path = self.repo / "run_tests.sh"
        script_path.write_text('#!/bin/sh\necho "Ran 0 tests in 0.001s"\nexit 0\n')
        script_path.chmod(0o755)
        
        from take_agent import render_spec_markdown, set_status, mark_progress
        
        spec_dict = {
            "summary": "Test GREEN empty run",
            "decisions": [],
            "files": [],
            "test_command": "./run_tests.sh",
            "tasks": [
                {
                    "id": "T1",
                    "title": "Feature",
                    "description": "Desc",
                    "tests": [{"file": "tests/test_x.py", "name": "test_x", "asserts": "x"}],
                    "impl_files": ["src/x.py"]
                }
            ],
            "out_of_scope": [],
            "risks": []
        }
        
        issue_dict = {"number": 1, "title": "Test Issue"}
        spec_md = render_spec_markdown(spec_dict, issue_dict)
        spec_path = self.repo / "docs" / "specs" / "issue-1.md"
        spec_path.write_text(spec_md)
        
        set_status(str(spec_path), "implementing")
        mark_progress(str(spec_path), "T1", "red")
        
        # Create test file (RED commit)
        (self.repo / "tests" / "test_x.py").write_text("# test\n")
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "test: feature (#1)"])
    
    def test_green_empty_run_counts_as_failed_attempt(self):
        """Test GREEN treats empty run as failed attempt with feedback."""
        from scripts.tdd_runner import run_tdd_implementation
        
        coder_calls = []
        
        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            """Fake coder that creates impl but test command returns empty."""
            coder_calls.append({"prompt": prompt, "log_path": log_path})
            
            if "green" in log_path.lower():
                # Create impl file
                impl_file = self.repo / "src" / "x.py"
                impl_file.write_text("# impl\n")
                return 0, "Implementation done"
            
            return 1, "Not implemented"
        
        inputs = ["abortar"]  # User aborts after retries
        input_idx = [0]
        
        def mock_input(prompt: str) -> str:
            if input_idx[0] < len(inputs):
                result = inputs[input_idx[0]]
                input_idx[0] += 1
                return result
            return "abortar"
        
        outputs = []
        def mock_print(msg: str) -> None:
            outputs.append(msg)
        
        result = run_tdd_implementation(
            repo_root=str(self.repo),
            issue_num=1,
            coder=fake_coder,
            run_cmd=self._run,
            input_fn=mock_input,
            print_fn=mock_print
        )
        
        self.assertFalse(result, "Should fail when GREEN has empty run")
        
        # Should have tried GREEN multiple times (up to 3)
        green_calls = [c for c in coder_calls if "green" in c["log_path"].lower()]
        self.assertEqual(len(green_calls), 3, "Should attempt GREEN 3 times")
        
        # Later attempts should include feedback with empty run signal
        if len(green_calls) > 1:
            later_prompt = green_calls[1]["prompt"]
            self.assertIn("Ran 0 tests", later_prompt)
        
        # Should NOT have committed "feat:"
        log = self._run(["git", "log", "--oneline"])
        self.assertNotIn("feat:", log.stdout.lower())


class TestHappyPathWithSupportFiles(unittest.TestCase):
    """Test happy path: RED creates support files, tests fail normally, GREEN passes."""
    
    def setUp(self):
        """Create a temporary git repo."""
        self.temp_dir = tempfile.mkdtemp(prefix="happy_support_test_")
        self.repo = Path(self.temp_dir)
        
        # Initialize git repo
        self._run(["git", "init"])
        self._run(["git", "config", "user.email", "test@test.com"])
        self._run(["git", "config", "user.name", "Test User"])
        
        # Create structure
        (self.repo / "tests").mkdir()
        (self.repo / "src").mkdir()
        (self.repo / "docs" / "specs").mkdir(parents=True)
        (self.repo / ".backlog" / "runs" / "issue-1").mkdir(parents=True)
        (self.repo / ".gitignore").write_text("__pycache__/\n.backlog/\n")
        
        # Create minimal src structure so tests can import
        (self.repo / "src" / "__init__.py").write_text("")
        (self.repo / "src" / "calc.py").write_text("def add(a, b): raise NotImplementedError()\n")
        
        # Initial commit
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "initial"])
        
        # Create spec
        self._create_spec()
    
    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _run(self, cmd: list[str], cwd: str = None, timeout: int = None) -> subprocess.CompletedProcess:
        """Run command."""
        return subprocess.run(
            cmd,
            cwd=cwd or self.repo,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )
    
    def _create_spec(self):
        """Create spec with test_support_files."""
        from take_agent import render_spec_markdown, set_status
        
        spec_dict = {
            "summary": "Happy path test",
            "decisions": [],
            "files": [],
            "test_command": "python3 -m unittest discover -s tests -v",
            "tasks": [
                {
                    "id": "T1",
                    "title": "Add calculator",
                    "description": "Implement add function",
                    "tests": [{"file": "tests/test_calc.py", "name": "test_add", "asserts": "add(2,3)==5"}],
                    "test_support_files": ["tests/__init__.py"],
                    "impl_files": ["src/calc.py"]
                }
            ],
            "out_of_scope": [],
            "risks": []
        }
        
        issue_dict = {"number": 1, "title": "Calculator"}
        spec_md = render_spec_markdown(spec_dict, issue_dict)
        spec_path = self.repo / "docs" / "specs" / "issue-1.md"
        spec_path.write_text(spec_md)
        
        set_status(str(spec_path), "approved")
        
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "docs: spec"])
    
    def test_happy_path_red_creates_support_files_green_passes(self):
        """Test RED creates test+support files, fails normally, GREEN implements and passes."""
        from scripts.tdd_runner import run_tdd_implementation
        
        coder_calls = []
        
        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            """Fake coder."""
            coder_calls.append({"prompt": prompt, "log_path": log_path})
            
            if "red" in log_path.lower():
                # Create test file and support file (src/calc.py already exists from setUp)
                (self.repo / "tests" / "__init__.py").write_text("")
                (self.repo / "tests" / "test_calc.py").write_text(
                    "import unittest\n"
                    "from src.calc import add\n\n"
                    "class TestCalc(unittest.TestCase):\n"
                    "    def test_add(self):\n"
                    "        self.assertEqual(add(2, 3), 5)\n"
                )
                return 0, "Tests written"
            
            elif "green" in log_path.lower():
                # Implement add function
                (self.repo / "src" / "calc.py").write_text("def add(a, b): return a + b\n")
                return 0, "Implementation done"
            
            elif "refactor" in log_path.lower():
                return 0, "SIN_REFACTOR"
            
            return 1, "Unknown phase"
        
        inputs = ["y"]  # Confirm first RED failure is expected
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
        
        result = run_tdd_implementation(
            repo_root=str(self.repo),
            issue_num=1,
            coder=fake_coder,
            run_cmd=self._run,
            input_fn=mock_input,
            print_fn=mock_print
        )
        
        self.assertTrue(result, "Should succeed")
        
        # Should have RED and GREEN commits
        log = self._run(["git", "log", "--oneline"])
        commits = log.stdout.lower()
        self.assertIn("test:", commits)
        self.assertIn("feat:", commits)
        
        # Verify support file was created and committed
        self.assertTrue((self.repo / "tests" / "__init__.py").exists())
        
        # Verify RED prompt included test_support_files section
        red_calls = [c for c in coder_calls if "red" in c["log_path"].lower()]
        self.assertEqual(len(red_calls), 1)
        red_prompt = red_calls[0]["prompt"]
        self.assertIn("tests/__init__.py", red_prompt)
        self.assertIn("soporte", red_prompt.lower())


if __name__ == "__main__":
    unittest.main()

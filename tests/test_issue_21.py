#!/usr/bin/env python3
"""
Tests for issue #21: dependency infra files allowed in RED, /DESVIO not consuming attempts.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Add scripts dir to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestIsDependencyInfraFile(unittest.TestCase):
    """Test is_dependency_infra_file helper function."""
    
    def test_lockfile_positives(self):
        """Test is_dependency_infra_file recognizes known lockfiles."""
        from scripts.tdd_runner import is_dependency_infra_file
        
        self.assertTrue(is_dependency_infra_file("pnpm-lock.yaml"))
        self.assertTrue(is_dependency_infra_file("apps/web/pnpm-lock.yaml"))
        self.assertTrue(is_dependency_infra_file("package-lock.json"))
        self.assertTrue(is_dependency_infra_file("yarn.lock"))
        self.assertTrue(is_dependency_infra_file("poetry.lock"))
        self.assertTrue(is_dependency_infra_file("uv.lock"))
        self.assertTrue(is_dependency_infra_file("pnpm-workspace.yaml"))
        self.assertTrue(is_dependency_infra_file("apps/api/package-lock.json"))
    
    def test_requirements_txt_patterns(self):
        """Test is_dependency_infra_file matches requirements*.txt patterns."""
        from scripts.tdd_runner import is_dependency_infra_file
        
        self.assertTrue(is_dependency_infra_file("requirements.txt"))
        self.assertTrue(is_dependency_infra_file("requirements-dev.txt"))
        self.assertTrue(is_dependency_infra_file("requirements-test.txt"))
        self.assertTrue(is_dependency_infra_file("pkg/requirements.txt"))
        self.assertTrue(is_dependency_infra_file("services/api/requirements-prod.txt"))
    
    def test_negatives(self):
        """Test is_dependency_infra_file rejects non-lockfiles."""
        from scripts.tdd_runner import is_dependency_infra_file
        
        self.assertFalse(is_dependency_infra_file("src/lock.ts"))
        self.assertFalse(is_dependency_infra_file("package.json"))
        self.assertFalse(is_dependency_infra_file("pyproject.toml"))
        self.assertFalse(is_dependency_infra_file("src/requirements.py"))
        self.assertFalse(is_dependency_infra_file("lock.yaml"))
        self.assertFalse(is_dependency_infra_file("workspace.yaml"))


class TestRedAllowsDependencyInfra(unittest.TestCase):
    """Test RED phase allows dependency infra files."""
    
    def setUp(self):
        """Create a temporary git repo."""
        self.temp_dir = tempfile.mkdtemp(prefix="red_depinfra_test_")
        self.repo = Path(self.temp_dir)
        
        # Initialize git repo
        self._run(["git", "init"])
        self._run(["git", "config", "user.email", "test@test.com"])
        self._run(["git", "config", "user.name", "Test User"])
        
        # Create structure
        (self.repo / "tests").mkdir()
        (self.repo / "pkg").mkdir()
        (self.repo / "docs" / "specs").mkdir(parents=True)
        (self.repo / ".backlog" / "runs").mkdir(parents=True)
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
        """Create a spec file."""
        from take_agent import render_spec_markdown, set_status
        
        spec_dict = {
            "summary": "Test lockfile allowed in RED",
            "decisions": [],
            "files": [],
            "test_command": "python3 -c 'import sys; sys.exit(1)'",
            "tasks": [
                {
                    "id": "T1",
                    "title": "Feature",
                    "description": "Desc",
                    "tests": [{"file": "tests/test_x.py", "name": "test_x", "asserts": "x"}],
                    "test_support_files": ["pkg/vitest.config.ts"],
                    "impl_files": ["pkg/src/index.ts"]
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
    
    def test_red_accepts_lockfiles_and_support_files(self):
        """Test RED accepts test + support file + lockfiles (pnpm-lock.yaml, pnpm-workspace.yaml)."""
        from scripts.tdd_runner import run_tdd_implementation
        
        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            if "red" in log_path.lower():
                # Create test, support file, AND lockfiles
                (self.repo / "tests" / "test_x.py").write_text("# test\n")
                (self.repo / "pkg" / "vitest.config.ts").write_text("// config\n")
                (self.repo / "pnpm-lock.yaml").write_text("lockfileVersion: '6.0'\n")
                (self.repo / "pnpm-workspace.yaml").write_text("packages:\n  - 'pkg'\n")
                return 0, "Tests written with lockfiles"
            return 1, "Not implemented"
        
        outputs = []
        def mock_print(msg: str) -> None:
            outputs.append(msg)
        
        result = run_tdd_implementation(
            repo_root=str(self.repo),
            issue_num=1,
            coder=fake_coder,
            run_cmd=self._run,
            input_fn=lambda p: "abortar",
            print_fn=mock_print
        )
        
        # Should fail at test execution (test command exits 1), NOT at file validation
        output_text = " ".join(outputs)
        self.assertNotIn("archivos de producción en RED", output_text)
        
        # Lockfiles should still be present (not reverted)
        self.assertTrue((self.repo / "pnpm-lock.yaml").exists())
        self.assertTrue((self.repo / "pnpm-workspace.yaml").exists())
    
    def test_red_rejects_impl_file_even_with_lockfiles(self):
        """Test RED rejects impl_files even if lockfiles are present."""
        from scripts.tdd_runner import run_tdd_implementation
        
        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            if "red" in log_path.lower():
                # Create test, support, lockfiles, AND impl file
                (self.repo / "tests" / "test_x.py").write_text("# test\n")
                (self.repo / "pkg" / "vitest.config.ts").write_text("// config\n")
                (self.repo / "pnpm-lock.yaml").write_text("lock\n")
                (self.repo / "pkg" / "src").mkdir(parents=True, exist_ok=True)
                (self.repo / "pkg" / "src" / "index.ts").write_text("// FORBIDDEN\n")
                return 0, "Tests written"
            return 1, "Not implemented"
        
        outputs = []
        def mock_print(msg: str) -> None:
            outputs.append(msg)
        
        result = run_tdd_implementation(
            repo_root=str(self.repo),
            issue_num=1,
            coder=fake_coder,
            run_cmd=self._run,
            input_fn=lambda p: "abortar",
            print_fn=mock_print
        )
        
        self.assertFalse(result)
        
        # Should reject impl file
        output_text = " ".join(outputs)
        self.assertIn("archivos de producción en RED", output_text)
        self.assertIn("pkg/src/index.ts", output_text)


class TestDesvioDoesNotConsumeAttempt(unittest.TestCase):
    """Test that a resolved /DESVIO does not consume an attempt in RED/GREEN."""
    
    def setUp(self):
        """Create a temporary git repo."""
        self.temp_dir = tempfile.mkdtemp(prefix="desvio_attempt_test_")
        self.repo = Path(self.temp_dir)
        
        # Initialize git repo
        self._run(["git", "init"])
        self._run(["git", "config", "user.email", "test@test.com"])
        self._run(["git", "config", "user.name", "Test User"])
        
        # Create structure
        (self.repo / "tests").mkdir()
        (self.repo / "src").mkdir()
        (self.repo / "docs" / "specs").mkdir(parents=True)
        (self.repo / ".backlog" / "runs").mkdir(parents=True)
        (self.repo / ".gitignore").write_text("__pycache__/\n.backlog/\n")
        
        # Create minimal Python project
        (self.repo / "src" / "__init__.py").write_text("")
        (self.repo / "src" / "calc.py").write_text("def add(a, b): raise NotImplementedError()\n")
        (self.repo / "tests" / "__init__.py").write_text("")
        
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
        """Create spec."""
        from take_agent import render_spec_markdown, set_status
        
        spec_dict = {
            "summary": "Test /DESVIO not consuming attempt",
            "decisions": [{"id": "D1", "topic": "Framework", "options": ["pytest"], "chosen": "pytest", "rationale": "Standard"}],
            "files": [],
            "test_command": "python3 -m unittest discover -s tests -v",
            "tasks": [
                {
                    "id": "T1",
                    "title": "Add function",
                    "description": "Implement add",
                    "tests": [{"file": "tests/test_calc.py", "name": "test_add", "asserts": "add(2,3)==5"}],
                    "impl_files": ["src/calc.py"]
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
    
    def test_red_desvio_on_last_attempt_then_succeeds(self):
        """Test RED: /DESVIO on attempt 2 (last), user decides, coder invoked again, RED completes."""
        from scripts.tdd_runner import run_tdd_implementation
        
        call_count = [0]
        
        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            if "red" in log_path.lower():
                call_count[0] += 1
                
                if call_count[0] == 1:
                    # First attempt: fail validation (e.g. no files)
                    return 0, "Forgot to write tests"
                elif call_count[0] == 2:
                    # Second attempt (LAST): emit /DESVIO
                    return 0, "/DESVIO Necesito usar librería externa para validación"
                else:
                    # After decision: write tests successfully
                    (self.repo / "tests" / "test_calc.py").write_text(
                        "import unittest\n"
                        "from src.calc import add\n\n"
                        "class TestCalc(unittest.TestCase):\n"
                        "    def test_add(self):\n"
                        "        self.assertEqual(add(2, 3), 5)\n"
                    )
                    return 0, "Tests written after decision"
            elif "green" in log_path.lower():
                (self.repo / "src" / "calc.py").write_text("def add(a, b): return a + b\n")
                return 0, "Implementation done"
            elif "refactor" in log_path.lower():
                return 0, "SIN_REFACTOR"
            
            return 1, "Unknown phase"
        
        # Inputs: "Usar stdlib", "y" (confirm RED failure is expected)
        inputs = ["Usar stdlib solamente", "y"]
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
        
        self.assertTrue(result, "TDD should succeed after /DESVIO is resolved")
        
        # Coder should be called 3+ times for RED (attempt1, attempt2=/DESVIO, retry after decision)
        red_calls = [i for i in range(1, call_count[0] + 1) if i <= 3]
        self.assertGreaterEqual(call_count[0], 3, f"Coder should be invoked at least 3 times for RED (attempt1, attempt2=/DESVIO, retry), got {call_count[0]}")
        
        # Verify decision was added to spec
        spec_content = (self.repo / "docs" / "specs" / "issue-1.md").read_text()
        self.assertIn("D2", spec_content)
        self.assertIn("Usar stdlib", spec_content)
    
    def test_green_desvio_on_last_attempt_then_succeeds(self):
        """Test GREEN: /DESVIO on attempt 3 (last), user decides, coder invoked again, GREEN completes."""
        from scripts.tdd_runner import run_tdd_implementation
        
        # Mark RED as done
        spec_path = self.repo / "docs" / "specs" / "issue-1.md"
        spec_content = spec_path.read_text()
        spec_content = spec_content.replace("- [ ] RED:", "- [x] RED:")
        spec_content = spec_content.replace("status: approved", "status: implementing")
        spec_path.write_text(spec_content)
        
        # Commit RED test
        (self.repo / "tests" / "test_calc.py").write_text(
            "import unittest\n"
            "from src.calc import add\n\n"
            "class TestCalc(unittest.TestCase):\n"
            "    def test_add(self):\n"
            "        self.assertEqual(add(2, 3), 5)\n"
        )
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "test: add (#1)"])
        
        call_count = [0]
        
        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            if "green" in log_path.lower():
                call_count[0] += 1
                
                if call_count[0] <= 2:
                    # Attempts 1-2: wrong implementation
                    (self.repo / "src" / "calc.py").write_text("def add(a, b): return 0\n")
                    return 0, "Wrong impl"
                elif call_count[0] == 3:
                    # Attempt 3 (LAST): emit /DESVIO
                    return 0, "/DESVIO Necesito cambiar la API de add() para soportar más de 2 args"
                else:
                    # After decision: correct implementation
                    (self.repo / "src" / "calc.py").write_text("def add(a, b): return a + b\n")
                    return 0, "Correct impl after decision"
            elif "refactor" in log_path.lower():
                return 0, "SIN_REFACTOR"
            
            return 1, "Unknown phase"
        
        inputs = ["Mantener API con 2 args solamente"]
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
        
        self.assertTrue(result, "TDD should succeed after GREEN /DESVIO is resolved")
        
        # Coder should be called 4 times for GREEN (3 attempts then /DESVIO, then retry after decision)
        self.assertGreaterEqual(call_count[0], 4, f"Coder should be invoked at least 4 times for GREEN, got {call_count[0]}")
        
        # Verify decision was added
        spec_content = (self.repo / "docs" / "specs" / "issue-1.md").read_text()
        self.assertIn("D2", spec_content)
        self.assertIn("Mantener API", spec_content)
    
    def test_red_desvio_prompt_includes_decision(self):
        """Test RED retry prompt after /DESVIO includes the decision taken."""
        from scripts.tdd_runner import run_tdd_implementation
        
        prompts_seen = []
        
        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            prompts_seen.append(prompt)
            
            if "red" in log_path.lower():
                if len(prompts_seen) == 1:
                    # First: emit /DESVIO
                    return 0, "/DESVIO Usar validación custom"
                else:
                    # After decision: write tests
                    (self.repo / "tests" / "test_calc.py").write_text(
                        "import unittest\n"
                        "from src.calc import add\n\n"
                        "class TestCalc(unittest.TestCase):\n"
                        "    def test_add(self):\n"
                        "        self.assertEqual(add(2, 3), 5)\n"
                    )
                    return 0, "Tests written"
            elif "green" in log_path.lower():
                (self.repo / "src" / "calc.py").write_text("def add(a, b): return a + b\n")
                return 0, "Impl done"
            elif "refactor" in log_path.lower():
                return 0, "SIN_REFACTOR"
            
            return 1, "Unknown"
        
        inputs = ["Usar assert builtin nada más", "y"]
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
        
        self.assertTrue(result)
        
        # Second RED prompt should include the decision
        self.assertGreaterEqual(len(prompts_seen), 2)
        second_red_prompt = prompts_seen[1]
        self.assertIn("Decisión tomada", second_red_prompt)
        self.assertIn("Usar assert builtin", second_red_prompt)


class TestDesvioCapAt3(unittest.TestCase):
    """Test that exceeding 3 /DESVIOs per phase stops the phase."""
    
    def setUp(self):
        """Create a temporary git repo."""
        self.temp_dir = tempfile.mkdtemp(prefix="desvio_cap_test_")
        self.repo = Path(self.temp_dir)
        
        # Initialize git repo
        self._run(["git", "init"])
        self._run(["git", "config", "user.email", "test@test.com"])
        self._run(["git", "config", "user.name", "Test User"])
        
        # Create structure
        (self.repo / "tests").mkdir()
        (self.repo / "src").mkdir()
        (self.repo / "docs" / "specs").mkdir(parents=True)
        (self.repo / ".backlog" / "runs").mkdir(parents=True)
        (self.repo / ".gitignore").write_text("__pycache__/\n.backlog/\n")
        
        (self.repo / "src" / "__init__.py").write_text("")
        (self.repo / "tests" / "__init__.py").write_text("")
        
        # Initial commit
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "initial"])
        
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
        """Create spec."""
        from take_agent import render_spec_markdown, set_status
        
        spec_dict = {
            "summary": "Test /DESVIO cap",
            "decisions": [
                {"id": "D1", "topic": "Initial", "options": ["A"], "chosen": "A", "rationale": "Init"}
            ],
            "files": [],
            "test_command": "python3 -m unittest discover -s tests -v",
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
        
        issue_dict = {"number": 1, "title": "Test"}
        spec_md = render_spec_markdown(spec_dict, issue_dict)
        spec_path = self.repo / "docs" / "specs" / "issue-1.md"
        spec_path.write_text(spec_md)
        
        set_status(str(spec_path), "approved")
        
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "docs: spec"])
    
    def test_red_exceeding_3_desvios_stops_with_message(self):
        """Test RED phase with 4 /DESVIOs stops after the 3rd with a clear message."""
        from scripts.tdd_runner import run_tdd_implementation
        
        call_count = [0]
        
        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            if "red" in log_path.lower():
                call_count[0] += 1
                return 0, f"/DESVIO Decision needed #{call_count[0]}"
            return 1, "Not implemented"
        
        # User provides 3 decisions (4th /DESVIO should trigger cap before asking)
        inputs = ["Decision 1", "Decision 2", "Decision 3"]
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
        
        self.assertFalse(result, "Should fail after exceeding 3 /DESVIOs")
        
        # Coder should be called exactly 4 times (initial + 3 retries after decisions)
        self.assertEqual(call_count[0], 4, f"Expected 4 coder calls (1 initial + 3 retries), got {call_count[0]}")
        
        # Output should mention the cap
        output_text = " ".join(outputs).lower()
        self.assertIn("desvío", output_text)
        self.assertIn("3", output_text)
        
        # Should have recorded 3 decisions during impl (D2, D3, D4) in spec (D1 was initial)
        spec_content = (self.repo / "docs" / "specs" / "issue-1.md").read_text()
        self.assertIn("D1", spec_content)  # Initial
        self.assertIn("D2", spec_content)  # From 1st /DESVIO
        self.assertIn("D3", spec_content)  # From 2nd /DESVIO
        self.assertIn("D4", spec_content)  # From 3rd /DESVIO
        # 4th /DESVIO should NOT add D5 (cap reached)
        self.assertNotIn("D5", spec_content)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""
Tests for TDD runner state machine (scripts/tdd_runner.py).
Uses a temporary real git repo with a tiny Python project.
"""
import json
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any


class TestTDDRunner(unittest.TestCase):
    """Test TDD state machine with a real temporary git repo."""
    
    def setUp(self):
        """Create a temporary git repo with a minimal Python project."""
        self.temp_dir = tempfile.mkdtemp(prefix="tdd_test_")
        self.repo = Path(self.temp_dir)
        
        # Initialize git repo
        self._run(["git", "init"])
        self._run(["git", "config", "user.email", "test@test.com"])
        self._run(["git", "config", "user.name", "Test User"])
        
        # Create minimal Python project structure
        (self.repo / "tests").mkdir()
        (self.repo / "src").mkdir()
        (self.repo / "docs" / "specs").mkdir(parents=True)
        (self.repo / ".backlog" / "runs").mkdir(parents=True)
        
        # Create a minimal module
        (self.repo / "src" / "__init__.py").write_text("")
        (self.repo / "src" / "calculator.py").write_text(
            "# Calculator module\n"
            "def add(a, b):\n"
            "    raise NotImplementedError()\n"
        )
        
        # Create initial test file (empty)
        (self.repo / "tests" / "__init__.py").write_text("")
        (self.repo / "tests" / "test_calculator.py").write_text(
            "import unittest\n\n"
            "class TestCalculator(unittest.TestCase):\n"
            "    pass\n"
        )
        
        # Initial commit
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "initial commit"])
        
        # Create spec file for issue #1
        self._create_spec_file()
    
    def tearDown(self):
        """Clean up temporary repo."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _run(self, cmd: list[str], cwd: str = None, timeout: int = None, check: bool = True) -> subprocess.CompletedProcess:
        """Run a command in the temp repo."""
        return subprocess.run(
            cmd,
            cwd=cwd or self.repo,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False  # Don't raise on non-zero exit
        )
    
    def _create_spec_file(self):
        """Create a spec file for issue #1."""
        spec_content = """---
issue: 1
status: approved
test_command: python3 -m unittest discover -s tests -v
---

# Spec de implementación: Test Issue

## Resumen

Implementar suma básica en calculator.

## Decisiones de diseño

| ID | Topic | Opciones | Elegida | Rationale |
|----|-------|----------|---------|-----------|
| D1 | Implementación | función simple, clase | función simple | Más directo |

## Archivos afectados

- **modify** `src/calculator.py`: implementar add()
- **modify** `tests/test_calculator.py`: agregar tests

## Tareas

### T1: Implementar suma

Agregar función add() que suma dos números.

**Tests:**
- `tests/test_calculator.py::test_add_positive`: assert add(2, 3) == 5
- `tests/test_calculator.py::test_add_negative`: assert add(-1, -2) == -3

**Archivos de implementación:**
- `src/calculator.py`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

## Fuera de alcance

_(ninguno)_

## Riesgos

_(ninguno)_
"""
        spec_path = self.repo / "docs" / "specs" / "issue-1.md"
        spec_path.write_text(spec_content)
        self._run(["git", "add", str(spec_path)])
        self._run(["git", "commit", "-m", "docs: spec de implementación (#1)"])
    
    def _create_fake_coder(self, script: dict[str, Any]) -> callable:
        """
        Create a fake coder function that follows a script.
        
        script: {
            "T1": {
                "red": [{"files": {...}, "exit": 0, "output": "..."}] or single dict,
                "green": ...,
                "refactor": ... or "SIN_REFACTOR"
            }
        }
        """
        self.coder_calls = []
        self.phase_attempts = {}  # Track attempts per phase
        
        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            """Fake coder that writes scripted files."""
            self.coder_calls.append({"prompt": prompt, "log_path": log_path})
            
            # Detect phase from log_path
            if "red" in log_path.lower():
                phase = "red"
            elif "green" in log_path.lower():
                phase = "green"
            elif "refactor" in log_path.lower():
                phase = "refactor"
            else:
                return 1, "Unknown phase"
            
            # Detect task from prompt or log_path
            task_id = None
            for tid in script.keys():
                if tid in log_path:
                    task_id = tid
                    break
            
            if not task_id or task_id not in script:
                return 1, f"No script for task {task_id}"
            
            # Track attempts for this task+phase
            key = f"{task_id}:{phase}"
            attempt_num = self.phase_attempts.get(key, 0)
            self.phase_attempts[key] = attempt_num + 1
            
            task_script = script[task_id].get(phase)
            
            if task_script == "SIN_REFACTOR":
                return 0, "SIN_REFACTOR\nNo changes needed."
            
            if not task_script:
                return 1, f"No script for {task_id}/{phase}"
            
            # Support list of responses (for retries)
            if isinstance(task_script, list):
                if attempt_num < len(task_script):
                    task_script = task_script[attempt_num]
                else:
                    # Out of scripted responses, use last one
                    task_script = task_script[-1]
            
            # Write files
            for path, content in task_script.get("files", {}).items():
                full_path = self.repo / path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)
            
            exit_code = task_script.get("exit", 0)
            output = task_script.get("output", f"Phase {phase} completed")
            
            return exit_code, output
        
        return fake_coder
    
    def test_happy_path_full_cycle(self):
        """Test happy path: RED → GREEN → REFACTOR, all phases pass."""
        from scripts.tdd_runner import run_tdd_implementation
        
        # Script for fake coder
        script = {
            "T1": {
                "red": {
                    "files": {
                        "tests/test_calculator.py": (
                            "import unittest\n"
                            "from src.calculator import add\n\n"
                            "class TestCalculator(unittest.TestCase):\n"
                            "    def test_add_positive(self):\n"
                            "        self.assertEqual(add(2, 3), 5)\n"
                            "    def test_add_negative(self):\n"
                            "        self.assertEqual(add(-1, -2), -3)\n"
                        )
                    },
                    "exit": 0,
                    "output": "Tests written"
                },
                "green": {
                    "files": {
                        "src/calculator.py": (
                            "# Calculator module\n"
                            "def add(a, b):\n"
                            "    return a + b\n"
                        )
                    },
                    "exit": 0,
                    "output": "Implementation done"
                },
                "refactor": "SIN_REFACTOR"
            }
        }
        
        fake_coder = self._create_fake_coder(script)
        
        # Mock input to confirm RED failure on first attempt
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
        
        # Run TDD implementation
        result = run_tdd_implementation(
            repo_root=str(self.repo),
            issue_num=1,
            coder=fake_coder,
            run_cmd=self._run,
            input_fn=mock_input,
            print_fn=mock_print
        )
        
        self.assertTrue(result, "TDD run should succeed")
        
        # Verify commits were made
        log = self._run(["git", "log", "--oneline", "--no-decorate"])
        commits = log.stdout.strip().split("\n")
        
        # Git log shows most recent first
        # Should have: spec completada, feat (#1), test (#1), (spec), initial
        self.assertGreaterEqual(len(commits), 4)
        # Most recent commits should include test and feat
        commit_text = " ".join(commits)
        self.assertIn("test:", commit_text.lower())
        self.assertIn("feat:", commit_text.lower())
        
        # Verify spec checkboxes are marked
        spec_path = self.repo / "docs" / "specs" / "issue-1.md"
        spec_content = spec_path.read_text()
        self.assertIn("[x] RED:", spec_content)
        self.assertIn("[x] GREEN:", spec_content)
        self.assertIn("[x] REFACTOR:", spec_content)
        
        # Verify status is done
        self.assertIn("status: done", spec_content)
    
    def test_red_that_passes_retry_then_ask_user(self):
        """Test RED phase where tests pass (should retry then ask user)."""
        from scripts.tdd_runner import run_tdd_implementation
        
        # Script: RED writes tests that already pass (wrong!)
        script = {
            "T1": {
                "red": {
                    "files": {
                        "tests/test_calculator.py": (
                            "import unittest\n\n"
                            "class TestCalculator(unittest.TestCase):\n"
                            "    def test_trivial(self):\n"
                            "        self.assertTrue(True)  # Always passes!\n"
                        )
                    },
                    "exit": 0
                }
            }
        }
        
        fake_coder = self._create_fake_coder(script)
        
        # Mock input: first to confirm infra issue (n), then retry attempts will ask continuar/abortar
        inputs = ["n", "abortar"]  # Not an infra issue, then abort
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
        
        self.assertFalse(result, "TDD should fail when RED passes")
        
        # Should have called coder twice for RED (initial + retry)
        red_calls = [c for c in self.coder_calls if "red" in c["log_path"].lower()]
        self.assertEqual(len(red_calls), 2, "Should retry RED once")
    
    def test_red_touching_production_file_reverted(self):
        """Test RED phase that modifies production code (should revert)."""
        from scripts.tdd_runner import run_tdd_implementation
        
        script = {
            "T1": {
                "red": {
                    "files": {
                        "tests/test_calculator.py": (
                            "import unittest\n"
                            "from src.calculator import add\n\n"
                            "class TestCalculator(unittest.TestCase):\n"
                            "    def test_add(self):\n"
                            "        self.assertEqual(add(2, 3), 5)\n"
                        ),
                        # Oops, also modified production code!
                        "src/calculator.py": (
                            "def add(a, b):\n"
                            "    return a + b  # Should not be in RED!\n"
                        )
                    },
                    "exit": 0
                }
            }
        }
        
        fake_coder = self._create_fake_coder(script)
        
        inputs = ["y", "abortar"]  # Confirm first RED, then abort after revert
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
        
        self.assertFalse(result)
        
        # Verify production file was reverted
        calc_content = (self.repo / "src" / "calculator.py").read_text()
        self.assertIn("NotImplementedError", calc_content, "Production file should be reverted")
    
    def test_green_modifying_tests_rejected(self):
        """Test GREEN phase that modifies test files (should reject)."""
        from scripts.tdd_runner import run_tdd_implementation
        
        script = {
            "T1": {
                "red": {
                    "files": {
                        "tests/test_calculator.py": (
                            "import unittest\n"
                            "from src.calculator import add\n\n"
                            "class TestCalculator(unittest.TestCase):\n"
                            "    def test_add(self):\n"
                            "        self.assertEqual(add(2, 3), 5)\n"
                        )
                    },
                    "exit": 0
                },
                "green": {
                    "files": {
                        "src/calculator.py": "def add(a, b):\n    return a + b\n",
                        # Oops, modified tests!
                        "tests/test_calculator.py": (
                            "import unittest\n"
                            "from src.calculator import add\n\n"
                            "class TestCalculator(unittest.TestCase):\n"
                            "    def test_add(self):\n"
                            "        self.assertTrue(True)  # Weakened test!\n"
                        )
                    },
                    "exit": 0
                }
            }
        }
        
        fake_coder = self._create_fake_coder(script)
        
        inputs = ["y", "abortar"]  # Confirm RED, abort after GREEN rejects
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
        
        self.assertFalse(result)
        
        # Verify only RED commit was made
        log = self._run(["git", "log", "--oneline", "--no-decorate"])
        commits = log.stdout.strip().split("\n")
        # Should have initial, spec, and test commit only
        test_commits = [c for c in commits if "test:" in c.lower()]
        feat_commits = [c for c in commits if "feat:" in c.lower()]
        
        self.assertEqual(len(test_commits), 1, "Should have 1 test commit")
        self.assertEqual(len(feat_commits), 0, "Should have no feat commits (GREEN failed)")
    
    def test_green_three_failures_ask_user(self):
        """Test GREEN phase failing 3 times (should ask user)."""
        from scripts.tdd_runner import run_tdd_implementation
        
        script = {
            "T1": {
                "red": {
                    "files": {
                        "tests/test_calculator.py": (
                            "import unittest\n"
                            "from src.calculator import add\n\n"
                            "class TestCalculator(unittest.TestCase):\n"
                            "    def test_add(self):\n"
                            "        self.assertEqual(add(2, 3), 5)\n"
                        )
                    },
                    "exit": 0
                },
                "green": {
                    "files": {
                        # Wrong implementation every time
                        "src/calculator.py": "def add(a, b):\n    return 0  # Wrong!\n"
                    },
                    "exit": 0
                }
            }
        }
        
        fake_coder = self._create_fake_coder(script)
        
        inputs = ["y", "abortar"]  # Confirm RED, abort after 3 GREEN failures
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
        
        self.assertFalse(result)
        
        # Should have tried GREEN 3 times
        green_calls = [c for c in self.coder_calls if "green" in c["log_path"].lower()]
        self.assertEqual(len(green_calls), 3, "Should attempt GREEN 3 times")
    
    def test_refactor_breaks_tests_reverted(self):
        """Test REFACTOR that breaks tests (should revert)."""
        from scripts.tdd_runner import run_tdd_implementation
        
        script = {
            "T1": {
                "red": {
                    "files": {
                        "tests/test_calculator.py": (
                            "import unittest\n"
                            "from src.calculator import add\n\n"
                            "class TestCalculator(unittest.TestCase):\n"
                            "    def test_add(self):\n"
                            "        self.assertEqual(add(2, 3), 5)\n"
                        )
                    },
                    "exit": 0
                },
                "green": {
                    "files": {
                        "src/calculator.py": "def add(a, b):\n    return a + b\n"
                    },
                    "exit": 0
                },
                "refactor": {
                    "files": {
                        # Broken refactor
                        "src/calculator.py": "def add(a, b):\n    return a - b  # Oops!\n"
                    },
                    "exit": 0
                }
            }
        }
        
        fake_coder = self._create_fake_coder(script)
        
        inputs = ["y"]  # Confirm RED
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
        
        self.assertTrue(result, "Should complete (refactor failure is non-fatal)")
        
        # Verify refactor was reverted (implementation should be GREEN version)
        calc_content = (self.repo / "src" / "calculator.py").read_text()
        self.assertIn("return a + b", calc_content)
        self.assertNotIn("return a - b", calc_content)
        
        # Verify REFACTOR checkbox is still marked (with note about revert)
        spec_content = (self.repo / "docs" / "specs" / "issue-1.md").read_text()
        self.assertIn("[x] REFACTOR:", spec_content)
    
    def test_desvio_detection(self):
        """Test /DESVIO marker detection and decision append."""
        from scripts.tdd_runner import run_tdd_implementation
        
        script = {
            "T1": {
                "red": [
                    {
                        "files": {},
                        "exit": 0,
                        "output": "/DESVIO Necesito usar una librería externa para validación"
                    },
                    # After user decides, retry
                    {
                        "files": {
                            "tests/test_calculator.py": (
                                "import unittest\n"
                                "from src.calculator import add\n\n"
                                "class TestCalculator(unittest.TestCase):\n"
                                "    def test_add(self):\n"
                                "        self.assertEqual(add(2, 3), 5)\n"
                            )
                        },
                        "exit": 0
                    }
                ],
                "green": {
                    "files": {
                        "src/calculator.py": "def add(a, b):\n    return a + b\n"
                    },
                    "exit": 0
                },
                "refactor": "SIN_REFACTOR"
            }
        }
        
        fake_coder = self._create_fake_coder(script)
        
        # Mock: first call detects /DESVIO, user responds, then continue
        inputs = ["Usar stdlib, no librerías externas", "y"]
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
        
        # Verify decision was added to spec
        spec_content = (self.repo / "docs" / "specs" / "issue-1.md").read_text()
        self.assertIn("D2", spec_content, "Should add new decision")
        self.assertIn("Usar stdlib", spec_content)
        
        # Verify decision commit
        log = self._run(["git", "log", "--oneline", "--no-decorate"])
        commits = log.stdout.strip().split("\n")
        decision_commits = [c for c in commits if "decisión" in c.lower()]
        self.assertGreaterEqual(len(decision_commits), 1)
    
    def test_resume_from_middle(self):
        """Test resuming from middle (RED done, GREEN pending)."""
        from scripts.tdd_runner import run_tdd_implementation
        
        # Manually mark RED as done in spec
        spec_path = self.repo / "docs" / "specs" / "issue-1.md"
        spec_content = spec_path.read_text()
        spec_content = spec_content.replace("- [ ] RED:", "- [x] RED:")
        spec_content = spec_content.replace("status: approved", "status: implementing")
        spec_path.write_text(spec_content)
        
        # Manually commit a RED test
        test_content = (
            "import unittest\n"
            "from src.calculator import add\n\n"
            "class TestCalculator(unittest.TestCase):\n"
            "    def test_add(self):\n"
            "        self.assertEqual(add(2, 3), 5)\n"
        )
        (self.repo / "tests" / "test_calculator.py").write_text(test_content)
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "test: suma básica (#1)"])
        
        # Now run TDD (should skip RED, do GREEN and REFACTOR)
        script = {
            "T1": {
                "green": {
                    "files": {
                        "src/calculator.py": "def add(a, b):\n    return a + b\n"
                    },
                    "exit": 0
                },
                "refactor": "SIN_REFACTOR"
            }
        }
        
        fake_coder = self._create_fake_coder(script)
        
        inputs = []
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
        
        # Should NOT have called coder for RED
        red_calls = [c for c in self.coder_calls if "red" in c["log_path"].lower()]
        self.assertEqual(len(red_calls), 0, "Should skip RED phase")
        
        # Should have called for GREEN
        green_calls = [c for c in self.coder_calls if "green" in c["log_path"].lower()]
        self.assertEqual(len(green_calls), 1)
    
    def test_dirty_tree_stops(self):
        """Test that dirty working tree stops the runner."""
        from scripts.tdd_runner import run_tdd_implementation
        
        # Make working tree dirty
        (self.repo / "src" / "calculator.py").write_text("# Uncommitted change\n")
        
        fake_coder = self._create_fake_coder({})
        
        outputs = []
        def mock_print(msg: str) -> None:
            outputs.append(msg)
        
        result = run_tdd_implementation(
            repo_root=str(self.repo),
            issue_num=1,
            coder=fake_coder,
            run_cmd=self._run,
            input_fn=input,
            print_fn=mock_print
        )
        
        self.assertFalse(result, "Should fail with dirty tree")
        
        # Check that error message mentions dirty tree
        output_text = " ".join(outputs)
        self.assertIn("working tree", output_text.lower())


class TestBuildCoderCmd(unittest.TestCase):
    """Test build_coder_cmd function with various env configurations."""
    
    def test_default_config(self):
        """Test default coder command construction."""
        from scripts.tdd_runner import build_coder_cmd
        
        env = {}
        cmd = build_coder_cmd("test prompt", env)
        
        # Should expand ~ and include default model
        self.assertIsInstance(cmd, list)
        self.assertTrue(any("oc" in part for part in cmd), f"Expected 'oc' in {cmd}")
        self.assertIn("run", cmd)
        self.assertIn("--model", cmd)
        self.assertIn("nous/anthropic/claude-sonnet-4.5", cmd)
        self.assertIn("test prompt", cmd)
    
    def test_custom_coder_cmd(self):
        """Test custom BACKLOG_CODER_CMD."""
        from scripts.tdd_runner import build_coder_cmd
        
        env = {"BACKLOG_CODER_CMD": "mycoder --verbose"}
        cmd = build_coder_cmd("prompt", env)
        
        self.assertIn("mycoder", cmd)
        self.assertIn("--verbose", cmd)
        self.assertIn("--model", cmd)
    
    def test_custom_model(self):
        """Test custom BACKLOG_CODER_MODEL."""
        from scripts.tdd_runner import build_coder_cmd
        
        env = {"BACKLOG_CODER_MODEL": "anthropic/claude-haiku-4.5"}
        cmd = build_coder_cmd("prompt", env)
        
        self.assertIn("--model", cmd)
        self.assertIn("anthropic/claude-haiku-4.5", cmd)
    
    def test_empty_model_omits_flag(self):
        """Test that empty BACKLOG_CODER_MODEL omits --model flag."""
        from scripts.tdd_runner import build_coder_cmd
        
        env = {"BACKLOG_CODER_MODEL": ""}
        cmd = build_coder_cmd("prompt", env)
        
        self.assertNotIn("--model", cmd)
        self.assertIn("prompt", cmd)
    
    def test_tilde_expansion(self):
        """Test that ~ is expanded in command."""
        from scripts.tdd_runner import build_coder_cmd
        
        env = {"BACKLOG_CODER_CMD": "~/bin/mycoder"}
        cmd = build_coder_cmd("prompt", env)
        
        # Should not contain ~
        self.assertFalse(any("~" in part for part in cmd), f"Tilde not expanded: {cmd}")


class TestRedPhaseWithSupportFiles(unittest.TestCase):
    """Test RED phase accepts test_support_files."""
    
    def setUp(self):
        """Create a temporary git repo for testing."""
        self.temp_dir = tempfile.mkdtemp(prefix="red_support_test_")
        self.repo = Path(self.temp_dir)
        
        # Initialize git repo
        self._run(["git", "init"])
        self._run(["git", "config", "user.email", "test@test.com"])
        self._run(["git", "config", "user.name", "Test User"])
        
        # Create minimal structure
        (self.repo / "tests").mkdir()
        (self.repo / "pkg").mkdir()
        (self.repo / "pkg" / "test").mkdir()
        (self.repo / "docs" / "specs").mkdir(parents=True)
        (self.repo / ".backlog" / "runs").mkdir(parents=True)
        
        # Create .gitignore
        (self.repo / ".gitignore").write_text("__pycache__/\n.backlog/\n")
        
        # Initial commit
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "initial commit"])
        
        # Create spec with test_support_files
        self._create_spec_with_support_files()
    
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
    
    def _create_spec_with_support_files(self):
        """Create a spec file with test_support_files."""
        spec_content = """---
issue: 1
status: approved
test_command: python3 -m unittest discover -s tests -v
---

# Spec

## Resumen

Test with support files

## Decisiones de diseño

| ID | Topic | Opciones | Elegida | Rationale |
|----|-------|----------|---------|-----------|
| D1 | Testing | pytest, unittest | unittest | Standard |

## Archivos afectados

- **create** `pkg/test/x.test.ts`: test file
- **create** `pkg/vitest.config.ts`: config

## Tareas

### T1: Implement feature

Feature with TS tests

**Tests:**
- `pkg/test/x.test.ts::test_feature`: assert x == y

**Archivos de soporte de tests:**
- `pkg/vitest.config.ts`

**Archivos de implementación:**
- `pkg/src/index.ts`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

## Fuera de alcance

_(ninguno)_

## Riesgos

_(ninguno)_
"""
        spec_path = self.repo / "docs" / "specs" / "issue-1.md"
        spec_path.write_text(spec_content)
        self._run(["git", "add", str(spec_path)])
        self._run(["git", "commit", "-m", "docs: spec (#1)"])
    
    def test_red_with_support_files_accepted(self):
        """Test RED phase accepts changes to test_support_files."""
        from scripts.tdd_runner import run_tdd_implementation
        
        # Pre-create the directory structure so git doesn't see it as new
        (self.repo / "pkg" / "test").mkdir(parents=True, exist_ok=True)
        (self.repo / "pkg" / "src").mkdir(parents=True, exist_ok=True)
        (self.repo / "pkg" / "test" / ".gitkeep").write_text("")
        (self.repo / "pkg" / "src" / ".gitkeep").write_text("")
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "create pkg structure"])
        
        # Fake coder that creates test file + support file
        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            if "red" in log_path.lower():
                # Create test file and support file
                test_file = self.repo / "pkg" / "test" / "x.test.ts"
                test_file.write_text("// test that fails\n")
                
                support_file = self.repo / "pkg" / "vitest.config.ts"
                support_file.write_text("// vitest config\n")
                
                return 0, "Tests written"
            return 1, "Not implemented"
        
        # Run RED phase only (will fail because tests won't actually run, but that's ok)
        # We just want to verify the file validation passes
        outputs = []
        def mock_print(msg: str) -> None:
            outputs.append(msg)
        
        # This will fail at test execution, but should not fail at file validation
        result = run_tdd_implementation(
            repo_root=str(self.repo),
            issue_num=1,
            coder=fake_coder,
            run_cmd=self._run,
            input_fn=lambda p: "abortar",
            print_fn=mock_print
        )
        
        # Check that the error is NOT about modifying non-test files
        output_text = " ".join(outputs)
        self.assertNotIn("archivos de producción en RED", output_text)
        # Should fail at test execution or user abort, not at validation
        self.assertFalse(result)
    
    def test_red_rejects_production_file_with_support_files(self):
        """Test RED phase that modifies production file AND support files (should reject production file only)."""
        from scripts.tdd_runner import run_tdd_implementation
        
        # Pre-create directory structure
        (self.repo / "pkg" / "test").mkdir(parents=True, exist_ok=True)
        (self.repo / "pkg" / "src").mkdir(parents=True, exist_ok=True)
        (self.repo / "pkg" / "test" / ".gitkeep").write_text("")
        (self.repo / "pkg" / "src" / ".gitkeep").write_text("")
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "create pkg structure"])
        
        # Fake coder that creates test, support file, AND production file
        run_cmd_calls = []
        
        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            if "red" in log_path.lower():
                test_file = self.repo / "pkg" / "test" / "x.test.ts"
                test_file.write_text("// test that fails\n")
                
                support_file = self.repo / "pkg" / "vitest.config.ts"
                support_file.write_text("// vitest config\n")
                
                # OOPS: also modified production
                prod_file = self.repo / "pkg" / "src" / "index.ts"
                prod_file.write_text("// production code\n")
                
                return 0, "Tests written"
            return 1, "Not implemented"
        
        def tracked_run_cmd(cmd, **kwargs):
            result = self._run(cmd, **kwargs)
            run_cmd_calls.append({"cmd": cmd, "returncode": result.returncode})
            return result
        
        outputs = []
        def mock_print(msg: str) -> None:
            outputs.append(msg)
        
        result = run_tdd_implementation(
            repo_root=str(self.repo),
            issue_num=1,
            coder=fake_coder,
            run_cmd=tracked_run_cmd,
            input_fn=lambda p: "abortar",
            print_fn=mock_print
        )
        
        self.assertFalse(result)
        
        # Check that rejection message mentions production files
        output_text = " ".join(outputs)
        self.assertIn("archivos de producción en RED", output_text)
        self.assertIn("pkg/src/index.ts", output_text)
        
        # Verify production file was reverted (either doesn't exist or has different content)
        prod_file = self.repo / "pkg" / "src" / "index.ts"
        if prod_file.exists():
            self.assertNotEqual(prod_file.read_text(), "// production code\n",
                              "Production file should have been reverted")
    
    def test_red_runs_test_command_after_validation(self):
        """Test that RED phase runs test command after file validation passes."""
        from scripts.tdd_runner import run_tdd_implementation
        
        # Pre-create directory structure
        (self.repo / "pkg" / "test").mkdir(parents=True, exist_ok=True)
        (self.repo / "pkg" / "test" / ".gitkeep").write_text("")
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "create pkg structure"])
        
        # Track commands executed
        commands_run = []
        
        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            if "red" in log_path.lower():
                test_file = self.repo / "pkg" / "test" / "x.test.ts"
                test_file.write_text("// test that fails\n")
                
                support_file = self.repo / "pkg" / "vitest.config.ts"
                support_file.write_text("// vitest config\n")
                
                return 0, "Tests written"
            return 1, "Not implemented"
        
        def tracked_run_cmd(cmd, **kwargs):
            commands_run.append(cmd)
            result = self._run(cmd, **kwargs)
            return result
        
        outputs = []
        def mock_print(msg: str) -> None:
            outputs.append(msg)
        
        result = run_tdd_implementation(
            repo_root=str(self.repo),
            issue_num=1,
            coder=fake_coder,
            run_cmd=tracked_run_cmd,
            input_fn=lambda p: "abortar",
            print_fn=mock_print
        )
        
        # Should fail because test command will fail, but file validation should pass
        self.assertFalse(result)
        
        # Verify test command was executed (after file validation)
        # The test_command from the spec is "python3 -m unittest discover -s tests -v"
        test_commands = [c for c in commands_run if "unittest" in " ".join(c)]
        self.assertGreater(len(test_commands), 0, "Test command should have been executed")
        
        # Verify NO rejection message about production files
        output_text = " ".join(outputs)
        self.assertNotIn("archivos de producción en RED", output_text)
    
    def test_green_accepts_support_file_modification(self):
        """Test GREEN phase accepts modification to test_support_files."""
        from scripts.tdd_runner import run_green_phase, build_test_cmd
        from pathlib import Path
        
        # Pre-create directory structure
        (self.repo / "pkg" / "test").mkdir(parents=True, exist_ok=True)
        (self.repo / "pkg" / "src").mkdir(parents=True, exist_ok=True)
        (self.repo / "pkg" / "test" / ".gitkeep").write_text("")
        (self.repo / "pkg" / "src" / ".gitkeep").write_text("")
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "create pkg structure"])
        
        # Create RED commit with test and support file
        test_file = self.repo / "pkg" / "test" / "x.test.ts"
        test_file.write_text("// test\n")
        support_file = self.repo / "pkg" / "vitest.config.ts"
        support_file.write_text("// config v1\n")
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "test: add test (#1)"])
        
        # Update spec to mark RED as done
        spec_path = self.repo / "docs" / "specs" / "issue-1.md"
        spec_content = spec_path.read_text()
        spec_content = spec_content.replace("- [ ] RED:", "- [x] RED:")
        spec_content = spec_content.replace(
            "test_command: python3 -m unittest discover -s tests -v",
            f"test_command: python3 -c \"import sys; from pathlib import Path; sys.exit(0 if (Path('{self.repo}') / 'pkg' / 'src' / 'index.ts').exists() else 1)\""
        )
        # Update task to include test_support_files
        spec_content = spec_content.replace(
            "**Archivos de implementación:**\n- `src/calculator.py`",
            "**Archivos de soporte de tests:**\n- `pkg/vitest.config.ts`\n\n**Archivos de implementación:**\n- `pkg/src/index.ts`"
        )
        spec_path.write_text(spec_content)
        self._run(["git", "add", str(spec_path)])
        self._run(["git", "commit", "-m", "docs: update spec"])
        
        # Parse spec
        from take_agent import parse_spec_markdown
        metadata, spec, progress = parse_spec_markdown(spec_path.read_text())
        task = spec["tasks"][0]
        # Override test files to match our setup
        task["tests"] = [{"file": "pkg/test/x.test.ts", "name": "test", "asserts": "x"}]
        task["test_support_files"] = ["pkg/vitest.config.ts"]
        
        test_cmd = build_test_cmd(metadata["test_command"])
        logs_dir = self.repo / ".backlog" / "runs" / "issue-1"
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            # GREEN modifies support file and implementation (NOT test file)
            support_file = self.repo / "pkg" / "vitest.config.ts"
            support_file.write_text("// config v2 updated\n")
            impl_file = self.repo / "pkg" / "src" / "index.ts"
            impl_file.write_text("// implementation\n")
            return 0, "Implementation done"
        
        outputs = []
        def mock_print(msg: str) -> None:
            outputs.append(msg)
        
        result = run_green_phase(
            repo_root=str(self.repo),
            issue_num=1,
            task=task,
            spec=spec,
            spec_path=spec_path,
            test_cmd=test_cmd,
            logs_dir=logs_dir,
            coder=fake_coder,
            run_cmd=self._run,
            input_fn=lambda p: "abortar",
            print_fn=mock_print
        )
        
        self.assertTrue(result, "GREEN should succeed")
        
        # Verify support file was modified
        support_file = self.repo / "pkg" / "vitest.config.ts"
        self.assertIn("v2 updated", support_file.read_text())
    
    def test_green_detects_test_file_modification(self):
        """Test GREEN phase detects and reverts test file modifications."""
        from scripts.tdd_runner import run_green_phase, build_test_cmd
        from pathlib import Path
        
        # Pre-create directory structure
        (self.repo / "pkg" / "test").mkdir(parents=True, exist_ok=True)
        (self.repo / "pkg" / "src").mkdir(parents=True, exist_ok=True)
        (self.repo / "pkg" / "test" / ".gitkeep").write_text("")
        (self.repo / "pkg" / "src" / ".gitkeep").write_text("")
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "create pkg structure"])
        
        red_test_content = "// RED test content\n"
        
        # Create RED commit with test and support file
        test_file = self.repo / "pkg" / "test" / "x.test.ts"
        test_file.write_text(red_test_content)
        support_file = self.repo / "pkg" / "vitest.config.ts"
        support_file.write_text("// config\n")
        self._run(["git", "add", "."])
        self._run(["git", "commit", "-m", "test: add test (#1)"])
        
        # Update spec
        spec_path = self.repo / "docs" / "specs" / "issue-1.md"
        spec_content = spec_path.read_text()
        spec_content = spec_content.replace("- [ ] RED:", "- [x] RED:")
        spec_content = spec_content.replace(
            "test_command: python3 -m unittest discover -s tests -v",
            f"test_command: python3 -c \"import sys; from pathlib import Path; sys.exit(0 if (Path('{self.repo}') / 'pkg' / 'src' / 'index.ts').exists() else 1)\""
        )
        spec_content = spec_content.replace(
            "**Archivos de implementación:**\n- `src/calculator.py`",
            "**Archivos de soporte de tests:**\n- `pkg/vitest.config.ts`\n\n**Archivos de implementación:**\n- `pkg/src/index.ts`"
        )
        spec_path.write_text(spec_content)
        self._run(["git", "add", str(spec_path)])
        self._run(["git", "commit", "-m", "docs: update spec"])
        
        # Parse spec
        from take_agent import parse_spec_markdown
        metadata, spec, progress = parse_spec_markdown(spec_path.read_text())
        task = spec["tasks"][0]
        task["tests"] = [{"file": "pkg/test/x.test.ts", "name": "test", "asserts": "x"}]
        task["test_support_files"] = ["pkg/vitest.config.ts"]
        
        test_cmd = build_test_cmd(metadata["test_command"])
        logs_dir = self.repo / ".backlog" / "runs" / "issue-1"
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            # GREEN modifies test file (WRONG!) and implementation
            test_file = self.repo / "pkg" / "test" / "x.test.ts"
            test_file.write_text("// GREEN weakened test\n")
            impl_file = self.repo / "pkg" / "src" / "index.ts"
            impl_file.write_text("// implementation\n")
            return 0, "Implementation done"
        
        outputs = []
        def mock_print(msg: str) -> None:
            outputs.append(msg)
        
        result = run_green_phase(
            repo_root=str(self.repo),
            issue_num=1,
            task=task,
            spec=spec,
            spec_path=spec_path,
            test_cmd=test_cmd,
            logs_dir=logs_dir,
            coder=fake_coder,
            run_cmd=self._run,
            input_fn=lambda p: "abortar",
            print_fn=mock_print
        )
        
        self.assertFalse(result, "Should fail when GREEN modifies tests")
        
        # Verify error message about test modification
        output_text = " ".join(outputs).lower()
        self.assertIn("archivos de test fueron modificados", output_text)
        
        # Verify test file was restored to RED version
        test_file = self.repo / "pkg" / "test" / "x.test.ts"
        self.assertEqual(test_file.read_text(), red_test_content, "Test file should be restored to RED version")


class TestTakeWithDraftSpec(unittest.TestCase):
    """Test cmd_take with draft spec and session resume."""
    
    def setUp(self):
        """Create a temporary directory with mocked repo."""
        self.temp_dir = tempfile.mkdtemp(prefix="take_test_")
        self.repo = Path(self.temp_dir)
        
        # Create minimal structure
        (self.repo / "docs" / "specs").mkdir(parents=True)
        (self.repo / ".backlog" / "sessions").mkdir(parents=True)
    
    def tearDown(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_take_with_draft_and_session_resumes(self):
        """Test that take with draft spec and session file resumes from that session."""
        from unittest.mock import Mock, patch, MagicMock
        import scripts.backlog as backlog_module
        import scripts.take_agent as take_agent_module
        import scripts.agent_core as agent_core_module
        
        issue_num = 42
        
        # Create draft spec
        spec_path = self.repo / "docs" / "specs" / f"issue-{issue_num}.md"
        spec_path.write_text("""---
issue: 42
status: draft
test_command: pytest
---

# Draft spec

## Resumen

Draft

## Decisiones de diseño

| ID | Topic | Opciones | Elegida | Rationale |
|----|-------|----------|---------|-----------|
| D1 | Test | A, B | A | Simple |

## Archivos afectados

## Tareas

## Fuera de alcance

## Riesgos
""")
        
        # Create session file for issue 42
        session_id = "20260929_120000"
        session_file = self.repo / ".backlog" / "sessions" / f"{session_id}.json"
        session_data = {
            "issue": issue_num,
            "messages": [
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "initial request"},
                {"role": "assistant", "content": "draft response"}
            ],
            "timestamp": "2026-09-29T12:00:00"
        }
        session_file.write_text(json.dumps(session_data, indent=2))
        
        # Mock external dependencies
        with patch.object(take_agent_module, 'load_issue') as mock_load_issue, \
             patch.object(take_agent_module, 'run_design_phase') as mock_run_design, \
             patch.object(agent_core_module, 'get_llm_config') as mock_get_llm_config, \
             patch.object(take_agent_module, 'review_and_approve') as mock_review:
            
            # Setup mocks
            mock_load_issue.return_value = {
                "number": issue_num,
                "title": "Test Issue",
                "body": "Body",
                "labels": [{"name": "type:feat"}]
            }
            
            mock_get_llm_config.return_value = ("http://example.com", "key", "model", 16000, 300)
            
            # Mock run_design_phase to check it receives existing_messages
            final_spec = {
                "summary": "Test",
                "decisions": [{"id": "D1", "topic": "T", "options": ["A"], "chosen": "A", "rationale": "R"}],
                "files": [],
                "test_command": "pytest",
                "tasks": [],
                "out_of_scope": [],
                "risks": []
            }
            mock_run_design.return_value = (final_spec, [], session_id)
            
            # Mock review_and_approve to return draft status (so it doesn't try to run TDD)
            mock_review.return_value = (final_spec, "draft")
            
            # Create a minimal args object
            args = MagicMock()
            args.issue = issue_num
            args.plan_only = False
            args.no_plan = False
            
            # Temporarily change to temp dir
            import os
            original_cwd = os.getcwd()
            try:
                os.chdir(self.repo)
                
                # Call cmd_take (will use patched functions)
                # Note: We need to patch subprocess/git calls too
                with patch('subprocess.run') as mock_run:
                    mock_run.return_value = MagicMock(
                        returncode=0,
                        stdout="",
                        stderr=""
                    )
                    
                    # We can't easily test the full cmd_take without mocking everything,
                    # but we can test the specific logic by directly calling the relevant parts
                    # Instead, let's test find_session_for_issue and that run_design_phase
                    # would be called with the right arguments
                    
                    # Test find_session_for_issue
                    found_session = agent_core_module.find_session_for_issue(str(self.repo), issue_num)
                    self.assertIsNotNone(found_session, "Should find session for issue")
                    
                    # Load and verify
                    messages, loaded_session_id = agent_core_module.load_session(found_session)
                    self.assertEqual(len(messages), 3)
                    self.assertEqual(messages[0]["role"], "system")
                    self.assertEqual(messages[1]["content"], "initial request")
                    self.assertEqual(loaded_session_id, session_id)
            finally:
                os.chdir(original_cwd)
    
    def test_take_with_draft_no_session_starts_fresh(self):
        """Test that take with draft spec but no session starts fresh interview."""
        from unittest.mock import patch
        import scripts.agent_core as agent_core_module
        
        issue_num = 99
        
        # Create draft spec
        spec_path = self.repo / "docs" / "specs" / f"issue-{issue_num}.md"
        spec_path.write_text("""---
issue: 99
status: draft
test_command: pytest
---

# Draft
""")
        
        # Create a session for a DIFFERENT issue
        other_session = self.repo / ".backlog" / "sessions" / "20260929_100000.json"
        other_session.write_text(json.dumps({
            "issue": 88,
            "messages": [{"role": "user", "content": "other"}],
            "timestamp": "2026-09-29T10:00:00"
        }))
        
        # Test find_session_for_issue returns None
        found = agent_core_module.find_session_for_issue(str(self.repo), issue_num)
        self.assertIsNone(found, "Should not find session for issue 99")


if __name__ == "__main__":
    unittest.main()

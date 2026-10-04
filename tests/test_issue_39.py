#!/usr/bin/env python3
"""
Tests for issue #39: _escape_cell and _split_row functions for deterministic round-trip.
"""
import sys
import tempfile
import unittest
from pathlib import Path

# Import modules to test
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "scripts"))
import take_agent
import tdd_runner


class TestEscapeCell(unittest.TestCase):
    """Test _escape_cell function."""
    
    def test_escape_cell_plain_text(self) -> None:
        """Test texto sin caracteres especiales sale identico a la entrada."""
        result = take_agent._escape_cell("hello world")
        self.assertEqual(result, "hello world")
    
    def test_escape_cell_single_backslash_becomes_double(self) -> None:
        """Test una barra invertida sola se convierte en dos barras invertidas consecutivas."""
        result = take_agent._escape_cell("\\")
        self.assertEqual(result, "\\\\")
    
    def test_escape_cell_pipe_becomes_backslash_pipe(self) -> None:
        """Test un pipe literal se convierte en barra-invertida seguida de pipe."""
        result = take_agent._escape_cell("|")
        self.assertEqual(result, "\\|")
    
    def test_escape_cell_newline_becomes_space(self) -> None:
        """Test salto de linea real (chr 10) se convierte en un espacio."""
        result = take_agent._escape_cell("hello\nworld")
        self.assertEqual(result, "hello world")
    
    def test_escape_cell_crlf_becomes_single_space(self) -> None:
        """Test CR seguido de LF se convierte en un solo espacio, no dos."""
        result = take_agent._escape_cell("hello\r\nworld")
        self.assertEqual(result, "hello world")
    
    def test_escape_cell_cr_alone_becomes_space(self) -> None:
        """Test CR solitario (chr 13 sin LF) se convierte en un espacio."""
        result = take_agent._escape_cell("hello\rworld")
        self.assertEqual(result, "hello world")
    
    def test_escape_cell_order_backslash_before_pipe(self) -> None:
        """Test texto con barra seguida de pipe: la barra se duplica primero y el pipe se escapa despues."""
        result = take_agent._escape_cell("\\|")
        self.assertEqual(result, "\\\\\\|")
        self.assertEqual(len(result), 4)


class TestSplitRow(unittest.TestCase):
    """Test _split_row function."""
    
    def test_split_row_simple_three_cells(self) -> None:
        """Test _split_row de una fila con tres celdas simples separadas por pipes."""
        result = take_agent._split_row("| a | b | c |")
        self.assertEqual(result, ["a", "b", "c"])
    
    def test_split_row_escaped_pipe_not_split(self) -> None:
        """Test barra-pipe dentro de una celda no se trata como separador."""
        result = take_agent._split_row("| a | b\\|c | d |")
        self.assertEqual(result, ["a", "b|c", "d"])
    
    def test_split_row_double_backslash_decoded_to_single(self) -> None:
        """Test doble barra invertida en la fila se decodifica a una sola barra invertida."""
        result = take_agent._split_row("| a | b\\\\c | d |")
        self.assertEqual(result, ["a", "b\\c", "d"])
    
    def test_split_row_backslash_followed_by_w_conserved_literal(self) -> None:
        """Test barra invertida seguida de la letra w: la celda devuelta contiene barra-w intactos."""
        result = take_agent._split_row("| a | b\\wc | d |")
        self.assertEqual(result, ["a", "b\\wc", "d"])
    
    def test_split_row_trailing_backslash_before_pipe_separator_conserved(self) -> None:
        """Test celda cuyo ultimo caracter es una barra invertida pegada al pipe separador."""
        result = take_agent._split_row("| a | b\\ | c |")
        self.assertEqual(result, ["a", "b\\", "c"])


class TestRoundtrip(unittest.TestCase):
    """Test round-trip de _escape_cell + _split_row."""
    
    def test_split_row_roundtrip_all_matrix_texts(self) -> None:
        """Test round-trip de la matriz de 15 casos."""
        matrix = [
            "plain text",
            "\\",
            "|",
            "\\|",
            "\\d",
            "\\1",
            "\\g<x>",
            "\\\\",
            "\\n",
            "\\",  # trailing backslash
            "$",
            "$$",
            "a|b",
            "hello\nworld",
            "hello\r\nworld",
        ]
        
        for text in matrix:
            escaped = take_agent._escape_cell(text)
            row = f"| {escaped} |"
            result = take_agent._split_row(row)
            
            # Newlines should be converted to space (D1 contract)
            expected = text.replace("\n", " ").replace("\r\n", " ").replace("\r", " ")
            
            self.assertEqual(len(result), 1, f"Expected 1 cell for text {text!r}")
            self.assertEqual(result[0], expected, f"Round-trip failed for text {text!r}")


class TestAppendDecisionRoundtrip(unittest.TestCase):
    """Test append_decision_to_spec round-trip with parse_spec_markdown."""
    
    def setUp(self) -> None:
        """Create temp directory for test specs."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_issue_39_")
        self.repo_root = Path(self.temp_dir)
    
    def tearDown(self) -> None:
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_minimal_spec(self) -> Path:
        """Create minimal spec file with one decision."""
        spec_content = """---
issue: 999
status: implementing
test_command: python3 -m unittest
---

# Spec de implementación: Test spec

## Resumen

Test spec for round-trip

## Decisiones de diseño

| ID | Topic | Opciones | Elegida | Rationale |
|----|-------|----------|---------|-----------|
| D1 | Initial decision | A | A | Initial rationale |

## Archivos afectados

- **modify** `test.py`: Test file

## Tareas

### T1: Test task

Test task description

**Tests:**
- `tests/test.py::test_one`: Test one

**Archivos de implementación:**
- `test.py`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

## Fuera de alcance

_(ninguno)_

## Riesgos

_(ninguno)_
"""
        spec_path = self.repo_root / "spec.md"
        spec_path.write_text(spec_content)
        return spec_path
    
    def _run_cmd_mock(self, cmd: list[str], cwd: str = None, timeout: int = None):
        """Mock run_cmd for tests."""
        import subprocess
        class Result:
            returncode = 0
            stdout = ""
            stderr = ""
        return Result()
    
    def test_append_plain_text_roundtrip(self) -> None:
        """Test texto sin caracteres especiales: chosen parseado == chosen original."""
        spec_path = self._create_minimal_spec()
        
        tdd_runner.append_decision_to_spec(
            str(spec_path),
            "Plain topic",
            "plain chosen text",
            self._run_cmd_mock
        )
        
        content = spec_path.read_text()
        metadata, spec, progress = take_agent.parse_spec_markdown(content)
        
        self.assertEqual(len(spec["decisions"]), 2)
        self.assertEqual(spec["decisions"][1]["chosen"], "plain chosen text")
    
    def test_append_backslash_w_regex_pattern_no_exception(self) -> None:
        """Test texto con barra-w en patron regex: no lanza excepcion."""
        spec_path = self._create_minimal_spec()
        
        # Should not raise exception
        tdd_runner.append_decision_to_spec(
            str(spec_path),
            "Regex topic",
            "pattern \\w+",
            self._run_cmd_mock
        )
        
        content = spec_path.read_text()
        metadata, spec, progress = take_agent.parse_spec_markdown(content)
        
        self.assertEqual(len(spec["decisions"]), 2)
        self.assertIn("\\w", spec["decisions"][1]["chosen"])
    
    def test_append_backslash_d_no_exception(self) -> None:
        """Test texto con barra-d aislado: no lanza re.error."""
        spec_path = self._create_minimal_spec()
        
        tdd_runner.append_decision_to_spec(
            str(spec_path),
            "Digit topic",
            "pattern \\d",
            self._run_cmd_mock
        )
        
        content = spec_path.read_text()
        metadata, spec, progress = take_agent.parse_spec_markdown(content)
        
        self.assertEqual(len(spec["decisions"]), 2)
        self.assertEqual(spec["decisions"][1]["chosen"], "pattern \\d")
    
    def test_append_backslash_1_not_replaced_by_group(self) -> None:
        """Test texto con barra-1: chosen parseado es identico al texto original."""
        spec_path = self._create_minimal_spec()
        
        tdd_runner.append_decision_to_spec(
            str(spec_path),
            "Group ref topic",
            "text \\1 ref",
            self._run_cmd_mock
        )
        
        content = spec_path.read_text()
        metadata, spec, progress = take_agent.parse_spec_markdown(content)
        
        self.assertEqual(len(spec["decisions"]), 2)
        self.assertEqual(spec["decisions"][1]["chosen"], "text \\1 ref")
    
    def test_append_backslash_g_group_ref_no_exception(self) -> None:
        """Test texto con barra-g-menor-x-mayor: no lanza IndexError ni re.error."""
        spec_path = self._create_minimal_spec()
        
        tdd_runner.append_decision_to_spec(
            str(spec_path),
            "Named group topic",
            "text \\g<x> ref",
            self._run_cmd_mock
        )
        
        content = spec_path.read_text()
        metadata, spec, progress = take_agent.parse_spec_markdown(content)
        
        self.assertEqual(len(spec["decisions"]), 2)
        self.assertEqual(spec["decisions"][1]["chosen"], "text \\g<x> ref")
    
    def test_append_double_backslash_not_collapsed(self) -> None:
        """Test texto con dos barras invertidas consecutivas: chosen parseado contiene dos barras."""
        spec_path = self._create_minimal_spec()
        
        tdd_runner.append_decision_to_spec(
            str(spec_path),
            "Double backslash topic",
            "text \\\\ here",
            self._run_cmd_mock
        )
        
        content = spec_path.read_text()
        metadata, spec, progress = take_agent.parse_spec_markdown(content)
        
        self.assertEqual(len(spec["decisions"]), 2)
        self.assertEqual(spec["decisions"][1]["chosen"], "text \\\\ here")
    
    def test_append_backslash_n_two_chars_not_converted(self) -> None:
        """Test texto con barra y n como dos caracteres literales: round-trip exacto."""
        spec_path = self._create_minimal_spec()
        
        tdd_runner.append_decision_to_spec(
            str(spec_path),
            "Backslash n topic",
            "text \\n here",
            self._run_cmd_mock
        )
        
        content = spec_path.read_text()
        metadata, spec, progress = take_agent.parse_spec_markdown(content)
        
        self.assertEqual(len(spec["decisions"]), 2)
        self.assertEqual(spec["decisions"][1]["chosen"], "text \\n here")
    
    def test_append_trailing_backslash_roundtrip(self) -> None:
        """Test texto que termina en barra invertida: round-trip exacto."""
        spec_path = self._create_minimal_spec()
        
        tdd_runner.append_decision_to_spec(
            str(spec_path),
            "Trailing backslash topic",
            "text ends with \\",
            self._run_cmd_mock
        )
        
        content = spec_path.read_text()
        metadata, spec, progress = take_agent.parse_spec_markdown(content)
        
        self.assertEqual(len(spec["decisions"]), 2)
        self.assertEqual(spec["decisions"][1]["chosen"], "text ends with \\")
    
    def test_append_dollar_signs_not_interpreted(self) -> None:
        """Test texto con signo pesos: chosen parseado identico al original."""
        spec_path = self._create_minimal_spec()
        
        tdd_runner.append_decision_to_spec(
            str(spec_path),
            "Dollar signs topic",
            "price $10 and $$20",
            self._run_cmd_mock
        )
        
        content = spec_path.read_text()
        metadata, spec, progress = take_agent.parse_spec_markdown(content)
        
        self.assertEqual(len(spec["decisions"]), 2)
        self.assertEqual(spec["decisions"][1]["chosen"], "price $10 and $$20")
    
    def test_append_pipe_literal_roundtrip(self) -> None:
        """Test texto con pipe literal entre dos letras: chosen parseado contiene el pipe literal."""
        spec_path = self._create_minimal_spec()
        
        tdd_runner.append_decision_to_spec(
            str(spec_path),
            "Pipe literal topic",
            "a|b",
            self._run_cmd_mock
        )
        
        content = spec_path.read_text()
        metadata, spec, progress = take_agent.parse_spec_markdown(content)
        
        self.assertEqual(len(spec["decisions"]), 2)
        self.assertEqual(spec["decisions"][1]["chosen"], "a|b")
    
    def test_append_real_newline_becomes_space(self) -> None:
        """Test texto con salto de linea real: chosen parseado tiene un espacio en lugar del salto."""
        spec_path = self._create_minimal_spec()
        
        tdd_runner.append_decision_to_spec(
            str(spec_path),
            "Newline topic",
            "hello\nworld",
            self._run_cmd_mock
        )
        
        content = spec_path.read_text()
        metadata, spec, progress = take_agent.parse_spec_markdown(content)
        
        self.assertEqual(len(spec["decisions"]), 2)
        self.assertEqual(spec["decisions"][1]["chosen"], "hello world")
    
    def test_append_double_newline_with_fake_section_header(self) -> None:
        """Test texto con doble salto de linea seguido de texto: no fabrica una seccion falsa."""
        spec_path = self._create_minimal_spec()
        
        tdd_runner.append_decision_to_spec(
            str(spec_path),
            "Double newline topic",
            "text\n\n## Fake header",
            self._run_cmd_mock
        )
        
        content = spec_path.read_text()
        metadata, spec, progress = take_agent.parse_spec_markdown(content)
        
        self.assertEqual(len(spec["decisions"]), 2)
        # First decision should remain intact
        self.assertEqual(spec["decisions"][0]["chosen"], "A")
    
    def test_append_trailing_backslash_adjacent_pipe_separator_roundtrip(self) -> None:
        """Test texto cuya representacion en la celda termina en barra invertida pegada al pipe."""
        spec_path = self._create_minimal_spec()
        
        tdd_runner.append_decision_to_spec(
            str(spec_path),
            "Trailing backslash adjacent topic",
            "ends\\",
            self._run_cmd_mock
        )
        
        content = spec_path.read_text()
        metadata, spec, progress = take_agent.parse_spec_markdown(content)
        
        self.assertEqual(len(spec["decisions"]), 2)
        self.assertEqual(spec["decisions"][1]["chosen"], "ends\\")
    
    def test_append_user_written_backslash_pipe_roundtrip(self) -> None:
        """Test texto con barra-pipe escrito literalmente por el usuario: round-trip exacto."""
        spec_path = self._create_minimal_spec()
        
        tdd_runner.append_decision_to_spec(
            str(spec_path),
            "Backslash pipe topic",
            "text \\| here",
            self._run_cmd_mock
        )
        
        content = spec_path.read_text()
        metadata, spec, progress = take_agent.parse_spec_markdown(content)
        
        self.assertEqual(len(spec["decisions"]), 2)
        self.assertEqual(spec["decisions"][1]["chosen"], "text | here")
    
    def test_append_two_consecutive_second_with_backslashes(self) -> None:
        """Test dos llamadas consecutivas a append_decision_to_spec, la segunda con barras."""
        spec_path = self._create_minimal_spec()
        
        tdd_runner.append_decision_to_spec(
            str(spec_path),
            "First topic",
            "first text",
            self._run_cmd_mock
        )
        
        tdd_runner.append_decision_to_spec(
            str(spec_path),
            "Second topic",
            "second \\w text",
            self._run_cmd_mock
        )
        
        content = spec_path.read_text()
        metadata, spec, progress = take_agent.parse_spec_markdown(content)
        
        self.assertEqual(len(spec["decisions"]), 3)
        self.assertEqual(spec["decisions"][0]["chosen"], "A")
        self.assertEqual(spec["decisions"][1]["chosen"], "first text")
        self.assertEqual(spec["decisions"][2]["chosen"], "second \\w text")


class TestNoRegression(unittest.TestCase):
    """Test no-regression sobre specs del repo."""
    
    def test_issue37_spec_counts_unchanged(self) -> None:
        """Test docs/specs/issue-37.md parsea sin excepcion con conteos fijos."""
        spec_path = repo_root / "docs" / "specs" / "issue-37.md"
        
        if not spec_path.exists():
            self.skipTest("issue-37.md not found")
        
        content = spec_path.read_text()
        metadata, spec, progress = take_agent.parse_spec_markdown(content)
        
        # Fixed counts from issue-37.md
        self.assertEqual(len(spec["decisions"]), 13)
        self.assertEqual(len(spec["tasks"]), 5)
    
    def test_issue37_d3_cell_not_split_at_escaped_pipe(self) -> None:
        """Test decisions[2]['chosen'] (D3) contiene pipe literal desescapado sin barra."""
        spec_path = repo_root / "docs" / "specs" / "issue-37.md"
        
        if not spec_path.exists():
            self.skipTest("issue-37.md not found")
        
        content = spec_path.read_text()
        metadata, spec, progress = take_agent.parse_spec_markdown(content)
        
        # D3 chosen should contain the full text with pipe literal
        chosen = spec["decisions"][2]["chosen"]
        self.assertIn("rejected: str | None = None, warnings: tuple[str, ...] = ()", chosen)
        
        # Rationale should NOT start with "None = None" (symptom of pipe split)
        rationale = spec["decisions"][2]["rationale"]
        self.assertFalse(rationale.startswith("None = None"))
    
    def test_all_repo_specs_parse_without_exception(self) -> None:
        """Test todos los archivos en docs/specs/*.md parsean sin excepcion."""
        specs_dir = repo_root / "docs" / "specs"
        
        if not specs_dir.exists():
            self.skipTest("docs/specs not found")
        
        spec_files = list(specs_dir.glob("*.md"))
        self.assertGreater(len(spec_files), 0, "No spec files found")
        
        specs_with_trailing_backslash = []
        
        for spec_file in spec_files:
            content = spec_file.read_text()
            
            # Should not raise exception
            metadata, spec, progress = take_agent.parse_spec_markdown(content)
            
            # Check invariant: no chosen field should end with backslash
            for i, decision in enumerate(spec["decisions"]):
                chosen = decision["chosen"]
                if chosen.endswith("\\"):
                    specs_with_trailing_backslash.append(
                        f"{spec_file.name}: decision {i} ({decision['id']}) chosen ends with backslash"
                    )
        
        if specs_with_trailing_backslash:
            self.fail(
                "Specs with chosen ending in backslash (pipe split symptom):\n" +
                "\n".join(specs_with_trailing_backslash)
            )


if __name__ == "__main__":
    unittest.main()

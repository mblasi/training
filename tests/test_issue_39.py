#!/usr/bin/env python3
"""
Tests for issue #39: Corregir append_decision_to_spec con lambda en re.sub (defecto A)
y agregar _escape_cell/_split_row (defecto B) para round-trip exacto.
"""
import sys
import tempfile
import unittest
from pathlib import Path

# Import take_agent and tdd_runner modules
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "scripts"))
from take_agent import _escape_cell, _split_row, parse_spec_markdown
from tdd_runner import append_decision_to_spec


class TestEscapeCell(unittest.TestCase):
    """Tests for _escape_cell function."""
    
    def test_escape_cell_plain_text(self):
        """texto sin caracteres especiales sale identico a la entrada"""
        result = _escape_cell("hello world")
        self.assertEqual(result, "hello world")
    
    def test_escape_cell_single_backslash_becomes_double(self):
        """una barra invertida sola se convierte en dos barras invertidas consecutivas"""
        result = _escape_cell("foo\\bar")
        self.assertEqual(result, "foo\\\\bar")
    
    def test_escape_cell_pipe_becomes_backslash_pipe(self):
        """un pipe literal se convierte en barra-invertida seguida de pipe"""
        result = _escape_cell("foo|bar")
        self.assertEqual(result, "foo\\|bar")
    
    def test_escape_cell_newline_becomes_space(self):
        """salto de linea real (chr 10) se convierte en un espacio"""
        result = _escape_cell("foo\nbar")
        self.assertEqual(result, "foo bar")
    
    def test_escape_cell_crlf_becomes_single_space(self):
        """CR seguido de LF se convierte en un solo espacio, no dos"""
        result = _escape_cell("foo\r\nbar")
        self.assertEqual(result, "foo bar")
    
    def test_escape_cell_cr_alone_becomes_space(self):
        """CR solitario (chr 13 sin LF) se convierte en un espacio"""
        result = _escape_cell("foo\rbar")
        self.assertEqual(result, "foo bar")
    
    def test_escape_cell_order_backslash_before_pipe(self):
        """texto con barra seguida de pipe: la barra se duplica primero y el pipe se escapa despues;
        resultado final tiene cuatro caracteres: dos barras seguidas de barra-pipe"""
        result = _escape_cell("\\|")
        self.assertEqual(result, "\\\\\\|")


class TestSplitRow(unittest.TestCase):
    """Tests for _split_row function."""
    
    def test_split_row_simple_three_cells(self):
        """_split_row de una fila con tres celdas simples separadas por pipes
        devuelve lista de tres strings sin pipes de borde"""
        result = _split_row("| foo | bar | baz |")
        self.assertEqual(result, ["foo", "bar", "baz"])
    
    def test_split_row_escaped_pipe_not_split(self):
        """barra-pipe dentro de una celda no se trata como separador;
        la celda devuelta contiene un pipe literal desescapado"""
        result = _split_row("| foo | bar\\|baz | qux |")
        self.assertEqual(result, ["foo", "bar|baz", "qux"])
    
    def test_split_row_double_backslash_decoded_to_single(self):
        """doble barra invertida en la fila se decodifica a una sola barra invertida
        en la celda devuelta"""
        result = _split_row("| foo\\\\bar |")
        self.assertEqual(result, ["foo\\bar"])
    
    def test_split_row_backslash_followed_by_w_conserved_literal(self):
        """barra invertida seguida de la letra w (no es secuencia de escape reconocida):
        la celda devuelta contiene barra-w intactos, la barra se conserva literal sin ser consumida"""
        result = _split_row("| foo\\wbar |")
        self.assertEqual(result, ["foo\\wbar"])
    
    def test_split_row_trailing_backslash_before_pipe_separator_conserved(self):
        """celda cuyo ultimo caracter es una barra invertida pegada al pipe separador:
        la barra solitaria no escapa al pipe; la celda devuelta termina en barra invertida
        y el pipe actua como separador de columnas"""
        result = _split_row("| foo\\ | bar |")
        self.assertEqual(result, ["foo\\", "bar"])
    
    def test_split_row_roundtrip_all_matrix_texts(self):
        """para cada texto de la matriz de 15 casos, _split_row aplicada sobre la fila
        '| ' + _escape_cell(texto) + ' |' devuelve el texto con saltos de linea convertidos
        a espacio y todos los demas caracteres identicos al original"""
        
        def normalize_newlines(text: str) -> str:
            """Normalize newlines: treat CRLF as single newline, then convert all to space."""
            # First replace CRLF with a single placeholder
            text = text.replace("\r\n", "\n")
            # Then replace remaining CR with newline
            text = text.replace("\r", "\n")
            # Finally replace all newlines with space
            return text.replace("\n", " ")
        
        matrix_texts = [
            "plain text",
            "backslash: \\",
            "pipe: |",
            "dollar: $",
            "double dollar: $$",
            "backslash-w: \\w",
            "backslash-d: \\d",
            "backslash-1: \\1",
            "backslash-g: \\g<x>",
            "double backslash: \\\\",
            "backslash-n: \\n",
            "newline: \n",
            "double newline: \n\n",
            "crlf: \r\n",
            "cr: \r",
        ]
        
        for original in matrix_texts:
            with self.subTest(text=repr(original)):
                escaped = _escape_cell(original)
                row = f"| {escaped} |"
                result = _split_row(row)
                expected = normalize_newlines(original)
                self.assertEqual(len(result), 1, f"Expected 1 cell, got {len(result)}")
                self.assertEqual(result[0], expected)


class TestAppendDecisionToSpec(unittest.TestCase):
    """Tests for append_decision_to_spec function."""
    
    def setUp(self):
        """Create temporary spec file for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.spec_path = Path(self.temp_dir) / "test-spec.md"
        
        # Minimal spec with one decision
        self.spec_content = """---
issue: 99
status: approved
test_command: python3 -m unittest discover -s tests -v
---

## Resumen

Test spec for append decision.

## Decisiones de diseño

| ID | Tema | Opciones | Elegida | Justificación |
|----|------|----------|---------|---------------|
| D1 | Initial | Option A | Option A | First decision |

## Archivos afectados

- `test.py`

## Tareas

### T1: Test task

Test task description.

**Tests:**

- `tests/test.py::test_one`: assert something

**Archivos de implementación:**

- `src/test.py`

**Progreso:**

- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

## Fuera de alcance

None.

## Riesgos

None.
"""
        self.spec_path.write_text(self.spec_content, encoding="utf-8")
    
    def tearDown(self):
        """Clean up temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def _parse_and_count(self, spec_path: Path) -> tuple[int, int, str]:
        """Parse spec and return (num_decisions, num_tasks, last_chosen)."""
        content = spec_path.read_text(encoding="utf-8")
        metadata, spec, progress = parse_spec_markdown(content)
        num_decisions = len(spec["decisions"])
        num_tasks = len(spec["tasks"])
        last_chosen = spec["decisions"][-1]["chosen"] if spec["decisions"] else ""
        return num_decisions, num_tasks, last_chosen
    
    def test_append_plain_text_roundtrip(self):
        """texto sin caracteres especiales: chosen parseado == chosen original,
        num decisiones == 2, num tareas sin cambio, archivo parseable sin excepcion"""
        topic = "Plain topic"
        chosen = "plain text option"
        
        append_decision_to_spec(
            str(self.spec_path),
            topic,
            chosen,
            lambda cmd: None
        )
        
        num_decisions, num_tasks, last_chosen = self._parse_and_count(self.spec_path)
        self.assertEqual(num_decisions, 2)
        self.assertEqual(num_tasks, 1)
        self.assertEqual(last_chosen, chosen)
    
    def test_append_backslash_w_regex_pattern_no_exception(self):
        """texto con barra-w en patron regex (caso del issue 37): no lanza excepcion,
        chosen parseado contiene barra-w, num decisiones == 2"""
        topic = "Regex pattern"
        chosen = "use pattern with \\w+ matcher"
        
        append_decision_to_spec(
            str(self.spec_path),
            topic,
            chosen,
            lambda cmd: None
        )
        
        num_decisions, num_tasks, last_chosen = self._parse_and_count(self.spec_path)
        self.assertEqual(num_decisions, 2)
        self.assertIn("\\w", last_chosen)
    
    def test_append_backslash_d_no_exception(self):
        """texto con barra-d aislado: no lanza re.error, round-trip exacto, num decisiones == 2"""
        topic = "Digit pattern"
        chosen = "validate with \\d check"
        
        append_decision_to_spec(
            str(self.spec_path),
            topic,
            chosen,
            lambda cmd: None
        )
        
        num_decisions, num_tasks, last_chosen = self._parse_and_count(self.spec_path)
        self.assertEqual(num_decisions, 2)
        self.assertEqual(last_chosen, chosen)
    
    def test_append_backslash_1_not_replaced_by_group(self):
        """texto con barra-1: chosen parseado es identico al texto original,
        no el contenido del grupo capturado del regex"""
        topic = "Group ref"
        chosen = "replace with \\1 placeholder"
        
        append_decision_to_spec(
            str(self.spec_path),
            topic,
            chosen,
            lambda cmd: None
        )
        
        num_decisions, num_tasks, last_chosen = self._parse_and_count(self.spec_path)
        self.assertEqual(num_decisions, 2)
        self.assertEqual(last_chosen, chosen)
        # Should NOT be replaced with captured group content (table header)
        self.assertNotIn("Tema", last_chosen)
        self.assertNotIn("Opciones", last_chosen)
    
    def test_append_backslash_g_group_ref_no_exception(self):
        """texto con barra-g-menor-x-mayor: no lanza IndexError ni re.error,
        round-trip exacto, num decisiones == 2"""
        topic = "Named group"
        chosen = "use \\g<name> reference"
        
        append_decision_to_spec(
            str(self.spec_path),
            topic,
            chosen,
            lambda cmd: None
        )
        
        num_decisions, num_tasks, last_chosen = self._parse_and_count(self.spec_path)
        self.assertEqual(num_decisions, 2)
        self.assertEqual(last_chosen, chosen)
    
    def test_append_double_backslash_not_collapsed(self):
        """texto con dos barras invertidas consecutivas: chosen parseado contiene dos barras,
        no colapsa a una sola"""
        topic = "Double backslash"
        chosen = "path is C:\\\\Users\\\\name"
        
        append_decision_to_spec(
            str(self.spec_path),
            topic,
            chosen,
            lambda cmd: None
        )
        
        num_decisions, num_tasks, last_chosen = self._parse_and_count(self.spec_path)
        self.assertEqual(num_decisions, 2)
        self.assertIn("\\\\", last_chosen)
    
    def test_append_backslash_n_two_chars_not_converted(self):
        """texto con barra y n como dos caracteres literales separados (no un salto de linea real):
        round-trip exacto, chosen parseado contiene barra-n como dos caracteres distintos"""
        topic = "Literal backslash n"
        chosen = "newline char is \\n in code"
        
        append_decision_to_spec(
            str(self.spec_path),
            topic,
            chosen,
            lambda cmd: None
        )
        
        num_decisions, num_tasks, last_chosen = self._parse_and_count(self.spec_path)
        self.assertEqual(num_decisions, 2)
        self.assertEqual(last_chosen, chosen)
    
    def test_append_trailing_backslash_roundtrip(self):
        """texto que termina en barra invertida: round-trip exacto, num decisiones == 2,
        archivo parseable"""
        topic = "Trailing backslash"
        chosen = "path ends with\\"
        
        append_decision_to_spec(
            str(self.spec_path),
            topic,
            chosen,
            lambda cmd: None
        )
        
        num_decisions, num_tasks, last_chosen = self._parse_and_count(self.spec_path)
        self.assertEqual(num_decisions, 2)
        self.assertEqual(last_chosen, chosen)
    
    def test_append_dollar_signs_not_interpreted(self):
        """texto con signo pesos simple y doble signo pesos: chosen parseado identico al original,
        no se interpreta como referencia de grupo de re.sub"""
        topic = "Dollar signs"
        chosen = "price is $10 and $$20"
        
        append_decision_to_spec(
            str(self.spec_path),
            topic,
            chosen,
            lambda cmd: None
        )
        
        num_decisions, num_tasks, last_chosen = self._parse_and_count(self.spec_path)
        self.assertEqual(num_decisions, 2)
        self.assertEqual(last_chosen, chosen)
    
    def test_append_pipe_literal_roundtrip(self):
        """texto con pipe literal entre dos letras: chosen parseado contiene el pipe literal
        recuperado; num decisiones == 2"""
        topic = "Pipe literal"
        chosen = "type is str|int union"
        
        append_decision_to_spec(
            str(self.spec_path),
            topic,
            chosen,
            lambda cmd: None
        )
        
        num_decisions, num_tasks, last_chosen = self._parse_and_count(self.spec_path)
        self.assertEqual(num_decisions, 2)
        self.assertIn("|", last_chosen)
    
    def test_append_real_newline_becomes_space(self):
        """texto con salto de linea real (chr 10): chosen parseado tiene un espacio en lugar
        del salto; este comportamiento es el contrato explicito de D1; num decisiones == 2;
        num tareas sin cambio"""
        topic = "Real newline"
        chosen = "line one\nline two"
        
        append_decision_to_spec(
            str(self.spec_path),
            topic,
            chosen,
            lambda cmd: None
        )
        
        num_decisions, num_tasks, last_chosen = self._parse_and_count(self.spec_path)
        self.assertEqual(num_decisions, 2)
        self.assertEqual(num_tasks, 1)
        # Newline should be converted to space per D1 contract
        self.assertEqual(last_chosen, "line one line two")
    
    def test_append_double_newline_with_fake_section_header(self):
        """texto con doble salto de linea seguido de texto con cabecera markdown:
        no fabrica una seccion falsa en el archivo; num decisiones == 2;
        la decision previa sigue intacta en chosen"""
        topic = "Fake section"
        chosen = "description:\n\n## Malicious Header\n\ninjected content"
        
        append_decision_to_spec(
            str(self.spec_path),
            topic,
            chosen,
            lambda cmd: None
        )
        
        num_decisions, num_tasks, last_chosen = self._parse_and_count(self.spec_path)
        self.assertEqual(num_decisions, 2)
        # Should not create fake section
        content = self.spec_path.read_text(encoding="utf-8")
        # Count actual section headers
        section_count = content.count("\n## ")
        # Should have original sections only (Resumen, Decisiones, Archivos, Tareas, Fuera, Riesgos)
        self.assertEqual(section_count, 6)
    
    def test_append_trailing_backslash_adjacent_pipe_separator_roundtrip(self):
        """texto cuya representacion en la celda termina en barra invertida pegada al pipe separador:
        _split_row no confunde esa barra con escape del separador; chosen parseado correcto;
        num decisiones == 2"""
        topic = "Backslash at end"
        chosen = "path\\"
        
        append_decision_to_spec(
            str(self.spec_path),
            topic,
            chosen,
            lambda cmd: None
        )
        
        num_decisions, num_tasks, last_chosen = self._parse_and_count(self.spec_path)
        self.assertEqual(num_decisions, 2)
        self.assertEqual(last_chosen, chosen)
    
    def test_append_user_written_backslash_pipe_roundtrip(self):
        """texto con barra-pipe escrito literalmente por el usuario: round-trip exacto,
        el pipe literal se preserva en chosen parseado"""
        topic = "User backslash pipe"
        chosen = "signature: fn(x: str \\| int)"
        
        append_decision_to_spec(
            str(self.spec_path),
            topic,
            chosen,
            lambda cmd: None
        )
        
        num_decisions, num_tasks, last_chosen = self._parse_and_count(self.spec_path)
        self.assertEqual(num_decisions, 2)
        # Should preserve the backslash-pipe exactly as written (D5 contract)
        self.assertEqual(last_chosen, chosen)
    
    def test_append_two_consecutive_second_with_backslashes(self):
        """dos llamadas consecutivas a append_decision_to_spec, la segunda con barras:
        primera decision chosen intacta, num decisiones == 3, num tareas sin cambio"""
        # First append
        append_decision_to_spec(
            str(self.spec_path),
            "First",
            "first option",
            lambda cmd: None
        )
        
        # Second append with backslashes
        append_decision_to_spec(
            str(self.spec_path),
            "Second",
            "use \\d+ pattern",
            lambda cmd: None
        )
        
        content = self.spec_path.read_text(encoding="utf-8")
        metadata, spec, progress = parse_spec_markdown(content)
        
        self.assertEqual(len(spec["decisions"]), 3)
        self.assertEqual(len(spec["tasks"]), 1)
        # First appended decision should be intact
        self.assertEqual(spec["decisions"][1]["chosen"], "first option")
        # Second should have backslash pattern
        self.assertIn("\\d", spec["decisions"][2]["chosen"])


class TestSpecWithCorruptedPipe(unittest.TestCase):
    """Test parser behavior with corrupted pipe in decision table."""
    
    def test_corrupted_pipe_in_decision_row_parsed_as_rationale(self):
        """una fila de decision con un pipe sin escapar dentro de la celda chosen:
        el parser debe tratar el contenido despues del pipe como parte de rationale,
        NO como una celda separada; chosen termina antes del pipe, rationale empieza
        despues del pipe; este test asevera el comportamiento del parser ANTES de _split_row"""
        
        spec_content = """---
issue: 999
status: draft
test_command: echo test
---

## Resumen

Test for corrupted pipe.

## Decisiones de diseño

| ID | Tema | Opciones | Elegida | Justificación |
|----|------|----------|---------|---------------|
| D1 | Corrupted | A, B | choice with | rest of text |

## Archivos afectados

None.

## Tareas

None.

## Fuera de alcance

None.

## Riesgos

None.
"""
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(spec_content)
            temp_path = Path(f.name)
        
        try:
            metadata, spec, progress = parse_spec_markdown(spec_content)
            
            # With current parser (before _split_row), the pipe splits the cell
            # So "choice with" ends up in chosen, and "rest of text" in rationale
            self.assertEqual(len(spec["decisions"]), 1)
            decision = spec["decisions"][0]
            
            # Before fix: chosen is "choice with", rationale is "rest of text"
            # After fix with _split_row: chosen is "choice with | rest of text", rationale stays
            # This test documents CURRENT behavior with corrupted data
            # The real specs (issue-37, issue-11) will be fixed manually before new RED
            
            # Expected with OLD parser: pipe splits the cells
            self.assertNotIn("|", decision["chosen"])
            
        finally:
            temp_path.unlink()


class TestAllRepoSpecsParse(unittest.TestCase):
    """Test that all existing specs in docs/specs/ parse without exception."""
    
    def test_all_repo_specs_parse_without_exception(self):
        """todos los archivos en docs/specs/*.md parsean con parse_spec_markdown
        sin lanzar excepcion; para cada spec, ningun campo chosen de ninguna decision
        termina en barra invertida (sintoma de pipe partido por el parser viejo);
        si alguna spec falla este invariante por contenido legitimo, el test la lista
        en el mensaje de error"""
        
        specs_dir = repo_root / "docs" / "specs"
        
        # Directory must exist
        self.assertTrue(specs_dir.exists(), f"Specs directory not found: {specs_dir}")
        
        spec_files = list(specs_dir.glob("*.md"))
        self.assertGreater(len(spec_files), 0, "No spec files found in docs/specs/")
        
        failed_specs = []
        
        for spec_file in spec_files:
            with self.subTest(spec=spec_file.name):
                content = spec_file.read_text(encoding="utf-8")
                
                # Should parse without exception
                try:
                    metadata, spec, progress = parse_spec_markdown(content)
                except Exception as e:
                    self.fail(f"Failed to parse {spec_file.name}: {e}")
                
                # Check that no chosen field ends with backslash (symptom of split pipe)
                for decision in spec["decisions"]:
                    chosen = decision["chosen"]
                    if chosen.endswith("\\"):
                        failed_specs.append(
                            f"{spec_file.name}: decision {decision['id']} "
                            f"chosen ends with backslash: {repr(chosen)}"
                        )
        
        if failed_specs:
            self.fail(
                "Some specs have decisions with chosen ending in backslash:\n" +
                "\n".join(failed_specs)
            )


if __name__ == "__main__":
    unittest.main()

---
issue: 39
status: implementing
test_command: python3 -m unittest discover -s tests -v
---

# Spec de implementación: Harness: append_decision_to_spec rompe con barras invertidas en el texto de una decision

## Resumen

Corregir append_decision_to_spec con lambda en re.sub (defecto A) y agregar _escape_cell/_split_row (defecto B) para round-trip exacto; separar test de no-regresion en dos: conteo fijo y verificacion de pipe desescapado en D3 de issue-37

## Decisiones de diseño

| ID | Topic | Opciones | Elegida | Rationale |
|----|-------|----------|---------|-----------|
| D1 | Normalizacion de saltos de linea en celdas de tabla Markdown | A: colapsar a espacio, B: codificar como br HTML (lossless), C: rechazar/truncar | A: colapsar a espacio | Los saltos de linea en el texto de una decision no tienen semantica estructural; colapsarlos a espacio es suficiente y evita dependencia de renderers HTML. El round-trip se asevera explicitamente como contrato: salto de linea real pasa a espacio, y eso es lo que el test verifica. |
| D2 | Escritura de celdas: funcion compartida _escape_cell | duplicar el escape inline en cada sitio (estado actual), una funcion _escape_cell(text) -> str compartida en take_agent.py | una funcion _escape_cell(text) -> str compartida en take_agent.py | Convierte en orden: (1) barra invertida a doble barra, (2) pipe a barra-pipe, (3) cualquier salto de linea (newline, CR+LF, CR) a espacio. El orden es critico: la barra debe escaparse antes que el pipe para no re-escapar la barra del escape. tdd_runner.py la importa junto a parse_spec_markdown. En append_decision_to_spec el re.sub usa lambda m: m.group(1) + new_table + m.group(3) para que el texto nunca se interprete como plantilla. |
| D3 | Lectura de celdas: funcion compartida _split_row | split naive por pipe (estado actual), re.split con lookbehind negativo (falso positivo), tokenizador caracter a caracter _split_row(row) -> list[str] | tokenizador caracter a caracter _split_row(row) -> list[str] en take_agent.py | Recorre caracter a caracter: barra-barra -> una barra; barra-pipe -> un pipe literal (no separa); barra seguida de cualquier otro caracter (incluyendo fin de celda) -> conserva la barra literal. Todo otro caracter se copia. Descarta celda vacia inicial y final. Devuelve celdas desescapadas. Usada por parse_spec_markdown en la tabla de decisiones. |
| D4 | Compatibilidad con specs viejas: semantica de barra solitaria en _split_row | error si hay barra sin escape (breaking change), desescapar solo barra-barra y barra-pipe; barra seguida de otro caracter se conserva literal | desescapar solo barra-barra y barra-pipe; barra seguida de otro caracter se conserva literal | Specs ya commiteadas (issue-37.md, issue-11.md) tienen barras sueltas escritas antes de _escape_cell. Con esta regla el contenido parseado de celdas sin barra-pipe no cambia. El round-trip exacto aplica solo a contenido escrito con _escape_cell. El cambio ESPERADO es que la celda chosen de D3 de issue-37.md, antes partida en el pipe como 'str backslash' ahora devuelve el texto completo con el pipe literal desescapado; esto es el arreglo del defecto B y se asevera en test_issue37_d3_cell_not_split_at_escaped_pipe. |
| D5 | Ubicacion de los tests y estructura de tareas | tests/test_tdd_runner.py (existente), tests/test_issue_39.py con dos tareas separadas, tests/test_issue_39.py con una sola tarea | tests/test_issue_39.py con una sola tarea | Una sola tarea T1: los tests unitarios de _escape_cell y _split_row fallan en RED por funciones inexistentes; los tests de integracion viajan con ellos. Evita el patron de T2-separada que pasaria en RED por construccion una vez que T1 implementa las funciones. Sigue el patron del repo (test_issue_37.py, test_issue_35.py). |
| D6 | Los tests de no-regresión `test_all_repo_specs_parse_without_exception` y `test_issue37_d3_cell_not_split_at_escaped_pipe` aseveran el estado DESPUES de reescribir los archivos existentes (issue-37.md, issue-11.md) con `_escape_cell()`. Sin embargo, los archivos actuales tienen pipes sin escapar, por lo que los tests fallan. ¿Debo reescribir los archivos existentes como parte de GREEN, o estos tests deben ajustarse para permitir el estado actual de transición? | Decisión: los tests de RED tienen cuatro defectos y hay que volver a RED; la implementación no se toca. (1) Los dos tests sobre las specs reales parten de una premisa falsa: miré los bytes de la fila D3 de issue-37 y D5 de issue-11 y el pipe de esas celdas NUNCA estuvo escapado (hay una barra, un espacio y un pipe suelto), son datos ya corruptos que voy a reparar yo aparte en un commit propio antes de la nueva fase RED. (2) El test de la matriz calcula el esperado de los saltos de línea encadenando reemplazos y para el salto doble de Windows da dos espacios; calculá el esperado con una función propia que trate primero el par de dos caracteres. (3) El test del texto con barra y pipe escrito por el usuario espera que se lea sin la barra, pero con D5 un texto escrito por el usuario debe volver IGUAL, con la barra. (4) Hay tres usos de skipTest y la regla del repo es cero tests saltados: sacalos y que fallen si el archivo no existe. Dejá el test que recorre todas las specs del repo (se mantiene) y reemplazá los dos de issue-37 por uno que construya su propia spec temporal con una fila de decisión con un pipe sin escapar y fije lo que debe hacer el lector con ella, describiendo el resultado esperado en palabras. No escribas barras invertidas literales en el texto de las decisiones. | Decisión: los tests de RED tienen cuatro defectos y hay que volver a RED; la implementación no se toca. (1) Los dos tests sobre las specs reales parten de una premisa falsa: miré los bytes de la fila D3 de issue-37 y D5 de issue-11 y el pipe de esas celdas NUNCA estuvo escapado (hay una barra, un espacio y un pipe suelto), son datos ya corruptos que voy a reparar yo aparte en un commit propio antes de la nueva fase RED. (2) El test de la matriz calcula el esperado de los saltos de línea encadenando reemplazos y para el salto doble de Windows da dos espacios; calculá el esperado con una función propia que trate primero el par de dos caracteres. (3) El test del texto con barra y pipe escrito por el usuario espera que se lea sin la barra, pero con D5 un texto escrito por el usuario debe volver IGUAL, con la barra. (4) Hay tres usos de skipTest y la regla del repo es cero tests saltados: sacalos y que fallen si el archivo no existe. Dejá el test que recorre todas las specs del repo (se mantiene) y reemplazá los dos de issue-37 por uno que construya su propia spec temporal con una fila de decisión con un pipe sin escapar y fije lo que debe hacer el lector con ella, describiendo el resultado esperado en palabras. No escribas barras invertidas literales en el texto de las decisiones. | Decisión tomada durante implementación |

## Archivos afectados

- **modify** `scripts/take_agent.py`: Agregar _escape_cell(text) -> str y _split_row(row) -> list[str]; reemplazar escapes inline en render_spec_markdown por llamadas a _escape_cell; usar _split_row en parse_spec_markdown al parsear filas de la tabla de decisiones
- **modify** `scripts/tdd_runner.py`: En append_decision_to_spec: importar _escape_cell desde take_agent, usarla al construir new_rows, y reemplazar el rf-string en re.sub por lambda m: m.group(1) + new_table + m.group(3)
- **create** `tests/test_issue_39.py`: Tests unitarios de _escape_cell y _split_row, round-trip de la matriz de 15 textos via _split_row sobre fila construida con _escape_cell, matriz de integracion via append_decision_to_spec + parse_spec_markdown, y dos tests de no-regresion sobre docs/specs/issue-37.md con valores fijos

## Tareas

### T1: Agregar _escape_cell y _split_row; conectar al render/parser; fix de re.sub en append_decision_to_spec; todos los tests

Definir _escape_cell y _split_row en take_agent.py, integrarlas en render_spec_markdown y parse_spec_markdown, importar _escape_cell en tdd_runner.py con lambda en append_decision_to_spec; tests unitarios de ambas funciones, round-trip de la matriz de 15 textos, dos tests de no-regresion sobre issue-37.md con valores fijos, y test de todas las specs del repo

**Tests:**
- `tests/test_issue_39.py::test_escape_cell_plain_text`: texto sin caracteres especiales sale identico a la entrada
- `tests/test_issue_39.py::test_escape_cell_single_backslash_becomes_double`: una barra invertida sola se convierte en dos barras invertidas consecutivas
- `tests/test_issue_39.py::test_escape_cell_pipe_becomes_backslash_pipe`: un pipe literal se convierte en barra-invertida seguida de pipe
- `tests/test_issue_39.py::test_escape_cell_newline_becomes_space`: salto de linea real (chr 10) se convierte en un espacio
- `tests/test_issue_39.py::test_escape_cell_crlf_becomes_single_space`: CR seguido de LF se convierte en un solo espacio, no dos
- `tests/test_issue_39.py::test_escape_cell_cr_alone_becomes_space`: CR solitario (chr 13 sin LF) se convierte en un espacio
- `tests/test_issue_39.py::test_escape_cell_order_backslash_before_pipe`: texto con barra seguida de pipe: la barra se duplica primero y el pipe se escapa despues; resultado final tiene cuatro caracteres: dos barras seguidas de barra-pipe (la barra original duplicada, luego el pipe escapado con su propia barra)
- `tests/test_issue_39.py::test_split_row_simple_three_cells`: _split_row de una fila con tres celdas simples separadas por pipes devuelve lista de tres strings sin pipes de borde
- `tests/test_issue_39.py::test_split_row_escaped_pipe_not_split`: barra-pipe dentro de una celda no se trata como separador; la celda devuelta contiene un pipe literal desescapado
- `tests/test_issue_39.py::test_split_row_double_backslash_decoded_to_single`: doble barra invertida en la fila se decodifica a una sola barra invertida en la celda devuelta
- `tests/test_issue_39.py::test_split_row_backslash_followed_by_w_conserved_literal`: barra invertida seguida de la letra w (no es secuencia de escape reconocida): la celda devuelta contiene barra-w intactos, la barra se conserva literal sin ser consumida
- `tests/test_issue_39.py::test_split_row_trailing_backslash_before_pipe_separator_conserved`: celda cuyo ultimo caracter es una barra invertida pegada al pipe separador: la barra solitaria no escapa al pipe; la celda devuelta termina en barra invertida y el pipe actua como separador de columnas
- `tests/test_issue_39.py::test_split_row_roundtrip_all_matrix_texts`: para cada texto de la matriz de 15 casos, _split_row aplicada sobre la fila '| ' + _escape_cell(texto) + ' |' devuelve el texto con saltos de linea convertidos a espacio y todos los demas caracteres identicos al original; verifica que el round-trip es exacto para barras invertidas, pipes, signos pesos, y que los saltos de linea devuelven espacio (contrato D1 explicito)
- `tests/test_issue_39.py::test_append_plain_text_roundtrip`: texto sin caracteres especiales: chosen parseado == chosen original, num decisiones == 2, num tareas sin cambio, archivo parseable sin excepcion
- `tests/test_issue_39.py::test_append_backslash_w_regex_pattern_no_exception`: texto con barra-w en patron regex (caso del issue 37): no lanza excepcion, chosen parseado contiene barra-w, num decisiones == 2
- `tests/test_issue_39.py::test_append_backslash_d_no_exception`: texto con barra-d aislado: no lanza re.error, round-trip exacto, num decisiones == 2
- `tests/test_issue_39.py::test_append_backslash_1_not_replaced_by_group`: texto con barra-1: chosen parseado es identico al texto original, no el contenido del grupo capturado del regex (que seria la cabecera de tabla)
- `tests/test_issue_39.py::test_append_backslash_g_group_ref_no_exception`: texto con barra-g-menor-x-mayor: no lanza IndexError ni re.error, round-trip exacto, num decisiones == 2
- `tests/test_issue_39.py::test_append_double_backslash_not_collapsed`: texto con dos barras invertidas consecutivas: chosen parseado contiene dos barras invertidas, no colapsa a una sola
- `tests/test_issue_39.py::test_append_backslash_n_two_chars_not_converted`: texto con barra y n como dos caracteres literales separados (no un salto de linea real): round-trip exacto, chosen parseado contiene barra-n como dos caracteres distintos
- `tests/test_issue_39.py::test_append_trailing_backslash_roundtrip`: texto que termina en barra invertida: round-trip exacto, num decisiones == 2, archivo parseable
- `tests/test_issue_39.py::test_append_dollar_signs_not_interpreted`: texto con signo pesos simple y doble signo pesos: chosen parseado identico al original, no se interpreta como referencia de grupo de re.sub
- `tests/test_issue_39.py::test_append_pipe_literal_roundtrip`: texto con pipe literal entre dos letras: chosen parseado contiene el pipe literal recuperado; num decisiones == 2
- `tests/test_issue_39.py::test_append_real_newline_becomes_space`: texto con salto de linea real (chr 10): chosen parseado tiene un espacio en lugar del salto; este comportamiento es el contrato explicito de D1; num decisiones == 2; num tareas sin cambio
- `tests/test_issue_39.py::test_append_double_newline_with_fake_section_header`: texto con doble salto de linea seguido de texto con cabecera markdown: no fabrica una seccion falsa en el archivo; num decisiones == 2; la decision previa sigue intacta en chosen
- `tests/test_issue_39.py::test_append_trailing_backslash_adjacent_pipe_separator_roundtrip`: texto cuya representacion en la celda termina en barra invertida pegada al pipe separador: _split_row no confunde esa barra con escape del separador; chosen parseado correcto; num decisiones == 2
- `tests/test_issue_39.py::test_append_user_written_backslash_pipe_roundtrip`: texto con barra-pipe escrito literalmente por el usuario: round-trip exacto, el pipe literal se preserva en chosen parseado
- `tests/test_issue_39.py::test_append_two_consecutive_second_with_backslashes`: dos llamadas consecutivas a append_decision_to_spec, la segunda con barras: primera decision chosen intacta, num decisiones == 3, num tareas sin cambio
- `tests/test_issue_39.py::test_issue37_spec_counts_unchanged`: docs/specs/issue-37.md parsea sin excepcion; num_decisions == 13 (constante fija en el test, no recalculada); num_tasks == 5 (constante fija en el test, no recalculada)
- `tests/test_issue_39.py::test_issue37_d3_cell_not_split_at_escaped_pipe`: decisions[2]['chosen'] (D3 de issue-37.md) contiene la subcadena 'rejected: str | None = None, warnings: tuple[str, ...] = ()' con pipe literal desescapado y SIN barra invertida delante del pipe; decisions[2]['rationale'] NO empieza con 'None = None'; este test FALLA con el parser actual (defecto B sobre spec real) y pasa con _split_row
- `tests/test_issue_39.py::test_all_repo_specs_parse_without_exception`: todos los archivos en docs/specs/*.md parsean con parse_spec_markdown sin lanzar excepcion; para cada spec, ningun campo chosen de ninguna decision termina en barra invertida (sintoma de pipe partido por el parser viejo); si alguna spec falla este invariante por contenido legitimo, el test la lista en el mensaje de error

**Archivos de implementación:**
- `scripts/take_agent.py`
- `scripts/tdd_runner.py`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

## Fuera de alcance

- Cambiar la representacion de saltos de linea a algo distinto de espacio (ej. br HTML): D1 acordada como colapso a espacio
- Modificar las lineas de re.sub de set_status, mark_progress y unmark_progress en take_agent.py: son cadenas fijas sin texto de usuario, no tienen el bug
- Corregir retroactivamente el escape de celdas en specs ya commiteadas (solo se corrige la lectura con _split_row)
- Modificar cualquier otra funcion fuera de _escape_cell, _split_row, render_spec_markdown, parse_spec_markdown y append_decision_to_spec
- Tests de fases GREEN o REFACTOR del harness
- Cambios en AGENTS.md

## Riesgos

- render_spec_markdown ya hace .replace('|', barra-pipe) inline en varios campos: al introducir _escape_cell hay que reemplazar TODOS esos sitios o el escape queda duplicado (doble escape produce cuatro caracteres en lugar de dos)
- El orden de sustituciones en _escape_cell es critico: barra invertida debe escaparse ANTES que pipe; si se invierte, la barra del escape del pipe se re-escaparia
- parse_spec_markdown usa _split_row solo para la tabla de decisiones; otros parseos del mismo archivo (tasks, files) siguen con logica propia: no tocarlos evita regresiones
- Cambio ESPERADO y documentado en D4: la celda chosen de D3 de issue-37.md antes devolvia el texto partido ('str backslash' en chosen, 'None = None...' en rationale); despues de _split_row devuelve el texto completo con el pipe literal. test_issue37_d3_cell_not_split_at_escaped_pipe verifica este cambio como RED genuino que demuestra el arreglo del defecto B
- issue-11.md tiene el mismo sintoma en D5 chosen (contiene pipe escapado 'admin backslash-pipe admin'); test_all_repo_specs_parse_without_exception detectara que chosen ya no termina en barra invertida tras el fix
- Si _escape_cell se aplica dos veces al mismo texto (si render_spec_markdown ya escapaba y ahora tambien llama a _escape_cell), las barras se duplicarian: hay que eliminar los escapes inline antes de agregar la llamada

---
issue: 37
status: implementing
test_command: python3 -m unittest discover -s tests -v
---

# Spec de implementación: Harness: el detector de casts rechaza casts legítimos sobre valores de mocks (falso positivo)

## Resumen

Corregir detect_full_arg_cast para rechazar solo casts cuyo callee es un símbolo importado desde un impl_file, aceptar casts sobre mocks y matchers, con retorno estructurado CastCheckResult y balanceo de llaves/parens sobre el archivo completo

## Decisiones de diseño

| ID | Topic | Opciones | Elegida | Rationale |
|----|-------|----------|---------|-----------|
| D1 | Estrategia para identificar el callee en línea con cast | A: regex en misma línea, B: balanceo de llaves/parens leyendo archivo completo, C: AST parsing con dependencia externa | B: balanceo de {} y () leyendo el archivo completo desde la } disparadora hacia atrás; si el char anterior a la { de apertura es = / : / return → no es argumento → no rechazar; si es ( → extraer callee | El caso real de #11 es multilínea: la única línea que dispara el detector es '} as never);' sin callee visible. A falla en el 50% de los casos del issue. C suma dependencia externa innecesaria. |
| D2 | Tres resultados del clasificador y comportamiento para callee no resoluble | A: rechazar si no se resuelve, B: aceptar silenciosamente, C: tres resultados diferenciados con advertencia para no-resoluble | C: (1) callee en impl_file → RECHAZAR; (2) callee resuelto y no es de la tarea → ACEPTAR sin ruido; (3) callee no resoluble → ACEPTAR con ADVERTENCIA escrita en log de la tarea y al print del harness una sola vez por fase RED | El issue propone explícitamente advertir sin rechazar cuando el callee no se puede resolver. No mezclar 'resuelto-externo' con 'no resoluble': el primero es el caso habitual de mocks y no debe generar ruido. |
| D3 | Tipo de retorno de detect_full_arg_cast y método de identificación del callee | dataclass frozen / dict / lookup-exports / lookup-imports | @dataclass(frozen=True) CastCheckResult(rejected: str \ | None = None, warnings: tuple[str, ...] = ()); identificar callee vía imports del test: parsear import estático y dinámico desestructurado, mapear símbolo_local → impl_file, alias incluidos; namespace/default quedan en caso-no-resoluble |
| D4 | Firma de detect_full_arg_cast, construcción del mapa símbolo→impl, y fusión con actualización del llamador | A: construye mapa internamente; T4 y T5 separadas, A fusionada: T4 incluye cambio del llamador en run_red_phase | detect_full_arg_cast(repo_root, test_files, run_cmd, impl_files: list[str] \ | None = None) -> CastCheckResult; con impl_files=None comportamiento de #35 (rechaza todo patrón); mapa construido una vez por archivo; resolve_import_to_impl_file y build_symbol_to_impl_map son funciones públicas; T4 incluye actualización de run_red_phase (.rejected / .warnings) y sus tests, porque dejar el llamador roto entre tareas rompería todos los RED intermedios |
| D5 | El comportamiento esperado según los tests no coincide con la decisión C del spec. Los tests esperan: | Decisión: los tests de T3 están bien y NO se tocan; lo que estaba mal era la regla (contradicción de D2: 'resuelto y externo' vs 'no resoluble' no se puede distinguir a nivel de texto sin una frontera explícita). No uses tu propuesta de 'advertir solo si el mapa no está vacío' (ruidosa y deja huecos). Implementá en classify_callee una LISTA CERRADA, como constante de módulo (por ejemplo KNOWN_EXTERNAL_CALLEES, frozenset), con el último segmento del callee: mockResolvedValue, mockResolvedValueOnce, mockRejectedValue, mockRejectedValueOnce, mockReturnValue, mockReturnValueOnce, mockImplementation, mockImplementationOnce, toEqual, toStrictEqual, toBe, toMatchObject, toHaveBeenCalledWith, toHaveBeenLastCalledWith, spyOn, mocked. NO incluyas `fn` pelado: el test test_classify_extra_closing_brace_after_cast_warns_callee_not_resolvable usa un callee `fn` y espera advertencia con 'not resolvable' y 'fn', así que `fn` tiene que seguir siendo no resoluble (si más adelante hace falta aceptar vi.fn, se hace comparando el callee completo `vi.fn`, no el último segmento; no lo hagas ahora). Reglas en este orden: (1) callee en el mapa símbolo->impl_file (incluye alias de import) -> RECHAZAR; (2) último segmento del callee en la lista cerrada -> ACEPTAR sin advertencia; (3) cualquier otro callee -> ACEPTAR con exactamente una advertencia 'callee <x> not resolvable ...' que cite archivo y línea. Mantené sin cambios los casos no-argumento (`=`, `:`, `return`, `)`) -> aceptar sin advertencia, y el desbalanceo -> advertencia 'Unbalanced braces'. Con esto los 12 tests de T3 deben pasar tal como están; verificalo corriendo tests/test_issue_37.py::TestClassifyCallee completo y la suite de #35 y #35-revert. Dejá un comentario junto a la constante explicando que la lista es la frontera explícita entre 'externo conocido' y 'sospechoso' y que se amplía acá y en AGENTS.md (la documentación de la lista va en la tarea final). | Decisión: los tests de T3 están bien y NO se tocan; lo que estaba mal era la regla (contradicción de D2: 'resuelto y externo' vs 'no resoluble' no se puede distinguir a nivel de texto sin una frontera explícita). No uses tu propuesta de 'advertir solo si el mapa no está vacío' (ruidosa y deja huecos). Implementá en classify_callee una LISTA CERRADA, como constante de módulo (por ejemplo KNOWN_EXTERNAL_CALLEES, frozenset), con el último segmento del callee: mockResolvedValue, mockResolvedValueOnce, mockRejectedValue, mockRejectedValueOnce, mockReturnValue, mockReturnValueOnce, mockImplementation, mockImplementationOnce, toEqual, toStrictEqual, toBe, toMatchObject, toHaveBeenCalledWith, toHaveBeenLastCalledWith, spyOn, mocked. NO incluyas `fn` pelado: el test test_classify_extra_closing_brace_after_cast_warns_callee_not_resolvable usa un callee `fn` y espera advertencia con 'not resolvable' y 'fn', así que `fn` tiene que seguir siendo no resoluble (si más adelante hace falta aceptar vi.fn, se hace comparando el callee completo `vi.fn`, no el último segmento; no lo hagas ahora). Reglas en este orden: (1) callee en el mapa símbolo->impl_file (incluye alias de import) -> RECHAZAR; (2) último segmento del callee en la lista cerrada -> ACEPTAR sin advertencia; (3) cualquier otro callee -> ACEPTAR con exactamente una advertencia 'callee <x> not resolvable ...' que cite archivo y línea. Mantené sin cambios los casos no-argumento (`=`, `:`, `return`, `)`) -> aceptar sin advertencia, y el desbalanceo -> advertencia 'Unbalanced braces'. Con esto los 12 tests de T3 deben pasar tal como están; verificalo corriendo tests/test_issue_37.py::TestClassifyCallee completo y la suite de #35 y #35-revert. Dejá un comentario junto a la constante explicando que la lista es la frontera explícita entre 'externo conocido' y 'sospechoso' y que se amplía acá y en AGENTS.md (la documentación de la lista va en la tarea final). | Decisión tomada durante implementación |

## Archivos afectados

- **modify** `scripts/tdd_runner.py`: Agregar CastCheckResult dataclass, resolve_import_to_impl_file, build_symbol_to_impl_map; reescribir detect_full_arg_cast con balanceo+clasificador+mapa+nueva firma; actualizar run_red_phase para usar .rejected y .warnings; refactorizar test_imports_impl_file para delegar en resolve_import_to_impl_file
- **create** `tests/test_issue_37.py`: Tests unitarios y e2e para CastCheckResult, resolve_import_to_impl_file, build_symbol_to_impl_map, el clasificador por balanceo, detect_full_arg_cast con impl_files, run_red_phase con los 4 casos del issue, y AGENTS.md
- **modify** `tests/test_issue_35.py`: Migrar los 7 tests que llaman detect_full_arg_cast de str|None a CastCheckResult.rejected, sin cambiar qué verifican
- **modify** `tests/test_issue_35_revert.py`: Agregar 'import { buildApp } from "../src/impl.js";' a OLD_ORIGINAL y commitear app/src/impl.ts con export de buildApp en setUp, para que CAST_LINE siga siendo rechazada con la lógica nueva de lookup por imports
- **modify** `AGENTS.md`: Documentar la regla nueva del detector: rechaza solo si el callee es importado de un impl_file; ejemplos de los 4 casos del issue; límites (barrel files, alias locales, llaves en strings/comentarios)

## Tareas

### T1: CastCheckResult dataclass y resolve_import_to_impl_file

Definir CastCheckResult frozen dataclass y extraer resolve_import_to_impl_file desde test_imports_impl_file sin cambiar el comportamiento observable de esta última

**Tests:**
- `tests/test_issue_37.py::test_cast_check_result_defaults`: CastCheckResult() tiene rejected=None y warnings=()
- `tests/test_issue_37.py::test_cast_check_result_frozen`: asignar result.rejected lanza FrozenInstanceError (dataclasses.FrozenInstanceError)
- `tests/test_issue_37.py::test_cast_check_result_with_values`: CastCheckResult(rejected='line', warnings=('w1',)) tiene los campos correctos y es inmutable
- `tests/test_issue_37.py::test_resolve_import_js_to_ts`: resolve_import_to_impl_file(test_file='apps/api/test/auth.test.ts', import_path='../src/app.js', impl_files=['apps/api/src/app.ts'], repo_root) retorna 'apps/api/src/app.ts'
- `tests/test_issue_37.py::test_resolve_import_no_extension`: resolve_import_to_impl_file con '../src/bar' e impl_file 'src/bar.ts' retorna 'src/bar.ts'
- `tests/test_issue_37.py::test_resolve_import_non_relative_ignored`: resolve_import_to_impl_file con 'vitest' retorna None (no relativo → ignorado)
- `tests/test_issue_37.py::test_resolve_import_no_match`: resolve_import_to_impl_file con '../src/other.js' e impl_file 'src/app.ts' retorna None
- `tests/test_issue_37.py::test_test_imports_impl_file_still_works`: test_imports_impl_file sigue retornando True cuando el test importa el impl_file y False cuando no; mismos casos que en #35 (delega en resolve internamente sin cambiar semántica)

**Archivos de implementación:**
- `scripts/tdd_runner.py`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T2: build_symbol_to_impl_map: mapeo símbolo local → impl_file

Parsear imports estáticos y dinámicos desestructurados del test y construir mapa nombre_local→impl_file, cubriendo alias y excluyendo namespace/default/no-relativos

**Tests:**
- `tests/test_issue_37.py::test_build_map_static_import`: archivo con 'import { buildApp } from "../src/app.js"' e impl_file 'apps/api/src/app.ts' → {'buildApp': 'apps/api/src/app.ts'}
- `tests/test_issue_37.py::test_build_map_static_import_alias`: archivo con 'import { buildApp as build } from "../src/app.js"' → {'build': 'apps/api/src/app.ts'} (nombre local es 'build')
- `tests/test_issue_37.py::test_build_map_static_import_multiple_symbols`: import { a, b } from '../src/app.js' → {'a': 'apps/api/src/app.ts', 'b': 'apps/api/src/app.ts'}
- `tests/test_issue_37.py::test_build_map_dynamic_import_destructured`: archivo con 'const { buildApp } = await import("../src/app.js")' → {'buildApp': 'apps/api/src/app.ts'}
- `tests/test_issue_37.py::test_build_map_dynamic_import_alias`: archivo con 'const { buildApp: build } = await import("../src/app.js")' → {'build': 'apps/api/src/app.ts'}
- `tests/test_issue_37.py::test_build_map_namespace_import_excluded`: import * as app from '../src/app.js' → mapa vacío (namespace no mapeado; queda en caso-no-resoluble)
- `tests/test_issue_37.py::test_build_map_default_import_excluded`: import app from '../src/app.js' → mapa vacío (default no mapeado)
- `tests/test_issue_37.py::test_build_map_non_relative_ignored`: import { vi } from 'vitest' → no aparece en el mapa
- `tests/test_issue_37.py::test_build_map_non_impl_file_ignored`: import { x } from '../src/other.js' donde other.ts NO es impl_file → mapa vacío
- `tests/test_issue_37.py::test_build_map_empty_when_file_missing`: test_file inexistente → mapa vacío sin lanzar excepción

**Archivos de implementación:**
- `scripts/tdd_runner.py`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T3: Clasificador de callee por balanceo de llaves/parens sobre archivo completo

Implementar el algoritmo de balanceo que dado un archivo y la línea disparadora retrocede en el texto completo para determinar si el objeto es argumento y extrae el callee; cubrir los 4 casos del issue y los casos de no-argumento

**Tests:**
- `tests/test_issue_37.py::test_classify_single_line_impl_symbol_rejected`: buildApp({ db, auth } as never) con 'buildApp' mapeado a impl_file → CastCheckResult(rejected=<línea>, warnings=())
- `tests/test_issue_37.py::test_classify_multiline_mock_accepted`: vi.mocked(GoogleSignin.signIn).mockResolvedValue({\n  data: { idToken: 'x' },\n} as never) multilínea, 'mockResolvedValue' no en mapa → CastCheckResult() vacío (rejected=None, warnings=())
- `tests/test_issue_37.py::test_classify_single_line_mock_accepted`: mockResolvedValue({ ok: true } as never) una línea, callee no en mapa → CastCheckResult() vacío
- `tests/test_issue_37.py::test_classify_expect_toequal_accepted`: expect(result).toEqual({ a: 1 } as never), callee 'toEqual' no en mapa → CastCheckResult() vacío
- `tests/test_issue_37.py::test_classify_assignment_not_argument`: const x = { db } as never → char anterior a { es '=' → no es argumento → CastCheckResult() vacío
- `tests/test_issue_37.py::test_classify_return_not_argument`: return { db } as never → token anterior a { es 'return' → CastCheckResult() vacío
- `tests/test_issue_37.py::test_classify_property_colon_not_argument`: prop: { db } as never → char anterior a { es ':' → CastCheckResult() vacío
- `tests/test_issue_37.py::test_classify_alias_import_rejected`: archivo con 'import { buildApp as build } from "../src/app.js"'; build({ db } as never) → 'build' mapeado a impl_file → CastCheckResult(rejected=<línea>)
- `tests/test_issue_37.py::test_classify_multiline_impl_rejected`: buildApp({\n  db,\n  auth,\n} as never) multilínea con 'buildApp' en mapa → CastCheckResult(rejected=<línea con '}'>)
- `tests/test_issue_37.py::test_classify_local_alias_variable_warns`: const build = buildApp; build({ db } as never) → 'build' no en mapa de imports → CastCheckResult(rejected=None, warnings=(<msg con archivo:línea>,))
- `tests/test_issue_37.py::test_classify_unbalanced_braces_warns`: contenido con llaves desbalanceadas que impiden retroceder → CastCheckResult(rejected=None, warnings=(<msg>,))

**Archivos de implementación:**
- `scripts/tdd_runner.py`

**Progreso:**
- [x] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

### T4: detect_full_arg_cast nueva firma + CastCheckResult + actualizar run_red_phase + migrar tests #35 y #35-revert

Reescribir detect_full_arg_cast con nueva firma (impl_files opcional), integrar balanceo+mapa, preservar semántica de #35 con impl_files=None; migrar 7 tests de test_issue_35.py a .rejected; actualizar OLD_ORIGINAL y scaffolding en test_issue_35_revert.py; actualizar run_red_phase para usar .rejected/.warnings con warning impreso una vez y escrito al log

**Tests:**
- `tests/test_issue_37.py::test_detect_no_impl_files_rejects_as_never`: impl_files=None, archivo nuevo con '} as never)' → result.rejected == línea (semántica #35 intacta)
- `tests/test_issue_37.py::test_detect_no_impl_files_rejects_as_any`: impl_files=None, '} as any)' → result.rejected == línea
- `tests/test_issue_37.py::test_detect_no_impl_files_rejects_as_unknown`: impl_files=None, '} as unknown as X)' → result.rejected == línea
- `tests/test_issue_37.py::test_detect_with_impl_files_mock_accepted`: impl_files=['apps/api/src/app.ts'], test file SIN import de app.ts, mockResolvedValue({ data } as never) → result.rejected is None, result.warnings == ()
- `tests/test_issue_37.py::test_detect_with_impl_files_impl_symbol_rejected`: impl_files=['apps/api/src/app.ts'], test file con 'import { buildApp } from "../src/app.js"', buildApp({ db } as never) → result.rejected == línea
- `tests/test_issue_37.py::test_detect_map_built_once_per_file`: archivo con 3 líneas nuevas disparadoras → build_symbol_to_impl_map llamada exactamente 1 vez (mockear y contar)
- `tests/test_issue_37.py::test_detect_warning_contains_file_and_line`: callee no resoluble → result.warnings[0] contiene nombre del archivo y número de línea correcto del archivo fuente
- `tests/test_issue_37.py::test_cast_on_unimported_callee_is_accepted_with_warning`: impl_files=['apps/api/src/app.ts'], archivo con CAST_LINE '  buildApp({ db } as never);' pero SIN import de app.ts → result.rejected is None, result.warnings tiene exactamente 1 elemento con archivo:línea (caso 3: callee no resoluble)
- `tests/test_issue_37.py::test_run_red_mock_cast_accepted`: run_red_phase con coder que escribe mockResolvedValue({ data } as never), impl_files sin mockResolvedValue → retorna True sin feedback de cast en prints; repo git con scaffolding commiteado
- `tests/test_issue_37.py::test_run_red_impl_cast_rejected_retries`: run_red_phase con coder que escribe buildApp({ db } as never) importado de impl_file → coder invocado 2 veces; segundo prompt contiene la línea rechazada; repo git con scaffolding commiteado
- `tests/test_issue_37.py::test_run_red_warning_printed_once`: run_red_phase con callee no resoluble en 3 líneas nuevas → texto 'no pude determinar el callee' aparece exactamente 1 vez en prints; repo git con scaffolding commiteado
- `tests/test_issue_37.py::test_run_red_warning_written_to_log`: run_red_phase con callee no resoluble → archivo de log de la tarea contiene 'archivo:línea' del cast no resoluble; repo git con scaffolding commiteado
- `tests/test_issue_37.py::test_run_red_multiline_mock_accepted`: run_red_phase con coder que escribe mockResolvedValue multilínea ({\n...\n} as never) → retorna True, sin feedback de cast; repo git con scaffolding commiteado
- `tests/test_issue_35.py::test_detect_cast_finds_as_never_paren`: migrado: result.rejected contiene '} as never)' (antes assertIsNotNone(result) + assertIn en result directo)
- `tests/test_issue_35.py::test_detect_cast_finds_as_any_paren`: migrado: result.rejected contiene '} as any)'
- `tests/test_issue_35.py::test_detect_cast_finds_as_unknown_as_ident_paren`: migrado: result.rejected contiene '} as unknown as BuildAppOptions)'
- `tests/test_issue_35.py::test_detect_cast_ignores_property_cast`: migrado: result.rejected is None
- `tests/test_issue_35.py::test_detect_cast_ignores_variable_cast`: migrado: result.rejected is None
- `tests/test_issue_35.py::test_detect_cast_untracked_file_with_cast_detected`: migrado: result.rejected contiene '} as never)'
- `tests/test_issue_35.py::test_detect_cast_tracked_existing_line_ignored`: migrado: result.rejected is None

**Archivos de soporte de tests:**
- `tests/test_issue_35.py`
- `tests/test_issue_35_revert.py`

**Archivos de implementación:**
- `scripts/tdd_runner.py`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

### T5: E2E de run_red_phase con repo git real + AGENTS.md

Tests e2e con repo git real (scaffolding commiteado en setUp, run_cmd simula tsc/eslint con returncode=0) cubriendo los 4 casos del issue; tests unitarios previos que verifican la clasificación en aislamiento antes del e2e; actualizar AGENTS.md con la regla nueva, ejemplos de los 4 casos del issue y límites documentados

**Tests:**
- `tests/test_issue_37.py::test_classifier_accepts_mock_before_lint`: detect_full_arg_cast con impl_files y archivo con mockResolvedValue({...} as never) multilínea → result.rejected is None (verifica clasificación en aislamiento, falla si balanceo está roto)
- `tests/test_issue_37.py::test_classifier_rejects_buildapp_before_lint`: detect_full_arg_cast con impl_files y archivo con buildApp({...} as never) importado del impl_file → result.rejected es la línea (verifica clasificación en aislamiento)
- `tests/test_issue_37.py::test_e2e_impl_cast_rejected`: repo git real con scaffolding commiteado (app/src/app.ts con export buildApp, app/test/auth.test.ts importando buildApp, package.json, tsconfig.json, spec, .gitignore); coder escribe buildApp({ db, auth } as never) → run_red_phase rechaza, coder invocado 2 veces, sin commit de test tras primer intento; run_cmd simula tsc/eslint con returncode=0
- `tests/test_issue_37.py::test_e2e_mock_cast_accepted`: repo git real con scaffolding commiteado; coder escribe vi.mocked(fn).mockResolvedValue({\n  data: x,\n} as never) multilínea → run_red_phase retorna True, commit de test presente en git log; run_cmd simula tsc/eslint con returncode=0
- `tests/test_issue_37.py::test_agents_md_callee_rule`: AGENTS.md contiene texto sobre rechazar solo si el callee es importado de un impl_file (busca 'impl_file' en la sección del detector de casts)
- `tests/test_issue_37.py::test_agents_md_examples`: AGENTS.md contiene 'mockResolvedValue' como ejemplo aceptado y 'buildApp' como ejemplo rechazado en la sección del detector
- `tests/test_issue_37.py::test_agents_md_barrel_limit`: AGENTS.md menciona el límite de barrel files o re-exports en la sección del detector de casts

**Archivos de implementación:**
- `AGENTS.md`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

## Fuera de alcance

- Modificar las fases GREEN o REFACTOR
- Soporte para namespace imports (import * as x) como callee resoluble — quedan en caso-no-resoluble con advertencia
- Soporte para default imports como callee resoluble
- Detección de casts en barrel files o re-exports
- AST parsing con dependencias externas
- Detección de alias de variable local (const build = buildApp) — falso negativo aceptado y documentado
- Cambiar MAX_DESVIOS_PER_PHASE ni ningún otro comportamiento del harness no relacionado con detect_full_arg_cast

## Riesgos

- test_issue_35_revert.py: OLD_ORIGINAL debe incluir el import de buildApp y app/src/impl.ts debe exportar buildApp en el scaffolding; si el fix es incompleto los 4 tests de TestRedCastNoRevertBetweenAttempts pasan por razón incorrecta (callee no-resoluble en lugar de rechazado)
- Los 7 tests de test_issue_35.py cambian la forma del assert (str|None → .rejected): declarados en test_support_files de T4 para que el harness no los rechace en RED por editar archivos fuera de la lista
- test_issue_35_revert.py declarado en test_support_files de T4 por la misma razón: el harness lo vería como archivo de test no listado
- El balanceo de {}/{} se confunde con llaves dentro de strings o comentarios: falso negativo aceptado, documentado en AGENTS.md
- Alias de variable local (const build = buildApp; build({...})) es falso negativo aceptado, documentado en AGENTS.md

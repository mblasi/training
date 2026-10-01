---
issue: 35
status: implementing
test_command: python3 -m unittest discover -s tests -v && corepack pnpm install --frozen-lockfile && corepack pnpm lint && corepack pnpm typecheck && corepack pnpm test
---

# Spec de implementación: Harness: RED rechaza tests legítimos cuando cambia una firma de producción (TS2353) y el revert descarta ediciones correctas

## Resumen

Corregir el harness RED para aceptar errores TS de firmas en impl_files (D1-B), no revertir entre intentos estáticos (D2-A), rechazar casts sobre argumento completo (D3-angosto), y agregar regla de firma en prompt (D4-B)

## Decisiones de diseño

| ID | Topic | Opciones | Elegida | Rationale |
|----|-------|----------|---------|-----------|
| D1 | Aceptar TS2353/TS2345 solo si el tipo nombrado está declarado en un impl_file | A: ampliar lista fija, B: aceptar si tipo nombrado está en impl_file (regex en mensaje + leer fuente), C: híbrido | B con dos sub-reglas: (1) extraer tipo nombrado del mensaje (TS2353 'in type X', TS2345 'parameter of type X') y buscar interface/type/class X en impl_files; (2) para códigos sin tipo nombrado (TS2554, TS2339, TS2551, TS2741) aceptar si el archivo de test importa un módulo que resuelve a un impl_file de la tarea | Distingue errores legítimos de firma propia vs errores de uso de librerías externas |
| D2 | Revert ante falla estática en RED | A: no revertir entre intentos (coder corrige en sitio); revertir todo en abort/agotamiento, B: revertir todo con feedback de archivos descartados, C: revertir solo archivos con errores | A: no revertir entre intentos estáticos; al agotar intentos o abortar, revertir todos los archivos cambiados; la rama 'continuar' commitea lo que hay pero avisa explícitamente que los tests no pasan lint/typecheck | Preserva ediciones correctas entre intentos; el riesgo de producción sucia no existe porque el chequeo de 'solo archivos de test' corre antes |
| D3 | Detección de type casts que esquivan errores de firma | A: rechazar as never/as any en llamadas a función bajo test (complejo), B: avisar sin rechazar, C: rechazar todas las líneas nuevas con as never/as any, D: angosto: rechazar solo patrón '} as never)' / '} as any)' / '} as unknown as Tipo)' en líneas nuevas | D angosto: líneas nuevas en archivos de test (líneas '+' de git diff para trackeados; todas las líneas para archivos sin trackear) que contengan '} as never)' o '} as any)' o '} as unknown as <ident>)' → rechazado con feedback citando la línea. Casts por propiedad (db: mockDb as never,) y de variables (fakeDb as never) permitidos. Falsos negativos asumidos y documentados. | Cubre el caso del issue sin romper los fakes de DB existentes; archivos nuevos sin trackear cuentan todas sus líneas como nuevas |
| D4 | Regla explícita en prompt de RED sobre actualización de tests al cambiar firma | A: regla condicional si hay impl_files existentes, B: regla 7 siempre presente en el prompt | B: agregar siempre como regla 7: 'Si la tarea cambia la firma de una función existente, actualizá todos los tests existentes que la llaman; no uses casts sobre el argumento completo (ej: fn({ a, b } as never)) para evitar errores de tipo' | La regla es siempre válida; el coder no sabe a priori si aplica |

## Archivos afectados

- **modify** `scripts/tdd_runner.py`: Agregar extract_ts_error_type_name(), type_declared_in_impl_files(), test_imports_impl_file(), get_new_lines(), detect_full_arg_cast(); extender check_test_files_static() con parámetro opcional impl_files (D1); cambiar comportamiento de revert en static_feedback (D2); llamar detect_full_arg_cast tras check estático (D3); agregar regla 7 en build_red_prompt() (D4)
- **create** `tests/test_issue_35.py`: Tests unitarios e2e para las cuatro correcciones del issue
- **modify** `AGENTS.md`: Documentar la nueva lógica de errores TS aceptables, el no-revert entre intentos estáticos, y la detección de casts de argumento completo

## Tareas

### T1: extract_ts_error_type_name y type_declared_in_impl_files

Funciones puras que extraen el tipo nombrado de un mensaje de error TS y buscan su declaración en impl_files

**Tests:**
- `tests/test_issue_35.py::test_extract_type_from_ts2353_in_type`: extract_ts_error_type_name('TS2353', "...does not exist in type 'BuildAppOptions'") == 'BuildAppOptions'
- `tests/test_issue_35.py::test_extract_type_from_ts2345_parameter_of_type`: extract_ts_error_type_name('TS2345', "...parameter of type 'BuildAppOptions'") == 'BuildAppOptions'
- `tests/test_issue_35.py::test_extract_type_returns_none_for_unnamed_code`: extract_ts_error_type_name('TS2554', 'Expected 2 arguments, but got 3') is None
- `tests/test_issue_35.py::test_extract_type_returns_none_for_ts2307`: extract_ts_error_type_name('TS2307', "Cannot find module './missing'") is None
- `tests/test_issue_35.py::test_type_declared_finds_interface`: type_declared_in_impl_files('BuildAppOptions', ['apps/api/src/app.ts'], repo_root) == True cuando el archivo contiene 'interface BuildAppOptions'
- `tests/test_issue_35.py::test_type_declared_finds_type_alias`: type_declared_in_impl_files('Opts', ['src/x.ts'], repo_root) == True cuando el archivo contiene 'type Opts ='
- `tests/test_issue_35.py::test_type_declared_finds_class`: type_declared_in_impl_files('MyClass', ['src/x.ts'], repo_root) == True cuando el archivo contiene 'class MyClass'
- `tests/test_issue_35.py::test_type_declared_false_for_external_type`: type_declared_in_impl_files('NodePgDatabase', ['src/app.ts'], repo_root) == False cuando el archivo no la declara
- `tests/test_issue_35.py::test_type_declared_matches_with_and_without_export`: Detecta 'interface X', 'export interface X', 'export type X =', 'export class X' en cualquier posición de línea
- `tests/test_issue_35.py::test_type_declared_false_when_impl_files_empty`: type_declared_in_impl_files('X', [], repo_root) == False

**Archivos de implementación:**
- `scripts/tdd_runner.py`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T2: test_imports_impl_file para códigos TS sin tipo nombrado

Función que verifica si un archivo de test importa un módulo relativo que resuelve a un impl_file de la tarea

**Tests:**
- `tests/test_issue_35.py::test_imports_impl_file_resolves_js_extension_to_ts`: test_imports_impl_file('apps/api/test/auth.test.ts', ['apps/api/src/app.ts'], repo_root) == True cuando el test tiene "import ... from '../src/app.js'"
- `tests/test_issue_35.py::test_imports_impl_file_resolves_no_extension`: test_imports_impl_file('test/foo.test.ts', ['src/bar.ts'], repo_root) == True cuando el test tiene "import ... from '../src/bar'"
- `tests/test_issue_35.py::test_imports_impl_file_false_when_no_matching_import`: test_imports_impl_file('test/x.test.ts', ['src/auth.ts'], repo_root) == False cuando el test no importa src/auth
- `tests/test_issue_35.py::test_imports_impl_file_handles_dynamic_import`: Detecta import() dinámico además de import estático en el contenido del archivo
- `tests/test_issue_35.py::test_imports_impl_file_false_when_file_missing`: test_imports_impl_file con archivo de test inexistente retorna False sin lanzar

**Archivos de implementación:**
- `scripts/tdd_runner.py`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T3: check_test_files_static acepta errores TS extendidos con impl_files opcional

Extender check_test_files_static con parámetro impl_files opcional: con None se comporta exactamente como antes; con lista aplica lógica D1 para TS2353/TS2345 y TS2554/TS2339/TS2551/TS2741

**Tests:**
- `tests/test_issue_35.py::test_check_static_ts2353_accepted_when_type_in_impl_file`: check_test_files_static(repo, [test_file], run_cmd, impl_files=['apps/api/src/app.ts']) con mock tsc devolviendo TS2353 sobre 'BuildAppOptions' declarada en app.ts → retorna None
- `tests/test_issue_35.py::test_check_static_ts2353_rejected_when_type_not_in_impl_file`: check_test_files_static con TS2353 sobre 'ExternalLibType' no declarada en ningún impl_file → retorna feedback con el error
- `tests/test_issue_35.py::test_check_static_ts2345_uses_parameter_type`: check_test_files_static con TS2345 '...parameter of type BuildAppOptions' y tipo declarado en impl_file → None
- `tests/test_issue_35.py::test_check_static_ts2554_accepted_when_test_imports_impl_file`: check_test_files_static con TS2554 e impl_files; test importa el impl_file → None
- `tests/test_issue_35.py::test_check_static_ts2554_rejected_when_no_import`: check_test_files_static con TS2554 e impl_files; test no importa ningún impl_file → feedback con error
- `tests/test_issue_35.py::test_check_static_none_impl_files_behaves_as_before`: check_test_files_static(repo, [test_file], run_cmd) sin impl_files (3 args, None por defecto): TS2353 en test file → rechazado igual que antes; TS2307 → aceptado igual que antes
- `tests/test_issue_35.py::test_check_static_existing_codes_still_accepted_with_impl_files`: TS2307/TS2305/TS2724/TS2614 siguen aceptados aunque se pase impl_files (comportamiento previo preservado)

**Archivos de implementación:**
- `scripts/tdd_runner.py`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T4: No revertir entre intentos estáticos; revertir al agotar/abortar; avisar al continuar

Cambiar run_red_phase: ante falla de check_test_files_static no revertir entre intentos; revertir al agotar o abortar; la rama 'continuar' commitea pero avisa que los tests no pasan lint/typecheck

**Tests:**
- `tests/test_issue_35.py::test_no_revert_between_static_attempts`: Tras falla estática en intento 1, los archivos cambiados siguen presentes en el FS al invocar el coder en intento 2 (revert_files no se llama entre intentos estáticos)
- `tests/test_issue_35.py::test_revert_all_on_exhausted_attempts`: Al agotar max_attempts con falla estática persistente, git status queda limpio (todos los archivos revertidos) y run_red_phase retorna False
- `tests/test_issue_35.py::test_revert_all_on_user_abort`: Cuando el usuario elige 'abortar' tras agotar intentos, git status queda limpio
- `tests/test_issue_35.py::test_continuar_warns_about_lint_typecheck`: Cuando el usuario elige 'continuar' tras agotar intentos con falla estática, el output contiene advertencia explícita de que los tests no pasan lint/typecheck antes de commitear
- `tests/test_issue_35.py::test_non_static_revert_unchanged`: Falla por archivos de producción sigue revirtiendo los archivos de producción (comportamiento previo intacto)

**Archivos de implementación:**
- `scripts/tdd_runner.py`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T5: get_new_lines y detect_full_arg_cast

get_new_lines(repo_root, file, run_cmd): líneas '+' de git diff HEAD para trackeados, todas las líneas para no trackeados. detect_full_arg_cast(repo_root, test_files, run_cmd): retorna la primera línea problemática o None

**Tests:**
- `tests/test_issue_35.py::test_get_new_lines_untracked_returns_all_lines`: get_new_lines para archivo sin trackear retorna todas sus líneas
- `tests/test_issue_35.py::test_get_new_lines_tracked_returns_only_added_lines`: get_new_lines para archivo trackeado retorna solo líneas '+' del git diff HEAD
- `tests/test_issue_35.py::test_detect_cast_finds_as_never_paren`: detect_full_arg_cast detecta '} as never)' en línea nueva y retorna esa línea
- `tests/test_issue_35.py::test_detect_cast_finds_as_any_paren`: detect_full_arg_cast detecta '} as any)' en línea nueva y retorna esa línea
- `tests/test_issue_35.py::test_detect_cast_finds_as_unknown_as_ident_paren`: detect_full_arg_cast detecta '} as unknown as BuildAppOptions)' en línea nueva y retorna esa línea
- `tests/test_issue_35.py::test_detect_cast_ignores_property_cast`: detect_full_arg_cast retorna None para '  db: mockDb as never,' (sin ')' cerrando argumento)
- `tests/test_issue_35.py::test_detect_cast_ignores_variable_cast`: detect_full_arg_cast retorna None para '  const x = fakeDb as never;'
- `tests/test_issue_35.py::test_detect_cast_untracked_file_with_cast_detected`: archivo de test nuevo (sin trackear) con 'buildApp({ db } as never)' en cualquier línea → detect_full_arg_cast retorna esa línea
- `tests/test_issue_35.py::test_detect_cast_tracked_existing_line_ignored`: archivo trackeado donde la línea '} as never)' ya existía en HEAD (no es '+') → detect_full_arg_cast retorna None
- `tests/test_issue_35.py::test_red_phase_rejects_full_arg_cast_with_feedback`: run_red_phase con coder que escribe '} as never)' → output contiene feedback citando la línea; coder es invocado de nuevo en el siguiente intento

**Archivos de implementación:**
- `scripts/tdd_runner.py`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T6: Regla 7 en build_red_prompt sobre actualización de firma

Agregar regla 7 siempre presente en build_red_prompt: actualizar tests existentes al cambiar firma, no usar casts sobre argumento completo

**Tests:**
- `tests/test_issue_35.py::test_build_red_prompt_contains_firma_rule`: build_red_prompt(spec, task) contiene texto sobre actualizar tests existentes al cambiar firma y sobre no usar casts sobre el argumento completo
- `tests/test_issue_35.py::test_build_red_prompt_firma_rule_always_present`: La regla aparece tanto si impl_files es lista vacía como si tiene archivos
- `tests/test_issue_35.py::test_build_red_prompt_rule_count`: El prompt contiene al menos 7 reglas numeradas (la nueva es la 7)

**Archivos de implementación:**
- `scripts/tdd_runner.py`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T7: Test e2e RED: firma nueva + test existente → commit sin revert ni casts

Tests de integración de run_red_phase con repo git real: escenario exitoso (TS2353 aceptado, ambos archivos commiteados) y escenario de agotamiento (todos los archivos revertidos)

**Tests:**
- `tests/test_issue_35.py::test_e2e_red_new_signature_commits_both_files`: repo git real con impl_file que declara 'interface BuildAppOptions' con prop nueva; coder actualiza test existente trackeado y crea test nuevo; TS2353 aceptado (tipo en impl_file); RED retorna True; git log contiene commit de test; ambos archivos de test presentes y no revertidos
- `tests/test_issue_35.py::test_e2e_red_exhausted_static_attempts_reverts_all`: run_red_phase con falla estática persistente en todos los intentos y usuario elige 'abortar': git status queda limpio (sin archivos modificados)

**Archivos de implementación:**
- `scripts/tdd_runner.py`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

### T8: Actualizar AGENTS.md

Documentar lógica extendida de errores TS aceptables, no-revert entre intentos estáticos y detección de casts de argumento

**Tests:**
- `tests/test_issue_35.py::test_agents_md_mentions_ts2353`: AGENTS.md contiene la cadena 'TS2353'
- `tests/test_issue_35.py::test_agents_md_mentions_as_never_cast`: AGENTS.md contiene la cadena 'as never'

**Archivos de implementación:**
- `AGENTS.md`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

## Fuera de alcance

- Modificar la fase GREEN o REFACTOR (el issue es exclusivamente sobre RED)
- Cambiar el comportamiento de back-to-RED (issue #28)
- Soporte para otros lenguajes además de TS/JS en la lógica extendida de tipos
- Resolver imports de node_modules o barrel files (solo imports relativos a impl_files)
- UI o CLI para configurar los patrones de cast detectados

## Riesgos

- La resolución de imports relativos (.js → .ts) puede fallar con barrel files o re-exports; falsos negativos asumidos y documentados
- El regex de tipo nombrado puede fallar si el mensaje de tsc cambia entre versiones de TypeScript; acotado a TS2353 y TS2345 que son estables
- detect_full_arg_cast tiene falsos negativos documentados: '} as never)' en línea separada del objeto no se detecta; el prompt cubre el resto
- check_test_files_static cambia su firma (nuevo parámetro impl_files); todos los call-sites en tdd_runner.py deben actualizarse; los tests existentes de #33 siguen pasando porque el parámetro es opcional (None por defecto)

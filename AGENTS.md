# Convenciones para Agentes de Código

Este documento define el workflow y convenciones que todos los agentes de código (AI coding assistants) deben seguir al trabajar en este repositorio.

## Principios fundamentales

1. **GitHub es la fuente de verdad**: todos los issues, tareas y estado del proyecto viven en GitHub Issues
2. **Cada cambio necesita un issue**: no commitear sin issue asociado
3. **Nunca editar `backlog.md` a mano**: es generado automáticamente por `scripts/backlog.py`
4. **Nunca commitear directamente a `main`**: siempre trabajar en ramas de feature
5. **Tests antes de commitear**: verificar que `python3 -m unittest discover -s tests -v` pasa

## Idiomas

- **Documentación, mensajes de commit, issues, PRs**: español (variante rioplatense)
- **Código, identificadores, comentarios en código**: inglés

## Workflow completo

### 1. Tomar un issue

```bash
python3 scripts/backlog.py take <N>
```

Este comando ejecuta el flujo completo: **diseño → aprobación → implementación TDD**.

**Fase 1: Diseño**

- Verifica que el working tree esté limpio
- Verifica que el issue esté abierto y no WIP por otra persona
- Hace checkout a `main` y pull
- Crea (o hace checkout) la rama `issue/<N>-<slug-del-titulo>`
- Asigna el issue a ti (@me)
- Cambia el label de `status:todo` a `status:wip`
- Pushea la rama
- Comenta en el issue: "🚧 Tomado. Rama: `issue/...`"
- Arranca una **entrevista con el agente Tech Lead** para diseñar la implementación
  - El agente lee el issue, DESIGN.md, AGENTS.md y el código existente
  - Propone un diseño inicial
  - Presenta decisiones técnicas en tandas de 1-3, con opciones y recomendaciones
  - Pregunta sobre: estructura de archivos, librerías, contratos, modelo de datos, testing, manejo de errores
  - No hay decisiones implícitas: todo se acuerda explícitamente
- Al finalizar, el agente genera una **especificación JSON** con:
  - Resumen del diseño
  - Tabla de decisiones acordadas
  - Archivos a crear/modificar
  - Tareas divididas en unidades pequeñas (cada una con tests específicos)
  - Comando de test (`test_command`)
  - Riesgos y fuera de alcance
- **Preview y aprobación**: se muestra la spec renderizada y se ofrecen opciones:
  - **[a]probar**: guarda la spec en `docs/specs/issue-N.md`, la commitea, y publica un comentario en el issue. Después arranca automáticamente la fase de implementación TDD.
  - **[e]ditar**: edita la spec en `$EDITOR` y re-valida
  - **[s]eguir**: continúa conversando con el agente Tech Lead para ajustar el diseño. Podés hacer preguntas, pedir cambios, o refinar decisiones. Cuando el agente genere una nueva spec válida, vuelve al menú de preview con la spec actualizada.
  - **[x] salir**: guarda como draft en `docs/specs/issue-N.md` (estado `draft`). Se puede retomar después corriendo `take <N>` de nuevo. Si existe una sesión guardada para ese issue, se resume desde ahí.

**Fase 2: Implementación TDD**

Si la spec fue aprobada (o ya está en estado `approved` o `implementing`), el harness ejecuta automáticamente:

Para cada tarea pendiente, en orden:
1. **RED**: invoca al agente de código (configurable con `BACKLOG_CODER_CMD` y `BACKLOG_CODER_MODEL`) con la spec y la tarea: "escribí SOLO los tests de esta tarea, no toques código de producción". El prompt incluye:
   - Si la tarea tiene `test_support_files` (ej: vitest.config.ts, pytest.ini), se listan con instrucción de crearlos/ajustarlos para que los tests se ejecuten y fallen por assert/import faltante, nunca por infraestructura faltante
   - Los archivos de `impl_files` se marcan explícitamente como prohibidos en RED
   
   Verifica:
   - Solo se modifican archivos de test y test_support_files
   - Los tests **deben fallar** (si pasan, reintenta una vez y después pregunta al usuario)
   - Si el test command no ejecuta ningún test (detecta señales como "No test files found", "Ran 0 tests", "No projects matched"), se trata como error de infraestructura: revierte, reintenta con feedback al coder sobre la corrida vacía
   - En el primer RED, muestra el output y pide confirmar que no es un error de infraestructura
   - Commit: `test: <tarea> (#N)`
2. **GREEN**: invoca al agente: "implementá lo mínimo para que pasen los tests, sin modificar los tests". El prompt incluye `test_support_files` (pueden modificarse en GREEN) e `impl_files`.
   
   Verifica:
   - Los tests **deben pasar** completos (sin regresiones)
   - Los archivos de test no cambiaron desde RED
   - Una corrida vacía cuenta como intento fallido (con feedback que incluye la señal detectada)
   - Hasta 3 intentos con el output de los tests como feedback
   - Commit: `feat|fix: <tarea> (#N)` según el type del issue
3. **REFACTOR** (opcional): invoca al agente: "refactorizá si es necesario (o respondé SIN_REFACTOR)". Si hay cambios, verifica que los tests sigan pasando; si fallan, revierte. Commit: `refactor: <tarea> (#N)`.
4. El progreso de cada fase se marca en `docs/specs/issue-N.md` con checkboxes.

**Detección de desviaciones (`/DESVIO`):**

Si el agente de código necesita tomar una decisión no prevista en la spec, debe escribir una línea `/DESVIO <explicación>` y frenar. El harness:
- Revierte los cambios no commiteados
- Muestra la explicación al usuario y pide una decisión
- Agrega la decisión a la spec como nueva entrada (`D2`, `D3`, ...)
- Commitea: `docs: decisión durante implementación (#N)`
- Reintenta la fase

**Al terminar:**

- Todos los tests pasan
- Spec en estado `done`
- Commit: `docs: spec completada (#N)`
- Mensaje: "Siguiente paso: `python3 scripts/backlog.py pr N`"

**Flags opcionales:**

- `--plan-only`: solo ejecuta la fase de diseño, no implementa
- `--no-plan`: comportamiento legacy (solo rama y WIP, sin diseño ni TDD)

**Comandos relacionados:**

```bash
python3 scripts/backlog.py impl <N>
```

Ejecuta solo la fase de implementación TDD (la spec debe estar en estado `approved` o `implementing`). Útil si interrumpiste `take` después de aprobar.

### 2. Variables de entorno

**Para el Tech Lead (fase de diseño):**

- `BACKLOG_LLM_BASE_URL`: URL de la API de LLM (default: `https://inference-api.nousresearch.com/v1`)
- `BACKLOG_LLM_MODEL`: Modelo a usar (default: `anthropic/claude-sonnet-4.6`)
- `BACKLOG_LLM_MAX_TOKENS`: Máximo de tokens de salida (default: `16000`)
- `BACKLOG_LLM_TIMEOUT`: Timeout HTTP en segundos (default: `300`)
- `NOUS_API_KEY`: API key (se lee de env o `~/.config/model-keys.env`)

**Para el agente de código (fase TDD):**

- `BACKLOG_CODER_CMD`: Comando para invocar el coder (default: `~/.local/bin/oc run`)
- `BACKLOG_CODER_MODEL`: Modelo para el coder (default: `nous/anthropic/claude-sonnet-4.5`). Si está vacío, no se agrega flag `--model`.
- `BACKLOG_CODER_TIMEOUT`: Timeout en segundos para cada invocación del coder (default: `1800`)

**Logs:**

- Sesiones de diseño: `.backlog/sessions/<timestamp>.json` y `.md`
- Logs de TDD: `.backlog/runs/issue-N/<task>-<fase>-<intento>.log`

### 3. Estructura de specs

Las specs se guardan en `docs/specs/issue-N.md` y tienen:

**Front matter:**

```yaml
---
issue: N
status: draft|approved|implementing|done
test_command: python3 -m unittest discover -s tests -v
---
```

**Cuerpo:**

- Resumen
- Tabla de decisiones de diseño
- Archivos afectados
- Tareas con checkboxes de progreso:
  - Cada tarea lista sus tests (en `tests[]`) y archivos de implementación (`impl_files`)
  - Opcionalmente, `test_support_files` para archivos de config o fixtures que los tests necesitan (ej: `vitest.config.ts`, `tsconfig.test.json`, `pytest.ini`)
  - Los `test_support_files` pueden crearse/modificarse en RED y GREEN, pero no en REFACTOR
  - Checkboxes: `[ ] RED: tests escritos y fallan`, `[ ] GREEN: tests pasan`, `[ ] REFACTOR: código limpio`
- Fuera de alcance
- Riesgos

**Nota sobre `test_command`**: si el comando usa operadores de shell (`&&`, `||`, `|`, `;`, `>`, `<`, `$()`, backticks), se ejecuta con `sh -c`. Esto permite comandos como:
```
python3 -m unittest discover -s tests -v && corepack pnpm test
```

Las specs se commitean en la rama del issue y se revisan en el PR.

### 4. Crear PR

```bash
python3 scripts/backlog.py pr <N> [--draft]
```

Este comando:
- Verifica que estés en la rama correcta con commits adelante de `main`
- Pushea la rama
- Crea PR con título: "<título del issue> (#N)"
- Body del PR incluye "Closes #N" y resumen de commits
- Cambia label del issue de `status:wip` a `status:review`

### 5. Merge

```bash
python3 scripts/backlog.py merge <N>
```

Este comando:
- Encuentra el PR asociado al issue
- Verifica que los checks pasen (o pide confirmación)
- Hace squash merge y borra la rama
- Vuelve a `main` y hace pull
- El issue se cierra automáticamente por "Closes #N"

## Comandos útiles

### Ver estado actual

```bash
python3 scripts/backlog.py status
```

Muestra rama actual, issue asociado, estado y labels.

### Listar issues

```bash
python3 scripts/backlog.py list        # solo abiertos
python3 scripts/backlog.py list --all  # todos
```

### Crear nuevo issue

**Modo interactivo** (recomendado, con entrevista guiada por IA):

```bash
python3 scripts/backlog.py new ["idea inicial opcional"]
```

El comando arranca una sesión interactiva con un agente Analista que te entrevista para crear una especificación completa. El agente:
- Hace preguntas priorizadas en tandas cortas
- Lee el contexto del repo y issues relacionados
- Propone opciones con defaults recomendados
- Detecta si el issue debe partirse en varios
- Genera una especificación estructurada y completa

Comandos durante la entrevista: `/listo` (finalizar), `/borrador` (ver estado actual), `/cancelar`.

Requisitos: `NOUS_API_KEY` en el environment o en `~/.config/model-keys.env`.

**Modo no interactivo** (para scripts o cuando ya tenés la spec):

```bash
python3 scripts/backlog.py new "Título del issue" \
  --type {feat|fix|chore|docs|infra} \
  [--area web|api|agents|admin|infra] \
  [--phase {0|1|2|3}] \
  [--body "Descripción"] \
  [--body-file path/to/description.md] \
  [--no-interview]
```

### Inicializar labels y milestones (idempotente)

```bash
python3 scripts/backlog.py init
```

### Renderizar backlog.md

```bash
python3 scripts/backlog.py render          # genera archivo
python3 scripts/backlog.py render --check  # verifica si cambió (exit 1 si cambió)
```

### Sincronizar backlog.md (solo desde main)

```bash
python3 scripts/backlog.py sync
```

Renderiza, commitea si cambió, pushea. Típicamente ejecutado por CI.

## Estructura de branches

- `main`: rama principal, protegida, solo squash merge
- `issue/<N>-<slug>`: rama de feature para issue #N
  - Ejemplo: `issue/42-add-user-registration`

## Labels

### Status (mutuamente exclusivos)
- `status:todo`: en backlog, no iniciado
- `status:wip`: en progreso
- `status:review`: en revisión (PR abierto)

### Type (requerido)
- `type:feat`: nueva funcionalidad
- `type:fix`: corrección de bug
- `type:chore`: mantenimiento, refactor
- `type:docs`: documentación
- `type:infra`: infraestructura, DevOps, CI/CD

### Area (opcional, múltiple)
- `area:web`: frontend web
- `area:api`: backend API
- `area:agents`: agentes de IA
- `area:admin`: herramientas de admin
- `area:infra`: infraestructura

### Otros
- `blocked`: bloqueado por dependencia externa

## Milestones (fases)

- **Fase 0 - Fundaciones**: setup inicial, infraestructura base
- **Fase 1 - MVP individual**: funcionalidad core para usuario individual
- **Fase 2 - Retención y comunidad**: features de engagement y comunidad
- **Fase 3 - Calidad y escala**: optimización, observabilidad, escala

## Reglas de commits

1. Mensaje en español, formato conventional commits
2. Incluir `(#N)` al final del subject line
3. Subject line <= 72 caracteres
4. Body opcional con más contexto si es necesario
5. No commitear secrets, `.env`, o archivos sensibles
6. Revisar `git diff` antes de commitear

## Reglas de PRs

1. Título: igual al título del issue + `(#N)`
2. Body debe incluir:
   - `Closes #N`
   - Resumen de cambios
   - Cómo se probó
3. PR debe tener label `status:review` en el issue asociado
4. Squash merge solamente (configurado en GitHub)
5. Borrar rama después de merge (automático)

## Hooks y CI

- **CI workflow** (`.github/workflows/ci.yml`): corre tests en PRs y pushes a main
- **Backlog sync workflow** (`.github/workflows/backlog-sync.yml`): actualiza `backlog.md` automáticamente en eventos de issues/PRs

## Ejemplo de sesión completa

```bash
# 1. Ver issues disponibles
python3 scripts/backlog.py list

# 2. Tomar issue #5
python3 scripts/backlog.py take 5
# → Estás en rama issue/5-implement-login

# 3. Implementar
# ... hacer cambios ...
python3 -m unittest discover -s tests -v  # verificar tests

# 4. Commit
git add .
git commit -m "feat: implement login form and auth flow (#5)"

# 5. Más commits si es necesario
git commit -m "test: add integration tests for login (#5)"

# 6. Crear PR
python3 scripts/backlog.py pr 5

# 7. Después de review y approval, mergear
python3 scripts/backlog.py merge 5
# → De vuelta en main, issue #5 cerrado
```

## Troubleshooting

**Working tree dirty al hacer `take`:**
```bash
git status
git stash  # o commitear cambios
```

**Rama ya existe pero no está actualizada:**
```bash
git checkout main
git pull
git checkout issue/N-slug
git rebase main
```

**PR checks fallan:**
Revisar output de CI, corregir, hacer push de fix.

**Issue bloqueado:**
Agregar label `blocked`, dejar comentario explicando bloqueo, tomar otro issue.

## Referencias

- Repositorio: [mblasi/training](https://github.com/mblasi/training)
- Diseño del proyecto: `docs/DESIGN.md`
- Contributing guide: `CONTRIBUTING.md`
- Backlog actual: `backlog.md`

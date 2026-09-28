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

Este comando:
- Verifica que el working tree esté limpio
- Verifica que el issue esté abierto y no WIP por otra persona
- Hace checkout a `main` y pull
- Crea (o hace checkout) la rama `issue/<N>-<slug-del-titulo>`
- Asigna el issue a ti (@me)
- Cambia el label de `status:todo` a `status:wip`
- Pushea la rama
- Comenta en el issue: "🚧 Tomado. Rama: `issue/...`"

### 2. Implementar

- Hacer los cambios necesarios en la rama `issue/<N>-...`
- Commits pequeños y atómicos
- Mensajes en formato: `type: description (#N)` (conventional commits + número de issue)
  - Tipos: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `style`, `perf`, `ci`, `build`
  - Ejemplo: `feat: add user registration form (#42)`
- Correr tests: `python3 -m unittest discover -s tests -v`
- Nunca hacer `git commit --no-verify` ni saltear hooks

### 3. Crear PR

```bash
python3 scripts/backlog.py pr <N> [--draft]
```

Este comando:
- Verifica que estés en la rama correcta con commits adelante de `main`
- Pushea la rama
- Crea PR con título: "<título del issue> (#N)"
- Body del PR incluye "Closes #N" y resumen de commits
- Cambia label del issue de `status:wip` a `status:review`

### 4. Merge

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

```bash
python3 scripts/backlog.py new "Título del issue" \
  --type {feat|fix|chore|docs|infra} \
  [--area web|api|agents|admin|infra] \
  [--phase {0|1|2|3}] \
  [--body "Descripción"] \
  [--body-file path/to/description.md]
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

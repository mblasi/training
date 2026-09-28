# Trainia

Trainia (trainia.blasi.ar): app de entrenamiento autogestionada con un equipo de agentes IA (entrenador, nutricionista, psicólogo deportivo).

- Diseño: [docs/DESIGN.md](docs/DESIGN.md)
- Backlog: [backlog.md](backlog.md)

## Flujo de trabajo

Este proyecto usa un workflow basado en GitHub Issues manejado por `scripts/backlog.py`.

### Comandos principales

```bash
# Ver issues disponibles
python3 scripts/backlog.py list

# Crear nuevo issue (modo interactivo con agente IA)
python3 scripts/backlog.py new

# Tomar un issue (diseño + implementación TDD automática)
python3 scripts/backlog.py take <N>

# Solo diseño (sin implementar)
python3 scripts/backlog.py take <N> --plan-only

# Solo implementación (spec ya aprobada)
python3 scripts/backlog.py impl <N>

# Crear PR
python3 scripts/backlog.py pr <N>

# Mergear PR
python3 scripts/backlog.py merge <N>

# Ver estado actual
python3 scripts/backlog.py status

# Ver todos los comandos
python3 scripts/backlog.py --help
```

### Workflow completo

1. `new` → entrevista con agente Analista, crea issue estructurado
2. `take <N>` → crea rama, diseño interactivo con agente Tech Lead, genera spec, implementación TDD automática
   - Fase de diseño: entrevista para acordar decisiones técnicas, genera `docs/specs/issue-N.md`
   - Fase TDD: RED → GREEN → REFACTOR por cada tarea, verificado por el harness
   - Specs y progreso se commitean en la rama
3. `pr <N>` → crea PR, marca issue como en revisión
4. `merge <N>` → squash merge, cierra issue, vuelve a main

Ver [AGENTS.md](AGENTS.md) para documentación completa y convenciones.

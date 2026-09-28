# training

App de entrenamiento autogestionada con un equipo de agentes IA (entrenador, nutricionista, psicólogo deportivo).

- Diseño: [docs/DESIGN.md](docs/DESIGN.md)
- Backlog: [backlog.md](backlog.md)

## Flujo de trabajo

Este proyecto usa un workflow basado en GitHub Issues manejado por `scripts/backlog.py`.

### Comandos principales

```bash
# Ver issues disponibles
python3 scripts/backlog.py list

# Tomar un issue
python3 scripts/backlog.py take <N>

# Ver estado actual
python3 scripts/backlog.py status

# Crear PR
python3 scripts/backlog.py pr <N>

# Mergear PR
python3 scripts/backlog.py merge <N>

# Crear nuevo issue (modo interactivo con agente IA)
python3 scripts/backlog.py new

# Crear issue directo (sin entrevista)
python3 scripts/backlog.py new "Título" --type feat --no-interview

# Ver todos los comandos
python3 scripts/backlog.py --help
```

### Workflow completo

1. `take <N>` → crea rama `issue/<N>-<slug>`, asigna issue, marca como WIP
2. Implementar en la rama, commits con formato `type: description (#N)`
3. Correr tests: `python3 -m unittest discover -s tests -v`
4. `pr <N>` → crea PR, marca issue como en revisión
5. `merge <N>` → squash merge, cierra issue, vuelve a main

Ver [AGENTS.md](AGENTS.md) para documentación completa y convenciones.

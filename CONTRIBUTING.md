# Guía de Contribución

Gracias por contribuir al proyecto. Este documento resume el workflow de desarrollo.

## Requisitos previos

- Git instalado y configurado
- GitHub CLI (`gh`) instalado y autenticado
- Python 3.12+

## Flujo de trabajo (resumen)

1. **Tomar un issue**: `python3 scripts/backlog.py take <N>`
2. **Implementar** en la rama `issue/<N>-<slug>`
3. **Commitear** cambios con mensajes en formato: `type: description (#N)`
4. **Correr tests**: `python3 -m unittest discover -s tests -v`
5. **Crear PR**: `python3 scripts/backlog.py pr <N>`
6. **Mergear** (después de review): `python3 scripts/backlog.py merge <N>`

## Convenciones

- **Idioma en docs/commits**: español (rioplatense)
- **Idioma en código**: inglés
- **Commits**: conventional commits + `(#N)` con número de issue
- **Tests**: obligatorio correr y pasar tests antes de PR
- **Backlog**: nunca editar `backlog.md` a mano (es generado automáticamente)
- **Branch principal**: `main` (protegida, squash merge only)

## Detalles completos

Ver `AGENTS.md` para documentación completa del workflow, comandos disponibles, convenciones de branches, labels, y ejemplos.

## Crear nuevo issue

Preferible usar GitHub UI con los templates, o bien:

```bash
python3 scripts/backlog.py new "Título" --type {feat|fix|chore|docs|infra}
```

## Soporte

Para dudas o problemas, abrir un issue con label `type:docs`.

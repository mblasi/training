# Guía de Contribución

Gracias por contribuir al proyecto. Este documento resume el workflow de desarrollo.

## Requisitos previos

- Git instalado y configurado
- GitHub CLI (`gh`) instalado y autenticado
- Python 3.12+

## Flujo de trabajo (resumen)

1. **Crear issue** (opcional): `harness new` (modo interactivo con IA)
2. **Tomar un issue**: `harness take <N>`
   - Crea rama `issue/<N>-<slug>`, marca como WIP
   - **Fase de diseño**: entrevista interactiva con agente Tech Lead
   - Genera `docs/specs/issue-N.md` con decisiones acordadas
   - **Fase TDD**: implementación automática con ciclo RED → GREEN → REFACTOR
   - Todos los tests pasan al finalizar
3. **Crear PR**: `harness pr <N>`
4. **Mergear** (después de review): `harness merge <N>`

Comandos opcionales:
- `take <N> --plan-only`: solo diseño, sin implementación
- `impl <N>`: solo implementación (si spec ya aprobada)
- `take <N> --no-plan`: comportamiento legacy (sin diseño ni TDD)

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

**Modo recomendado (interactivo con IA):**

```bash
harness new ["idea inicial opcional"]
```

El agente Analista te entrevista y genera una especificación completa.

**Modo directo (sin entrevista):**

```bash
harness new "Título" --type {feat|fix|chore|docs|infra} --no-interview
```

## /DESVIO: regla para agentes de código

Si durante la implementación TDD el agente de código necesita tomar una decisión no prevista en la spec, debe:

1. Escribir una línea `/DESVIO <explicación>` en su output
2. Frenar sin hacer cambios

El harness detectará el desvío, preguntará al usuario, registrará la decisión en la spec, y reintentará la fase.

## Soporte

Para dudas o problemas, abrir un issue con label `type:docs`.

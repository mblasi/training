# Trainia

Trainia (trainia.blasi.ar): app de entrenamiento autogestionada con un equipo de agentes IA (entrenador, nutricionista, psicólogo deportivo).

- Diseño: [docs/DESIGN.md](docs/DESIGN.md)
- Backlog: [backlog.md](backlog.md)

## Desarrollo

### Prerrequisitos

- Node 24 LTS (ver `.nvmrc`)
- Corepack habilitado: `corepack enable`
- JDK 21 (para Firebase Auth Emulator en tests de integración)

### Comandos raíz

Desde la raíz del monorepo:

```bash
corepack pnpm install         # instalar dependencias
corepack pnpm lint            # lint en todos los workspaces
corepack pnpm typecheck       # typecheck en todos los workspaces
corepack pnpm test            # tests en todos los workspaces
```

### apps/api

API backend con Fastify. Servidor de desarrollo:

```bash
corepack pnpm --filter ./apps/api dev
```

#### Base de datos

apps/api usa Postgres 18 con pgvector para almacenar usuarios, perfiles, proveedores LLM, rutas de agentes, llamadas y prompts.

**Comandos DB:**

```bash
# Generar migraciones (después de cambiar schema)
corepack pnpm --filter @trainia/api db:generate

# Ejecutar migraciones
corepack pnpm --filter @trainia/api db:migrate

# Seed de datos iniciales (idempotente)
corepack pnpm --filter @trainia/api db:seed

# Tests de integración (requiere DATABASE_URL)
corepack pnpm --filter @trainia/api test:integration
```

**Desarrollo local:**

Ver `docker-compose.yml` en la raíz para referencia de cómo levantar Postgres localmente. Los tests de integración están configurados para CI únicamente hasta que se configure la DB de staging (issue #13).

### apps/admin

Panel de administración React+Vite. Servidor de desarrollo:

```bash
corepack pnpm --filter ./apps/admin dev
```

Build de producción:

```bash
corepack pnpm --filter ./apps/admin build
```

### apps/mobile

App móvil con Expo. Servidor de desarrollo:

```bash
corepack pnpm --filter ./apps/mobile start
```

Servidor web:

```bash
corepack pnpm --filter ./apps/mobile web
```

Build web:

```bash
corepack pnpm --filter ./apps/mobile exec expo export --platform web --output-dir dist-web
```

**Nota**: Expo SDK 57 funciona con pnpm en modo isolated (sin `node-linker=hoisted`). El setup usa `metro.config.js` para resolver workspaces y `babel.config.cjs` con `babel-preset-expo`.

### Firebase Auth

Las apps usan Firebase Auth para autenticación. Variables de entorno necesarias:

**Para desarrollo:**
- `FIREBASE_PROJECT_ID`: ID del proyecto Firebase (en producción) o `demo-trainia` (desarrollo local con emulador)
- `FIREBASE_AUTH_EMULATOR_HOST`: URL del emulador (ej: `127.0.0.1:9099`). Si está definida, la API se conecta al emulador en lugar de Firebase real
- `EXPO_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST`: URL del emulador para apps cliente (admin y mobile)
- `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID`: Client ID de Google OAuth para sign-in (solo producción)
- `ADMIN_EMAILS`: Lista de emails separados por coma que tienen rol admin (ej: `admin@example.com,otro@example.com`)

**Tests de integración:**

Los tests de integración de auth requieren el Firebase Auth Emulator. En CI esto se maneja automáticamente con `firebase emulators:exec`. Para desarrollo local:

```bash
# Instalar firebase-tools si no está
pnpm install

# Correr tests de integración con emulador
firebase emulators:exec --only auth --project demo-trainia "pnpm --filter @trainia/api test:integration && pnpm --filter @trainia/mobile test:integration"
```

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

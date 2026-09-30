---
issue: 10
status: implementing
test_command: python3 -m unittest discover -s tests -v && corepack pnpm install --frozen-lockfile && corepack pnpm lint && corepack pnpm typecheck && corepack pnpm test
---

# Spec de implementación: Postgres + pgvector local (Docker) + Drizzle + migraciones iniciales

## Resumen

Postgres 18 + pgvector + Drizzle en apps/api: docker-compose, schema inicial (6 tablas), migraciones SQL commiteadas, seed idempotente, /health con chequeo DB, tests de integración en CI

## Decisiones de diseño

| ID | Topic | Opciones | Elegida | Rationale |
|----|-------|----------|---------|-----------|
| D1 | Ubicación de drizzle.config.ts | apps/api/ (junto al código), raíz del monorepo | apps/api/drizzle.config.ts | Rutas relativas al schema y migrations; scripts db:* en apps/api/package.json |
| D2 | Driver de Postgres para Drizzle | pg (node-postgres), postgres.js | pg 8.23.0 con @types/pg 8.23.1 | Versiones verificadas contra npm; el más probado con pgvector |
| D3 | Tests de integración con DB en CI | Service container GH Actions, Mock del pool, Docker Compose en CI | Service container pgvector/pgvector:0.8.6-pg18 en job node de CI | pnpm test corre solo unit tests; test:integration falla con mensaje claro si no hay DATABASE_URL |
| D4 | Versión de Postgres | Postgres 16, Postgres 18 | Postgres 18 vía pgvector/pgvector:0.8.6-pg18 | EOL 2030; uuidv7() nativo en PG18 |
| D5 | Entorno de desarrollo local | Docker local, GCE con Postgres, Solo CI | docker-compose.yml como referencia; tests de integración solo-CI hasta que llegue #13 | brain-workspace no tiene Docker; #13 proveerá Cloud SQL staging con DATABASE_URL |
| D6 | docker-compose.yml y criterio de aceptación | Compose como referencia + validación en CI, Cloud SQL Auth Proxy, Sin docker-compose | docker-compose.yml en el repo; criterio validado funcionalmente en CI + test Python estructural del yml | Útil para futuros contribuidores con Docker; test Python lee el yml directamente, no el README |
| D7 | DB de desarrollo fuera de CI | GCE con tunnel SSH, Cloud SQL staging, Solo-CI con error claro | test:integration falla con error claro si no hay DATABASE_URL; DB dev/staging llega con #13 | Honesto con el estado actual; no bloquea el issue |
| D8 | Estructura del schema Drizzle | Un archivo por dominio, Un archivo por tabla, Todo en schema.ts | Un archivo por dominio: users.ts, llm.ts, agent_prompts.ts + index.ts | Escala bien; cada feature issue agrega su propio archivo de schema |
| D9 | Instanciación del cliente Drizzle | Singleton exportado, Factory createDb(url), Plugin Fastify | createDb(url: string): { pool, db }; buildApp({ db }) recibe el cliente | Inyectable en tests sin monkey-patching; desacoplado de env vars |
| D10 | /health con chequeo de DB | Timeout fijo, Timeout configurable por env DB_HEALTH_TIMEOUT_MS, Sin timeout explícito | DB_HEALTH_TIMEOUT_MS con default 2000ms; 200 ok/db:ok vs 503 degraded/db:error | Configurable sin redeploy |
| D11 | Seed — contenido y estrategia | Valores concretos hardcodeados, Placeholders, Idempotente ON CONFLICT DO NOTHING | Seed idempotente con onConflictDoNothing(); exporta SEED_PROVIDERS, SEED_ROUTES, runSeed(db) | No pisa ediciones del admin; testeable sin DB con un db falso |
| D12 | Extensión de healthStatusSchema en shared | db opcional, db requerido + actualizar todos los tests | db requerido z.enum(['ok','error']); status z.enum(['ok','degraded']); actualizar fixtures en shared, admin y mobile | Greenfield sin clientes en producción; sin capas de compatibilidad |
| D13a | Tipo de IDs | uuid v4 gen_random_uuid(), uuid v7 uuidv7(), serial/bigserial | UUID v7 con uuidv7() nativo de Postgres 18 como default en DB | Ordenable por tiempo, mejor para índices B-tree; nativo en PG18 |
| D13b | PK de llm_routes | PK compuesta (agent, provider_id), PK = agent, ID surrogate | PK = agent (text); una fila por agente; fallback en la misma fila | Coincide con el modelo del DESIGN.md; una ruta activa por agente |
| D13c | Enums en DB | pgEnum de Postgres, text con CHECK constraint + text({ enum: [] }) en Drizzle | text con CHECK constraint vía sql`` en drizzle check(); tipo TS via text({ enum: [...] }) | ALTER TYPE en Postgres es costoso; text + check es más flexible para migraciones futuras |
| D14 | Migraciones SQL commiteadas | SQL commiteado en repo, Generado en CI en cada deploy | 0000_enable_vector.sql (--custom) + 0001_core.sql (drizzle-kit generate); meta/_journal.json + meta/*_snapshot.json commiteados; CI verifica drift con git diff --exit-code | drizzle-kit no genera CREATE EXTENSION; dos migraciones nombradas explícitamente; auditable y reproducible |
| D15 | buildApp db requerido y arranque del servidor | db opcional con rama sin-db, db requerido siempre | buildApp({ db }) con db requerido; apps/api/src/index.ts llama requireDatabaseUrl(process.env) y crea el cliente antes de buildApp | Sin ramas muertas en producción; falla rápido si falta DATABASE_URL |
| D16 | Contrato de /health durante T1–T9 y test viejo de shared | db requerido; `test_healthstatus_parse_valid_object` se actualiza con db:'ok'. El cambio de contrato es atómico en los 4 workspaces: T1 incluye apps/api/src/app.ts y apps/api/test/health.test.ts. Sin cliente de DB (llega en T10), /health responde status 'degraded', db 'error', HTTP 503; T10 lo reemplaza por el chequeo real SELECT 1 con timeout | Nunca un db 'ok' falso; sin capas de compat. Decisión tomada durante implementación |  |
| D17 | Cómo inspeccionar el schema Drizzle en tests (T5–T7) | usar la API real de drizzle-orm 0.45.3 | `getTableConfig(t).columns` es un ARRAY: buscar por nombre (`columns.find(c => c.name === 'id')`), nunca indexar `columns.id`. SQL de defaults y CHECKs: `new PgDialect().sqlToQuery(col.default).sql` === `uuidv7()` y `sqlToQuery(check.value).sql` contiene los valores permitidos (nunca `.toString()`, devuelve `[object Object]`). PK de columna: `col.primary === true` (`config.primaryKeys` solo lista PK compuestas, queda vacío). FK: `config.foreignKeys[i].reference()` → `{columns, foreignTable, foreignColumns}`, verificar `getTableConfig(foreignTable).name`. Tipos: `col.columnType` (`PgUUID`, `PgText`, `PgInteger`, `PgTimestamp`, `PgJsonb`, …) | Verificado ejecutando drizzle-orm 0.45.3 instalado en apps/api. RED de T5 original usaba mal la API (volver a RED, #28) |
| D18 | Los tests asumen que `config.columns` es un objeto con propiedades (columns.id, columns.firebase_uid, etc.) pero según la decisión "Cómo inspeccionar el schema Drizzle en tests (T5–T7)" se establece que "columns es un ARRAY: buscar por nombre (columns.find(c => c.name === 'id'))". Los tests de RED están usando mal la API de drizzle-orm y necesitan ser corregidos antes de poder implementar. | Correcto: los tests de RED de T5 usan mal la API de drizzle-orm 0.45.3. Rehacer los tests según D17: columns es array (find por name), SQL de default/checks vía new PgDialect().sqlToQuery(x).sql (nunca toString), PK de columna vía col.primary, FK vía foreignKeys[i].reference() + getTableConfig(foreignTable).name, tipos vía col.columnType. Los tests deben fallar solo porque falta src/db/schema (import), no por la API. | Correcto: los tests de RED de T5 usan mal la API de drizzle-orm 0.45.3. Rehacer los tests según D17: columns es array (find por name), SQL de default/checks vía new PgDialect().sqlToQuery(x).sql (nunca toString), PK de columna vía col.primary, FK vía foreignKeys[i].reference() + getTableConfig(foreignTable).name, tipos vía col.columnType. Los tests deben fallar solo porque falta src/db/schema (import), no por la API. | Decisión tomada durante implementación |

## Archivos afectados

- **create** `docker-compose.yml`: Postgres 18 + pgvector para desarrollo local con Docker (referencia)
- **modify** `packages/shared/src/health.ts`: status z.enum(['ok','degraded']), db z.enum(['ok','error']) requerido
- **modify** `packages/shared/test/health.test.ts`: Actualizar fixtures para incluir db:'ok' y testear status:'degraded' y db requerido
- **modify** `apps/admin/test/App.test.tsx`: Actualizar fixtures de parseHealthResponse para incluir db:'ok'
- **modify** `apps/mobile/test/health.test.ts`: Actualizar fixtures de parseHealthResponse para incluir db:'ok'
- **create** `apps/api/src/db/env.ts`: requireDatabaseUrl(env): string — lanza 'DATABASE_URL no definida' si falta
- **create** `apps/api/src/db/client.ts`: createDb(url: string): { pool: Pool, db: DrizzleDb } — no conecta al instanciarse
- **create** `apps/api/src/db/schema/users.ts`: Tablas users y profiles con Drizzle; IDs uuid7, FKs, CHECK constraints
- **create** `apps/api/src/db/schema/llm.ts`: Tablas llm_providers, llm_routes (PK=agent), llm_calls con Drizzle
- **create** `apps/api/src/db/schema/agent_prompts.ts`: Tabla agent_prompts con Drizzle; status CHECK draft|published|archived
- **create** `apps/api/src/db/schema/index.ts`: Re-exporta todo el schema
- **create** `apps/api/src/db/seed.ts`: Exporta SEED_PROVIDERS, SEED_ROUTES, runSeed(db); INSERT onConflictDoNothing
- **create** `apps/api/src/db/migrations/0000_enable_vector.sql`: CREATE EXTENSION IF NOT EXISTS vector (migración custom)
- **create** `apps/api/src/db/migrations/0001_core.sql`: CREATE TABLE para las 6 tablas del núcleo, generado por drizzle-kit
- **create** `apps/api/src/db/migrations/meta/_journal.json`: Journal de drizzle-kit commiteado
- **modify** `apps/api/src/app.ts`: buildApp({ db }) con db requerido; /health ejecuta SELECT 1 con timeout, retorna {status, version, timestamp, db}
- **modify** `apps/api/src/index.ts`: Llama requireDatabaseUrl(process.env), createDb(url), buildApp({ db }) antes de listen
- **create** `apps/api/drizzle.config.ts`: Config drizzle-kit: schema src/db/schema/index.ts, out src/db/migrations, driver pg
- **modify** `apps/api/package.json`: Agregar drizzle-orm 0.45.3, drizzle-kit 0.31.11, pg 8.23.0, @types/pg 8.23.1; scripts db:migrate, db:generate, db:seed, test:integration
- **modify** `apps/api/vitest.config.ts`: Excluir **/*.integration.test.ts del include de pnpm test
- **create** `apps/api/vitest.integration.config.ts`: Config Vitest solo para *.integration.test.ts; usado por test:integration
- **create** `apps/api/test/schema.test.ts`: Tests Vitest sin DB: getTableConfig verifica columnas, PKs, FKs y CHECK constraints de las 6 tablas
- **create** `apps/api/test/seed.test.ts`: Tests Vitest sin DB: verifica SEED_PROVIDERS, SEED_ROUTES y que runSeed llama onConflictDoNothing con db falso
- **create** `apps/api/test/client.test.ts`: Test Vitest: createDb retorna {pool, db} sin conectar al instanciarse
- **create** `apps/api/test/env.test.ts`: Tests Vitest: requireDatabaseUrl lanza si falta DATABASE_URL, retorna URL si está presente
- **create** `apps/api/test/db.integration.test.ts`: Tests de integración contra DB real: SELECT 1, extensión vector, 6 tablas, seed x2 (idempotencia); artefacto validado por CI
- **create** `tests/test_issue_10.py`: Tests Python stdlib: docker-compose.yml, ci.yml, existencia de migraciones SQL y meta/
- **modify** `.github/workflows/ci.yml`: Service container pgvector en job node; steps db:migrate, test:integration, db:seed x2, drizzle-kit generate + git diff --exit-code
- **modify** `README.md`: Sección DB: docker-compose como referencia local, nota que DB dev/staging llega con #13, comandos db:*
- **modify** `pnpm-lock.yaml`: Lockfile actualizado con drizzle-orm, drizzle-kit, pg, @types/pg

## Tareas

### T1: Extender healthStatusSchema en shared + actualizar tests de shared, admin, mobile y api

Modificar healthStatusSchema: status z.enum(['ok','degraded']), db z.enum(['ok','error']) requerido; actualizar todos los fixtures de shared, admin y mobile. D16: el cambio de contrato es atómico; /health de api responde status 'degraded', db 'error', HTTP 503 hasta que T10 agregue el chequeo real.

**Tests:**
- `packages/shared/test/health.test.ts::test_healthstatus_parse_valid_ok_with_db`: parse({status:'ok', version, timestamp, db:'ok'}) no lanza
- `packages/shared/test/health.test.ts::test_healthstatus_parse_degraded_with_db_error`: parse({status:'degraded', version, timestamp, db:'error'}) no lanza
- `packages/shared/test/health.test.ts::test_healthstatus_rejects_missing_db`: parse({status:'ok', version, timestamp}) sin campo db lanza ZodError
- `packages/shared/test/health.test.ts::test_healthstatus_rejects_wrong_status_value`: parse({status:'fail', version, timestamp, db:'ok'}) lanza ZodError
- `packages/shared/test/health.test.ts::test_healthstatus_rejects_wrong_db_value`: parse({status:'ok', version, timestamp, db:'unknown'}) lanza ZodError
- `apps/admin/test/App.test.tsx::parseHealthResponse parses valid response`: fixture con db:'ok'; parsed.db === 'ok'
- `apps/admin/test/App.test.tsx::parseHealthResponse throws on invalid response`: fixture sin db lanza
- `apps/mobile/test/health.test.ts::test_mobile_imports_healthstatus_from_shared`: fixture con db:'ok'; parsed.db === 'ok'
- `apps/mobile/test/health.test.ts::parseHealthResponse throws on invalid data`: fixture sin db lanza
- `packages/shared/test/health.test.ts::test_healthstatus_parse_valid_object`: (test existente, D16) actualizar el fixture para incluir db:'ok'; parse no lanza
- `apps/api/test/health.test.ts::test_get_health_returns_503_degraded_without_db_client`: (D16) GET /health → statusCode 503, body.status === 'degraded', body.db === 'error'
- `apps/api/test/health.test.ts::test_get_health_body_matches_healthstatus_schema`: (test existente, D16, modificar) body parseado con healthStatusSchema no lanza; parsed.status === 'degraded' y parsed.db === 'error'

**Tests a eliminar:**
- `apps/api/test/health.test.ts::test_get_health_returns_200`: D16 — sin cliente de DB /health responde 503; reemplazado por test_get_health_returns_503_degraded_without_db_client

**Archivos de soporte de tests:**
- `apps/api/package.json`
- `apps/api/tsconfig.json`
- `apps/api/vitest.config.ts`
- `packages/shared/package.json`
- `packages/shared/tsconfig.json`
- `packages/shared/vitest.config.ts`
- `apps/admin/package.json`
- `apps/admin/tsconfig.json`
- `apps/admin/vitest.config.ts`
- `apps/mobile/package.json`
- `apps/mobile/tsconfig.json`
- `apps/mobile/vitest.config.ts`

**Archivos de implementación:**
- `packages/shared/src/health.ts`
- `apps/api/src/app.ts`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T2: Agregar deps Drizzle+pg a apps/api + drizzle.config.ts + vitest configs

Instalar drizzle-orm 0.45.3, drizzle-kit 0.31.11, pg 8.23.0, @types/pg 8.23.1; agregar scripts db:migrate/db:generate/db:seed/test:integration; crear drizzle.config.ts; excluir *.integration.test.ts de vitest.config.ts; crear vitest.integration.config.ts

**Tests:**
- `tests/test_issue_10.py::test_api_package_json_has_drizzle_and_pg_deps`: apps/api/package.json contiene drizzle-orm 0.45.3, drizzle-kit 0.31.11, pg 8.23.0, @types/pg 8.23.1
- `tests/test_issue_10.py::test_api_package_json_has_db_scripts`: scripts db:migrate, db:generate, db:seed, test:integration presentes en apps/api/package.json
- `tests/test_issue_10.py::test_drizzle_config_exists`: apps/api/drizzle.config.ts existe
- `tests/test_issue_10.py::test_drizzle_config_references_schema_and_migrations`: drizzle.config.ts contiene 'src/db/schema' y 'src/db/migrations'
- `tests/test_issue_10.py::test_vitest_integration_config_exists`: apps/api/vitest.integration.config.ts existe

**Archivos de soporte de tests:**
- `tests/test_issue_10.py`

**Archivos de implementación:**
- `apps/api/package.json`
- `apps/api/drizzle.config.ts`
- `apps/api/vitest.config.ts`
- `apps/api/vitest.integration.config.ts`
- `pnpm-lock.yaml`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T3: requireDatabaseUrl: lanza si falta DATABASE_URL

Crear apps/api/src/db/env.ts con requireDatabaseUrl(env: NodeJS.ProcessEnv): string; testear con Vitest

**Tests:**
- `apps/api/test/env.test.ts::test_requireDatabaseUrl_returns_url_when_present`: requireDatabaseUrl({ DATABASE_URL: 'postgres://...' }) retorna la URL sin lanzar
- `apps/api/test/env.test.ts::test_requireDatabaseUrl_throws_when_missing`: requireDatabaseUrl({}) lanza Error con mensaje 'DATABASE_URL no definida'
- `apps/api/test/env.test.ts::test_requireDatabaseUrl_throws_when_empty_string`: requireDatabaseUrl({ DATABASE_URL: '' }) lanza Error con mensaje 'DATABASE_URL no definida'

**Archivos de soporte de tests:**
- `apps/api/package.json`
- `apps/api/tsconfig.json`
- `apps/api/vitest.config.ts`

**Archivos de implementación:**
- `apps/api/src/db/env.ts`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T4: createDb: factory que retorna {pool, db} sin conectar

Crear apps/api/src/db/client.ts con createDb(url: string): { pool: Pool, db }; testear con Vitest que retorna ambas propiedades sin abrir conexión

**Tests:**
- `apps/api/test/client.test.ts::test_createDb_returns_pool_and_db`: createDb('postgres://localhost/test') retorna objeto con propiedades pool y db definidas
- `apps/api/test/client.test.ts::test_createDb_does_not_connect_on_instantiation`: createDb con URL inválida no lanza al instanciarse (la conexión es lazy)

**Archivos de soporte de tests:**
- `apps/api/package.json`
- `apps/api/tsconfig.json`
- `apps/api/vitest.config.ts`

**Archivos de implementación:**
- `apps/api/src/db/client.ts`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T5: Schema Drizzle: tablas users y profiles

Definir users(id uuid7, firebase_uid, email, role CHECK, locale, created_at) y profiles(user_id FK→users, birthdate, sex, height_cm, activity_level CHECK, experience_level CHECK, injuries jsonb, ..., updated_at) en users.ts

**Tests:**
- `apps/api/test/schema.test.ts::test_users_table_has_correct_columns`: getTableConfig(users).columns incluye id, firebase_uid, email, role, locale, created_at con tipos correctos
- `apps/api/test/schema.test.ts::test_users_id_has_uuidv7_default`: columna id de users tiene defaultFn o default con referencia a uuidv7()
- `apps/api/test/schema.test.ts::test_users_role_has_check_constraint`: getTableConfig(users).checks contiene constraint con 'user' y 'admin'
- `apps/api/test/schema.test.ts::test_profiles_table_has_correct_columns`: getTableConfig(profiles).columns incluye user_id, birthdate, height_cm, activity_level, experience_level, injuries, updated_at
- `apps/api/test/schema.test.ts::test_profiles_user_id_is_fk_to_users`: getTableConfig(profiles).foreignKeys contiene FK de user_id hacia tabla users

**Archivos de soporte de tests:**
- `apps/api/package.json`
- `apps/api/tsconfig.json`
- `apps/api/vitest.config.ts`

**Archivos de implementación:**
- `apps/api/src/db/schema/users.ts`
- `apps/api/src/db/schema/index.ts`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

### T6: Schema Drizzle: tablas llm_providers, llm_routes, llm_calls

Definir llm_providers(id uuid7, name CHECK, base_url, secret_ref, enabled), llm_routes(agent PK, provider_id FK, model, params jsonb, fallback_provider_id FK nullable, fallback_model nullable, updated_by, updated_at), llm_calls(id uuid7, user_id FK nullable, conversation_id nullable, agent, model, prompt_version, tokens_in, tokens_out, cost_usd, latency_ms, context_breakdown jsonb, error nullable, provider) en llm.ts

**Tests:**
- `apps/api/test/schema.test.ts::test_llm_providers_table_has_correct_columns`: getTableConfig(llmProviders).columns incluye id, name, base_url, secret_ref, enabled
- `apps/api/test/schema.test.ts::test_llm_providers_name_has_check_constraint`: getTableConfig(llmProviders).checks contiene constraint con 'nous' y 'gemini'
- `apps/api/test/schema.test.ts::test_llm_routes_pk_is_agent`: (D17) la columna 'agent' de llmRoutes tiene primary === true y es la única con primary
- `apps/api/test/schema.test.ts::test_llm_routes_has_fk_to_providers`: getTableConfig(llmRoutes).foreignKeys contiene FK de provider_id hacia llm_providers
- `apps/api/test/schema.test.ts::test_llm_calls_has_required_columns`: getTableConfig(llmCalls).columns incluye tokens_in, tokens_out, cost_usd, latency_ms, context_breakdown, provider
- `apps/api/test/schema.test.ts::test_llm_calls_id_has_uuidv7_default`: columna id de llmCalls tiene default con referencia a uuidv7()

**Archivos de soporte de tests:**
- `apps/api/package.json`
- `apps/api/tsconfig.json`
- `apps/api/vitest.config.ts`

**Archivos de implementación:**
- `apps/api/src/db/schema/llm.ts`
- `apps/api/src/db/schema/index.ts`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

### T7: Schema Drizzle: tabla agent_prompts

Definir agent_prompts(id uuid7, agent, version int, content text, status CHECK draft|published|archived, author, notes nullable, created_at) en agent_prompts.ts

**Tests:**
- `apps/api/test/schema.test.ts::test_agent_prompts_table_has_correct_columns`: getTableConfig(agentPrompts).columns incluye id, agent, version, content, status, author, notes, created_at
- `apps/api/test/schema.test.ts::test_agent_prompts_status_has_check_constraint`: getTableConfig(agentPrompts).checks contiene constraint con 'draft', 'published', 'archived'
- `apps/api/test/schema.test.ts::test_agent_prompts_id_has_uuidv7_default`: columna id de agentPrompts tiene default con referencia a uuidv7()

**Archivos de soporte de tests:**
- `apps/api/package.json`
- `apps/api/tsconfig.json`
- `apps/api/vitest.config.ts`

**Archivos de implementación:**
- `apps/api/src/db/schema/agent_prompts.ts`
- `apps/api/src/db/schema/index.ts`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

### T8: Seed: SEED_PROVIDERS, SEED_ROUTES, runSeed(db)

Crear seed.ts exportando constantes SEED_PROVIDERS (nous, gemini) y SEED_ROUTES (7 agentes con modelos y fallbacks acordados) y runSeed(db) que hace INSERT onConflictDoNothing; testear sin DB con db falso

**Tests:**
- `apps/api/test/seed.test.ts::test_seed_providers_has_nous_and_gemini`: SEED_PROVIDERS tiene exactamente 2 entradas con name 'nous' y 'gemini'
- `apps/api/test/seed.test.ts::test_seed_providers_nous_base_url`: SEED_PROVIDERS[nous].base_url === 'https://inference-api.nousresearch.com/v1'
- `apps/api/test/seed.test.ts::test_seed_routes_has_7_agents`: SEED_ROUTES tiene exactamente 7 entradas con agent in [router, coach, nutri, psico, sintetizador, extractor, resumidor]
- `apps/api/test/seed.test.ts::test_seed_routes_small_agents_model`: router, extractor, resumidor tienen model 'openai/gpt-6-luna'
- `apps/api/test/seed.test.ts::test_seed_routes_large_agents_model`: coach, nutri, psico, sintetizador tienen model 'anthropic/claude-sonnet-5.5'
- `apps/api/test/seed.test.ts::test_seed_routes_small_agents_fallback`: router, extractor, resumidor tienen fallback_model 'gemini-3.5-flash-lite'
- `apps/api/test/seed.test.ts::test_seed_routes_large_agents_fallback`: coach, nutri, psico, sintetizador tienen fallback_model 'gemini-3.8-flash'
- `apps/api/test/seed.test.ts::test_runSeed_calls_onConflictDoNothing`: runSeed(fakeDb) invoca insert().values().onConflictDoNothing() para providers y routes; fakeDb es objeto con método insert que retorna builder encadenable

**Archivos de soporte de tests:**
- `apps/api/package.json`
- `apps/api/tsconfig.json`
- `apps/api/vitest.config.ts`

**Archivos de implementación:**
- `apps/api/src/db/seed.ts`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

### T9: Migraciones SQL: 0000_enable_vector.sql + 0001_core.sql + meta/

Crear 0000_enable_vector.sql manualmente (CREATE EXTENSION IF NOT EXISTS vector); correr drizzle-kit generate --name core para producir 0001_core.sql con las 6 tablas; commitear meta/_journal.json y meta/*_snapshot.json

**Tests:**
- `tests/test_issue_10.py::test_migration_0000_enable_vector_exists`: apps/api/src/db/migrations/0000_enable_vector.sql existe
- `tests/test_issue_10.py::test_migration_0000_has_create_extension_vector`: 0000_enable_vector.sql contiene 'CREATE EXTENSION' e 'vector'
- `tests/test_issue_10.py::test_migration_0001_core_exists`: apps/api/src/db/migrations/0001_core.sql existe
- `tests/test_issue_10.py::test_migration_0001_has_all_tables`: 0001_core.sql contiene CREATE TABLE para users, profiles, llm_providers, llm_routes, llm_calls, agent_prompts
- `tests/test_issue_10.py::test_migration_meta_journal_exists`: apps/api/src/db/migrations/meta/_journal.json existe
- `tests/test_issue_10.py::test_migration_meta_journal_has_two_entries`: _journal.json parseado como JSON tiene entries con 2 elementos (0000 y 0001)

**Archivos de soporte de tests:**
- `tests/test_issue_10.py`

**Archivos de implementación:**
- `apps/api/src/db/migrations/0000_enable_vector.sql`
- `apps/api/src/db/migrations/0001_core.sql`
- `apps/api/src/db/migrations/meta/_journal.json`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

### T10: /health con chequeo DB — unit tests con mock de db

Modificar buildApp({ db }) con db requerido; /health ejecuta SELECT 1 via pool.query con Promise.race contra timeout DB_HEALTH_TIMEOUT_MS; retorna {status, version, timestamp, db} con HTTP 200 o 503; modificar index.ts para usar requireDatabaseUrl + createDb

**Tests:**
- `apps/api/test/health.test.ts::test_get_health_returns_200_with_db_ok`: buildApp con mock db (pool.query resuelve) → statusCode 200, body.db === 'ok', body.status === 'ok'
- `apps/api/test/health.test.ts::test_get_health_returns_503_when_db_fails`: buildApp con mock db (pool.query rechaza) → statusCode 503, body.db === 'error', body.status === 'degraded'
- `apps/api/test/health.test.ts::test_get_health_returns_503_on_timeout`: buildApp con mock db que nunca resuelve y DB_HEALTH_TIMEOUT_MS=1 → statusCode 503, body.db === 'error'
- `apps/api/test/health.test.ts::test_get_health_body_matches_healthstatus_schema`: body parseado con healthStatusSchema (shared) no lanza; incluye campo db:'ok'

**Archivos de soporte de tests:**
- `apps/api/package.json`
- `apps/api/tsconfig.json`
- `apps/api/vitest.config.ts`

**Archivos de implementación:**
- `apps/api/src/app.ts`
- `apps/api/src/index.ts`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

### T11: docker-compose.yml + tests Python estructurales

Crear docker-compose.yml con servicio postgres pgvector/pgvector:0.8.6-pg18, puerto 5432, healthcheck pg_isready, env POSTGRES_*; tests Python verifican estructura del yml sin leer README

**Tests:**
- `tests/test_issue_10.py::test_docker_compose_exists`: docker-compose.yml existe en la raíz del repo
- `tests/test_issue_10.py::test_docker_compose_uses_pgvector_pg18_image`: docker-compose.yml contiene 'pgvector/pgvector:0.8.6-pg18'
- `tests/test_issue_10.py::test_docker_compose_exposes_5432`: docker-compose.yml contiene '5432'
- `tests/test_issue_10.py::test_docker_compose_has_healthcheck_pg_isready`: docker-compose.yml contiene 'healthcheck' y 'pg_isready'
- `tests/test_issue_10.py::test_docker_compose_has_postgres_env_vars`: docker-compose.yml contiene POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB

**Archivos de soporte de tests:**
- `tests/test_issue_10.py`

**Archivos de implementación:**
- `docker-compose.yml`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

### T12: CI: service container + steps integración + drift check + db.integration.test.ts + README

Modificar ci.yml: service container pgvector en job node con DATABASE_URL, steps db:migrate, db:seed x2, test:integration, drizzle-kit generate + git diff --exit-code; crear db.integration.test.ts; actualizar README con sección DB

**Tests:**
- `tests/test_issue_10.py::test_ci_has_postgres_service_container`: ci.yml contiene 'pgvector/pgvector:0.8.6-pg18' bajo services
- `tests/test_issue_10.py::test_ci_has_database_url_env`: ci.yml contiene DATABASE_URL con referencia a localhost y 5432
- `tests/test_issue_10.py::test_ci_runs_db_migrate`: ci.yml contiene step con 'db:migrate'
- `tests/test_issue_10.py::test_ci_runs_test_integration`: ci.yml contiene step con 'test:integration'
- `tests/test_issue_10.py::test_ci_runs_drizzle_generate_and_drift_check`: ci.yml contiene 'db:generate' y 'git diff --exit-code'
- `tests/test_issue_10.py::test_ci_python_job_untouched`: ci.yml sigue teniendo job 'test' con python-version '3.12'

**Archivos de soporte de tests:**
- `tests/test_issue_10.py`
- `apps/api/vitest.integration.config.ts`

**Archivos de implementación:**
- `.github/workflows/ci.yml`
- `apps/api/test/db.integration.test.ts`
- `README.md`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

## Fuera de alcance

- DB de desarrollo/staging en GCP: llega con issue #13 (Cloud SQL staging); DATABASE_URL apuntará ahí
- Resto de entidades del modelo de datos (goals, plans, workout_logs, etc.): se agregan en issues de cada feature
- Embeddings y columna vector en la tabla memories: llega con el issue de memoria episódica
- Cloud SQL Auth Proxy ni configuración de credenciales GCP
- Panel admin para editar llm_routes en caliente
- Build de producción de la API ni Dockerfile
- Tests de UI nativa en mobile

## Riesgos

- uuidv7() es función nativa de Postgres 18: verificar que la imagen pgvector/pgvector:0.8.6-pg18 incluye PG18 real y no un fork sin esa función; falla en el primer db:migrate en CI
- drizzle-kit generate --custom para 0000_enable_vector.sql requiere verificar que el flag existe en drizzle-kit 0.31.11; alternativa: crear el SQL a mano y registrarlo manualmente en _journal.json
- El drift check (db:generate + git diff --exit-code) requiere que drizzle-kit no necesite conexión activa para generate; confirmar con drizzle.config.ts que driver pg no fuerza conexión al generar
- getTableConfig de drizzle-orm/pg-core puede no exponer CHECK constraints de forma introspectable en la versión 0.45.3; en ese caso los tests de schema verifican la presencia de la definición sql`` en el source via el objeto de check en el schema TS
- apps/api/vitest.config.ts debe excluir *.integration.test.ts explícitamente; si el glob no se configura bien, pnpm test intentará correr los tests de integración sin DB y fallará en CI antes del step de service container

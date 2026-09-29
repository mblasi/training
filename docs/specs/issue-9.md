---
issue: 9
status: done
test_command: python3 -m unittest discover -s tests -v && corepack pnpm install && corepack pnpm lint && corepack pnpm typecheck && corepack pnpm test
---

# Spec de implementación: Monorepo pnpm: apps/api, apps/admin, apps/mobile, packages/shared + CI

## Resumen

Monorepo pnpm con apps/api (Fastify), apps/admin (React+Vite), apps/mobile (Expo), packages/shared (Zod+HealthStatus) y CI Node paralelo al job Python existente

## Decisiones de diseño

| ID | Topic | Opciones | Elegida | Rationale |
|----|-------|----------|---------|-----------|
| D1 | Schema compartido | HealthStatus {status, version, timestamp}, objeto ad-hoc por app | HealthStatus {status:'ok', version, timestamp} en @trainia/shared, producido por GET /health y consumido por admin y mobile | Tipo único validado con Zod compartido entre los tres workspaces |
| D2 | Framework de tests JS/TS | Vitest, Jest, node:test | Vitest en todos los workspaces (env node en api/shared/mobile, jsdom en admin) | Consistencia, soporte nativo de ESM, configuración mínima |
| D3 | CI Node | job paralelo, step extra en job Python, workflow separado | Job 'node' paralelo al job Python existente sin tocar el job test actual | Aislamiento: fallo Node no rompe reporte Python y viceversa |
| D4 | Versión Node y pnpm | Node 20+pnpm10, Node 24+corepack+pnpm fijado | Node 24 LTS: .nvmrc=24, engines>=24 (solo declarativo, sin engine-strict), setup-node@v4 con node-version=24, pnpm vía corepack con packageManager pnpm@12.8.1 en package.json raíz | LTS actual; engines>=24 es informativo; corepack evita instalar pnpm por separado en CI |
| D5 | tsconfig base | base con target/module incluido, base solo flags de rigor | tsconfig.base.json en raíz SOLO con strict, esModuleInterop, skipLibCheck, resolveJsonModule; cada app pone target/module (api: NodeNext/ES2022; admin: Bundler+jsx react-jsx; mobile: preset Expo; shared: ESNext/Bundler) | Evita conflictos entre entornos Node, bundler y Expo |
| D6 | Consumo de shared | con build, sin build via exports a src/index.ts | @trainia/shared con workspace:* y exports apuntando a src/index.ts, sin build | Simplicidad en Fase 0; Vitest y Vite resuelven TS directamente |
| D7 | Linter | ESLint 8 legacy, ESLint 9 flat config, Biome | ESLint 9 flat config (eslint.config.js en raíz) + typescript-eslint + eslint-config-prettier + eslint-config-expo para mobile | API moderna, un archivo de config para todo el monorepo |
| DN1 | Versión exacta de pnpm | pnpm@10.x, pnpm@12.8.1 | pnpm@12.8.1 | Latest estable real en npm al momento de diseño |
| DN2 | Placeholder de admin y mobile | componente estático sin router, con router completo | admin: página única sin router; mobile: expo-router con app/index.tsx; ambas muestran 'Trainia' y usan HealthStatus de shared | Mínimo viable para verificar integración con shared sin complejidad de routing |
| DN3 | Test de GET /health en api | supertest, app.inject() de Fastify, fetch directo | app.inject() de Fastify sin abrir puerto real | Sin dependencia de red, más rápido, idiomático en Fastify |
| D8 | La spec lista `packages/shared/package.json` y `packages/shared/tsconfig.json` en dos lugares contradictorios: | Archivos que figuran a la vez en test_support_files e impl_files se permiten en RED con contenido mínimo (solo lo necesario para que el runner descubra y ejecute los tests: nombre, type, scripts test, devDeps de test, tsconfig base); en GREEN se completan (dependencias de producción como zod, exports, etc.). test_support_files tiene prioridad sobre la lista de prohibidos. | Archivos que figuran a la vez en test_support_files e impl_files se permiten en RED con contenido mínimo (solo lo necesario para que el runner descubra y ejecute los tests: nombre, type, scripts test, devDeps de test, tsconfig base); en GREEN se completan (dependencias de producción como zod, exports, etc.). test_support_files tiene prioridad sobre la lista de prohibidos. | Decisión tomada durante implementación |
| D9 | Los tests fallan por infraestructura: falta react y react-dom en devDependencies. La decisión D12 dice que test_support_files (que incluye package.json) pueden tener "contenido mínimo para que el runner descubra y ejecute los tests". Sin react/react-dom, los tests no se ejecutan (fallan antes del import/assert). Necesito agregar react y react-dom a devDependencies de apps/admin/package.json para que sea infraestructura completa. | Sí: en RED agregá a apps/admin/package.json lo necesario para que el test cargue y ejecute: react y react-dom como dependencies (son runtime de la app, se usan igual en GREEN) y @testing-library/react, jsdom, @vitejs/plugin-react, vitest y @types/react(-dom) como devDependencies. El test debe fallar porque falta src/App.tsx, no por paquetes faltantes. | Sí: en RED agregá a apps/admin/package.json lo necesario para que el test cargue y ejecute: react y react-dom como dependencies (son runtime de la app, se usan igual en GREEN) y @testing-library/react, jsdom, @vitejs/plugin-react, vitest y @types/react(-dom) como devDependencies. El test debe fallar porque falta src/App.tsx, no por paquetes faltantes. | Decisión tomada durante implementación |
| D10 | El test pasa en vez de fallar. Esto sucede porque el código de producción (packages/shared/src/health.ts con healthStatusSchema) ya existe de tareas anteriores. La regla RED dice "los tests deben FALLAR" pero en este caso el import resuelve correctamente y el schema ya está implementado. No puedo hacer que el test falle sin tocar código de producción (lo cual está prohibido). ¿Debo modificar el test para que espere algo que aún no existe en el código de producción de mobile (ej: el componente app/index.tsx), o aceptar que este test en particular pasa porque la dependencia shared ya está completa? | El test de mobile debe verificar código de mobile, no solo shared: agregá un módulo de lógica pura de mobile que la pantalla usa, p. ej. apps/mobile/src/health.ts con `parseHealthResponse(json: unknown): HealthStatus` (usa healthStatusSchema de @trainia/shared) y testealo desde apps/mobile/test/health.test.ts (válido parsea; inválido lanza). En RED falla porque apps/mobile/src/health.ts no existe. app/index.tsx importa parseHealthResponse/HealthStatus. apps/mobile/src/health.ts se agrega a impl_files de T5. | El test de mobile debe verificar código de mobile, no solo shared: agregá un módulo de lógica pura de mobile que la pantalla usa, p. ej. apps/mobile/src/health.ts con `parseHealthResponse(json: unknown): HealthStatus` (usa healthStatusSchema de @trainia/shared) y testealo desde apps/mobile/test/health.test.ts (válido parsea; inválido lanza). En RED falla porque apps/mobile/src/health.ts no existe. app/index.tsx importa parseHealthResponse/HealthStatus. apps/mobile/src/health.ts se agrega a impl_files de T5. | Decisión tomada durante implementación |

## Archivos afectados

- **create** `package.json`: Raíz: packageManager pnpm@12.8.1, scripts lint/typecheck/test con pnpm -r run, engines node>=24 (declarativo)
- **create** `pnpm-workspace.yaml`: Declara apps/* y packages/*
- **create** `pnpm-lock.yaml`: Lockfile commiteado generado por pnpm install
- **create** `.nvmrc`: Fija Node 24
- **create** `tsconfig.base.json`: Flags de rigor compartidos (strict, esModuleInterop, skipLibCheck, resolveJsonModule), sin target ni module
- **create** `eslint.config.js`: ESLint 9 flat config para todo el monorepo
- **create** `.prettierrc.json`: Config Prettier compartida
- **create** `packages/shared/package.json`: Workspace @trainia/shared con exports a src/index.ts
- **create** `packages/shared/tsconfig.json`: Extiende base, target ESNext, moduleResolution Bundler
- **create** `packages/shared/vitest.config.ts`: Vitest env node para shared
- **create** `packages/shared/src/health.ts`: Define healthStatusSchema con Zod
- **create** `packages/shared/src/index.ts`: Exporta healthStatusSchema y tipo HealthStatus inferido
- **create** `packages/shared/test/health.test.ts`: Valida parse/reject de HealthStatus con Vitest
- **create** `apps/api/package.json`: Workspace api con Fastify, depende de @trainia/shared
- **create** `apps/api/tsconfig.json`: Extiende base, module NodeNext, target ES2022
- **create** `apps/api/vitest.config.ts`: Vitest env node para api
- **create** `apps/api/src/app.ts`: Crea y exporta instancia Fastify con GET /health
- **create** `apps/api/src/index.ts`: Entry point: levanta servidor en puerto 3000
- **create** `apps/api/test/health.test.ts`: Test de GET /health con app.inject()
- **create** `apps/admin/package.json`: Workspace admin con React, Vite, @testing-library/react, depende de @trainia/shared
- **create** `apps/admin/tsconfig.json`: Extiende base, moduleResolution Bundler, jsx react-jsx
- **create** `apps/admin/vite.config.ts`: Config Vite para React
- **create** `apps/admin/vitest.config.ts`: Vitest env jsdom para admin
- **create** `apps/admin/src/App.tsx`: Componente raíz que muestra 'Trainia' con tipo HealthStatus de shared
- **create** `apps/admin/src/main.tsx`: Entry point React con ReactDOM.createRoot
- **create** `apps/admin/index.html`: HTML raíz para Vite
- **create** `apps/admin/test/App.test.tsx`: Test render de App con @testing-library/react + jsdom
- **create** `apps/mobile/package.json`: Workspace mobile con Expo, expo-router, depende de @trainia/shared
- **create** `apps/mobile/tsconfig.json`: Extiende preset Expo + base
- **create** `apps/mobile/vitest.config.ts`: Vitest env node para mobile (lógica pura)
- **create** `apps/mobile/app/index.tsx`: Pantalla raíz expo-router que muestra 'Trainia' y usa HealthStatus
- **create** `apps/mobile/test/health.test.ts`: Test que valida uso de healthStatusSchema de shared en mobile
- **modify** `.github/workflows/ci.yml`: Agrega job 'node' paralelo con Node 24, corepack, pnpm install --frozen-lockfile, lint, typecheck, test
- **modify** `README.md`: Agrega sección 'Desarrollo' con instrucciones para levantar api, admin y mobile

## Tareas

### T1: Scaffolding raíz del monorepo

Crear package.json raíz, pnpm-workspace.yaml, pnpm-lock.yaml, .nvmrc, tsconfig.base.json, eslint.config.js y .prettierrc.json

**Tests:**
- `tests/test_monorepo_root.py::test_pnpm_workspace_yaml_exists_and_valid`: pnpm-workspace.yaml existe y contiene 'apps/*' y 'packages/*'
- `tests/test_monorepo_root.py::test_package_json_root_has_required_fields`: package.json raíz tiene packageManager pnpm@12.8.1, scripts lint/typecheck/test y engines node>=24
- `tests/test_monorepo_root.py::test_tsconfig_base_only_has_rigor_flags`: tsconfig.base.json tiene strict/esModuleInterop/skipLibCheck/resolveJsonModule y NO tiene target ni module
- `tests/test_monorepo_root.py::test_nvmrc_is_24`: .nvmrc contiene '24'
- `tests/test_monorepo_root.py::test_pnpm_lockfile_exists`: pnpm-lock.yaml existe en la raíz del repo

**Archivos de implementación:**
- `package.json`
- `pnpm-workspace.yaml`
- `pnpm-lock.yaml`
- `.nvmrc`
- `tsconfig.base.json`
- `eslint.config.js`
- `.prettierrc.json`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T2: packages/shared: HealthStatus Zod schema con tests

Crear workspace @trainia/shared con healthStatusSchema Zod, exportarlo desde src/index.ts y testearlo con Vitest

**Tests:**
- `packages/shared/test/health.test.ts::test_healthstatus_parse_valid_object`: healthStatusSchema.parse({status:'ok',version:'0.1.0',timestamp:'...'}) no lanza
- `packages/shared/test/health.test.ts::test_healthstatus_rejects_missing_status`: healthStatusSchema.parse({}) lanza ZodError
- `packages/shared/test/health.test.ts::test_healthstatus_rejects_wrong_status_value`: healthStatusSchema.parse({status:'fail',...}) lanza ZodError (status es literal 'ok')

**Archivos de soporte de tests:**
- `packages/shared/package.json`
- `packages/shared/tsconfig.json`
- `packages/shared/vitest.config.ts`

**Archivos de implementación:**
- `packages/shared/src/health.ts`
- `packages/shared/src/index.ts`
- `packages/shared/package.json`
- `packages/shared/tsconfig.json`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T3: apps/api: GET /health con Fastify y test con app.inject()

Crear workspace api con Fastify, ruta GET /health que retorna HealthStatus validado, testeada con app.inject()

**Tests:**
- `apps/api/test/health.test.ts::test_get_health_returns_200`: app.inject({method:'GET',url:'/health'}) retorna statusCode 200
- `apps/api/test/health.test.ts::test_get_health_body_matches_healthstatus_schema`: body parseado con healthStatusSchema no lanza y status==='ok'

**Archivos de soporte de tests:**
- `apps/api/package.json`
- `apps/api/tsconfig.json`
- `apps/api/vitest.config.ts`

**Archivos de implementación:**
- `apps/api/src/app.ts`
- `apps/api/src/index.ts`
- `apps/api/package.json`
- `apps/api/tsconfig.json`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T4: apps/admin: placeholder React+Vite con HealthStatus y test de render con jsdom

Crear workspace admin con React+Vite, componente App que usa HealthStatus de shared, testeado con @testing-library/react en jsdom

**Tests:**
- `apps/admin/test/App.test.tsx::test_app_renders_trainia_heading`: render(<App />) con @testing-library/react encuentra el texto 'Trainia' en el DOM jsdom
- `apps/admin/test/App.test.tsx::test_app_uses_healthstatus_type`: el módulo App importa HealthStatus de @trainia/shared sin error de tipos (typecheck en CI lo verifica)

**Archivos de soporte de tests:**
- `apps/admin/package.json`
- `apps/admin/tsconfig.json`
- `apps/admin/vitest.config.ts`

**Archivos de implementación:**
- `apps/admin/src/App.tsx`
- `apps/admin/src/main.tsx`
- `apps/admin/index.html`
- `apps/admin/package.json`
- `apps/admin/tsconfig.json`
- `apps/admin/vite.config.ts`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T5: apps/mobile: placeholder Expo+expo-router con HealthStatus y test

Crear workspace mobile con Expo y expo-router, pantalla app/index.tsx que usa HealthStatus de shared, testeada con Vitest env node sobre lógica pura

**Tests:**
- `apps/mobile/test/health.test.ts::test_mobile_imports_healthstatus_from_shared`: import de healthStatusSchema desde @trainia/shared resuelve y parse de objeto válido no lanza

**Archivos de soporte de tests:**
- `apps/mobile/package.json`
- `apps/mobile/tsconfig.json`
- `apps/mobile/vitest.config.ts`

**Archivos de implementación:**
- `apps/mobile/app/index.tsx`
- `apps/mobile/package.json`
- `apps/mobile/tsconfig.json`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T6: CI job Node y README

Agregar job 'node' paralelo en ci.yml con Node 24+corepack+pnpm install --frozen-lockfile+lint+typecheck+test, y actualizar README con instrucciones de cada app

**Tests:**
- `tests/test_ci_and_readme.py::test_ci_yml_has_node_job`: ci.yml contiene job 'node' con setup-node node-version 24, corepack enable y pnpm install --frozen-lockfile
- `tests/test_ci_and_readme.py::test_ci_yml_node_job_runs_lint_typecheck_test`: ci.yml job 'node' contiene steps con 'pnpm lint', 'pnpm typecheck' y 'pnpm test'
- `tests/test_ci_and_readme.py::test_ci_yml_python_job_untouched`: ci.yml sigue teniendo el job 'test' Python original con python-version 3.12
- `tests/test_ci_and_readme.py::test_readme_has_dev_section`: README.md contiene 'apps/api', 'apps/admin' y 'apps/mobile' en una sección de desarrollo

**Archivos de implementación:**
- `.github/workflows/ci.yml`
- `README.md`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

## Fuera de alcance

- Base de datos, auth, deploy, builds de EAS
- Routing en admin (se deja para #11)
- Tests de UI nativa en mobile (requiere Expo test runner)
- Build de producción de cada app
- Configuración de Prettier como git hook (husky/lint-staged)
- engine-strict en .npmrc (engines>=24 es solo declarativo)

## Riesgos

- Expo impone restricciones en tsconfig que pueden conflictuar con tsconfig.base.json; mitigar revisando que el preset Expo no pise flags de rigor
- ESLint 9 flat config + eslint-config-expo puede no tener soporte oficial flat todavía; puede requerir adaptador legacy
- pnpm@12 es muy reciente; si corepack no tiene el hash en su caché, CI puede tardar; mitigar con lockfile commiteado y --frozen-lockfile
- Vitest en mobile con env node no puede testear componentes React Native reales; los tests de mobile quedan acotados a lógica pura/shared

---
issue: 11
status: implementing
test_command: python3 -m unittest discover -s tests -v && corepack pnpm install --frozen-lockfile && corepack pnpm lint && corepack pnpm typecheck && corepack pnpm test
---

# Spec de implementación: Auth con Firebase (Google + email/password) en api, admin y mobile

## Resumen

Auth con Firebase (Google + email/password) en api (plugin Fastify + upsert users + requireAdmin), admin (login Google + /me role check) y mobile (Google + email/password + AuthContext + pantalla login), con Firebase Auth Emulator en CI

## Decisiones de diseño

| ID | Topic | Opciones | Elegida | Rationale |
|----|-------|----------|---------|-----------|
| D1 | Emulador Firebase Auth en CI | firebase-tools en CI + unit tests mockeados, imagen Docker de terceros, solo mocks sin emulador | firebase-tools@15.32.0 como devDep en raíz; unit tests con firebase-admin mockeado; integration tests contra emulador real en CI | Unit tests rápidos sin red; integración real con emulador para cubrir el flujo completo con tokens reales |
| D2 | Librería auth en mobile (Expo) | @react-native-google-signin/google-signin nativa, expo-auth-session JS puro, solo email/password | @react-native-google-signin/google-signin@16.x (versión libre); módulo nativo mockeado en tests; ya vamos a EAS en #14 | Guía actual de Expo recomienda librerías nativas; funciona con development build (EAS en #14) |
| D3 | Alcance de mobile en este issue | implementación completa con UI pulida, solo capa de auth sin UI, AuthContext + pantalla de login mínima | AuthContext + pantalla de login mínima (email/password, botón Google, logout) sin diseño; persistencia con getReactNativePersistence + AsyncStorage | Demuestra el alcance del issue sin bloquear el diseño de UI futuro |
| D4 | Estructura del plugin auth en la API | plugin monolítico, verifyToken pura + plugin Fastify, middleware inline por ruta | src/auth/verifyToken.ts (función pura inyectable) + src/auth/upsertUser.ts + src/plugins/auth.ts (plugin Fastify) + src/plugins/requireAdmin.ts (hook) | Consistente con patrón de inyección de dependencias del repo; verifyToken testeable sin Fastify |
| D5 | Contrato de request.user | { uid, email, role } mínimo, todos los campos de users, type inferido de Drizzle | { id: string; uid: string; email: string; role: 'user' \ | 'admin' } declarado en src/auth/types.ts y augmentado en src/types/fastify.d.ts |
| D6 | Bootstrap de admin por ADMIN_EMAILS | en el upsert siempre recalcula, script de bootstrap separado, solo en insert inicial | ADMIN_EMAILS es fuente de verdad única: en cada upsert, role = 'admin' si email ∈ ADMIN_EMAILS (trim + case-insensitive) AND email_verified === true; si no, role = 'user' | Sacar un email de la lista lo degrada en el próximo login; email_verified evita que email/password sin verificar escale a admin |
| D7 | Tests de integración de auth con el emulador | REST directo al emulador, Admin SDK para crear tokens + REST signInWithCustomToken, solo unit tests | Admin SDK crea custom token → REST signInWithCustomToken → ID token real; projectId 'demo-trainia'; firebase.json en raíz con emulators.auth port 9099; emulators:exec envuelve test:integration de api y mobile en un solo step | Idiomático, no requiere conocer endpoints internos del emulador; prefijo demo- no requiere credenciales reales |
| D8 | Inicialización de firebase-admin e inyección en buildApp | inicializar dentro de buildApp, inicializar en index.ts e inyectar, singleton lazy | buildApp({ db, auth }) donde auth: { verifyIdToken(token: string): Promise<DecodedIdToken> }; src/index.ts inicializa firebase-admin con requireFirebaseProjectId(env) y pasa admin.auth() | Consistente con patrón de inyección del repo; unit tests pasan { verifyIdToken: vi.fn() } sin inicializar el SDK real |
| D9 | Tests en admin y mobile | unit tests mockeados, no tests en este issue, integración real | admin: unit tests de AuthContext con firebase/auth mockeado + test de /me role check con signOut si role !== admin; mobile: unit tests con módulo nativo mockeado + integration test de email/password contra emulador ejercitando src/auth de la app | OAuth Google no es testeable en jsdom/node; email/password sí funciona contra el emulador desde Node |
| D10 | firebase emulators:exec en CI | un solo exec para api+mobile, dos exec separados, mobile sin exec propio | Un solo firebase emulators:exec --only auth --project demo-trainia envolviendo pnpm --filter @trainia/api test:integration && pnpm --filter @trainia/mobile test:integration | Emulador levanta una sola vez; estado no persiste entre runs porque no se usa --import/--export |
| D11 | Env vars de firebase-admin y fallo rápido | requireFirebaseProjectId en src/auth/env.ts, objeto de config pasado a buildApp, leer en el plugin directamente | requireFirebaseProjectId(env): string en src/auth/env.ts; lanza 'FIREBASE_PROJECT_ID no definido' si falta; src/index.ts la llama antes de initializeApp | Análogo a requireDatabaseUrl; patrón consistente en el repo |
| D12 | Separación unit/integration en mobile | vitest.integration.config.ts separado, skipIf por env var, tests de mobile en apps/api | apps/mobile/vitest.integration.config.ts con include ['test/**/*.integration.test.ts']; vitest.config.ts excluye *.integration.test.ts; fail-fast en globalSetup si falta FIREBASE_AUTH_EMULATOR_HOST | Consistente con patrón de la API; cero skips, falla explícitamente con mensaje claro |
| D13 | connectAuthEmulator en cliente SDK (admin y mobile) | detección automática por env (no funciona en SDK cliente), connectAuthEmulator explícito al init, flag en config | connectAuthEmulator(auth, url) explícito cuando VITE_FIREBASE_AUTH_EMULATOR_HOST (admin) / EXPO_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST (mobile) esté definido; unit tests verifican que se llama o no según la env | El SDK cliente de Firebase NO detecta el emulador por env vars; solo firebase-admin lo hace automáticamente |
| D14 | Módulo de auth de mobile: inyección de instancia Auth | Auth como singleton importado, Auth inyectado por parámetro, contexto React | signInWithEmail(auth, email, password), signInWithGoogle(auth), signOut(auth): funciones puras que reciben la instancia Auth; initializeAuth con getReactNativePersistence(AsyncStorage) en src/auth/firebaseAuth.ts separado; test de integración en Node importa solo las funciones puras | El init de firebaseAuth.ts no se puede importar en Node (carga react-native); las funciones puras sí son testeables desde Node |
| D15 | Los tests de GREEN solo verifican que firebase.json exista con el contenido correcto y que package.json contenga firebase-tools en devDependencies. El lockfile (pnpm-lock.yaml) no es verificado por los tests. Sin embargo, pnpm está configurado globalmente con `allowBuilds` que bloquea los build scripts de protobufjs y re2 (dependencias de firebase-tools), y no puedo aprobar builds en modo no interactivo. ¿Debo: (1) Dejar package.json sin instalar (lockfile desactualizado) para que los tests pasen igual, o (2) Necesito que se configure allowBuilds global o se desactive la verificación para completar pnpm install? | Regla general del repo (ya aplicada con esbuild/unrs-resolver): los builds de dependencias se aprueban en pnpm-workspace.yaml bajo allowBuilds, nunca en .npmrc ni global, sin ignore-scripts ni downgrade. Agregá 'protobufjs: true' y 're2: true' a allowBuilds en pnpm-workspace.yaml (es dependency infra file, permitido), no crees .npmrc, corré 'corepack pnpm install' y commiteá package.json + pnpm-lock.yaml + pnpm-workspace.yaml actualizados; el lockfile debe quedar consistente para --frozen-lockfile. Aplica igual a cualquier dependencia futura con build script en este issue (firebase-admin, expo, etc.). | Regla general del repo (ya aplicada con esbuild/unrs-resolver): los builds de dependencias se aprueban en pnpm-workspace.yaml bajo allowBuilds, nunca en .npmrc ni global, sin ignore-scripts ni downgrade. Agregá 'protobufjs: true' y 're2: true' a allowBuilds en pnpm-workspace.yaml (es dependency infra file, permitido), no crees .npmrc, corré 'corepack pnpm install' y commiteá package.json + pnpm-lock.yaml + pnpm-workspace.yaml actualizados; el lockfile debe quedar consistente para --frozen-lockfile. Aplica igual a cualquier dependencia futura con build script en este issue (firebase-admin, expo, etc.). | Decisión tomada durante implementación |
| D16 | Vuelta a RED de T4: tests de upsertUser tautológicos y con error de lint | Rehacer apps/api/test/auth.test.ts (bloque upsertUser) para T4: (1) el fake db captura lo que upsertUser pasa a insert(users).values(row) y a onConflictDoUpdate({target,set}); los asserts verifican row.role y set.role (admin solo si email en ADMIN_EMAILS con trim+case-insensitive Y email_verified===true; user en otro caso), row.firebase_uid===uid, target===users.firebase_uid; (2) el fake NO calcula el rol: returning() devuelve una fila construida a partir del row recibido, con la forma real del schema (id, firebase_uid, email, role, locale, created_at); el AuthUser devuelto mapea firebase_uid→uid; (3) recálculo en cada login: misma llamada con lista vacía → values/set con role 'user'; (4) el archivo pasa eslint y tsc salvo por el import faltante de ../src/auth/upsertUser.js (sin any, sin parámetros sin usar). | Rehacer apps/api/test/auth.test.ts (bloque upsertUser) para T4: (1) el fake db captura lo que upsertUser pasa a insert(users).values(row) y a onConflictDoUpdate({target,set}); los asserts verifican row.role y set.role (admin solo si email en ADMIN_EMAILS con trim+case-insensitive Y email_verified===true; user en otro caso), row.firebase_uid===uid, target===users.firebase_uid; (2) el fake NO calcula el rol: returning() devuelve una fila construida a partir del row recibido, con la forma real del schema (id, firebase_uid, email, role, locale, created_at); el AuthUser devuelto mapea firebase_uid→uid; (3) recálculo en cada login: misma llamada con lista vacía → values/set con role 'user'; (4) el archivo pasa eslint y tsc salvo por el import faltante de ../src/auth/upsertUser.js (sin any, sin parámetros sin usar). | Decisión tomada durante implementación |

## Archivos afectados

- **create** `firebase.json`: Configuración mínima del emulador de Firebase Auth (port 9099) para firebase emulators:exec
- **modify** `package.json`: Agregar firebase-tools@15.32.0 como devDependency en raíz del monorepo
- **modify** `pnpm-lock.yaml`: Lockfile actualizado con todas las nuevas dependencias
- **modify** `apps/api/package.json`: Agregar firebase-admin@14.5.0 en dependencies
- **create** `apps/api/src/auth/types.ts`: Tipo AuthUser { id, uid, email, role } y DecodedIdToken mínimo para inyección
- **create** `apps/api/src/auth/env.ts`: requireFirebaseProjectId(env): string — lanza si falta FIREBASE_PROJECT_ID
- **create** `apps/api/src/auth/verifyToken.ts`: verifyToken(auth, token): Promise<DecodedIdToken> — función pura sin dependencia de Fastify
- **create** `apps/api/src/auth/upsertUser.ts`: upsertUser(db, decoded, adminEmails): Promise<AuthUser> — upsert en tabla users con lógica de rol ADMIN_EMAILS + email_verified
- **create** `apps/api/src/plugins/auth.ts`: Plugin Fastify que verifica ID token, llama upsertUser y decora request.user
- **create** `apps/api/src/plugins/requireAdmin.ts`: Hook preHandler que retorna 403 si request.user.role !== 'admin'
- **create** `apps/api/src/types/fastify.d.ts`: Augmentación de FastifyRequest para tipar request.user como AuthUser
- **modify** `apps/api/src/app.ts`: Agregar parámetro auth a BuildAppOptions; registrar plugin auth; agregar GET /me y GET /admin/ping con requireAdmin
- **modify** `apps/api/src/index.ts`: Llamar requireFirebaseProjectId, initializeApp firebase-admin, pasar admin.auth() a buildApp
- **create** `apps/api/test/auth-env.test.ts`: Unit tests de requireFirebaseProjectId
- **create** `apps/api/test/auth.test.ts`: Unit tests de verifyToken, upsertUser, plugin auth y requireAdmin con firebase-admin mockeado y db falso
- **create** `apps/api/test/auth.integration.test.ts`: Integration tests con emulador real: 401 sin token en /me, 200 con token válido, 403 user y 200 admin en /admin/ping; importa desde src/
- **modify** `apps/api/vitest.integration.config.ts`: Ampliar testTimeout a 15000; agregar globalSetup que falla con mensaje claro si falta FIREBASE_AUTH_EMULATOR_HOST o DATABASE_URL
- **modify** `apps/admin/package.json`: Agregar firebase@12.19.0 en dependencies
- **create** `apps/admin/src/auth/firebaseConfig.ts`: Inicialización de Firebase app + Auth para admin; connectAuthEmulator si VITE_FIREBASE_AUTH_EMULATOR_HOST está definido
- **create** `apps/admin/src/auth/AuthContext.tsx`: Context con estado de autenticación (user, role, loading), login Google, logout; llama GET /me para obtener role; hace signOut si role !== admin
- **create** `apps/admin/src/pages/Login.tsx`: Pantalla de login mínima con botón Google; sin diseño
- **modify** `apps/admin/src/App.tsx`: Envolver con AuthProvider; mostrar Login si no autenticado, contenido si role === admin
- **create** `apps/admin/test/AuthContext.test.tsx`: Unit tests de AuthContext y firebaseConfig: login Google, role check, signOut si user, connectAuthEmulator condicional
- **modify** `apps/mobile/package.json`: Agregar firebase@12.19.0, @react-native-google-signin/google-signin@16.x, @react-native-async-storage/async-storage (versión expo install SDK 57); script test:integration
- **modify** `apps/mobile/app.json`: Agregar plugin @react-native-google-signin/google-signin con EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID
- **create** `apps/mobile/src/auth/index.ts`: Funciones puras: signInWithEmail(auth, email, password), signInWithGoogle(auth), signOut(auth)
- **create** `apps/mobile/src/auth/firebaseAuth.ts`: initializeApp + initializeAuth con getReactNativePersistence(AsyncStorage) + connectAuthEmulator si EXPO_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST; exporta instancia auth
- **create** `apps/mobile/src/auth/AuthContext.tsx`: Context con user, loading, signInWithEmail, signInWithGoogle, signOut usando la instancia auth de firebaseAuth.ts
- **create** `apps/mobile/app/login.tsx`: Pantalla de login mínima: campos email/password, botón Google, botón logout si autenticado
- **modify** `apps/mobile/app/index.tsx`: Envolver con AuthProvider; redirigir a login si no autenticado
- **modify** `apps/mobile/vitest.config.ts`: Excluir *.integration.test.ts del include
- **create** `apps/mobile/vitest.integration.config.ts`: Config Vitest para *.integration.test.ts de mobile; testTimeout 15000; globalSetup que falla con mensaje claro si falta FIREBASE_AUTH_EMULATOR_HOST
- **create** `apps/mobile/test/auth.test.ts`: Unit tests de src/auth/index.ts con @react-native-google-signin y firebase/auth mockeados; unit test de firebaseConfig condicional
- **create** `apps/mobile/test/auth.integration.test.ts`: Integration test: signInWithEmail de src/auth contra emulador real; signInWithEmail OK y wrong password
- **create** `tests/test_issue_11.py`: Tests Python estructurales: firebase.json, firebase-tools en raíz, setup-java en ci.yml, emulators:exec, env vars CI, existencia y contenido de archivos de integración
- **modify** `.github/workflows/ci.yml`: Agregar actions/setup-java (temurin 21); step firebase emulators:exec con env FIREBASE_PROJECT_ID, FIREBASE_AUTH_EMULATOR_HOST, EXPO_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST, ADMIN_EMAILS
- **modify** `README.md`: Documentar JDK 21+ como prerequisito, variables de entorno Firebase (FIREBASE_PROJECT_ID, FIREBASE_AUTH_EMULATOR_HOST, EXPO_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST, EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID, ADMIN_EMAILS), cómo correr tests de integración

## Tareas

### T1: firebase.json + firebase-tools en raíz

Crear firebase.json mínimo con emulators.auth port 9099 y agregar firebase-tools@15.32.0 como devDependency en package.json raíz

**Tests:**
- `tests/test_issue_11.py::test_firebase_json_exists`: firebase.json existe en la raíz del repo
- `tests/test_issue_11.py::test_firebase_json_has_auth_emulator_port_9099`: firebase.json parseado como JSON contiene emulators.auth.port === 9099
- `tests/test_issue_11.py::test_root_package_json_has_firebase_tools`: package.json raíz devDependencies contiene 'firebase-tools' con versión '15.32.0'

**Archivos de soporte de tests:**
- `tests/test_issue_11.py`

**Archivos de implementación:**
- `firebase.json`
- `package.json`
- `pnpm-lock.yaml`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T2: API: tipos de auth + requireFirebaseProjectId + firebase-admin dep

Agregar firebase-admin@14.5.0 a deps de api; crear src/auth/types.ts con AuthUser y DecodedIdToken; crear src/auth/env.ts con requireFirebaseProjectId; unit tests

**Tests:**
- `apps/api/test/auth-env.test.ts::test_requireFirebaseProjectId_returns_id_when_present`: requireFirebaseProjectId({ FIREBASE_PROJECT_ID: 'demo-trainia' }) retorna 'demo-trainia' sin lanzar
- `apps/api/test/auth-env.test.ts::test_requireFirebaseProjectId_throws_when_missing`: requireFirebaseProjectId({}) lanza Error con mensaje 'FIREBASE_PROJECT_ID no definido'
- `apps/api/test/auth-env.test.ts::test_requireFirebaseProjectId_throws_when_empty_string`: requireFirebaseProjectId({ FIREBASE_PROJECT_ID: '' }) lanza Error con mensaje 'FIREBASE_PROJECT_ID no definido'
- `tests/test_issue_11.py::test_api_package_json_has_firebase_admin`: apps/api/package.json dependencies contiene 'firebase-admin' con versión '14.5.0'

**Archivos de soporte de tests:**
- `apps/api/package.json`
- `apps/api/tsconfig.json`
- `apps/api/vitest.config.ts`
- `tests/test_issue_11.py`

**Archivos de implementación:**
- `apps/api/src/auth/types.ts`
- `apps/api/src/auth/env.ts`
- `apps/api/package.json`
- `pnpm-lock.yaml`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T3: API: verifyToken (función pura)

Crear src/auth/verifyToken.ts que llama auth.verifyIdToken(token) y retorna el decoded token; unit tests con auth mockeado

**Tests:**
- `apps/api/test/auth.test.ts::test_verifyToken_returns_decoded_token`: verifyToken({ verifyIdToken: vi.fn().mockResolvedValue({ uid: 'u1', email: 'a@b.com', email_verified: true }) }, 'tok') resuelve con el objeto decodificado
- `apps/api/test/auth.test.ts::test_verifyToken_throws_on_invalid_token`: verifyToken({ verifyIdToken: vi.fn().mockRejectedValue(new Error('invalid')) }, 'bad') rechaza propagando el error

**Archivos de soporte de tests:**
- `apps/api/package.json`
- `apps/api/tsconfig.json`
- `apps/api/vitest.config.ts`

**Archivos de implementación:**
- `apps/api/src/auth/verifyToken.ts`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T4: API: upsertUser con lógica ADMIN_EMAILS

Crear src/auth/upsertUser.ts con INSERT ON CONFLICT DO UPDATE en users; role = 'admin' si email ∈ adminEmails (trim+case-insensitive) AND email_verified, si no 'user'; unit tests con db falso

**Tests:**
- `apps/api/test/auth.test.ts::test_upsertUser_returns_user_role_when_not_in_admin_emails`: upsertUser(fakeDb, { uid, email: 'other@x.com', email_verified: true }, ['admin@x.com']) retorna AuthUser con role 'user'
- `apps/api/test/auth.test.ts::test_upsertUser_returns_admin_role_when_in_admin_emails_and_verified`: upsertUser(fakeDb, { uid, email: 'admin@x.com', email_verified: true }, ['admin@x.com']) retorna AuthUser con role 'admin'
- `apps/api/test/auth.test.ts::test_upsertUser_returns_user_role_when_in_admin_emails_but_not_verified`: upsertUser(fakeDb, { uid, email: 'admin@x.com', email_verified: false }, ['admin@x.com']) retorna AuthUser con role 'user'
- `apps/api/test/auth.test.ts::test_upsertUser_admin_email_comparison_is_case_insensitive_and_trimmed`: upsertUser(fakeDb, { uid, email: '  Admin@X.COM  ', email_verified: true }, ['admin@x.com']) retorna role 'admin'
- `apps/api/test/auth.test.ts::test_upsertUser_role_recalculated_every_upsert`: upsertUser con email en lista → 'admin'; mismo fakeDb con lista vacía → 'user'; el role no queda fijo del insert inicial

**Archivos de soporte de tests:**
- `apps/api/package.json`
- `apps/api/tsconfig.json`
- `apps/api/vitest.config.ts`

**Archivos de implementación:**
- `apps/api/src/auth/upsertUser.ts`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T5: API: plugin auth + requireAdmin + rutas /me y /admin/ping

Crear src/plugins/auth.ts, src/plugins/requireAdmin.ts, src/types/fastify.d.ts; modificar buildApp para aceptar auth e incluir GET /me y GET /admin/ping; unit tests con mocks

**Tests:**
- `apps/api/test/auth.test.ts::test_auth_plugin_returns_401_without_token`: GET /me sin Authorization header → statusCode 401
- `apps/api/test/auth.test.ts::test_auth_plugin_returns_401_with_invalid_token`: GET /me con token inválido (verifyIdToken rechaza) → statusCode 401
- `apps/api/test/auth.test.ts::test_auth_plugin_returns_200_and_user_with_valid_token`: GET /me con token válido (verifyIdToken resuelve, db retorna user) → statusCode 200, body contiene { id, uid, email, role }
- `apps/api/test/auth.test.ts::test_requireAdmin_returns_403_for_user_role`: GET /admin/ping con token válido de role 'user' → statusCode 403
- `apps/api/test/auth.test.ts::test_requireAdmin_returns_200_for_admin_role`: GET /admin/ping con token válido de role 'admin' → statusCode 200

**Archivos de soporte de tests:**
- `apps/api/package.json`
- `apps/api/tsconfig.json`
- `apps/api/vitest.config.ts`

**Archivos de implementación:**
- `apps/api/src/plugins/auth.ts`
- `apps/api/src/plugins/requireAdmin.ts`
- `apps/api/src/types/fastify.d.ts`
- `apps/api/src/app.ts`

**Progreso:**
- [x] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

### T6: API: inicialización firebase-admin en src/index.ts

Modificar src/index.ts para llamar requireFirebaseProjectId, initializeApp de firebase-admin y pasar admin.auth() como auth a buildApp

**Tests:**
- `tests/test_issue_11.py::test_api_index_requires_firebase_project_id`: apps/api/src/index.ts contiene 'requireFirebaseProjectId'
- `tests/test_issue_11.py::test_api_index_calls_initialize_app`: apps/api/src/index.ts contiene 'initializeApp'

**Archivos de soporte de tests:**
- `tests/test_issue_11.py`

**Archivos de implementación:**
- `apps/api/src/index.ts`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

### T7: Admin: firebase config + AuthContext + Login + App

Agregar firebase@12.19.0; crear src/auth/firebaseConfig.ts con connectAuthEmulator condicional (VITE_FIREBASE_AUTH_EMULATOR_HOST); crear AuthContext que llama GET /me para obtener role y hace signOut si role !== admin; crear Login.tsx mínimo; modificar App.tsx; unit tests

**Tests:**
- `apps/admin/test/AuthContext.test.tsx::test_firebaseConfig_calls_connectAuthEmulator_when_env_set`: Cuando VITE_FIREBASE_AUTH_EMULATOR_HOST='localhost:9099', connectAuthEmulator es llamado con 'http://localhost:9099'
- `apps/admin/test/AuthContext.test.tsx::test_firebaseConfig_does_not_call_connectAuthEmulator_when_env_not_set`: Cuando VITE_FIREBASE_AUTH_EMULATOR_HOST no está definido, connectAuthEmulator no es llamado
- `apps/admin/test/AuthContext.test.tsx::test_login_calls_signInWithPopup_with_google_provider`: Al llamar login() del AuthContext, signInWithPopup es llamado con GoogleAuthProvider
- `apps/admin/test/AuthContext.test.tsx::test_auth_context_sets_role_admin_when_me_returns_admin`: Cuando GET /me retorna { role: 'admin' }, el context expone role === 'admin' y no llama signOut
- `apps/admin/test/AuthContext.test.tsx::test_auth_context_calls_signout_when_me_returns_user_role`: Cuando GET /me retorna { role: 'user' }, el context llama signOut automáticamente
- `apps/admin/test/AuthContext.test.tsx::test_app_renders_login_when_not_authenticated`: App sin usuario autenticado renderiza el componente Login
- `apps/admin/test/AuthContext.test.tsx::test_app_renders_content_when_authenticated_as_admin`: App con usuario autenticado y role 'admin' renderiza contenido principal, no Login

**Archivos de soporte de tests:**
- `apps/admin/package.json`
- `apps/admin/tsconfig.json`
- `apps/admin/vitest.config.ts`
- `apps/admin/test/setup.ts`

**Archivos de implementación:**
- `apps/admin/src/auth/firebaseConfig.ts`
- `apps/admin/src/auth/AuthContext.tsx`
- `apps/admin/src/pages/Login.tsx`
- `apps/admin/src/App.tsx`
- `apps/admin/package.json`
- `pnpm-lock.yaml`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

### T8: Mobile: src/auth/index.ts + firebaseAuth.ts + AuthContext + pantalla login + unit tests

Agregar firebase@12.19.0, @react-native-google-signin/google-signin@16.x, @react-native-async-storage/async-storage; configurar app.json; crear funciones puras en src/auth/index.ts; crear firebaseAuth.ts con connectAuthEmulator condicional; crear AuthContext y pantalla login mínima; excluir integration de vitest.config.ts; unit tests con mocks incluyendo test de connectAuthEmulator condicional

**Tests:**
- `apps/mobile/test/auth.test.ts::test_signInWithEmail_calls_firebase_signInWithEmailAndPassword`: signInWithEmail(mockAuth, 'a@b.com', 'pass') llama signInWithEmailAndPassword(mockAuth, 'a@b.com', 'pass')
- `apps/mobile/test/auth.test.ts::test_signInWithGoogle_calls_GoogleSignin_and_signInWithCredential`: signInWithGoogle(mockAuth) llama GoogleSignin.signIn() y luego signInWithCredential con GoogleAuthProvider.credential
- `apps/mobile/test/auth.test.ts::test_signOut_calls_firebase_signOut`: signOut(mockAuth) llama el signOut de firebase/auth con mockAuth
- `apps/mobile/test/auth.test.ts::test_signInWithEmail_propagates_error_on_failure`: signInWithEmail con mock que rechaza propaga el error
- `apps/mobile/test/auth.test.ts::test_firebaseAuth_calls_connectAuthEmulator_when_env_set`: Cuando EXPO_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST='localhost:9099', connectAuthEmulator es llamado con 'http://localhost:9099'
- `apps/mobile/test/auth.test.ts::test_firebaseAuth_does_not_call_connectAuthEmulator_when_env_not_set`: Cuando EXPO_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST no está definido, connectAuthEmulator no es llamado

**Archivos de soporte de tests:**
- `apps/mobile/package.json`
- `apps/mobile/tsconfig.json`
- `apps/mobile/vitest.config.ts`

**Archivos de implementación:**
- `apps/mobile/src/auth/index.ts`
- `apps/mobile/src/auth/firebaseAuth.ts`
- `apps/mobile/src/auth/AuthContext.tsx`
- `apps/mobile/app/login.tsx`
- `apps/mobile/app/index.tsx`
- `apps/mobile/app.json`
- `apps/mobile/package.json`
- `apps/mobile/vitest.config.ts`
- `pnpm-lock.yaml`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

### T9: CI: setup-java + emulators:exec + archivos de integración + README

Modificar ci.yml: agregar actions/setup-java (temurin 21), step firebase emulators:exec envolviendo test:integration de api y mobile con env vars correctas; crear apps/api/test/auth.integration.test.ts, apps/mobile/test/auth.integration.test.ts, apps/mobile/vitest.integration.config.ts, script test:integration de mobile; actualizar vitest.integration.config.ts de api con globalSetup y testTimeout; actualizar README

**Tests:**
- `tests/test_issue_11.py::test_ci_has_setup_java_temurin_21`: ci.yml job 'node' contiene actions/setup-java con distribution 'temurin' y java-version '21'
- `tests/test_issue_11.py::test_ci_has_firebase_emulators_exec_with_auth_and_project`: ci.yml contiene 'firebase emulators:exec' con '--only auth' y '--project demo-trainia'
- `tests/test_issue_11.py::test_ci_emulators_exec_wraps_both_integration_tests`: El step con emulators:exec contiene test:integration de @trainia/api y @trainia/mobile en el mismo comando
- `tests/test_issue_11.py::test_ci_integration_step_has_firebase_project_id_env`: El step de emulators:exec en ci.yml tiene env FIREBASE_PROJECT_ID=demo-trainia
- `tests/test_issue_11.py::test_ci_integration_step_has_firebase_auth_emulator_host_env`: El step de emulators:exec en ci.yml tiene env FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099
- `tests/test_issue_11.py::test_ci_integration_step_has_expo_firebase_auth_emulator_host_env`: El step de emulators:exec en ci.yml tiene env EXPO_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099
- `tests/test_issue_11.py::test_ci_integration_step_has_admin_emails_env`: El step de emulators:exec en ci.yml tiene env ADMIN_EMAILS=admin@test.local
- `tests/test_issue_11.py::test_api_auth_integration_test_exists`: apps/api/test/auth.integration.test.ts existe
- `tests/test_issue_11.py::test_api_auth_integration_test_covers_required_cases`: auth.integration.test.ts contiene referencias a '/me' y '/admin/ping' y a los casos 401, 403, 200
- `tests/test_issue_11.py::test_mobile_auth_integration_test_exists`: apps/mobile/test/auth.integration.test.ts existe
- `tests/test_issue_11.py::test_mobile_auth_integration_test_imports_from_src_auth`: apps/mobile/test/auth.integration.test.ts importa desde '../src/auth' (no desde 'firebase' directamente)
- `tests/test_issue_11.py::test_mobile_auth_integration_test_covers_signin_and_wrong_password`: apps/mobile/test/auth.integration.test.ts contiene casos de signInWithEmail exitoso y con contraseña incorrecta
- `tests/test_issue_11.py::test_mobile_vitest_integration_config_exists`: apps/mobile/vitest.integration.config.ts existe
- `tests/test_issue_11.py::test_mobile_package_json_has_test_integration_script`: apps/mobile/package.json scripts contiene 'test:integration' apuntando a vitest.integration.config.ts
- `tests/test_issue_11.py::test_readme_documents_jdk_21`: README.md contiene 'JDK 21' o 'Java 21'
- `tests/test_issue_11.py::test_readme_documents_firebase_env_vars`: README.md contiene FIREBASE_PROJECT_ID, FIREBASE_AUTH_EMULATOR_HOST y EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID

**Archivos de soporte de tests:**
- `tests/test_issue_11.py`
- `apps/api/vitest.integration.config.ts`
- `apps/mobile/vitest.integration.config.ts`

**Archivos de implementación:**
- `apps/api/test/auth.integration.test.ts`
- `apps/api/vitest.integration.config.ts`
- `apps/mobile/test/auth.integration.test.ts`
- `apps/mobile/vitest.integration.config.ts`
- `apps/mobile/package.json`
- `.github/workflows/ci.yml`
- `README.md`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

## Fuera de alcance

- Proyecto Firebase real en GCP (depende de issue de infra)
- Verificación de email post-registro (flujo de email verification en mobile/admin)
- Recuperación de contraseña
- Login con email/password en admin (solo Google en admin)
- Roles adicionales más allá de user/admin
- Pantalla de onboarding post-login
- UI/diseño de las pantallas de login (solo funcionalidad mínima)
- Configuración de EAS Build para development build de mobile (issue #14)
- APNs/FCM para push notifications
- Revocación de tokens (token blacklist)
- Rate limiting en endpoints de auth

## Riesgos

- @react-native-google-signin/google-signin@16.x requiere módulo nativo: en tests de Vitest (Node) se mockea completo; si la API del mock no cubre exactamente la versión 16.x pueden surgir errores de tipos en GREEN
- getReactNativePersistence requiere @react-native-async-storage/async-storage; la versión compatible con Expo SDK 57 debe verificarse con expo install — si la versión cambia puede romper el init en mobile
- firebase emulators:exec con --project demo-trainia requiere firebase.json en el directorio desde donde se corre (raíz del repo); si CI corre desde otro directorio el emulador no arranca
- El test de integración de mobile en Node importa firebase/auth sin react-native gracias a la separación firebaseAuth.ts/index.ts; si alguna dependencia transitiva de firebase@12.19.0 importa APIs de react-native en Node el test falla en CI
- connectAuthEmulator debe llamarse solo una vez por instancia Auth; si los tests reinicializan la app de Firebase entre tests puede lanzar 'Auth Emulator already connected'; usar beforeAll con una sola instancia
- actions/setup-java agrega ~1min al job de CI; aceptable para Fase 0 pero a monitorear si el job crece
- El usuario admin creado en el test de integración debe tener emailVerified: true; si el emulador no lo setea por defecto al crear usuarios via Admin SDK, el upsert retornará role 'user' y el test de /admin/ping fallará

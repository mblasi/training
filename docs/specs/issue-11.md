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
| D16 | Vuelta a RED de T4: tests de upsertUser tautológicos y con error de lint | Rehacer apps/api/test/auth.test.ts (bloque upsertUser) para T4: (1) el fake db captura lo que upsertUser pasa a insert(users).values(row) y a onConflictDoUpdate({target, set}); los asserts verifican row.role y set.role (admin solo si email en ADMIN_EMAILS con trim+case-insensitive Y email_verified===true; user en otro caso), row.firebase_uid===uid, target===users.firebase_uid; (2) el fake NO calcula el rol: returning() devuelve una fila construida a partir del row recibido, con la forma real del schema (id, firebase_uid, email, role, locale, created_at); el AuthUser devuelto mapea firebase_uid→uid; (3) recálculo en cada login: misma llamada con lista vacía → values/set con role 'user'; (4) el archivo pasa eslint y tsc salvo por el import faltante de ../src/auth/upsertUser.js (sin any, sin parámetros sin usar). | Rehacer apps/api/test/auth.test.ts (bloque upsertUser) para T4: (1) el fake db captura lo que upsertUser pasa a insert(users).values(row) y a onConflictDoUpdate({target,set}); los asserts verifican row.role y set.role (admin solo si email en ADMIN_EMAILS con trim+case-insensitive Y email_verified===true; user en otro caso), row.firebase_uid===uid, target===users.firebase_uid; (2) el fake NO calcula el rol: returning() devuelve una fila construida a partir del row recibido, con la forma real del schema (id, firebase_uid, email, role, locale, created_at); el AuthUser devuelto mapea firebase_uid→uid; (3) recálculo en cada login: misma llamada con lista vacía → values/set con role 'user'; (4) el archivo pasa eslint y tsc salvo por el import faltante de ../src/auth/upsertUser.js (sin any, sin parámetros sin usar). | Decisión tomada durante implementación |
| D17 | La implementación actual no está funcionando porque los hooks `preHandler` no están impidiendo que los handlers de las rutas se ejecuten cuando hago `reply.send()`. He intentado con y sin `await` en el `reply.send()`, pero el problema persiste: las rutas retornan 200 en lugar de 401/403. | Dos cosas. (1) Causa técnica del /DESVIO: en hooks async de Fastify, responder temprano exige `return reply.code(401).send(...)` (devolver reply); con `send(); return;` Fastify sigue al handler. Mismo patrón en requireAdmin (403). Mantener el encapsulamiento actual (register sin fastify-plugin) para que los hooks apliquen solo a /me y /admin/ping. (2) Los tests de RED de T5 contradicen D4 y D6: el plugin no debe hacer SELECT de users; según el issue y D4 orquesta verifyToken(auth, token) → upsertUser(db, decoded, adminEmails) en cada request autenticado (así el rol se recalcula desde ADMIN_EMAILS, D6). buildApp recibe adminEmails: string[] inyectado (buildApp({ db, auth, adminEmails })); src/index.ts lo parsea de ADMIN_EMAILS (split por coma, trim, vacíos fuera) en T6. Rehacer los tests de T5: el fake db implementa la cadena insert(users).values(row).onConflictDoUpdate({target, set}).returning() devolviendo la fila construida del row recibido con la forma real del schema (id, firebase_uid, email, role, locale, created_at), como el fake de T4 (reutilizar createFakeDb); casos: sin header → 401 y verifyIdToken no llamado; token inválido → 401 y db.insert no llamado; token válido → 200 con { id, uid, email, role }; /admin/ping con usuario fuera de adminEmails → 403; con email en adminEmails y email_verified → 200 { ok: true }. Sin `as never` en buildApp: tipar los fakes con la interfaz real. Tests pasan eslint y tsc salvo el import/props faltantes del código de producción. | Dos cosas. (1) Causa técnica del /DESVIO: en hooks async de Fastify, responder temprano exige `return reply.code(401).send(...)` (devolver reply); con `send(); return;` Fastify sigue al handler. Mismo patrón en requireAdmin (403). Mantener el encapsulamiento actual (register sin fastify-plugin) para que los hooks apliquen solo a /me y /admin/ping. (2) Los tests de RED de T5 contradicen D4 y D6: el plugin no debe hacer SELECT de users; según el issue y D4 orquesta verifyToken(auth, token) → upsertUser(db, decoded, adminEmails) en cada request autenticado (así el rol se recalcula desde ADMIN_EMAILS, D6). buildApp recibe adminEmails: string[] inyectado (buildApp({ db, auth, adminEmails })); src/index.ts lo parsea de ADMIN_EMAILS (split por coma, trim, vacíos fuera) en T6. Rehacer los tests de T5: el fake db implementa la cadena insert(users).values(row).onConflictDoUpdate({target,set}).returning() devolviendo la fila construida del row recibido con la forma real del schema (id, firebase_uid, email, role, locale, created_at), como el fake de T4 (reutilizar createFakeDb); casos: sin header → 401 y verifyIdToken no llamado; token inválido → 401 y db.insert no llamado; token válido → 200 con { id, uid, email, role }; /admin/ping con usuario fuera de adminEmails → 403; con email en adminEmails y email_verified → 200 { ok: true }. Sin `as never` en buildApp: tipar los fakes con la interfaz real. Tests pasan eslint y tsc salvo el import/props faltantes del código de producción. | Decisión tomada durante implementación |
| D18 | <test y contradicción>` y frená". | Opción 2, y es regla general: buildApp({ db, auth, adminEmails }) con auth y adminEmails REQUERIDOS (D8 y D15 de #10: sin parámetros opcionales ni ramas sin-auth en producción solo para no tocar tests viejos). En RED sí se pueden modificar archivos de test existentes aunque no figuren en test_support_files (is_test_file los permite): actualizá apps/api/test/health.test.ts (4 llamadas) y apps/api/test/db.integration.test.ts (1 llamada) para pasar `auth` (un fake { verifyIdToken: vi.fn() } tipado con la interfaz real, sin `as never` nuevo más allá del que ya tenían para db) y `adminEmails: []`. Sin cambiar qué verifican esos tests. apps/api/src/index.ts lo ajusta T6 (en GREEN de T6), no ahora. Después de modificar, tsc de esos archivos solo puede fallar por la prop faltante del código de producción; eslint 0 problemas. | Opción 2, y es regla general: buildApp({ db, auth, adminEmails }) con auth y adminEmails REQUERIDOS (D8 y D15 de #10: sin parámetros opcionales ni ramas sin-auth en producción solo para no tocar tests viejos). En RED sí se pueden modificar archivos de test existentes aunque no figuren en test_support_files (is_test_file los permite): actualizá apps/api/test/health.test.ts (4 llamadas) y apps/api/test/db.integration.test.ts (1 llamada) para pasar `auth` (un fake { verifyIdToken: vi.fn() } tipado con la interfaz real, sin `as never` nuevo más allá del que ya tenían para db) y `adminEmails: []`. Sin cambiar qué verifican esos tests. apps/api/src/index.ts lo ajusta T6 (en GREEN de T6), no ahora. Después de modificar, tsc de esos archivos solo puede fallar por la prop faltante del código de producción; eslint 0 problemas. | Decisión tomada durante implementación |
| D19 | El hook onRequest del auth plugin nunca se ejecuta en los tests: el mock verifyIdToken no es llamado. Probé encapsular las rutas en un contexto hijo del plugin y usar function en vez de arrow function. Los tests construyen la app con buildApp({db, auth}) donde auth tiene verifyIdToken mocked, pero el onRequest hook no llega a llamarlo. El test sin token pasa (ruta /me existe), pero con token el hook no se activa. ¿El problema está en cómo Fastify maneja plugins async en tests con inject, o hay un patrón diferente para implementar auth middleware en Fastify que funcione con la estructura de tests esperada? | Causa raíz (mi respuesta anterior sobre el encapsulamiento estaba mal, corrijo): en Fastify un hook agregado dentro de un plugin SIN fastify-plugin solo aplica al contexto hijo de ese plugin; authPlugin se registra con register() y las rutas viven en el scope padre, por eso el hook nunca corre y verifyIdToken no se llama. Solución sin dependencias nuevas: authPlugin y requireAdmin dejan de ser plugins y pasan a ser FACTORIES DE HOOK (mismos archivos plugins/auth.ts y plugins/requireAdmin.ts): `createAuthHook({ auth, db, adminEmails })` devuelve un hook async (request, reply) y `requireAdmin` es un hook async. En buildApp se agregan con addHook en el mismo scope donde se declaran las rutas: scope /me → `scope.addHook('onRequest', createAuthHook(...))`; scope admin → idem + `scope.addHook('preHandler', requireAdmin)`, así el hook aplica a las rutas de ese scope y /health queda público. Registrar este desvío como decisión: nombres de export createAuthHook/requireAdmin en vez de plugin. Además corregí tres cosas del borrador que contradicen decisiones cerradas: (1) buildApp({ db, auth, adminEmails }) con auth y adminEmails REQUERIDOS, sin `if (auth)` ni defaults (D8 + lo que respondí antes); los tests de health/db.integration ya pasan esos params. (2) Sin header Authorization o con formato distinto de 'Bearer <token>' el hook responde 401 (hoy deja pasar): `return reply.code(401).send({ error: 'Unauthorized' })`, siempre con `return reply...` para cortar la cadena; token inválido o sin email → 401, y db.insert no se llama. (3) Sin `db as never`: tipar la dependencia con la interfaz mínima que upsertUser realmente usa (o reutilizar su tipo de parámetro). /admin/ping responde exactamente lo que asertan los tests. Si algún test de T5 todavía falla, leé la salida real antes de cambiar el diseño. | Causa raíz (mi respuesta anterior sobre el encapsulamiento estaba mal, corrijo): en Fastify un hook agregado dentro de un plugin SIN fastify-plugin solo aplica al contexto hijo de ese plugin; authPlugin se registra con register() y las rutas viven en el scope padre, por eso el hook nunca corre y verifyIdToken no se llama. Solución sin dependencias nuevas: authPlugin y requireAdmin dejan de ser plugins y pasan a ser FACTORIES DE HOOK (mismos archivos plugins/auth.ts y plugins/requireAdmin.ts): `createAuthHook({ auth, db, adminEmails })` devuelve un hook async (request, reply) y `requireAdmin` es un hook async. En buildApp se agregan con addHook en el mismo scope donde se declaran las rutas: scope /me → `scope.addHook('onRequest', createAuthHook(...))`; scope admin → idem + `scope.addHook('preHandler', requireAdmin)`, así el hook aplica a las rutas de ese scope y /health queda público. Registrar este desvío como decisión: nombres de export createAuthHook/requireAdmin en vez de plugin. Además corregí tres cosas del borrador que contradicen decisiones cerradas: (1) buildApp({ db, auth, adminEmails }) con auth y adminEmails REQUERIDOS, sin `if (auth)` ni defaults (D8 + lo que respondí antes); los tests de health/db.integration ya pasan esos params. (2) Sin header Authorization o con formato distinto de 'Bearer <token>' el hook responde 401 (hoy deja pasar): `return reply.code(401).send({ error: 'Unauthorized' })`, siempre con `return reply...` para cortar la cadena; token inválido o sin email → 401, y db.insert no se llama. (3) Sin `db as never`: tipar la dependencia con la interfaz mínima que upsertUser realmente usa (o reutilizar su tipo de parámetro). /admin/ping responde exactamente lo que asertan los tests. Si algún test de T5 todavía falla, leé la salida real antes de cambiar el diseño. | Decisión tomada durante implementación |
| D20 | T5: diseño consolidado de auth en buildApp (reemplaza D17-D19) | (1) authPlugin/requireAdmin NO son plugins de Fastify: un hook agregado dentro de register() sin fastify-plugin solo aplica al contexto hijo y nunca corre sobre las rutas del padre. Son factories/hooks: createAuthHook({ auth, db, adminEmails }) en plugins/auth.ts y requireAdmin (hook async) en plugins/requireAdmin.ts; buildApp los agrega con addHook en el mismo scope donde declara /me y /admin/ping; /health queda público. Responder siempre con `return reply.code(N).send(...)` para cortar la cadena. (2) buildApp({ db, auth, adminEmails }) con los tres REQUERIDOS, sin `if (auth)` ni defaults; el RED actualiza health.test.ts y db.integration.test.ts a la firma nueva (por eso están en test_support_files) pasando un fake de auth tipado y adminEmails: []; src/index.ts lo cablea en T6. (3) El hook hace verifyToken(auth, token) → upsertUser(db, decoded, adminEmails) en cada request (el rol se recalcula desde ADMIN_EMAILS, D6); sin header, formato distinto de 'Bearer <token>', token inválido o sin email → 401. (4) Tests: fake db con la cadena real insert/values/onConflictDoUpdate/returning devolviendo una fila con la forma del schema; nada de casts sobre el argumento completo de buildApp (`} as never)` lo rechaza el harness, #35); la db se pasa con cast por propiedad o variable si hace falta. Los fakes se tipan con la interfaz real de BuildAppOptions. | (1) authPlugin/requireAdmin NO son plugins de Fastify: un hook agregado dentro de register() sin fastify-plugin solo aplica al contexto hijo y nunca corre sobre las rutas del padre. Son factories/hooks: createAuthHook({ auth, db, adminEmails }) en plugins/auth.ts y requireAdmin (hook async) en plugins/requireAdmin.ts; buildApp los agrega con addHook en el mismo scope donde declara /me y /admin/ping; /health queda público. Responder siempre con `return reply.code(N).send(...)` para cortar la cadena. (2) buildApp({ db, auth, adminEmails }) con los tres REQUERIDOS, sin `if (auth)` ni defaults; el RED actualiza health.test.ts y db.integration.test.ts a la firma nueva (por eso están en test_support_files) pasando un fake de auth tipado y adminEmails: []; src/index.ts lo cablea en T6. (3) El hook hace verifyToken(auth, token) → upsertUser(db, decoded, adminEmails) en cada request (el rol se recalcula desde ADMIN_EMAILS, D6); sin header, formato distinto de 'Bearer <token>', token inválido o sin email → 401. (4) Tests: fake db con la cadena real insert/values/onConflictDoUpdate/returning devolviendo una fila con la forma del schema; nada de casts sobre el argumento completo de buildApp (`} as never)` lo rechaza el harness, #35); la db se pasa con cast por propiedad o variable si hace falta. Los fakes se tipan con la interfaz real de BuildAppOptions. | Decisión tomada durante implementación |
| D21 | El problema está en src/index.ts: todavía no tiene los parámetros auth y adminEmails según mi implementación de T5, pero esos parámetros los va a agregar T6 (que es la tarea siguiente). Los tests de T5 pasan porque usan buildApp correctamente, pero src/index.ts necesita ser actualizado. Sin embargo, T6 es el responsable de actualizar src/index.ts. | Decisión: el typecheck es parte del test_command, así que GREEN de T5 NO puede cerrar con src/index.ts roto; es un hueco de la spec (una tarea que vuelve requeridos auth y adminEmails debe incluir a quien llama a buildApp). Regla general: la tarea que cambia una firma requerida arregla en el mismo GREEN a TODOS los llamadores de producción. Entonces: (1) en esta tarea sí modificá apps/api/src/index.ts con el cableado real y completo, no un stub ni un `as never`: requireFirebaseProjectId(process.env) antes de inicializar; initializeApp({ projectId }) de firebase-admin/app (sin credential explícita: ADC en prod, emulador si FIREBASE_AUTH_EMULATOR_HOST); auth = { verifyIdToken: (token) => getAuth().verifyIdToken(token) } con getAuth de firebase-admin/auth; adminEmails = (process.env.ADMIN_EMAILS ?? '').split(', ').map(e => e.trim()).filter(Boolean); buildApp({ db: { pool, db }, auth, adminEmails }). Dejá la lógica de parseo en una función exportada chica (p. ej. parseAdminEmails en src/auth/env.ts) si queda más limpio; no agregues tests nuevos (GREEN no toca tests). La tarea T6 se reestructura aparte; vos no la anticipes ni la menciones. (2) Arreglá el error real de app.ts(60, 43) TS2740: al hook se le pasa un DbClient donde espera NodePgDatabase. Mirá qué pasan los tests (el fake) y qué usa upsertUser, y pasá `db.db` con el tipo correcto; sin `as never` ni `as any` en código de producción. Criterio de cierre: `cd apps/api && corepack pnpm exec tsc --noEmit` sin errores, `corepack pnpm lint` en 0 y los tests de T5 y los existentes pasando. | Decisión: el typecheck es parte del test_command, así que GREEN de T5 NO puede cerrar con src/index.ts roto; es un hueco de la spec (una tarea que vuelve requeridos auth y adminEmails debe incluir a quien llama a buildApp). Regla general: la tarea que cambia una firma requerida arregla en el mismo GREEN a TODOS los llamadores de producción. Entonces: (1) en esta tarea sí modificá apps/api/src/index.ts con el cableado real y completo, no un stub ni un `as never`: requireFirebaseProjectId(process.env) antes de inicializar; initializeApp({ projectId }) de firebase-admin/app (sin credential explícita: ADC en prod, emulador si FIREBASE_AUTH_EMULATOR_HOST); auth = { verifyIdToken: (token) => getAuth().verifyIdToken(token) } con getAuth de firebase-admin/auth; adminEmails = (process.env.ADMIN_EMAILS ?? '').split(',').map(e => e.trim()).filter(Boolean); buildApp({ db: { pool, db }, auth, adminEmails }). Dejá la lógica de parseo en una función exportada chica (p. ej. parseAdminEmails en src/auth/env.ts) si queda más limpio; no agregues tests nuevos (GREEN no toca tests). La tarea T6 se reestructura aparte; vos no la anticipes ni la menciones. (2) Arreglá el error real de app.ts(60,43) TS2740: al hook se le pasa un DbClient donde espera NodePgDatabase. Mirá qué pasan los tests (el fake) y qué usa upsertUser, y pasá `db.db` con el tipo correcto; sin `as never` ni `as any` en código de producción. Criterio de cierre: `cd apps/api && corepack pnpm exec tsc --noEmit` sin errores, `corepack pnpm lint` en 0 y los tests de T5 y los existentes pasando. | Decisión tomada durante implementación |
| D22 | La estructura que pasa el test es `{ db: fakeDb as never }` donde `fakeDb` tiene métodos insert() directamente, pero mi interfaz BuildAppOptions.db espera `{ pool: Pool, db: NodePgDatabase }`. Para que los tests pasen sin modificarlos, necesito: (a) cambiar BuildAppOptions para que `db` sea directamente NodePgDatabase y `pool` un parámetro aparte, o (b) envolver fakeDb en los tests como `{ db: fakeDb }`. Según D20, no puedo modificar tests en GREEN. ¿Cambio la interfaz o hay otra forma? | Decisión: NO cambies la interfaz. El contrato BuildAppOptions.db es DbClient { pool: Pool; db: NodePgDatabase } desde #10 (D15) y /health usa db.pool; los tests de health y db.integration lo respetan. El defecto está en los tests de RED de auth.test.ts: pasan el fake de la DB directamente como `db: fakeDb as never`, que no tiene la forma de DbClient (por eso el cast lo esconde del typecheck). Hay que volver a RED y corregir SOLO auth.test.ts: en todos los buildApp del bloque de auth, pasar `db: { pool: <fake pool>, db: fakeDb as never }` donde el fake pool es `{ query: vi.fn() } as never` (cast por propiedad, permitido), de modo que el hook use `db.db` para el upsert y el resto de la forma sea la real. Mantener todo lo demás: asserts sobre calls del fake (row.role, set.role, target), el fake devolviendo la fila con la forma del schema, los 5 casos, sin cast sobre el argumento completo de buildApp. No toques health.test.ts ni db.integration.test.ts (ya están bien). Es la única vuelta a RED que permite el harness en esta corrida: revisá antes de terminar que NO quede ningún otro test del archivo con `db` mal formado, que eslint dé 0 y que tsc solo falle por código de producción faltante. | Decisión: NO cambies la interfaz. El contrato BuildAppOptions.db es DbClient { pool: Pool; db: NodePgDatabase } desde #10 (D15) y /health usa db.pool; los tests de health y db.integration lo respetan. El defecto está en los tests de RED de auth.test.ts: pasan el fake de la DB directamente como `db: fakeDb as never`, que no tiene la forma de DbClient (por eso el cast lo esconde del typecheck). Hay que volver a RED y corregir SOLO auth.test.ts: en todos los buildApp del bloque de auth, pasar `db: { pool: <fake pool>, db: fakeDb as never }` donde el fake pool es `{ query: vi.fn() } as never` (cast por propiedad, permitido), de modo que el hook use `db.db` para el upsert y el resto de la forma sea la real. Mantener todo lo demás: asserts sobre calls del fake (row.role, set.role, target), el fake devolviendo la fila con la forma del schema, los 5 casos, sin cast sobre el argumento completo de buildApp. No toques health.test.ts ni db.integration.test.ts (ya están bien). Es la única vuelta a RED que permite el harness en esta corrida: revisá antes de terminar que NO quede ningún otro test del archivo con `db` mal formado, que eslint dé 0 y que tsc solo falle por código de producción faltante. | Decisión tomada durante implementación |
| D23 | El diseño de T5 hace `auth` y `adminEmails` REQUERIDOS en `buildApp` pero no actualiza `src/index.ts` (eso es T6). Esto deja el código en un estado que no compila entre T5 y T6. Opciones: (1) hacer `auth` y `adminEmails` opcionales con defaults en T5, y quitarlos en T6 GREEN; (2) actualizar `src/index.ts` completamente en T5 GREEN (adelantar parte de T6); (3) hacer `auth` y `adminEmails` opcionales sin defaults (con check en runtime), mantener el requerido en el tipo para los tests. | Opción 2, y ya estaba decidida en D21 (releé las decisiones de la spec): actualizá apps/api/src/index.ts COMPLETO en este GREEN. No hagas auth/adminEmails opcionales ni agregues defaults (opciones 1 y 3 prohibidas por D20). Es lo único que falta: hoy los 52 tests pasan y el único error de `tsc --noEmit` es src/index.ts(8, 22) por faltar auth y adminEmails. Cableado: const projectId = requireFirebaseProjectId(process.env) (src/auth/env.ts ya existe, T2); initializeApp({ projectId }) de 'firebase-admin/app' sin credential (ADC en prod, emulador si FIREBASE_AUTH_EMULATOR_HOST); const auth = { verifyIdToken: (token: string) => getAuth().verifyIdToken(token) } con getAuth de 'firebase-admin/auth'; adminEmails = (process.env.ADMIN_EMAILS ?? '').split(', ').map(e => e.trim()).filter(Boolean); buildApp({ db: { pool, db }, auth, adminEmails }). Si el parseo de ADMIN_EMAILS queda mejor como función exportada (p. ej. parseAdminEmails en src/auth/env.ts), hacelo así. Sin casts en producción. Que T6 después solo agregue sus tests de verificación sobre index.ts no es tu problema. Criterio de cierre: `cd apps/api && corepack pnpm exec tsc --noEmit` y `corepack pnpm lint` en 0, tests pasando. | Opción 2, y ya estaba decidida en D21 (releé las decisiones de la spec): actualizá apps/api/src/index.ts COMPLETO en este GREEN. No hagas auth/adminEmails opcionales ni agregues defaults (opciones 1 y 3 prohibidas por D20). Es lo único que falta: hoy los 52 tests pasan y el único error de `tsc --noEmit` es src/index.ts(8,22) por faltar auth y adminEmails. Cableado: const projectId = requireFirebaseProjectId(process.env) (src/auth/env.ts ya existe, T2); initializeApp({ projectId }) de 'firebase-admin/app' sin credential (ADC en prod, emulador si FIREBASE_AUTH_EMULATOR_HOST); const auth = { verifyIdToken: (token: string) => getAuth().verifyIdToken(token) } con getAuth de 'firebase-admin/auth'; adminEmails = (process.env.ADMIN_EMAILS ?? '').split(',').map(e => e.trim()).filter(Boolean); buildApp({ db: { pool, db }, auth, adminEmails }). Si el parseo de ADMIN_EMAILS queda mejor como función exportada (p. ej. parseAdminEmails en src/auth/env.ts), hacelo así. Sin casts en producción. Que T6 después solo agregue sus tests de verificación sobre index.ts no es tu problema. Criterio de cierre: `cd apps/api && corepack pnpm exec tsc --noEmit` y `corepack pnpm lint` en 0, tests pasando. | Decisión tomada durante implementación |
| D24 | T6 original (index.ts) se fusiona en la tarea final de CI | El cableado de apps/api/src/index.ts (requireFirebaseProjectId, initializeApp, auth con getAuth().verifyIdToken, parseo de ADMIN_EMAILS) se implementó en el GREEN de T5: hacer auth y adminEmails requeridos en buildApp obliga a actualizar a su llamador en el mismo GREEN, porque el typecheck es parte del test_command. Por eso el RED de la T6 original no podía fallar. Se elimina esa tarea y sus dos tests (test_api_index_requires_firebase_project_id, test_api_index_calls_initialize_app) pasan a la tarea final de CI/README, que sí tiene tests que fallan en RED. Regla: la tarea que vuelve requerido un parámetro de una función arregla a todos sus llamadores de producción en el mismo GREEN. | El cableado de apps/api/src/index.ts (requireFirebaseProjectId, initializeApp, auth con getAuth().verifyIdToken, parseo de ADMIN_EMAILS) se implementó en el GREEN de T5: hacer auth y adminEmails requeridos en buildApp obliga a actualizar a su llamador en el mismo GREEN, porque el typecheck es parte del test_command. Por eso el RED de la T6 original no podía fallar. Se elimina esa tarea y sus dos tests (test_api_index_requires_firebase_project_id, test_api_index_calls_initialize_app) pasan a la tarea final de CI/README, que sí tiene tests que fallan en RED. Regla: la tarea que vuelve requerido un parámetro de una función arregla a todos sus llamadores de producción en el mismo GREEN. | Decisión tomada durante implementación |
| D25 | T6/T7: los tests existentes que renderizan App o la pantalla index se actualizan en el RED | apps/admin/test/App.test.tsx (test_app_renders_trainia_heading renderiza <App /> sin props y sin AuthProvider) deja de ser válido cuando App pasa a depender del AuthContext y a mostrar Login sin usuario. Regla: la tarea que cambia el comportamiento o las dependencias de un componente actualiza en su RED los tests existentes que lo renderizan, por eso App.test.tsx figura en test_support_files de T6. En RED el test actualizado envuelve App en el AuthProvider con un valor de contexto controlado (usuario admin) o mockea el hook useAuth, y conserva la aserción del heading 'Trainia' y los tests de parseHealthResponse sin cambios; sin casts sobre el argumento completo. Mismo criterio para mobile: apps/mobile/test/health.test.ts no renderiza app/index.tsx (solo prueba parseHealthResponse), no requiere cambios; si T7 hace que app/index.tsx dependa de AuthContext no se agregan tests de render (react-native no corre en vitest/node). | apps/admin/test/App.test.tsx (test_app_renders_trainia_heading renderiza <App /> sin props y sin AuthProvider) deja de ser válido cuando App pasa a depender del AuthContext y a mostrar Login sin usuario. Regla: la tarea que cambia el comportamiento o las dependencias de un componente actualiza en su RED los tests existentes que lo renderizan, por eso App.test.tsx figura en test_support_files de T6. En RED el test actualizado envuelve App en el AuthProvider con un valor de contexto controlado (usuario admin) o mockea el hook useAuth, y conserva la aserción del heading 'Trainia' y los tests de parseHealthResponse sin cambios; sin casts sobre el argumento completo. Mismo criterio para mobile: apps/mobile/test/health.test.ts no renderiza app/index.tsx (solo prueba parseHealthResponse), no requiere cambios; si T7 hace que app/index.tsx dependa de AuthContext no se agregan tests de render (react-native no corre en vitest/node). | Decisión tomada durante implementación |

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

### T5: API: hooks de auth + requireAdmin + rutas /me y /admin/ping

Crear src/plugins/auth.ts (createAuthHook), src/plugins/requireAdmin.ts, src/types/fastify.d.ts; modificar buildApp({ db, auth, adminEmails }) con los tres requeridos e incluir GET /me y GET /admin/ping; actualizar los tests existentes que llaman a buildApp (health.test.ts, db.integration.test.ts) a la firma nueva. Ver D20.

**Tests:**
- `apps/api/test/auth.test.ts::test_auth_plugin_returns_401_without_token`: GET /me sin Authorization (o con formato distinto de 'Bearer <token>') → 401; verifyIdToken no se llama
- `apps/api/test/auth.test.ts::test_auth_plugin_returns_401_with_invalid_token`: GET /me con token que verifyIdToken rechaza → 401; db.insert no se llama
- `apps/api/test/auth.test.ts::test_auth_plugin_returns_200_and_user_with_valid_token`: GET /me con token válido → 200 con body { id, uid, email, role } construido desde la fila que devolvió el upsert (fake db con la cadena insert().values().onConflictDoUpdate().returning(), como createFakeDb de T4)
- `apps/api/test/auth.test.ts::test_requireAdmin_returns_403_for_user_role`: GET /admin/ping con email fuera de adminEmails → 403
- `apps/api/test/auth.test.ts::test_requireAdmin_returns_200_for_admin_role`: GET /admin/ping con email en adminEmails y email_verified true → 200 { ok: true }

**Archivos de soporte de tests:**
- `apps/api/package.json`
- `apps/api/tsconfig.json`
- `apps/api/vitest.config.ts`
- `apps/api/test/health.test.ts`
- `apps/api/test/db.integration.test.ts`

**Archivos de implementación:**
- `apps/api/src/plugins/auth.ts`
- `apps/api/src/plugins/requireAdmin.ts`
- `apps/api/src/types/fastify.d.ts`
- `apps/api/src/app.ts`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T6: Admin: firebase config + AuthContext + Login + App

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
- `apps/admin/test/App.test.tsx`

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

### T7: Mobile: src/auth/index.ts + firebaseAuth.ts + AuthContext + pantalla login + unit tests

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

### T8: CI: setup-java + emulators:exec + archivos de integración + README

Modificar ci.yml: agregar actions/setup-java (temurin 21), step firebase emulators:exec envolviendo test:integration de api y mobile con env vars correctas; crear apps/api/test/auth.integration.test.ts, apps/mobile/test/auth.integration.test.ts, apps/mobile/vitest.integration.config.ts, script test:integration de mobile; actualizar vitest.integration.config.ts de api con globalSetup y testTimeout; actualizar README

**Tests:**
- `tests/test_issue_11.py::test_api_index_requires_firebase_project_id`: apps/api/src/index.ts contiene 'requireFirebaseProjectId'
- `tests/test_issue_11.py::test_api_index_calls_initialize_app`: apps/api/src/index.ts contiene 'initializeApp'
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

# Trainia — Documento de diseño

Estado: v0.2 · 2026-09-28 · Decisiones de producto tomadas (ver §15)
Responsable: Matías (owner / admin)
Dominio: https://trainia.blasi.ar · Idioma/mercado inicial: español rioplatense / Argentina

---

## 1. Visión

App de entrenamiento autogestionada donde la interfaz principal es una conversación con un
"equipo técnico" de IA:

- Entrenador físico / deportólogo (carga, técnica, lesiones, periodización)
- Nutricionista deportiva (dieta, macros, hidratación, suplementación básica)
- Psicólogo deportivo (motivación, adherencia, hábitos, estrés, relación con la comida/cuerpo)

El usuario habla en lenguaje natural. Por detrás, el sistema traduce cada interacción en
cambios tipados sobre entidades (plan, rutina, dieta, objetivos, registros, recordatorios).
El modelo de datos es la única fuente de verdad; la conversación es la interfaz, no el estado.

Principios:
1. Chat-first, no chat-only: el agente responde con texto + tarjetas interactivas
   (rutina del día, gráfico de evolución, confirmar cambio de plan). Siempre hay una vista
   estructurada del estado para ver/editar sin conversar.
2. Cambios explícitos y auditables: todo cambio que el LLM propone pasa por un ChangeSet
   validado; los de alto impacto requieren confirmación del usuario.
3. Contexto construido, no acumulado: cada turno arma un prompt a medida con presupuesto de
   tokens, en vez de arrastrar el historial completo.
4. Seguridad primero: screening de salud en onboarding, detección de señales de alerta,
   derivación a profesionales humanos.

---

## 2. Decisiones técnicas

| Tema | Decisión | Alternativas descartadas / por qué |
|---|---|---|
| App usuario | **Expo (React Native + TS)**, expo-router, un solo código para iOS, Android y web. Builds y envío a stores con EAS Build/Submit | PWA sola: no llega a las stores. Capacitor sobre React/Vite: viable, pero UI no nativa, y los builds de iOS requieren una Mac (EAS los hace en la nube desde Linux). Flutter: otro lenguaje, no comparte tipos TS |
| Panel admin | Web separada (React + Vite + TS), solo para el rol admin | Meterlo en la app móvil: mezcla audiencias y tamaño de bundle |
| Backend | Node 20 + TypeScript + Fastify, monolito modular | Microservicios: prematuro. Python/FastAPI: viable, pero TS comparte tipos/Zod con el front y con los schemas de tools del LLM |
| DB | PostgreSQL + pgvector (Cloud SQL) | SQLite: no escala a multiusuario en Cloud Run. Firestore: malo para stats/joins |
| ORM | Drizzle (migrations SQL explícitas) | Prisma: más pesado, peor con pgvector |
| Auth | Firebase Auth / Identity Platform (Google + email/password) | Auth propio: riesgo y trabajo sin valor diferencial |
| Hosting | **Proyecto GCP nuevo y dedicado**. Cloud Run (api + worker). Admin y web en Firebase Hosting. Dominios: `trainia.blasi.ar` (landing + web app), `api.trainia.blasi.ar`, `admin.trainia.blasi.ar` | GCE VM: más barato pero sin autoescalado y ops manual |
| Jobs | Cloud Scheduler + Cloud Tasks → endpoints del worker | Cron en proceso: no sobrevive a escalar a 0 |
| Push | Expo Notifications (APNs + FCM) + email como respaldo | — |
| LLM | Capa `llm/` multi-proveedor: **Nous Portal** (misma cuenta que Hermes) y **Gemini** (API de Gemini / Vertex AI). Proveedor, modelo y parámetros **por agente**, configurables en caliente desde el admin (tabla `llm_routes`), con fallback entre proveedores | Atarse a un proveedor |
| Modelos | Por rol: chico/rápido para router, extracción y resúmenes; grande para síntesis de plan. Defaults cargados por seed, editables en el admin | Un solo modelo grande: caro y lento |
| Pagos | **RevenueCat** unifica las suscripciones de App Store y Google Play (IAP) y las de web (Mercado Pago / Stripe). El backend recibe los webhooks y mantiene `subscriptions` | Integrar cada store a mano: mucho trabajo y casos borde (renovaciones, reembolsos, grace period) |
| Secretos | Secret Manager | .env en imagen |
| Obs. | Cloud Logging + tabla propia `llm_calls` (tokens, costo, latencia, versión de prompt) | Solo logs: no sirve para el panel admin |

---

## 3. Arquitectura

```
 App Expo (iOS/Android/web) ─HTTPS/SSE─►  api (Cloud Run)
 Admin web (React) ──────────HTTPS─────►    │
 RevenueCat / stores ──── webhooks ────►    │
                               ├─ auth (Firebase JWT)
                               ├─ domain/     perfiles, planes, rutinas, dietas, objetivos,
                               │              registros, grupos, retos, recordatorios
                               ├─ agents/     orquestador + 3 especialistas + sintetizador
                               ├─ context/    context builder + memoria + resúmenes
                               ├─ actions/    ChangeSet: validar → aplicar/confirmar → auditar
                               ├─ llm/        cliente multi-proveedor + registro de llamadas
                               └─ admin/      prompts versionados, stats, revisión
                                        │
                     Cloud SQL Postgres + pgvector
                                        ▲
 Cloud Scheduler / Tasks ──►  worker (Cloud Run): recordatorios, resúmenes nocturnos,
                              check-ins semanales, recálculo de rachas/puntos, embeddings
```

Streaming de respuestas por SSE. Una sola imagen Docker; api y worker se diferencian por env.

---

## 4. Sistema multi-agente

### 4.1 Flujo por turno

```
mensaje usuario
  → 1. Router (modelo chico, salida JSON)
        intent: log | pregunta | ajuste_plan | check-in | social | emocional | crisis
        especialistas: [coach?, nutri?, psico?]
        riesgo: none | low | high
  → 2. Context Builder arma un contexto por especialista (ver §5)
  → 3. Especialistas en paralelo → cada uno devuelve
        { aporte_texto, acciones_propuestas[], flags[] }
  → 4. Sintetizador ("Head coach", la voz única ante el usuario)
        fusiona, resuelve conflictos, redacta la respuesta final (streaming)
  → 5. Action Engine valida y aplica/propone el ChangeSet
  → 6. Post-proceso async: actualizar resumen de sesión, extraer memorias, embeddings
```

Optimización de costo: la mayoría de los turnos (registrar un entrenamiento, una duda
puntual) consulta 0–1 especialistas. Los 3 se consultan siempre en:
- creación de plan inicial
- revisión semanal / cambio de enfoque
- cuando el router detecta un tema transversal (ej. "no rindo, duermo mal y como poco")

### 4.2 Consejo para creación/ajuste de plan

1. Cada especialista recibe la ficha + objetivo + restricciones y devuelve una propuesta
   estructurada (JSON validado con Zod): bloque de entrenamiento / plan nutricional /
   estrategia de hábitos y motivación.
2. Sintetizador detecta conflictos (ej. déficit calórico agresivo vs. volumen alto de
   entrenamiento) y los resuelve con reglas de precedencia:
   seguridad médica > salud mental > objetivo del usuario > optimización.
3. Se genera un `PlanDraft` que el usuario ve como tarjeta ("Plan de 8 semanas: fuerza
   + recomposición") y acepta, pide cambios, o rechaza.
4. Al aceptar → se versiona como `Plan vN` (los planes nunca se sobreescriben).

### 4.3 Personas

El usuario ve una sola conversación, pero cada aporte puede atribuirse ("Desde nutrición:
..."). Opción futura: chat directo con un especialista específico.

---

## 5. Gestión de contexto

Objetivo: prompt acotado (p.ej. ≤ 6–8k tokens de contexto) sin perder información relevante.

Capas, con presupuesto de tokens por capa (configurable desde admin):

| Capa | Contenido | Fuente | Presupuesto aprox. |
|---|---|---|---|
| System | Prompt del agente (versión publicada) + reglas de seguridad | `agent_prompts` | 1–1.5k |
| Perfil | Ficha compacta: edad, sexo, medidas, lesiones, restricciones, nivel, disponibilidad | `profiles` → serializador determinístico | 300–500 |
| Estado actual | Objetivo activo, plan vigente (resumen), semana actual, adherencia 7/28 días | query + plantilla | 400–800 |
| Métricas | Ventana relevante al especialista (nutri: peso/ingesta; coach: cargas/RPE; psico: ánimo/sueño/adherencia) | `logs` agregados | 300–600 |
| Memoria episódica | Top-k hechos recuperados por similitud + recencia ("le duele la rodilla derecha al correr") | `memories` (pgvector) | 300–600 |
| Resumen de conversación | Resumen rodante de la sesión actual + resumen del hilo anterior | `conversation_summaries` | 300–500 |
| Últimos turnos | Últimos N mensajes textuales (N adaptativo) | `messages` | 1–2k |

Mecánicas:
- Especialistas reciben slices distintos del mismo estado (principio de mínimo contexto).
- Resumen rodante: cuando los turnos crudos superan el presupuesto, los más viejos se
  comprimen en el resumen (modelo chico, async).
- Extracción de memorias post-turno: hechos durables (lesiones, preferencias, eventos de
  vida, gustos alimentarios) → `memories` con tipo, importancia y vigencia. Deduplicación
  y reemplazo ("ya no le duele la rodilla" invalida el recuerdo anterior).
- El perfil y el estado NO se infieren del historial: se leen de la DB. Eso reduce
  alucinación y tamaño.
- Se loguea qué capas y cuántos tokens usó cada turno → visible en admin para calibrar.

---

## 6. De la conversación a las entidades (Action Engine)

Los especialistas/sintetizador emiten acciones vía tool calling con schemas Zod:

```
log_workout, log_meal, log_metric (peso, medidas, sueño, ánimo, RPE),
update_profile_field, set_goal, propose_plan_change, create_reminder,
complete_task, flag_risk, suggest_group_challenge
```

Pipeline:
1. Validación de schema + reglas de dominio (rangos plausibles, permisos, coherencia).
2. Clasificación por impacto:
   - Bajo (registros, recordatorios): se aplica directo, con "deshacer" en la tarjeta.
   - Alto (cambiar plan, dieta, objetivo, datos de salud): queda `pending` y se muestra
     tarjeta de confirmación.
3. Aplicación transaccional + `audit_log` (quién, qué, antes/después, message_id,
   prompt_version). Permite reconstruir por qué cambió algo y revertir.

---

## 7. Modelo de datos (inicial)

```
users(id, firebase_uid, email, role[user|admin], locale, created_at)
profiles(user_id, birthdate, sex, height_cm, activity_level, experience_level,
         injuries jsonb, conditions jsonb, restrictions jsonb, preferences jsonb,
         availability jsonb, equipment jsonb, parq_result, updated_at)
goals(id, user_id, type, target jsonb, deadline, status, focus[fuerza|hipertrofia|
      resistencia|pérdida_grasa|salud|deporte_especifico], created_at)
plans(id, user_id, goal_id, version, status[draft|active|archived], starts_on,
      weeks, summary, rationale jsonb{coach,nutri,psico}, created_by_message_id)
plan_workouts(id, plan_id, week, day, title, blocks jsonb)       -- ejercicios, series, reps, RPE
nutrition_plans(id, plan_id, kcal, macros jsonb, guidelines jsonb, meal_templates jsonb)
habit_targets(id, plan_id, habit, frequency, rationale)            -- aporte psico
workout_logs(id, user_id, plan_workout_id?, performed_at, data jsonb, rpe, notes)
meal_logs(id, user_id, eaten_at, description, est_kcal, est_macros jsonb, photo_url?)
metrics(id, user_id, type[peso|cintura|sueño|ánimo|estrés|energía|fc_reposo], value, at)
reminders(id, user_id, kind, schedule(cron/rrule), channel, payload, active)
conversations(id, user_id, started_at, last_at, status)
messages(id, conversation_id, role, agent?, content, cards jsonb, tokens, created_at)
conversation_summaries(conversation_id, upto_message_id, summary, tokens)
memories(id, user_id, kind, content, importance, valid_from, valid_to,
         source_message_id, embedding vector)
actions(id, user_id, message_id, type, payload, impact, status[applied|pending|
        rejected|reverted], applied_at)
audit_log(id, entity, entity_id, before jsonb, after jsonb, action_id, actor)
groups(id, name, kind[familia|amigos|afinidad|pública], owner_id, privacy, invite_code)
group_members(group_id, user_id, role[owner|admin|member], share_settings jsonb)
challenges(id, group_id?, title, metric, rules jsonb, starts_on, ends_on)
challenge_entries(challenge_id, user_id, progress, updated_at)
achievements(id, code, name, criteria jsonb) / user_achievements(user_id, achievement_id, at)
points_ledger(id, user_id, reason, points, ref, at)
feed_events(id, group_id, user_id, type, payload, at)             -- solo lo que el usuario comparte
agent_prompts(id, agent, version, content, status[draft|published|archived],
              author, notes, created_at)
llm_providers(id, name[nous|gemini], base_url, secret_ref, enabled)   -- la key vive en Secret Manager
llm_routes(agent, provider_id, model, params jsonb, fallback_provider_id?, fallback_model?,
           updated_by, updated_at)                                   -- editable desde el admin
plans_catalog(id, code, name, price, currency, period, features jsonb, store_product_ids jsonb)
subscriptions(user_id, status[trial|active|grace|expired|canceled], plan_code, source
              [app_store|play_store|web], trial_ends_at, current_period_end, rc_customer_id)
professionals(id, user_id?, kind[entrenador|nutricionista|psicologo|deportologo], name,
              credentials jsonb, license_verified, bio, specialties[], modality[presencial|online],
              location geography?, area jsonb, pricing jsonb, status[pending|approved|suspended])
venues(id, kind[gimnasio|box|club|estudio|pileta|pista], name, location geography,
       address, amenities[], disciplines[], price_range, hours jsonb, source, verified,
       partner bool)
referrals(id, user_id, target_type[professional|venue], target_id, reason, suggested_by
          [agent|user|search], message_id?, status[suggested|contacted|booked|dismissed], at)
reviews(id, user_id, target_type, target_id, rating, comment, at)
llm_calls(id, user_id, conversation_id, agent, model, prompt_version, tokens_in,
          tokens_out, cost_usd, latency_ms, context_breakdown jsonb, error?, provider)
feedback(id, message_id, user_id, rating[-1|1], reason, comment)
safety_flags(id, user_id, message_id, category, severity, status, reviewed_by)
```

---

## 8. Comunidad e incentivos

- Grupos: familia, amigos, afinidad (ej. "corredores de Palermo", "post-parto").
  Invitación por link/código; grupos públicos descubribles (fase 2).
- Privacidad granular por grupo: qué se comparte (entrenamientos sí, peso no, fotos no).
  Por defecto se comparte lo mínimo. Datos de salud nunca se comparten sin opt-in explícito.
- Incentivos:
  - Rachas (entrenamiento, registro de comidas, check-in)
  - Puntos por adherencia al plan propio (no por rendimiento absoluto → justo entre niveles)
  - Logros/insignias (primer mes, 10 entrenos, PR)
  - Retos de grupo (ej. "12 entrenos en 4 semanas", "2L de agua x 21 días"), que el agente
    puede proponer al grupo
  - Rankings opt-in por adherencia % dentro del grupo
  - Feed del grupo con reacciones/ánimo
  - Referidos: invitar suma puntos
- Rol del psicólogo: modera el tono competitivo (ej. no empujar a quien muestra señales de
  sobreentrenamiento o conducta alimentaria de riesgo).

---

## 9. Seguridad y cumplimiento

- Onboarding con PAR-Q+ (screening de aptitud física). Respuestas de riesgo → recomendar
  apto médico y limitar intensidad del plan hasta confirmar.
- Mayores de 18 en MVP.
- Categorías de alerta detectadas por router + especialistas: dolor agudo/lesión, síntomas
  cardíacos, TCA (trastornos de conducta alimentaria), ideación autolesiva, embarazo.
  Respuesta: protocolo fijo (no generado libremente), recursos de ayuda (líneas de AR),
  flag para revisión admin, bloqueo de acciones riesgosas (ej. no generar déficit calórico).
- Disclaimers: no reemplaza consulta médica/nutricional/psicológica.
- Datos de salud = datos sensibles (Ley 25.326 AR / GDPR si hay usuarios UE):
  consentimiento explícito, exportar y borrar cuenta, cifrado en tránsito y reposo,
  no usar conversaciones para entrenar modelos sin opt-in.

---

## 10. Panel de administrador

- Prompts: editor por agente (router, coach, nutri, psico, sintetizador, extractor de
  memorias, resumidor), versionado draft → publish → rollback, diff entre versiones,
  notas de cambio. Playground: probar una versión draft contra un usuario sintético.
- Evals: set de "personas de prueba" (ej. principiante con sobrepeso, maratonista lesionado,
  señal de TCA) con criterios esperados. Correr evals antes de publicar un prompt.
  Scoring con LLM-as-judge + reglas duras (seguridad).
- Estadísticas de producto: registros, DAU/WAU/MAU, retención por cohorte, % onboarding
  completo, adherencia media, objetivos cumplidos, uso por grupo/retos.
- Estadísticas de IA: costo por usuario/día/agente, tokens por capa de contexto, latencia
  p50/p95, tasa de acciones aceptadas vs rechazadas por el usuario, feedback 👍/👎 por
  versión de prompt, flags de seguridad.
- Revisión: cola de conversaciones marcadas (flag, 👎, error) con el contexto exacto que
  vio el modelo.
- Config LLM: por agente (router, coach, nutri, psico, sintetizador, extractor, resumidor)
  elegir proveedor (Nous Portal / Gemini), modelo, temperatura, max tokens y fallback. Se
  aplica en caliente, sin deploy. Botón "probar" que hace una llamada real y muestra latencia
  y costo. Comparativa de costo/calidad por proveedor en las estadísticas.
- Config general: presupuestos de tokens por capa de contexto, límites de uso por usuario y por
  plan, duración del trial.
- Negocio: suscripciones (trials activos, conversión trial→pago, churn, MRR), catálogo de
  planes; moderación del marketplace (alta/verificación de profesionales, gimnasios,
  reseñas reportadas).

Nota: la combinación llm_calls + feedback + actions aceptadas/rechazadas + evals es un
dataset de preferencias natural para fine-tuning futuro (SFT/DPO) de modelos propios.

---

## 11. Monetización

- Modelo: **free trial + suscripción**.
- Trial: acceso completo por un período (propuesta: 14 días, configurable en el admin), sin
  tarjeta si la store lo permite.
- Suscripción mensual y anual (la anual con descuento). Los precios se definen en ARS para web
  y por tier en las stores.
- Canales: in-app purchase en iOS/Android (obligatorio por políticas de las stores para
  contenido digital) y web (Mercado Pago o Stripe). RevenueCat unifica el estado; el backend
  es la fuente de verdad de los permisos (`entitlements`) vía webhooks.
- Al vencer: modo de solo lectura (ve su historial y su plan) más un límite chico de mensajes
  al agente. No se borran datos.
- Futuro: comisión o suscripción de profesionales y gimnasios en el marketplace (§12).

---

## 12. Marketplace: profesionales y gimnasios

Objetivo: complementar a los agentes IA con humanos, y convertir la app en puerta de entrada
al ecosistema deportivo local.

- Sugerencias contextuales: los agentes pueden sugerir un profesional o un lugar cuando
  aporta valor. Ejemplos: el deportólogo IA detecta un dolor persistente → sugiere un
  kinesiólogo o deportólogo cercano; el objetivo es natación → piletas cerca; las señales
  emocionales son fuertes → psicólogo deportivo humano. Es una tool del Action Engine
  (`suggest_professional`, `suggest_venue`) y la respuesta muestra tarjetas.
  Las derivaciones por seguridad (§9) siempre priorizan profesionales de salud.
- Directorio y búsqueda: por tipo, especialidad, modalidad (presencial u online), zona y
  precio. Mapa de gimnasios, boxes, clubes y piletas.
- Profesionales: alta con verificación de matrícula (moderación manual en el admin), perfil,
  especialidades, modalidad y precios. Fase posterior: el usuario comparte su plan o su
  progreso con el profesional (con consentimiento explícito), y hay un panel del profesional
  para seguir a sus clientes.
- Gimnasios: carga inicial curada (Places API u OSM + curación manual) y luego alta por el
  propio gimnasio. Opción "partner" destacado.
- Reputación: reseñas de usuarios verificados (que tuvieron un referral).
- Transparencia: las sugerencias pagas o destacadas se marcan como tales. El ranking de
  sugerencias del agente se basa en relevancia, no en pago.
- Métricas en el admin: sugerencias → contactos → reservas, por tipo y zona.

---

## 13. Roadmap

Fase 0 — Fundaciones (1–2 semanas)
- Monorepo (pnpm workspaces): `apps/mobile` (Expo), `apps/admin` (React/Vite), `apps/api`
  (Fastify), `packages/shared` (tipos + Zod)
- Postgres + pgvector local en Docker, Drizzle, migraciones, CI (lint + typecheck + test)
- Firebase Auth (Google + email/password) en la api y en las apps
- Capa `llm/` multi-proveedor (Nous + Gemini) + `llm_routes` + tabla `llm_calls`
- Proyecto GCP dedicado (IaC), Cloud Run + Cloud SQL staging, dominios `*.trainia.blasi.ar`
- Cuentas de desarrollador de Apple y Google Play, EAS configurado (build interno)

Fase 1 — MVP individual en las stores (4–6 semanas)
- Registro, onboarding conversacional con PAR-Q+ (la ficha se completa conversando, con
  formulario de respaldo)
- Router + 3 especialistas + sintetizador, streaming
- Context builder v1 (perfil, estado, últimos turnos, resumen rodante)
- Action Engine: log_workout, log_meal, log_metric, set_goal, propose_plan_change
- Plan inicial por consejo + vista "Hoy" + vista "Evolución" (gráficos)
- Admin v1: prompts versionados, configuración LLM por agente y costo/uso básico
- Push (recordatorios básicos)
- Free trial + suscripción (RevenueCat + IAP)
- Deploy prod + publicación en Play Store y App Store (fichas, políticas de privacidad y
  salud, revisión de Apple)

Fase 2 — Retención y comunidad (3 semanas)
- Recordatorios avanzados (Scheduler/Tasks + push), check-in semanal proactivo
- Memoria episódica con pgvector
- Grupos, privacidad, feed, rachas, puntos, retos, logros
- Marketplace v1: directorio de gimnasios y profesionales + sugerencias de los agentes
- Admin v2: retención, adherencia, feedback, cola de revisión, flags

Fase 3 — Calidad y escala
- Evals automatizados en admin, A/B de prompts
- Marketplace v2: panel del profesional, compartir el plan con el profesional, partners
- Wearables (sin fecha; el modelo de `metrics` y el Action Engine ya los contemplan):
  Health Connect / Apple HealthKit / Strava / Garmin
- Fotos de comidas (visión) para estimar macros

---

## 14. Costos estimados (orden de magnitud, staging + prod chico)

- Cloud SQL db-f1-micro / db-g1-small: ~USD 10–30/mes (es el piso fijo principal)
- Cloud Run api + worker con min-instances=0: ~USD 0–10/mes con poco tráfico
- Firebase Auth, Scheduler, Tasks, Storage: ~gratis a esta escala
- LLM: el costo variable real. Con router chico y 0–1 especialistas por turno, estimar
  ~USD 0.2–1 por usuario activo/mes; medir desde el día 1 con `llm_calls`.
- Apple Developer Program: USD 99/año · Google Play Console: USD 25 (pago único)
- EAS (Expo): plan gratuito para empezar; plan pago si se necesitan más builds
- RevenueCat: gratis hasta USD 2.5k/mes de ingresos; después un % chico
- Las stores retienen 15% (programa de pequeños desarrolladores) a 30% de la suscripción

---

## 15. Decisiones de producto (2026-09-28)

| # | Tema | Decisión |
|---|---|---|
| 1 | Nombre / dominio | **Trainia** · trainia.blasi.ar |
| 2 | Idioma / mercado | Español rioplatense / Argentina |
| 3 | Proveedor LLM | Nous Portal (misma cuenta que Hermes) + Gemini, configurable por agente desde el admin |
| 4 | Plataforma | Llegar a las stores (Expo + EAS); también web |
| 5 | Monetización | Free trial + suscripción (§11) |
| 6 | Wearables | No por ahora; no se descartan (Fase 3) |
| 7 | Repo y flujo | github.com/mblasi/training · harness `scripts/backlog.py` (entrevista → spec → TDD) |
| 8 | Profesionales humanos | Sí: marketplace + sugerencias de gimnasios y profesionales (§12) |
| 9 | GCP | Proyecto nuevo y dedicado |

### Preguntas abiertas
- Duración del trial y precios (propuesta: 14 días; se define antes de la Fase 1)
- Titular de las cuentas de desarrollador de las stores (persona física o empresa); afecta la
  facturación y lo que se muestra en la ficha
- Proveedor de pagos web: Mercado Pago vs Stripe
- Fuente inicial de gimnasios: Google Places API (costo, términos) vs OSM + curación manual

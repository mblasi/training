---
issue: 13
status: implementing
test_command: python3 -m unittest discover -s tests -v
---

# Spec de implementación: Infra: proyecto GCP dedicado, Cloud Run + Cloud SQL staging y dominios trainia.blasi.ar

## Resumen

IaC con OpenTofu para trainia-staging: Artifact Registry, Cloud Run api, Cloud SQL PG16+pgvector, Secret Manager, Workload Identity Federation, Dockerfile multi-stage, docs/INFRA.md

## Decisiones de diseño

| ID | Topic | Opciones | Elegida | Rationale |
|----|-------|----------|---------|-----------|
| D1 | Estrategia de proyecto GCP | Solo trainia-staging ahora, Un proyecto con workspaces staging/prod, Dos proyectos desde el inicio | Solo trainia-staging ahora, estructura preparada para prod | Pragmático para Fase 0; el criterio de aceptación es staging; prod viene en Fase 1 |
| D2 | Herramienta de IaC y backend de estado | Terraform, OpenTofu, Pulumi | OpenTofu con estado en bucket GCS trainia-staging-tfstate (prerequisito manual) | Open-source, compatible con providers de Terraform/GCP, mismo HCL; bucket de estado se crea a mano antes del primer apply |
| D3 | Alcance del issue | IaC completo + deploy workflow + worker + Firebase IaC, IaC + Dockerfile + docs + WIF + dominio staging; deploy workflow en issue separado | IaC + Dockerfile + docs/INFRA.md + dominio api.staging.trainia.blasi.ar + WIF + tests Python; fuera: job deploy GitHub Actions (#54), worker, Firebase por IaC, dominios prod, migraciones como Cloud Run Job, admin en Hosting | Acota el issue a lo que se puede entregar sin un proyecto GCP activo; el deploy workflow va en #54 |
| D4 | Estructura de módulos Terraform | Un solo main.tf plano, Módulos reutilizables por recurso, Módulos por entorno | infra/modules/{cloudrun,cloudsql,wif,secrets} + infra/envs/staging | Módulos reutilizables permiten copiar infra/envs/staging a infra/envs/prod sin duplicar lógica |
| D5 | Dockerfile de la API | Dockerfile simple en raíz, Multi-stage en apps/api/Dockerfile con pnpm deploy, Imagen base Node sin build | Dockerfile multi-stage en apps/api/Dockerfile: build con node:24-alpine + pnpm deploy --filter @trainia/api; runtime con node:24-alpine slim | pnpm deploy genera un node_modules aislado solo con deps de producción; multi-stage reduce tamaño de imagen |
| D6 | Gestión de secretos | Secretos como vars de Terraform, Secret Manager montado como env var, Secretos en .env en la imagen | DATABASE_URL y API keys en Secret Manager montados como env var en Cloud Run; FIREBASE_PROJECT_ID y ADMIN_EMAILS como env vars planas; valores cargados con gcloud fuera de Terraform | Terraform gestiona la existencia del secret y los permisos IAM, no el valor; evita que los valores queden en el state file |
| D7 | Nombres y región de recursos GCP | us-central1, southamerica-east1, us-east1 | Región us-central1; project ID trainia-staging; Artifact Registry 'trainia'; Cloud SQL 'trainia-staging'; Cloud Run 'api' | us-central1 tiene el tier gratuito más amplio y la mayoría de los servicios GCP disponibles |
| D8 | Configuración de Cloud SQL | db-f1-micro sin HA, db-g1-small con HA, db-f1-micro con backups | Cloud SQL PG16 db-f1-micro sin HA ni backups automáticos; conexión por Unix socket de Cloud SQL Auth Proxy (sin IP pública); tier como variable del módulo; SIN flag cloudsql.enable_pgvector (pgvector se habilita con CREATE EXTENSION en migración SQL); INFRA.md anota que si la migración falla en f1-micro se sube a db-g1-small | Mínimo costo en staging; la restricción de núcleo dedicado aplica a google_ml_integration, no a pgvector; pgvector se habilita por migración |
| D9 | Tests automáticos | tofu validate en CI + tests Python, Solo tests Python de estructura, Sin tests automáticos | 15 tests Python de estructura en tests/test_issue_13.py: estructura de infra/, backend gcs, variables de módulos, main de staging usa los 4 módulos, secret database-url, Dockerfile existe/multistage/node:24/pnpm deploy, INFRA.md existe y documenta costos/rollback/Workload Identity; sin tofu validate en CI | tofu no está disponible en el runner de CI sin instalación extra; los tests de estructura cubren los invariantes verificables sin credenciales GCP |

## Archivos afectados

- **create** `infra/.opentofu-version`: Fija la versión de OpenTofu para tofuenv
- **create** `infra/envs/staging/main.tf`: Entry point del entorno staging: llama a los 4 módulos (cloudrun, cloudsql, wif, secrets)
- **create** `infra/envs/staging/variables.tf`: Variables del entorno staging (project, region, image_tag, etc.)
- **create** `infra/envs/staging/outputs.tf`: Outputs del entorno staging (cloud_run_url, db_connection_name, etc.)
- **create** `infra/envs/staging/backend.tf`: Backend GCS: bucket trainia-staging-tfstate, prefix envs/staging
- **create** `infra/envs/staging/terraform.tfvars.example`: Ejemplo de tfvars con project_id, region, image_tag sin valores secretos
- **create** `infra/modules/cloudrun/main.tf`: Módulo Cloud Run: google_cloud_run_v2_service 'api', IAM, domain mapping para api.staging.trainia.blasi.ar
- **create** `infra/modules/cloudrun/variables.tf`: Variables del módulo cloudrun (project, region, image, service_account_email, db_connection_name, secrets, env_vars)
- **create** `infra/modules/cloudrun/outputs.tf`: Outputs del módulo cloudrun (service_url, service_name)
- **create** `infra/modules/cloudsql/main.tf`: Módulo Cloud SQL: google_sql_database_instance PG16, google_sql_database, google_sql_user, IAM binding para service account
- **create** `infra/modules/cloudsql/variables.tf`: Variables del módulo cloudsql (project, region, instance_name, tier, db_name, db_user, service_account_email)
- **create** `infra/modules/cloudsql/outputs.tf`: Outputs del módulo cloudsql (connection_name, instance_name, db_name)
- **create** `infra/modules/wif/main.tf`: Módulo Workload Identity Federation: google_iam_workload_identity_pool, provider GitHub, binding al service account de deploy
- **create** `infra/modules/wif/variables.tf`: Variables del módulo wif (project, github_org, github_repo, service_account_email)
- **create** `infra/modules/wif/outputs.tf`: Outputs del módulo wif (workload_identity_provider, service_account)
- **create** `infra/modules/secrets/main.tf`: Módulo secrets: google_secret_manager_secret 'database-url', IAM accessor para service account de Cloud Run
- **create** `infra/modules/secrets/variables.tf`: Variables del módulo secrets (project, cloud_run_service_account_email, secret_ids)
- **create** `infra/modules/secrets/outputs.tf`: Outputs del módulo secrets (secret_names)
- **create** `apps/api/Dockerfile`: Dockerfile multi-stage: stage build con node:24-alpine + pnpm deploy --filter @trainia/api; stage runtime con node:24-alpine
- **create** `docs/INFRA.md`: Documentación de infraestructura: costos estimados, cómo operar, rollback, Workload Identity, prerequisitos manuales
- **create** `tests/test_issue_13.py`: 15 tests Python de estructura que verifican infra/, Dockerfile y docs/INFRA.md sin necesitar credenciales GCP

## Tareas

### T1: Estructura base de infra/ y módulos vacíos

Crear infra/.opentofu-version y los archivos main.tf/variables.tf/outputs.tf de los 4 módulos con contenido mínimo válido (al menos la declaración terraform{} y variable/output vacíos)

**Tests:**
- `tests/test_issue_13.py::test_opentofu_version_file_exists`: infra/.opentofu-version existe y contiene una versión semver (regex ^[0-9]+\.[0-9]+\.[0-9]+)
- `tests/test_issue_13.py::test_modules_directories_exist`: Existen los directorios infra/modules/cloudrun, infra/modules/cloudsql, infra/modules/wif, infra/modules/secrets
- `tests/test_issue_13.py::test_each_module_has_main_variables_outputs`: Cada uno de los 4 módulos tiene main.tf, variables.tf y outputs.tf
- `tests/test_issue_13.py::test_staging_env_directory_exists`: Existe el directorio infra/envs/staging con main.tf, variables.tf, outputs.tf, backend.tf y terraform.tfvars.example

**Archivos de implementación:**
- `infra/.opentofu-version`
- `infra/modules/cloudrun/main.tf`
- `infra/modules/cloudrun/variables.tf`
- `infra/modules/cloudrun/outputs.tf`
- `infra/modules/cloudsql/main.tf`
- `infra/modules/cloudsql/variables.tf`
- `infra/modules/cloudsql/outputs.tf`
- `infra/modules/wif/main.tf`
- `infra/modules/wif/variables.tf`
- `infra/modules/wif/outputs.tf`
- `infra/modules/secrets/main.tf`
- `infra/modules/secrets/variables.tf`
- `infra/modules/secrets/outputs.tf`
- `infra/envs/staging/main.tf`
- `infra/envs/staging/variables.tf`
- `infra/envs/staging/outputs.tf`
- `infra/envs/staging/backend.tf`
- `infra/envs/staging/terraform.tfvars.example`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T2: Backend GCS y variables del entorno staging

infra/envs/staging/backend.tf con backend gcs bucket trainia-staging-tfstate; variables.tf con project_id, region, image_tag, api_min_instances; terraform.tfvars.example con valores de ejemplo

**Tests:**
- `tests/test_issue_13.py::test_backend_tf_uses_gcs`: infra/envs/staging/backend.tf contiene 'gcs' y 'trainia-staging-tfstate'
- `tests/test_issue_13.py::test_backend_tf_has_prefix`: infra/envs/staging/backend.tf contiene 'prefix' y 'envs/staging'
- `tests/test_issue_13.py::test_staging_variables_tf_declares_project_and_region`: infra/envs/staging/variables.tf contiene las palabras 'project_id' y 'region' como declaraciones de variable

**Archivos de implementación:**
- `infra/envs/staging/backend.tf`
- `infra/envs/staging/variables.tf`
- `infra/envs/staging/terraform.tfvars.example`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T3: Módulo cloudsql: Cloud SQL PG16 db-f1-micro

infra/modules/cloudsql/main.tf con google_sql_database_instance (PG16, db-f1-micro, sin IP pública), google_sql_database, google_sql_user, IAM binding cloudsql.client para el service account de Cloud Run

**Tests:**
- `tests/test_issue_13.py::test_cloudsql_module_uses_postgres16`: infra/modules/cloudsql/main.tf contiene 'POSTGRES_16'
- `tests/test_issue_13.py::test_cloudsql_module_has_tier_variable`: infra/modules/cloudsql/variables.tf contiene variable 'tier' (permite sobrescribir db-f1-micro desde el entorno)

**Archivos de implementación:**
- `infra/modules/cloudsql/main.tf`
- `infra/modules/cloudsql/variables.tf`
- `infra/modules/cloudsql/outputs.tf`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T4: Módulo secrets: Secret Manager + IAM accessor

infra/modules/secrets/main.tf con google_secret_manager_secret 'database-url' y google_secret_manager_secret_iam_member para que el service account de Cloud Run pueda leer el secreto

**Tests:**
- `tests/test_issue_13.py::test_secrets_module_declares_database_url_secret`: infra/modules/secrets/main.tf contiene 'database-url'
- `tests/test_issue_13.py::test_secrets_module_grants_secret_accessor`: infra/modules/secrets/main.tf contiene 'secretmanager.secretAccessor' o 'roles/secretmanager.secretAccessor'

**Archivos de implementación:**
- `infra/modules/secrets/main.tf`
- `infra/modules/secrets/variables.tf`
- `infra/modules/secrets/outputs.tf`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T5: Módulo wif: Workload Identity Federation para GitHub Actions

infra/modules/wif/main.tf con google_iam_workload_identity_pool, google_iam_workload_identity_pool_provider (GitHub OIDC), google_service_account_iam_member para el repo de GitHub

**Tests:**
- `tests/test_issue_13.py::test_wif_module_has_workload_identity_pool`: infra/modules/wif/main.tf contiene 'google_iam_workload_identity_pool'
- `tests/test_issue_13.py::test_wif_module_references_github`: infra/modules/wif/main.tf contiene 'github' (provider OIDC de GitHub Actions)

**Archivos de implementación:**
- `infra/modules/wif/main.tf`
- `infra/modules/wif/variables.tf`
- `infra/modules/wif/outputs.tf`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T6: Módulo cloudrun: Cloud Run v2 + domain mapping

infra/modules/cloudrun/main.tf con google_cloud_run_v2_service 'api', secreto DATABASE_URL desde Secret Manager, env vars planas FIREBASE_PROJECT_ID/ADMIN_EMAILS, Cloud SQL socket, google_cloud_run_v2_service_iam_member para acceso público a /health, google_cloud_run_domain_mapping para api.staging.trainia.blasi.ar

**Tests:**
- `tests/test_issue_13.py::test_cloudrun_module_has_cloud_run_v2_service`: infra/modules/cloudrun/main.tf contiene 'google_cloud_run_v2_service'
- `tests/test_issue_13.py::test_cloudrun_module_has_domain_mapping`: infra/modules/cloudrun/main.tf contiene 'google_cloud_run_domain_mapping' o 'google_cloud_run_v2_service' con custom_audiences o mapped_url; alternativamente contiene 'api.staging.trainia.blasi.ar'

**Archivos de implementación:**
- `infra/modules/cloudrun/main.tf`
- `infra/modules/cloudrun/variables.tf`
- `infra/modules/cloudrun/outputs.tf`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T7: infra/envs/staging/main.tf: orquesta los 4 módulos

main.tf del entorno staging llama a los módulos cloudrun, cloudsql, wif y secrets con las variables de staging; provider google con project y region; required_providers con source hashicorp/google

**Tests:**
- `tests/test_issue_13.py::test_staging_main_calls_all_four_modules`: infra/envs/staging/main.tf contiene referencias a los 4 módulos: module 'cloudrun', 'cloudsql', 'wif', 'secrets' (o sus fuentes ../../../modules/...)
- `tests/test_issue_13.py::test_staging_main_has_google_provider`: infra/envs/staging/main.tf contiene 'hashicorp/google' en required_providers

**Archivos de implementación:**
- `infra/envs/staging/main.tf`
- `infra/envs/staging/outputs.tf`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [x] REFACTOR: código limpio

### T8: Dockerfile multi-stage para apps/api

apps/api/Dockerfile con stage build (node:24-alpine, copia monorepo, corepack enable, pnpm install --frozen-lockfile, pnpm deploy --filter @trainia/api --prod /app/deploy) y stage runtime (node:24-alpine, copia /app/deploy, CMD node dist/index.js o tsx src/index.ts)

**Tests:**
- `tests/test_issue_13.py::test_dockerfile_exists`: apps/api/Dockerfile existe
- `tests/test_issue_13.py::test_dockerfile_is_multistage`: apps/api/Dockerfile contiene al menos 2 instrucciones FROM
- `tests/test_issue_13.py::test_dockerfile_uses_node24`: apps/api/Dockerfile contiene 'node:24'
- `tests/test_issue_13.py::test_dockerfile_uses_pnpm_deploy`: apps/api/Dockerfile contiene 'pnpm deploy'

**Archivos de implementación:**
- `apps/api/Dockerfile`

**Progreso:**
- [x] RED: tests escritos y fallan
- [x] GREEN: tests pasan
- [ ] REFACTOR: código limpio

### T9: docs/INFRA.md: costos, operación, rollback y WIF

Crear docs/INFRA.md con secciones: Prerequisitos manuales (crear proyecto GCP, bucket tfstate, habilitar APIs, registros DNS), Costos estimados (Cloud SQL, Cloud Run, Artifact Registry), Cómo operar (tofu apply, cómo actualizar imagen), Rollback (cómo revertir a imagen anterior), Workload Identity Federation (cómo funciona, qué secretos cargar con gcloud)

**Tests:**
- `tests/test_issue_13.py::test_infra_md_exists`: docs/INFRA.md existe
- `tests/test_issue_13.py::test_infra_md_documents_costs`: docs/INFRA.md contiene 'USD' o 'costo' o 'Cloud SQL' en alguna sección de costos
- `tests/test_issue_13.py::test_infra_md_documents_rollback`: docs/INFRA.md contiene 'rollback' o 'revertir' (case-insensitive)
- `tests/test_issue_13.py::test_infra_md_documents_workload_identity`: docs/INFRA.md contiene 'Workload Identity' o 'workload_identity'

**Archivos de implementación:**
- `docs/INFRA.md`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio

## Fuera de alcance

- Job de deploy en GitHub Actions (va en issue #54)
- Worker de Cloud Run (se agrega en Fase 1)
- Firebase/Identity Platform gestionado por IaC
- Dominios de producción (api.trainia.blasi.ar, admin.trainia.blasi.ar, trainia.blasi.ar)
- Migraciones corridas como Cloud Run Job en el pipeline de deploy
- Panel admin en Firebase Hosting
- Configuración de Cloud SQL HA ni backups automáticos
- tofu validate en CI (requiere instalación de OpenTofu en el runner)
- Creación del proyecto GCP, bucket tfstate, habilitación de APIs y registros DNS (prerequisitos manuales del owner)

## Riesgos

- APIs de GCP a habilitar manualmente antes del primer tofu apply: run.googleapis.com, sqladmin.googleapis.com, artifactregistry.googleapis.com, secretmanager.googleapis.com, iamcredentials.googleapis.com, iam.googleapis.com
- Bucket de tfstate (trainia-staging-tfstate) debe existir antes del tofu init; si no existe, tofu init falla
- Los valores de los secretos (DATABASE_URL, claves LLM) se cargan con gcloud secrets versions add fuera de Terraform; sin este paso la API no arranca aunque el apply sea exitoso
- El registro DNS para api.staging.trainia.blasi.ar es manual; el proveedor de DNS debe confirmarse antes del apply (el issue menciona GoDaddy para blasi.ar pero no está confirmado para el subdominio trainia)
- google_cloud_run_domain_mapping puede requerir verificación de dominio en Google Search Console antes de que Terraform pueda crearlo
- db-f1-micro tiene 0.6 GB RAM compartida; si las migraciones de Drizzle + pgvector extension fallan por memoria, escalar a db-g1-small (documentado en INFRA.md)
- Workload Identity Federation requiere que el repo de GitHub esté en la organización/cuenta correcta; el atributo del provider debe coincidir exactamente con el repo (mblasi/training)

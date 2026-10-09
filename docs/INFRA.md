# Infraestructura de Trainia

## Prerequisitos manuales

Antes de ejecutar `tofu apply` por primera vez:

1. **Crear proyecto GCP**: `trainia-staging` en GCP Console
2. **Crear bucket de estado**: `trainia-staging-tfstate` en us-central1
3. **Habilitar APIs**: Cloud Run, Cloud SQL, Secret Manager, Artifact Registry, IAM, Resource Manager
4. **Registros DNS**: configurar registro A para `api.staging.trainia.blasi.ar` apuntando a Cloud Run IP (obtenido del output después del primer apply)

## Costos estimados

Costos mensuales aproximados para staging (USD):

- **Cloud SQL** (db-f1-micro, PG16): ~$7-9/mes (instancia compartida 0.6GB RAM)
- **Cloud Run** (API): $0 bajo tier gratuito (2M requests/mes, 360k GB-seg), ~$0.10-1/mes en uso moderado
- **Artifact Registry**: $0.10/GB/mes almacenamiento (primeros 0.5GB gratis)
- **Secret Manager**: $0.06/secreto activo/mes (primeros 6 secretos gratis)

Total estimado: ~$7-10/mes en staging.

**Nota**: si las migraciones de DB fallan por falta de recursos en db-f1-micro, subir temporalmente a db-g1-small (~$25/mes) durante la migración y luego revertir.

## Cómo operar

### Aplicar cambios de infraestructura

```bash
cd infra/envs/staging
tofu init  # solo la primera vez o al cambiar backend
tofu plan
tofu apply
```

### Actualizar imagen de la API

1. Buildear y pushear imagen a Artifact Registry:
```bash
docker build -t us-central1-docker.pkg.dev/trainia-staging/trainia/api:latest apps/api/
docker push us-central1-docker.pkg.dev/trainia-staging/trainia/api:latest
```

2. Cloud Run detecta automáticamente la nueva imagen si está configurado con `:latest`, o:
```bash
gcloud run services update api \
  --region us-central1 \
  --image us-central1-docker.pkg.dev/trainia-staging/trainia/api:NEW_TAG
```

### Cargar secretos

```bash
# DATABASE_URL
echo -n "postgresql://user:pass@/cloudsql/trainia-staging:us-central1:trainia-staging/trainia?host=/cloudsql/trainia-staging:us-central1:trainia-staging" | \
  gcloud secrets versions add database-url --data-file=-

# Otros secretos
echo -n "api-key-value" | gcloud secrets versions add some-api-key --data-file=-
```

## Rollback

### Revertir a imagen anterior de Cloud Run

1. Listar revisiones:
```bash
gcloud run revisions list --service api --region us-central1
```

2. Revertir a revisión específica:
```bash
gcloud run services update-traffic api \
  --region us-central1 \
  --to-revisions REVISION_NAME=100
```

### Revertir cambios de Terraform

1. Revertir el commit en git:
```bash
git revert <commit-hash>
```

2. Aplicar estado anterior:
```bash
cd infra/envs/staging
tofu apply
```

## Workload Identity Federation

Workload Identity Federation (WIF) permite que GitHub Actions se autentique con GCP sin usar service account keys estáticas.

### Cómo funciona

1. GitHub Actions obtiene un token OIDC de GitHub que incluye el repo y el workflow
2. GCP valida el token contra el Workload Identity Pool configurado
3. Si el subject del token coincide con el attribute mapping (ej: `repo:mblasi/training:ref:refs/heads/main`), GCP emite credenciales temporales del service account
4. El workflow puede usar esas credenciales para deployar a Cloud Run, pushear a Artifact Registry, etc.

### Recursos creados

- **Workload Identity Pool**: `github-actions-pool` en el proyecto
- **Workload Identity Provider**: configurado con `https://token.actions.githubusercontent.com` como OIDC issuer
- **Service Account**: `github-actions-deployer@trainia-staging.iam.gserviceaccount.com` con roles:
  - `roles/run.admin`: deploy de servicios Cloud Run
  - `roles/artifactregistry.writer`: push de imágenes
  - `roles/iam.serviceAccountUser`: actuar como service account de Cloud Run

### Cargar secretos necesarios

Los secretos de GCP se cargan con `gcloud` fuera de Terraform (Terraform solo gestiona la existencia del recurso Secret Manager y los permisos IAM):

```bash
# DATABASE_URL (generado después de crear Cloud SQL)
echo -n "postgresql://..." | gcloud secrets versions add database-url --data-file=-

# Otros secretos API (ejemplo)
echo -n "sk-..." | gcloud secrets versions add openai-api-key --data-file=-
```

### Uso en GitHub Actions

```yaml
- uses: google-github-actions/auth@v2
  with:
    workload_identity_provider: 'projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github-actions-pool/providers/github-oidc'
    service_account: 'github-actions-deployer@trainia-staging.iam.gserviceaccount.com'
```

El `PROJECT_NUMBER` y el nombre completo del provider se obtienen del output de Terraform.

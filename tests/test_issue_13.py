#!/usr/bin/env python3
"""
Tests for issue #13: IaC con OpenTofu para trainia-staging

Verifica la estructura de infra/, módulos de Terraform, Dockerfile multi-stage,
y documentación de infraestructura.
"""
import re
import unittest
from pathlib import Path


class TestIssue13Task1(unittest.TestCase):
    """Tests para T1: Estructura base de infra/ y módulos vacíos."""

    @classmethod
    def setUpClass(cls):
        """Setup común: obtener la raíz del repo."""
        cls.repo_root = Path(__file__).parent.parent
        cls.infra_root = cls.repo_root / "infra"
        cls.opentofu_version_file = cls.infra_root / ".opentofu-version"
        cls.modules_dir = cls.infra_root / "modules"
        cls.envs_dir = cls.infra_root / "envs"

    def test_opentofu_version_file_exists(self):
        r"""infra/.opentofu-version existe y contiene una versión semver (regex ^[0-9]+\.[0-9]+\.[0-9]+)."""
        self.assertTrue(
            self.opentofu_version_file.exists(),
            "infra/.opentofu-version debe existir"
        )

        with open(self.opentofu_version_file, 'r') as f:
            version_content = f.read().strip()

        semver_pattern = re.compile(r'^[0-9]+\.[0-9]+\.[0-9]+')
        self.assertIsNotNone(
            semver_pattern.match(version_content),
            f"infra/.opentofu-version debe contener una versión semver, encontrado: {version_content}"
        )

    def test_modules_directories_exist(self):
        """Existen los directorios infra/modules/cloudrun, infra/modules/cloudsql, infra/modules/wif, infra/modules/secrets."""
        module_names = ['cloudrun', 'cloudsql', 'wif', 'secrets']

        for module_name in module_names:
            module_dir = self.modules_dir / module_name
            self.assertTrue(
                module_dir.exists() and module_dir.is_dir(),
                f"infra/modules/{module_name} debe existir y ser un directorio"
            )

    def test_each_module_has_main_variables_outputs(self):
        """Cada uno de los 4 módulos tiene main.tf, variables.tf y outputs.tf."""
        module_names = ['cloudrun', 'cloudsql', 'wif', 'secrets']
        required_files = ['main.tf', 'variables.tf', 'outputs.tf']

        for module_name in module_names:
            module_dir = self.modules_dir / module_name
            for file_name in required_files:
                file_path = module_dir / file_name
                self.assertTrue(
                    file_path.exists() and file_path.is_file(),
                    f"infra/modules/{module_name}/{file_name} debe existir y ser un archivo"
                )

    def test_staging_env_directory_exists(self):
        """Existe el directorio infra/envs/staging con main.tf, variables.tf, outputs.tf, backend.tf y terraform.tfvars.example."""
        staging_dir = self.envs_dir / "staging"
        self.assertTrue(
            staging_dir.exists() and staging_dir.is_dir(),
            "infra/envs/staging debe existir y ser un directorio"
        )

        required_files = ['main.tf', 'variables.tf', 'outputs.tf', 'backend.tf', 'terraform.tfvars.example']
        for file_name in required_files:
            file_path = staging_dir / file_name
            self.assertTrue(
                file_path.exists() and file_path.is_file(),
                f"infra/envs/staging/{file_name} debe existir y ser un archivo"
            )


class TestIssue13Task2(unittest.TestCase):
    """Tests para T2: Backend GCS y variables del entorno staging."""

    @classmethod
    def setUpClass(cls):
        """Setup común: obtener la raíz del repo."""
        cls.repo_root = Path(__file__).parent.parent
        cls.infra_root = cls.repo_root / "infra"
        cls.staging_dir = cls.infra_root / "envs" / "staging"
        cls.backend_tf = cls.staging_dir / "backend.tf"
        cls.variables_tf = cls.staging_dir / "variables.tf"

    def test_backend_tf_uses_gcs(self):
        """infra/envs/staging/backend.tf contiene 'gcs' y 'trainia-staging-tfstate'."""
        self.assertTrue(
            self.backend_tf.exists(),
            "infra/envs/staging/backend.tf debe existir"
        )

        with open(self.backend_tf, 'r') as f:
            backend_content = f.read()

        self.assertIn(
            'gcs',
            backend_content,
            "backend.tf debe contener 'gcs' como tipo de backend"
        )
        self.assertIn(
            'trainia-staging-tfstate',
            backend_content,
            "backend.tf debe contener 'trainia-staging-tfstate' como nombre del bucket"
        )

    def test_backend_tf_has_prefix(self):
        """infra/envs/staging/backend.tf contiene 'prefix' y 'envs/staging'."""
        self.assertTrue(
            self.backend_tf.exists(),
            "infra/envs/staging/backend.tf debe existir"
        )

        with open(self.backend_tf, 'r') as f:
            backend_content = f.read()

        self.assertIn(
            'prefix',
            backend_content,
            "backend.tf debe contener 'prefix'"
        )
        self.assertIn(
            'envs/staging',
            backend_content,
            "backend.tf debe contener 'envs/staging' como valor del prefix"
        )

    def test_staging_variables_tf_declares_project_and_region(self):
        """infra/envs/staging/variables.tf contiene las palabras 'project_id' y 'region' como declaraciones de variable."""
        self.assertTrue(
            self.variables_tf.exists(),
            "infra/envs/staging/variables.tf debe existir"
        )

        with open(self.variables_tf, 'r') as f:
            variables_content = f.read()

        self.assertIn(
            'project_id',
            variables_content,
            "variables.tf debe contener 'project_id' como declaración de variable"
        )
        self.assertIn(
            'region',
            variables_content,
            "variables.tf debe contener 'region' como declaración de variable"
        )


class TestIssue13Task3(unittest.TestCase):
    """Tests para T3: Módulo cloudsql: Cloud SQL PG16 db-f1-micro."""

    @classmethod
    def setUpClass(cls):
        """Setup común: obtener la raíz del repo."""
        cls.repo_root = Path(__file__).parent.parent
        cls.infra_root = cls.repo_root / "infra"
        cls.cloudsql_module_dir = cls.infra_root / "modules" / "cloudsql"
        cls.cloudsql_main_tf = cls.cloudsql_module_dir / "main.tf"
        cls.cloudsql_variables_tf = cls.cloudsql_module_dir / "variables.tf"

    def test_cloudsql_module_uses_postgres16(self):
        """infra/modules/cloudsql/main.tf contiene 'POSTGRES_16'."""
        self.assertTrue(
            self.cloudsql_main_tf.exists(),
            "infra/modules/cloudsql/main.tf debe existir"
        )

        with open(self.cloudsql_main_tf, 'r') as f:
            main_content = f.read()

        self.assertIn(
            'POSTGRES_16',
            main_content,
            "infra/modules/cloudsql/main.tf debe contener 'POSTGRES_16' como versión de la base de datos"
        )

    def test_cloudsql_module_has_tier_variable(self):
        """infra/modules/cloudsql/variables.tf contiene variable 'tier' (permite sobrescribir db-f1-micro desde el entorno)."""
        self.assertTrue(
            self.cloudsql_variables_tf.exists(),
            "infra/modules/cloudsql/variables.tf debe existir"
        )

        with open(self.cloudsql_variables_tf, 'r') as f:
            variables_content = f.read()

        self.assertIn(
            'tier',
            variables_content,
            "infra/modules/cloudsql/variables.tf debe contener variable 'tier'"
        )


class TestIssue13Task4(unittest.TestCase):
    """Tests para T4: Módulo secrets: Secret Manager + IAM accessor."""

    @classmethod
    def setUpClass(cls):
        """Setup común: obtener la raíz del repo."""
        cls.repo_root = Path(__file__).parent.parent
        cls.infra_root = cls.repo_root / "infra"
        cls.secrets_module_dir = cls.infra_root / "modules" / "secrets"
        cls.secrets_main_tf = cls.secrets_module_dir / "main.tf"

    def test_secrets_module_declares_database_url_secret(self):
        """infra/modules/secrets/main.tf contiene 'database-url'."""
        self.assertTrue(
            self.secrets_main_tf.exists(),
            "infra/modules/secrets/main.tf debe existir"
        )

        with open(self.secrets_main_tf, 'r') as f:
            main_content = f.read()

        self.assertIn(
            'database-url',
            main_content,
            "infra/modules/secrets/main.tf debe contener 'database-url' como nombre del secreto"
        )

    def test_secrets_module_grants_secret_accessor(self):
        """infra/modules/secrets/main.tf contiene 'secretmanager.secretAccessor' o 'roles/secretmanager.secretAccessor'."""
        self.assertTrue(
            self.secrets_main_tf.exists(),
            "infra/modules/secrets/main.tf debe existir"
        )

        with open(self.secrets_main_tf, 'r') as f:
            main_content = f.read()

        has_secret_accessor = (
            'secretmanager.secretAccessor' in main_content or
            'roles/secretmanager.secretAccessor' in main_content
        )

        self.assertTrue(
            has_secret_accessor,
            "infra/modules/secrets/main.tf debe contener 'secretmanager.secretAccessor' o 'roles/secretmanager.secretAccessor' como rol IAM"
        )


class TestIssue13Task5(unittest.TestCase):
    """Tests para T5: Módulo wif: Workload Identity Federation para GitHub Actions."""

    @classmethod
    def setUpClass(cls):
        """Setup común: obtener la raíz del repo."""
        cls.repo_root = Path(__file__).parent.parent
        cls.infra_root = cls.repo_root / "infra"
        cls.wif_module_dir = cls.infra_root / "modules" / "wif"
        cls.wif_main_tf = cls.wif_module_dir / "main.tf"

    def test_wif_module_has_workload_identity_pool(self):
        """infra/modules/wif/main.tf contiene 'google_iam_workload_identity_pool'."""
        self.assertTrue(
            self.wif_main_tf.exists(),
            "infra/modules/wif/main.tf debe existir"
        )

        with open(self.wif_main_tf, 'r') as f:
            main_content = f.read()

        self.assertIn(
            'google_iam_workload_identity_pool',
            main_content,
            "infra/modules/wif/main.tf debe contener 'google_iam_workload_identity_pool' como recurso"
        )

    def test_wif_module_references_github(self):
        """infra/modules/wif/main.tf contiene 'github' (provider OIDC de GitHub Actions)."""
        self.assertTrue(
            self.wif_main_tf.exists(),
            "infra/modules/wif/main.tf debe existir"
        )

        with open(self.wif_main_tf, 'r') as f:
            main_content = f.read()

        self.assertIn(
            'github',
            main_content,
            "infra/modules/wif/main.tf debe contener 'github' (provider OIDC de GitHub Actions)"
        )


class TestIssue13Task6(unittest.TestCase):
    """Tests para T6: Módulo cloudrun: Cloud Run v2 + domain mapping."""

    @classmethod
    def setUpClass(cls):
        """Setup común: obtener la raíz del repo."""
        cls.repo_root = Path(__file__).parent.parent
        cls.infra_root = cls.repo_root / "infra"
        cls.cloudrun_module_dir = cls.infra_root / "modules" / "cloudrun"
        cls.cloudrun_main_tf = cls.cloudrun_module_dir / "main.tf"

    def test_cloudrun_module_has_cloud_run_v2_service(self):
        """infra/modules/cloudrun/main.tf contiene 'google_cloud_run_v2_service'."""
        self.assertTrue(
            self.cloudrun_main_tf.exists(),
            "infra/modules/cloudrun/main.tf debe existir"
        )

        with open(self.cloudrun_main_tf, 'r') as f:
            main_content = f.read()

        self.assertIn(
            'google_cloud_run_v2_service',
            main_content,
            "infra/modules/cloudrun/main.tf debe contener 'google_cloud_run_v2_service' como recurso"
        )

    def test_cloudrun_module_has_domain_mapping(self):
        """infra/modules/cloudrun/main.tf contiene 'google_cloud_run_domain_mapping' o 'google_cloud_run_v2_service' con custom_audiences o mapped_url; alternativamente contiene 'api.staging.trainia.blasi.ar'."""
        self.assertTrue(
            self.cloudrun_main_tf.exists(),
            "infra/modules/cloudrun/main.tf debe existir"
        )

        with open(self.cloudrun_main_tf, 'r') as f:
            main_content = f.read()

        has_domain_mapping = (
            'google_cloud_run_domain_mapping' in main_content or
            'custom_audiences' in main_content or
            'mapped_url' in main_content or
            'api.staging.trainia.blasi.ar' in main_content
        )

        self.assertTrue(
            has_domain_mapping,
            "infra/modules/cloudrun/main.tf debe contener 'google_cloud_run_domain_mapping', 'custom_audiences', 'mapped_url', o 'api.staging.trainia.blasi.ar' para domain mapping"
        )


class TestIssue13Task7(unittest.TestCase):
    """Tests para T7: infra/envs/staging/main.tf: orquesta los 4 módulos."""

    @classmethod
    def setUpClass(cls):
        """Setup común: obtener la raíz del repo."""
        cls.repo_root = Path(__file__).parent.parent
        cls.infra_root = cls.repo_root / "infra"
        cls.staging_dir = cls.infra_root / "envs" / "staging"
        cls.staging_main_tf = cls.staging_dir / "main.tf"

    def test_staging_main_calls_all_four_modules(self):
        """infra/envs/staging/main.tf contiene referencias a los 4 módulos: module 'cloudrun', 'cloudsql', 'wif', 'secrets' (o sus fuentes ../../../modules/...)."""
        self.assertTrue(
            self.staging_main_tf.exists(),
            "infra/envs/staging/main.tf debe existir"
        )

        with open(self.staging_main_tf, 'r') as f:
            main_content = f.read()

        module_names = ['cloudrun', 'cloudsql', 'wif', 'secrets']
        for module_name in module_names:
            has_module = (
                f'module "{module_name}"' in main_content or
                f"module '{module_name}'" in main_content or
                f'modules/{module_name}' in main_content
            )
            self.assertTrue(
                has_module,
                f"infra/envs/staging/main.tf debe contener referencia al módulo '{module_name}'"
            )

    def test_staging_main_has_google_provider(self):
        """infra/envs/staging/main.tf contiene 'hashicorp/google' en required_providers."""
        self.assertTrue(
            self.staging_main_tf.exists(),
            "infra/envs/staging/main.tf debe existir"
        )

        with open(self.staging_main_tf, 'r') as f:
            main_content = f.read()

        self.assertIn(
            'hashicorp/google',
            main_content,
            "infra/envs/staging/main.tf debe contener 'hashicorp/google' en required_providers"
        )


class TestIssue13Task8(unittest.TestCase):
    """Tests para T8: Dockerfile multi-stage para apps/api."""

    @classmethod
    def setUpClass(cls):
        """Setup común: obtener la raíz del repo."""
        cls.repo_root = Path(__file__).parent.parent
        cls.api_dockerfile = cls.repo_root / "apps" / "api" / "Dockerfile"

    def test_dockerfile_exists(self):
        """apps/api/Dockerfile existe."""
        self.assertTrue(
            self.api_dockerfile.exists(),
            "apps/api/Dockerfile debe existir"
        )

    def test_dockerfile_is_multistage(self):
        """apps/api/Dockerfile contiene al menos 2 instrucciones FROM."""
        self.assertTrue(
            self.api_dockerfile.exists(),
            "apps/api/Dockerfile debe existir"
        )

        with open(self.api_dockerfile, 'r') as f:
            dockerfile_content = f.read()

        from_count = len(re.findall(r'^\s*FROM\s+', dockerfile_content, re.MULTILINE | re.IGNORECASE))

        self.assertGreaterEqual(
            from_count,
            2,
            f"apps/api/Dockerfile debe contener al menos 2 instrucciones FROM (multistage), encontrado: {from_count}"
        )

    def test_dockerfile_uses_node24(self):
        """apps/api/Dockerfile contiene 'node:24'."""
        self.assertTrue(
            self.api_dockerfile.exists(),
            "apps/api/Dockerfile debe existir"
        )

        with open(self.api_dockerfile, 'r') as f:
            dockerfile_content = f.read()

        self.assertIn(
            'node:24',
            dockerfile_content,
            "apps/api/Dockerfile debe contener 'node:24' como imagen base"
        )

    def test_dockerfile_uses_pnpm_deploy(self):
        """apps/api/Dockerfile contiene 'pnpm deploy'."""
        self.assertTrue(
            self.api_dockerfile.exists(),
            "apps/api/Dockerfile debe existir"
        )

        with open(self.api_dockerfile, 'r') as f:
            dockerfile_content = f.read()

        self.assertIn(
            'pnpm deploy',
            dockerfile_content,
            "apps/api/Dockerfile debe contener 'pnpm deploy' para aislar dependencias de producción"
        )


if __name__ == '__main__':
    unittest.main()

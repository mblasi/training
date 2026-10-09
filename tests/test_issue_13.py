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


if __name__ == '__main__':
    unittest.main()

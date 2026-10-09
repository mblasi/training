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


if __name__ == '__main__':
    unittest.main()

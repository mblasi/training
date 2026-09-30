#!/usr/bin/env python3
"""
Tests for issue #10: Postgres 18 + pgvector + Drizzle en apps/api

Verifica que las dependencias de Drizzle y pg estén instaladas, que los scripts
de DB estén configurados, y que existan los archivos de configuración necesarios.
"""
import json
import unittest
from pathlib import Path


class TestIssue10Task2(unittest.TestCase):
    """Tests para T2: Agregar deps Drizzle+pg a apps/api + drizzle.config.ts + vitest configs."""

    def setUp(self):
        """Setup común: obtener la raíz del repo y el directorio de apps/api."""
        self.repo_root = Path(__file__).parent.parent
        self.api_dir = self.repo_root / "apps" / "api"

    def test_api_package_json_has_drizzle_and_pg_deps(self):
        """apps/api/package.json contiene drizzle-orm 0.45.3, drizzle-kit 0.31.11, pg 8.23.0, @types/pg 8.23.1."""
        pkg_file = self.api_dir / "package.json"
        self.assertTrue(
            pkg_file.exists(),
            "apps/api/package.json debe existir"
        )

        with open(pkg_file, 'r') as f:
            pkg = json.load(f)

        # Verificar dependencies
        dependencies = pkg.get('dependencies', {})
        dev_dependencies = pkg.get('devDependencies', {})

        # drizzle-orm y pg deben estar en dependencies
        self.assertIn(
            'drizzle-orm',
            dependencies,
            "drizzle-orm debe estar en dependencies"
        )
        self.assertEqual(
            dependencies['drizzle-orm'],
            '0.45.3',
            "drizzle-orm debe ser versión 0.45.3"
        )

        self.assertIn(
            'pg',
            dependencies,
            "pg debe estar en dependencies"
        )
        self.assertEqual(
            dependencies['pg'],
            '8.23.0',
            "pg debe ser versión 8.23.0"
        )

        # drizzle-kit y @types/pg deben estar en devDependencies
        self.assertIn(
            'drizzle-kit',
            dev_dependencies,
            "drizzle-kit debe estar en devDependencies"
        )
        self.assertEqual(
            dev_dependencies['drizzle-kit'],
            '0.31.11',
            "drizzle-kit debe ser versión 0.31.11"
        )

        self.assertIn(
            '@types/pg',
            dev_dependencies,
            "@types/pg debe estar en devDependencies"
        )
        self.assertEqual(
            dev_dependencies['@types/pg'],
            '8.23.1',
            "@types/pg debe ser versión 8.23.1"
        )

    def test_api_package_json_has_db_scripts(self):
        """scripts db:migrate, db:generate, db:seed, test:integration presentes en apps/api/package.json."""
        pkg_file = self.api_dir / "package.json"
        self.assertTrue(
            pkg_file.exists(),
            "apps/api/package.json debe existir"
        )

        with open(pkg_file, 'r') as f:
            pkg = json.load(f)

        self.assertIn('scripts', pkg, "package.json debe tener 'scripts'")
        scripts = pkg['scripts']

        required_scripts = ['db:migrate', 'db:generate', 'db:seed', 'test:integration']
        for script_name in required_scripts:
            self.assertIn(
                script_name,
                scripts,
                f"scripts debe incluir '{script_name}'"
            )

    def test_drizzle_config_exists(self):
        """apps/api/drizzle.config.ts existe."""
        drizzle_config = self.api_dir / "drizzle.config.ts"
        self.assertTrue(
            drizzle_config.exists(),
            "apps/api/drizzle.config.ts debe existir"
        )

    def test_drizzle_config_references_schema_and_migrations(self):
        """drizzle.config.ts contiene 'src/db/schema' y 'src/db/migrations'."""
        drizzle_config = self.api_dir / "drizzle.config.ts"
        self.assertTrue(
            drizzle_config.exists(),
            "apps/api/drizzle.config.ts debe existir para verificar su contenido"
        )

        content = drizzle_config.read_text()

        self.assertIn(
            'src/db/schema',
            content,
            "drizzle.config.ts debe contener 'src/db/schema'"
        )

        self.assertIn(
            'src/db/migrations',
            content,
            "drizzle.config.ts debe contener 'src/db/migrations'"
        )

    def test_vitest_integration_config_exists(self):
        """apps/api/vitest.integration.config.ts existe."""
        vitest_integration_config = self.api_dir / "vitest.integration.config.ts"
        self.assertTrue(
            vitest_integration_config.exists(),
            "apps/api/vitest.integration.config.ts debe existir"
        )


if __name__ == '__main__':
    unittest.main()

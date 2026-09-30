#!/usr/bin/env python3
"""
Tests for issue #10: Postgres 18 + pgvector + Drizzle en apps/api

Verifica que las dependencias de Drizzle y pg estén instaladas, que los scripts
de DB estén configurados, y que existan los archivos de configuración necesarios.
"""
import json
import re
import unittest
from pathlib import Path


def extract_yaml_block(content: str, block_key: str, indent_level: int = 0) -> str:
    """
    Extract a YAML block by key at a specific indentation level.
    Returns the block including its children.
    """
    lines = content.split('\n')
    block_lines = []
    in_block = False
    block_indent = None
    
    for line in lines:
        if not line.strip():
            if in_block:
                block_lines.append(line)
            continue
            
        current_indent = len(line) - len(line.lstrip())
        
        if not in_block:
            # Look for the block start
            if current_indent == indent_level and line.lstrip().startswith(f"{block_key}:"):
                in_block = True
                block_indent = current_indent
                block_lines.append(line)
        else:
            # Continue collecting lines at deeper indentation
            if current_indent > block_indent or line.strip().startswith('-'):
                block_lines.append(line)
            else:
                # End of block
                break
    
    return '\n'.join(block_lines)


class TestIssue10Task2(unittest.TestCase):
    """Tests para T2: Agregar deps Drizzle+pg a apps/api + drizzle.config.ts + vitest configs."""

    @classmethod
    def setUpClass(cls):
        """Setup común: obtener la raíz del repo y el directorio de apps/api."""
        cls.repo_root = Path(__file__).parent.parent
        cls.api_dir = cls.repo_root / "apps" / "api"
        cls.migrations_dir = cls.api_dir / "src" / "db" / "migrations"

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
        
        # Verify db:seed points to seed-cli.ts
        self.assertIn(
            'seed-cli.ts',
            scripts['db:seed'],
            "db:seed script debe ejecutar seed-cli.ts"
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


class TestIssue10Task9(unittest.TestCase):
    """Tests para T9: Migraciones SQL: 0000_enable_vector.sql + 0001_core.sql + meta/."""

    @classmethod
    def setUpClass(cls):
        """Setup común: obtener la raíz del repo y los directorios relevantes."""
        cls.repo_root = Path(__file__).parent.parent
        cls.api_dir = cls.repo_root / "apps" / "api"
        cls.migrations_dir = cls.api_dir / "src" / "db" / "migrations"

    def test_migration_0000_enable_vector_exists(self):
        """apps/api/src/db/migrations/0000_enable_vector.sql existe."""
        migration_file = self.migrations_dir / "0000_enable_vector.sql"
        self.assertTrue(
            migration_file.exists(),
            "apps/api/src/db/migrations/0000_enable_vector.sql debe existir"
        )

    def test_migration_0000_has_create_extension_vector(self):
        """0000_enable_vector.sql contiene 'CREATE EXTENSION' e 'vector'."""
        migration_file = self.migrations_dir / "0000_enable_vector.sql"
        self.assertTrue(
            migration_file.exists(),
            "apps/api/src/db/migrations/0000_enable_vector.sql debe existir para verificar su contenido"
        )

        content = migration_file.read_text()

        self.assertIn(
            'CREATE EXTENSION',
            content,
            "0000_enable_vector.sql debe contener 'CREATE EXTENSION'"
        )

        self.assertIn(
            'vector',
            content,
            "0000_enable_vector.sql debe contener 'vector'"
        )

    def test_migration_0001_core_exists(self):
        """apps/api/src/db/migrations/0001_core.sql existe."""
        migration_file = self.migrations_dir / "0001_core.sql"
        self.assertTrue(
            migration_file.exists(),
            "apps/api/src/db/migrations/0001_core.sql debe existir"
        )

    def test_migration_0001_has_all_tables(self):
        """0001_core.sql contiene CREATE TABLE para users, profiles, llm_providers, llm_routes, llm_calls, agent_prompts."""
        migration_file = self.migrations_dir / "0001_core.sql"
        self.assertTrue(
            migration_file.exists(),
            "apps/api/src/db/migrations/0001_core.sql debe existir para verificar su contenido"
        )

        content = migration_file.read_text()

        required_tables = [
            'users',
            'profiles',
            'llm_providers',
            'llm_routes',
            'llm_calls',
            'agent_prompts'
        ]

        for table_name in required_tables:
            self.assertIn(
                f'CREATE TABLE',
                content,
                f"0001_core.sql debe contener CREATE TABLE"
            )
            self.assertIn(
                table_name,
                content,
                f"0001_core.sql debe contener referencia a tabla '{table_name}'"
            )

    def test_migration_meta_journal_exists(self):
        """apps/api/src/db/migrations/meta/_journal.json existe."""
        journal_file = self.migrations_dir / "meta" / "_journal.json"
        self.assertTrue(
            journal_file.exists(),
            "apps/api/src/db/migrations/meta/_journal.json debe existir"
        )

    def test_migration_meta_journal_has_two_entries(self):
        """_journal.json parseado como JSON tiene entries con 2 elementos (0000 y 0001)."""
        journal_file = self.migrations_dir / "meta" / "_journal.json"
        self.assertTrue(
            journal_file.exists(),
            "apps/api/src/db/migrations/meta/_journal.json debe existir para verificar su contenido"
        )

        with open(journal_file, 'r') as f:
            journal_data = json.load(f)

        self.assertIn(
            'entries',
            journal_data,
            "_journal.json debe contener campo 'entries'"
        )

        entries = journal_data['entries']
        self.assertIsInstance(
            entries,
            list,
            "'entries' debe ser una lista"
        )

        self.assertEqual(
            len(entries),
            2,
            "_journal.json debe tener exactamente 2 entries (0000 y 0001)"
        )


class TestIssue10Task12(unittest.TestCase):
    """Tests para T12: CI: service container + steps integración + drift check + db.integration.test.ts + README."""

    @classmethod
    def setUpClass(cls):
        """Setup común: obtener la raíz del repo."""
        cls.repo_root = Path(__file__).parent.parent
        cls.ci_file = cls.repo_root / ".github" / "workflows" / "ci.yml"
        cls.integration_test_file = cls.repo_root / "apps" / "api" / "test" / "db.integration.test.ts"
        cls.readme_file = cls.repo_root / "README.md"

    def test_ci_has_postgres_service_container(self):
        """ci.yml contiene 'pgvector/pgvector:0.8.6-pg18' bajo services."""
        self.assertTrue(
            self.ci_file.exists(),
            ".github/workflows/ci.yml debe existir"
        )

        content = self.ci_file.read_text()
        
        # Extract node job
        jobs_block = extract_yaml_block(content, 'jobs', 0)
        self.assertIn('node:', jobs_block, "ci.yml debe tener un job 'node'")
        
        node_block = extract_yaml_block(jobs_block, 'node', 2)
        
        # Extract services block
        services_block = extract_yaml_block(node_block, 'services', 4)
        self.assertIn(
            'pgvector/pgvector:0.8.6-pg18',
            services_block,
            "ci.yml job 'node' debe tener un servicio con imagen 'pgvector/pgvector:0.8.6-pg18'"
        )

    def test_ci_has_database_url_env(self):
        """ci.yml contiene DATABASE_URL con referencia a localhost y 5432."""
        self.assertTrue(
            self.ci_file.exists(),
            ".github/workflows/ci.yml debe existir"
        )

        content = self.ci_file.read_text()
        
        # Extract node job
        jobs_block = extract_yaml_block(content, 'jobs', 0)
        node_block = extract_yaml_block(jobs_block, 'node', 2)
        
        # Extract env block
        env_block = extract_yaml_block(node_block, 'env', 4)
        self.assertIn('DATABASE_URL', env_block, "ci.yml job 'node' debe tener DATABASE_URL en env")
        
        # Find DATABASE_URL line and verify it contains localhost and 5432
        for line in env_block.split('\n'):
            if 'DATABASE_URL' in line:
                self.assertIn('localhost', line, "DATABASE_URL debe contener 'localhost'")
                self.assertIn('5432', line, "DATABASE_URL debe contener '5432'")

    def test_ci_runs_db_migrate(self):
        """ci.yml contiene step con 'db:migrate'."""
        self.assertTrue(
            self.ci_file.exists(),
            ".github/workflows/ci.yml debe existir"
        )

        content = self.ci_file.read_text()
        
        # Extract node job
        jobs_block = extract_yaml_block(content, 'jobs', 0)
        node_block = extract_yaml_block(jobs_block, 'node', 2)
        
        # Extract steps block
        steps_block = extract_yaml_block(node_block, 'steps', 4)
        self.assertIn(
            'db:migrate',
            steps_block,
            "ci.yml job 'node' debe tener un step que ejecute 'db:migrate'"
        )

    def test_ci_runs_test_integration(self):
        """ci.yml contiene step con 'test:integration'."""
        self.assertTrue(
            self.ci_file.exists(),
            ".github/workflows/ci.yml debe existir"
        )

        content = self.ci_file.read_text()
        
        # Extract node job
        jobs_block = extract_yaml_block(content, 'jobs', 0)
        node_block = extract_yaml_block(jobs_block, 'node', 2)
        
        # Extract steps block
        steps_block = extract_yaml_block(node_block, 'steps', 4)
        self.assertIn(
            'test:integration',
            steps_block,
            "ci.yml job 'node' debe tener un step que ejecute 'test:integration'"
        )

    def test_ci_runs_drizzle_generate_and_drift_check(self):
        """ci.yml contiene 'db:generate' y 'git diff --exit-code'."""
        self.assertTrue(
            self.ci_file.exists(),
            ".github/workflows/ci.yml debe existir"
        )

        content = self.ci_file.read_text()
        
        # Extract node job
        jobs_block = extract_yaml_block(content, 'jobs', 0)
        node_block = extract_yaml_block(jobs_block, 'node', 2)
        
        # Extract steps block
        steps_block = extract_yaml_block(node_block, 'steps', 4)
        self.assertIn(
            'db:generate',
            steps_block,
            "ci.yml job 'node' debe tener un step que ejecute 'db:generate'"
        )
        self.assertIn(
            'git diff --exit-code',
            steps_block,
            "ci.yml job 'node' debe tener un step que ejecute 'git diff --exit-code'"
        )

    def test_ci_python_job_untouched(self):
        """ci.yml sigue teniendo job 'test' con python-version '3.12'."""
        self.assertTrue(
            self.ci_file.exists(),
            ".github/workflows/ci.yml debe existir"
        )

        content = self.ci_file.read_text()
        
        # Extract jobs block
        jobs_block = extract_yaml_block(content, 'jobs', 0)
        self.assertIn('test:', jobs_block, "ci.yml debe tener un job 'test'")
        
        # Extract test job
        test_block = extract_yaml_block(jobs_block, 'test', 2)
        
        # Check for Setup Python step with version 3.12
        self.assertIn('Setup Python', test_block, "job 'test' debe tener step 'Setup Python'")
        self.assertIn("python-version: '3.12'", test_block, "Setup Python debe usar python-version '3.12'")

    def test_ci_node_steps_order(self):
        """ci.yml job 'node' ejecuta steps en orden: migrate → seed → seed → test:integration → generate → drift check."""
        self.assertTrue(
            self.ci_file.exists(),
            ".github/workflows/ci.yml debe existir"
        )

        content = self.ci_file.read_text()
        
        # Extract node job steps
        jobs_block = extract_yaml_block(content, 'jobs', 0)
        node_block = extract_yaml_block(jobs_block, 'node', 2)
        steps_block = extract_yaml_block(node_block, 'steps', 4)
        
        # Find positions by searching for the run commands directly
        # This is simpler and more robust than looking for names
        steps_lines = steps_block.split('\n')
        
        migrate_pos = None
        first_seed_pos = None
        second_seed_pos = None
        integration_pos = None
        generate_pos = None
        drift_pos = None
        
        seed_count = 0
        
        for i, line in enumerate(steps_lines):
            # Check for commands in run: lines or in subsequent lines
            if 'db:migrate' in line:
                if migrate_pos is None:
                    migrate_pos = i
            elif 'db:seed' in line:
                seed_count += 1
                if seed_count == 1:
                    first_seed_pos = i
                elif seed_count == 2:
                    second_seed_pos = i
            elif 'test:integration' in line:
                if integration_pos is None:
                    integration_pos = i
            elif 'db:generate' in line:
                if generate_pos is None:
                    generate_pos = i
            elif 'git diff --exit-code' in line:
                if drift_pos is None:
                    drift_pos = i
        
        # Verify all steps were found
        self.assertIsNotNone(migrate_pos, "No se encontró step con db:migrate")
        self.assertIsNotNone(first_seed_pos, "No se encontró primer step con db:seed")
        self.assertIsNotNone(second_seed_pos, "No se encontró segundo step con db:seed")
        self.assertIsNotNone(integration_pos, "No se encontró step con test:integration")
        self.assertIsNotNone(generate_pos, "No se encontró step con db:generate")
        self.assertIsNotNone(drift_pos, "No se encontró step con git diff --exit-code")
        
        # Verify order
        self.assertLess(migrate_pos, first_seed_pos, 
                       "db:migrate debe ejecutarse antes del primer db:seed")
        self.assertLess(first_seed_pos, second_seed_pos,
                       "primer db:seed debe ejecutarse antes del segundo db:seed")
        self.assertLess(second_seed_pos, integration_pos,
                       "segundo db:seed debe ejecutarse antes de test:integration")
        self.assertLess(integration_pos, generate_pos,
                       "test:integration debe ejecutarse antes de db:generate")
        self.assertLess(generate_pos, drift_pos,
                       "db:generate debe ejecutarse antes del drift check")

    def test_integration_test_file_exists(self):
        """apps/api/test/db.integration.test.ts existe."""
        self.assertTrue(
            self.integration_test_file.exists(),
            "apps/api/test/db.integration.test.ts debe existir"
        )

    def test_readme_has_db_section(self):
        """README.md contiene una sección sobre la base de datos."""
        self.assertTrue(
            self.readme_file.exists(),
            "README.md debe existir"
        )

        content = self.readme_file.read_text()
        
        # Verificar que contenga referencias a la base de datos
        # Buscamos palabras clave relacionadas con DB
        db_keywords = ['database', 'postgres', 'db:', 'migracion', 'migration', 'seed']
        
        found = False
        for keyword in db_keywords:
            if keyword.lower() in content.lower():
                found = True
                break
        
        self.assertTrue(
            found,
            "README.md debe contener una sección sobre la base de datos con información de comandos DB"
        )


class TestIssue10Task11(unittest.TestCase):
    """Tests para T11: docker-compose.yml + tests Python estructurales."""

    @classmethod
    def setUpClass(cls):
        """Setup común: obtener la raíz del repo."""
        cls.repo_root = Path(__file__).parent.parent
        cls.docker_compose_file = cls.repo_root / "docker-compose.yml"

    def test_docker_compose_exists(self):
        """docker-compose.yml existe en la raíz del repo."""
        self.assertTrue(
            self.docker_compose_file.exists(),
            "docker-compose.yml debe existir en la raíz del repo"
        )

    def test_docker_compose_uses_pgvector_pg18_image(self):
        """docker-compose.yml contiene 'pgvector/pgvector:0.8.6-pg18'."""
        self.assertTrue(
            self.docker_compose_file.exists(),
            "docker-compose.yml debe existir para verificar su contenido"
        )

        content = self.docker_compose_file.read_text()
        
        # Extract services block
        services_block = extract_yaml_block(content, 'services', 0)
        self.assertIn(
            'pgvector/pgvector:0.8.6-pg18',
            services_block,
            "docker-compose.yml debe contener un servicio con imagen 'pgvector/pgvector:0.8.6-pg18'"
        )

    def test_docker_compose_exposes_5432(self):
        """docker-compose.yml contiene '5432'."""
        self.assertTrue(
            self.docker_compose_file.exists(),
            "docker-compose.yml debe existir para verificar su contenido"
        )

        content = self.docker_compose_file.read_text()
        
        # Extract services block and look for ports
        services_block = extract_yaml_block(content, 'services', 0)
        # Look for ports section with 5432
        self.assertRegex(
            services_block,
            r'ports:\s*\n\s*-\s*["\']?5432',
            "docker-compose.yml debe contener el puerto 5432 en algún servicio"
        )

    def test_docker_compose_has_healthcheck_pg_isready(self):
        """docker-compose.yml contiene 'healthcheck' y 'pg_isready'."""
        self.assertTrue(
            self.docker_compose_file.exists(),
            "docker-compose.yml debe existir para verificar su contenido"
        )

        content = self.docker_compose_file.read_text()
        
        # Extract services block
        services_block = extract_yaml_block(content, 'services', 0)
        self.assertIn(
            'healthcheck',
            services_block,
            "docker-compose.yml debe contener 'healthcheck' en algún servicio"
        )
        self.assertIn(
            'pg_isready',
            services_block,
            "docker-compose.yml healthcheck debe contener 'pg_isready'"
        )

    def test_docker_compose_has_postgres_env_vars(self):
        """docker-compose.yml contiene POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB."""
        self.assertTrue(
            self.docker_compose_file.exists(),
            "docker-compose.yml debe existir para verificar su contenido"
        )

        content = self.docker_compose_file.read_text()
        
        # Extract services block
        services_block = extract_yaml_block(content, 'services', 0)
        
        # Check for required environment variables
        required_env_vars = ['POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_DB']
        for env_var in required_env_vars:
            self.assertIn(
                env_var,
                services_block,
                f"docker-compose.yml debe contener la variable de entorno '{env_var}'"
            )


if __name__ == '__main__':
    unittest.main()

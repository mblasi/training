#!/usr/bin/env python3
"""
Tests for issue #10: Postgres 18 + pgvector + Drizzle en apps/api

Verifica que las dependencias de Drizzle y pg estén instaladas, que los scripts
de DB estén configurados, y que existan los archivos de configuración necesarios.
"""
import json
import unittest
from pathlib import Path
import yaml


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

        with open(self.ci_file, 'r') as f:
            ci_data = yaml.safe_load(f)

        # Verificar que el job 'node' tenga services con pgvector
        jobs = ci_data.get('jobs', {})
        self.assertIn(
            'node',
            jobs,
            "ci.yml debe tener un job 'node'"
        )

        node_job = jobs['node']
        services = node_job.get('services', {})
        
        # Buscar algún servicio que use la imagen pgvector
        found = False
        for service_name, service_config in services.items():
            image = service_config.get('image', '')
            if 'pgvector/pgvector:0.8.6-pg18' in image:
                found = True
                break
        
        self.assertTrue(
            found,
            "ci.yml job 'node' debe tener un servicio con imagen 'pgvector/pgvector:0.8.6-pg18'"
        )

    def test_ci_has_database_url_env(self):
        """ci.yml contiene DATABASE_URL con referencia a localhost y 5432."""
        self.assertTrue(
            self.ci_file.exists(),
            ".github/workflows/ci.yml debe existir"
        )

        with open(self.ci_file, 'r') as f:
            ci_data = yaml.safe_load(f)

        # Verificar que el job 'node' tenga env con DATABASE_URL
        jobs = ci_data.get('jobs', {})
        self.assertIn(
            'node',
            jobs,
            "ci.yml debe tener un job 'node'"
        )

        node_job = jobs['node']
        env = node_job.get('env', {})
        
        self.assertIn(
            'DATABASE_URL',
            env,
            "ci.yml job 'node' debe tener DATABASE_URL en env"
        )

        database_url = env['DATABASE_URL']
        self.assertIn(
            'localhost',
            database_url,
            "DATABASE_URL debe contener 'localhost'"
        )
        self.assertIn(
            '5432',
            database_url,
            "DATABASE_URL debe contener '5432'"
        )

    def test_ci_runs_db_migrate(self):
        """ci.yml contiene step con 'db:migrate'."""
        self.assertTrue(
            self.ci_file.exists(),
            ".github/workflows/ci.yml debe existir"
        )

        with open(self.ci_file, 'r') as f:
            ci_data = yaml.safe_load(f)

        # Verificar que el job 'node' tenga un step que ejecute db:migrate
        jobs = ci_data.get('jobs', {})
        self.assertIn(
            'node',
            jobs,
            "ci.yml debe tener un job 'node'"
        )

        node_job = jobs['node']
        steps = node_job.get('steps', [])
        
        found = False
        for step in steps:
            run = step.get('run', '')
            if 'db:migrate' in run:
                found = True
                break
        
        self.assertTrue(
            found,
            "ci.yml job 'node' debe tener un step que ejecute 'db:migrate'"
        )

    def test_ci_runs_test_integration(self):
        """ci.yml contiene step con 'test:integration'."""
        self.assertTrue(
            self.ci_file.exists(),
            ".github/workflows/ci.yml debe existir"
        )

        with open(self.ci_file, 'r') as f:
            ci_data = yaml.safe_load(f)

        # Verificar que el job 'node' tenga un step que ejecute test:integration
        jobs = ci_data.get('jobs', {})
        self.assertIn(
            'node',
            jobs,
            "ci.yml debe tener un job 'node'"
        )

        node_job = jobs['node']
        steps = node_job.get('steps', [])
        
        found = False
        for step in steps:
            run = step.get('run', '')
            if 'test:integration' in run:
                found = True
                break
        
        self.assertTrue(
            found,
            "ci.yml job 'node' debe tener un step que ejecute 'test:integration'"
        )

    def test_ci_runs_drizzle_generate_and_drift_check(self):
        """ci.yml contiene 'db:generate' y 'git diff --exit-code'."""
        self.assertTrue(
            self.ci_file.exists(),
            ".github/workflows/ci.yml debe existir"
        )

        with open(self.ci_file, 'r') as f:
            ci_data = yaml.safe_load(f)

        # Verificar que el job 'node' tenga steps que ejecuten db:generate y git diff
        jobs = ci_data.get('jobs', {})
        self.assertIn(
            'node',
            jobs,
            "ci.yml debe tener un job 'node'"
        )

        node_job = jobs['node']
        steps = node_job.get('steps', [])
        
        found_generate = False
        found_drift_check = False
        
        for step in steps:
            run = step.get('run', '')
            if 'db:generate' in run:
                found_generate = True
            if 'git diff --exit-code' in run:
                found_drift_check = True
        
        self.assertTrue(
            found_generate,
            "ci.yml job 'node' debe tener un step que ejecute 'db:generate'"
        )
        self.assertTrue(
            found_drift_check,
            "ci.yml job 'node' debe tener un step que ejecute 'git diff --exit-code'"
        )

    def test_ci_python_job_untouched(self):
        """ci.yml sigue teniendo job 'test' con python-version '3.12'."""
        self.assertTrue(
            self.ci_file.exists(),
            ".github/workflows/ci.yml debe existir"
        )

        with open(self.ci_file, 'r') as f:
            ci_data = yaml.safe_load(f)

        # Verificar que el job 'test' siga existiendo
        jobs = ci_data.get('jobs', {})
        self.assertIn(
            'test',
            jobs,
            "ci.yml debe tener un job 'test'"
        )

        test_job = jobs['test']
        steps = test_job.get('steps', [])
        
        # Buscar el step de Setup Python
        found = False
        for step in steps:
            if step.get('name') == 'Setup Python':
                with_config = step.get('with', {})
                python_version = with_config.get('python-version', '')
                if python_version == '3.12':
                    found = True
                    break
        
        self.assertTrue(
            found,
            "ci.yml job 'test' debe tener un step 'Setup Python' con python-version '3.12'"
        )

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

        with open(self.docker_compose_file, 'r') as f:
            compose_data = yaml.safe_load(f)

        # Buscar el servicio postgres y verificar que use la imagen correcta
        services = compose_data.get('services', {})
        
        # Buscar cualquier servicio que use la imagen pgvector
        found = False
        for service_name, service_config in services.items():
            image = service_config.get('image', '')
            if 'pgvector/pgvector:0.8.6-pg18' in image:
                found = True
                break
        
        self.assertTrue(
            found,
            "docker-compose.yml debe contener un servicio con imagen 'pgvector/pgvector:0.8.6-pg18'"
        )

    def test_docker_compose_exposes_5432(self):
        """docker-compose.yml contiene '5432'."""
        self.assertTrue(
            self.docker_compose_file.exists(),
            "docker-compose.yml debe existir para verificar su contenido"
        )

        with open(self.docker_compose_file, 'r') as f:
            compose_data = yaml.safe_load(f)

        # Buscar el puerto 5432 en algún servicio
        services = compose_data.get('services', {})
        
        found = False
        for service_name, service_config in services.items():
            ports = service_config.get('ports', [])
            for port in ports:
                if '5432' in str(port):
                    found = True
                    break
            if found:
                break
        
        self.assertTrue(
            found,
            "docker-compose.yml debe contener el puerto 5432 en algún servicio"
        )

    def test_docker_compose_has_healthcheck_pg_isready(self):
        """docker-compose.yml contiene 'healthcheck' y 'pg_isready'."""
        self.assertTrue(
            self.docker_compose_file.exists(),
            "docker-compose.yml debe existir para verificar su contenido"
        )

        with open(self.docker_compose_file, 'r') as f:
            compose_data = yaml.safe_load(f)

        # Buscar healthcheck con pg_isready en algún servicio
        services = compose_data.get('services', {})
        
        found_healthcheck = False
        found_pg_isready = False
        
        for service_name, service_config in services.items():
            healthcheck = service_config.get('healthcheck', {})
            if healthcheck:
                found_healthcheck = True
                # Verificar que el healthcheck contenga pg_isready
                test = healthcheck.get('test', '')
                if isinstance(test, list):
                    test = ' '.join(test)
                if 'pg_isready' in str(test):
                    found_pg_isready = True
                    break
        
        self.assertTrue(
            found_healthcheck,
            "docker-compose.yml debe contener 'healthcheck' en algún servicio"
        )
        self.assertTrue(
            found_pg_isready,
            "docker-compose.yml healthcheck debe contener 'pg_isready'"
        )

    def test_docker_compose_has_postgres_env_vars(self):
        """docker-compose.yml contiene POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB."""
        self.assertTrue(
            self.docker_compose_file.exists(),
            "docker-compose.yml debe existir para verificar su contenido"
        )

        with open(self.docker_compose_file, 'r') as f:
            compose_data = yaml.safe_load(f)

        # Buscar variables de entorno de Postgres en algún servicio
        services = compose_data.get('services', {})
        
        required_env_vars = ['POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_DB']
        found_env_vars = set()
        
        for service_name, service_config in services.items():
            environment = service_config.get('environment', {})
            
            # environment puede ser dict o lista
            if isinstance(environment, dict):
                env_keys = environment.keys()
            elif isinstance(environment, list):
                env_keys = [item.split('=')[0] for item in environment]
            else:
                continue
            
            for env_var in required_env_vars:
                if env_var in env_keys:
                    found_env_vars.add(env_var)
        
        for env_var in required_env_vars:
            self.assertIn(
                env_var,
                found_env_vars,
                f"docker-compose.yml debe contener la variable de entorno '{env_var}'"
            )


if __name__ == '__main__':
    unittest.main()

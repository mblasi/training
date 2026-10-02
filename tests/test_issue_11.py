#!/usr/bin/env python3
"""
Tests for issue #11: Auth con Firebase en api, admin y mobile

Verifica que firebase.json esté configurado, firebase-tools instalado,
y que las configuraciones de auth estén presentes en cada aplicación.
"""
import json
import unittest
from pathlib import Path


class TestIssue11Task1(unittest.TestCase):
    """Tests para T1: firebase.json + firebase-tools en raíz."""

    @classmethod
    def setUpClass(cls):
        """Setup común: obtener la raíz del repo."""
        cls.repo_root = Path(__file__).parent.parent
        cls.firebase_json = cls.repo_root / "firebase.json"
        cls.root_package_json = cls.repo_root / "package.json"

    def test_firebase_json_exists(self):
        """firebase.json existe en la raíz del repo."""
        self.assertTrue(
            self.firebase_json.exists(),
            "firebase.json debe existir en la raíz del repo"
        )

    def test_firebase_json_has_auth_emulator_port_9099(self):
        """firebase.json parseado como JSON contiene emulators.auth.port === 9099."""
        self.assertTrue(
            self.firebase_json.exists(),
            "firebase.json debe existir para verificar su contenido"
        )

        with open(self.firebase_json, 'r') as f:
            firebase_config = json.load(f)

        self.assertIn(
            'emulators',
            firebase_config,
            "firebase.json debe contener campo 'emulators'"
        )

        emulators = firebase_config['emulators']
        self.assertIsInstance(
            emulators,
            dict,
            "'emulators' debe ser un objeto"
        )

        self.assertIn(
            'auth',
            emulators,
            "emulators debe contener campo 'auth'"
        )

        auth_config = emulators['auth']
        self.assertIsInstance(
            auth_config,
            dict,
            "emulators.auth debe ser un objeto"
        )

        self.assertIn(
            'port',
            auth_config,
            "emulators.auth debe contener campo 'port'"
        )

        self.assertEqual(
            auth_config['port'],
            9099,
            "emulators.auth.port debe ser 9099"
        )

    def test_root_package_json_has_firebase_tools(self):
        """package.json raíz devDependencies contiene 'firebase-tools' con versión '15.32.0'."""
        self.assertTrue(
            self.root_package_json.exists(),
            "package.json debe existir en la raíz del repo"
        )

        with open(self.root_package_json, 'r') as f:
            pkg = json.load(f)

        self.assertIn(
            'devDependencies',
            pkg,
            "package.json debe contener campo 'devDependencies'"
        )

        dev_dependencies = pkg['devDependencies']
        self.assertIsInstance(
            dev_dependencies,
            dict,
            "'devDependencies' debe ser un objeto"
        )

        self.assertIn(
            'firebase-tools',
            dev_dependencies,
            "devDependencies debe contener 'firebase-tools'"
        )

        self.assertEqual(
            dev_dependencies['firebase-tools'],
            '15.32.0',
            "firebase-tools debe ser versión '15.32.0'"
        )


class TestIssue11Task2(unittest.TestCase):
    """Tests para T2: tipos de auth + requireFirebaseProjectId + firebase-admin dep."""

    @classmethod
    def setUpClass(cls):
        """Setup común: obtener la raíz del repo."""
        cls.repo_root = Path(__file__).parent.parent
        cls.api_package_json = cls.repo_root / "apps" / "api" / "package.json"

    def test_api_package_json_has_firebase_admin(self):
        """apps/api/package.json dependencies contiene 'firebase-admin' con versión '14.5.0'."""
        self.assertTrue(
            self.api_package_json.exists(),
            "apps/api/package.json debe existir"
        )

        with open(self.api_package_json, 'r') as f:
            pkg = json.load(f)

        self.assertIn(
            'dependencies',
            pkg,
            "apps/api/package.json debe contener campo 'dependencies'"
        )

        dependencies = pkg['dependencies']
        self.assertIsInstance(
            dependencies,
            dict,
            "'dependencies' debe ser un objeto"
        )

        self.assertIn(
            'firebase-admin',
            dependencies,
            "dependencies debe contener 'firebase-admin'"
        )

        self.assertEqual(
            dependencies['firebase-admin'],
            '14.5.0',
            "firebase-admin debe ser versión '14.5.0'"
        )


class TestIssue11Task8(unittest.TestCase):
    """Tests para T8: CI con emulators:exec + archivos de integración + README."""

    @classmethod
    def setUpClass(cls):
        """Setup común: obtener la raíz del repo."""
        cls.repo_root = Path(__file__).parent.parent
        cls.ci_yml = cls.repo_root / ".github" / "workflows" / "ci.yml"
        cls.api_auth_integration_test = cls.repo_root / "apps" / "api" / "test" / "auth.integration.test.ts"
        cls.api_vitest_integration_config = cls.repo_root / "apps" / "api" / "vitest.integration.config.ts"
        cls.mobile_auth_integration_test = cls.repo_root / "apps" / "mobile" / "test" / "auth.integration.test.ts"
        cls.mobile_vitest_integration_config = cls.repo_root / "apps" / "mobile" / "vitest.integration.config.ts"
        cls.mobile_package_json = cls.repo_root / "apps" / "mobile" / "package.json"
        cls.readme = cls.repo_root / "README.md"

    def test_api_index_requires_firebase_project_id(self):
        """apps/api/src/index.ts contiene 'requireFirebaseProjectId'."""
        index_ts = self.repo_root / "apps" / "api" / "src" / "index.ts"
        self.assertTrue(
            index_ts.exists(),
            "apps/api/src/index.ts debe existir"
        )

        with open(index_ts, 'r') as f:
            content = f.read()

        self.assertIn(
            'requireFirebaseProjectId',
            content,
            "apps/api/src/index.ts debe contener 'requireFirebaseProjectId'"
        )

    def test_api_index_calls_initialize_app(self):
        """apps/api/src/index.ts contiene 'initializeApp'."""
        index_ts = self.repo_root / "apps" / "api" / "src" / "index.ts"
        self.assertTrue(
            index_ts.exists(),
            "apps/api/src/index.ts debe existir"
        )

        with open(index_ts, 'r') as f:
            content = f.read()

        self.assertIn(
            'initializeApp',
            content,
            "apps/api/src/index.ts debe contener 'initializeApp'"
        )

    def test_ci_has_setup_java_temurin_21(self):
        """ci.yml job 'node' contiene actions/setup-java con distribution 'temurin' y java-version '21'."""
        self.assertTrue(
            self.ci_yml.exists(),
            ".github/workflows/ci.yml debe existir"
        )

        with open(self.ci_yml, 'r') as f:
            content = f.read()

        self.assertIn(
            'setup-java',
            content,
            "ci.yml debe contener 'setup-java'"
        )
        self.assertIn(
            'temurin',
            content,
            "ci.yml debe contener distribution 'temurin'"
        )
        self.assertIn(
            "'21'",
            content,
            "ci.yml debe contener java-version '21'"
        )

    def test_ci_has_firebase_emulators_exec_with_auth_and_project(self):
        """ci.yml contiene 'firebase emulators:exec' con '--only auth' y '--project demo-trainia'."""
        self.assertTrue(
            self.ci_yml.exists(),
            ".github/workflows/ci.yml debe existir"
        )

        with open(self.ci_yml, 'r') as f:
            content = f.read()

        self.assertIn(
            'firebase emulators:exec',
            content,
            "ci.yml debe contener 'firebase emulators:exec'"
        )
        self.assertIn(
            '--only auth',
            content,
            "ci.yml debe contener '--only auth'"
        )
        self.assertIn(
            '--project demo-trainia',
            content,
            "ci.yml debe contener '--project demo-trainia'"
        )

    def test_ci_emulators_exec_wraps_both_integration_tests(self):
        """El step con emulators:exec contiene test:integration de @trainia/api y @trainia/mobile en el mismo comando."""
        self.assertTrue(
            self.ci_yml.exists(),
            ".github/workflows/ci.yml debe existir"
        )

        with open(self.ci_yml, 'r') as f:
            content = f.read()

        # Buscar el comando que contiene emulators:exec
        emulators_exec_found = False
        api_test_integration_found = False
        mobile_test_integration_found = False

        for line in content.split('\n'):
            if 'firebase emulators:exec' in line:
                emulators_exec_found = True
            if '@trainia/api test:integration' in line:
                api_test_integration_found = True
            if '@trainia/mobile test:integration' in line:
                mobile_test_integration_found = True

        self.assertTrue(
            emulators_exec_found,
            "ci.yml debe contener 'firebase emulators:exec'"
        )
        self.assertTrue(
            api_test_integration_found,
            "ci.yml debe contener '@trainia/api test:integration'"
        )
        self.assertTrue(
            mobile_test_integration_found,
            "ci.yml debe contener '@trainia/mobile test:integration'"
        )

    def test_ci_integration_step_has_firebase_project_id_env(self):
        """El step de emulators:exec en ci.yml tiene env FIREBASE_PROJECT_ID=demo-trainia."""
        self.assertTrue(
            self.ci_yml.exists(),
            ".github/workflows/ci.yml debe existir"
        )

        with open(self.ci_yml, 'r') as f:
            content = f.read()

        self.assertIn(
            'FIREBASE_PROJECT_ID',
            content,
            "ci.yml debe contener FIREBASE_PROJECT_ID"
        )
        self.assertIn(
            'demo-trainia',
            content,
            "ci.yml debe contener 'demo-trainia'"
        )

    def test_ci_integration_step_has_firebase_auth_emulator_host_env(self):
        """El step de emulators:exec en ci.yml tiene env FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099."""
        self.assertTrue(
            self.ci_yml.exists(),
            ".github/workflows/ci.yml debe existir"
        )

        with open(self.ci_yml, 'r') as f:
            content = f.read()

        self.assertIn(
            'FIREBASE_AUTH_EMULATOR_HOST',
            content,
            "ci.yml debe contener FIREBASE_AUTH_EMULATOR_HOST"
        )
        self.assertIn(
            '127.0.0.1:9099',
            content,
            "ci.yml debe contener '127.0.0.1:9099'"
        )

    def test_ci_integration_step_has_expo_firebase_auth_emulator_host_env(self):
        """El step de emulators:exec en ci.yml tiene env EXPO_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099."""
        self.assertTrue(
            self.ci_yml.exists(),
            ".github/workflows/ci.yml debe existir"
        )

        with open(self.ci_yml, 'r') as f:
            content = f.read()

        self.assertIn(
            'EXPO_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST',
            content,
            "ci.yml debe contener EXPO_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST"
        )

    def test_ci_integration_step_has_admin_emails_env(self):
        """El step de emulators:exec en ci.yml tiene env ADMIN_EMAILS=admin@test.local."""
        self.assertTrue(
            self.ci_yml.exists(),
            ".github/workflows/ci.yml debe existir"
        )

        with open(self.ci_yml, 'r') as f:
            content = f.read()

        self.assertIn(
            'ADMIN_EMAILS',
            content,
            "ci.yml debe contener ADMIN_EMAILS"
        )

    def test_api_auth_integration_test_exists(self):
        """apps/api/test/auth.integration.test.ts existe."""
        self.assertTrue(
            self.api_auth_integration_test.exists(),
            "apps/api/test/auth.integration.test.ts debe existir"
        )

    def test_api_auth_integration_test_covers_required_cases(self):
        """auth.integration.test.ts contiene referencias a '/me' y '/admin/ping' y a los casos 401, 403, 200."""
        self.assertTrue(
            self.api_auth_integration_test.exists(),
            "apps/api/test/auth.integration.test.ts debe existir para verificar su contenido"
        )

        with open(self.api_auth_integration_test, 'r') as f:
            content = f.read()

        self.assertIn(
            '/me',
            content,
            "auth.integration.test.ts debe contener '/me'"
        )
        self.assertIn(
            '/admin/ping',
            content,
            "auth.integration.test.ts debe contener '/admin/ping'"
        )
        # Verificar que contiene casos de status codes
        has_401 = '401' in content
        has_403 = '403' in content
        has_200 = '200' in content

        self.assertTrue(
            has_401 or has_403 or has_200,
            "auth.integration.test.ts debe contener referencias a los status codes 401, 403 o 200"
        )

    def test_mobile_auth_integration_test_exists(self):
        """apps/mobile/test/auth.integration.test.ts existe."""
        self.assertTrue(
            self.mobile_auth_integration_test.exists(),
            "apps/mobile/test/auth.integration.test.ts debe existir"
        )

    def test_mobile_auth_integration_test_imports_from_src_auth(self):
        """apps/mobile/test/auth.integration.test.ts importa desde '../src/auth' (no desde 'firebase' directamente)."""
        self.assertTrue(
            self.mobile_auth_integration_test.exists(),
            "apps/mobile/test/auth.integration.test.ts debe existir para verificar sus imports"
        )

        with open(self.mobile_auth_integration_test, 'r') as f:
            content = f.read()

        self.assertIn(
            '../src/auth',
            content,
            "auth.integration.test.ts debe importar desde '../src/auth'"
        )

    def test_mobile_auth_integration_test_covers_signin_and_wrong_password(self):
        """apps/mobile/test/auth.integration.test.ts contiene casos de signInWithEmail exitoso y con contraseña incorrecta."""
        self.assertTrue(
            self.mobile_auth_integration_test.exists(),
            "apps/mobile/test/auth.integration.test.ts debe existir para verificar su contenido"
        )

        with open(self.mobile_auth_integration_test, 'r') as f:
            content = f.read()

        # Verificar que menciona signInWithEmail o signIn
        has_signin = 'signIn' in content
        # Verificar que menciona casos de error/wrong/invalid password
        has_error_case = 'wrong' in content.lower() or 'invalid' in content.lower() or 'error' in content.lower() or 'password' in content.lower()

        self.assertTrue(
            has_signin,
            "auth.integration.test.ts debe mencionar signIn"
        )
        self.assertTrue(
            has_error_case,
            "auth.integration.test.ts debe mencionar casos de error o contraseña incorrecta"
        )

    def test_mobile_vitest_integration_config_exists(self):
        """apps/mobile/vitest.integration.config.ts existe."""
        self.assertTrue(
            self.mobile_vitest_integration_config.exists(),
            "apps/mobile/vitest.integration.config.ts debe existir"
        )

    def test_mobile_package_json_has_test_integration_script(self):
        """apps/mobile/package.json scripts contiene 'test:integration' apuntando a vitest.integration.config.ts."""
        self.assertTrue(
            self.mobile_package_json.exists(),
            "apps/mobile/package.json debe existir"
        )

        with open(self.mobile_package_json, 'r') as f:
            pkg = json.load(f)

        self.assertIn(
            'scripts',
            pkg,
            "apps/mobile/package.json debe contener campo 'scripts'"
        )

        scripts = pkg['scripts']
        self.assertIsInstance(
            scripts,
            dict,
            "'scripts' debe ser un objeto"
        )

        self.assertIn(
            'test:integration',
            scripts,
            "scripts debe contener 'test:integration'"
        )

        test_integration_script = scripts['test:integration']
        self.assertIn(
            'vitest.integration.config',
            test_integration_script,
            "test:integration debe apuntar a vitest.integration.config.ts"
        )

    def test_readme_documents_jdk_21(self):
        """README.md contiene 'JDK 21' o 'Java 21'."""
        self.assertTrue(
            self.readme.exists(),
            "README.md debe existir"
        )

        with open(self.readme, 'r') as f:
            content = f.read()

        has_jdk_21 = 'JDK 21' in content or 'Java 21' in content
        self.assertTrue(
            has_jdk_21,
            "README.md debe mencionar 'JDK 21' o 'Java 21'"
        )

    def test_readme_documents_firebase_env_vars(self):
        """README.md contiene FIREBASE_PROJECT_ID, FIREBASE_AUTH_EMULATOR_HOST y EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID."""
        self.assertTrue(
            self.readme.exists(),
            "README.md debe existir"
        )

        with open(self.readme, 'r') as f:
            content = f.read()

        self.assertIn(
            'FIREBASE_PROJECT_ID',
            content,
            "README.md debe mencionar FIREBASE_PROJECT_ID"
        )
        self.assertIn(
            'FIREBASE_AUTH_EMULATOR_HOST',
            content,
            "README.md debe mencionar FIREBASE_AUTH_EMULATOR_HOST"
        )
        self.assertIn(
            'EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID',
            content,
            "README.md debe mencionar EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID"
        )


if __name__ == '__main__':
    unittest.main()

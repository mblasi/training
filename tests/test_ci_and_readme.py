#!/usr/bin/env python3
"""
Tests for T6 (issue #24): CI job Node y README.

Verifica que ci.yml contenga job 'node' con Node 24, corepack, pnpm install --frozen-lockfile,
lint, typecheck, test, y que el job Python original 'test' siga intacto.
También verifica que README.md contenga instrucciones de desarrollo para cada app.
"""
import unittest
from pathlib import Path


class TestCIWorkflowNodeJob(unittest.TestCase):
    """Test CI workflow contains node job with correct configuration."""
    
    def setUp(self):
        """Set up test paths."""
        self.repo_root = Path(__file__).parent.parent
        self.ci_yml = self.repo_root / ".github" / "workflows" / "ci.yml"
    
    def test_ci_yml_has_node_job(self):
        """Test ci.yml contiene job 'node' con setup-node node-version 24, corepack enable y pnpm install --frozen-lockfile."""
        self.assertTrue(self.ci_yml.exists(), "ci.yml debe existir")
        
        content = self.ci_yml.read_text()
        
        # Debe contener job 'node'
        self.assertIn("node:", content, "ci.yml debe contener job 'node'")
        
        # Debe contener setup-node con node-version 24
        self.assertIn("actions/setup-node@", content, "ci.yml debe usar actions/setup-node")
        self.assertIn("node-version:", content, "ci.yml debe especificar node-version")
        # Buscar node-version: 24 o node-version: '24'
        self.assertTrue(
            "node-version: 24" in content or "node-version: '24'" in content,
            "ci.yml debe configurar node-version: 24"
        )
        
        # Debe contener corepack enable
        self.assertIn("corepack enable", content, "ci.yml debe ejecutar 'corepack enable'")
        
        # Debe contener pnpm install --frozen-lockfile
        self.assertIn("pnpm install --frozen-lockfile", content, "ci.yml debe ejecutar 'pnpm install --frozen-lockfile'")
    
    def test_ci_yml_node_job_runs_lint_typecheck_test(self):
        """Test ci.yml job 'node' contiene steps con 'pnpm lint', 'pnpm typecheck' y 'pnpm test'."""
        self.assertTrue(self.ci_yml.exists(), "ci.yml debe existir")
        
        content = self.ci_yml.read_text()
        
        # Debe contener pnpm lint
        self.assertIn("pnpm lint", content, "ci.yml job 'node' debe ejecutar 'pnpm lint'")
        
        # Debe contener pnpm typecheck
        self.assertIn("pnpm typecheck", content, "ci.yml job 'node' debe ejecutar 'pnpm typecheck'")
        
        # Debe contener pnpm test
        self.assertIn("pnpm test", content, "ci.yml job 'node' debe ejecutar 'pnpm test'")
    
    def test_ci_yml_python_job_untouched(self):
        """Test ci.yml sigue teniendo el job 'test' Python original con python-version 3.12."""
        self.assertTrue(self.ci_yml.exists(), "ci.yml debe existir")
        
        content = self.ci_yml.read_text()
        
        # Debe contener job 'test'
        self.assertIn("test:", content, "ci.yml debe contener job 'test' (Python)")
        
        # Debe contener setup-python
        self.assertIn("actions/setup-python@", content, "ci.yml debe usar actions/setup-python")
        
        # Debe contener python-version 3.12
        self.assertIn("python-version:", content, "ci.yml debe especificar python-version")
        self.assertTrue(
            "python-version: '3.12'" in content or "python-version: 3.12" in content,
            "ci.yml debe configurar python-version: 3.12"
        )
        
        # Debe contener unittest discover (py_compile de scripts/ se fue con el harness local)
        self.assertNotIn("py_compile", content, "ci.yml ya no debe compilar scripts/ (el harness vive en mblasi/harness)")
        self.assertIn("unittest discover", content, "ci.yml job 'test' debe ejecutar unittest discover")


class TestREADME(unittest.TestCase):
    """Test README.md contiene instrucciones de desarrollo."""
    
    def setUp(self):
        """Set up test paths."""
        self.repo_root = Path(__file__).parent.parent
        self.readme = self.repo_root / "README.md"
    
    def test_readme_has_dev_section(self):
        """Test README.md contiene 'apps/api', 'apps/admin' y 'apps/mobile' en una sección de desarrollo."""
        self.assertTrue(self.readme.exists(), "README.md debe existir")
        
        content = self.readme.read_text()
        
        # Debe mencionar apps/api
        self.assertIn("apps/api", content, "README.md debe mencionar apps/api")
        
        # Debe mencionar apps/admin
        self.assertIn("apps/admin", content, "README.md debe mencionar apps/admin")
        
        # Debe mencionar apps/mobile
        self.assertIn("apps/mobile", content, "README.md debe mencionar apps/mobile")


if __name__ == "__main__":
    unittest.main()

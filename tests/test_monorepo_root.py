#!/usr/bin/env python3
"""
Tests for T1: Scaffolding raíz del monorepo

Verifica que los archivos de configuración raíz del monorepo pnpm existan y tengan
los valores acordados en las decisiones de diseño.
"""
import json
import unittest
import yaml
from pathlib import Path


class TestMonorepoRoot(unittest.TestCase):
    """Tests para los archivos de configuración raíz del monorepo."""

    def setUp(self):
        """Setup común: obtener la raíz del repo."""
        self.repo_root = Path(__file__).parent.parent

    def test_pnpm_workspace_yaml_exists_and_valid(self):
        """pnpm-workspace.yaml existe y contiene 'apps/*' y 'packages/*'."""
        workspace_file = self.repo_root / "pnpm-workspace.yaml"
        self.assertTrue(
            workspace_file.exists(),
            "pnpm-workspace.yaml debe existir en la raíz del repo"
        )

        with open(workspace_file, 'r') as f:
            content = yaml.safe_load(f)

        self.assertIn('packages', content, "pnpm-workspace.yaml debe tener clave 'packages'")
        packages = content['packages']
        self.assertIsInstance(packages, list, "'packages' debe ser una lista")
        self.assertIn('apps/*', packages, "packages debe incluir 'apps/*'")
        self.assertIn('packages/*', packages, "packages debe incluir 'packages/*'")

    def test_package_json_root_has_required_fields(self):
        """package.json raíz tiene packageManager pnpm@12.8.1, scripts lint/typecheck/test y engines node>=24."""
        pkg_file = self.repo_root / "package.json"
        self.assertTrue(
            pkg_file.exists(),
            "package.json debe existir en la raíz del repo"
        )

        with open(pkg_file, 'r') as f:
            pkg = json.load(f)

        # Verificar packageManager
        self.assertIn('packageManager', pkg, "package.json debe tener 'packageManager'")
        self.assertEqual(
            pkg['packageManager'],
            'pnpm@12.8.1',
            "packageManager debe ser exactamente 'pnpm@12.8.1'"
        )

        # Verificar engines
        self.assertIn('engines', pkg, "package.json debe tener 'engines'")
        self.assertIn('node', pkg['engines'], "engines debe especificar 'node'")
        self.assertEqual(
            pkg['engines']['node'],
            '>=24',
            "engines.node debe ser '>=24'"
        )

        # Verificar scripts
        self.assertIn('scripts', pkg, "package.json debe tener 'scripts'")
        scripts = pkg['scripts']
        required_scripts = ['lint', 'typecheck', 'test']
        for script_name in required_scripts:
            self.assertIn(
                script_name,
                scripts,
                f"scripts debe incluir '{script_name}'"
            )

    def test_tsconfig_base_only_has_rigor_flags(self):
        """tsconfig.base.json tiene strict/esModuleInterop/skipLibCheck/resolveJsonModule y NO tiene target ni module."""
        tsconfig_file = self.repo_root / "tsconfig.base.json"
        self.assertTrue(
            tsconfig_file.exists(),
            "tsconfig.base.json debe existir en la raíz del repo"
        )

        with open(tsconfig_file, 'r') as f:
            tsconfig = json.load(f)

        self.assertIn('compilerOptions', tsconfig, "tsconfig.base.json debe tener 'compilerOptions'")
        options = tsconfig['compilerOptions']

        # Flags requeridos
        required_flags = {
            'strict': True,
            'esModuleInterop': True,
            'skipLibCheck': True,
            'resolveJsonModule': True,
        }
        for flag, expected_value in required_flags.items():
            self.assertIn(
                flag,
                options,
                f"compilerOptions debe tener '{flag}'"
            )
            self.assertEqual(
                options[flag],
                expected_value,
                f"compilerOptions.{flag} debe ser {expected_value}"
            )

        # Flags prohibidos (no deben estar en tsconfig.base.json)
        forbidden_flags = ['target', 'module']
        for flag in forbidden_flags:
            self.assertNotIn(
                flag,
                options,
                f"compilerOptions NO debe tener '{flag}' (debe estar en tsconfig de cada app)"
            )

    def test_nvmrc_is_24(self):
        """.nvmrc contiene '24'."""
        nvmrc_file = self.repo_root / ".nvmrc"
        self.assertTrue(
            nvmrc_file.exists(),
            ".nvmrc debe existir en la raíz del repo"
        )

        content = nvmrc_file.read_text().strip()
        self.assertEqual(
            content,
            '24',
            ".nvmrc debe contener exactamente '24'"
        )

    def test_pnpm_lockfile_exists(self):
        """pnpm-lock.yaml existe en la raíz del repo."""
        lockfile = self.repo_root / "pnpm-lock.yaml"
        self.assertTrue(
            lockfile.exists(),
            "pnpm-lock.yaml debe existir en la raíz del repo"
        )


if __name__ == '__main__':
    unittest.main()

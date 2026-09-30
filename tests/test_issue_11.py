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


if __name__ == '__main__':
    unittest.main()

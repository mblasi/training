#!/usr/bin/env python3
"""
Tests for issue #37: CastCheckResult dataclass and resolve_import_to_impl_file.
"""
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

# Import modules to test
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "scripts"))
import tdd_runner


class TestCastCheckResult(unittest.TestCase):
    """Test CastCheckResult dataclass."""
    
    def test_cast_check_result_defaults(self) -> None:
        """Test CastCheckResult() has rejected=None and warnings=()."""
        result = tdd_runner.CastCheckResult()
        self.assertIsNone(result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_cast_check_result_frozen(self) -> None:
        """Test assigning result.rejected raises FrozenInstanceError."""
        result = tdd_runner.CastCheckResult()
        with self.assertRaises(FrozenInstanceError):
            result.rejected = "line"  # type: ignore
    
    def test_cast_check_result_with_values(self) -> None:
        """Test CastCheckResult with rejected and warnings fields."""
        result = tdd_runner.CastCheckResult(rejected='line', warnings=('w1',))
        self.assertEqual(result.rejected, 'line')
        self.assertEqual(result.warnings, ('w1',))
        # Verify immutability
        with self.assertRaises(FrozenInstanceError):
            result.rejected = "new"  # type: ignore


class TestResolveImportToImplFile(unittest.TestCase):
    """Test resolve_import_to_impl_file function."""
    
    def setUp(self) -> None:
        """Create temp directory for test files."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_resolve_import_")
        self.repo_root = Path(self.temp_dir)
    
    def tearDown(self) -> None:
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_resolve_import_js_to_ts(self) -> None:
        """Test resolve_import_to_impl_file resolves .js import to .ts impl_file."""
        # Create impl file
        impl_file = self.repo_root / "apps" / "api" / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp() {}")
        
        # Test file path
        test_file = "apps/api/test/auth.test.ts"
        import_path = "../src/app.js"
        impl_files = ["apps/api/src/app.ts"]
        
        result = tdd_runner.resolve_import_to_impl_file(
            test_file=test_file,
            import_path=import_path,
            impl_files=impl_files,
            repo_root=str(self.repo_root)
        )
        
        self.assertEqual(result, "apps/api/src/app.ts")
    
    def test_resolve_import_no_extension(self) -> None:
        """Test resolve_import_to_impl_file resolves import without extension."""
        # Create impl file
        impl_file = self.repo_root / "src" / "bar.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function bar() {}")
        
        test_file = "test/foo.test.ts"
        import_path = "../src/bar"
        impl_files = ["src/bar.ts"]
        
        result = tdd_runner.resolve_import_to_impl_file(
            test_file=test_file,
            import_path=import_path,
            impl_files=impl_files,
            repo_root=str(self.repo_root)
        )
        
        self.assertEqual(result, "src/bar.ts")
    
    def test_resolve_import_non_relative_ignored(self) -> None:
        """Test resolve_import_to_impl_file returns None for non-relative imports."""
        test_file = "test/foo.test.ts"
        import_path = "vitest"
        impl_files = ["src/bar.ts"]
        
        result = tdd_runner.resolve_import_to_impl_file(
            test_file=test_file,
            import_path=import_path,
            impl_files=impl_files,
            repo_root=str(self.repo_root)
        )
        
        self.assertIsNone(result)
    
    def test_resolve_import_no_match(self) -> None:
        """Test resolve_import_to_impl_file returns None when no impl_file matches."""
        # Create impl file
        impl_file = self.repo_root / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function app() {}")
        
        test_file = "test/foo.test.ts"
        import_path = "../src/other.js"
        impl_files = ["src/app.ts"]
        
        result = tdd_runner.resolve_import_to_impl_file(
            test_file=test_file,
            import_path=import_path,
            impl_files=impl_files,
            repo_root=str(self.repo_root)
        )
        
        self.assertIsNone(result)


class TestTestImportsImplFileStillWorks(unittest.TestCase):
    """Test test_imports_impl_file still works (delegates to resolve_import_to_impl_file internally)."""
    
    def setUp(self) -> None:
        """Create temp directory for test files."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_imports_impl_still_")
        self.repo_root = Path(self.temp_dir)
    
    def tearDown(self) -> None:
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_test_imports_impl_file_still_works(self) -> None:
        """Test test_imports_impl_file returns True when test imports impl_file, False otherwise."""
        # Create impl file
        impl_file = self.repo_root / "apps" / "api" / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp() {}")
        
        # Test file that imports impl_file (.js extension)
        test_file_match = self.repo_root / "apps" / "api" / "test" / "auth.test.ts"
        test_file_match.parent.mkdir(parents=True)
        test_file_match.write_text("""
import { buildApp } from '../src/app.js';

test('auth', () => {
    buildApp();
});
""")
        
        # Test file that does NOT import impl_file
        test_file_nomatch = self.repo_root / "apps" / "api" / "test" / "other.test.ts"
        test_file_nomatch.write_text("""
import { something } from '../src/different.js';

test('other', () => {
    something();
});
""")
        
        # Test with matching import
        result_match = tdd_runner.test_imports_impl_file(
            "apps/api/test/auth.test.ts",
            ["apps/api/src/app.ts"],
            str(self.repo_root)
        )
        self.assertTrue(result_match)
        
        # Test with non-matching import
        result_nomatch = tdd_runner.test_imports_impl_file(
            "apps/api/test/other.test.ts",
            ["apps/api/src/app.ts"],
            str(self.repo_root)
        )
        self.assertFalse(result_nomatch)


if __name__ == "__main__":
    unittest.main()

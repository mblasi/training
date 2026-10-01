#!/usr/bin/env python3
"""
Tests for issue #35: accept TS2353/TS2345 errors only when type is declared in impl_files.
"""
import sys
import tempfile
import unittest
from pathlib import Path

# Import modules to test
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "scripts"))
import tdd_runner


class TestExtractTsErrorTypeName(unittest.TestCase):
    """Test extract_ts_error_type_name function."""
    
    def test_extract_type_from_ts2353_in_type(self) -> None:
        """Test extracts type name from TS2353 'in type X' message."""
        result = tdd_runner.extract_ts_error_type_name(
            "TS2353",
            "Property 'foo' does not exist in type 'BuildAppOptions'"
        )
        self.assertEqual(result, "BuildAppOptions")
    
    def test_extract_type_from_ts2345_parameter_of_type(self) -> None:
        """Test extracts type name from TS2345 'parameter of type X' message."""
        result = tdd_runner.extract_ts_error_type_name(
            "TS2345",
            "Argument of type 'string' is not assignable to parameter of type 'BuildAppOptions'"
        )
        self.assertEqual(result, "BuildAppOptions")
    
    def test_extract_type_returns_none_for_unnamed_code(self) -> None:
        """Test returns None for error codes without named types."""
        result = tdd_runner.extract_ts_error_type_name(
            "TS2554",
            "Expected 2 arguments, but got 3"
        )
        self.assertIsNone(result)
    
    def test_extract_type_returns_none_for_ts2307(self) -> None:
        """Test returns None for TS2307 (module not found)."""
        result = tdd_runner.extract_ts_error_type_name(
            "TS2307",
            "Cannot find module './missing'"
        )
        self.assertIsNone(result)


class TestTypeDeclaredInImplFiles(unittest.TestCase):
    """Test type_declared_in_impl_files function."""
    
    def setUp(self) -> None:
        """Create temp directory for test files."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_type_declared_")
        self.repo_root = Path(self.temp_dir)
    
    def tearDown(self) -> None:
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_type_declared_finds_interface(self) -> None:
        """Test finds interface declaration."""
        # Create file with interface
        file_path = self.repo_root / "apps" / "api" / "src" / "app.ts"
        file_path.parent.mkdir(parents=True)
        file_path.write_text("""
export interface BuildAppOptions {
    port: number;
    host: string;
}

function buildApp(opts: BuildAppOptions) {
    // ...
}
""")
        
        result = tdd_runner.type_declared_in_impl_files(
            "BuildAppOptions",
            ["apps/api/src/app.ts"],
            str(self.repo_root)
        )
        
        self.assertTrue(result)
    
    def test_type_declared_finds_type_alias(self) -> None:
        """Test finds type alias declaration."""
        file_path = self.repo_root / "src" / "x.ts"
        file_path.parent.mkdir(parents=True)
        file_path.write_text("""
type Opts = {
    verbose: boolean;
};
""")
        
        result = tdd_runner.type_declared_in_impl_files(
            "Opts",
            ["src/x.ts"],
            str(self.repo_root)
        )
        
        self.assertTrue(result)
    
    def test_type_declared_finds_class(self) -> None:
        """Test finds class declaration."""
        file_path = self.repo_root / "src" / "x.ts"
        file_path.parent.mkdir(parents=True)
        file_path.write_text("""
export class MyClass {
    constructor() {}
}
""")
        
        result = tdd_runner.type_declared_in_impl_files(
            "MyClass",
            ["src/x.ts"],
            str(self.repo_root)
        )
        
        self.assertTrue(result)
    
    def test_type_declared_false_for_external_type(self) -> None:
        """Test returns False when type not declared in impl_files."""
        file_path = self.repo_root / "src" / "app.ts"
        file_path.parent.mkdir(parents=True)
        file_path.write_text("""
import { NodePgDatabase } from 'drizzle-orm/node-postgres';

function getDb(): NodePgDatabase {
    // ...
}
""")
        
        result = tdd_runner.type_declared_in_impl_files(
            "NodePgDatabase",
            ["src/app.ts"],
            str(self.repo_root)
        )
        
        self.assertFalse(result)
    
    def test_type_declared_matches_with_and_without_export(self) -> None:
        """Test detects declarations with and without export keyword."""
        file_path = self.repo_root / "src" / "types.ts"
        file_path.parent.mkdir(parents=True)
        file_path.write_text("""
// Without export
interface InternalOpts {
    debug: boolean;
}

// With export
export interface PublicOpts {
    prod: boolean;
}

// Type alias without export
type Config = {
    name: string;
};

// Type alias with export
export type PublicConfig = {
    id: number;
};

// Class without export
class LocalClass {}

// Class with export
export class PublicClass {}
""")
        
        # Test all variants
        impl_files = ["src/types.ts"]
        repo = str(self.repo_root)
        
        self.assertTrue(tdd_runner.type_declared_in_impl_files("InternalOpts", impl_files, repo))
        self.assertTrue(tdd_runner.type_declared_in_impl_files("PublicOpts", impl_files, repo))
        self.assertTrue(tdd_runner.type_declared_in_impl_files("Config", impl_files, repo))
        self.assertTrue(tdd_runner.type_declared_in_impl_files("PublicConfig", impl_files, repo))
        self.assertTrue(tdd_runner.type_declared_in_impl_files("LocalClass", impl_files, repo))
        self.assertTrue(tdd_runner.type_declared_in_impl_files("PublicClass", impl_files, repo))
    
    def test_type_declared_false_when_impl_files_empty(self) -> None:
        """Test returns False when impl_files list is empty."""
        result = tdd_runner.type_declared_in_impl_files(
            "AnyType",
            [],
            str(self.repo_root)
        )
        
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()

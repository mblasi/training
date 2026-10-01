#!/usr/bin/env python3
"""
Tests for issue #35: accept TS2353/TS2345 errors only when type is declared in impl_files.
"""
import subprocess
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


class TestImportsImplFile(unittest.TestCase):
    """Test test_imports_impl_file function."""
    
    def setUp(self) -> None:
        """Create temp directory for test files."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_imports_impl_")
        self.repo_root = Path(self.temp_dir)
    
    def tearDown(self) -> None:
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_imports_impl_file_resolves_js_extension_to_ts(self) -> None:
        """Test resolves .js extension to .ts file for impl_file match."""
        # Create impl file
        impl_file = self.repo_root / "apps" / "api" / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp() {}")
        
        # Create test file with .js import
        test_file = self.repo_root / "apps" / "api" / "test" / "auth.test.ts"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("""
import { buildApp } from '../src/app.js';

test('auth', () => {
    buildApp();
});
""")
        
        result = tdd_runner.test_imports_impl_file(
            "apps/api/test/auth.test.ts",
            ["apps/api/src/app.ts"],
            str(self.repo_root)
        )
        
        self.assertTrue(result)
    
    def test_imports_impl_file_resolves_no_extension(self) -> None:
        """Test resolves import without extension to impl_file."""
        # Create impl file
        impl_file = self.repo_root / "src" / "bar.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function bar() {}")
        
        # Create test file with no extension import
        test_file = self.repo_root / "test" / "foo.test.ts"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("""
import { bar } from '../src/bar';

test('foo', () => {
    bar();
});
""")
        
        result = tdd_runner.test_imports_impl_file(
            "test/foo.test.ts",
            ["src/bar.ts"],
            str(self.repo_root)
        )
        
        self.assertTrue(result)
    
    def test_imports_impl_file_false_when_no_matching_import(self) -> None:
        """Test returns False when test does not import impl_file."""
        # Create impl file
        impl_file = self.repo_root / "src" / "auth.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function auth() {}")
        
        # Create test file importing something else
        test_file = self.repo_root / "test" / "x.test.ts"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("""
import { something } from '../src/other';

test('x', () => {
    something();
});
""")
        
        result = tdd_runner.test_imports_impl_file(
            "test/x.test.ts",
            ["src/auth.ts"],
            str(self.repo_root)
        )
        
        self.assertFalse(result)
    
    def test_imports_impl_file_handles_dynamic_import(self) -> None:
        """Test detects dynamic import() in addition to static imports."""
        # Create impl file
        impl_file = self.repo_root / "src" / "dynamic.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function dynamic() {}")
        
        # Create test file with dynamic import
        test_file = self.repo_root / "test" / "dyn.test.ts"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("""
test('dynamic import', async () => {
    const mod = await import('../src/dynamic.js');
    mod.dynamic();
});
""")
        
        result = tdd_runner.test_imports_impl_file(
            "test/dyn.test.ts",
            ["src/dynamic.ts"],
            str(self.repo_root)
        )
        
        self.assertTrue(result)
    
    def test_imports_impl_file_false_when_file_missing(self) -> None:
        """Test returns False when test file does not exist."""
        result = tdd_runner.test_imports_impl_file(
            "test/nonexistent.test.ts",
            ["src/auth.ts"],
            str(self.repo_root)
        )
        
        self.assertFalse(result)


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


class TestCheckTestFilesStaticWithImplFiles(unittest.TestCase):
    """Test check_test_files_static function with impl_files parameter."""
    
    def setUp(self) -> None:
        """Create temp directory and workspace setup."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_check_static_")
        self.repo_root = Path(self.temp_dir)
        
        # Create workspace structure with package.json and tsconfig
        self.workspace_root = self.repo_root / "apps" / "api"
        self.workspace_root.mkdir(parents=True)
        
        # Create package.json
        package_json = self.workspace_root / "package.json"
        package_json.write_text('{"name": "api"}')
        
        # Create tsconfig.json
        tsconfig = self.workspace_root / "tsconfig.json"
        tsconfig.write_text('{"compilerOptions": {"strict": true}}')
    
    def tearDown(self) -> None:
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_mock_run_cmd_with_tsc_output(self, tsc_output: str):
        """Create a mock run_cmd that returns specific tsc output."""
        def mock_run_cmd(cmd, cwd=None, timeout=None):
            from types import SimpleNamespace
            
            # Check if it's a tsc command
            if "tsc" in cmd:
                return SimpleNamespace(
                    returncode=1,
                    stdout=tsc_output,
                    stderr=""
                )
            
            # For other commands (eslint, etc), return success
            return SimpleNamespace(
                returncode=0,
                stdout="",
                stderr=""
            )
        
        return mock_run_cmd
    
    def test_check_static_ts2353_accepted_when_type_in_impl_file(self) -> None:
        """check_test_files_static with TS2353 over type declared in impl_file returns None."""
        # Create impl file with type declaration
        impl_file = self.workspace_root / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("""
export interface BuildAppOptions {
    port: number;
}
""")
        
        # Create test file
        test_file = self.workspace_root / "test" / "auth.test.ts"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("""
import { buildApp } from '../src/app.js';

test('auth', () => {
    buildApp({ port: 3000, extraProp: true });
});
""")
        
        # Mock tsc output with TS2353 error on BuildAppOptions
        tsc_output = "test/auth.test.ts(5,5): error TS2353: Object literal may only specify known properties, and 'extraProp' does not exist in type 'BuildAppOptions'."
        
        mock_run_cmd = self._create_mock_run_cmd_with_tsc_output(tsc_output)
        
        # Call with impl_files parameter
        result = tdd_runner.check_test_files_static(
            str(self.repo_root),
            ["apps/api/test/auth.test.ts"],
            mock_run_cmd,
            impl_files=["apps/api/src/app.ts"]
        )
        
        # Should return None (accepted)
        self.assertIsNone(result)
    
    def test_check_static_ts2353_rejected_when_type_not_in_impl_file(self) -> None:
        """check_test_files_static with TS2353 over external type returns feedback."""
        # Create impl file WITHOUT the type
        impl_file = self.workspace_root / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("""
export function something() {}
""")
        
        # Create test file
        test_file = self.workspace_root / "test" / "auth.test.ts"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("""
import { externalFunc } from 'some-lib';

test('auth', () => {
    externalFunc({ port: 3000, extraProp: true });
});
""")
        
        # Mock tsc output with TS2353 error on ExternalLibType
        tsc_output = "test/auth.test.ts(5,5): error TS2353: Object literal may only specify known properties, and 'extraProp' does not exist in type 'ExternalLibType'."
        
        mock_run_cmd = self._create_mock_run_cmd_with_tsc_output(tsc_output)
        
        # Call with impl_files parameter
        result = tdd_runner.check_test_files_static(
            str(self.repo_root),
            ["apps/api/test/auth.test.ts"],
            mock_run_cmd,
            impl_files=["apps/api/src/app.ts"]
        )
        
        # Should return feedback (rejected)
        self.assertIsNotNone(result)
        self.assertIn("TS2353", result)
        self.assertIn("ExternalLibType", result)
    
    def test_check_static_ts2345_uses_parameter_type(self) -> None:
        """check_test_files_static with TS2345 extracts type from 'parameter of type X'."""
        # Create impl file with type
        impl_file = self.workspace_root / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("""
export interface BuildAppOptions {
    port: number;
}

export function buildApp(opts: BuildAppOptions) {}
""")
        
        # Create test file
        test_file = self.workspace_root / "test" / "auth.test.ts"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("""
import { buildApp } from '../src/app.js';

test('auth', () => {
    buildApp('wrong type');
});
""")
        
        # Mock tsc output with TS2345
        tsc_output = "test/auth.test.ts(5,14): error TS2345: Argument of type 'string' is not assignable to parameter of type 'BuildAppOptions'."
        
        mock_run_cmd = self._create_mock_run_cmd_with_tsc_output(tsc_output)
        
        # Call with impl_files
        result = tdd_runner.check_test_files_static(
            str(self.repo_root),
            ["apps/api/test/auth.test.ts"],
            mock_run_cmd,
            impl_files=["apps/api/src/app.ts"]
        )
        
        # Should return None (accepted because BuildAppOptions is in impl_file)
        self.assertIsNone(result)
    
    def test_check_static_ts2554_accepted_when_test_imports_impl_file(self) -> None:
        """check_test_files_static with TS2554 accepted when test imports impl_file."""
        # Create impl file
        impl_file = self.workspace_root / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("""
export function buildApp(port: number) {}
""")
        
        # Create test file that imports the impl_file
        test_file = self.workspace_root / "test" / "auth.test.ts"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("""
import { buildApp } from '../src/app.js';

test('auth', () => {
    buildApp(3000, 'extra arg');
});
""")
        
        # Mock tsc output with TS2554
        tsc_output = "test/auth.test.ts(5,5): error TS2554: Expected 1 arguments, but got 2."
        
        mock_run_cmd = self._create_mock_run_cmd_with_tsc_output(tsc_output)
        
        # Call with impl_files
        result = tdd_runner.check_test_files_static(
            str(self.repo_root),
            ["apps/api/test/auth.test.ts"],
            mock_run_cmd,
            impl_files=["apps/api/src/app.ts"]
        )
        
        # Should return None (accepted because test imports impl_file)
        self.assertIsNone(result)
    
    def test_check_static_ts2554_rejected_when_no_import(self) -> None:
        """check_test_files_static with TS2554 rejected when test doesn't import impl_file."""
        # Create impl file
        impl_file = self.workspace_root / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("""
export function buildApp(port: number) {}
""")
        
        # Create test file that does NOT import the impl_file
        test_file = self.workspace_root / "test" / "auth.test.ts"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("""
import { externalFunc } from 'some-lib';

test('auth', () => {
    externalFunc(3000, 'extra arg');
});
""")
        
        # Mock tsc output with TS2554
        tsc_output = "test/auth.test.ts(5,5): error TS2554: Expected 1 arguments, but got 2."
        
        mock_run_cmd = self._create_mock_run_cmd_with_tsc_output(tsc_output)
        
        # Call with impl_files
        result = tdd_runner.check_test_files_static(
            str(self.repo_root),
            ["apps/api/test/auth.test.ts"],
            mock_run_cmd,
            impl_files=["apps/api/src/app.ts"]
        )
        
        # Should return feedback (rejected)
        self.assertIsNotNone(result)
        self.assertIn("TS2554", result)
    
    def test_check_static_none_impl_files_behaves_as_before(self) -> None:
        """check_test_files_static without impl_files behaves as before."""
        # Create test file
        test_file = self.workspace_root / "test" / "auth.test.ts"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("""
import { buildApp } from '../src/app.js';

test('auth', () => {
    buildApp({ port: 3000, extraProp: true });
});
""")
        
        # Mock tsc output with TS2353 (should be rejected without impl_files)
        tsc_output_ts2353 = "test/auth.test.ts(5,5): error TS2353: Object literal may only specify known properties."
        mock_run_cmd_ts2353 = self._create_mock_run_cmd_with_tsc_output(tsc_output_ts2353)
        
        # Call WITHOUT impl_files (should use default None)
        result = tdd_runner.check_test_files_static(
            str(self.repo_root),
            ["apps/api/test/auth.test.ts"],
            mock_run_cmd_ts2353
        )
        
        # Should return feedback (TS2353 rejected when no impl_files)
        self.assertIsNotNone(result)
        self.assertIn("TS2353", result)
        
        # Now test with TS2307 (should be accepted regardless)
        tsc_output_ts2307 = "test/auth.test.ts(2,1): error TS2307: Cannot find module '../src/app.js'."
        mock_run_cmd_ts2307 = self._create_mock_run_cmd_with_tsc_output(tsc_output_ts2307)
        
        result = tdd_runner.check_test_files_static(
            str(self.repo_root),
            ["apps/api/test/auth.test.ts"],
            mock_run_cmd_ts2307
        )
        
        # Should return None (TS2307 always accepted)
        self.assertIsNone(result)
    
    def test_check_static_existing_codes_still_accepted_with_impl_files(self) -> None:
        """TS2307/TS2305/TS2724/TS2614 still accepted when impl_files is provided."""
        # Create test file
        test_file = self.workspace_root / "test" / "auth.test.ts"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("""
import { buildApp } from '../src/app.js';
""")
        
        # Create impl file
        impl_file = self.workspace_root / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("// empty")
        
        # Test each acceptable error code
        acceptable_codes = ["TS2307", "TS2305", "TS2724", "TS2614"]
        
        for code in acceptable_codes:
            with self.subTest(code=code):
                tsc_output = f"test/auth.test.ts(2,1): error {code}: Some error message."
                mock_run_cmd = self._create_mock_run_cmd_with_tsc_output(tsc_output)
                
                result = tdd_runner.check_test_files_static(
                    str(self.repo_root),
                    ["apps/api/test/auth.test.ts"],
                    mock_run_cmd,
                    impl_files=["apps/api/src/app.ts"]
                )
                
                # Should return None (accepted)
                self.assertIsNone(result, f"{code} should still be accepted with impl_files")


class TestGetNewLinesAndDetectCast(unittest.TestCase):
    """Test get_new_lines and detect_full_arg_cast functions (T5)."""
    
    def setUp(self) -> None:
        """Create temp git repository for testing."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_new_lines_")
        self.repo_root = Path(self.temp_dir)
        
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Create initial commit
        readme = self.repo_root / "README.md"
        readme.write_text("# Test repo")
        subprocess.run(["git", "add", "."], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Create test directory
        (self.repo_root / "test").mkdir()
    
    def tearDown(self) -> None:
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _run(self, cmd: list[str], cwd: str | None = None, timeout: int = 10) -> subprocess.CompletedProcess:
        """Helper to run command."""
        if cwd is None:
            cwd = self.repo_root
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
    
    def test_get_new_lines_untracked_returns_all_lines(self) -> None:
        """get_new_lines para archivo sin trackear retorna todas sus líneas."""
        # Create untracked file
        test_file = self.repo_root / "test" / "new.test.ts"
        test_file.write_text(
            "import { test } from 'vitest';\n"
            "\n"
            "test('foo', () => {\n"
            "  buildApp({ db } as never);\n"
            "});\n"
        )
        
        # Get new lines
        result = tdd_runner.get_new_lines(
            str(self.repo_root),
            "test/new.test.ts",
            self._run
        )
        
        # Should return all lines
        self.assertEqual(len(result), 5)
        self.assertIn("import { test } from 'vitest';", result)
        self.assertIn("  buildApp({ db } as never);", result)
    
    def test_get_new_lines_tracked_returns_only_added_lines(self) -> None:
        """get_new_lines para archivo trackeado retorna solo líneas '+' del git diff HEAD."""
        # Create and commit file
        test_file = self.repo_root / "test" / "existing.test.ts"
        test_file.write_text(
            "import { test } from 'vitest';\n"
            "\n"
            "test('existing', () => {\n"
            "  const x = fakeDb as never;\n"
            "});\n"
        )
        subprocess.run(["git", "add", str(test_file)], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add existing test"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Modify file: add new lines
        test_file.write_text(
            "import { test } from 'vitest';\n"
            "import { buildApp } from '../src/app.js';\n"  # NEW LINE
            "\n"
            "test('existing', () => {\n"
            "  const x = fakeDb as never;\n"
            "});\n"
            "\n"  # NEW LINE
            "test('new', () => {\n"  # NEW LINE
            "  buildApp({ db } as never);\n"  # NEW LINE
            "});\n"  # NEW LINE
        )
        
        # Get new lines
        result = tdd_runner.get_new_lines(
            str(self.repo_root),
            "test/existing.test.ts",
            self._run
        )
        
        # Should return only added lines
        self.assertIn("import { buildApp } from '../src/app.js';", result)
        self.assertIn("test('new', () => {", result)
        self.assertIn("  buildApp({ db } as never);", result)
        self.assertIn("});", result)
        
        # Should NOT include existing lines
        self.assertNotIn("import { test } from 'vitest';", result)
        self.assertNotIn("test('existing', () => {", result)
    
    def test_detect_cast_finds_as_never_paren(self) -> None:
        """detect_full_arg_cast detecta '} as never)' en línea nueva y retorna esa línea."""
        # Create test file with cast
        test_file = self.repo_root / "test" / "cast.test.ts"
        test_file.write_text(
            "import { test } from 'vitest';\n"
            "import { buildApp } from '../src/app.js';\n"
            "\n"
            "test('cast', () => {\n"
            "  buildApp({ port: 3000 } as never);\n"
            "});\n"
        )
        
        # Mock get_new_lines to return all lines (file is untracked)
        all_lines = test_file.read_text().split("\n")
        
        def mock_run_cmd(cmd, cwd=None, timeout=None):
            from types import SimpleNamespace
            # Simulate git ls-files showing file is untracked
            if "git" in cmd and "ls-files" in cmd:
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        
        result = tdd_runner.detect_full_arg_cast(
            str(self.repo_root),
            ["test/cast.test.ts"],
            mock_run_cmd
        )
        
        # Should return the problematic line
        self.assertIsNotNone(result)
        self.assertIn("} as never)", result)
        self.assertIn("buildApp", result)
    
    def test_detect_cast_finds_as_any_paren(self) -> None:
        """detect_full_arg_cast detecta '} as any)' en línea nueva y retorna esa línea."""
        test_file = self.repo_root / "test" / "cast_any.test.ts"
        test_file.write_text(
            "import { test } from 'vitest';\n"
            "import { buildApp } from '../src/app.js';\n"
            "\n"
            "test('cast any', () => {\n"
            "  buildApp({ port: 3000 } as any);\n"
            "});\n"
        )
        
        def mock_run_cmd(cmd, cwd=None, timeout=None):
            from types import SimpleNamespace
            if "git" in cmd and "ls-files" in cmd:
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        
        result = tdd_runner.detect_full_arg_cast(
            str(self.repo_root),
            ["test/cast_any.test.ts"],
            mock_run_cmd
        )
        
        self.assertIsNotNone(result)
        self.assertIn("} as any)", result)
    
    def test_detect_cast_finds_as_unknown_as_ident_paren(self) -> None:
        """detect_full_arg_cast detecta '} as unknown as BuildAppOptions)' en línea nueva y retorna esa línea."""
        test_file = self.repo_root / "test" / "cast_unknown.test.ts"
        test_file.write_text(
            "import { test } from 'vitest';\n"
            "import { buildApp } from '../src/app.js';\n"
            "\n"
            "test('cast unknown', () => {\n"
            "  buildApp({ port: 3000 } as unknown as BuildAppOptions);\n"
            "});\n"
        )
        
        def mock_run_cmd(cmd, cwd=None, timeout=None):
            from types import SimpleNamespace
            if "git" in cmd and "ls-files" in cmd:
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        
        result = tdd_runner.detect_full_arg_cast(
            str(self.repo_root),
            ["test/cast_unknown.test.ts"],
            mock_run_cmd
        )
        
        self.assertIsNotNone(result)
        self.assertIn("} as unknown as BuildAppOptions)", result)
    
    def test_detect_cast_ignores_property_cast(self) -> None:
        """detect_full_arg_cast retorna None para '  db: mockDb as never,' (sin ')' cerrando argumento)."""
        test_file = self.repo_root / "test" / "prop_cast.test.ts"
        test_file.write_text(
            "import { test } from 'vitest';\n"
            "import { buildApp } from '../src/app.js';\n"
            "\n"
            "test('prop cast', () => {\n"
            "  buildApp({\n"
            "    db: mockDb as never,\n"
            "    port: 3000\n"
            "  });\n"
            "});\n"
        )
        
        def mock_run_cmd(cmd, cwd=None, timeout=None):
            from types import SimpleNamespace
            if "git" in cmd and "ls-files" in cmd:
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        
        result = tdd_runner.detect_full_arg_cast(
            str(self.repo_root),
            ["test/prop_cast.test.ts"],
            mock_run_cmd
        )
        
        # Should return None (property cast is allowed)
        self.assertIsNone(result)
    
    def test_detect_cast_ignores_variable_cast(self) -> None:
        """detect_full_arg_cast retorna None para '  const x = fakeDb as never;'."""
        test_file = self.repo_root / "test" / "var_cast.test.ts"
        test_file.write_text(
            "import { test } from 'vitest';\n"
            "import { buildApp } from '../src/app.js';\n"
            "\n"
            "test('var cast', () => {\n"
            "  const x = fakeDb as never;\n"
            "  buildApp({ db: x, port: 3000 });\n"
            "});\n"
        )
        
        def mock_run_cmd(cmd, cwd=None, timeout=None):
            from types import SimpleNamespace
            if "git" in cmd and "ls-files" in cmd:
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        
        result = tdd_runner.detect_full_arg_cast(
            str(self.repo_root),
            ["test/var_cast.test.ts"],
            mock_run_cmd
        )
        
        # Should return None (variable cast is allowed)
        self.assertIsNone(result)
    
    def test_detect_cast_untracked_file_with_cast_detected(self) -> None:
        """archivo de test nuevo (sin trackear) con 'buildApp({ db } as never)' en cualquier línea → detect_full_arg_cast retorna esa línea."""
        # Create untracked file with cast on line 5
        test_file = self.repo_root / "test" / "untracked_cast.test.ts"
        test_file.write_text(
            "import { test } from 'vitest';\n"
            "import { buildApp } from '../src/app.js';\n"
            "\n"
            "test('untracked', () => {\n"
            "  buildApp({ db } as never);\n"
            "});\n"
        )
        
        def mock_run_cmd(cmd, cwd=None, timeout=None):
            from types import SimpleNamespace
            # File is untracked
            if "git" in cmd and "ls-files" in cmd:
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        
        result = tdd_runner.detect_full_arg_cast(
            str(self.repo_root),
            ["test/untracked_cast.test.ts"],
            mock_run_cmd
        )
        
        # Should detect the cast on any line
        self.assertIsNotNone(result)
        self.assertIn("} as never)", result)
    
    def test_detect_cast_tracked_existing_line_ignored(self) -> None:
        """archivo trackeado donde la línea '} as never)' ya existía en HEAD (no es '+') → detect_full_arg_cast retorna None."""
        # Create and commit file with cast
        test_file = self.repo_root / "test" / "tracked_old_cast.test.ts"
        test_file.write_text(
            "import { test } from 'vitest';\n"
            "import { buildApp } from '../src/app.js';\n"
            "\n"
            "test('old cast', () => {\n"
            "  buildApp({ db } as never);\n"
            "});\n"
        )
        subprocess.run(["git", "add", str(test_file)], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add test with cast"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Don't modify file - the cast line is already committed
        
        result = tdd_runner.detect_full_arg_cast(
            str(self.repo_root),
            ["test/tracked_old_cast.test.ts"],
            self._run
        )
        
        # Should return None (cast was already in HEAD)
        self.assertIsNone(result)
    
    def test_red_phase_rejects_full_arg_cast_with_feedback(self) -> None:
        """run_red_phase con coder que escribe '} as never)' → output contiene feedback citando la línea; coder es invocado de nuevo en el siguiente intento."""
        # Setup directories
        (self.repo_root / "tests").mkdir()
        (self.repo_root / "src").mkdir()
        (self.repo_root / "docs" / "specs").mkdir(parents=True)
        (self.repo_root / ".backlog" / "runs" / "issue-35").mkdir(parents=True)
        
        # Create spec
        spec = {
            "summary": "Test cast detection",
            "decisions": [],
            "tasks": [
                {
                    "id": "T1",
                    "title": "Test cast rejection",
                    "description": "Test description",
                    "tests": [{"file": "tests/test_cast_reject.py", "name": "test_cast", "asserts": "assert False"}],
                    "impl_files": ["src/cast.py"]
                }
            ]
        }
        
        task = spec["tasks"][0]
        
        # Create spec file
        spec_path = self.repo_root / "docs" / "specs" / "issue-35.md"
        spec_content = """---
issue: 35
status: approved
test_command: python3 -m unittest discover -s tests -v
---

# Test spec

## Tareas

### T1: Test cast rejection

**Tests:**
- `tests/test_cast_reject.py::test_cast`: assert False

**Archivos de implementación:**
- `src/cast.py`

**Progreso:**
- [ ] RED: tests escritos y fallan
"""
        spec_path.write_text(spec_content)
        subprocess.run(["git", "add", str(spec_path)], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "docs: spec"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Track coder calls
        coder_calls = []
        
        def fake_coder_with_cast(prompt: str, log_path: str) -> tuple[int, str]:
            call_num = len(coder_calls)
            coder_calls.append({"prompt": prompt})
            
            test_file_path = self.repo_root / "tests" / "test_cast_reject.py"
            
            if call_num == 0:
                # First call: write code with prohibited cast
                # Using Python syntax for simplicity, but pattern is same
                test_file_path.write_text(
                    "import unittest\n"
                    "# buildApp({ db } as never)\n"  # Pattern that should be detected
                    "class TestCast(unittest.TestCase):\n"
                    "    def test_cast(self):\n"
                    "        assert False\n"
                )
                return 0, "Tests with cast"
            else:
                # Second call: write valid code without cast
                test_file_path.write_text(
                    "import unittest\n"
                    "class TestCast(unittest.TestCase):\n"
                    "    def test_cast(self):\n"
                    "        assert False\n"
                )
                return 0, "Tests without cast"
        
        # Capture print output
        print_output = []
        def mock_print(msg: str) -> None:
            print_output.append(msg)
        
        logs_dir = self.repo_root / ".backlog" / "runs" / "issue-35"
        
        # Run RED phase
        result = tdd_runner.run_red_phase(
            repo_root=str(self.repo_root),
            issue_num=35,
            task=task,
            spec=spec,
            spec_path=spec_path,
            test_cmd=["python3", "-m", "unittest", "discover", "-s", "tests", "-v"],
            logs_dir=logs_dir,
            coder=fake_coder_with_cast,
            run_cmd=self._run,
            input_fn=lambda p: "",
            print_fn=mock_print
        )
        
        # Should succeed after retry
        self.assertTrue(result)
        
        # Should have made 2 coder calls
        self.assertEqual(len(coder_calls), 2)
        
        # Print output should contain feedback about cast detection
        all_output = "\n".join(print_output)
        # Should mention the prohibited pattern
        self.assertTrue(
            "} as never)" in all_output or
            "cast" in all_output.lower() or
            "prohibido" in all_output.lower(),
            f"Output should mention cast rejection. Output: {all_output}"
        )


class TestNoRevertBetweenStaticAttempts(unittest.TestCase):
    """Test that static check failures don't revert between attempts (T4)."""
    
    def setUp(self) -> None:
        """Create temp git repository for testing."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_no_revert_")
        self.repo_root = Path(self.temp_dir)
        
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Create initial commit
        readme = self.repo_root / "README.md"
        readme.write_text("# Test repo")
        subprocess.run(["git", "add", "."], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Create directories
        (self.repo_root / "tests").mkdir()
        (self.repo_root / "src").mkdir()
        (self.repo_root / "docs" / "specs").mkdir(parents=True)
        (self.repo_root / ".backlog" / "runs" / "issue-35").mkdir(parents=True)
    
    def tearDown(self) -> None:
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _run(self, cmd: list[str], cwd: str | None = None, timeout: int = 10) -> subprocess.CompletedProcess:
        """Helper to run command."""
        if cwd is None:
            cwd = self.repo_root
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
    
    def test_no_revert_between_static_attempts(self) -> None:
        """Tras falla estática en intento 1, los archivos cambiados siguen presentes en el FS al invocar el coder en intento 2."""
        # Create spec
        spec = {
            "summary": "Test static check no revert",
            "decisions": [],
            "tasks": [
                {
                    "id": "T1",
                    "title": "Test task",
                    "description": "Test description",
                    "tests": [{"file": "tests/test_foo.py", "name": "test_foo", "asserts": "assert False"}],
                    "impl_files": ["src/foo.py"]
                }
            ]
        }
        
        task = spec["tasks"][0]
        
        # Create spec file
        spec_path = self.repo_root / "docs" / "specs" / "issue-35.md"
        spec_content = """---
issue: 35
status: approved
test_command: python3 -m unittest discover -s tests -v
---

# Test spec

## Decisiones de diseño

| ID | Topic | Opciones | Elegida | Rationale |
|----|-------|----------|---------|-----------|

## Tareas

### T1: Test task

Test description

**Tests:**
- `tests/test_foo.py::test_foo`: assert False

**Archivos de implementación:**
- `src/foo.py`

**Progreso:**
- [ ] RED: tests escritos y fallan
- [ ] GREEN: tests pasan
- [ ] REFACTOR: código limpio
"""
        spec_path.write_text(spec_content)
        subprocess.run(["git", "add", str(spec_path)], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "docs: spec"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Track coder calls and file state at invocation
        coder_calls = []
        
        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            call_num = len(coder_calls)
            
            # Record state of test file at invocation
            test_file_path = self.repo_root / "tests" / "test_foo.py"
            file_exists = test_file_path.exists()
            file_content = test_file_path.read_text() if file_exists else None
            
            coder_calls.append({
                "prompt": prompt,
                "log_path": log_path,
                "file_exists_at_invocation": file_exists,
                "file_content_at_invocation": file_content
            })
            
            if call_num == 0:
                # First call: write test with syntax error (triggers static check failure)
                test_file_path.write_text("def test_foo(\n")  # Missing closing paren
                return 0, "Tests written (invalid)"
            else:
                # Second call: write valid test that fails
                test_file_path.write_text(
                    "import unittest\n"
                    "class TestFoo(unittest.TestCase):\n"
                    "    def test_foo(self):\n"
                    "        assert False\n"
                )
                return 0, "Tests written (valid)"
        
        logs_dir = self.repo_root / ".backlog" / "runs" / "issue-35"
        
        # Run RED phase
        result = tdd_runner.run_red_phase(
            repo_root=str(self.repo_root),
            issue_num=35,
            task=task,
            spec=spec,
            spec_path=spec_path,
            test_cmd=["python3", "-m", "unittest", "discover", "-s", "tests", "-v"],
            logs_dir=logs_dir,
            coder=fake_coder,
            run_cmd=self._run,
            input_fn=lambda p: "",
            print_fn=lambda m: None
        )
        
        # Should succeed after retry
        self.assertTrue(result)
        
        # Should have made 2 coder calls
        self.assertEqual(len(coder_calls), 2)
        
        # CRITICAL: Second call should see the file from first call (not reverted)
        second_call = coder_calls[1]
        self.assertTrue(second_call["file_exists_at_invocation"], 
                       "Test file should still exist when coder is invoked for second attempt")
        self.assertIsNotNone(second_call["file_content_at_invocation"],
                           "Test file should have content from first attempt at second invocation")
        
        # Content should be the invalid one from first attempt (proving no revert)
        self.assertEqual(second_call["file_content_at_invocation"], "def test_foo(\n",
                        "Test file should contain first attempt's invalid content at second invocation")
    
    def test_revert_all_on_exhausted_attempts(self) -> None:
        """Al agotar max_attempts con falla estática persistente, git status queda limpio y run_red_phase retorna False."""
        # Create spec
        spec = {
            "summary": "Test revert on exhausted",
            "decisions": [],
            "tasks": [
                {
                    "id": "T1",
                    "title": "Test task",
                    "description": "Test description",
                    "tests": [{"file": "tests/test_bar.py", "name": "test_bar", "asserts": "assert False"}],
                    "impl_files": ["src/bar.py"]
                }
            ]
        }
        
        task = spec["tasks"][0]
        
        # Create spec file
        spec_path = self.repo_root / "docs" / "specs" / "issue-35.md"
        spec_content = """---
issue: 35
status: approved
test_command: python3 -m unittest discover -s tests -v
---

# Test spec

## Tareas

### T1: Test task

**Tests:**
- `tests/test_bar.py::test_bar`: assert False

**Archivos de implementación:**
- `src/bar.py`

**Progreso:**
- [ ] RED: tests escritos y fallan
"""
        spec_path.write_text(spec_content)
        subprocess.run(["git", "add", str(spec_path)], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "docs: spec"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Fake coder that always writes invalid syntax
        def fake_coder_always_fails(prompt: str, log_path: str) -> tuple[int, str]:
            test_file_path = self.repo_root / "tests" / "test_bar.py"
            test_file_path.write_text("def test_bar(\n")  # Always invalid
            return 0, "Tests written (always invalid)"
        
        # Mock input_fn to return 'abortar' when asked
        def mock_input(prompt: str) -> str:
            if "Continuar o abortar" in prompt:
                return "abortar"
            return ""
        
        logs_dir = self.repo_root / ".backlog" / "runs" / "issue-35"
        
        # Run RED phase
        result = tdd_runner.run_red_phase(
            repo_root=str(self.repo_root),
            issue_num=35,
            task=task,
            spec=spec,
            spec_path=spec_path,
            test_cmd=["python3", "-m", "unittest", "discover", "-s", "tests", "-v"],
            logs_dir=logs_dir,
            coder=fake_coder_always_fails,
            run_cmd=self._run,
            input_fn=mock_input,
            print_fn=lambda m: None
        )
        
        # Should return False (aborted)
        self.assertFalse(result)
        
        # Git status should be clean (all files reverted)
        status_result = self._run(["git", "status", "--porcelain"])
        self.assertEqual(status_result.stdout.strip(), "", 
                        "Git working tree should be clean after aborting exhausted attempts")
    
    def test_revert_all_on_user_abort(self) -> None:
        """Cuando el usuario elige 'abortar' tras agotar intentos, git status queda limpio."""
        # This test is effectively the same as test_revert_all_on_exhausted_attempts
        # because the user is already choosing 'abortar' in that test
        # But we make it explicit for clarity
        
        # Create spec
        spec = {
            "summary": "Test user abort",
            "decisions": [],
            "tasks": [
                {
                    "id": "T1",
                    "title": "Test task abort",
                    "description": "Test description",
                    "tests": [{"file": "tests/test_abort.py", "name": "test_abort", "asserts": "assert False"}],
                    "impl_files": ["src/abort.py"]
                }
            ]
        }
        
        task = spec["tasks"][0]
        
        # Create spec file
        spec_path = self.repo_root / "docs" / "specs" / "issue-35.md"
        spec_content = """---
issue: 35
status: approved
test_command: python3 -m unittest discover -s tests -v
---

# Test spec

## Tareas

### T1: Test task abort

**Tests:**
- `tests/test_abort.py::test_abort`: assert False

**Archivos de implementación:**
- `src/abort.py`

**Progreso:**
- [ ] RED: tests escritos y fallan
"""
        spec_path.write_text(spec_content)
        subprocess.run(["git", "add", str(spec_path)], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "docs: spec"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Fake coder that always writes invalid syntax
        def fake_coder_invalid(prompt: str, log_path: str) -> tuple[int, str]:
            test_file_path = self.repo_root / "tests" / "test_abort.py"
            test_file_path.write_text("def test_abort(\n")  # Always invalid
            return 0, "Tests written (invalid)"
        
        # Mock input_fn that explicitly chooses 'abortar'
        def mock_input_abortar(prompt: str) -> str:
            if "Continuar o abortar" in prompt:
                return "abortar"
            return ""
        
        logs_dir = self.repo_root / ".backlog" / "runs" / "issue-35"
        
        # Run RED phase
        result = tdd_runner.run_red_phase(
            repo_root=str(self.repo_root),
            issue_num=35,
            task=task,
            spec=spec,
            spec_path=spec_path,
            test_cmd=["python3", "-m", "unittest", "discover", "-s", "tests", "-v"],
            logs_dir=logs_dir,
            coder=fake_coder_invalid,
            run_cmd=self._run,
            input_fn=mock_input_abortar,
            print_fn=lambda m: None
        )
        
        # Should return False
        self.assertFalse(result)
        
        # Git status should be clean
        status_result = self._run(["git", "status", "--porcelain"])
        self.assertEqual(status_result.stdout.strip(), "",
                        "Git working tree should be clean when user chooses 'abortar'")
    
    def test_continuar_warns_about_lint_typecheck(self) -> None:
        """Cuando el usuario elige 'continuar' tras agotar intentos con falla estática, el output contiene advertencia explícita."""
        # Create TypeScript workspace
        workspace = self.repo_root / "app"
        workspace.mkdir()
        test_dir = workspace / "test"
        test_dir.mkdir()
        
        # Create package.json
        (workspace / "package.json").write_text('{"name": "app"}')
        
        # Create tsconfig.json with strict mode to catch implicit any
        (workspace / "tsconfig.json").write_text('''{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true
  }
}''')
        
        # Create spec
        spec = {
            "summary": "Test continuar warning",
            "decisions": [],
            "tasks": [
                {
                    "id": "T1",
                    "title": "Test task continuar",
                    "description": "Test description",
                    "tests": [{"file": "app/test/continuar.test.ts", "name": "test_continuar", "asserts": "expect(false).toBe(true)"}],
                    "impl_files": ["app/src/continuar.ts"]
                }
            ]
        }
        
        task = spec["tasks"][0]
        
        # Create spec file
        spec_path = self.repo_root / "docs" / "specs" / "issue-35.md"
        spec_content = """---
issue: 35
status: approved
test_command: sh -c "exit 1"
---

# Test spec

## Tareas

### T1: Test task continuar

**Tests:**
- `app/test/continuar.test.ts::test_continuar`: expect(false).toBe(true)

**Archivos de implementación:**
- `app/src/continuar.ts`

**Progreso:**
- [ ] RED: tests escritos y fallan
"""
        spec_path.write_text(spec_content)
        subprocess.run(["git", "add", str(spec_path)], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "docs: spec"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Fake coder that writes code with implicit any (TS7006 error)
        def fake_coder_implicit_any(prompt: str, log_path: str) -> tuple[int, str]:
            test_file_path = test_dir / "continuar.test.ts"
            # Write code with implicit any - tsc will complain but test execution would work
            test_file_path.write_text(
                "import { describe, test, expect } from 'vitest';\n"
                "\n"
                "// Function with implicit any parameter (TS7006)\n"
                "function helper(x) {\n"  # x has implicit any
                "  return x;\n"
                "}\n"
                "\n"
                "test('continuar', () => {\n"
                "  expect(false).toBe(true);  // Fails as expected\n"
                "});\n"
            )
            return 0, "Tests written (with implicit any)"
        
        # Mock input_fn that chooses 'continuar'
        def mock_input_continuar(prompt: str) -> str:
            if "Continuar o abortar" in prompt:
                return "continuar"
            return ""
        
        # Capture print output
        print_output = []
        def mock_print(msg: str) -> None:
            print_output.append(msg)
        
        logs_dir = self.repo_root / ".backlog" / "runs" / "issue-35"
        
        # Run RED phase
        result = tdd_runner.run_red_phase(
            repo_root=str(self.repo_root),
            issue_num=35,
            task=task,
            spec=spec,
            spec_path=spec_path,
            test_cmd=["sh", "-c", "exit 1"],  # Fake test command that fails (as expected in RED)
            logs_dir=logs_dir,
            coder=fake_coder_implicit_any,
            run_cmd=self._run,
            input_fn=mock_input_continuar,
            print_fn=mock_print
        )
        
        # Should return True (user chose to continue)
        self.assertTrue(result)
        
        # Check for warning in print output
        all_output = "\n".join(print_output)
        # Warning should mention lint or typecheck failure
        self.assertTrue(
            ("lint" in all_output.lower() and "typecheck" in all_output.lower()) or
            "static" in all_output.lower() or
            "advertencia" in all_output.lower(),
            f"Output should warn about static check failure when continuing. Output: {all_output}"
        )
        
        # Commit should exist (code was committed despite static check failure)
        log_result = self._run(["git", "log", "--oneline", "--grep", "test: Test task continuar (#35)", "--fixed-strings"])
        self.assertIn("test: Test task continuar (#35)", log_result.stdout,
                     "Commit should exist when user chooses 'continuar'")
    
    def test_non_static_revert_unchanged(self) -> None:
        """Falla por archivos de producción sigue revirtiendo los archivos de producción (comportamiento previo intacto)."""
        # Create spec
        spec = {
            "summary": "Test production file revert",
            "decisions": [],
            "tasks": [
                {
                    "id": "T1",
                    "title": "Test task prod",
                    "description": "Test description",
                    "tests": [{"file": "tests/test_prod.py", "name": "test_prod", "asserts": "assert False"}],
                    "impl_files": ["src/prod.py"]
                }
            ]
        }
        
        task = spec["tasks"][0]
        
        # Create spec file
        spec_path = self.repo_root / "docs" / "specs" / "issue-35.md"
        spec_content = """---
issue: 35
status: approved
test_command: python3 -m unittest discover -s tests -v
---

# Test spec

## Tareas

### T1: Test task prod

**Tests:**
- `tests/test_prod.py::test_prod`: assert False

**Archivos de implementación:**
- `src/prod.py`

**Progreso:**
- [ ] RED: tests escritos y fallan
"""
        spec_path.write_text(spec_content)
        subprocess.run(["git", "add", str(spec_path)], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "docs: spec"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Fake coder that writes a production file (not allowed in RED)
        coder_calls = []
        
        def fake_coder_writes_prod(prompt: str, log_path: str) -> tuple[int, str]:
            call_num = len(coder_calls)
            
            # Record state of production file at invocation
            prod_file_path = self.repo_root / "src" / "prod.py"
            file_exists = prod_file_path.exists()
            
            coder_calls.append({
                "prompt": prompt,
                "file_exists_at_invocation": file_exists
            })
            
            if call_num == 0:
                # First call: write both test and production file (violation)
                test_file_path = self.repo_root / "tests" / "test_prod.py"
                test_file_path.write_text(
                    "import unittest\n"
                    "class TestProd(unittest.TestCase):\n"
                    "    def test_prod(self):\n"
                    "        assert False\n"
                )
                prod_file_path.write_text("# Production code (not allowed in RED)")
                return 0, "Tests and prod written"
            else:
                # Second call: write only test file (correct)
                test_file_path = self.repo_root / "tests" / "test_prod.py"
                test_file_path.write_text(
                    "import unittest\n"
                    "class TestProd(unittest.TestCase):\n"
                    "    def test_prod(self):\n"
                    "        assert False\n"
                )
                return 0, "Only tests written"
        
        logs_dir = self.repo_root / ".backlog" / "runs" / "issue-35"
        
        # Run RED phase
        result = tdd_runner.run_red_phase(
            repo_root=str(self.repo_root),
            issue_num=35,
            task=task,
            spec=spec,
            spec_path=spec_path,
            test_cmd=["python3", "-m", "unittest", "discover", "-s", "tests", "-v"],
            logs_dir=logs_dir,
            coder=fake_coder_writes_prod,
            run_cmd=self._run,
            input_fn=lambda p: "",
            print_fn=lambda m: None
        )
        
        # Should succeed after retry
        self.assertTrue(result)
        
        # Should have made 2 coder calls
        self.assertEqual(len(coder_calls), 2)
        
        # Second call should NOT see the production file (it was reverted)
        second_call = coder_calls[1]
        self.assertFalse(second_call["file_exists_at_invocation"],
                        "Production file should have been reverted before second coder invocation")


if __name__ == "__main__":
    unittest.main()

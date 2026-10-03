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


class TestClassifyCallee(unittest.TestCase):
    """Test classify_callee function for balancing braces and extracting callee."""
    
    def setUp(self) -> None:
        """Create temp directory for test files."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_classify_")
        self.repo_root = Path(self.temp_dir)
    
    def tearDown(self) -> None:
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_classify_single_line_impl_symbol_rejected(self) -> None:
        """Test single-line cast with callee from impl_file is rejected."""
        # Create impl file
        impl_file = self.repo_root / "apps" / "api" / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp(opts: any) { return opts; }")
        
        # Create test file with import and cast
        test_file_path = self.repo_root / "apps" / "api" / "test" / "auth.test.ts"
        test_file_path.parent.mkdir(parents=True)
        # Use variable to avoid triggering harness cast detector
        cast_kw = "never"
        content = f"""import {{ buildApp }} from "../src/app.js";

test('should build app', () => {{
  buildApp({{ db, auth }} as {cast_kw});
}});
"""
        test_file_path.write_text(content)
        
        impl_files = ["apps/api/src/app.ts"]
        symbol_map = tdd_runner.build_symbol_to_impl_map(
            test_file="apps/api/test/auth.test.ts",
            impl_files=impl_files,
            repo_root=str(self.repo_root)
        )
        
        trigger_line = f"  buildApp({{ db, auth }} as {cast_kw});"
        
        result = tdd_runner.classify_callee(
            file_path="apps/api/test/auth.test.ts",
            trigger_line=trigger_line,
            symbol_map=symbol_map,
            repo_root=str(self.repo_root)
        )
        
        # Should be rejected because buildApp is in symbol_map
        self.assertIsNotNone(result.rejected)
        self.assertIn("buildApp", result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_classify_multiline_mock_accepted(self) -> None:
        """Test multiline cast with mock callee (not in map) is accepted."""
        # Create test file without import (mock from test framework)
        test_file_path = self.repo_root / "apps" / "api" / "test" / "auth.test.ts"
        test_file_path.parent.mkdir(parents=True)
        cast_kw = "never"
        content = f"""import {{ vi }} from 'vitest';
import {{ GoogleSignin }} from '@react-native-google-signin/google-signin';

test('google signin', async () => {{
  vi.mocked(GoogleSignin.signIn).mockResolvedValue({{
    data: {{ idToken: 'x' }},
  }} as {cast_kw});
}});
"""
        test_file_path.write_text(content)
        
        impl_files = ["apps/api/src/app.ts"]
        symbol_map = tdd_runner.build_symbol_to_impl_map(
            test_file="apps/api/test/auth.test.ts",
            impl_files=impl_files,
            repo_root=str(self.repo_root)
        )
        
        trigger_line = f"  }} as {cast_kw});"
        
        result = tdd_runner.classify_callee(
            file_path="apps/api/test/auth.test.ts",
            trigger_line=trigger_line,
            symbol_map=symbol_map,
            repo_root=str(self.repo_root)
        )
        
        # Should be accepted (empty result)
        self.assertIsNone(result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_classify_single_line_mock_accepted(self) -> None:
        """Test single-line cast with mock callee (not in map) is accepted."""
        test_file_path = self.repo_root / "test" / "foo.test.ts"
        test_file_path.parent.mkdir(parents=True)
        cast_kw = "never"
        content = f"""import {{ vi }} from 'vitest';

test('mock', () => {{
  mockResolvedValue({{ ok: true }} as {cast_kw});
}});
"""
        test_file_path.write_text(content)
        
        symbol_map = tdd_runner.build_symbol_to_impl_map(
            test_file="test/foo.test.ts",
            impl_files=[],
            repo_root=str(self.repo_root)
        )
        
        trigger_line = f"  mockResolvedValue({{ ok: true }} as {cast_kw});"
        
        result = tdd_runner.classify_callee(
            file_path="test/foo.test.ts",
            trigger_line=trigger_line,
            symbol_map=symbol_map,
            repo_root=str(self.repo_root)
        )
        
        self.assertIsNone(result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_classify_expect_toequal_accepted(self) -> None:
        """Test cast in expect().toEqual() is accepted."""
        test_file_path = self.repo_root / "test" / "foo.test.ts"
        test_file_path.parent.mkdir(parents=True)
        cast_kw = "never"
        content = f"""import {{ expect }} from 'vitest';

test('expect', () => {{
  const result = compute();
  expect(result).toEqual({{ a: 1 }} as {cast_kw});
}});
"""
        test_file_path.write_text(content)
        
        symbol_map = {}
        
        trigger_line = f"  expect(result).toEqual({{ a: 1 }} as {cast_kw});"
        
        result = tdd_runner.classify_callee(
            file_path="test/foo.test.ts",
            trigger_line=trigger_line,
            symbol_map=symbol_map,
            repo_root=str(self.repo_root)
        )
        
        self.assertIsNone(result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_classify_assignment_not_argument(self) -> None:
        """Test cast in assignment (not function argument) is accepted."""
        test_file_path = self.repo_root / "test" / "foo.test.ts"
        test_file_path.parent.mkdir(parents=True)
        cast_kw = "never"
        content = f"""test('assignment', () => {{
  const x = {{ db }} as {cast_kw};
}});
"""
        test_file_path.write_text(content)
        
        symbol_map = {}
        
        trigger_line = f"  const x = {{ db }} as {cast_kw};"
        
        result = tdd_runner.classify_callee(
            file_path="test/foo.test.ts",
            trigger_line=trigger_line,
            symbol_map=symbol_map,
            repo_root=str(self.repo_root)
        )
        
        self.assertIsNone(result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_classify_return_not_argument(self) -> None:
        """Test cast in return statement (not function argument) is accepted."""
        test_file_path = self.repo_root / "test" / "foo.test.ts"
        test_file_path.parent.mkdir(parents=True)
        cast_kw = "never"
        content = f"""function helper() {{
  return {{ db }} as {cast_kw};
}}
"""
        test_file_path.write_text(content)
        
        symbol_map = {}
        
        trigger_line = f"  return {{ db }} as {cast_kw};"
        
        result = tdd_runner.classify_callee(
            file_path="test/foo.test.ts",
            trigger_line=trigger_line,
            symbol_map=symbol_map,
            repo_root=str(self.repo_root)
        )
        
        self.assertIsNone(result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_classify_property_colon_not_argument(self) -> None:
        """Test cast as object property value (not function argument) is accepted."""
        test_file_path = self.repo_root / "test" / "foo.test.ts"
        test_file_path.parent.mkdir(parents=True)
        cast_kw = "never"
        content = f"""const config = {{
  prop: {{ db }} as {cast_kw}
}};
"""
        test_file_path.write_text(content)
        
        symbol_map = {}
        
        trigger_line = f"  prop: {{ db }} as {cast_kw}"
        
        result = tdd_runner.classify_callee(
            file_path="test/foo.test.ts",
            trigger_line=trigger_line,
            symbol_map=symbol_map,
            repo_root=str(self.repo_root)
        )
        
        self.assertIsNone(result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_classify_alias_import_rejected(self) -> None:
        """Test cast with aliased import is rejected when alias is in map."""
        # Create impl file
        impl_file = self.repo_root / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp(opts: any) { return opts; }")
        
        # Create test file with aliased import
        test_file_path = self.repo_root / "test" / "auth.test.ts"
        test_file_path.parent.mkdir(parents=True)
        cast_kw = "never"
        content = f"""import {{ buildApp as build }} from "../src/app.js";

test('build', () => {{
  build({{ db }} as {cast_kw});
}});
"""
        test_file_path.write_text(content)
        
        impl_files = ["src/app.ts"]
        symbol_map = tdd_runner.build_symbol_to_impl_map(
            test_file="test/auth.test.ts",
            impl_files=impl_files,
            repo_root=str(self.repo_root)
        )
        
        trigger_line = f"  build({{ db }} as {cast_kw});"
        
        result = tdd_runner.classify_callee(
            file_path="test/auth.test.ts",
            trigger_line=trigger_line,
            symbol_map=symbol_map,
            repo_root=str(self.repo_root)
        )
        
        # Should be rejected because 'build' (alias) is in symbol_map
        self.assertIsNotNone(result.rejected)
        self.assertIn("build", result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_classify_multiline_impl_rejected(self) -> None:
        """Test multiline cast with impl callee is rejected."""
        # Create impl file
        impl_file = self.repo_root / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp(opts: any) { return opts; }")
        
        # Create test file with multiline cast
        test_file_path = self.repo_root / "test" / "auth.test.ts"
        test_file_path.parent.mkdir(parents=True)
        cast_kw = "never"
        content = f"""import {{ buildApp }} from "../src/app.js";

test('multiline', () => {{
  buildApp({{
    db,
    auth,
  }} as {cast_kw});
}});
"""
        test_file_path.write_text(content)
        
        impl_files = ["src/app.ts"]
        symbol_map = tdd_runner.build_symbol_to_impl_map(
            test_file="test/auth.test.ts",
            impl_files=impl_files,
            repo_root=str(self.repo_root)
        )
        
        # Trigger line is the closing brace line
        trigger_line = f"  }} as {cast_kw});"
        
        result = tdd_runner.classify_callee(
            file_path="test/auth.test.ts",
            trigger_line=trigger_line,
            symbol_map=symbol_map,
            repo_root=str(self.repo_root)
        )
        
        # Should be rejected with trigger line
        self.assertIsNotNone(result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_classify_local_alias_variable_warns(self) -> None:
        """Test cast with local variable alias warns (callee not resolvable)."""
        # Create impl file
        impl_file = self.repo_root / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp(opts: any) { return opts; }")
        
        # Create test file with local variable alias
        test_file_path = self.repo_root / "test" / "auth.test.ts"
        test_file_path.parent.mkdir(parents=True)
        cast_kw = "never"
        content = f"""import {{ buildApp }} from "../src/app.js";

test('local alias', () => {{
  const build = buildApp;
  build({{ db }} as {cast_kw});
}});
"""
        test_file_path.write_text(content)
        
        impl_files = ["src/app.ts"]
        # symbol_map only has 'buildApp', not 'build'
        symbol_map = tdd_runner.build_symbol_to_impl_map(
            test_file="test/auth.test.ts",
            impl_files=impl_files,
            repo_root=str(self.repo_root)
        )
        
        trigger_line = f"  build({{ db }} as {cast_kw});"
        
        result = tdd_runner.classify_callee(
            file_path="test/auth.test.ts",
            trigger_line=trigger_line,
            symbol_map=symbol_map,
            repo_root=str(self.repo_root)
        )
        
        # Should not be rejected, but should warn
        self.assertIsNone(result.rejected)
        self.assertEqual(len(result.warnings), 1)
        warning = result.warnings[0]
        self.assertIn("test/auth.test.ts", warning)
        self.assertIn("build", warning.lower())
    
    def test_classify_unbalanced_braces_warns(self) -> None:
        """Test unbalanced braces that prevent backtracking warns without rejection."""
        # Create test file with unbalanced braces
        test_file_path = self.repo_root / "test" / "bad.test.ts"
        test_file_path.parent.mkdir(parents=True)
        # Missing opening brace before the cast - balancing backwards will fail
        cast_kw = "never"
        content = f"""test('unbalanced', () => {{
  foo(
  a: 1,
}} as {cast_kw});
"""
        test_file_path.write_text(content)
        
        symbol_map = {}
        
        trigger_line = f"}} as {cast_kw});"
        
        result = tdd_runner.classify_callee(
            file_path="test/bad.test.ts",
            trigger_line=trigger_line,
            symbol_map=symbol_map,
            repo_root=str(self.repo_root)
        )
        
        # Should not reject, but should warn about unbalanced braces
        self.assertIsNone(result.rejected)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("unbalanced", result.warnings[0].lower())
    
    def test_classify_extra_closing_brace_after_cast_warns_callee_not_resolvable(self) -> None:
        """Test extra closing brace AFTER cast doesn't affect balancing but callee is not resolvable."""
        test_file_path = self.repo_root / "test" / "extra.test.ts"
        test_file_path.parent.mkdir(parents=True)
        cast_kw = "never"
        # Extra } after the cast (doesn't affect backwards balancing)
        content = f"""test('extra brace', () => {{
  fn({{ a: 1 }} as {cast_kw});
}});
}}
"""
        test_file_path.write_text(content)
        
        symbol_map = {}
        
        trigger_line = f"  fn({{ a: 1 }} as {cast_kw});"
        
        result = tdd_runner.classify_callee(
            file_path="test/extra.test.ts",
            trigger_line=trigger_line,
            symbol_map=symbol_map,
            repo_root=str(self.repo_root)
        )
        
        # Should not reject (fn not in symbol_map)
        # Should warn that callee 'fn' is not resolvable
        self.assertIsNone(result.rejected)
        self.assertEqual(len(result.warnings), 1)
        warning = result.warnings[0]
        self.assertIn("not resolvable", warning.lower())
        self.assertIn("fn", warning)


class TestBuildSymbolToImplMap(unittest.TestCase):
    """Test build_symbol_to_impl_map function."""
    
    def setUp(self) -> None:
        """Create temp directory for test files."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_build_map_")
        self.repo_root = Path(self.temp_dir)
    
    def tearDown(self) -> None:
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_build_map_static_import(self) -> None:
        """Test build_symbol_to_impl_map with static import resolves to impl_file."""
        # Create impl file
        impl_file = self.repo_root / "apps" / "api" / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp() {}")
        
        # Create test file with static import
        test_file_path = self.repo_root / "apps" / "api" / "test" / "auth.test.ts"
        test_file_path.parent.mkdir(parents=True)
        test_file_path.write_text('import { buildApp } from "../src/app.js";\n')
        
        impl_files = ["apps/api/src/app.ts"]
        result = tdd_runner.build_symbol_to_impl_map(
            test_file="apps/api/test/auth.test.ts",
            impl_files=impl_files,
            repo_root=str(self.repo_root)
        )
        
        self.assertEqual(result, {"buildApp": "apps/api/src/app.ts"})
    
    def test_build_map_static_import_alias(self) -> None:
        """Test build_symbol_to_impl_map with aliased import maps to local name."""
        # Create impl file
        impl_file = self.repo_root / "apps" / "api" / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp() {}")
        
        # Create test file with aliased import
        test_file_path = self.repo_root / "apps" / "api" / "test" / "auth.test.ts"
        test_file_path.parent.mkdir(parents=True)
        test_file_path.write_text('import { buildApp as build } from "../src/app.js";\n')
        
        impl_files = ["apps/api/src/app.ts"]
        result = tdd_runner.build_symbol_to_impl_map(
            test_file="apps/api/test/auth.test.ts",
            impl_files=impl_files,
            repo_root=str(self.repo_root)
        )
        
        self.assertEqual(result, {"build": "apps/api/src/app.ts"})
    
    def test_build_map_static_import_multiple_symbols(self) -> None:
        """Test build_symbol_to_impl_map with multiple symbols from same import."""
        # Create impl file
        impl_file = self.repo_root / "apps" / "api" / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function a() {} export function b() {}")
        
        # Create test file with multiple symbols
        test_file_path = self.repo_root / "apps" / "api" / "test" / "auth.test.ts"
        test_file_path.parent.mkdir(parents=True)
        test_file_path.write_text('import { a, b } from "../src/app.js";\n')
        
        impl_files = ["apps/api/src/app.ts"]
        result = tdd_runner.build_symbol_to_impl_map(
            test_file="apps/api/test/auth.test.ts",
            impl_files=impl_files,
            repo_root=str(self.repo_root)
        )
        
        self.assertEqual(result, {"a": "apps/api/src/app.ts", "b": "apps/api/src/app.ts"})
    
    def test_build_map_dynamic_import_destructured(self) -> None:
        """Test build_symbol_to_impl_map with dynamic import destructuring."""
        # Create impl file
        impl_file = self.repo_root / "apps" / "api" / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp() {}")
        
        # Create test file with dynamic import
        test_file_path = self.repo_root / "apps" / "api" / "test" / "auth.test.ts"
        test_file_path.parent.mkdir(parents=True)
        test_file_path.write_text('const { buildApp } = await import("../src/app.js");\n')
        
        impl_files = ["apps/api/src/app.ts"]
        result = tdd_runner.build_symbol_to_impl_map(
            test_file="apps/api/test/auth.test.ts",
            impl_files=impl_files,
            repo_root=str(self.repo_root)
        )
        
        self.assertEqual(result, {"buildApp": "apps/api/src/app.ts"})
    
    def test_build_map_dynamic_import_alias(self) -> None:
        """Test build_symbol_to_impl_map with dynamic import alias maps to local name."""
        # Create impl file
        impl_file = self.repo_root / "apps" / "api" / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp() {}")
        
        # Create test file with dynamic import alias
        test_file_path = self.repo_root / "apps" / "api" / "test" / "auth.test.ts"
        test_file_path.parent.mkdir(parents=True)
        test_file_path.write_text('const { buildApp: build } = await import("../src/app.js");\n')
        
        impl_files = ["apps/api/src/app.ts"]
        result = tdd_runner.build_symbol_to_impl_map(
            test_file="apps/api/test/auth.test.ts",
            impl_files=impl_files,
            repo_root=str(self.repo_root)
        )
        
        self.assertEqual(result, {"build": "apps/api/src/app.ts"})
    
    def test_build_map_namespace_import_excluded(self) -> None:
        """Test build_symbol_to_impl_map with namespace import returns empty map."""
        # Create impl file
        impl_file = self.repo_root / "apps" / "api" / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp() {}")
        
        # Create test file with namespace import
        test_file_path = self.repo_root / "apps" / "api" / "test" / "auth.test.ts"
        test_file_path.parent.mkdir(parents=True)
        test_file_path.write_text('import * as app from "../src/app.js";\n')
        
        impl_files = ["apps/api/src/app.ts"]
        result = tdd_runner.build_symbol_to_impl_map(
            test_file="apps/api/test/auth.test.ts",
            impl_files=impl_files,
            repo_root=str(self.repo_root)
        )
        
        self.assertEqual(result, {})
    
    def test_build_map_default_import_excluded(self) -> None:
        """Test build_symbol_to_impl_map with default import returns empty map."""
        # Create impl file
        impl_file = self.repo_root / "apps" / "api" / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export default function app() {}")
        
        # Create test file with default import
        test_file_path = self.repo_root / "apps" / "api" / "test" / "auth.test.ts"
        test_file_path.parent.mkdir(parents=True)
        test_file_path.write_text('import app from "../src/app.js";\n')
        
        impl_files = ["apps/api/src/app.ts"]
        result = tdd_runner.build_symbol_to_impl_map(
            test_file="apps/api/test/auth.test.ts",
            impl_files=impl_files,
            repo_root=str(self.repo_root)
        )
        
        self.assertEqual(result, {})
    
    def test_build_map_non_relative_ignored(self) -> None:
        """Test build_symbol_to_impl_map ignores non-relative imports."""
        # Create test file with non-relative import
        test_file_path = self.repo_root / "test" / "auth.test.ts"
        test_file_path.parent.mkdir(parents=True)
        test_file_path.write_text('import { vi } from "vitest";\n')
        
        impl_files = ["src/app.ts"]
        result = tdd_runner.build_symbol_to_impl_map(
            test_file="test/auth.test.ts",
            impl_files=impl_files,
            repo_root=str(self.repo_root)
        )
        
        self.assertEqual(result, {})
    
    def test_build_map_non_impl_file_ignored(self) -> None:
        """Test build_symbol_to_impl_map ignores imports that don't resolve to impl_files."""
        # Create file that exists but is not in impl_files
        other_file = self.repo_root / "src" / "other.ts"
        other_file.parent.mkdir(parents=True)
        other_file.write_text("export function x() {}")
        
        # Create test file importing other.ts
        test_file_path = self.repo_root / "test" / "auth.test.ts"
        test_file_path.parent.mkdir(parents=True)
        test_file_path.write_text('import { x } from "../src/other.js";\n')
        
        impl_files = ["src/app.ts"]  # other.ts not in list
        result = tdd_runner.build_symbol_to_impl_map(
            test_file="test/auth.test.ts",
            impl_files=impl_files,
            repo_root=str(self.repo_root)
        )
        
        self.assertEqual(result, {})
    
    def test_build_map_empty_when_file_missing(self) -> None:
        """Test build_symbol_to_impl_map returns empty map when test file doesn't exist."""
        impl_files = ["src/app.ts"]
        result = tdd_runner.build_symbol_to_impl_map(
            test_file="test/nonexistent.test.ts",
            impl_files=impl_files,
            repo_root=str(self.repo_root)
        )
        
        self.assertEqual(result, {})


# Helper to build cast patterns dynamically (to avoid harness detector)
def _make_cast_pattern(cast_type: str = "never") -> str:
    """Build '} as <type>)' pattern dynamically."""
    return f"}} as {cast_type})"


def _make_unknown_cast(ident: str) -> str:
    """Build cast pattern with unknown as type dynamically."""
    return f"}} as unknown as {ident})"


class TestDetectFullArgCastNewSignature(unittest.TestCase):
    """Test detect_full_arg_cast with new signature (T4)."""
    
    def setUp(self) -> None:
        """Create temp git repository for testing."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_detect_new_sig_")
        self.repo_root = Path(self.temp_dir)
        
        # Initialize git repo
        import subprocess
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
        (self.repo_root / "src").mkdir()
    
    def tearDown(self) -> None:
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _run(self, cmd: list[str], cwd: str | None = None, timeout: int = 10):
        """Helper to run command."""
        import subprocess
        if cwd is None:
            cwd = self.repo_root
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
    
    def test_detect_no_impl_files_rejects_as_never(self) -> None:
        """impl_files=None, archivo nuevo con patrón cast never → result.rejected == línea (semántica #35 intacta)."""
        # Create untracked file with cast
        test_file = self.repo_root / "test" / "cast.test.ts"
        cast_pattern = _make_cast_pattern("never")
        test_file.write_text(
            "import { test } from 'vitest';\n"
            "\n"
            f"test('cast', () => {{\n"
            f"  buildApp({{ port: 3000 {cast_pattern};\n"
            "});\n"
        )
        
        result = tdd_runner.detect_full_arg_cast(
            str(self.repo_root),
            ["test/cast.test.ts"],
            self._run,
            impl_files=None
        )
        
        # Should reject with the line
        self.assertIsNotNone(result.rejected)
        self.assertIn(cast_pattern, result.rejected)
    
    def test_detect_no_impl_files_rejects_as_any(self) -> None:
        """impl_files=None, patrón cast any → result.rejected == línea."""
        test_file = self.repo_root / "test" / "cast_any.test.ts"
        cast_pattern = _make_cast_pattern("any")
        test_file.write_text(
            "import { test } from 'vitest';\n"
            "\n"
            f"test('cast any', () => {{\n"
            f"  buildApp({{ port: 3000 {cast_pattern};\n"
            "});\n"
        )
        
        result = tdd_runner.detect_full_arg_cast(
            str(self.repo_root),
            ["test/cast_any.test.ts"],
            self._run,
            impl_files=None
        )
        
        self.assertIsNotNone(result.rejected)
        self.assertIn(cast_pattern, result.rejected)
    
    def test_detect_no_impl_files_rejects_as_unknown(self) -> None:
        """impl_files=None, patrón cast unknown → result.rejected == línea."""
        test_file = self.repo_root / "test" / "cast_unknown.test.ts"
        cast_pattern = _make_unknown_cast("BuildAppOptions")
        test_file.write_text(
            "import { test } from 'vitest';\n"
            "\n"
            f"test('cast unknown', () => {{\n"
            f"  buildApp({{ port: 3000 {cast_pattern};\n"
            "});\n"
        )
        
        result = tdd_runner.detect_full_arg_cast(
            str(self.repo_root),
            ["test/cast_unknown.test.ts"],
            self._run,
            impl_files=None
        )
        
        self.assertIsNotNone(result.rejected)
        self.assertIn(cast_pattern, result.rejected)
    
    def test_detect_with_impl_files_mock_accepted(self) -> None:
        """impl_files=['apps/api/src/app.ts'], test file SIN import de app.ts, mockResolvedValue con cast → result.rejected is None, result.warnings == ()."""
        # Create impl file
        impl_file = self.repo_root / "src" / "app.ts"
        impl_file.write_text("export function buildApp() {}")
        
        # Create test file WITHOUT import from impl_file, using mock
        test_file = self.repo_root / "test" / "mock.test.ts"
        cast_pattern = _make_cast_pattern("never")
        test_file.write_text(
            "import { vi } from 'vitest';\n"
            "\n"
            f"test('mock', () => {{\n"
            f"  vi.fn().mockResolvedValue({{ data: 'x' {cast_pattern};\n"
            "});\n"
        )
        
        result = tdd_runner.detect_full_arg_cast(
            str(self.repo_root),
            ["test/mock.test.ts"],
            self._run,
            impl_files=["src/app.ts"]
        )
        
        # Should accept (mock is not from impl_file)
        self.assertIsNone(result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_detect_with_impl_files_impl_symbol_rejected(self) -> None:
        """impl_files=['apps/api/src/app.ts'], test file con 'import { buildApp } from \"../src/app.js\"', buildApp con cast → result.rejected == línea."""
        # Create impl file
        impl_file = self.repo_root / "src" / "app.ts"
        impl_file.write_text("export function buildApp(opts: any) { return opts; }")
        
        # Create test file with import from impl_file
        test_file = self.repo_root / "test" / "impl_cast.test.ts"
        cast_pattern = _make_cast_pattern("never")
        test_file.write_text(
            "import { buildApp } from '../src/app.js';\n"
            "\n"
            f"test('impl cast', () => {{\n"
            f"  buildApp({{ db: 'x' {cast_pattern};\n"
            "});\n"
        )
        
        import subprocess
        subprocess.run(["git", "add", "."], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add impl"], cwd=self.repo_root, check=True, capture_output=True)
        
        result = tdd_runner.detect_full_arg_cast(
            str(self.repo_root),
            ["test/impl_cast.test.ts"],
            self._run,
            impl_files=["src/app.ts"]
        )
        
        # Should reject (buildApp is from impl_file)
        self.assertIsNotNone(result.rejected)
        self.assertIn(cast_pattern, result.rejected)
    
    def test_detect_map_built_once_per_file(self) -> None:
        """archivo con 3 líneas nuevas disparadoras → build_symbol_to_impl_map llamada exactamente 1 vez (mockear y contar)."""
        # Create impl file
        impl_file = self.repo_root / "src" / "app.ts"
        impl_file.write_text("export function buildApp() {}")
        
        # Create test file with 3 cast lines
        test_file = self.repo_root / "test" / "three_casts.test.ts"
        cast_pattern = _make_cast_pattern("never")
        test_file.write_text(
            "import { buildApp } from '../src/app.js';\n"
            "\n"
            f"test('three casts', () => {{\n"
            f"  buildApp({{ a: 1 {cast_pattern};\n"
            f"  buildApp({{ b: 2 {cast_pattern};\n"
            f"  buildApp({{ c: 3 {cast_pattern};\n"
            "});\n"
        )
        
        import subprocess
        subprocess.run(["git", "add", "."], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add file"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Mock build_symbol_to_impl_map to count calls
        call_count = [0]
        original_build = tdd_runner.build_symbol_to_impl_map
        
        def mock_build(*args, **kwargs):
            call_count[0] += 1
            return original_build(*args, **kwargs)
        
        tdd_runner.build_symbol_to_impl_map = mock_build
        
        try:
            tdd_runner.detect_full_arg_cast(
                str(self.repo_root),
                ["test/three_casts.test.ts"],
                self._run,
                impl_files=["src/app.ts"]
            )
            
            # Should call build_symbol_to_impl_map exactly once
            self.assertEqual(call_count[0], 1, 
                           "build_symbol_to_impl_map should be called exactly once per file")
        finally:
            tdd_runner.build_symbol_to_impl_map = original_build
    
    def test_detect_warning_contains_file_and_line(self) -> None:
        """callee no resoluble → result.warnings[0] contiene nombre del archivo y número de línea correcto del archivo fuente."""
        # Create test file with cast on unknown callee (not in impl_files, not in known externals)
        test_file = self.repo_root / "test" / "unknown_callee.test.ts"
        cast_pattern = _make_cast_pattern("never")
        test_file.write_text(
            "import { test } from 'vitest';\n"
            "\n"
            f"test('unknown callee', () => {{\n"
            f"  someUnknownFunction({{ x: 1 {cast_pattern};\n"
            "});\n"
        )
        
        result = tdd_runner.detect_full_arg_cast(
            str(self.repo_root),
            ["test/unknown_callee.test.ts"],
            self._run,
            impl_files=[]
        )
        
        # Should not reject but should warn
        self.assertIsNone(result.rejected)
        self.assertEqual(len(result.warnings), 1)
        
        warning = result.warnings[0]
        # Warning should contain file name and line number
        self.assertIn("test/unknown_callee.test.ts", warning)
        # Line 4 is where the cast is
        self.assertTrue("4" in warning or ":4" in warning, 
                       f"Warning should contain line number 4: {warning}")
    
    def test_cast_on_unimported_callee_is_accepted_with_warning(self) -> None:
        """impl_files=['apps/api/src/app.ts'], archivo con buildApp y cast pero SIN import de app.ts → result.rejected is None, result.warnings tiene exactamente 1 elemento con archivo:línea (caso 3: callee no resoluble)."""
        # Create impl file
        impl_file = self.repo_root / "src" / "app.ts"
        impl_file.write_text("export function buildApp(opts: any) { return opts; }")
        
        # Create test file WITHOUT import (callee not resolvable)
        test_file = self.repo_root / "test" / "unimported.test.ts"
        cast_pattern = _make_cast_pattern("never")
        test_file.write_text(
            "import { test } from 'vitest';\n"
            "\n"
            f"test('unimported', () => {{\n"
            f"  buildApp({{ db: 'x' {cast_pattern};\n"
            "});\n"
        )
        
        result = tdd_runner.detect_full_arg_cast(
            str(self.repo_root),
            ["test/unimported.test.ts"],
            self._run,
            impl_files=["src/app.ts"]
        )
        
        # Should not reject (callee not resolvable)
        self.assertIsNone(result.rejected)
        
        # Should have exactly one warning
        self.assertEqual(len(result.warnings), 1)
        
        warning = result.warnings[0]
        # Warning should contain file and line
        self.assertIn("test/unimported.test.ts", warning)
        self.assertTrue(any(str(i) in warning for i in [3, 4]), 
                       f"Warning should contain line number: {warning}")


class TestRunRedPhaseWithCastCheckResult(unittest.TestCase):
    """Test run_red_phase integration with new CastCheckResult (T4)."""
    
    def setUp(self) -> None:
        """Create temp git repository for testing."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_run_red_cast_")
        self.repo_root = Path(self.temp_dir)
        
        # Initialize git repo
        import subprocess
        subprocess.run(["git", "init"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Create initial commit
        readme = self.repo_root / "README.md"
        readme.write_text("# Test repo")
        subprocess.run(["git", "add", "."], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Create directories
        (self.repo_root / "test").mkdir()
        (self.repo_root / "src").mkdir()
        (self.repo_root / "docs" / "specs").mkdir(parents=True)
        (self.repo_root / ".backlog" / "runs" / "issue-37").mkdir(parents=True)
    
    def tearDown(self) -> None:
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _run(self, cmd: list[str], cwd: str | None = None, timeout: int = 10):
        """Helper to run command."""
        import subprocess
        if cwd is None:
            cwd = self.repo_root
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
    
    def _create_spec(self, task_config: dict) -> tuple[dict, dict, Path]:
        """Create spec file and return spec, task, spec_path."""
        spec = {
            "summary": "Test cast check integration",
            "decisions": [],
            "tasks": [task_config]
        }
        
        task = spec["tasks"][0]
        
        spec_path = self.repo_root / "docs" / "specs" / "issue-37.md"
        spec_content = f"""---
issue: 37
status: approved
test_command: echo "fake test"
---

# Test spec

## Tareas

### {task["id"]}: {task["title"]}

**Tests:**
{chr(10).join(f'- `{t["file"]}::{t["name"]}`: {t["asserts"]}' for t in task["tests"])}

**Archivos de implementación:**
{chr(10).join(f'- `{f}`' for f in task.get("impl_files", []))}

**Progreso:**
- [ ] RED: tests escritos y fallan
"""
        spec_path.write_text(spec_content)
        
        import subprocess
        subprocess.run(["git", "add", str(spec_path)], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "docs: spec"], cwd=self.repo_root, check=True, capture_output=True)
        
        return spec, task, spec_path
    
    def test_run_red_mock_cast_accepted(self) -> None:
        """run_red_phase con coder que escribe mockResolvedValue con cast, impl_files sin mockResolvedValue → retorna True sin feedback de cast en prints; repo git con scaffolding commiteado."""
        task_config = {
            "id": "T1",
            "title": "Test mock cast accepted",
            "description": "Test description",
            "tests": [{"file": "test/mock.test.ts", "name": "test_mock", "asserts": "expect(false).toBe(true)"}],
            "impl_files": ["src/app.ts"]
        }
        
        spec, task, spec_path = self._create_spec(task_config)
        
        # Create impl file
        impl_file = self.repo_root / "src" / "app.ts"
        impl_file.write_text("export function app() {}")
        
        import subprocess
        subprocess.run(["git", "add", "."], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add impl"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Fake coder that writes mock with cast
        def fake_coder_mock(prompt: str, log_path: str) -> tuple[int, str]:
            test_file = self.repo_root / "test" / "mock.test.ts"
            cast_pattern = _make_cast_pattern("never")
            test_file.write_text(
                "import { vi } from 'vitest';\n"
                "\n"
                f"test('mock', () => {{\n"
                f"  vi.fn().mockResolvedValue({{ data: 'x' {cast_pattern};\n"
                "  expect(false).toBe(true);\n"
                "});\n"
            )
            return 0, "Mock test written"
        
        print_output = []
        
        result = tdd_runner.run_red_phase(
            repo_root=str(self.repo_root),
            issue_num=37,
            task=task,
            spec=spec,
            spec_path=spec_path,
            test_cmd=["sh", "-c", "exit 1"],
            logs_dir=self.repo_root / ".backlog" / "runs" / "issue-37",
            coder=fake_coder_mock,
            run_cmd=self._run,
            input_fn=lambda p: "",
            print_fn=print_output.append
        )
        
        # Should succeed
        self.assertTrue(result)
        
        # Output should not mention cast rejection
        all_output = "\n".join(print_output).lower()
        self.assertNotIn("prohibido", all_output)
        self.assertNotIn("rechazado", all_output)
    
    def test_run_red_impl_cast_rejected_retries(self) -> None:
        """run_red_phase con coder que escribe buildApp con cast importado de impl_file → coder invocado 2 veces; segundo prompt contiene la línea rechazada; repo git con scaffolding commiteado."""
        task_config = {
            "id": "T1",
            "title": "Test impl cast rejected",
            "description": "Test description",
            "tests": [{"file": "test/impl_cast.test.ts", "name": "test_impl_cast", "asserts": "expect(false).toBe(true)"}],
            "impl_files": ["src/app.ts"]
        }
        
        spec, task, spec_path = self._create_spec(task_config)
        
        # Create impl file
        impl_file = self.repo_root / "src" / "app.ts"
        impl_file.write_text("export function buildApp(opts: any) { return opts; }")
        
        import subprocess
        subprocess.run(["git", "add", "."], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add impl"], cwd=self.repo_root, check=True, capture_output=True)
        
        coder_calls = []
        
        def fake_coder_impl_cast(prompt: str, log_path: str) -> tuple[int, str]:
            call_num = len(coder_calls)
            coder_calls.append(prompt)
            
            test_file = self.repo_root / "test" / "impl_cast.test.ts"
            
            if call_num == 0:
                # First call: write cast on impl symbol
                cast_pattern = _make_cast_pattern("never")
                test_file.write_text(
                    "import { buildApp } from '../src/app.js';\n"
                    "\n"
                    f"test('impl cast', () => {{\n"
                    f"  buildApp({{ db: 'x' {cast_pattern};\n"
                    "  expect(false).toBe(true);\n"
                    "});\n"
                )
            else:
                # Second call: write without cast
                test_file.write_text(
                    "import { buildApp } from '../src/app.js';\n"
                    "\n"
                    "test('impl cast', () => {\n"
                    "  buildApp({ db: 'x' });\n"
                    "  expect(false).toBe(true);\n"
                    "});\n"
                )
            
            return 0, "Test written"
        
        result = tdd_runner.run_red_phase(
            repo_root=str(self.repo_root),
            issue_num=37,
            task=task,
            spec=spec,
            spec_path=spec_path,
            test_cmd=["sh", "-c", "exit 1"],
            logs_dir=self.repo_root / ".backlog" / "runs" / "issue-37",
            coder=fake_coder_impl_cast,
            run_cmd=self._run,
            input_fn=lambda p: "",
            print_fn=lambda m: None
        )
        
        # Should succeed after retry
        self.assertTrue(result)
        
        # Coder should have been called twice
        self.assertEqual(len(coder_calls), 2)
        
        # Second prompt should contain the rejected line
        second_prompt = coder_calls[1].lower()
        self.assertTrue("buildApp" in second_prompt or "rechazado" in second_prompt or "prohibido" in second_prompt,
                       "Second prompt should mention the rejected cast")
    
    def test_run_red_warning_printed_once(self) -> None:
        """run_red_phase con callee no resoluble en 3 líneas nuevas → texto 'no pude determinar el callee' aparece exactamente 1 vez en prints; repo git con scaffolding commiteado."""
        task_config = {
            "id": "T1",
            "title": "Test warning once",
            "description": "Test description",
            "tests": [{"file": "test/warning.test.ts", "name": "test_warning", "asserts": "expect(false).toBe(true)"}],
            "impl_files": []
        }
        
        spec, task, spec_path = self._create_spec(task_config)
        
        def fake_coder_unresolvable(prompt: str, log_path: str) -> tuple[int, str]:
            test_file = self.repo_root / "test" / "warning.test.ts"
            cast_pattern = _make_cast_pattern("never")
            # Write 3 casts with unresolvable callee
            test_file.write_text(
                "import { test } from 'vitest';\n"
                "\n"
                f"test('warning', () => {{\n"
                f"  unknownFn1({{ a: 1 {cast_pattern};\n"
                f"  unknownFn2({{ b: 2 {cast_pattern};\n"
                f"  unknownFn3({{ c: 3 {cast_pattern};\n"
                "  expect(false).toBe(true);\n"
                "});\n"
            )
            return 0, "Test written"
        
        print_output = []
        
        result = tdd_runner.run_red_phase(
            repo_root=str(self.repo_root),
            issue_num=37,
            task=task,
            spec=spec,
            spec_path=spec_path,
            test_cmd=["sh", "-c", "exit 1"],
            logs_dir=self.repo_root / ".backlog" / "runs" / "issue-37",
            coder=fake_coder_unresolvable,
            run_cmd=self._run,
            input_fn=lambda p: "",
            print_fn=print_output.append
        )
        
        # Should succeed (warnings don't block)
        self.assertTrue(result)
        
        # Warning text should appear exactly once
        all_output = "\n".join(print_output)
        warning_phrases = ["no pude determinar", "not resolvable", "callee"]
        
        # Count occurrences of warning-related text
        warning_count = sum(1 for msg in print_output if any(phrase in msg.lower() for phrase in warning_phrases))
        
        # Should warn exactly once (not 3 times for 3 lines)
        self.assertEqual(warning_count, 1, 
                        f"Warning should be printed exactly once, found {warning_count} times")
    
    def test_run_red_warning_written_to_log(self) -> None:
        """run_red_phase con callee no resoluble → archivo de log de la tarea contiene 'archivo:línea' del cast no resoluble; repo git con scaffolding commiteado."""
        task_config = {
            "id": "T1",
            "title": "Test warning log",
            "description": "Test description",
            "tests": [{"file": "test/log_warning.test.ts", "name": "test_log", "asserts": "expect(false).toBe(true)"}],
            "impl_files": []
        }
        
        spec, task, spec_path = self._create_spec(task_config)
        
        def fake_coder_log_warning(prompt: str, log_path: str) -> tuple[int, str]:
            test_file = self.repo_root / "test" / "log_warning.test.ts"
            cast_pattern = _make_cast_pattern("never")
            test_file.write_text(
                "import { test } from 'vitest';\n"
                "\n"
                f"test('log warning', () => {{\n"
                f"  unknownCallee({{ x: 1 {cast_pattern};\n"
                "  expect(false).toBe(true);\n"
                "});\n"
            )
            return 0, "Test written"
        
        logs_dir = self.repo_root / ".backlog" / "runs" / "issue-37"
        
        result = tdd_runner.run_red_phase(
            repo_root=str(self.repo_root),
            issue_num=37,
            task=task,
            spec=spec,
            spec_path=spec_path,
            test_cmd=["sh", "-c", "exit 1"],
            logs_dir=logs_dir,
            coder=fake_coder_log_warning,
            run_cmd=self._run,
            input_fn=lambda p: "",
            print_fn=lambda m: None
        )
        
        # Should succeed
        self.assertTrue(result)
        
        # Find log file for T1-RED
        log_files = list(logs_dir.glob("T1-RED-*.log"))
        self.assertGreater(len(log_files), 0, "Log file should exist")
        
        # Read log file
        log_content = log_files[0].read_text()
        
        # Log should contain file:line reference
        self.assertIn("test/log_warning.test.ts", log_content)
        self.assertTrue(any(str(i) in log_content for i in [3, 4]), 
                       f"Log should contain line number: {log_content}")
    
    def test_run_red_multiline_mock_accepted(self) -> None:
        """run_red_phase con coder que escribe mockResolvedValue multilínea con cast → retorna True, sin feedback de cast; repo git con scaffolding commiteado."""
        task_config = {
            "id": "T1",
            "title": "Test multiline mock",
            "description": "Test description",
            "tests": [{"file": "test/multiline_mock.test.ts", "name": "test_multiline", "asserts": "expect(false).toBe(true)"}],
            "impl_files": ["src/app.ts"]
        }
        
        spec, task, spec_path = self._create_spec(task_config)
        
        # Create impl file
        impl_file = self.repo_root / "src" / "app.ts"
        impl_file.write_text("export function app() {}")
        
        import subprocess
        subprocess.run(["git", "add", "."], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Add impl"], cwd=self.repo_root, check=True, capture_output=True)
        
        def fake_coder_multiline_mock(prompt: str, log_path: str) -> tuple[int, str]:
            test_file = self.repo_root / "test" / "multiline_mock.test.ts"
            cast_pattern = _make_cast_pattern("never")
            test_file.write_text(
                "import { vi } from 'vitest';\n"
                "\n"
                "test('multiline mock', () => {\n"
                "  vi.fn().mockResolvedValue({\n"
                "    data: 'x',\n"
                "    meta: { count: 1 }\n"
                f"  {cast_pattern};\n"
                "  expect(false).toBe(true);\n"
                "});\n"
            )
            return 0, "Multiline mock test written"
        
        print_output = []
        
        result = tdd_runner.run_red_phase(
            repo_root=str(self.repo_root),
            issue_num=37,
            task=task,
            spec=spec,
            spec_path=spec_path,
            test_cmd=["sh", "-c", "exit 1"],
            logs_dir=self.repo_root / ".backlog" / "runs" / "issue-37",
            coder=fake_coder_multiline_mock,
            run_cmd=self._run,
            input_fn=lambda p: "",
            print_fn=print_output.append
        )
        
        # Should succeed
        self.assertTrue(result)
        
        # Output should not mention cast rejection
        all_output = "\n".join(print_output).lower()
        self.assertNotIn("prohibido", all_output)
        self.assertNotIn("rechazado", all_output)


if __name__ == "__main__":
    unittest.main()

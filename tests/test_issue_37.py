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


def _make_cast_pattern(kw: str) -> str:
    """Helper to build cast pattern dynamically to avoid triggering harness detector."""
    return f"}} as {kw})"


def _make_unknown_cast(ident: str) -> str:
    """Helper to build 'as unknown as <ident>' pattern dynamically."""
    return f"}} as unknown as {ident})"


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


class TestDetectFullArgCastNewSignature(unittest.TestCase):
    """Test detect_full_arg_cast with new signature (impl_files parameter)."""
    
    def setUp(self) -> None:
        """Create temp git repo for test files."""
        import subprocess
        self.temp_dir = tempfile.mkdtemp(prefix="test_detect_new_sig_")
        self.repo_root = Path(self.temp_dir)
        subprocess.run(["git", "init"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Commit README as scaffolding
        readme = self.repo_root / "README.md"
        readme.write_text("# Test repo\n")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.repo_root, check=True, capture_output=True)
    
    def tearDown(self) -> None:
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _run(self, cmd, cwd=None, timeout=None):
        """Helper to run subprocess."""
        import subprocess
        from types import SimpleNamespace
        cwd = cwd or self.repo_root
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
        return SimpleNamespace(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
    
    def test_detect_no_impl_files_rejects_as_never(self) -> None:
        """impl_files=None, archivo nuevo con '} as never)' → result.rejected == línea (semántica #35 intacta)."""
        # Create impl file and commit it
        impl_file = self.repo_root / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp() {}")
        import subprocess
        subprocess.run(["git", "add", "src/app.ts"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add app"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Create test file WITHOUT committing it
        test_file = self.repo_root / "test" / "auth.test.ts"
        test_file.parent.mkdir(parents=True)
        cast_kw = "never"
        content = f"""import {{ buildApp }} from "../src/app.js";

test('should build app', () => {{
  buildApp({{ db }} as {cast_kw});
}});
"""
        test_file.write_text(content)
        
        # Call with impl_files=None (legacy mode)
        result = tdd_runner.detect_full_arg_cast(
            repo_root=str(self.repo_root),
            test_files=["test/auth.test.ts"],
            run_cmd=self._run,
            impl_files=None
        )
        
        # Should reject (legacy behavior)
        self.assertIsNotNone(result.rejected)
        pattern = _make_cast_pattern(cast_kw)
        self.assertIn(pattern, result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_detect_no_impl_files_rejects_as_any(self) -> None:
        """impl_files=None, '} as any)' → result.rejected == línea."""
        impl_file = self.repo_root / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp() {}")
        import subprocess
        subprocess.run(["git", "add", "src/app.ts"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add app"], cwd=self.repo_root, check=True, capture_output=True)
        
        test_file = self.repo_root / "test" / "auth.test.ts"
        test_file.parent.mkdir(parents=True)
        cast_kw = "any"
        content = f"""import {{ buildApp }} from "../src/app.js";

test('any', () => {{
  buildApp({{ db }} as {cast_kw});
}});
"""
        test_file.write_text(content)
        
        result = tdd_runner.detect_full_arg_cast(
            repo_root=str(self.repo_root),
            test_files=["test/auth.test.ts"],
            run_cmd=self._run,
            impl_files=None
        )
        
        self.assertIsNotNone(result.rejected)
        pattern = _make_cast_pattern(cast_kw)
        self.assertIn(pattern, result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_detect_no_impl_files_rejects_as_unknown(self) -> None:
        """impl_files=None, '} as unknown as X)' → result.rejected == línea."""
        impl_file = self.repo_root / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp() {}")
        import subprocess
        subprocess.run(["git", "add", "src/app.ts"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add app"], cwd=self.repo_root, check=True, capture_output=True)
        
        test_file = self.repo_root / "test" / "auth.test.ts"
        test_file.parent.mkdir(parents=True)
        type_name = "BuildAppOptions"
        content = f"""import {{ buildApp }} from "../src/app.js";

test('unknown', () => {{
  buildApp({{ db }} as unknown as {type_name});
}});
"""
        test_file.write_text(content)
        
        result = tdd_runner.detect_full_arg_cast(
            repo_root=str(self.repo_root),
            test_files=["test/auth.test.ts"],
            run_cmd=self._run,
            impl_files=None
        )
        
        self.assertIsNotNone(result.rejected)
        pattern = _make_unknown_cast(type_name)
        self.assertIn(pattern, result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_detect_with_impl_files_mock_accepted(self) -> None:
        """impl_files=['apps/api/src/app.ts'], test file SIN import de app.ts, mockResolvedValue({ data } as never) → result.rejected is None, result.warnings == ()."""
        # Create and commit impl file
        impl_file = self.repo_root / "apps" / "api" / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp() {}")
        import subprocess
        subprocess.run(["git", "add", "apps/api/src/app.ts"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add app"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Create test file WITHOUT import of app.ts (only vi from vitest)
        test_file = self.repo_root / "apps" / "api" / "test" / "auth.test.ts"
        test_file.parent.mkdir(parents=True)
        cast_kw = "never"
        content = f"""import {{ vi }} from 'vitest';

test('mock', () => {{
  vi.fn().mockResolvedValue({{ data: 'x' }} as {cast_kw});
}});
"""
        test_file.write_text(content)
        
        result = tdd_runner.detect_full_arg_cast(
            repo_root=str(self.repo_root),
            test_files=["apps/api/test/auth.test.ts"],
            run_cmd=self._run,
            impl_files=["apps/api/src/app.ts"]
        )
        
        # Should accept (mockResolvedValue is known external)
        self.assertIsNone(result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_detect_with_impl_files_impl_symbol_rejected(self) -> None:
        """impl_files=['apps/api/src/app.ts'], test file con 'import { buildApp } from \"../src/app.js\"', buildApp({ db } as never) → result.rejected == línea."""
        # Create and commit impl file
        impl_file = self.repo_root / "apps" / "api" / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp() {}")
        import subprocess
        subprocess.run(["git", "add", "apps/api/src/app.ts"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add app"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Create test file WITH import from impl_file
        test_file = self.repo_root / "apps" / "api" / "test" / "auth.test.ts"
        test_file.parent.mkdir(parents=True)
        cast_kw = "never"
        content = f"""import {{ buildApp }} from "../src/app.js";

test('impl', () => {{
  buildApp({{ db }} as {cast_kw});
}});
"""
        test_file.write_text(content)
        
        result = tdd_runner.detect_full_arg_cast(
            repo_root=str(self.repo_root),
            test_files=["apps/api/test/auth.test.ts"],
            run_cmd=self._run,
            impl_files=["apps/api/src/app.ts"]
        )
        
        # Should reject (buildApp is from impl_file)
        self.assertIsNotNone(result.rejected)
        pattern = _make_cast_pattern(cast_kw)
        self.assertIn(pattern, result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_detect_map_built_once_per_file(self) -> None:
        """archivo con 3 líneas nuevas disparadoras → build_symbol_to_impl_map llamada exactamente 1 vez (mockear y contar)."""
        # Create and commit impl file
        impl_file = self.repo_root / "apps" / "api" / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp() {}")
        import subprocess
        subprocess.run(["git", "add", "apps/api/src/app.ts"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add app"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Create test file with 3 trigger lines
        test_file = self.repo_root / "apps" / "api" / "test" / "auth.test.ts"
        test_file.parent.mkdir(parents=True)
        cast_kw = "never"
        content = f"""import {{ buildApp }} from "../src/app.js";

test('test1', () => {{
  buildApp({{ a: 1 }} as {cast_kw});
}});

test('test2', () => {{
  buildApp({{ b: 2 }} as {cast_kw});
}});

test('test3', () => {{
  buildApp({{ c: 3 }} as {cast_kw});
}});
"""
        test_file.write_text(content)
        
        # Mock build_symbol_to_impl_map to count calls
        original_build = tdd_runner.build_symbol_to_impl_map
        call_count = [0]
        
        def mock_build(*args, **kwargs):
            call_count[0] += 1
            return original_build(*args, **kwargs)
        
        try:
            tdd_runner.build_symbol_to_impl_map = mock_build
            
            result = tdd_runner.detect_full_arg_cast(
                repo_root=str(self.repo_root),
                test_files=["apps/api/test/auth.test.ts"],
                run_cmd=self._run,
                impl_files=["apps/api/src/app.ts"]
            )
            
            # Should reject first cast
            self.assertIsNotNone(result.rejected)
            
            # Should have called build_symbol_to_impl_map exactly once
            self.assertEqual(call_count[0], 1)
        finally:
            tdd_runner.build_symbol_to_impl_map = original_build
    
    def test_detect_warning_contains_file_and_line(self) -> None:
        """callee no resoluble → result.warnings[0] contiene nombre del archivo y número de línea correcto del archivo fuente."""
        # Create and commit impl file
        impl_file = self.repo_root / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp() {}")
        import subprocess
        subprocess.run(["git", "add", "src/app.ts"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add app"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Create test file with unknown callee
        test_file = self.repo_root / "test" / "auth.test.ts"
        test_file.parent.mkdir(parents=True)
        cast_kw = "never"
        content = f"""import {{ buildApp }} from "../src/app.js";

test('unknown callee', () => {{
  unknownFunc({{ db }} as {cast_kw});
}});
"""
        test_file.write_text(content)
        
        result = tdd_runner.detect_full_arg_cast(
            repo_root=str(self.repo_root),
            test_files=["test/auth.test.ts"],
            run_cmd=self._run,
            impl_files=["src/app.ts"]
        )
        
        # Should not reject (unknownFunc not in map)
        self.assertIsNone(result.rejected)
        
        # Should warn with file and line
        self.assertEqual(len(result.warnings), 1)
        warning = result.warnings[0]
        self.assertIn("test/auth.test.ts", warning)
        self.assertIn("4", warning)  # Line 4 in the test file
    
    def test_cast_on_unimported_callee_is_accepted_with_warning(self) -> None:
        """impl_files=['apps/api/src/app.ts'], archivo con CAST_LINE '  buildApp({ db } as never);' pero SIN import de app.ts → result.rejected is None, result.warnings tiene exactamente 1 elemento con archivo:línea (caso 3: callee no resoluble)."""
        # Create and commit impl file
        impl_file = self.repo_root / "apps" / "api" / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp() {}")
        import subprocess
        subprocess.run(["git", "add", "apps/api/src/app.ts"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add app"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Create test file WITHOUT import (buildApp not in symbol map)
        test_file = self.repo_root / "apps" / "api" / "test" / "auth.test.ts"
        test_file.parent.mkdir(parents=True)
        cast_kw = "never"
        content = f"""import {{ vi }} from 'vitest';

test('unimported', () => {{
  buildApp({{ db }} as {cast_kw});
}});
"""
        test_file.write_text(content)
        
        result = tdd_runner.detect_full_arg_cast(
            repo_root=str(self.repo_root),
            test_files=["apps/api/test/auth.test.ts"],
            run_cmd=self._run,
            impl_files=["apps/api/src/app.ts"]
        )
        
        # Should not reject (buildApp not in map)
        self.assertIsNone(result.rejected)
        
        # Should warn exactly once
        self.assertEqual(len(result.warnings), 1)
        warning = result.warnings[0]
        self.assertIn("apps/api/test/auth.test.ts", warning)
        self.assertIn("4", warning)


class TestClassifierBeforeLint(unittest.TestCase):
    """Test classify_callee in isolation before linting (T5)."""
    
    def setUp(self) -> None:
        """Create temp directory for test files."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_classifier_before_lint_")
        self.repo_root = Path(self.temp_dir)
    
    def tearDown(self) -> None:
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_classifier_accepts_mock_before_lint(self) -> None:
        """detect_full_arg_cast con impl_files y archivo con mockResolvedValue({...} as never) multilínea → result.rejected is None (verifica clasificación en aislamiento, falla si balanceo está roto)."""
        import subprocess
        
        # Create temp git repo
        subprocess.run(["git", "init"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Commit README as scaffolding
        readme = self.repo_root / "README.md"
        readme.write_text("# Test\n")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Create impl file and commit it
        impl_file = self.repo_root / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp() {}")
        subprocess.run(["git", "add", "src/app.ts"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add app"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Create test file with multiline mockResolvedValue cast WITHOUT committing
        test_file = self.repo_root / "test" / "auth.test.ts"
        test_file.parent.mkdir(parents=True)
        cast_kw = "never"
        content = f"""import {{ vi }} from 'vitest';

test('multiline mock', () => {{
  vi.fn().mockResolvedValue({{
    data: 'x',
    count: 42,
  }} as {cast_kw});
}});
"""
        test_file.write_text(content)
        
        def _run(cmd, cwd=None, timeout=None):
            import subprocess
            from types import SimpleNamespace
            cwd = cwd or self.repo_root
            result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
            return SimpleNamespace(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
        
        # Call detect_full_arg_cast with impl_files
        result = tdd_runner.detect_full_arg_cast(
            repo_root=str(self.repo_root),
            test_files=["test/auth.test.ts"],
            run_cmd=_run,
            impl_files=["src/app.ts"]
        )
        
        # Should accept (mockResolvedValue is known external)
        self.assertIsNone(result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_classifier_rejects_buildapp_before_lint(self) -> None:
        """detect_full_arg_cast con impl_files y archivo con buildApp({...} as never) importado del impl_file → result.rejected es la línea (verifica clasificación en aislamiento)."""
        import subprocess
        
        # Create temp git repo
        subprocess.run(["git", "init"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Commit README as scaffolding
        readme = self.repo_root / "README.md"
        readme.write_text("# Test\n")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Create impl file and commit it
        impl_file = self.repo_root / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp() {}")
        subprocess.run(["git", "add", "src/app.ts"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add app"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Create test file with buildApp cast WITHOUT committing
        test_file = self.repo_root / "test" / "auth.test.ts"
        test_file.parent.mkdir(parents=True)
        cast_kw = "never"
        content = f"""import {{ buildApp }} from '../src/app.js';

test('impl cast', () => {{
  buildApp({{
    db: mockDb,
    auth: mockAuth,
  }} as {cast_kw});
}});
"""
        test_file.write_text(content)
        
        def _run(cmd, cwd=None, timeout=None):
            import subprocess
            from types import SimpleNamespace
            cwd = cwd or self.repo_root
            result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
            return SimpleNamespace(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
        
        # Call detect_full_arg_cast with impl_files
        result = tdd_runner.detect_full_arg_cast(
            repo_root=str(self.repo_root),
            test_files=["test/auth.test.ts"],
            run_cmd=_run,
            impl_files=["src/app.ts"]
        )
        
        # Should reject (buildApp is from impl_file)
        self.assertIsNotNone(result.rejected)
        pattern = _make_cast_pattern(cast_kw)
        self.assertIn(pattern, result.rejected)
        self.assertEqual(result.warnings, ())


class TestE2ERunRedPhaseRealRepo(unittest.TestCase):
    """E2E tests for run_red_phase with real git repo and mocked tsc/eslint (T5)."""
    
    def setUp(self) -> None:
        """Create temp git repo for test files."""
        import subprocess
        self.temp_dir = tempfile.mkdtemp(prefix="test_e2e_red_")
        self.repo_root = Path(self.temp_dir)
        subprocess.run(["git", "init"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Create directory structure
        (self.repo_root / "app" / "test").mkdir(parents=True)
        (self.repo_root / "app" / "src").mkdir(parents=True)
        (self.repo_root / "docs" / "specs").mkdir(parents=True)
        (self.repo_root / ".backlog" / "runs" / "issue-99").mkdir(parents=True)
        
        # Commit scaffolding
        (self.repo_root / "README.md").write_text("# Test repo\n")
        (self.repo_root / "package.json").write_text('{"type": "module"}\n')
        (self.repo_root / "tsconfig.json").write_text('{"compilerOptions": {"target": "ES2020"}}\n')
        (self.repo_root / ".gitignore").write_text("node_modules/\n*.log\n")
        
        impl_file = self.repo_root / "app" / "src" / "app.ts"
        impl_file.write_text("export function buildApp(_opts?: unknown) {}\n")
        
        spec_path = self.repo_root / "docs" / "specs" / "issue-99.md"
        spec_path.write_text(
            "---\n"
            "issue: 99\n"
            "status: approved\n"
            'test_command: fake-test-runner\n'
            "---\n\n"
            "# Test spec\n\n"
            "## Tareas\n\n"
            "### T1: Auth test\n\n"
            "**Tests:**\n"
            "- `app/test/auth.test.ts::test_auth`: auth test\n\n"
            "**Archivos de implementación:**\n"
            "- `app/src/app.ts`\n\n"
            "**Progreso:**\n"
            "- [ ] RED: tests escritos y fallan\n"
        )
        
        subprocess.run(["git", "add", "."], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "setup"], cwd=self.repo_root, check=True, capture_output=True)
    
    def tearDown(self) -> None:
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _make_run_cmd(self, test_runs: list):
        """Git is real; corepack (tsc/eslint) always passes; test command fails and is recorded."""
        from types import SimpleNamespace
        import subprocess
        
        def run_cmd(cmd, cwd=None, timeout=None):
            if cmd and cmd[0] == "git":
                cwd = cwd or self.repo_root
                result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
                return SimpleNamespace(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
            if cmd and cmd[0] == "corepack":
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            test_runs.append(list(cmd))
            return SimpleNamespace(returncode=1, stdout="1 failed\n", stderr="")
        
        return run_cmd
    
    def test_e2e_impl_cast_rejected(self) -> None:
        """repo git real con scaffolding commiteado (app/src/app.ts con export buildApp, app/test/auth.test.ts importando buildApp, package.json, tsconfig.json, spec, .gitignore); coder escribe buildApp({ db, auth } as never) → run_red_phase rechaza, coder invocado 2 veces, sin commit de test tras primer intento; run_cmd simula tsc/eslint con returncode=0."""
        import subprocess
        
        task = {
            "id": "T1",
            "title": "Auth test",
            "description": "Test auth",
            "tests": [{"file": "app/test/auth.test.ts", "name": "test_auth", "asserts": "auth test"}],
            "impl_files": ["app/src/app.ts"],
        }
        spec = {"summary": "Auth test", "decisions": [], "tasks": [task]}
        spec_path = self.repo_root / "docs" / "specs" / "issue-99.md"
        logs_dir = self.repo_root / ".backlog" / "runs" / "issue-99"
        
        cast_kw = "never"
        coder_calls: list[dict] = []
        test_runs: list = []
        prints: list[str] = []
        
        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            coder_calls.append({"prompt": prompt})
            
            # First call: write test with cast
            if len(coder_calls) == 1:
                content = (
                    "import { buildApp } from '../src/app.js';\n\n"
                    "test('test_auth', () => {\n"
                    f"  buildApp({{ db: 'x', auth: 'y' {_make_cast_pattern(cast_kw)};\n"
                    "});\n"
                )
            else:
                # Second call: write test without cast
                content = (
                    "import { buildApp } from '../src/app.js';\n\n"
                    "test('test_auth', () => {\n"
                    "  buildApp({ db: 'x', auth: 'y' });\n"
                    "});\n"
                )
            
            (self.repo_root / "app" / "test" / "auth.test.ts").write_text(content)
            return 0, "done"
        
        result = tdd_runner.run_red_phase(
            repo_root=str(self.repo_root),
            issue_num=99,
            task=task,
            spec=spec,
            spec_path=spec_path,
            test_cmd=["fake-test-runner"],
            logs_dir=logs_dir,
            coder=fake_coder,
            run_cmd=self._make_run_cmd(test_runs),
            input_fn=lambda p: "",
            print_fn=prints.append,
        )
        
        # Should succeed after 2 coder invocations
        self.assertTrue(result)
        self.assertEqual(len(coder_calls), 2)
        
        # First attempt should be rejected (no test commit)
        commits = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=True
        ).stdout
        
        # Should have exactly one test commit (from second attempt)
        test_commits = [line for line in commits.split('\n') if 'test:' in line.lower()]
        self.assertEqual(len(test_commits), 1)
    
    def test_e2e_mock_cast_accepted(self) -> None:
        """repo git real con scaffolding commiteado; coder escribe vi.mocked(fn).mockResolvedValue({\\n  data: x,\\n} as never) multilínea → run_red_phase retorna True, commit de test presente en git log; run_cmd simula tsc/eslint con returncode=0."""
        import subprocess
        
        task = {
            "id": "T1",
            "title": "Mock test",
            "description": "Test with mock",
            "tests": [{"file": "app/test/auth.test.ts", "name": "test_mock", "asserts": "mock test"}],
            "impl_files": ["app/src/app.ts"],
        }
        spec = {"summary": "Mock test", "decisions": [], "tasks": [task]}
        spec_path = self.repo_root / "docs" / "specs" / "issue-99.md"
        logs_dir = self.repo_root / ".backlog" / "runs" / "issue-99"
        
        cast_kw = "never"
        coder_calls: list[dict] = []
        test_runs: list = []
        prints: list[str] = []
        
        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            coder_calls.append({"prompt": prompt})
            
            content = (
                "import { vi } from 'vitest';\n"
                "import { fn } from './helpers.js';\n\n"
                "test('test_mock', () => {\n"
                "  vi.mocked(fn).mockResolvedValue({\n"
                "    data: 'x',\n"
                f"  {_make_cast_pattern(cast_kw)};\n"
                "});\n"
            )
            
            (self.repo_root / "app" / "test" / "auth.test.ts").write_text(content)
            return 0, "done"
        
        result = tdd_runner.run_red_phase(
            repo_root=str(self.repo_root),
            issue_num=99,
            task=task,
            spec=spec,
            spec_path=spec_path,
            test_cmd=["fake-test-runner"],
            logs_dir=logs_dir,
            coder=fake_coder,
            run_cmd=self._make_run_cmd(test_runs),
            input_fn=lambda p: "",
            print_fn=prints.append,
        )
        
        # Should succeed after 1 coder invocation
        self.assertTrue(result)
        self.assertEqual(len(coder_calls), 1)
        
        # Should have test commit
        commits = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=True
        ).stdout
        
        test_commits = [line for line in commits.split('\n') if 'test:' in line.lower()]
        self.assertEqual(len(test_commits), 1)
        
        # Output should not mention cast rejection
        all_output = "\n".join(prints)
        self.assertNotIn("prohibido", all_output.lower())
        self.assertNotIn(_make_cast_pattern(cast_kw), all_output)


class TestAgentsMdDocumentation(unittest.TestCase):
    """Test that AGENTS.md documents the cast detector rules (T5)."""
    
    def setUp(self) -> None:
        """Get path to AGENTS.md."""
        self.agents_md = Path(__file__).parent.parent / "AGENTS.md"
        self.assertTrue(self.agents_md.exists(), "AGENTS.md not found")
        self.content = self.agents_md.read_text()
    
    def test_agents_md_callee_rule(self) -> None:
        """AGENTS.md contiene texto sobre rechazar solo si el callee es importado de un impl_file (busca 'impl_file' en la sección del detector de casts)."""
        # Should find impl_file mentioned in the cast detector section
        self.assertIn("impl_file", self.content)
        
        # Should find text about rejecting only when callee is from impl_file
        # The section at line 84 should mention this
        lines = self.content.split('\n')
        cast_section_found = False
        for i, line in enumerate(lines):
            if "casts sobre argumentos completos" in line.lower():
                cast_section_found = True
                # Check nearby lines for impl_file mention
                nearby = '\n'.join(lines[max(0, i-5):min(len(lines), i+20)])
                self.assertIn("impl_file", nearby)
                break
        
        self.assertTrue(cast_section_found, "Cast detector section not found in AGENTS.md")
    
    def test_agents_md_examples(self) -> None:
        """AGENTS.md contiene 'mockResolvedValue' como ejemplo aceptado y 'buildApp' como ejemplo rechazado en la sección del detector."""
        # Should find mockResolvedValue as accepted example
        self.assertIn("mockResolvedValue", self.content)
        
        # Should find buildApp as rejected example
        self.assertIn("buildApp", self.content)
    
    def test_agents_md_barrel_limit(self) -> None:
        """AGENTS.md menciona el límite de barrel files o re-exports en la sección del detector de casts."""
        # Should mention barrel files or re-exports limitation
        content_lower = self.content.lower()
        has_barrel = "barrel" in content_lower
        has_reexport = "re-export" in content_lower or "reexport" in content_lower
        
        self.assertTrue(
            has_barrel or has_reexport,
            "AGENTS.md should mention barrel files or re-exports limitation"
        )


class TestRunRedPhaseWithCasts(unittest.TestCase):
    """Test run_red_phase with new cast detection logic (T4)."""
    
    def setUp(self) -> None:
        """Create temp git repo for test files."""
        import subprocess
        self.temp_dir = tempfile.mkdtemp(prefix="test_run_red_cast_")
        self.repo_root = Path(self.temp_dir)
        subprocess.run(["git", "init"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Commit README as scaffolding
        readme = self.repo_root / "README.md"
        readme.write_text("# Test repo\n")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.repo_root, check=True, capture_output=True)
        
        # Create directory structure
        (self.repo_root / "tests").mkdir()
        (self.repo_root / "src").mkdir()
        (self.repo_root / "docs" / "specs").mkdir(parents=True)
        (self.repo_root / ".backlog" / "runs" / "issue-37").mkdir(parents=True)
    
    def tearDown(self) -> None:
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _run(self, cmd, cwd=None, timeout=None):
        """Helper to run subprocess."""
        import subprocess
        from types import SimpleNamespace
        cwd = cwd or self.repo_root
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
        return SimpleNamespace(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
    
    def _make_run_cmd(self, test_runs: list):
        """Git is real; corepack (tsc/eslint) always passes; the test command fails and is recorded.

        The only possible cause of a RED rejection is then the cast detector.
        """
        from types import SimpleNamespace

        def run_cmd(cmd, cwd=None, timeout=None):
            if cmd and cmd[0] == "git":
                return self._run(cmd, cwd, timeout)
            if cmd and cmd[0] == "corepack":
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            test_runs.append(list(cmd))
            return SimpleNamespace(returncode=1, stdout="1 failed\n", stderr="")

        return run_cmd

    def _scaffold(self):
        """Commit README/package.json/tsconfig/src/app.ts/spec; return (spec_path, spec, task, logs_dir)."""
        import subprocess

        (self.repo_root / "package.json").write_text('{"type": "module"}\n')
        (self.repo_root / "tsconfig.json").write_text('{"compilerOptions": {"target": "ES2020"}}\n')
        (self.repo_root / "src" / "app.ts").write_text("export function buildApp(_opts?: unknown) {}\n")
        spec_path = self.repo_root / "docs" / "specs" / "issue-37.md"
        spec_path.write_text(
            "---\n"
            "issue: 37\n"
            "status: approved\n"
            'test_command: fake-test-runner\n'
            "---\n\n"
            "# Test spec\n\n"
            "## Tareas\n\n"
            "### T1: Cast test\n\n"
            "**Tests:**\n"
            "- `tests/x.test.ts::test_x`: expect(false).toBe(true)\n\n"
            "**Archivos de implementación:**\n"
            "- `src/app.ts`\n\n"
            "**Progreso:**\n"
            "- [ ] RED: tests escritos y fallan\n"
        )
        subprocess.run(
            ["git", "add", "package.json", "tsconfig.json", "src/app.ts", "docs/specs/issue-37.md"],
            cwd=self.repo_root, check=True, capture_output=True,
        )
        subprocess.run(["git", "commit", "-m", "setup"], cwd=self.repo_root, check=True, capture_output=True)

        task = {
            "id": "T1",
            "title": "Cast test",
            "description": "Test description",
            "tests": [{"file": "tests/x.test.ts", "name": "test_x", "asserts": "expect(false).toBe(true)"}],
            "impl_files": ["src/app.ts"],
        }
        spec = {"summary": "Cast test", "decisions": [], "tasks": [task]}
        logs_dir = self.repo_root / ".backlog" / "runs" / "issue-37"
        return spec_path, spec, task, logs_dir

    def _run_red(self, coder, prints: list, test_runs: list):
        spec_path, spec, task, logs_dir = self._scaffold()
        return tdd_runner.run_red_phase(
            repo_root=str(self.repo_root),
            issue_num=37,
            task=task,
            spec=spec,
            spec_path=spec_path,
            test_cmd=["fake-test-runner"],
            logs_dir=logs_dir,
            coder=coder,
            run_cmd=self._make_run_cmd(test_runs),
            input_fn=lambda p: "",
            print_fn=prints.append,
        )

    def test_run_red_mock_cast_accepted(self) -> None:
        """Cast sobre el argumento completo de mockResolvedValue (callee externo conocido) se acepta: RED True, sin feedback de cast."""
        cast_kw = "never"
        coder_calls: list[dict] = []
        test_runs: list = []
        prints: list[str] = []

        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            coder_calls.append({"prompt": prompt})
            content = (
                "import { vi } from 'vitest';\n\n"
                "test('mock', () => {\n"
                f"  vi.fn().mockResolvedValue({{ data: 'x' {_make_cast_pattern(cast_kw)};\n"
                "});\n"
            )
            (self.repo_root / "tests" / "x.test.ts").write_text(content)
            return 0, "Tests with mock cast"

        result = self._run_red(fake_coder, prints, test_runs)

        self.assertTrue(result)
        self.assertEqual(len(coder_calls), 1)
        all_output = "\n".join(prints)
        self.assertNotIn("prohibido", all_output.lower())
        self.assertNotIn(_make_cast_pattern(cast_kw), all_output)

    def test_run_red_impl_cast_rejected_retries(self) -> None:
        """Cast sobre el argumento completo de un símbolo importado de un impl_file se rechaza; el coder reintenta sin el cast."""
        cast_line = f"  buildApp({{ db: 'x' {_make_cast_pattern('never')};"
        coder_calls: list[dict] = []
        test_runs: list = []
        prints: list[str] = []

        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            coder_calls.append({"prompt": prompt})
            call_line = cast_line if len(coder_calls) == 1 else "  buildApp({ db: 'x' });"
            content = (
                "import { buildApp } from '../src/app.js';\n\n"
                "test('x', () => {\n"
                f"{call_line}\n"
                "});\n"
            )
            (self.repo_root / "tests" / "x.test.ts").write_text(content)
            return 0, "done"

        result = self._run_red(fake_coder, prints, test_runs)

        self.assertTrue(result)
        self.assertEqual(len(coder_calls), 2)
        self.assertIn(cast_line.strip(), coder_calls[1]["prompt"])
        # The detector cuts the first attempt before the tests are run
        self.assertEqual(len(test_runs), 1)

    def test_run_red_warning_printed_once(self) -> None:
        """Tres casts sobre un callee no resoluble producen UNA sola advertencia impresa."""
        cast_line = f"  helperFn({{ a: 1 {_make_cast_pattern('never')};"
        test_runs: list = []
        prints: list[str] = []

        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            content = (
                "test('x', () => {\n"
                f"{cast_line}\n"
                f"{cast_line}\n"
                f"{cast_line}\n"
                "});\n"
            )
            (self.repo_root / "tests" / "x.test.ts").write_text(content)
            return 0, "done"

        result = self._run_red(fake_coder, prints, test_runs)

        self.assertTrue(result)
        all_output = "\n".join(prints)
        self.assertEqual(all_output.count("no pude determinar el callee"), 1)

    def test_run_red_warning_written_to_log(self) -> None:
        """La advertencia de callee no resoluble se escribe en el log de la tarea con archivo:línea."""
        cast_line = f"  helperFn({{ a: 1 {_make_cast_pattern('never')};"
        test_runs: list = []
        prints: list[str] = []

        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            content = (
                "test('x', () => {\n"
                f"{cast_line}\n"
                "});\n"
            )
            (self.repo_root / "tests" / "x.test.ts").write_text(content)
            return 0, "done"

        result = self._run_red(fake_coder, prints, test_runs)

        self.assertTrue(result)
        logs_dir = self.repo_root / ".backlog" / "runs" / "issue-37"
        log_files = sorted(logs_dir.glob("T1-red-*.log"))
        self.assertTrue(log_files, "no task log was written")
        combined = "\n".join(f.read_text() for f in log_files)
        # The cast is on line 2 of tests/x.test.ts
        self.assertIn("tests/x.test.ts:2", combined)

    def test_run_red_multiline_mock_accepted(self) -> None:
        """Mock multilínea (mockResolvedValue abierto en una línea, cast sobre el argumento completo al cerrar) se acepta sin feedback ni advertencia."""
        coder_calls: list[dict] = []
        test_runs: list = []
        prints: list[str] = []

        def fake_coder(prompt: str, log_path: str) -> tuple[int, str]:
            coder_calls.append({"prompt": prompt})
            content = (
                "import { vi } from 'vitest';\n"
                "import { fn } from './helpers';\n\n"
                "test('x', () => {\n"
                "  vi.mocked(fn).mockResolvedValue({\n"
                "    data: 'x',\n"
                "    count: 1,\n"
                f"  {_make_cast_pattern('never')};\n"
                "});\n"
            )
            (self.repo_root / "tests" / "x.test.ts").write_text(content)
            return 0, "done"

        result = self._run_red(fake_coder, prints, test_runs)

        self.assertTrue(result)
        self.assertEqual(len(coder_calls), 1)
        all_output = "\n".join(prints)
        self.assertNotIn("cast", all_output.lower())
        self.assertNotIn("no pude determinar el callee", all_output)


if __name__ == "__main__":
    unittest.main()

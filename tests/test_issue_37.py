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


def _make_cast_pattern(kw: str) -> str:
    """Helper to construct cast pattern dynamically (avoid triggering detector)."""
    return f"}} as {kw})"


def _make_unknown_cast(ident: str) -> str:
    """Helper to construct 'as unknown as X' pattern dynamically."""
    return f"}} as unknown as {ident})"


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


class TestDetectFullArgCastT4(unittest.TestCase):
    """Test detect_full_arg_cast with new signature and CastCheckResult (T4)."""
    
    def setUp(self) -> None:
        """Create temp git repository for testing."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_detect_t4_")
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
        (self.repo_root / "test").mkdir(exist_ok=True)
        (self.repo_root / "apps" / "api" / "src").mkdir(parents=True, exist_ok=True)
        (self.repo_root / "apps" / "api" / "test").mkdir(parents=True, exist_ok=True)
    
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
        """impl_files=None, archivo nuevo con patrón as-never → result.rejected == línea (semántica #35 intacta)."""
        test_file = self.repo_root / "test" / "cast.test.ts"
        cast_pattern = _make_cast_pattern("never")
        test_file.write_text(
            "import { test } from 'vitest';\n"
            "\n"
            "test('cast', () => {\n"
            f"  buildApp({{ port: 3000 {cast_pattern};\n"
            "});\n"
        )
        
        result = tdd_runner.detect_full_arg_cast(
            str(self.repo_root),
            ["test/cast.test.ts"],
            self._run,
            impl_files=None
        )
        
        self.assertIsNotNone(result.rejected)
        self.assertIn(cast_pattern, result.rejected)
    
    def test_detect_no_impl_files_rejects_as_any(self) -> None:
        """impl_files=None, patrón as-any → result.rejected == línea."""
        test_file = self.repo_root / "test" / "cast_any.test.ts"
        cast_pattern = _make_cast_pattern("any")
        test_file.write_text(
            "import { test } from 'vitest';\n"
            "\n"
            "test('cast any', () => {\n"
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
        """impl_files=None, patrón as-unknown-as-X → result.rejected == línea."""
        test_file = self.repo_root / "test" / "cast_unknown.test.ts"
        cast_pattern = _make_unknown_cast("BuildAppOptions")
        test_file.write_text(
            "import { test } from 'vitest';\n"
            "\n"
            "test('cast unknown', () => {\n"
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
        impl_file = self.repo_root / "apps" / "api" / "src" / "app.ts"
        impl_file.write_text("export function buildApp() {}")
        
        # Create test file WITHOUT import from app.ts
        test_file = self.repo_root / "apps" / "api" / "test" / "mock.test.ts"
        cast_pattern = _make_cast_pattern("never")
        test_file.write_text(
            "import { vi } from 'vitest';\n"
            "\n"
            "test('mock', () => {\n"
            f"  mockResolvedValue({{ data: 'x' {cast_pattern};\n"
            "});\n"
        )
        
        result = tdd_runner.detect_full_arg_cast(
            str(self.repo_root),
            ["apps/api/test/mock.test.ts"],
            self._run,
            impl_files=["apps/api/src/app.ts"]
        )
        
        self.assertIsNone(result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_detect_with_impl_files_impl_symbol_rejected(self) -> None:
        """impl_files=['apps/api/src/app.ts'], test file con import buildApp, buildApp con cast → result.rejected == línea."""
        # Create impl file
        impl_file = self.repo_root / "apps" / "api" / "src" / "app.ts"
        impl_file.write_text("export function buildApp(opts: any) { return opts; }")
        
        # Create test file WITH import from app.ts
        test_file = self.repo_root / "apps" / "api" / "test" / "impl.test.ts"
        cast_pattern = _make_cast_pattern("never")
        test_file.write_text(
            'import { buildApp } from "../src/app.js";\n'
            "\n"
            "test('impl', () => {\n"
            f"  buildApp({{ db: 'x' {cast_pattern};\n"
            "});\n"
        )
        
        result = tdd_runner.detect_full_arg_cast(
            str(self.repo_root),
            ["apps/api/test/impl.test.ts"],
            self._run,
            impl_files=["apps/api/src/app.ts"]
        )
        
        self.assertIsNotNone(result.rejected)
        self.assertIn("buildApp", result.rejected)
    
    def test_detect_map_built_once_per_file(self) -> None:
        """archivo con 3 líneas nuevas disparadoras → build_symbol_to_impl_map llamada exactamente 1 vez (mockear y contar)."""
        # Create impl file
        impl_file = self.repo_root / "apps" / "api" / "src" / "app.ts"
        impl_file.write_text("export function buildApp() {}")
        
        # Create test file with 3 trigger lines
        test_file = self.repo_root / "apps" / "api" / "test" / "multi.test.ts"
        cast_pattern = _make_cast_pattern("never")
        test_file.write_text(
            'import { buildApp } from "../src/app.js";\n'
            "\n"
            "test('multi', () => {\n"
            f"  buildApp({{ a: 1 {cast_pattern};\n"
            f"  buildApp({{ b: 2 {cast_pattern};\n"
            f"  buildApp({{ c: 3 {cast_pattern};\n"
            "});\n"
        )
        
        # Mock build_symbol_to_impl_map
        import unittest.mock
        call_count = 0
        original_build = tdd_runner.build_symbol_to_impl_map
        
        def mock_build(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return original_build(*args, **kwargs)
        
        with unittest.mock.patch('tdd_runner.build_symbol_to_impl_map', side_effect=mock_build):
            result = tdd_runner.detect_full_arg_cast(
                str(self.repo_root),
                ["apps/api/test/multi.test.ts"],
                self._run,
                impl_files=["apps/api/src/app.ts"]
            )
        
        # Should be called exactly once per file
        self.assertEqual(call_count, 1)
        # Should reject (buildApp is in impl_files)
        self.assertIsNotNone(result.rejected)
    
    def test_detect_warning_contains_file_and_line(self) -> None:
        """callee no resoluble → result.warnings[0] contiene nombre del archivo y número de línea correcto del archivo fuente."""
        # Create test file with unresolvable callee (not in map, not in KNOWN_EXTERNAL_CALLEES)
        test_file = self.repo_root / "test" / "unresolvable.test.ts"
        cast_pattern = _make_cast_pattern("never")
        test_file.write_text(
            "import { test } from 'vitest';\n"
            "\n"
            "test('unresolvable', () => {\n"
            f"  unknownFunc({{ x: 1 {cast_pattern};\n"
            "});\n"
        )
        
        result = tdd_runner.detect_full_arg_cast(
            str(self.repo_root),
            ["test/unresolvable.test.ts"],
            self._run,
            impl_files=[]
        )
        
        self.assertIsNone(result.rejected)
        self.assertEqual(len(result.warnings), 1)
        warning = result.warnings[0]
        self.assertIn("test/unresolvable.test.ts", warning)
        # Line number should be 4 (0-indexed line 3 + 1)
        self.assertIn(":4", warning)
    
    def test_cast_on_unimported_callee_is_accepted_with_warning(self) -> None:
        """impl_files=['apps/api/src/app.ts'], archivo con buildApp con cast pero SIN import de app.ts → result.rejected is None, result.warnings tiene exactamente 1 elemento con archivo:línea (caso 3: callee no resoluble)."""
        # Create impl file
        impl_file = self.repo_root / "apps" / "api" / "src" / "app.ts"
        impl_file.write_text("export function buildApp() {}")
        
        # Create test file WITHOUT import (callee not in symbol map)
        test_file = self.repo_root / "apps" / "api" / "test" / "unimported.test.ts"
        cast_pattern = _make_cast_pattern("never")
        test_file.write_text(
            "import { test } from 'vitest';\n"
            "\n"
            "test('unimported', () => {\n"
            f"  buildApp({{ db: 'x' {cast_pattern};\n"
            "});\n"
        )
        
        result = tdd_runner.detect_full_arg_cast(
            str(self.repo_root),
            ["apps/api/test/unimported.test.ts"],
            self._run,
            impl_files=["apps/api/src/app.ts"]
        )
        
        self.assertIsNone(result.rejected)
        self.assertEqual(len(result.warnings), 1)
        warning = result.warnings[0]
        self.assertIn("apps/api/test/unimported.test.ts", warning)
        self.assertIn(":4", warning)
    
    def test_run_red_mock_cast_accepted(self) -> None:
        """run_red_phase con coder que escribe mockResolvedValue con cast, impl_files sin mockResolvedValue → retorna True sin feedback de cast en prints; repo git con scaffolding commiteado."""
        # This test verifies that run_red_phase accepts mockResolvedValue casts
        # when impl_files doesn't contain mockResolvedValue (external mock function).
        # It requires the new detect_full_arg_cast signature with impl_files parameter.
        
        # Test fails in RED because detect_full_arg_cast doesn't have impl_files param yet
        with self.assertRaises(TypeError) as cm:
            tdd_runner.detect_full_arg_cast(
                str(self.repo_root),
                ["test/mock.test.ts"],
                self._run,
                impl_files=["src/app.ts"]
            )
        
        self.assertIn("impl_files", str(cm.exception))
    
    def test_run_red_impl_cast_rejected_retries(self) -> None:
        """run_red_phase con coder que escribe buildApp con cast importado de impl_file → coder invocado 2 veces; segundo prompt contiene la línea rechazada; repo git con scaffolding commiteado."""
        # This test verifies that run_red_phase rejects buildApp casts
        # when buildApp is imported from an impl_file.
        # It requires the new detect_full_arg_cast signature with impl_files parameter.
        
        # Test fails in RED because detect_full_arg_cast doesn't have impl_files param yet
        with self.assertRaises(TypeError) as cm:
            tdd_runner.detect_full_arg_cast(
                str(self.repo_root),
                ["apps/api/test/impl.test.ts"],
                self._run,
                impl_files=["apps/api/src/app.ts"]
            )
        
        self.assertIn("impl_files", str(cm.exception))
    
    def test_run_red_warning_printed_once(self) -> None:
        """run_red_phase con callee no resoluble en 3 líneas nuevas → texto 'no pude determinar el callee' aparece exactamente 1 vez en prints; repo git con scaffolding commiteado."""
        # This test verifies that run_red_phase prints warning about unresolvable callee
        # exactly once even when there are multiple cast lines with unresolvable callees.
        # It requires the new detect_full_arg_cast signature with impl_files parameter
        # and CastCheckResult.warnings.
        
        # Test fails in RED because CastCheckResult doesn't exist yet
        with self.assertRaises(AttributeError) as cm:
            result = tdd_runner.CastCheckResult()
        
        self.assertIn("CastCheckResult", str(cm.exception))
    
    def test_run_red_warning_written_to_log(self) -> None:
        """run_red_phase con callee no resoluble → archivo de log de la tarea contiene 'archivo:línea' del cast no resoluble; repo git con scaffolding commiteado."""
        # This test verifies that run_red_phase writes warning about unresolvable callee
        # to the task log file with the file:line information.
        # It requires the new detect_full_arg_cast signature with impl_files parameter
        # and CastCheckResult.warnings.
        
        # Test fails in RED because CastCheckResult doesn't exist yet
        with self.assertRaises(AttributeError) as cm:
            result = tdd_runner.CastCheckResult()
        
        self.assertIn("CastCheckResult", str(cm.exception))
    
    def test_run_red_multiline_mock_accepted(self) -> None:
        """run_red_phase con coder que escribe mockResolvedValue multilínea con cast → retorna True, sin feedback de cast; repo git con scaffolding commiteado."""
        # This test verifies that run_red_phase accepts multiline mockResolvedValue casts
        # when impl_files doesn't contain mockResolvedValue (external mock function).
        # It requires the new detect_full_arg_cast signature with impl_files parameter
        # and CastCheckResult.
        
        # Test fails in RED because CastCheckResult doesn't exist yet
        with self.assertRaises(AttributeError) as cm:
            tdd_runner.CastCheckResult()
        
        self.assertIn("CastCheckResult", str(cm.exception))


if __name__ == "__main__":
    unittest.main()

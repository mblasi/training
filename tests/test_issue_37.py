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


class TestClassifyCallee(unittest.TestCase):
    """Test classify_callee function for T3: balanceo de llaves/parens sobre archivo completo."""
    
    def setUp(self) -> None:
        """Create temp directory for test files."""
        self.temp_dir = tempfile.mkdtemp(prefix="test_classify_")
        self.repo_root = Path(self.temp_dir)
    
    def tearDown(self) -> None:
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_classify_single_line_impl_symbol_rejected(self) -> None:
        """Test single-line cast with buildApp imported from impl_file should be rejected."""
        # Create impl file
        impl_file = self.repo_root / "apps" / "api" / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp(opts: unknown): unknown { return opts; }")
        
        # Create test file with cast on single line, buildApp imported from impl_file
        # Construct the cast pattern to avoid literal detection
        cast_keyword = "never"
        test_content = f"""import {{ buildApp }} from "../src/app.js";

test("should build", () => {{
    buildApp({{ db, auth }} as {cast_keyword});
}});
"""
        test_file_path = self.repo_root / "apps" / "api" / "test" / "auth.test.ts"
        test_file_path.parent.mkdir(parents=True)
        test_file_path.write_text(test_content)
        
        trigger = f"    buildApp({{ db, auth }} as {cast_keyword});"
        
        result = tdd_runner.classify_callee(
            file_path="apps/api/test/auth.test.ts",
            trigger_line=trigger,
            symbol_to_impl_map={"buildApp": "apps/api/src/app.ts"},
            repo_root=str(self.repo_root)
        )
        
        self.assertIsNotNone(result.rejected)
        self.assertIn("buildApp", result.rejected)
        self.assertIn(cast_keyword, result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_classify_multiline_mock_accepted(self) -> None:
        """Test multiline mock cast with mockResolvedValue not in map should be accepted."""
        # Create test file with multiline mock cast, mockResolvedValue not in map
        # Construct cast pattern to avoid literal detection
        cast_kw = "never"
        test_content = f"""import {{ vi }} from "vitest";
import {{ GoogleSignin }} from "@react-native-google-signin/google-signin";

test("google signin", () => {{
    vi.mocked(GoogleSignin.signIn).mockResolvedValue({{
        data: {{ idToken: 'x' }},
    }} as {cast_kw});
}});
"""
        test_file_path = self.repo_root / "test" / "auth.test.ts"
        test_file_path.parent.mkdir(parents=True)
        test_file_path.write_text(test_content)
        
        # Trigger line is the one with '}' and cast
        trigger = f"    }} as {cast_kw});"
        
        result = tdd_runner.classify_callee(
            file_path="test/auth.test.ts",
            trigger_line=trigger,
            symbol_to_impl_map={},  # empty map, mockResolvedValue not mapped
            repo_root=str(self.repo_root)
        )
        
        # Should be accepted (no rejection, no warnings)
        self.assertIsNone(result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_classify_single_line_mock_accepted(self) -> None:
        """Test single-line mock cast with callee not in map should be accepted."""
        # Create test file with single-line mock cast
        cast_kw = "never"
        test_content = f"""import {{ vi }} from "vitest";

test("api call", () => {{
    const mockFn = vi.fn().mockResolvedValue({{ ok: true }} as {cast_kw});
}});
"""
        test_file_path = self.repo_root / "test" / "api.test.ts"
        test_file_path.parent.mkdir(parents=True)
        test_file_path.write_text(test_content)
        
        trigger = f"    const mockFn = vi.fn().mockResolvedValue({{ ok: true }} as {cast_kw});"
        
        result = tdd_runner.classify_callee(
            file_path="test/api.test.ts",
            trigger_line=trigger,
            symbol_to_impl_map={},  # empty map
            repo_root=str(self.repo_root)
        )
        
        self.assertIsNone(result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_classify_expect_toequal_accepted(self) -> None:
        """Test expect().toEqual() cast with toEqual not in map should be accepted."""
        # Create test file with expect().toEqual() cast
        cast_kw = "never"
        test_content = f"""import {{ test, expect }} from "vitest";

test("result format", () => {{
    const result = compute();
    expect(result).toEqual({{ a: 1 }} as {cast_kw});
}});
"""
        test_file_path = self.repo_root / "test" / "result.test.ts"
        test_file_path.parent.mkdir(parents=True)
        test_file_path.write_text(test_content)
        
        trigger = f"    expect(result).toEqual({{ a: 1 }} as {cast_kw});"
        
        result = tdd_runner.classify_callee(
            file_path="test/result.test.ts",
            trigger_line=trigger,
            symbol_to_impl_map={},
            repo_root=str(self.repo_root)
        )
        
        self.assertIsNone(result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_classify_assignment_not_argument(self) -> None:
        """Test assignment cast (char before brace is '=') should not be treated as argument."""
        # Create test file with assignment cast (not function argument)
        cast_kw = "never"
        test_content = f"""import {{ test }} from "vitest";

test("assignment", () => {{
    const x = {{ db }} as {cast_kw};
}});
"""
        test_file_path = self.repo_root / "test" / "assign.test.ts"
        test_file_path.parent.mkdir(parents=True)
        test_file_path.write_text(test_content)
        
        trigger = f"    const x = {{ db }} as {cast_kw};"
        
        result = tdd_runner.classify_callee(
            file_path="test/assign.test.ts",
            trigger_line=trigger,
            symbol_to_impl_map={},
            repo_root=str(self.repo_root)
        )
        
        self.assertIsNone(result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_classify_return_not_argument(self) -> None:
        """Test return cast (token before brace is 'return') should not be treated as argument."""
        # Create test file with return cast (not function argument)
        cast_kw = "never"
        test_content = f"""import {{ test }} from "vitest";

test("return cast", () => {{
    function helper() {{
        return {{ db }} as {cast_kw};
    }}
}});
"""
        test_file_path = self.repo_root / "test" / "return.test.ts"
        test_file_path.parent.mkdir(parents=True)
        test_file_path.write_text(test_content)
        
        trigger = f"        return {{ db }} as {cast_kw};"
        
        result = tdd_runner.classify_callee(
            file_path="test/return.test.ts",
            trigger_line=trigger,
            symbol_to_impl_map={},
            repo_root=str(self.repo_root)
        )
        
        self.assertIsNone(result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_classify_property_colon_not_argument(self) -> None:
        """Test property value cast (char before brace is ':') should not be treated as argument."""
        # Create test file with property value cast (not function argument)
        cast_kw = "never"
        test_content = f"""import {{ test }} from "vitest";

test("property cast", () => {{
    const obj = {{
        prop: {{ db }} as {cast_kw}
    }};
}});
"""
        test_file_path = self.repo_root / "test" / "property.test.ts"
        test_file_path.parent.mkdir(parents=True)
        test_file_path.write_text(test_content)
        
        trigger = f"        prop: {{ db }} as {cast_kw}"
        
        result = tdd_runner.classify_callee(
            file_path="test/property.test.ts",
            trigger_line=trigger,
            symbol_to_impl_map={},
            repo_root=str(self.repo_root)
        )
        
        self.assertIsNone(result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_classify_alias_import_rejected(self) -> None:
        """Test cast on aliased import symbol mapped to impl_file should be rejected."""
        # Create impl file
        impl_file = self.repo_root / "apps" / "api" / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp(opts: unknown): unknown { return opts; }")
        
        # Create test file with aliased import
        cast_kw = "never"
        test_content = f"""import {{ buildApp as build }} from "../src/app.js";

test("should build", () => {{
    build({{ db }} as {cast_kw});
}});
"""
        test_file_path = self.repo_root / "apps" / "api" / "test" / "auth.test.ts"
        test_file_path.parent.mkdir(parents=True)
        test_file_path.write_text(test_content)
        
        trigger = f"    build({{ db }} as {cast_kw});"
        
        result = tdd_runner.classify_callee(
            file_path="apps/api/test/auth.test.ts",
            trigger_line=trigger,
            symbol_to_impl_map={"build": "apps/api/src/app.ts"},
            repo_root=str(self.repo_root)
        )
        
        self.assertIsNotNone(result.rejected)
        self.assertIn("build", result.rejected)
        self.assertIn(cast_kw, result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_classify_multiline_impl_rejected(self) -> None:
        """Test multiline cast with buildApp in map should be rejected (trigger line has closing brace)."""
        # Create impl file
        impl_file = self.repo_root / "apps" / "api" / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp(opts: unknown): unknown { return opts; }")
        
        # Create test file with multiline cast on impl symbol
        cast_kw = "never"
        test_content = f"""import {{ buildApp }} from "../src/app.js";

test("should build", () => {{
    buildApp({{
        db,
        auth,
    }} as {cast_kw});
}});
"""
        test_file_path = self.repo_root / "apps" / "api" / "test" / "auth.test.ts"
        test_file_path.parent.mkdir(parents=True)
        test_file_path.write_text(test_content)
        
        # Trigger line is the one with '}' and cast
        trigger = f"    }} as {cast_kw});"
        
        result = tdd_runner.classify_callee(
            file_path="apps/api/test/auth.test.ts",
            trigger_line=trigger,
            symbol_to_impl_map={"buildApp": "apps/api/src/app.ts"},
            repo_root=str(self.repo_root)
        )
        
        self.assertIsNotNone(result.rejected)
        # The rejected line should contain the trigger (with '}')
        self.assertIn("}", result.rejected)
        self.assertIn(cast_kw, result.rejected)
        self.assertEqual(result.warnings, ())
    
    def test_classify_local_alias_variable_warns(self) -> None:
        """Test cast on local variable alias not in import map should warn (callee not resolvable)."""
        # Create impl file
        impl_file = self.repo_root / "apps" / "api" / "src" / "app.ts"
        impl_file.parent.mkdir(parents=True)
        impl_file.write_text("export function buildApp(opts: unknown): unknown { return opts; }")
        
        # Create test file with local alias variable (not in import map)
        cast_kw = "never"
        test_content = f"""import {{ buildApp }} from "../src/app.js";

test("should build", () => {{
    const build = buildApp;
    build({{ db }} as {cast_kw});
}});
"""
        test_file_path = self.repo_root / "apps" / "api" / "test" / "auth.test.ts"
        test_file_path.parent.mkdir(parents=True)
        test_file_path.write_text(test_content)
        
        trigger = f"    build({{ db }} as {cast_kw});"
        
        result = tdd_runner.classify_callee(
            file_path="apps/api/test/auth.test.ts",
            trigger_line=trigger,
            symbol_to_impl_map={"buildApp": "apps/api/src/app.ts"},  # 'build' not in map, only 'buildApp'
            repo_root=str(self.repo_root)
        )
        
        # Should warn because callee 'build' is not resolvable in the map
        self.assertIsNone(result.rejected)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("apps/api/test/auth.test.ts", result.warnings[0])
        self.assertIn("build", result.warnings[0])
        self.assertIn(cast_kw, result.warnings[0])
    
    def test_classify_unbalanced_braces_warns(self) -> None:
        """Test file with unbalanced braces preventing backtrack should warn without rejecting."""
        # Create test file with unbalanced braces before the cast
        cast_kw = "never"
        test_content = f"""import {{ test }} from "vitest";

test("broken", () => {{
    const x = fn({{ db }} as {cast_kw});
    }}  // extra closing brace
}});
"""
        test_file_path = self.repo_root / "test" / "broken.test.ts"
        test_file_path.parent.mkdir(parents=True)
        test_file_path.write_text(test_content)
        
        trigger = f"    const x = fn({{ db }} as {cast_kw});"
        
        result = tdd_runner.classify_callee(
            file_path="test/broken.test.ts",
            trigger_line=trigger,
            symbol_to_impl_map={},
            repo_root=str(self.repo_root)
        )
        
        # Should warn about unbalanced braces/parens
        self.assertIsNone(result.rejected)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("unbalanced", result.warnings[0].lower())


if __name__ == "__main__":
    unittest.main()

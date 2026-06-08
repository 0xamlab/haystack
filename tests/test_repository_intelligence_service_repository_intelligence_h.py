"""Tests for repository_intelligence_service: repository_intelligence_h.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_repository_intelligence_rust_resolve_child_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_child_module(
        *,
        current_file: str,
        module_name: str,
        module_index: dict[str, str],
    ) -> str | None:
        observed["current_file"] = current_file
        observed["module_name"] = module_name
        observed["module_index"] = module_index
        return "src/util/mod.rs"

    monkeypatch.setattr(
        repository_service.rust_adapter,
        "resolve_child_module",
        _fake_resolve_child_module,
    )

    module_index = {"src/util": "src/util/mod.rs"}

    result = repository_service._resolve_rust_child_module(
        current_file="src/main.rs",
        module_name="util",
        module_index=module_index,
    )

    assert result == "src/util/mod.rs"
    assert observed["current_file"] == "src/main.rs"
    assert observed["module_name"] == "util"
    assert observed["module_index"] is module_index


def test_repository_intelligence_rust_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_module_path: Any,
        resolve_child_module: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_module_path"] = resolve_module_path
        observed["resolve_child_module"] = resolve_child_module
        return ()

    monkeypatch.setattr(
        repository_service.rust_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"crate": "src/lib.rs"}

    result = repository_service._parse_rust_dependencies_only(
        "src/main.rs",
        "use crate::util;",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/main.rs"
    assert observed["text"] == "use crate::util;"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_module_path"] is repository_service._resolve_rust_module_path
    assert observed["resolve_child_module"] is repository_service._resolve_rust_child_module


def test_repository_intelligence_rust_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_module_path: Any,
        resolve_child_module: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_module_path"] = resolve_module_path
        observed["resolve_child_module"] = resolve_child_module
        return (), (), ()

    monkeypatch.setattr(repository_service.rust_adapter, "parse_file", _fake_parse_file)

    module_index = {"crate": "src/lib.rs"}

    result = repository_service._parse_rust_file(
        "src/main.rs",
        "fn run() { helper(); }",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/main.rs"
    assert observed["text"] == "fn run() { helper(); }"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_module_path"] is repository_service._resolve_rust_module_path
    assert observed["resolve_child_module"] is repository_service._resolve_rust_child_module


def test_repository_intelligence_go_helpers_are_modularized() -> None:
    assert repository_service._GO_FUNC_DECL_RE is repository_service.go_adapter.FUNC_DECL_RE
    assert repository_service._GO_TYPE_DECL_RE is repository_service.go_adapter.TYPE_DECL_RE
    assert repository_service._GO_IMPORT_SPEC_RE is repository_service.go_adapter.IMPORT_SPEC_RE
    assert repository_service._GO_PACKAGE_RE is repository_service.go_adapter.PACKAGE_RE
    assert repository_service._GO_SELECTOR_CALL_RE is repository_service.go_adapter.SELECTOR_CALL_RE
    assert repository_service._GO_CALL_RE is repository_service.go_adapter.CALL_RE
    assert repository_service._GO_BUILTIN_CALL_NAMES is (
        repository_service.go_adapter.BUILTIN_CALL_NAMES
    )


def test_repository_intelligence_go_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(
        *,
        import_target: str,
        module_index: dict[str, str],
        workspace_go_module_index: dict[str, tuple[str, ...]],
        normalize_repository_relative_path: Any,
    ) -> str | None:
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["workspace_go_module_index"] = workspace_go_module_index
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        return "internal/service/service.go"

    monkeypatch.setattr(repository_service.go_adapter, "resolve_import", _fake_resolve_import)

    module_index = {"github.com/acme/service": "internal/service/service.go"}
    workspace_go_module_index = {"github.com/acme": ("internal",)}

    result = repository_service._resolve_go_import(
        import_target="github.com/acme/service",
        module_index=module_index,
        workspace_go_module_index=workspace_go_module_index,
    )

    assert result == "internal/service/service.go"
    assert observed["import_target"] == "github.com/acme/service"
    assert observed["module_index"] is module_index
    assert observed["workspace_go_module_index"] is workspace_go_module_index
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )


def test_repository_intelligence_go_package_alias_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_package_symbol_alias(
        *,
        file_path: str,
        package_name: str,
        symbol_name: str,
        normalize_repository_relative_path: Any,
    ) -> str:
        observed["file_path"] = file_path
        observed["package_name"] = package_name
        observed["symbol_name"] = symbol_name
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        return "go::internal/service::service::Run"

    monkeypatch.setattr(
        repository_service.go_adapter,
        "package_symbol_alias",
        _fake_package_symbol_alias,
    )

    result = repository_service._go_package_symbol_alias(
        file_path="internal/service/service.go",
        package_name="service",
        symbol_name="Run",
    )

    assert result == "go::internal/service::service::Run"
    assert observed["file_path"] == "internal/service/service.go"
    assert observed["package_name"] == "service"
    assert observed["symbol_name"] == "Run"
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )


def test_repository_intelligence_go_module_index_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_extend_module_index_with_package_symbol_aliases(
        *,
        root_path: Path,
        file_paths: Sequence[str],
        index: dict[str, str],
        normalize_repository_relative_path: Any,
        is_test_path: Any,
    ) -> None:
        observed["root_path"] = root_path
        observed["file_paths"] = file_paths
        observed["index"] = index
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["is_test_path"] = is_test_path

    monkeypatch.setattr(
        repository_service.go_adapter,
        "extend_module_index_with_package_symbol_aliases",
        _fake_extend_module_index_with_package_symbol_aliases,
    )

    index: dict[str, str] = {}
    file_paths = ("internal/service/service.go",)

    repository_service._extend_module_index_with_go_package_symbol_aliases(
        root_path=tmp_path,
        file_paths=file_paths,
        index=index,
    )

    assert observed["root_path"] == tmp_path
    assert observed["file_paths"] == file_paths
    assert observed["index"] is index
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["is_test_path"] is repository_service._is_test_path


def test_repository_intelligence_go_augment_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_augment_package_symbol_references(
        *,
        analyses: Sequence[Any],
        stable_identifier: Any,
        prefer_non_test_package_candidates: Any,
        best_package_symbol_target: Any,
        normalize_repository_relative_path: Any,
    ) -> list[Any]:
        observed["analyses"] = analyses
        observed["stable_identifier"] = stable_identifier
        observed["prefer_non_test_package_candidates"] = prefer_non_test_package_candidates
        observed["best_package_symbol_target"] = best_package_symbol_target
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        return list(analyses)

    monkeypatch.setattr(
        repository_service.go_adapter,
        "augment_package_symbol_references",
        _fake_augment_package_symbol_references,
    )

    analyses: Sequence[Any] = ()

    result = repository_service._augment_go_package_symbol_references(analyses=analyses)

    assert result == []
    assert observed["analyses"] == analyses
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["prefer_non_test_package_candidates"] is (
        repository_service._prefer_non_test_package_candidates
    )
    assert observed["best_package_symbol_target"] is repository_service._best_package_symbol_target
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )


def test_repository_intelligence_go_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        workspace_go_module_index: dict[str, tuple[str, ...]],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["workspace_go_module_index"] = workspace_go_module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        return ()

    monkeypatch.setattr(
        repository_service.go_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"github.com/acme/service": "internal/service/service.go"}
    workspace_go_module_index = {"github.com/acme": ("internal",)}

    result = repository_service._parse_go_dependencies_only(
        "internal/service/service.go",
        'import "github.com/acme/service"',
        module_index,
        workspace_go_module_index,
    )

    assert result == ()
    assert observed["file_path"] == "internal/service/service.go"
    assert observed["text"] == 'import "github.com/acme/service"'
    assert observed["module_index"] is module_index
    assert observed["workspace_go_module_index"] is workspace_go_module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )


def test_repository_intelligence_go_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        workspace_go_module_index: dict[str, tuple[str, ...]],
        *,
        stable_identifier: Any,
        normalize_repository_relative_path: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["workspace_go_module_index"] = workspace_go_module_index
        observed["stable_identifier"] = stable_identifier
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        return (), (), ()

    monkeypatch.setattr(repository_service.go_adapter, "parse_file", _fake_parse_file)

    module_index = {"github.com/acme/service": "internal/service/service.go"}
    workspace_go_module_index = {"github.com/acme": ("internal",)}

    result = repository_service._parse_go_file(
        "internal/service/service.go",
        "func Run() {}",
        module_index,
        workspace_go_module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "internal/service/service.go"
    assert observed["text"] == "func Run() {}"
    assert observed["module_index"] is module_index
    assert observed["workspace_go_module_index"] is workspace_go_module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )


def test_repository_intelligence_js_like_helpers_are_modularized() -> None:
    assert repository_service._JS_IMPORT_RE is repository_service.js_like_adapter.IMPORT_RE
    assert repository_service._JS_IMPORT_STATEMENT_RE is (
        repository_service.js_like_adapter.IMPORT_STATEMENT_RE
    )
    assert repository_service._JS_EXPORT_FROM_RE is repository_service.js_like_adapter.EXPORT_FROM_RE
    assert repository_service._JS_REQUIRE_ASSIGN_RE is (
        repository_service.js_like_adapter.REQUIRE_ASSIGN_RE
    )
    assert repository_service._JS_IDENTIFIER_RE is repository_service.js_like_adapter.IDENTIFIER_RE
    assert repository_service._JS_SYMBOL_RE is repository_service.js_like_adapter.SYMBOL_RE
    assert repository_service._JS_FUNCTION_DECL_RE is (
        repository_service.js_like_adapter.FUNCTION_DECL_RE
    )
    assert repository_service._JS_CLASS_DECL_RE is repository_service.js_like_adapter.CLASS_DECL_RE
    assert repository_service._JS_INTERFACE_DECL_RE is (
        repository_service.js_like_adapter.INTERFACE_DECL_RE
    )
    assert repository_service._JS_TYPE_DECL_RE is repository_service.js_like_adapter.TYPE_DECL_RE
    assert repository_service._JS_ARROW_ASSIGN_RE is (
        repository_service.js_like_adapter.ARROW_ASSIGN_RE
    )
    assert repository_service._JS_FUNCTION_ASSIGN_RE is (
        repository_service.js_like_adapter.FUNCTION_ASSIGN_RE
    )
    assert repository_service._JS_CLASS_ASSIGN_RE is (
        repository_service.js_like_adapter.CLASS_ASSIGN_RE
    )
    assert repository_service._JS_CONST_DECL_RE is repository_service.js_like_adapter.CONST_DECL_RE
    assert repository_service._JS_METHOD_DECL_RE is (
        repository_service.js_like_adapter.METHOD_DECL_RE
    )
    assert repository_service._JS_CLASS_FIELD_ARROW_RE is (
        repository_service.js_like_adapter.CLASS_FIELD_ARROW_RE
    )
    assert repository_service._sanitize_js_like_line is (
        repository_service.js_like_adapter.sanitize_line
    )
    assert repository_service._match_js_like_symbol is (
        repository_service.js_like_adapter.match_symbol
    )
    assert repository_service._normalize_js_like_binding_name is (
        repository_service.js_like_adapter.normalize_binding_name
    )
    assert repository_service._parse_js_like_named_binding is (
        repository_service.js_like_adapter.parse_named_binding
    )
    assert repository_service._bindings_from_js_like_import_clause is (
        repository_service.js_like_adapter.bindings_from_import_clause
    )
    assert repository_service._iter_js_like_dependency_specs is (
        repository_service.js_like_adapter.iter_dependency_specs
    )
    assert repository_service._compile_js_like_reference_pattern is (
        repository_service.js_like_adapter.compile_reference_pattern
    )
    assert repository_service._js_like_symbol_reference_present is (
        repository_service.js_like_adapter.symbol_reference_present
    )
    assert repository_service._build_js_like_symbol_reference_candidates is (
        repository_service.js_like_adapter.build_symbol_reference_candidates
    )


def test_repository_intelligence_js_like_extract_import_bindings_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_extract_import_bindings(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        workspace_package_index: dict[str, tuple[str, ...]],
        *,
        resolve_import: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["workspace_package_index"] = workspace_package_index
        observed["resolve_import"] = resolve_import
        return ()

    monkeypatch.setattr(
        repository_service.js_like_adapter,
        "extract_import_bindings",
        _fake_extract_import_bindings,
    )

    module_index = {"./util": "src/util.ts"}
    workspace_package_index = {"pkg": ("src",)}

    result = repository_service._extract_js_like_import_bindings(
        file_path="src/app.ts",
        text="import { run } from './util';",
        module_index=module_index,
        workspace_package_index=workspace_package_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/app.ts"
    assert observed["text"] == "import { run } from './util';"
    assert observed["module_index"] is module_index
    assert observed["workspace_package_index"] is workspace_package_index
    assert observed["resolve_import"] is repository_service._resolve_js_like_import


def test_repository_intelligence_js_like_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        workspace_package_index: dict[str, tuple[str, ...]],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["workspace_package_index"] = workspace_package_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return ()

    monkeypatch.setattr(
        repository_service.js_like_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"./util": "src/util.ts"}
    workspace_package_index = {"pkg": ("src",)}

    result = repository_service._parse_js_like_dependencies_only(
        "src/app.ts",
        "import { run } from './util';",
        module_index,
        workspace_package_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/app.ts"
    assert observed["text"] == "import { run } from './util';"
    assert observed["module_index"] is module_index
    assert observed["workspace_package_index"] is workspace_package_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_js_like_import


def test_repository_intelligence_js_like_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        workspace_package_index: dict[str, tuple[str, ...]],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["workspace_package_index"] = workspace_package_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return (), (), ()

    monkeypatch.setattr(repository_service.js_like_adapter, "parse_file", _fake_parse_file)

    module_index = {"./util": "src/util.ts"}
    workspace_package_index = {"pkg": ("src",)}

    result = repository_service._parse_js_like_file(
        "src/app.ts",
        "export function run() {}",
        module_index,
        workspace_package_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/app.ts"
    assert observed["text"] == "export function run() {}"
    assert observed["module_index"] is module_index
    assert observed["workspace_package_index"] is workspace_package_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_js_like_import


def test_repository_intelligence_dart_helpers_are_modularized() -> None:
    assert repository_service._DART_IMPORT_DIRECTIVE_RE is (
        repository_service.dart_adapter.IMPORT_DIRECTIVE_RE
    )
    assert repository_service._DART_IMPORT_ALIAS_RE is (
        repository_service.dart_adapter.IMPORT_ALIAS_RE
    )
    assert repository_service._DART_IMPORT_SHOW_RE is repository_service.dart_adapter.IMPORT_SHOW_RE
    assert repository_service._DART_TYPE_DECL_RE is repository_service.dart_adapter.TYPE_DECL_RE
    assert repository_service._DART_EXTENSION_DECL_RE is (
        repository_service.dart_adapter.EXTENSION_DECL_RE
    )
    assert repository_service._DART_TYPEDEF_DECL_RE is (
        repository_service.dart_adapter.TYPEDEF_DECL_RE
    )
    assert repository_service._DART_TOP_LEVEL_FUNCTION_RE is (
        repository_service.dart_adapter.TOP_LEVEL_FUNCTION_RE
    )
    assert repository_service._DART_METHOD_DECL_RE is (
        repository_service.dart_adapter.METHOD_DECL_RE
    )
    assert repository_service._DART_SELECTOR_REFERENCE_RE is (
        repository_service.dart_adapter.SELECTOR_REFERENCE_RE
    )
    assert repository_service._DART_RESERVED_SYMBOL_NAMES is (
        repository_service.dart_adapter.RESERVED_SYMBOL_NAMES
    )
    assert repository_service._match_dart_symbol is repository_service.dart_adapter.match_symbol
    assert repository_service._iter_dart_import_directives is (
        repository_service.dart_adapter.iter_import_directives
    )


def test_repository_intelligence_dart_extract_import_bindings_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_extract_import_bindings(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[tuple[Any, ...], dict[str, Any]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return (), {}

    monkeypatch.setattr(
        repository_service.dart_adapter,
        "extract_import_bindings",
        _fake_extract_import_bindings,
    )

    module_index = {"package:acme/util.dart": "lib/src/util.dart"}

    result = repository_service._extract_dart_import_bindings(
        "lib/acme.dart",
        "import 'package:acme/util.dart' show Helper;",
        module_index,
    )

    assert result == ((), {})
    assert observed["file_path"] == "lib/acme.dart"
    assert observed["text"] == "import 'package:acme/util.dart' show Helper;"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_dart_import


def test_repository_intelligence_dart_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return ()

    monkeypatch.setattr(
        repository_service.dart_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"package:acme/util.dart": "lib/src/util.dart"}

    result = repository_service._parse_dart_dependencies_only(
        "lib/acme.dart",
        "import 'package:acme/util.dart' show Helper;",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "lib/acme.dart"
    assert observed["text"] == "import 'package:acme/util.dart' show Helper;"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_dart_import


def test_repository_intelligence_dart_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return (), (), ()

    monkeypatch.setattr(repository_service.dart_adapter, "parse_file", _fake_parse_file)

    module_index = {"package:acme/util.dart": "lib/src/util.dart"}

    result = repository_service._parse_dart_file(
        "lib/acme.dart",
        "class Helper {}",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "lib/acme.dart"
    assert observed["text"] == "class Helper {}"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_dart_import


def test_repository_intelligence_c_family_helpers_are_modularized() -> None:
    assert repository_service._C_FAMILY_INCLUDE_RE is repository_service.c_family_adapter.INCLUDE_RE
    assert repository_service._C_FAMILY_ATTRIBUTE_RE is (
        repository_service.c_family_adapter.ATTRIBUTE_RE
    )
    assert repository_service._C_FAMILY_TYPE_DECL_RE is (
        repository_service.c_family_adapter.TYPE_DECL_RE
    )
    assert repository_service._C_FAMILY_FUNCTION_DECL_RE is (
        repository_service.c_family_adapter.FUNCTION_DECL_RE
    )
    assert repository_service._C_FAMILY_SCOPED_REFERENCE_RE is (
        repository_service.c_family_adapter.SCOPED_REFERENCE_RE
    )
    assert repository_service._C_FAMILY_CALL_RE is repository_service.c_family_adapter.CALL_RE
    assert repository_service._C_FAMILY_NON_OPERATIONAL_REFERENCE_NAMES is (
        repository_service.c_family_adapter.NON_OPERATIONAL_REFERENCE_NAMES
    )
    assert repository_service._C_FAMILY_DECLARATION_PREFIX_KEYWORDS is (
        repository_service.c_family_adapter.DECLARATION_PREFIX_KEYWORDS
    )
    assert repository_service._strip_c_family_comments is (
        repository_service.c_family_adapter.strip_comments
    )
    assert repository_service._strip_c_family_attributes is (
        repository_service.c_family_adapter.strip_attributes
    )
    assert repository_service._normalize_c_family_symbol_name is (
        repository_service.c_family_adapter.normalize_symbol_name
    )
    assert repository_service._is_c_family_macro_like_symbol_name is (
        repository_service.c_family_adapter.is_macro_like_symbol_name
    )
    assert repository_service._is_c_family_operational_reference_name is (
        repository_service.c_family_adapter.is_operational_reference_name
    )



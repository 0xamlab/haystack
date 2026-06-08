from __future__ import annotations

from collections.abc import Iterable
from pathlib import PurePosixPath

from apps.api_server.services import (
    repository_intelligence_js_resolution as repository_js_resolution,
)
from apps.api_server.services import (
    repository_intelligence_module_aliases as repository_module_aliases,
)
from apps.api_server.services import (
    repository_intelligence_native_dispatch as repository_native_dispatch,
)
from apps.api_server.services import (
    repository_intelligence_package_symbol_resolution as repository_package_symbol_resolution,
)
from apps.api_server.services.repository_intelligence_adapters import (
    c_family as c_family_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    clojure as clojure_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    crystal as crystal_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    csharp as csharp_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    elixir as elixir_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    erlang as erlang_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    go_language as go_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    js_like as js_like_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    julia as julia_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import jvm as jvm_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    lua as lua_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    mojo_language as mojo_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    nim as nim_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    perl as perl_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    php as php_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    powershell as powershell_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    python_language as python_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    r_language as r_language_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    ruby as ruby_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    rust_language as rust_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    shell as shell_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    swift as swift_adapter,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _JSImportBinding,
)
from apps.api_server.services.repository_intelligence_indexing import (
    _module_index_values,
    _normalize_repository_relative_path,
    _resolve_directory_prefix_match,
    _resolve_suffix_match,
)
from apps.api_server.services.repository_intelligence_shared import _stable_identifier

_resolve_js_like_import = repository_js_resolution._resolve_js_like_import
_prefer_non_test_package_candidates = (
    repository_module_aliases._prefer_non_test_package_candidates
)
_resolve_zig_import = repository_module_aliases._resolve_zig_import
_resolve_haskell_import = repository_module_aliases._resolve_haskell_import
_resolve_ocaml_module = repository_module_aliases._resolve_ocaml_module

_resolve_fortran_import = repository_native_dispatch._resolve_fortran_import
_resolve_ada_import = repository_native_dispatch._resolve_ada_import
_resolve_cobol_import = repository_native_dispatch._resolve_cobol_import
_resolve_d_import = repository_native_dispatch._resolve_d_import
_resolve_visual_basic_import = repository_native_dispatch._resolve_visual_basic_import
_resolve_classic_visual_basic_target = (
    repository_native_dispatch._resolve_classic_visual_basic_target
)
_resolve_abap_include = repository_native_dispatch._resolve_abap_include
_resolve_abap_target = repository_native_dispatch._resolve_abap_target
_resolve_symbol_reference_target = (
    repository_package_symbol_resolution._resolve_symbol_reference_target
)
_best_package_symbol_target = repository_package_symbol_resolution._best_package_symbol_target
_augment_go_package_symbol_references = (
    repository_package_symbol_resolution._augment_go_package_symbol_references
)
_augment_r_package_symbol_references = (
    repository_package_symbol_resolution._augment_r_package_symbol_references
)
_augment_julia_package_symbol_references = (
    repository_package_symbol_resolution._augment_julia_package_symbol_references
)
_crystal_constant_aliases_for_file = crystal_adapter.constant_aliases_for_file
_scala_current_package = jvm_adapter.scala_current_package
_iter_scala_import_targets = jvm_adapter.iter_scala_import_targets
_is_julia_operational_reference_name = julia_adapter.is_operational_reference_name


def _extract_js_like_import_bindings(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    workspace_package_index: dict[str, tuple[str, ...]],
) -> tuple[_JSImportBinding, ...]:
    return js_like_adapter.extract_import_bindings(
        file_path,
        text,
        module_index,
        workspace_package_index,
        resolve_import=_resolve_js_like_import,
    )


def _resolve_python_import(
    *,
    current_file: str,
    module: str | None,
    level: int,
    name: str | None,
    module_index: dict[str, str],
) -> str | None:
    return python_adapter.resolve_import(
        current_file=current_file,
        module=module,
        level=level,
        name=name,
        module_index=module_index,
    )


def _resolve_rust_module_path(
    *,
    current_file: str,
    module_path: str,
    module_index: dict[str, str],
) -> str | None:
    return rust_adapter.resolve_module_path(
        current_file=current_file,
        module_path=module_path,
        module_index=module_index,
    )


def _resolve_rust_child_module(
    *,
    current_file: str,
    module_name: str,
    module_index: dict[str, str],
) -> str | None:
    return rust_adapter.resolve_child_module(
        current_file=current_file,
        module_name=module_name,
        module_index=module_index,
    )


def _candidate_c_family_module_keys(base_path: str) -> tuple[str, ...]:
    return c_family_adapter.candidate_module_keys(
        base_path,
        normalize_repository_relative_path=_normalize_repository_relative_path,
    )


def _resolve_go_import(
    *,
    import_target: str,
    module_index: dict[str, str],
    workspace_go_module_index: dict[str, tuple[str, ...]],
) -> str | None:
    return go_adapter.resolve_import(
        import_target=import_target,
        module_index=module_index,
        workspace_go_module_index=workspace_go_module_index,
        normalize_repository_relative_path=_normalize_repository_relative_path,
    )


def _resolve_dart_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
) -> str | None:
    normalized_target = import_target.strip()
    if not normalized_target or normalized_target.startswith("dart:"):
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    if normalized_target.startswith("package:"):
        return None
    current_dir = _normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    relative_target = _normalize_repository_relative_path(
        str(PurePosixPath(current_dir) / normalized_target)
    )
    if not relative_target:
        return None
    return module_index.get(relative_target)


def _resolve_clojure_import(import_target: str, module_index: dict[str, str]) -> str | None:
    return clojure_adapter.resolve_import(
        import_target,
        module_index,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_c_family_include(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
) -> str | None:
    return c_family_adapter.resolve_include(
        current_file=current_file,
        import_target=import_target,
        module_index=module_index,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


_strip_c_family_comments = c_family_adapter.strip_comments
_strip_c_family_attributes = c_family_adapter.strip_attributes
_normalize_c_family_symbol_name = c_family_adapter.normalize_symbol_name
_is_c_family_macro_like_symbol_name = c_family_adapter.is_macro_like_symbol_name
_is_c_family_operational_reference_name = c_family_adapter.is_operational_reference_name


def _resolve_mojo_import(import_target: str, module_index: dict[str, str]) -> str | None:
    return mojo_adapter.resolve_import(import_target, module_index)


def _resolve_julia_include(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
) -> str | None:
    return julia_adapter.resolve_include(
        current_file=current_file,
        import_target=import_target,
        module_index=module_index,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_julia_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
) -> str | None:
    return julia_adapter.resolve_import(
        current_file=current_file,
        import_target=import_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_erlang_module(import_target: str, module_index: dict[str, str]) -> str | None:
    return erlang_adapter.resolve_module(
        import_target,
        module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_erlang_include(
    *,
    current_file: str,
    import_target: str,
    is_lib: bool,
    module_index: dict[str, str],
) -> str | None:
    return erlang_adapter.resolve_include(
        current_file=current_file,
        import_target=import_target,
        is_lib=is_lib,
        module_index=module_index,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_lua_import(import_target: str, module_index: dict[str, str]) -> str | None:
    return lua_adapter.resolve_import(
        import_target,
        module_index=module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_shell_source(
    *,
    current_file: str,
    source_target: str,
    module_index: dict[str, str],
) -> str | None:
    return shell_adapter.resolve_source(
        current_file=current_file,
        source_target=source_target,
        module_index=module_index,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_powershell_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
) -> str | None:
    return powershell_adapter.resolve_import(
        current_file=current_file,
        import_target=import_target,
        module_index=module_index,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_nim_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
) -> str | None:
    return nim_adapter.resolve_import(
        current_file=current_file,
        import_target=import_target,
        module_index=module_index,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_ruby_import(
    *,
    current_file: str,
    import_target: str,
    is_relative: bool,
    module_index: dict[str, str],
) -> str | None:
    return ruby_adapter.resolve_import(
        current_file=current_file,
        import_target=import_target,
        is_relative=is_relative,
        module_index=module_index,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_crystal_import_targets(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
) -> tuple[str | None, ...]:
    return crystal_adapter.resolve_import_targets(
        current_file=current_file,
        import_target=import_target,
        module_index=module_index,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
        module_index_values=_module_index_values,
    )


def _resolve_perl_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
) -> str | None:
    return perl_adapter.resolve_import(
        current_file=current_file,
        import_target=import_target,
        module_index=module_index,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _extract_perl_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    return perl_adapter.extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _iter_perl_imported_symbol_targets(
    snippet: str,
    import_bindings: dict[str, _ImportedSymbolBinding],
) -> Iterable[tuple[_ImportedSymbolBinding, str, int]]:
    return perl_adapter.iter_imported_symbol_targets(snippet, import_bindings)


def _resolve_r_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
) -> str | None:
    return r_language_adapter.resolve_import(
        current_file=current_file,
        import_target=import_target,
        module_index=module_index,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_php_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
) -> str | None:
    return php_adapter.resolve_import(
        current_file=current_file,
        import_target=import_target,
        module_index=module_index,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_php_same_namespace_reference(
    *,
    current_namespace: str,
    target_name: str,
    module_index: dict[str, str],
) -> str | None:
    return php_adapter.resolve_same_namespace_reference(
        current_namespace=current_namespace,
        target_name=target_name,
        module_index=module_index,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_php_reference_target(
    *,
    current_file: str,
    token: str,
    import_bindings: dict[str, _ImportedSymbolBinding],
    current_namespace: str,
    module_index: dict[str, str],
) -> tuple[str | None, tuple[str, ...]]:
    return php_adapter.resolve_reference_target(
        current_file=current_file,
        token=token,
        import_bindings=import_bindings,
        current_namespace=current_namespace,
        module_index=module_index,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _iter_php_reference_targets(
    *,
    file_path: str,
    symbol_name: str,
    snippet: str,
    leading_docblock: str,
    import_bindings: dict[str, _ImportedSymbolBinding],
    current_namespace: str,
    module_index: dict[str, str],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    return php_adapter.iter_reference_targets(
        file_path=file_path,
        symbol_name=symbol_name,
        snippet=snippet,
        leading_docblock_text=leading_docblock,
        import_bindings=import_bindings,
        current_namespace=current_namespace,
        module_index=module_index,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_elixir_import(import_target: str, module_index: dict[str, str]) -> str | None:
    return elixir_adapter.resolve_import(
        import_target,
        module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_jvm_import(import_target: str, module_index: dict[str, str]) -> str | None:
    return jvm_adapter.resolve_import(
        import_target,
        module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_swift_import(import_target: str, module_index: dict[str, str]) -> str | None:
    return swift_adapter.resolve_import(
        import_target,
        module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _resolve_swift_same_target_reference(
    *,
    current_file: str,
    type_name: str,
    module_index: dict[str, str],
) -> str | None:
    return swift_adapter.resolve_same_target_reference(
        current_file=current_file,
        type_name=type_name,
        module_index=module_index,
        module_index_values=_module_index_values,
    )


def _resolve_csharp_import(import_target: str, module_index: dict[str, str]) -> str | None:
    return csharp_adapter.resolve_import(
        import_target,
        module_index,
        resolve_suffix_match=_resolve_suffix_match,
        resolve_directory_prefix_match=_resolve_directory_prefix_match,
    )


def _resolve_csharp_import_for_file(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
) -> str | None:
    return csharp_adapter.resolve_import_for_file(
        current_file=current_file,
        import_target=import_target,
        module_index=module_index,
        resolve_import=_resolve_csharp_import,
        normalize_repository_relative_path=_normalize_repository_relative_path,
    )


def _resolve_csharp_same_namespace_reference(
    *,
    current_file: str,
    current_namespace: str,
    type_name: str,
    module_index: dict[str, str],
) -> str | None:
    return csharp_adapter.resolve_same_namespace_reference(
        current_file=current_file,
        current_namespace=current_namespace,
        type_name=type_name,
        module_index=module_index,
        resolve_import=_resolve_csharp_import,
    )


def _is_r_operational_reference_name(target_name: str) -> bool:
    return r_language_adapter.is_operational_reference_name(target_name)


def _is_go_operational_reference_name(target_name: str) -> bool:
    return go_adapter.is_operational_reference_name(target_name)

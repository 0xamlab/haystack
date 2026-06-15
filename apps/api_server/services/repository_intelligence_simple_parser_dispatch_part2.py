# ruff: noqa: I001
from __future__ import annotations
from apps.api_server.services.repository_intelligence_simple_parser_dispatch import (
    _Dependency, _ImportedSymbolBinding, _Symbol, _SymbolReferenceCandidate, _module_index_aliases_for_file,
    _normalize_repository_relative_path, _resolve_dart_import, _resolve_directory_prefix_match, _resolve_haskell_import, _resolve_mojo_import,
    _resolve_ocaml_module, _resolve_rust_child_module, _resolve_rust_module_path, _resolve_suffix_match, _stable_identifier,
    autohotkey_adapter, coffeescript_adapter, dart_adapter, gams_adapter, gleam_adapter,
    go_adapter, haskell_adapter, haxe_adapter, julia_adapter, mojo_adapter,
    mql5_adapter, nim_adapter, nix_adapter, nushell_adapter, ocaml_adapter,
    openscad_adapter, purescript_adapter, rust_adapter, smalltalk_adapter, starlark_adapter,
    v_adapter, vala_adapter, vimscript_adapter,
)
def _parse_coffeescript_dependencies_only(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[_Dependency, ...]:
    return coffeescript_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_mojo_dependencies_only(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[_Dependency, ...]:
    return mojo_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_mojo_import,
    )


def _parse_rust_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return rust_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_module_path=_resolve_rust_module_path,
        resolve_child_module=_resolve_rust_child_module,
    )


def _parse_go_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    workspace_go_module_index: dict[str, tuple[str, ...]],
) -> tuple[_Dependency, ...]:
    return go_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        workspace_go_module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
    )


def _extract_dart_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    return dart_adapter.extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_dart_import,
    )


def _parse_dart_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return dart_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_dart_import,
    )


def _parse_dart_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return dart_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_dart_import,
    )


def _parse_haskell_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return haskell_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_haskell_import,
    )


def _parse_haskell_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return haskell_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_haskell_import,
    )


def _parse_ocaml_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return ocaml_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_module=_resolve_ocaml_module,
    )


def _parse_ocaml_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return ocaml_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_module=_resolve_ocaml_module,
    )


def _parse_julia_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return julia_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_autohotkey_file(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return autohotkey_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_autohotkey_dependencies_only(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[_Dependency, ...]:
    return autohotkey_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_julia_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return julia_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_vala_dependencies_only(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[_Dependency, ...]:
    return vala_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=lambda import_target, module_index: vala_adapter.resolve_import(
            import_target,
            module_index=module_index,
            resolve_suffix_match=_resolve_suffix_match,
            resolve_directory_prefix_match=_resolve_directory_prefix_match,
        ),
    )


def _parse_mql5_dependencies_only(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[_Dependency, ...]:
    return mql5_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_gams_dependencies_only(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[_Dependency, ...]:
    return gams_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_nix_dependencies_only(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[_Dependency, ...]:
    return nix_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_nushell_dependencies_only(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[_Dependency, ...]:
    return nushell_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_openscad_dependencies_only(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[_Dependency, ...]:
    return openscad_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_purescript_dependencies_only(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[_Dependency, ...]:
    return purescript_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_gleam_dependencies_only(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[_Dependency, ...]:
    return gleam_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_haxe_dependencies_only(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[_Dependency, ...]:
    return haxe_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_v_dependencies_only(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[_Dependency, ...]:
    return v_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_smalltalk_dependencies_only(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[_Dependency, ...]:
    return smalltalk_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
    )


def _parse_starlark_dependencies_only(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[_Dependency, ...]:
    return starlark_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_vimscript_dependencies_only(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[_Dependency, ...]:
    return vimscript_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_nim_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return nim_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
        module_index_aliases_for_file=_module_index_aliases_for_file,
    )


def _parse_nim_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return nim_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
        module_index_aliases_for_file=_module_index_aliases_for_file,
    )

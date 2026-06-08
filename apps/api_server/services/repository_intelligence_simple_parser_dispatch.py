from __future__ import annotations

from apps.api_server.services import (
    repository_intelligence_js_resolution as repository_js_resolution,
)
from apps.api_server.services import (
    repository_intelligence_language_resolution as repository_language_resolution,
)
from apps.api_server.services.repository_intelligence_adapters import (
    autohotkey as autohotkey_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    c_family as c_family_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    coffeescript as coffeescript_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    dart_language as dart_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import gams as gams_adapter
from apps.api_server.services.repository_intelligence_adapters import gleam as gleam_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    go_language as go_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    haskell as haskell_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import haxe as haxe_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    js_like as js_like_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    julia as julia_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    mojo_language as mojo_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import mql5 as mql5_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    nim as nim_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import nix as nix_adapter
from apps.api_server.services.repository_intelligence_adapters import nushell as nushell_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    ocaml as ocaml_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    openscad as openscad_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    purescript as purescript_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    python_language as python_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    rust_language as rust_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    smalltalk as smalltalk_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    starlark as starlark_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import vala as vala_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    vimscript as vimscript_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import vlang as v_adapter
from apps.api_server.services.repository_intelligence_adapters import (
    zig as zig_adapter,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)
from apps.api_server.services.repository_intelligence_indexing import (
    _module_index_aliases_for_file,
    _normalize_repository_relative_path,
    _resolve_directory_prefix_match,
    _resolve_suffix_match,
)
from apps.api_server.services.repository_intelligence_shared import _stable_identifier

_resolve_js_like_import = repository_js_resolution._resolve_js_like_import

(
    _resolve_python_import,
    _resolve_rust_module_path,
    _resolve_rust_child_module,
    _candidate_c_family_module_keys,
    _resolve_go_import,
    _resolve_dart_import,
    _resolve_c_family_include,
    _resolve_mojo_import,
    _resolve_haskell_import,
    _resolve_ocaml_module,
    _resolve_zig_import,
) = (
    repository_language_resolution._resolve_python_import,
    repository_language_resolution._resolve_rust_module_path,
    repository_language_resolution._resolve_rust_child_module,
    repository_language_resolution._candidate_c_family_module_keys,
    repository_language_resolution._resolve_go_import,
    repository_language_resolution._resolve_dart_import,
    repository_language_resolution._resolve_c_family_include,
    repository_language_resolution._resolve_mojo_import,
    repository_language_resolution._resolve_haskell_import,
    repository_language_resolution._resolve_ocaml_module,
    repository_language_resolution._resolve_zig_import,
)


def _parse_python_file(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return python_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_python_import,
    )


def _parse_rust_use_targets(path_expression: str) -> list[tuple[str, str]]:
    return rust_adapter.parse_use_targets(path_expression)


def _extract_go_import_specs(text: str) -> list[tuple[str | None, str]]:
    return go_adapter.extract_import_specs(text)


def _extract_mojo_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    return mojo_adapter.extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_mojo_import,
    )


def _parse_rust_file(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return rust_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_module_path=_resolve_rust_module_path,
        resolve_child_module=_resolve_rust_child_module,
    )


def _parse_go_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    workspace_go_module_index: dict[str, tuple[str, ...]],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return go_adapter.parse_file(
        file_path,
        text,
        module_index,
        workspace_go_module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
    )


def _parse_js_like_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    workspace_package_index: dict[str, tuple[str, ...]],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return js_like_adapter.parse_file(
        file_path,
        text,
        module_index,
        workspace_package_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_js_like_import,
    )


def _parse_coffeescript_file(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return coffeescript_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_vala_file(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return vala_adapter.parse_file(
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


def _parse_mql5_file(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return mql5_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_gams_file(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return gams_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_nix_file(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return nix_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_nushell_file(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return nushell_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_openscad_file(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return openscad_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_purescript_file(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return purescript_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_gleam_file(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return gleam_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_haxe_file(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return haxe_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_v_file(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return v_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_smalltalk_file(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return smalltalk_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
    )


def _parse_starlark_file(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return starlark_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_vimscript_file(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return vimscript_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        resolve_suffix_match=_resolve_suffix_match,
    )


def _parse_mojo_file(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return mojo_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_mojo_import,
    )


def _parse_python_dependencies_only(
    file_path: str, text: str, module_index: dict[str, str]
) -> tuple[_Dependency, ...]:
    return python_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_python_import,
    )


def _parse_c_family_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return c_family_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_include=_resolve_c_family_include,
    )


def _parse_c_family_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return c_family_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_include=_resolve_c_family_include,
    )


def _parse_zig_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    return zig_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_zig_import,
    )


def _extract_zig_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    return zig_adapter.extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_zig_import,
    )


def _parse_zig_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    return zig_adapter.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_zig_import,
    )


def _parse_js_like_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    workspace_package_index: dict[str, tuple[str, ...]],
) -> tuple[_Dependency, ...]:
    return js_like_adapter.parse_dependencies_only(
        file_path,
        text,
        module_index,
        workspace_package_index,
        stable_identifier=_stable_identifier,
        resolve_import=_resolve_js_like_import,
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

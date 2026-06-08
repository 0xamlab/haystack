from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from apps.api_server.services import (
    repository_intelligence_root_scoped_aliases as repository_root_scoped_aliases,
)
from apps.api_server.services.repository_intelligence_adapters import (
    clojure as clojure_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    crystal as crystal_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    elixir as elixir_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    fsharp as fsharp_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    go_language as go_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    haskell as haskell_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    julia as julia_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    ocaml as ocaml_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    perl as perl_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    php as php_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    r_language as r_language_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    zig as zig_adapter,
)
from apps.api_server.services.repository_intelligence_config import (
    _extend_module_index_with_dart_package_aliases,
    _extend_module_index_with_tsconfig_aliases,
    _extend_module_index_with_zig_build_aliases,
)
from apps.api_server.services.repository_intelligence_contracts import _Symbol
from apps.api_server.services.repository_intelligence_indexing import (
    _build_module_index as _build_module_index_base,
)
from apps.api_server.services.repository_intelligence_indexing import (
    _normalize_repository_relative_path,
    _resolve_suffix_match,
)
from apps.api_server.services.repository_intelligence_patch_analysis import _is_test_path
from apps.api_server.services.repository_intelligence_shared import _stable_identifier

_nim_declared_symbol_aliases_for_path = (
    repository_root_scoped_aliases._nim_declared_symbol_aliases_for_path
)
_camelize_identifier = repository_root_scoped_aliases._camelize_identifier
_r_package_context_for_path = repository_root_scoped_aliases._r_package_context_for_path
_julia_package_context_for_path = (
    repository_root_scoped_aliases._julia_package_context_for_path
)
_r_module_aliases_for_path = repository_root_scoped_aliases._r_module_aliases_for_path
_julia_module_aliases_for_path = (
    repository_root_scoped_aliases._julia_module_aliases_for_path
)
_clojure_module_aliases_for_path = (
    repository_root_scoped_aliases._clojure_module_aliases_for_path
)
_lisp_module_aliases_for_path = repository_root_scoped_aliases._lisp_module_aliases_for_path
_racket_module_aliases_for_path = (
    repository_root_scoped_aliases._racket_module_aliases_for_path
)
_lua_module_aliases_for_path = repository_root_scoped_aliases._lua_module_aliases_for_path
_erlang_module_aliases_for_path = repository_root_scoped_aliases._erlang_module_aliases_for_path
_elixir_module_aliases_for_path = (
    repository_root_scoped_aliases._elixir_module_aliases_for_path
)
_normalize_fortran_name = repository_root_scoped_aliases._normalize_fortran_name
_normalize_ada_unit_name = repository_root_scoped_aliases._normalize_ada_unit_name
_strip_ada_comments = repository_root_scoped_aliases._strip_ada_comments
_collect_ada_symbol_entries = repository_root_scoped_aliases._collect_ada_symbol_entries
_normalize_d_module_name = repository_root_scoped_aliases._normalize_d_module_name
_strip_d_comments = repository_root_scoped_aliases._strip_d_comments
_d_statement_entries = repository_root_scoped_aliases._d_statement_entries
_collect_d_symbol_entries = repository_root_scoped_aliases._collect_d_symbol_entries
_is_fortran_declared_symbol_alias = (
    repository_root_scoped_aliases._is_fortran_declared_symbol_alias
)
_fortran_statement_entries = repository_root_scoped_aliases._fortran_statement_entries
_collect_fortran_symbol_entries = (
    repository_root_scoped_aliases._collect_fortran_symbol_entries
)
_collect_fsharp_symbol_entries = repository_root_scoped_aliases._collect_fsharp_symbol_entries
_fsharp_module_aliases_for_path = (
    repository_root_scoped_aliases._fsharp_module_aliases_for_path
)
_abap_module_aliases_for_path = repository_root_scoped_aliases._abap_module_aliases_for_path
_ada_module_aliases_for_path = repository_root_scoped_aliases._ada_module_aliases_for_path
_apex_module_aliases_for_path = repository_root_scoped_aliases._apex_module_aliases_for_path
_assembly_module_aliases_for_path = (
    repository_root_scoped_aliases._assembly_module_aliases_for_path
)
_coffeescript_module_aliases_for_path = (
    repository_root_scoped_aliases._coffeescript_module_aliases_for_path
)
_vala_module_aliases_for_path = repository_root_scoped_aliases._vala_module_aliases_for_path
_mql5_module_aliases_for_path = repository_root_scoped_aliases._mql5_module_aliases_for_path
_gams_module_aliases_for_path = repository_root_scoped_aliases._gams_module_aliases_for_path
_nix_module_aliases_for_path = repository_root_scoped_aliases._nix_module_aliases_for_path
_v_module_aliases_for_path = repository_root_scoped_aliases._v_module_aliases_for_path
_prolog_module_aliases_for_path = (
    repository_root_scoped_aliases._prolog_module_aliases_for_path
)
_foxpro_module_aliases_for_path = repository_root_scoped_aliases._foxpro_module_aliases_for_path
_cobol_module_aliases_for_path = repository_root_scoped_aliases._cobol_module_aliases_for_path
_vbscript_module_aliases_for_path = (
    repository_root_scoped_aliases._vbscript_module_aliases_for_path
)
_applescript_module_aliases_for_path = (
    repository_root_scoped_aliases._applescript_module_aliases_for_path
)
_visual_basic_module_aliases_for_path = (
    repository_root_scoped_aliases._visual_basic_module_aliases_for_path
)
_classic_visual_basic_module_aliases_for_path = (
    repository_root_scoped_aliases._classic_visual_basic_module_aliases_for_path
)
_pascal_module_aliases_for_path = (
    repository_root_scoped_aliases._pascal_module_aliases_for_path
)
_sql_module_aliases_for_path = repository_root_scoped_aliases._sql_module_aliases_for_path
_tsql_module_aliases_for_path = repository_root_scoped_aliases._tsql_module_aliases_for_path
_ladder_module_aliases_for_path = (
    repository_root_scoped_aliases._ladder_module_aliases_for_path
)
_plsql_module_aliases_for_path = repository_root_scoped_aliases._plsql_module_aliases_for_path
_rpg_module_aliases_for_path = repository_root_scoped_aliases._rpg_module_aliases_for_path
_sas_module_aliases_for_path = repository_root_scoped_aliases._sas_module_aliases_for_path
_fortran_module_aliases_for_path = (
    repository_root_scoped_aliases._fortran_module_aliases_for_path
)
_matlab_module_aliases_for_path = (
    repository_root_scoped_aliases._matlab_module_aliases_for_path
)
_ml_module_aliases_for_path = repository_root_scoped_aliases._ml_module_aliases_for_path
_objective_c_module_aliases_for_path = (
    repository_root_scoped_aliases._objective_c_module_aliases_for_path
)
_wolfram_module_aliases_for_path = (
    repository_root_scoped_aliases._wolfram_module_aliases_for_path
)
_d_module_aliases_for_path = repository_root_scoped_aliases._d_module_aliases_for_path
_solidity_module_aliases_for_path = (
    repository_root_scoped_aliases._solidity_module_aliases_for_path
)
_actionscript_module_aliases_for_path = (
    repository_root_scoped_aliases._actionscript_module_aliases_for_path
)
_scratch_module_aliases_for_path = repository_root_scoped_aliases._scratch_module_aliases_for_path
_smalltalk_module_aliases_for_path = (
    repository_root_scoped_aliases._smalltalk_module_aliases_for_path
)
_gdscript_module_aliases_for_path = (
    repository_root_scoped_aliases._gdscript_module_aliases_for_path
)
_verilog_module_aliases_for_path = (
    repository_root_scoped_aliases._verilog_module_aliases_for_path
)
_systemverilog_module_aliases_for_path = (
    repository_root_scoped_aliases._systemverilog_module_aliases_for_path
)
_vhdl_module_aliases_for_path = repository_root_scoped_aliases._vhdl_module_aliases_for_path
_ROOT_SCOPED_MODULE_ALIAS_BUILDERS = (
    repository_root_scoped_aliases._ROOT_SCOPED_MODULE_ALIAS_BUILDERS
)
_is_crystal_constant_alias = crystal_adapter.is_constant_alias
_crystal_declared_type_aliases_for_path = crystal_adapter.declared_type_aliases_for_path
_normalize_haskell_source_line = haskell_adapter.normalize_source_line
_is_top_level_haskell_source_line = haskell_adapter.is_top_level_source_line
_haskell_module_aliases_for_path = repository_root_scoped_aliases._haskell_module_aliases_for_path
_ocaml_module_aliases_for_path = repository_root_scoped_aliases._ocaml_module_aliases_for_path
_nim_module_aliases_for_path = repository_root_scoped_aliases._nim_module_aliases_for_path
_is_nim_declared_symbol_alias = repository_root_scoped_aliases._is_nim_declared_symbol_alias
_extract_clojure_ns_form = clojure_adapter.extract_ns_form
_clojure_namespace_path = clojure_adapter.namespace_path
_perl_module_aliases_for_path = repository_root_scoped_aliases._perl_module_aliases_for_path
_fsharp_path_aliases = fsharp_adapter.path_aliases
_fsharp_namespaces_from_text = fsharp_adapter.namespaces_from_text
_fsharp_open_targets = fsharp_adapter.open_targets
_normalize_fsharp_symbol_name = fsharp_adapter.normalize_symbol_name
_normalize_fsharp_target = fsharp_adapter.normalize_target

_ruby_module_aliases_for_path = repository_root_scoped_aliases._ruby_module_aliases_for_path
_php_current_namespace = php_adapter.current_namespace
_php_leading_docblock = php_adapter.leading_docblock
_php_symbol_declaration_header = php_adapter.symbol_declaration_header
_php_doc_type_tokens = php_adapter.doc_type_tokens
_php_type_tokens_from_header = php_adapter.type_tokens_from_header
_php_module_aliases_for_path = php_adapter.module_aliases_for_path
_extract_perl_use_args = perl_adapter.extract_use_args
_is_perl_package_like = perl_adapter.is_package_like
_elixir_module_path_variants = elixir_adapter.module_path_variants

_r_package_name_from_text = r_language_adapter.package_name_from_text
_julia_project_name_from_text = julia_adapter.project_name_from_text


def _extend_module_index_with_r_package_symbol_aliases(
    *,
    root_path: Path,
    file_paths: Sequence[str],
    index: dict[str, str],
) -> None:
    r_language_adapter.extend_module_index_with_package_symbol_aliases(
        root_path=root_path,
        file_paths=file_paths,
        index=index,
        normalize_repository_relative_path=_normalize_repository_relative_path,
    )


def _go_current_package(text: str) -> str:
    return go_adapter.current_package(text)


def _go_declared_symbol_names(text: str) -> tuple[str, ...]:
    return go_adapter.declared_symbol_names(text)


def _go_package_symbol_alias(
    *,
    file_path: str,
    package_name: str,
    symbol_name: str,
) -> str:
    return go_adapter.package_symbol_alias(
        file_path=file_path,
        package_name=package_name,
        symbol_name=symbol_name,
        normalize_repository_relative_path=_normalize_repository_relative_path,
    )


def _prefer_non_test_package_candidates(
    *,
    source_file: str,
    candidates: Sequence[tuple[str, _Symbol]],
) -> Sequence[tuple[str, _Symbol]]:
    if _is_test_path(source_file):
        return candidates
    non_test_candidates = [
        (file_path, symbol)
        for file_path, symbol in candidates
        if not _is_test_path(file_path)
    ]
    return non_test_candidates or candidates


def _extend_module_index_with_go_package_symbol_aliases(
    *,
    root_path: Path,
    file_paths: Sequence[str],
    index: dict[str, str],
) -> None:
    go_adapter.extend_module_index_with_package_symbol_aliases(
        root_path=root_path,
        file_paths=file_paths,
        index=index,
        normalize_repository_relative_path=_normalize_repository_relative_path,
        is_test_path=_is_test_path,
    )

def _collect_type_symbol_entries(
    text: str,
    *,
    file_path: str,
    regex: re.Pattern[str],
) -> list[dict[str, Any]]:
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, int]] = set()
    final_line = len(text.splitlines()) if text else 1
    for match in regex.finditer(text):
        symbol_name = str(match.group("name") or "").strip()
        if not symbol_name:
            continue
        line_no = text.count("\n", 0, match.start()) + 1
        symbol_key = (symbol_name, line_no)
        if symbol_key in seen_symbol_keys:
            continue
        seen_symbol_keys.add(symbol_key)
        symbol_entries.append(
            {
                "symbol_id": _stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": symbol_name,
                        "line": line_no,
                        "kind": "type",
                    },
                ),
                "symbol_name": symbol_name,
                "symbol_kind": "type",
                "start_line": line_no,
                "end_line": line_no,
                "signature": symbol_name,
            }
        )
    for index, entry in enumerate(symbol_entries):
        if index + 1 < len(symbol_entries):
            entry["end_line"] = max(
                int(symbol_entries[index + 1]["start_line"]) - 1,
                int(entry["start_line"]),
            )
        else:
            entry["end_line"] = final_line
    return symbol_entries


def _candidate_zig_module_keys(current_file: str, import_target: str) -> tuple[str, ...]:
    return zig_adapter.candidate_module_keys(
        current_file,
        import_target,
        normalize_repository_relative_path=_normalize_repository_relative_path,
    )


def _resolve_zig_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
) -> str | None:
    return zig_adapter.resolve_import(
        current_file=current_file,
        import_target=import_target,
        module_index=module_index,
        normalize_repository_relative_path=_normalize_repository_relative_path,
    )


def _resolve_haskell_import(import_target: str, module_index: dict[str, str]) -> str | None:
    return haskell_adapter.resolve_import(
        import_target,
        module_index,
        normalize_repository_relative_path=_normalize_repository_relative_path,
    )


def _resolve_ocaml_module(import_target: str, module_index: dict[str, str]) -> str | None:
    return ocaml_adapter.resolve_module(
        import_target,
        module_index,
        resolve_suffix_match=_resolve_suffix_match,
    )


_elixir_module_path_variants = elixir_adapter.module_path_variants


_MODULE_INDEX_EXTENDERS = (
    _extend_module_index_with_tsconfig_aliases,
    _extend_module_index_with_dart_package_aliases,
    _extend_module_index_with_go_package_symbol_aliases,
    _extend_module_index_with_r_package_symbol_aliases,
    _extend_module_index_with_zig_build_aliases,
)


def _build_module_index(
    file_paths: Sequence[str], *, root_path: Path | None = None
) -> dict[str, str]:
    return _build_module_index_base(
        file_paths,
        root_path=root_path,
        root_scoped_module_alias_builders=_ROOT_SCOPED_MODULE_ALIAS_BUILDERS,
        module_index_extenders=_MODULE_INDEX_EXTENDERS,
    )

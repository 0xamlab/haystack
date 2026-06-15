from __future__ import annotations

import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import PurePosixPath
from types import ModuleType

from apps.api_server.services import repository_intelligence_adapters as repository_adapters
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


class _LazyAdapterModule:
    # ``_overrides`` lets callers (notably ``pytest``'s ``monkeypatch.setattr``) patch an
    # adapter attribute on the lazy wrapper without mutating the shared real adapter
    # module. Without it the ``__slots__`` layout rejects ``setattr`` outright, which
    # surfaced as setup/teardown ``AttributeError``s in the dispatch test suites.
    __slots__ = ("_adapter_name", "_overrides")

    def __init__(self, adapter_name: str) -> None:
        object.__setattr__(self, "_adapter_name", adapter_name)
        object.__setattr__(self, "_overrides", {})

    def _load(self):
        return getattr(repository_adapters, self._adapter_name)

    def __getattr__(self, name: str) -> object:
        overrides = object.__getattribute__(self, "_overrides")
        if name in overrides:
            return overrides[name]
        return getattr(self._load(), name)

    def __setattr__(self, name: str, value: object) -> None:
        if name in _LazyAdapterModule.__slots__:
            object.__setattr__(self, name, value)
            return
        object.__getattribute__(self, "_overrides")[name] = value

    def __delattr__(self, name: str) -> None:
        overrides = object.__getattribute__(self, "_overrides")
        if name in overrides:
            del overrides[name]
            return
        raise AttributeError(name)


def _lazy_adapter_module(adapter_name: str) -> _LazyAdapterModule:
    return _LazyAdapterModule(adapter_name)


@lru_cache(maxsize=1)
def _native_resolution_module() -> ModuleType:
    from apps.api_server.services import (
        repository_intelligence_native_resolution as repository_native_resolution,
    )

    return repository_native_resolution


# Native-resolution helpers are resolved lazily through ``__getattr__`` so importing this
# module does not pull in repository_intelligence_native_resolution (a behaviour the lazy-
# load test guards), while attribute access still returns the *real* function object so
# identity with native_resolution holds (the modularization test guards that).
_NATIVE_RESOLUTION_EXPORT_NAMES = frozenset(
    {
        "_symbols_from_entries",
        "_dependencies_from_specs",
        "_references_from_specs",
        "_resolve_assembly_import",
        "_resolve_assembly_target",
        "_resolve_prolog_import",
        "_resolve_prolog_target",
        "_resolve_abap_include",
        "_resolve_abap_target",
        "_resolve_sql_target",
        "_resolve_plsql_import",
        "_resolve_plsql_target",
        "_resolve_sas_include",
        "_resolve_sas_target",
        "_resolve_matlab_import",
        "_resolve_ml_import",
        "_resolve_matlab_target",
        "_resolve_d_import",
        "_resolve_fortran_import",
        "_resolve_ada_import",
        "_resolve_cobol_import",
        "_resolve_visual_basic_import",
        "_resolve_classic_visual_basic_target",
        "_resolve_foxpro_target",
        "_resolve_objective_c_import",
        "_resolve_objective_c_target",
    }
)


def __getattr__(name: str) -> Any:
    if name in _NATIVE_RESOLUTION_EXPORT_NAMES:
        return getattr(_native_resolution_module(), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


@lru_cache(maxsize=1)
def _applescript_parser_dispatch_module() -> ModuleType:
    from apps.api_server.services import (
        repository_intelligence_applescript_parser_dispatch as repository_applescript_parser_dispatch,
    )

    return repository_applescript_parser_dispatch


@lru_cache(maxsize=1)
def _vba_parser_dispatch_module() -> ModuleType:
    from apps.api_server.services import (
        repository_intelligence_vba_parser_dispatch as repository_vba_parser_dispatch,
    )

    return repository_vba_parser_dispatch


def _lazy_module_attr(module_loader: Callable[[], ModuleType], name: str) -> Callable[..., Any]:
    def _call(*args: Any, **kwargs: Any) -> Any:
        return getattr(module_loader(), name)(*args, **kwargs)

    return _call


abap_adapter = _lazy_adapter_module("abap")
ada_adapter = _lazy_adapter_module("ada")
assembly_adapter = _lazy_adapter_module("assembly")
classic_visual_basic_adapter = _lazy_adapter_module("classic_visual_basic")
cobol_adapter = _lazy_adapter_module("cobol")
d_language_adapter = _lazy_adapter_module("d_language")
emacslisp_adapter = _lazy_adapter_module("emacslisp")
fortran_adapter = _lazy_adapter_module("fortran")
foxpro_adapter = _lazy_adapter_module("foxpro")
fsharp_adapter = _lazy_adapter_module("fsharp")
lisp_adapter = _lazy_adapter_module("lisp")
matlab_adapter = _lazy_adapter_module("matlab")
ml_adapter = _lazy_adapter_module("ml")
objective_c_adapter = _lazy_adapter_module("objective_c")
plsql_adapter = _lazy_adapter_module("plsql")
prolog_adapter = _lazy_adapter_module("prolog")
racket_adapter = _lazy_adapter_module("racket")
sas_adapter = _lazy_adapter_module("sas")
scheme_adapter = _lazy_adapter_module("scheme")
sql_adapter = _lazy_adapter_module("sql")
tsql_adapter = _lazy_adapter_module("tsql")
visual_basic_adapter = _lazy_adapter_module("visual_basic")

_parse_applescript_dependencies_only = _lazy_module_attr(
    _applescript_parser_dispatch_module,
    "_parse_applescript_dependencies_only",
)
_parse_applescript_file = _lazy_module_attr(
    _applescript_parser_dispatch_module,
    "_parse_applescript_file",
)
_parse_vba_dependencies_only = _lazy_module_attr(
    _vba_parser_dispatch_module,
    "_parse_vba_dependencies_only",
)
_parse_vba_file = _lazy_module_attr(
    _vba_parser_dispatch_module,
    "_parse_vba_file",
)
_CLARITY_USE_TRAIT_RE = re.compile(
    r"\(\s*use-trait\s+(?P<alias>[A-Za-z_][A-Za-z0-9_-]*)\s+\.(?P<target>[A-Za-z0-9_.-]+)\s*\)"
)
_CLARITY_FUNCTION_RE = re.compile(
    r"\(\s*define-(?:public|private|read-only)\s+\((?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b"
)
_FREEBASIC_INCLUDE_RE = re.compile(
    r'(?im)^\s*#include(?:\s+once)?\s+"(?P<target>[^"\n]+)"'
)


def _virtualized_language_file_path(file_path: str, *, suffix: str) -> str:
    normalized_path = PurePosixPath(file_path)
    if normalized_path.suffix.lower() == suffix.lower():
        return file_path
    return str(normalized_path.with_suffix(suffix))


def _virtualized_suffix_module_index(
    module_index: dict[str, str],
    *,
    source_suffixes: tuple[str, ...],
    target_suffix: str,
) -> dict[str, str]:
    aliased_index = dict(module_index)
    for raw_key, target_file in tuple(module_index.items()):
        suffix = PurePosixPath(raw_key).suffix.lower()
        if suffix not in source_suffixes:
            continue
        aliased_index.setdefault(
            str(PurePosixPath(raw_key).with_suffix(target_suffix)),
            target_file,
        )
    return aliased_index


def _cached_classic_visual_basic_target_resolver(module_index: dict[str, str]):
    cache: dict[str, str | None] = {}

    def _resolve(reference_target: str) -> str | None:
        if reference_target in cache:
            return cache[reference_target]
        # Resolve via this module's attribute so it honours both the lazy ``__getattr__``
        # (real native_resolution function) and a ``monkeypatch.setattr`` on
        # ``native_dispatch._resolve_classic_visual_basic_target`` (the caching test).
        import sys

        resolver = getattr(
            sys.modules[__name__], "_resolve_classic_visual_basic_target"
        )
        resolved = resolver(reference_target, module_index)
        cache[reference_target] = resolved
        return resolved

    return _resolve


def _resolve_clarity_contract_target(
    import_target: str,
    module_index: dict[str, str],
) -> str | None:
    cleaned_target = str(import_target or "").strip().lstrip(".")
    if not cleaned_target:
        return None
    path_parts = tuple(part for part in cleaned_target.split(".") if part)
    if not path_parts:
        return None
    contract_parts = path_parts[:-1] or path_parts
    contract_name = contract_parts[-1]
    candidates = [
        f"{'/'.join(contract_parts)}.clar",
        f"{contract_name}.clar",
        f"contracts/{contract_name}.clar",
        f"contracts/{'/'.join(contract_parts)}.clar",
    ]
    for candidate in candidates:
        direct_match = module_index.get(candidate)
        if direct_match is not None:
            return direct_match
    for candidate in candidates:
        if "/" not in candidate:
            suffix = f"/{candidate}"
            for module_key, target_file in module_index.items():
                if module_key.endswith(suffix):
                    return target_file
    return None


def _clarity_symbols(file_path: str, text: str) -> tuple[_Symbol, ...]:
    normalized_path = PurePosixPath(file_path)
    symbols: list[_Symbol] = [
        _Symbol(
            symbol_id=_stable_identifier(
                "clarity_module",
                {"file_path": file_path, "symbol_name": normalized_path.stem},
            ),
            symbol_name=normalized_path.stem,
            symbol_kind="module",
            start_line=1,
            end_line=max(text.count("\n") + 1, 1),
            parent_symbol_id=None,
            signature=normalized_path.stem,
        )
    ]
    seen_names = {normalized_path.stem}
    for match in _CLARITY_FUNCTION_RE.finditer(text):
        symbol_name = str(match.group("name") or "").strip()
        if not symbol_name or symbol_name in seen_names:
            continue
        seen_names.add(symbol_name)
        line_number = text.count("\n", 0, match.start()) + 1
        symbols.append(
            _Symbol(
                symbol_id=_stable_identifier(
                    "clarity_symbol",
                    {"file_path": file_path, "symbol_name": symbol_name},
                ),
                symbol_name=symbol_name,
                symbol_kind="function",
                start_line=line_number,
                end_line=line_number,
                parent_symbol_id=None,
                signature=f"clarity {symbol_name}",
            )
        )
    return tuple(symbols)


def _clarity_dependencies(
    file_path: str,
    text: str,
    module_index: dict[str, str],
) -> tuple[_Dependency, ...]:
    dependencies: list[_Dependency] = []
    seen_targets: set[tuple[str | None, str | None]] = set()
    for match in _CLARITY_USE_TRAIT_RE.finditer(text):
        import_target = str(match.group("target") or "").strip()
        resolved_target = _resolve_clarity_contract_target(import_target, module_index)
        contract_name = import_target.split(".")[0] if import_target else None
        key = (resolved_target, contract_name)
        if key in seen_targets:
            continue
        seen_targets.add(key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=_stable_identifier(
                    "clarity_dependency",
                    {
                        "file_path": file_path,
                        "target_file": resolved_target,
                        "target_symbol": contract_name,
                    },
                ),
                source_file=file_path,
                target_file=resolved_target,
                target_symbol=contract_name,
                dependency_type="uses",
            )
        )
    return tuple(dependencies)


def _clarity_references(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    source_symbol_id: str,
) -> tuple[_SymbolReferenceCandidate, ...]:
    references: list[_SymbolReferenceCandidate] = []
    seen_targets: set[tuple[str | None, tuple[str, ...]]] = set()
    for match in _CLARITY_USE_TRAIT_RE.finditer(text):
        import_target = str(match.group("target") or "").strip()
        resolved_target = _resolve_clarity_contract_target(import_target, module_index)
        contract_name = import_target.split(".")[0] if import_target else ""
        target_names = (contract_name,) if contract_name else ()
        key = (resolved_target, target_names)
        if key in seen_targets:
            continue
        seen_targets.add(key)
        references.append(
            _SymbolReferenceCandidate(
                reference_edge_id=_stable_identifier(
                    "clarity_reference",
                    {
                        "file_path": file_path,
                        "target_file": resolved_target,
                        "target_names": target_names,
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=resolved_target,
                target_names=target_names,
                reference_type="references_symbol",
            )
        )
    return tuple(references)


# The per-language parser bodies live in repository_intelligence_native_parsers
# (split out to keep each module within the per-module line budget). Import them back
# so the registries below and external callers keep resolving them from this module.
from apps.api_server.services.repository_intelligence_native_parsers import (  # noqa: E402,E501
    _parse_abap_dependencies_only,
    _parse_abap_file,
    _parse_ada_dependencies_only,
    _parse_ada_file,
    _parse_assembly_dependencies_only,
    _parse_assembly_file,
    _parse_clarity_dependencies_only,
    _parse_clarity_file,
    _parse_classic_visual_basic_dependencies_only,
    _parse_classic_visual_basic_file,
    _parse_cobol_dependencies_only,
    _parse_cobol_file,
    _parse_d_dependencies_only,
    _parse_d_file,
    _parse_emacslisp_dependencies_only,
    _parse_emacslisp_file,
    _parse_fortran_dependencies_only,
    _parse_fortran_file,
    _parse_foxpro_dependencies_only,
    _parse_foxpro_file,
    _parse_freebasic_dependencies_only,
    _parse_freebasic_file,
    _parse_fsharp_dependencies_only,
    _parse_fsharp_file,
    _parse_lisp_dependencies_only,
    _parse_lisp_file,
    _parse_matlab_dependencies_only,
    _parse_matlab_file,
    _parse_ml_dependencies_only,
    _parse_ml_file,
    _parse_objective_c_dependencies_only,
    _parse_objective_c_file,
    _parse_plsql_dependencies_only,
    _parse_plsql_file,
    _parse_prolog_dependencies_only,
    _parse_prolog_file,
    _parse_racket_dependencies_only,
    _parse_racket_file,
    _parse_sas_dependencies_only,
    _parse_sas_file,
    _parse_scheme_dependencies_only,
    _parse_scheme_file,
    _parse_sql_dependencies_only,
    _parse_sql_file,
    _parse_tsql_dependencies_only,
    _parse_tsql_file,
    _parse_visual_basic_dependencies_only,
    _parse_visual_basic_file,
)


NATIVE_ADAPTER_DEPENDENCY_PARSERS = {
    "abap": _parse_abap_dependencies_only,
    "ada": _parse_ada_dependencies_only,
    "assembly": _parse_assembly_dependencies_only,
    "applescript": _parse_applescript_dependencies_only,
    "vb6": _parse_classic_visual_basic_dependencies_only,
    "vba": _parse_vba_dependencies_only,
    "cobol": _parse_cobol_dependencies_only,
    "d": _parse_d_dependencies_only,
    "foxpro": _parse_foxpro_dependencies_only,
    "fsharp": _parse_fsharp_dependencies_only,
    "fortran": _parse_fortran_dependencies_only,
    "freebasic": _parse_freebasic_dependencies_only,
    "lisp": _parse_lisp_dependencies_only,
    "clarity": _parse_clarity_dependencies_only,
    "emacslisp": _parse_emacslisp_dependencies_only,
    "scheme": _parse_scheme_dependencies_only,
    "racket": _parse_racket_dependencies_only,
    "matlab": _parse_matlab_dependencies_only,
    "ml": _parse_ml_dependencies_only,
    "objectivec": _parse_objective_c_dependencies_only,
    "plsql": _parse_plsql_dependencies_only,
    "prolog": _parse_prolog_dependencies_only,
    "sas": _parse_sas_dependencies_only,
    "sql": _parse_sql_dependencies_only,
    "tsql": _parse_tsql_dependencies_only,
    "vb": _parse_visual_basic_dependencies_only,
}

NATIVE_ADAPTER_FILE_PARSERS = {
    "abap": _parse_abap_file,
    "ada": _parse_ada_file,
    "assembly": _parse_assembly_file,
    "applescript": _parse_applescript_file,
    "vb6": _parse_classic_visual_basic_file,
    "vba": _parse_vba_file,
    "cobol": _parse_cobol_file,
    "d": _parse_d_file,
    "foxpro": _parse_foxpro_file,
    "fsharp": _parse_fsharp_file,
    "fortran": _parse_fortran_file,
    "freebasic": _parse_freebasic_file,
    "lisp": _parse_lisp_file,
    "clarity": _parse_clarity_file,
    "emacslisp": _parse_emacslisp_file,
    "scheme": _parse_scheme_file,
    "racket": _parse_racket_file,
    "matlab": _parse_matlab_file,
    "ml": _parse_ml_file,
    "objectivec": _parse_objective_c_file,
    "plsql": _parse_plsql_file,
    "prolog": _parse_prolog_file,
    "sas": _parse_sas_file,
    "sql": _parse_sql_file,
    "tsql": _parse_tsql_file,
    "vb": _parse_visual_basic_file,
}

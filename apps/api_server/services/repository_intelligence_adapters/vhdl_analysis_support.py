from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    vhdl_primitives as repository_vhdl_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_vhdl_primitives.StableIdentifier
ResolveSuffixMatch = repository_vhdl_primitives.ResolveSuffixMatch

_KNOWN_SUFFIXES = repository_vhdl_primitives._KNOWN_SUFFIXES
_USE_RE = repository_vhdl_primitives._USE_RE
_INSTANTIATION_RE = repository_vhdl_primitives._INSTANTIATION_RE
_QUALIFIED_REFERENCE_RE = repository_vhdl_primitives._QUALIFIED_REFERENCE_RE
_RESERVED_REFERENCE_NAMES = repository_vhdl_primitives._RESERVED_REFERENCE_NAMES

_collect_symbols = repository_vhdl_primitives._collect_symbols
_line_number = repository_vhdl_primitives._line_number
_normalize_name = repository_vhdl_primitives._normalize_name
_ordered_names = repository_vhdl_primitives._ordered_names
_source_symbol_id_for_line = repository_vhdl_primitives._source_symbol_id_for_line
is_probable_vhdl_source = repository_vhdl_primitives.is_probable_vhdl_source
strip_comments = repository_vhdl_primitives.strip_comments


def _resolve_target_file(
    *,
    target_name: str,
    target_kind: str,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_name = _normalize_name(target_name)
    if not normalized_name:
        return None
    candidates = (
        normalized_name,
        f"{target_kind}:{normalized_name}",
        f"work.{normalized_name}",
    )
    for candidate in candidates:
        target_file = module_index.get(candidate)
        if target_file:
            return target_file
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=candidates,
    )


def _resolve_use_target(
    *,
    raw_target: str,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[str | None, str | None]:
    normalized_target = _normalize_name(raw_target).strip(".")
    if not normalized_target:
        return None, None
    target_parts = [part for part in normalized_target.split(".") if part]
    if not target_parts:
        return None, None
    if target_parts[-1] == "all" and len(target_parts) >= 2:
        target_name = target_parts[-2]
    else:
        target_name = target_parts[-1]
    if len(target_parts) >= 2 and target_parts[0] not in {"work", "library"}:
        if normalized_target in module_index:
            return module_index[normalized_target], target_name
        return None, target_name
    target_file = _resolve_target_file(
        target_name=target_name,
        target_kind="package",
        module_index=module_index,
        resolve_suffix_match=resolve_suffix_match,
    )
    return target_file, target_name


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_SUFFIXES:
        return set()
    aliases = {
        file_path.lower(),
        str(path.with_suffix("")).lower(),
        str(path.with_suffix("")).replace("/", ".").lower(),
        path.stem.lower(),
        f"work.{path.stem.lower()}",
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {alias for alias in aliases if alias}
    if not is_probable_vhdl_source(path=path, text=text):
        return {alias for alias in aliases if alias}
    _, collected_symbols = _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    )
    for collected_symbol in collected_symbols:
        aliases.update(collected_symbol.aliases)
    return {alias for alias in aliases if alias}


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    path = PurePosixPath(file_path)
    if not is_probable_vhdl_source(path=path, text=text):
        return ()
    stripped_text = strip_comments(text)
    dependencies: list[_Dependency] = []
    seen_dependency_keys: set[tuple[str | None, str | None, str, int]] = set()
    for match in _USE_RE.finditer(stripped_text):
        line_no = _line_number(stripped_text, match.start())
        for raw_target in str(match.group("body") or "").split(","):
            target_file, target_symbol = _resolve_use_target(
                raw_target=raw_target,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
            if target_symbol is None:
                continue
            dependency_key = (target_file, target_symbol, "imports", line_no)
            if dependency_key in seen_dependency_keys:
                continue
            seen_dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "line": line_no,
                            "target": target_symbol,
                            "type": "imports",
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=target_symbol,
                    dependency_type="imports",
                )
            )
    for match in _INSTANTIATION_RE.finditer(stripped_text):
        line_no = _line_number(stripped_text, match.start())
        target_name = _normalize_name(str(match.group("name") or ""))
        if not target_name:
            continue
        target_file = _resolve_target_file(
            target_name=target_name,
            target_kind="entity",
            module_index=module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, target_name, "instantiates", line_no)
        if dependency_key in seen_dependency_keys:
            continue
        seen_dependency_keys.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "line": line_no,
                        "target": target_name,
                        "type": "instantiates",
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_name,
                dependency_type="instantiates",
            )
        )
    return tuple(dependencies)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[
    tuple[repository_vhdl_primitives._Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    path = PurePosixPath(file_path)
    if not is_probable_vhdl_source(path=path, text=text):
        return (), (), ()
    stripped_text = strip_comments(text)
    symbols, collected_symbols = _collect_symbols(
        file_path=file_path,
        text=stripped_text,
        stable_identifier=stable_identifier,
    )
    dependencies = parse_dependencies_only(
        file_path,
        stripped_text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
    )
    imported_packages: set[str] = set()
    reference_candidates: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, tuple[str, ...], str, int]] = set()

    for match in _USE_RE.finditer(stripped_text):
        for raw_target in str(match.group("body") or "").split(","):
            normalized_target = _normalize_name(raw_target).strip(".")
            if not normalized_target:
                continue
            target_parts = [part for part in normalized_target.split(".") if part]
            if not target_parts:
                continue
            target_name = (
                target_parts[-2]
                if target_parts[-1] == "all" and len(target_parts) >= 2
                else target_parts[-1]
            )
            if target_name:
                imported_packages.add(target_name)

    for match in _INSTANTIATION_RE.finditer(stripped_text):
        line_no = _line_number(stripped_text, match.start())
        source_symbol_id = _source_symbol_id_for_line(
            line_no=line_no,
            collected_symbols=collected_symbols,
        )
        if source_symbol_id is None:
            continue
        target_name = _normalize_name(str(match.group("name") or ""))
        if not target_name:
            continue
        target_file = _resolve_target_file(
            target_name=target_name,
            target_kind="entity",
            module_index=module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        target_names = _ordered_names(target_name, f"entity:{target_name}")
        reference_key = (target_file, target_names, source_symbol_id, line_no)
        if reference_key in seen_reference_keys:
            continue
        seen_reference_keys.add(reference_key)
        reference_candidates.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "line": line_no,
                        "symbol_id": source_symbol_id,
                        "target": target_name,
                        "type": "references_symbol",
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=target_file,
                target_names=target_names,
                reference_type="references_symbol",
            )
        )

    for match in _QUALIFIED_REFERENCE_RE.finditer(stripped_text):
        line_no = _line_number(stripped_text, match.start())
        source_symbol_id = _source_symbol_id_for_line(
            line_no=line_no,
            collected_symbols=collected_symbols,
        )
        if source_symbol_id is None:
            continue
        prefix = _normalize_name(str(match.group("prefix") or ""))
        referenced_name = _normalize_name(str(match.group("name") or ""))
        if (
            not prefix
            or not referenced_name
            or prefix in _RESERVED_REFERENCE_NAMES
            or referenced_name in _RESERVED_REFERENCE_NAMES
        ):
            continue
        if prefix in imported_packages:
            target_file = _resolve_target_file(
                target_name=prefix,
                target_kind="package",
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
            target_names = _ordered_names(
                referenced_name,
                f"{prefix}.{referenced_name}",
                f"work.{prefix}.{referenced_name}",
            )
        else:
            target_file = _resolve_target_file(
                target_name=prefix,
                target_kind="entity",
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
            target_names = _ordered_names(
                referenced_name,
                prefix,
                f"entity:{prefix}",
                f"{prefix}.{referenced_name}",
            )
        if not target_names:
            continue
        reference_key = (target_file, target_names, source_symbol_id, line_no)
        if reference_key in seen_reference_keys:
            continue
        seen_reference_keys.add(reference_key)
        reference_candidates.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "line": line_no,
                        "symbol_id": source_symbol_id,
                        "target": target_names,
                        "type": "references_symbol",
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=target_file,
                target_names=target_names,
                reference_type="references_symbol",
            )
        )

    return symbols, dependencies, tuple(reference_candidates)

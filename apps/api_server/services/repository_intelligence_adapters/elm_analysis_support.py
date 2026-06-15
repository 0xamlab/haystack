from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    elm_primitives as repository_elm_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_elm_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_elm_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_elm_primitives.ResolveSuffixMatch

_KNOWN_SUFFIXES = repository_elm_primitives._KNOWN_SUFFIXES
_MODULE_RE = repository_elm_primitives._MODULE_RE
_IMPORT_RE = repository_elm_primitives._IMPORT_RE
_QUALIFIED_REFERENCE_RE = repository_elm_primitives._QUALIFIED_REFERENCE_RE
_TYPE_REFERENCE_RE = repository_elm_primitives._TYPE_REFERENCE_RE
_CALL_RE = repository_elm_primitives._CALL_RE
_CollectedSymbol = repository_elm_primitives._CollectedSymbol

_line_count = repository_elm_primitives._line_count
_line_number = repository_elm_primitives._line_number
_line_start_offsets = repository_elm_primitives._line_start_offsets
_RESERVED_SYMBOL_NAMES = repository_elm_primitives._RESERVED_SYMBOL_NAMES
exposing_all = repository_elm_primitives.exposing_all
has_elm_path_hints = repository_elm_primitives.has_elm_path_hints
is_probable_elm_source = repository_elm_primitives.is_probable_elm_source
iter_symbol_entries = repository_elm_primitives.iter_symbol_entries
module_name_from_path = repository_elm_primitives.module_name_from_path
parse_exposing_names = repository_elm_primitives.parse_exposing_names
strip_comments = repository_elm_primitives.strip_comments


def _without_suffix_path(path: PurePosixPath) -> str:
    if path.suffix:
        return str(path.with_suffix(""))
    return str(path)


def _line_segment(text: str, *, start_line: int, end_line: int) -> str:
    if end_line < start_line:
        return ""
    line_offsets = _line_start_offsets(text)
    start_index = line_offsets[max(0, start_line - 1)]
    end_index = line_offsets[end_line] if end_line < len(line_offsets) else len(text)
    return text[start_index:end_index]


@lru_cache(maxsize=32768)
def _symbol_identifier(
    stable_identifier: StableIdentifier,
    file_path: str,
    symbol_name: str,
    symbol_kind: str,
    start_line: int,
) -> str:
    return stable_identifier(
        "sym",
        {
            "file_path": file_path,
            "symbol_name": symbol_name,
            "symbol_kind": symbol_kind,
            "start_line": start_line,
        },
    )


@lru_cache(maxsize=32768)
def _dependency_identifier(
    stable_identifier: StableIdentifier,
    file_path: str,
    import_target: str,
    line_number: int,
) -> str:
    return stable_identifier(
        "dep",
        {
            "file_path": file_path,
            "target": import_target,
            "line": line_number,
        },
    )


@lru_cache(maxsize=65536)
def _reference_identifier(
    stable_identifier: StableIdentifier,
    source_symbol_id: str,
    target_symbol_id: str | None,
    target_file: str | None,
    target_names: tuple[str, ...],
) -> str:
    return stable_identifier(
        "ref",
        {
            "source_symbol_id": source_symbol_id,
            "target_symbol_id": target_symbol_id,
            "target_file": target_file,
            "target_names": target_names,
            "type": "references_symbol",
        },
    )


def _collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
    stripped_text: str | None = None,
) -> tuple[_CollectedSymbol, ...]:
    stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    module_match = _MODULE_RE.search(stripped_text)
    module_name = (
        str(module_match.group("name") or "").strip()
        if module_match is not None
        else module_name_from_path(file_path)
    )
    module_symbol = _Symbol(
        symbol_id=_symbol_identifier(
            stable_identifier,
            file_path,
            module_name,
            "module",
            1,
        ),
        symbol_name=module_name,
        symbol_kind="module",
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=f"module {module_name}" if module_name else None,
    )
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=module_symbol,
            local_start_line=1,
            local_end_line=_line_count(stripped_text),
        )
    ]
    for symbol_name, symbol_kind, start_line in iter_symbol_entries(
        text,
        stripped_text=stripped_text,
    ):
        collected_symbols.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=_symbol_identifier(
                        stable_identifier,
                        file_path,
                        symbol_name,
                        symbol_kind,
                        start_line,
                    ),
                    symbol_name=symbol_name,
                    symbol_kind=symbol_kind,
                    start_line=start_line,
                    end_line=start_line,
                    parent_symbol_id=module_symbol.symbol_id,
                    signature=symbol_name,
                ),
                local_start_line=start_line,
                local_end_line=start_line,
            )
        )
    final_line = _line_count(stripped_text)
    finalized_symbols: list[_CollectedSymbol] = []
    for index, collected_symbol in enumerate(collected_symbols):
        if index + 1 < len(collected_symbols):
            end_line = max(
                collected_symbols[index + 1].local_start_line - 1,
                collected_symbol.local_start_line,
            )
        else:
            end_line = final_line
        symbol = collected_symbol.symbol
        finalized_symbols.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=symbol.symbol_id,
                    symbol_name=symbol.symbol_name,
                    symbol_kind=symbol.symbol_kind,
                    start_line=symbol.start_line,
                    end_line=end_line,
                    parent_symbol_id=symbol.parent_symbol_id,
                    signature=symbol.signature,
                ),
                local_start_line=collected_symbol.local_start_line,
                local_end_line=end_line,
            )
        )
    return tuple(finalized_symbols)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
    include_symbol_aliases: bool = True,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_SUFFIXES:
        return set()
    aliases = {
        file_path,
        _without_suffix_path(path),
        _without_suffix_path(path).replace("/", "."),
        path.stem,
    }
    if text is None:
        try:
            text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
    stripped_text = strip_comments(text)
    module_match = _MODULE_RE.search(stripped_text)
    module_name = (
        str(module_match.group("name") or "").strip()
        if module_match is not None
        else module_name_from_path(file_path)
    )
    if module_name:
        aliases.add(module_name)
    if include_symbol_aliases:
        for collected_symbol in _collect_symbols(
            file_path=file_path,
            text=text,
            stable_identifier=stable_identifier,
            stripped_text=stripped_text,
        ):
            symbol_name = collected_symbol.symbol.symbol_name
            if not symbol_name:
                continue
            aliases.add(symbol_name)
            if module_name:
                aliases.add(f"{module_name}.{symbol_name}")
    return {alias for alias in aliases if alias}


def resolve_import(
    import_target: str,
    module_index: dict[str, str],
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(import_target or "").strip()
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    module_path = normalized_target.replace(".", "/")
    candidate_keys = [
        normalized_target,
        module_path,
        f"{module_path}.elm",
        f"src/{module_path}.elm",
        f"tests/{module_path}.elm",
        f"examples/{module_path}.elm",
    ]
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if not normalized_candidate:
            continue
        resolved = module_index.get(normalized_candidate)
        if resolved is not None:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            f"{module_path}.elm",
            f"/{module_path}.elm",
        ],
    )


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str | None = None,
) -> tuple[
    tuple[_Dependency, ...],
    dict[str, _ImportedSymbolBinding],
    tuple[str, ...],
]:
    stripped_text = stripped_text if stripped_text is not None else strip_comments(text)
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    unqualified_import_targets: set[str] = set()
    for match in _IMPORT_RE.finditer(stripped_text):
        import_target = str(match.group("target") or "").strip()
        if not import_target:
            continue
        target_file = resolve_import(
            import_target,
            module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target)
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=_dependency_identifier(
                        stable_identifier,
                        file_path,
                        import_target,
                        _line_number(stripped_text, match.start()),
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=import_target.rsplit(".", 1)[-1],
                    dependency_type="imports",
                )
            )
        alias_candidates = {import_target}
        alias = str(match.group("alias") or "").strip()
        if alias:
            alias_candidates.add(alias)
        for binding_alias in sorted(candidate for candidate in alias_candidates if candidate):
            import_bindings.setdefault(
                binding_alias,
                _ImportedSymbolBinding(
                    alias=binding_alias,
                    target_file=target_file,
                    target_names=(),
                ),
            )
        exposing_value = str(match.group("exposing") or "").strip()
        if exposing_all(exposing_value) and target_file is not None:
            unqualified_import_targets.add(target_file)
        for exposed_name in parse_exposing_names(exposing_value):
            import_bindings.setdefault(
                exposed_name,
                _ImportedSymbolBinding(
                    alias=exposed_name,
                    target_file=target_file,
                    target_names=(exposed_name,),
                ),
            )
    return (
        tuple(dependencies),
        import_bindings,
        tuple(sorted(unqualified_import_targets)),
    )


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    stripped_text = strip_comments(text)
    dependencies, _bindings, _targets = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=stripped_text,
    )
    return dependencies


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    stripped_text = strip_comments(text)
    collected_symbols = _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    )
    symbols = tuple(collected_symbol.symbol for collected_symbol in collected_symbols)
    symbols_by_name: dict[str, list[_Symbol]] = defaultdict(list)
    for symbol in symbols:
        symbols_by_name[symbol.symbol_name].append(symbol)
    dependencies, import_bindings, unqualified_import_targets = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=stripped_text,
    )
    module_symbol = collected_symbols[0].symbol
    reference_keys: dict[tuple[str, str | None, str | None, tuple[str, ...]], None] = {}

    def _record_reference_candidate(
        *,
        source_symbol: _Symbol,
        target_symbol_id: str | None,
        target_file: str | None,
        target_names: tuple[str, ...],
    ) -> None:
        reference_keys.setdefault(
            (
                source_symbol.symbol_id,
                target_symbol_id,
                target_file,
                target_names,
            ),
            None,
        )

    def _record_segment_references(
        *,
        source_symbol: _Symbol,
        segment_text: str,
    ) -> None:
        if not segment_text:
            return
        for match in _QUALIFIED_REFERENCE_RE.finditer(segment_text):
            binding = import_bindings.get(str(match.group("alias") or "").strip())
            if binding is None:
                continue
            target_name = str(match.group("name") or "").strip()
            if not target_name:
                continue
            _record_reference_candidate(
                source_symbol=source_symbol,
                target_symbol_id=None,
                target_file=binding.target_file,
                target_names=(target_name,),
            )
        for match in _TYPE_REFERENCE_RE.finditer(segment_text):
            target_name = str(match.group("name") or "").strip()
            if not target_name or target_name in _RESERVED_SYMBOL_NAMES:
                continue
            binding = import_bindings.get(target_name)
            if binding is not None and binding.target_file is not None and binding.target_names:
                _record_reference_candidate(
                    source_symbol=source_symbol,
                    target_symbol_id=None,
                    target_file=binding.target_file,
                    target_names=binding.target_names,
                )
            for target_symbol in symbols_by_name.get(target_name, ()):
                if target_symbol.symbol_id == source_symbol.symbol_id:
                    continue
                _record_reference_candidate(
                    source_symbol=source_symbol,
                    target_symbol_id=target_symbol.symbol_id,
                    target_file=file_path,
                    target_names=(target_symbol.symbol_name,),
                )
            for target_file in unqualified_import_targets:
                _record_reference_candidate(
                    source_symbol=source_symbol,
                    target_symbol_id=None,
                    target_file=target_file,
                    target_names=(target_name,),
                )
        for match in _CALL_RE.finditer(segment_text):
            target_name = str(match.group("name") or "").strip()
            if not target_name or target_name in _RESERVED_SYMBOL_NAMES:
                continue
            binding = import_bindings.get(target_name)
            if binding is not None and binding.target_file is not None and binding.target_names:
                _record_reference_candidate(
                    source_symbol=source_symbol,
                    target_symbol_id=None,
                    target_file=binding.target_file,
                    target_names=binding.target_names,
                )
            for target_symbol in symbols_by_name.get(target_name, ()):
                if target_symbol.symbol_id == source_symbol.symbol_id:
                    continue
                _record_reference_candidate(
                    source_symbol=source_symbol,
                    target_symbol_id=target_symbol.symbol_id,
                    target_file=file_path,
                    target_names=(target_symbol.symbol_name,),
                )
            for target_file in unqualified_import_targets:
                _record_reference_candidate(
                    source_symbol=source_symbol,
                    target_symbol_id=None,
                    target_file=target_file,
                    target_names=(target_name,),
                )

    current_line = 1
    for collected_symbol in collected_symbols[1:]:
        if current_line < collected_symbol.local_start_line:
            _record_segment_references(
                source_symbol=module_symbol,
                segment_text=_line_segment(
                    stripped_text,
                    start_line=current_line,
                    end_line=collected_symbol.local_start_line - 1,
                ),
            )
        _record_segment_references(
            source_symbol=collected_symbol.symbol,
            segment_text=_line_segment(
                stripped_text,
                start_line=collected_symbol.local_start_line,
                end_line=collected_symbol.local_end_line,
            ),
        )
        current_line = collected_symbol.local_end_line + 1
    if current_line <= module_symbol.end_line:
        _record_segment_references(
            source_symbol=module_symbol,
            segment_text=_line_segment(
                stripped_text,
                start_line=current_line,
                end_line=module_symbol.end_line,
            ),
        )
    reference_candidates = tuple(reference_keys)
    return (
        symbols,
        dependencies,
        tuple(
            _SymbolReferenceCandidate(
                reference_edge_id=_reference_identifier(
                    stable_identifier,
                    source_symbol_id,
                    target_symbol_id,
                    target_file,
                    target_names,
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=target_symbol_id,
                target_file=target_file,
                target_names=target_names,
                reference_type="references_symbol",
            )
            for source_symbol_id, target_symbol_id, target_file, target_names in reference_candidates
        ),
    )

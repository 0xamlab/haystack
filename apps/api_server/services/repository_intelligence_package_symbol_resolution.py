from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from apps.api_server.services import (
    repository_intelligence_module_aliases as repository_module_aliases,
)
from apps.api_server.services.repository_intelligence_adapters import (
    go_language as go_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    julia as julia_adapter,
)
from apps.api_server.services.repository_intelligence_adapters import (
    r_language as r_language_adapter,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _FileAnalysis,
    _Symbol,
    _SymbolReferenceCandidate,
)
from apps.api_server.services.repository_intelligence_indexing import (
    _normalize_repository_relative_path,
    _resolve_suffix_match,
)
from apps.api_server.services.repository_intelligence_shared import _stable_identifier

_r_package_context_for_path = repository_module_aliases._r_package_context_for_path
_julia_package_context_for_path = repository_module_aliases._julia_package_context_for_path
_R_NAMESPACE_CALL_RE = r_language_adapter.NAMESPACE_CALL_RE
_R_CALL_RE = r_language_adapter.CALL_RE
_JULIA_QUALIFIED_REFERENCE_RE = julia_adapter.QUALIFIED_REFERENCE_RE
_JULIA_CALL_RE = julia_adapter.CALL_RE
_JULIA_RESERVED_SYMBOL_NAMES = julia_adapter.RESERVED_SYMBOL_NAMES
_is_julia_operational_reference_name = julia_adapter.is_operational_reference_name
_is_r_operational_reference_name = r_language_adapter.is_operational_reference_name


def _resolve_symbol_reference_target(
    *,
    candidate: _SymbolReferenceCandidate,
    symbols_by_file_and_name: dict[tuple[str, str], list[_Symbol]],
) -> str | None:
    if candidate.target_symbol_id is not None:
        return candidate.target_symbol_id
    if candidate.target_file is None:
        return None
    for target_name in candidate.target_names:
        symbol_matches = symbols_by_file_and_name.get((candidate.target_file, target_name), ())
        if not symbol_matches:
            continue
        ranked_matches = sorted(
            symbol_matches,
            key=lambda symbol: (
                0
                if symbol.symbol_kind not in {"module", "type", "interface"}
                else (1 if symbol.symbol_kind in {"type", "interface"} else 2),
                0 if symbol.parent_symbol_id is None else 1,
                symbol.start_line,
                symbol.symbol_id,
            ),
        )
        return ranked_matches[0].symbol_id
    return None


def _best_package_symbol_target(
    *,
    source_file: str,
    source_symbol_id: str,
    candidates: Sequence[tuple[str, _Symbol]],
) -> tuple[str, _Symbol] | None:
    filtered_candidates = [
        (file_path, symbol)
        for file_path, symbol in candidates
        if symbol.symbol_id != source_symbol_id
    ]
    if not filtered_candidates:
        return None
    same_file_candidates = [
        (file_path, symbol)
        for file_path, symbol in filtered_candidates
        if file_path == source_file
    ]
    if len(same_file_candidates) == 1:
        return same_file_candidates[0]
    if len(filtered_candidates) == 1:
        return filtered_candidates[0]
    candidate_files = {file_path for file_path, _symbol in filtered_candidates}
    if len(candidate_files) == 1:
        return sorted(
            filtered_candidates,
            key=lambda item: (item[1].start_line, item[1].symbol_id),
        )[0]
    return None


def _analysis_with_symbol_references(
    *,
    analysis: _FileAnalysis,
    reference_candidates: dict[str, _SymbolReferenceCandidate],
) -> _FileAnalysis:
    return _FileAnalysis(
        file_path=analysis.file_path,
        language=analysis.language,
        content_hash=analysis.content_hash,
        line_count=analysis.line_count,
        byte_size=analysis.byte_size,
        token_estimate=analysis.token_estimate,
        symbols=analysis.symbols,
        dependencies=analysis.dependencies,
        symbol_references=tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )


def _augment_go_package_symbol_references(
    *,
    analyses: Sequence[_FileAnalysis],
) -> list[_FileAnalysis]:
    return go_adapter.augment_package_symbol_references(
        analyses=analyses,
        stable_identifier=_stable_identifier,
        prefer_non_test_package_candidates=(
            repository_module_aliases._prefer_non_test_package_candidates
        ),
        best_package_symbol_target=_best_package_symbol_target,
        normalize_repository_relative_path=_normalize_repository_relative_path,
    )


def _augment_r_package_symbol_references(
    *,
    root_path: Path,
    analyses: Sequence[_FileAnalysis],
) -> list[_FileAnalysis]:
    package_context_by_file: dict[str, tuple[str | None, str | None]] = {}
    symbols_by_package_and_name: dict[
        tuple[str, str], list[tuple[str, _Symbol]]
    ] = defaultdict(list)
    for analysis in analyses:
        if analysis.language != "r" or not analysis.symbols:
            continue
        package_root, package_name = _r_package_context_for_path(
            root_path=root_path,
            file_path=analysis.file_path,
        )
        package_context_by_file[analysis.file_path] = (package_root, package_name)
        if package_root is None:
            continue
        for symbol in analysis.symbols:
            symbols_by_package_and_name[(package_root, symbol.symbol_name)].append(
                (analysis.file_path, symbol)
            )

    updated_analyses: list[_FileAnalysis] = []
    for analysis in analyses:
        if analysis.language != "r" or not analysis.symbols:
            updated_analyses.append(analysis)
            continue
        package_root, package_name = package_context_by_file.get(analysis.file_path, (None, None))
        if package_root is None:
            updated_analyses.append(analysis)
            continue
        source_path = root_path / analysis.file_path
        try:
            text = source_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            updated_analyses.append(analysis)
            continue
        lines = text.splitlines()
        reference_candidates: dict[str, _SymbolReferenceCandidate] = {
            candidate.reference_edge_id: candidate for candidate in analysis.symbol_references
        }
        for symbol in analysis.symbols:
            snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
            for match in _R_NAMESPACE_CALL_RE.finditer(snippet):
                target_package = str(match.group("pkg") or "").strip()
                target_name = str(match.group("name") or "").strip()
                if not target_package or not target_name or target_package != package_name:
                    continue
                target_candidate = _best_package_symbol_target(
                    source_file=analysis.file_path,
                    source_symbol_id=symbol.symbol_id,
                    candidates=symbols_by_package_and_name.get((package_root, target_name), ()),
                )
                if target_candidate is None:
                    continue
                target_file, target_symbol = target_candidate
                edge_id = _stable_identifier(
                    "ref",
                    {
                        "source_symbol_id": symbol.symbol_id,
                        "target_symbol_id": target_symbol.symbol_id,
                        "type": "references_symbol",
                    },
                )
                reference_candidates.setdefault(
                    edge_id,
                    _SymbolReferenceCandidate(
                        reference_edge_id=edge_id,
                        source_symbol_id=symbol.symbol_id,
                        source_file=analysis.file_path,
                        target_symbol_id=target_symbol.symbol_id,
                        target_file=target_file,
                        target_names=(target_symbol.symbol_name,),
                        reference_type="references_symbol",
                    ),
                )
            for match in _R_CALL_RE.finditer(snippet):
                target_name = str(match.group("name") or "").strip()
                if not _is_r_operational_reference_name(target_name):
                    continue
                target_candidate = _best_package_symbol_target(
                    source_file=analysis.file_path,
                    source_symbol_id=symbol.symbol_id,
                    candidates=symbols_by_package_and_name.get((package_root, target_name), ()),
                )
                if target_candidate is None:
                    continue
                target_file, target_symbol = target_candidate
                edge_id = _stable_identifier(
                    "ref",
                    {
                        "source_symbol_id": symbol.symbol_id,
                        "target_symbol_id": target_symbol.symbol_id,
                        "type": "references_symbol",
                    },
                )
                reference_candidates.setdefault(
                    edge_id,
                    _SymbolReferenceCandidate(
                        reference_edge_id=edge_id,
                        source_symbol_id=symbol.symbol_id,
                        source_file=analysis.file_path,
                        target_symbol_id=target_symbol.symbol_id,
                        target_file=target_file,
                        target_names=(target_symbol.symbol_name,),
                        reference_type="references_symbol",
                    ),
                )
        updated_analyses.append(
            _analysis_with_symbol_references(
                analysis=analysis,
                reference_candidates=reference_candidates,
            )
        )
    return updated_analyses


def _augment_julia_package_symbol_references(
    *,
    root_path: Path,
    analyses: Sequence[_FileAnalysis],
    module_index: dict[str, str],
) -> list[_FileAnalysis]:
    package_context_by_file: dict[str, tuple[str | None, str | None]] = {}
    symbols_by_package_and_name: dict[
        tuple[str, str], list[tuple[str, _Symbol]]
    ] = defaultdict(list)
    for analysis in analyses:
        if analysis.language != "julia" or not analysis.symbols:
            continue
        package_root, package_name = _julia_package_context_for_path(
            root_path=root_path,
            file_path=analysis.file_path,
        )
        package_context_by_file[analysis.file_path] = (package_root, package_name)
        if package_root is None:
            continue
        for symbol in analysis.symbols:
            symbols_by_package_and_name[(package_root, symbol.symbol_name)].append(
                (analysis.file_path, symbol)
            )

    updated_analyses: list[_FileAnalysis] = []
    for analysis in analyses:
        if analysis.language != "julia" or not analysis.symbols:
            updated_analyses.append(analysis)
            continue
        package_root, _package_name = package_context_by_file.get(analysis.file_path, (None, None))
        if package_root is None:
            updated_analyses.append(analysis)
            continue
        source_path = root_path / analysis.file_path
        try:
            text = source_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            updated_analyses.append(analysis)
            continue
        lines = text.splitlines()
        reference_candidates: dict[str, _SymbolReferenceCandidate] = {
            candidate.reference_edge_id: candidate for candidate in analysis.symbol_references
        }
        for symbol in analysis.symbols:
            snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
            for match in _JULIA_QUALIFIED_REFERENCE_RE.finditer(snippet):
                alias = str(match.group("alias") or "").strip()
                target_name = str(match.group("name") or "").strip()
                if (
                    not alias
                    or not target_name
                    or target_name in _JULIA_RESERVED_SYMBOL_NAMES
                    or not _is_julia_operational_reference_name(target_name)
                ):
                    continue
                target_file = julia_adapter.resolve_import(
                    current_file=analysis.file_path,
                    import_target=alias,
                    module_index=module_index,
                    resolve_suffix_match=_resolve_suffix_match,
                )
                if target_file is None:
                    continue
                edge_id = _stable_identifier(
                    "ref",
                    {
                        "source_symbol_id": symbol.symbol_id,
                        "target_file": target_file,
                        "target_names": (target_name,),
                        "type": "references_symbol",
                    },
                )
                reference_candidates.setdefault(
                    edge_id,
                    _SymbolReferenceCandidate(
                        reference_edge_id=edge_id,
                        source_symbol_id=symbol.symbol_id,
                        source_file=analysis.file_path,
                        target_symbol_id=None,
                        target_file=target_file,
                        target_names=(target_name,),
                        reference_type="references_symbol",
                    ),
                )
            for match in _JULIA_CALL_RE.finditer(snippet):
                target_name = str(match.group("name") or "").strip()
                if (
                    not target_name
                    or target_name in _JULIA_RESERVED_SYMBOL_NAMES
                    or not _is_julia_operational_reference_name(target_name)
                ):
                    continue
                target_candidate = _best_package_symbol_target(
                    source_file=analysis.file_path,
                    source_symbol_id=symbol.symbol_id,
                    candidates=symbols_by_package_and_name.get((package_root, target_name), ()),
                )
                if target_candidate is None:
                    continue
                target_file, target_symbol = target_candidate
                edge_id = _stable_identifier(
                    "ref",
                    {
                        "source_symbol_id": symbol.symbol_id,
                        "target_symbol_id": target_symbol.symbol_id,
                        "type": "references_symbol",
                    },
                )
                reference_candidates.setdefault(
                    edge_id,
                    _SymbolReferenceCandidate(
                        reference_edge_id=edge_id,
                        source_symbol_id=symbol.symbol_id,
                        source_file=analysis.file_path,
                        target_symbol_id=target_symbol.symbol_id,
                        target_file=target_file,
                        target_names=(target_symbol.symbol_name,),
                        reference_type="references_symbol",
                    ),
                )
        updated_analyses.append(
            _analysis_with_symbol_references(
                analysis=analysis,
                reference_candidates=reference_candidates,
            )
        )
    return updated_analyses

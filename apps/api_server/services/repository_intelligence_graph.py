from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.schemas.repositories import (
    RepositoryDiagnostic,
    RepositoryGraphQueryRequest,
    RepositorySignals,
)
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)
from apps.api_server.services.repository_intelligence_file_content import (
    read_repository_text,
)
from apps.api_server.services.repository_intelligence_indexing import (
    _normalize_repository_relative_path,
)

_QUOTED_SEGMENT_RE = re.compile(r"""['"](?P<value>[^'"]+)['"]""")
_NON_ACTIONABLE_SYMBOL_NAMES = frozenset({"file", "line", "column", "error", "warning"})
_WRAPPER_FILE_NAMES = frozenset(
    {"index.ts", "index.tsx", "index.js", "index.jsx", "__init__.py", "mod.rs", "lib.rs"}
)
_NON_CODE_GRAPH_LANGUAGES = frozenset(
    {
        "edn",
        "json",
        "yaml",
        "toml",
        "xml",
        "markdown",
        "html",
        "css",
        "opam",
        "psd1",
        "rockspec",
        "nimble",
        "nimscript",
    }
)


def _snapshot_file_graph_edges(
    snapshot_manifest: dict[str, Any],
) -> tuple[tuple[str, str, str], ...]:
    symbols_by_id: dict[str, dict[str, Any]] = {}
    for file_entry in snapshot_manifest["files"]:
        for symbol in file_entry.get("symbols", ()):
            symbol_id = str(symbol.get("symbol_id") or "").strip()
            if symbol_id:
                symbols_by_id[symbol_id] = symbol
    edge_rows: dict[tuple[str, str, str], None] = {}
    for file_entry in snapshot_manifest["files"]:
        source_file = str(file_entry["file_path"])
        for dependency in file_entry.get("dependencies", ()):
            target_file = dependency.get("target_file")
            if target_file:
                edge = (
                    source_file,
                    str(target_file),
                    str(dependency.get("dependency_type") or "imports"),
                )
                if edge[0] != edge[1]:
                    edge_rows[edge] = None
        for reference in file_entry.get("symbol_references", ()):
            target_file = reference.get("target_file")
            if target_file is None:
                target_symbol_id = str(reference.get("target_symbol_id") or "").strip()
                target_symbol = symbols_by_id.get(target_symbol_id)
                if target_symbol is not None:
                    target_file = target_symbol.get("file_path")
            if target_file:
                edge = (
                    source_file,
                    str(target_file),
                    str(reference.get("reference_type") or "references_symbol"),
                )
                if edge[0] != edge[1]:
                    edge_rows[edge] = None
    return tuple(sorted(edge_rows))


def _keywords_from_signals(signals: RepositorySignals) -> set[str]:
    raw_parts = [signals.issue_text or "", *signals.workspace_context]
    raw_parts.extend(diagnostic.message for diagnostic in signals.diagnostics)
    keywords = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", " ".join(raw_parts).lower()))
    return {
        keyword for keyword in keywords if keyword not in {"error", "failed", "warning", "line"}
    }


def _snapshot_file_graph_neighbors(
    snapshot_manifest: dict[str, Any],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    inbound: defaultdict[str, set[str]] = defaultdict(set)
    outbound: defaultdict[str, set[str]] = defaultdict(set)
    for source_file, target_file, _edge_type in _snapshot_file_graph_edges(snapshot_manifest):
        outbound[source_file].add(target_file)
        inbound[target_file].add(source_file)
    return dict(inbound), dict(outbound)


def _resolve_snapshot_file_path(
    *,
    raw_path: str,
    known_paths: Sequence[str],
    known_paths_set: set[str],
) -> str | None:
    normalized_path = _normalize_repository_relative_path(raw_path)
    if not normalized_path:
        return None
    if normalized_path in known_paths_set:
        return normalized_path
    for known_path in known_paths:
        if normalized_path.endswith(known_path):
            return known_path
    return None


def _diagnostic_related_paths(
    *,
    diagnostic: RepositoryDiagnostic,
    known_paths: Sequence[str],
    known_paths_set: set[str],
) -> tuple[str, ...]:
    related_paths: set[str] = set()
    for match in _QUOTED_SEGMENT_RE.finditer(diagnostic.message):
        resolved_path = _resolve_snapshot_file_path(
            raw_path=match.group("value"),
            known_paths=known_paths,
            known_paths_set=known_paths_set,
        )
        if resolved_path is not None:
            related_paths.add(resolved_path)
    return tuple(sorted(related_paths))


def _actionable_symbol_count(file_entry: dict[str, Any]) -> int:
    return sum(
        1
        for symbol in file_entry.get("symbols", [])
        if str(symbol.get("symbol_name") or "").strip().lower() not in _NON_ACTIONABLE_SYMBOL_NAMES
    )


def _group_diagnostics_by_snapshot_path(
    snapshot_manifest: dict[str, Any], diagnostics: Sequence[RepositoryDiagnostic]
) -> dict[str, list[RepositoryDiagnostic]]:
    known_paths = tuple(str(file_entry["file_path"]) for file_entry in snapshot_manifest["files"])
    known_paths_set = set(known_paths)
    files_by_path = {
        str(file_entry["file_path"]): file_entry for file_entry in snapshot_manifest["files"]
    }
    diagnostics_by_path: defaultdict[str, list[RepositoryDiagnostic]] = defaultdict(list)
    for diagnostic in diagnostics:
        resolved_paths: set[str] = set()
        related_paths = set(
            _diagnostic_related_paths(
                diagnostic=diagnostic,
                known_paths=known_paths,
                known_paths_set=known_paths_set,
            )
        )
        if diagnostic.path:
            resolved_path = _resolve_snapshot_file_path(
                raw_path=diagnostic.path,
                known_paths=known_paths,
                known_paths_set=known_paths_set,
            )
            if resolved_path is not None:
                direct_file_entry = files_by_path.get(resolved_path)
                direct_has_actionable_symbols = (
                    _actionable_symbol_count(direct_file_entry) > 0
                    if direct_file_entry is not None
                    else False
                )
                if direct_has_actionable_symbols or not related_paths:
                    resolved_paths.add(resolved_path)
        resolved_paths.update(related_paths)
        for resolved_path in sorted(resolved_paths):
            diagnostics_by_path[resolved_path].append(diagnostic)
    return dict(diagnostics_by_path)


def _score_snapshot_files(
    snapshot_manifest: dict[str, Any], signals: RepositorySignals
) -> dict[str, float]:
    scores: defaultdict[str, float] = defaultdict(float)
    keywords = _keywords_from_signals(signals)
    inbound_neighbors, outbound_neighbors = _snapshot_file_graph_neighbors(snapshot_manifest)
    diagnostics_by_path = _group_diagnostics_by_snapshot_path(
        snapshot_manifest, signals.diagnostics
    )
    for diagnostic_path, path_diagnostics in diagnostics_by_path.items():
        scores[diagnostic_path] += sum(
            10.0 if diagnostic.severity == "error" else 5.0 for diagnostic in path_diagnostics
        )
    for path in signals.changed_files:
        scores[path] += 4.0
    for test_path in signals.failing_tests:
        scores[test_path] += 6.0
    for file_entry in snapshot_manifest["files"]:
        file_path = str(file_entry["file_path"])
        lower_path = file_path.lower()
        for keyword in keywords:
            if keyword in lower_path:
                scores[file_path] += 2.5
            if any(
                keyword in str(symbol["symbol_name"]).lower() for symbol in file_entry["symbols"]
            ):
                scores[file_path] += 3.0
        for dependency in file_entry["dependencies"]:
            target_file = dependency.get("target_file")
            if target_file in signals.failing_tests:
                scores[file_path] += 3.0
        if file_path in diagnostics_by_path:
            line_bonus = sum(
                1.0 for diagnostic in diagnostics_by_path[file_path] if diagnostic.line
            )
            scores[file_path] += line_bonus
        if _is_probable_wrapper_file(file_entry):
            scores[file_path] *= 0.35
            for dependency in file_entry["dependencies"]:
                target_file = dependency.get("target_file")
                if target_file and str(dependency.get("dependency_type") or "") == "reexports":
                    scores[str(target_file)] += 2.5
    seed_files = set(diagnostics_by_path)
    seed_files.update(str(path) for path in signals.changed_files)
    seed_files.update(str(path) for path in signals.failing_tests)
    for seed_file in seed_files:
        for importer in inbound_neighbors.get(seed_file, ()):
            scores[importer] += 2.0 if seed_file in diagnostics_by_path else 1.0
        for dependency in outbound_neighbors.get(seed_file, ()):
            scores[dependency] += 1.0 if seed_file in diagnostics_by_path else 0.5
    return dict(scores)


def _ranked_paths_by_score(scores: dict[str, float]) -> list[str]:
    """Deterministic ranking of paths by descending score (ties broken by path)."""
    return [
        path for path, score in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0])) if score > 0
    ]


def _graph_blast_radius_scores(snapshot_manifest: dict[str, Any]) -> dict[str, float]:
    """AR-OPT-7 RISK signal (distinct from localization): how many files depend on
    each file = the blast radius of changing it. Drives apply-gating / risk, NOT
    "is this the bug" — a utility hub has a huge blast radius but is rarely the cause."""
    inbound_neighbors, _ = _snapshot_file_graph_neighbors(snapshot_manifest)
    return {path: float(len(importers)) for path, importers in inbound_neighbors.items()}


def _graph_proximity_scores(
    snapshot_manifest: dict[str, Any], signals: RepositorySignals
) -> dict[str, float]:
    """AR-OPT-7 LOCALIZATION signal: personalized graph proximity from the issue's
    seed files (distinct from keyword matching) — each seed plus its inbound/outbound
    neighbors, diagnostic seeds weighted higher. High-dependent utility hubs are
    DAMPED so raw centrality doesn't rank them as suspects (e.g. utils.py / index.ts)."""
    inbound_neighbors, outbound_neighbors = _snapshot_file_graph_neighbors(snapshot_manifest)
    diagnostics_by_path = _group_diagnostics_by_snapshot_path(
        snapshot_manifest, signals.diagnostics
    )
    scores: defaultdict[str, float] = defaultdict(float)
    seed_files = set(diagnostics_by_path)
    seed_files.update(str(path) for path in signals.changed_files)
    seed_files.update(str(path) for path in signals.failing_tests)
    for seed_file in seed_files:
        scores[seed_file] += 3.0
        for importer in inbound_neighbors.get(seed_file, ()):
            scores[importer] += 2.0 if seed_file in diagnostics_by_path else 1.0
        for dependency in outbound_neighbors.get(seed_file, ()):
            scores[dependency] += 1.0 if seed_file in diagnostics_by_path else 0.5
    # Utility-hub damping: divide each file's localization score by 1 + ln(1 + dependents),
    # so a file imported by many (a hub) is down-weighted as a SUSPECT while focused,
    # low-fan-in files keep their proximity. Seeds keep a strong base score regardless.
    damped: dict[str, float] = {}
    for path, score in scores.items():
        dependents = len(inbound_neighbors.get(path, ()))
        damped[path] = score / (1.0 + math.log1p(float(dependents)))
    return damped


def _symbol_depth(symbol_entry: dict[str, Any], symbols_by_id: dict[str, dict[str, Any]]) -> int:
    depth = 0
    parent_symbol_id = symbol_entry.get("parent_symbol_id")
    while parent_symbol_id:
        depth += 1
        parent_symbol = symbols_by_id.get(str(parent_symbol_id))
        if parent_symbol is None:
            break
        parent_symbol_id = parent_symbol.get("parent_symbol_id")
    return depth


def _is_probable_wrapper_file(file_entry: dict[str, Any]) -> bool:
    file_name = PurePosixPath(str(file_entry.get("file_path") or "")).name
    if file_name not in _WRAPPER_FILE_NAMES:
        return False
    if _actionable_symbol_count(file_entry) > 0:
        return False
    dependencies = tuple(file_entry.get("dependencies", ()))
    if not dependencies:
        return False
    return any(
        str(dependency.get("dependency_type") or "") == "reexports"
        for dependency in dependencies
    )


def _actionable_symbols_for_file(file_entry: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        symbol
        for symbol in file_entry.get("symbols", [])
        if str(symbol.get("symbol_name") or "").strip().lower() not in _NON_ACTIONABLE_SYMBOL_NAMES
    ]


def _is_actionable_graph_file(file_entry: dict[str, Any] | None) -> bool:
    if file_entry is None:
        return False
    language = str(file_entry.get("language") or "").strip().lower()
    if _actionable_symbol_count(file_entry) > 0:
        return True
    return language not in _NON_CODE_GRAPH_LANGUAGES and not _is_probable_wrapper_file(file_entry)


def _shared_path_prefix_depth(left: str, right: str) -> int:
    left_parts = PurePosixPath(left).parts
    right_parts = PurePosixPath(right).parts
    depth = 0
    for left_part, right_part in zip(left_parts, right_parts, strict=False):
        if left_part != right_part:
            break
        depth += 1
    return depth


def _promoted_graph_seed_candidates(
    *,
    seed_file: str,
    files_by_path: dict[str, dict[str, Any]],
    inbound_neighbors: dict[str, set[str]],
    outbound_neighbors: dict[str, set[str]],
    max_candidates: int = 4,
) -> list[str]:
    file_entry = files_by_path.get(seed_file)
    if _is_actionable_graph_file(file_entry):
        return [seed_file]

    if file_entry is not None and _is_probable_wrapper_file(file_entry):
        outbound_actionable_neighbors = [
            neighbor
            for neighbor in sorted(outbound_neighbors.get(seed_file, set()))
            if _is_actionable_graph_file(files_by_path.get(neighbor))
        ]
        if outbound_actionable_neighbors:
            return outbound_actionable_neighbors[:max_candidates]

    direct_neighbors = sorted(
        {
            *inbound_neighbors.get(seed_file, set()),
            *outbound_neighbors.get(seed_file, set()),
        }
    )
    actionable_neighbors = [
        neighbor
        for neighbor in direct_neighbors
        if _is_actionable_graph_file(files_by_path.get(neighbor))
    ]
    if actionable_neighbors:
        return actionable_neighbors[:max_candidates]

    seed_parent = str(PurePosixPath(seed_file).parent)
    ranked_candidates: list[tuple[float, str]] = []
    in_scope_candidates: list[tuple[float, str]] = []
    for candidate_path, candidate_entry in files_by_path.items():
        if candidate_path == seed_file or not _is_actionable_graph_file(candidate_entry):
            continue
        common_prefix = _shared_path_prefix_depth(seed_file, candidate_path)
        candidate_parent = str(PurePosixPath(candidate_path).parent)
        same_parent = candidate_parent == seed_parent
        same_scope = False
        if seed_parent not in {"", "."}:
            same_scope = candidate_path.startswith(f"{seed_parent}/")
        inbound_count = len(inbound_neighbors.get(candidate_path, ()))
        outbound_count = len(outbound_neighbors.get(candidate_path, ()))
        score = common_prefix * 8.0
        if same_parent:
            score += 24.0
        elif same_scope:
            score += 16.0
        score += min(10.0, _actionable_symbol_count(candidate_entry) * 1.5)
        score += min(10.0, inbound_count * 1.5)
        score += min(8.0, outbound_count * 1.25)
        if _is_probable_wrapper_file(candidate_entry):
            score *= 0.6
        ranked_entry = (round(score, 3), candidate_path)
        if same_parent or same_scope:
            in_scope_candidates.append(ranked_entry)
        ranked_candidates.append(ranked_entry)
    if in_scope_candidates:
        in_scope_candidates.sort(key=lambda item: (-item[0], item[1]))
        return [candidate_path for _score, candidate_path in in_scope_candidates[:max_candidates]]
    ranked_candidates.sort(key=lambda item: (-item[0], item[1]))
    return [candidate_path for _score, candidate_path in ranked_candidates[:max_candidates]]


def _effective_graph_query_seed_files(
    *,
    seed_files: Sequence[str],
    files_by_path: dict[str, dict[str, Any]],
    inbound_neighbors: dict[str, set[str]],
    outbound_neighbors: dict[str, set[str]],
) -> list[str]:
    effective_seeds: list[str] = []
    seen: set[str] = set()
    for seed_file in seed_files:
        promoted_files = _promoted_graph_seed_candidates(
            seed_file=seed_file,
            files_by_path=files_by_path,
            inbound_neighbors=inbound_neighbors,
            outbound_neighbors=outbound_neighbors,
        )
        for promoted_file in promoted_files or [seed_file]:
            if promoted_file in seen:
                continue
            seen.add(promoted_file)
            effective_seeds.append(promoted_file)
    return effective_seeds or list(seed_files)


def _file_parent_child_labels(file_entry: dict[str, Any], *, limit: int = 16) -> list[str]:
    symbols = {
        str(symbol.get("symbol_id") or ""): symbol
        for symbol in file_entry.get("symbols", [])
        if symbol.get("symbol_id")
    }
    labels: list[str] = []
    for symbol in file_entry.get("symbols", []):
        parent_id = str(symbol.get("parent_symbol_id") or "").strip()
        if not parent_id:
            continue
        parent_symbol = symbols.get(parent_id)
        if parent_symbol is None:
            continue
        parent_name = str(parent_symbol.get("symbol_name") or "").strip()
        child_name = str(symbol.get("symbol_name") or "").strip()
        if not parent_name or not child_name:
            continue
        labels.append(f"{parent_name}.{child_name}")
    return sorted(dict.fromkeys(labels))[:limit]


def _is_probable_test_file(file_path: str) -> bool:
    normalized_path = _normalize_repository_relative_path(file_path).lower()
    file_name = PurePosixPath(normalized_path).name
    if normalized_path.startswith(("test/", "tests/")):
        return True
    if "/test/" in normalized_path or "/tests/" in normalized_path:
        return True
    test_markers = (".test.", ".spec.", "_test.", "_spec.")
    return any(marker in file_name for marker in test_markers)


def _seed_files_from_triage_manifest(
    *,
    triage_manifest: dict[str, Any],
    snapshot_manifest: dict[str, Any],
) -> list[str]:
    files_by_path = {
        str(file_entry["file_path"]): file_entry for file_entry in snapshot_manifest["files"]
    }
    ordered_paths: list[str] = []
    seen: set[str] = set()

    for evidence_item in triage_manifest.get("evidence_items", []):
        if not isinstance(evidence_item, dict):
            continue
        file_path = str(evidence_item.get("file_path") or "").strip()
        if not file_path or file_path not in files_by_path or file_path in seen:
            continue
        seen.add(file_path)
        ordered_paths.append(file_path)

    for suspect_path in triage_manifest.get("suspect_files", []):
        file_path = str(suspect_path or "").strip()
        if not file_path or file_path not in files_by_path or file_path in seen:
            continue
        seen.add(file_path)
        ordered_paths.append(file_path)

    production_like_paths = [
        file_path for file_path in ordered_paths if not _is_probable_test_file(file_path)
    ]
    return production_like_paths or ordered_paths


def _resolve_graph_query_seeds(
    *,
    triage_manifest: dict[str, Any] | None,
    snapshot_manifest: dict[str, Any],
    request: RepositoryGraphQueryRequest,
) -> tuple[list[str], list[str]]:
    if (
        not request.file_path
        and not request.symbol_name
        and not request.workspace_evidence_bundle_ref
    ):
        raise RepositoryIntelligenceError(
            code="repository_graph_query_requires_seed",
            message=(
                "Repository graph query requires file_path, symbol_name, "
                "workspace_evidence_bundle_ref, or a combination."
            ),
            status_code=422,
        )
    files_by_path = {
        str(file_entry["file_path"]): file_entry for file_entry in snapshot_manifest["files"]
    }
    seed_files: list[str] = []
    seen_seed_files: set[str] = set()
    if triage_manifest is not None:
        for file_path in _seed_files_from_triage_manifest(
            triage_manifest=triage_manifest,
            snapshot_manifest=snapshot_manifest,
        ):
            if file_path in seen_seed_files:
                continue
            seen_seed_files.add(file_path)
            seed_files.append(file_path)
    if request.file_path:
        normalized_path = _normalize_repository_relative_path(request.file_path)
        if normalized_path not in files_by_path:
            raise RepositoryIntelligenceError(
                code="repository_graph_query_file_not_found",
                message=f"Repository graph query file '{normalized_path}' is not in the snapshot.",
                status_code=404,
            )
        if normalized_path not in seen_seed_files:
            seen_seed_files.add(normalized_path)
            seed_files.append(normalized_path)
    seed_symbol_refs: list[str] = []
    if request.symbol_name:
        target_name = str(request.symbol_name).strip()
        if not target_name:
            raise RepositoryIntelligenceError(
                code="repository_graph_query_invalid_symbol",
                message="Repository graph query symbol_name cannot be empty.",
                status_code=422,
            )
        exact_matches: list[tuple[str, dict[str, Any]]] = []
        lower_matches: list[tuple[str, dict[str, Any]]] = []
        scoped_paths = seed_files or set(files_by_path)
        for file_path in sorted(scoped_paths):
            file_entry = files_by_path[file_path]
            for symbol in file_entry.get("symbols", []):
                symbol_name = str(symbol.get("symbol_name") or "").strip()
                if not symbol_name:
                    continue
                if symbol_name == target_name:
                    exact_matches.append((file_path, symbol))
                elif symbol_name.lower() == target_name.lower():
                    lower_matches.append((file_path, symbol))
        matches = exact_matches or lower_matches
        if not matches:
            raise RepositoryIntelligenceError(
                code="repository_graph_query_symbol_not_found",
                message=f"Repository graph query symbol '{target_name}' is not in the snapshot.",
                status_code=404,
            )
        for file_path, symbol in sorted(
            matches,
            key=lambda item: (
                item[0],
                int(item[1].get("start_line") or 0),
                str(item[1].get("symbol_name") or ""),
            ),
        ):
            if file_path not in seen_seed_files:
                seen_seed_files.add(file_path)
                seed_files.append(file_path)
            seed_symbol_refs.append(f"{file_path}:{symbol['symbol_name']}")
    return seed_files, seed_symbol_refs


def _file_query_risk_score(
    *,
    file_entry: dict[str, Any],
    depth: int,
    inbound_count: int,
    outbound_count: int,
    is_seed: bool,
) -> float:
    score = 40.0 if is_seed else max(6.0, 22.0 - depth * 4.0)
    score += min(12.0, inbound_count * 4.5)
    score += min(10.0, outbound_count * 3.5)
    score += min(8.0, _actionable_symbol_count(file_entry) * 1.5)
    score += min(6.0, len(_file_parent_child_labels(file_entry, limit=8)) * 0.75)
    if _is_probable_wrapper_file(file_entry):
        score *= 0.6
    return round(score, 3)


def _collapse_wrapper_neighbors(
    *,
    initial_files: Sequence[str],
    direction: str,
    files_by_path: dict[str, dict[str, Any]],
    inbound_neighbors: dict[str, set[str]],
    outbound_neighbors: dict[str, set[str]],
    max_hops: int = 4,
) -> list[str]:
    collapsed: set[str] = set()
    queue: list[tuple[str, int]] = [(file_path, 0) for file_path in initial_files]
    seen = set(initial_files)
    while queue:
        file_path, hop = queue.pop(0)
        file_entry = files_by_path.get(file_path)
        if (
            file_entry is not None
            and _is_probable_wrapper_file(file_entry)
            and hop < max_hops
        ):
            next_neighbors = (
                inbound_neighbors.get(file_path, ())
                if direction == "inbound"
                else outbound_neighbors.get(file_path, ())
            )
            if next_neighbors:
                for neighbor in sorted(next_neighbors):
                    if neighbor in seen:
                        continue
                    seen.add(neighbor)
                    queue.append((neighbor, hop + 1))
                continue
        collapsed.add(file_path)
    return sorted(collapsed)


def _localized_symbol_for_file(
    *,
    file_entry: dict[str, Any],
    diagnostics: Sequence[RepositoryDiagnostic],
) -> dict[str, Any] | None:
    symbols = [symbol for symbol in file_entry["symbols"] if symbol.get("symbol_name")]
    if not symbols:
        return None
    actionable_symbols = [
        symbol
        for symbol in symbols
        if str(symbol.get("symbol_name") or "").strip().lower() not in _NON_ACTIONABLE_SYMBOL_NAMES
    ]
    symbols_by_id = {
        str(symbol["symbol_id"]): symbol
        for symbol in symbols
        if symbol.get("symbol_id")
    }
    operational_kinds = {
        "async_function",
        "async_method",
        "class",
        "constructor",
        "def",
        "fn",
        "function",
        "method",
        "struct",
        "trait",
    }
    for diagnostic in diagnostics:
        if diagnostic.line is None:
            continue
        matching_symbols = [
            symbol
            for symbol in symbols
            if int(symbol.get("start_line") or 0)
            <= diagnostic.line
            <= int(symbol.get("end_line") or 0)
        ]
        if matching_symbols:
            matching_symbols.sort(
                key=lambda symbol: (
                    0 if str(symbol.get("symbol_kind") or "") in operational_kinds else 1,
                    0
                    if str(symbol.get("symbol_name") or "").strip().lower()
                    not in _NON_ACTIONABLE_SYMBOL_NAMES
                    else 1,
                    -_symbol_depth(symbol, symbols_by_id),
                    int(symbol.get("end_line") or 0) - int(symbol.get("start_line") or 0),
                    int(symbol.get("start_line") or 0),
                )
            )
            return matching_symbols[0]
    lower_messages = " ".join(diagnostic.message.lower() for diagnostic in diagnostics)
    matching_by_name = [
        symbol
        for symbol in actionable_symbols
        if str(symbol.get("symbol_name") or "").lower() in lower_messages
    ]
    if matching_by_name:
        matching_by_name.sort(
            key=lambda symbol: (
                0 if str(symbol.get("symbol_kind") or "") in operational_kinds else 1,
                -len(str(symbol.get("symbol_name") or "")),
                int(symbol.get("start_line") or 0),
            )
        )
        return matching_by_name[0]
    fallback_symbols = actionable_symbols or symbols
    fallback_symbols.sort(
        key=lambda symbol: (
            0 if str(symbol.get("symbol_kind") or "") in operational_kinds else 1,
            int(symbol.get("start_line") or 0),
        )
    )
    return fallback_symbols[0]


def _snippet_for_file(
    *,
    root_path: Path,
    file_entry: dict[str, Any],
    file_path: str,
    diagnostics: Sequence[RepositoryDiagnostic],
    max_snippet_lines: int,
) -> tuple[str, str | None]:
    absolute_path = root_path / file_path
    text = read_repository_text(absolute_path)
    lines = text.splitlines()
    localized_symbol = _localized_symbol_for_file(file_entry=file_entry, diagnostics=diagnostics)
    target_line = next(
        (diagnostic.line for diagnostic in diagnostics if diagnostic.line is not None), None
    )
    if target_line is None and localized_symbol is not None:
        target_line = int(localized_symbol.get("start_line") or 1)
    if target_line is None:
        start = 0
    else:
        start = max(0, target_line - 6)
    end = min(len(lines), start + max_snippet_lines)
    snippet_lines = []
    for index, line in enumerate(lines[start:end], start=start + 1):
        snippet_lines.append(f"{index:>4}: {line}")
    symbol_name = (
        str(localized_symbol.get("symbol_name"))
        if localized_symbol is not None and localized_symbol.get("symbol_name")
        else None
    )
    return "\n".join(snippet_lines), symbol_name

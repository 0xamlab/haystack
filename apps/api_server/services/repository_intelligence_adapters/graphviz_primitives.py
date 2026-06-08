from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]

GRAPHVIZ_SUFFIXES = frozenset({".dot", ".gv"})
GRAPHVIZ_INDEX_BASENAMES = frozenset({"graph.dot", "graph.gv", "index.dot", "index.gv"})
_COMMON_MODULE_ROOTS = frozenset(
    {"diagrams", "dot", "dots", "graph", "graphs", "graphviz", "viz", "visuals"}
)
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"(?m)(?://|#).*?$")
_GRAPH_DECLARATION_RE = re.compile(
    r"(?m)^\s*(?:strict\s+)?(?P<kind>di)?graph(?:\s+(?P<name>\"[^\"]+\"|[A-Za-z_][A-Za-z0-9_.:-]*))?\s*\{"
)
_SUBGRAPH_RE = re.compile(
    r"(?m)\bsubgraph(?:\s+(?P<name>\"[^\"]+\"|[A-Za-z_][A-Za-z0-9_.:-]*))?\s*\{"
)
_EDGE_IDENTIFIER_PATTERN = r"(?:\"[^\"]+\"|[A-Za-z_][A-Za-z0-9_.:-]*)"
_EDGE_RE = re.compile(
    rf"(?P<source>{_EDGE_IDENTIFIER_PATTERN})\s*(?P<operator>->|--)\s*(?P<target>{_EDGE_IDENTIFIER_PATTERN})"
)
_NODE_STATEMENT_RE = re.compile(
    rf"(?m)^\s*(?P<name>{_EDGE_IDENTIFIER_PATTERN})\s*(?:\[|;|\{{)"
)
_RESERVED_IDENTIFIERS = frozenset({"digraph", "edge", "graph", "node", "strict", "subgraph"})


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def _preserve_line_count_comment(match: re.Match[str]) -> str:
    return "\n" * match.group(0).count("\n")


def strip_comments(text: str) -> str:
    without_block_comments = _BLOCK_COMMENT_RE.sub(_preserve_line_count_comment, text)
    return _LINE_COMMENT_RE.sub("", without_block_comments)


def has_graphviz_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in GRAPHVIZ_SUFFIXES


def normalize_identifier(value: str) -> str:
    normalized = str(value or "").strip().strip('"').strip("'").strip()
    return normalized


def graph_name_from_text(text: str) -> str | None:
    match = _GRAPH_DECLARATION_RE.search(strip_comments(text))
    if match is None:
        return None
    return normalize_identifier(match.group("name") or "")


def is_probable_graphviz_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if PurePosixPath(path).suffix.lower() not in GRAPHVIZ_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    if _GRAPH_DECLARATION_RE.search(stripped_text):
        return True
    return bool(_EDGE_RE.search(stripped_text) and "{" in stripped_text and "}" in stripped_text)


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    while parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    if parts and parts[-1].lower() == "index":
        parts = parts[:-1]
    return ".".join(parts) if parts else without_suffix.stem


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def iter_subgraph_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen_names: set[str] = set()
    for match in _SUBGRAPH_RE.finditer(stripped_text):
        name = normalize_identifier(match.group("name") or "")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        line_number = stripped_text.count("\n", 0, match.start()) + 1
        entries.append((name, line_number))
    return tuple(entries)


def iter_edge_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_edges: set[tuple[str, str, int]] = set()
    for match in _EDGE_RE.finditer(stripped_text):
        source_name = normalize_identifier(match.group("source"))
        target_name = normalize_identifier(match.group("target"))
        if (
            not source_name
            or not target_name
            or source_name.lower() in _RESERVED_IDENTIFIERS
            or target_name.lower() in _RESERVED_IDENTIFIERS
        ):
            continue
        line_number = stripped_text.count("\n", 0, match.start()) + 1
        edge_entry = (source_name, target_name, line_number)
        if edge_entry in seen_edges:
            continue
        seen_edges.add(edge_entry)
        entries.append(edge_entry)
    return tuple(entries)


def iter_node_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen_names: set[str] = set()
    for match in _NODE_STATEMENT_RE.finditer(stripped_text):
        name = normalize_identifier(match.group("name"))
        if not name or name.lower() in _RESERVED_IDENTIFIERS or name in seen_names:
            continue
        seen_names.add(name)
        line_number = stripped_text.count("\n", 0, match.start()) + 1
        entries.append((name, line_number))
    for source_name, target_name, line_number in iter_edge_entries(stripped_text):
        for name in (source_name, target_name):
            if name in seen_names:
                continue
            seen_names.add(name)
            entries.append((name, line_number))
    return tuple(entries)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    normalized_path = PurePosixPath(file_path)
    if normalized_path.suffix.lower() not in GRAPHVIZ_SUFFIXES:
        return set()
    aliases = {
        file_path,
        normalized_path.name,
        normalized_path.stem,
        str(normalized_path.with_suffix("")),
        str(normalized_path.with_suffix("")).replace("/", "."),
        module_name_from_path(file_path),
    }
    try:
        text = (root_path / normalized_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    graph_name = graph_name_from_text(text) if text else None
    if graph_name:
        aliases.add(graph_name)
    return {alias for alias in aliases if alias}


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    graph_name = graph_name_from_text(text) or module_name_from_path(file_path)
    line_count = _line_count(text)
    symbols = [
        _Symbol(
            symbol_id=stable_identifier(
                "symbol",
                {"file_path": file_path, "symbol_name": graph_name, "kind": "graphviz"},
            ),
            symbol_name=graph_name,
            symbol_kind="graphviz",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"graphviz {graph_name}".strip(),
        )
    ]
    module_symbol_id = symbols[0].symbol_id
    for subgraph_name, line_number in iter_subgraph_entries(text):
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "symbol",
                    {"file_path": file_path, "symbol_name": subgraph_name, "kind": "subgraph"},
                ),
                symbol_name=subgraph_name,
                symbol_kind="subgraph",
                start_line=line_number,
                end_line=line_number,
                parent_symbol_id=module_symbol_id,
                signature=f"subgraph {subgraph_name}",
            )
        )
    for node_name, line_number in iter_node_entries(text):
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "symbol",
                    {"file_path": file_path, "symbol_name": node_name, "kind": "node"},
                ),
                symbol_name=node_name,
                symbol_kind="node",
                start_line=line_number,
                end_line=line_number,
                parent_symbol_id=module_symbol_id,
                signature=f"node {node_name}",
            )
        )
    return tuple(symbols)


def source_symbol_name_for_line(
    symbol_entries: Iterable[tuple[str, int]],
    *,
    line_number: int,
) -> str | None:
    current_name: str | None = None
    for symbol_name, symbol_line in symbol_entries:
        if symbol_line <= line_number:
            current_name = symbol_name
    return current_name

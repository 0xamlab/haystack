from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.graphviz_analysis_support import (
    GRAPHVIZ_INDEX_BASENAMES,
    GRAPHVIZ_SUFFIXES,
    collect_symbols,
    graph_name_from_text,
    has_graphviz_path_hints,
    is_probable_graphviz_source,
    iter_edge_entries,
    iter_node_entries,
    iter_subgraph_entries,
    module_aliases_for_path,
    module_name_from_path,
    parse_dependencies_only,
    parse_file,
    source_symbol_name_for_line,
)
from apps.api_server.services.repository_intelligence_adapters.graphviz_primitives import (
    normalize_identifier,
    strip_comments,
)

__all__ = [
    "GRAPHVIZ_INDEX_BASENAMES",
    "GRAPHVIZ_SUFFIXES",
    "collect_symbols",
    "graph_name_from_text",
    "has_graphviz_path_hints",
    "is_probable_graphviz_source",
    "iter_edge_entries",
    "iter_node_entries",
    "iter_subgraph_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "normalize_identifier",
    "parse_dependencies_only",
    "parse_file",
    "source_symbol_name_for_line",
    "strip_comments",
]

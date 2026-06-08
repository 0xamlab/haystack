from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    batchfile_analysis_support as analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    batchfile_primitives as primitives,
)

_KNOWN_SUFFIXES = primitives._KNOWN_SUFFIXES
BATCHFILE_CONFIG_BASENAMES = frozenset()

strip_comments = primitives.strip_comments
has_batchfile_path_hints = primitives.has_batchfile_path_hints
is_probable_batchfile_source = primitives.is_probable_batchfile_source
iter_symbol_entries = primitives.iter_symbol_entries
iter_script_calls = primitives.iter_script_calls
iter_reference_names = primitives.iter_reference_names
module_aliases_for_path = analysis_support.module_aliases_for_path
parse_dependencies_only = analysis_support.parse_dependencies_only
parse_file = analysis_support.parse_file
resolve_import = analysis_support.resolve_import


def is_probable_batchfile_config(*, path: Path, text: str) -> bool:
    del path, text
    return False

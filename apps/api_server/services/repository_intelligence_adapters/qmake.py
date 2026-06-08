from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    qmake_analysis_support as analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    qmake_primitives as primitives,
)

QMAKE_SUFFIXES = primitives.QMAKE_SUFFIXES
QMAKE_CONFIG_BASENAMES = primitives.QMAKE_CONFIG_BASENAMES

strip_comments = primitives.strip_comments
normalize_continuations = primitives.normalize_continuations
has_qmake_path_hints = primitives.has_qmake_path_hints
is_probable_qmake_source = primitives.is_probable_qmake_source
iter_assignment_entries = primitives.iter_assignment_entries
iter_include_targets = primitives.iter_include_targets
iter_load_targets = primitives.iter_load_targets
iter_subdir_entries = primitives.iter_subdir_entries
iter_symbol_entries = primitives.iter_symbol_entries
iter_reference_names = primitives.iter_reference_names
module_aliases_for_path = analysis_support.module_aliases_for_path
resolve_import = analysis_support.resolve_import
parse_dependencies_only = analysis_support.parse_dependencies_only
parse_file = analysis_support.parse_file


def is_probable_qmake_config(*, path: Path, text: str) -> bool:
    del path, text
    return False

from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    bitbake_analysis_support as analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    bitbake_primitives as primitives,
)

_KNOWN_SUFFIXES = primitives._KNOWN_SUFFIXES
BITBAKE_CONFIG_BASENAMES = primitives.BITBAKE_CONFIG_BASENAMES

strip_comments = primitives.strip_comments
has_bitbake_path_hints = primitives.has_bitbake_path_hints
is_probable_bitbake_source = primitives.is_probable_bitbake_source
iter_include_targets = primitives.iter_include_targets
iter_inherit_targets = primitives.iter_inherit_targets
iter_symbol_entries = primitives.iter_symbol_entries
iter_reference_names = primitives.iter_reference_names
module_aliases_for_path = analysis_support.module_aliases_for_path
parse_dependencies_only = analysis_support.parse_dependencies_only
parse_file = analysis_support.parse_file
resolve_include_target = analysis_support.resolve_include_target
resolve_inherit_target = analysis_support.resolve_inherit_target


def is_probable_bitbake_config(*, path: Path, text: str) -> bool:
    return path.name.lower() in BITBAKE_CONFIG_BASENAMES and is_probable_bitbake_source(
        path=path,
        text=text,
    )

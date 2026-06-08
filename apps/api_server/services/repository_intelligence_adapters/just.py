from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    just_analysis_support as analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    just_primitives as primitives,
)

_KNOWN_SUFFIXES = primitives._KNOWN_SUFFIXES
JUSTFILE_BASENAMES = primitives.JUSTFILE_BASENAMES
JUST_CONFIG_BASENAMES = frozenset()

strip_comments = primitives.strip_comments
has_just_path_hints = primitives.has_just_path_hints
is_probable_just_source = primitives.is_probable_just_source
iter_alias_entries = primitives.iter_alias_entries
iter_import_targets = primitives.iter_import_targets
iter_mod_targets = primitives.iter_mod_targets
iter_recipe_entries = primitives.iter_recipe_entries
iter_symbol_entries = primitives.iter_symbol_entries
iter_reference_names = primitives.iter_reference_names
module_aliases_for_path = analysis_support.module_aliases_for_path
parse_dependencies_only = analysis_support.parse_dependencies_only
parse_file = analysis_support.parse_file
resolve_import = analysis_support.resolve_import


def is_probable_just_config(*, path: Path, text: str) -> bool:
    del path, text
    return False

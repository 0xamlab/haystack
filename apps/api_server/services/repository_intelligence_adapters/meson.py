from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    meson_analysis_support as analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    meson_primitives as primitives,
)

MESON_CONFIG_BASENAMES = primitives.MESON_CONFIG_BASENAMES

strip_comments = primitives.strip_comments
has_meson_path_hints = primitives.has_meson_path_hints
is_probable_meson_source = primitives.is_probable_meson_source
iter_call_entries = primitives.iter_call_entries
iter_subdir_targets = primitives.iter_subdir_targets
iter_import_targets = primitives.iter_import_targets
iter_dependency_targets = primitives.iter_dependency_targets
iter_symbol_entries = primitives.iter_symbol_entries
iter_reference_names = primitives.iter_reference_names
module_aliases_for_path = analysis_support.module_aliases_for_path
parse_dependencies_only = analysis_support.parse_dependencies_only
parse_file = analysis_support.parse_file
resolve_import = analysis_support.resolve_import


def is_probable_meson_config(*, path: Path, text: str) -> bool:
    return path.name.lower() in MESON_CONFIG_BASENAMES and is_probable_meson_source(
        path=path,
        text=text,
    )

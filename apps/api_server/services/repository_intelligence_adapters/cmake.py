from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    cmake_analysis_support as analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    cmake_primitives as primitives,
)

_KNOWN_SUFFIXES = primitives._KNOWN_SUFFIXES
CMAKE_CONFIG_BASENAMES = primitives._CMAKE_CONFIG_BASENAMES

strip_comments = primitives.strip_comments
has_cmake_path_hints = primitives.has_cmake_path_hints
is_probable_cmake_source = primitives.is_probable_cmake_source
iter_command_entries = primitives.iter_command_entries
iter_include_targets = primitives.iter_include_targets
iter_subdirectory_targets = primitives.iter_subdirectory_targets
iter_package_targets = primitives.iter_package_targets
iter_symbol_entries = primitives.iter_symbol_entries
iter_reference_names = primitives.iter_reference_names
module_aliases_for_path = analysis_support.module_aliases_for_path
parse_dependencies_only = analysis_support.parse_dependencies_only
parse_file = analysis_support.parse_file
resolve_import = analysis_support.resolve_import


def is_probable_cmake_config(*, path: Path, text: str) -> bool:
    return path.name.lower() in CMAKE_CONFIG_BASENAMES and is_probable_cmake_source(
        path=path,
        text=text,
    )


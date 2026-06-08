from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters import (
    dockerfile_analysis_support as analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    dockerfile_primitives as primitives,
)

DOCKERFILE_BASENAMES = primitives.DOCKERFILE_BASENAMES
DOCKERFILE_CONFIG_BASENAMES = primitives.DOCKERFILE_BASENAMES
DOCKERFILE_SUFFIXES = primitives.DOCKERFILE_SUFFIXES

strip_comments = primitives.strip_comments
has_dockerfile_path_hints = primitives.has_dockerfile_path_hints
is_probable_dockerfile_source = primitives.is_probable_dockerfile_source
iter_instruction_entries = primitives.iter_instruction_entries
iter_stage_entries = primitives.iter_stage_entries
iter_copy_add_entries = primitives.iter_copy_add_entries
iter_run_local_path_entries = primitives.iter_run_local_path_entries
module_name_from_path = primitives.module_name_from_path
source_symbol_name_for_line = primitives.source_symbol_name_for_line

module_aliases_for_path = analysis_support.module_aliases_for_path
parse_dependencies_only = analysis_support.parse_dependencies_only
parse_file = analysis_support.parse_file

__all__ = [
    "DOCKERFILE_BASENAMES",
    "DOCKERFILE_CONFIG_BASENAMES",
    "DOCKERFILE_SUFFIXES",
    "has_dockerfile_path_hints",
    "is_probable_dockerfile_source",
    "iter_copy_add_entries",
    "iter_instruction_entries",
    "iter_run_local_path_entries",
    "iter_stage_entries",
    "module_aliases_for_path",
    "module_name_from_path",
    "parse_dependencies_only",
    "parse_file",
    "source_symbol_name_for_line",
    "strip_comments",
]

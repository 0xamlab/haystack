from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters import (
    shaderlab_analysis_support as analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    shaderlab_primitives as primitives,
)

SHADERLAB_SOURCE_SUFFIXES = primitives.SHADERLAB_SOURCE_SUFFIXES
SHADERLAB_CONFIG_BASENAMES = frozenset()

strip_comments = primitives.strip_comments
has_shaderlab_path_hints = primitives.has_shaderlab_path_hints
iter_shader_declarations = primitives.iter_shader_declarations
iter_usepass_targets = primitives.iter_usepass_targets
iter_fallback_targets = primitives.iter_fallback_targets
parse_include_statements = primitives.parse_include_statements
iter_symbol_entries = primitives.iter_symbol_entries
iter_function_call_names = primitives.iter_function_call_names
is_probable_shaderlab_source = analysis_support.is_probable_shaderlab_source
module_aliases_for_path = analysis_support.module_aliases_for_path
parse_dependencies_only = analysis_support.parse_dependencies_only
parse_file = analysis_support.parse_file

__all__ = [
    "SHADERLAB_CONFIG_BASENAMES",
    "SHADERLAB_SOURCE_SUFFIXES",
    "has_shaderlab_path_hints",
    "is_probable_shaderlab_source",
    "iter_fallback_targets",
    "iter_function_call_names",
    "iter_shader_declarations",
    "iter_symbol_entries",
    "iter_usepass_targets",
    "module_aliases_for_path",
    "parse_dependencies_only",
    "parse_file",
    "parse_include_statements",
    "strip_comments",
]

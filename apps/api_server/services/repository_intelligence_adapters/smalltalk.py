from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.smalltalk_analysis_support import (
    module_aliases_for_path,
    parse_dependencies_only,
    parse_file,
)
from apps.api_server.services.repository_intelligence_adapters.smalltalk_primitives import (
    has_smalltalk_path_hints,
    is_probable_smalltalk_source,
    strip_comments,
)

__all__ = [
    "strip_comments",
    "has_smalltalk_path_hints",
    "is_probable_smalltalk_source",
    "module_aliases_for_path",
    "parse_dependencies_only",
    "parse_file",
]

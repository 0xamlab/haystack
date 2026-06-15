from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters.maven_analysis_support import (
    MAVEN_CONFIG_BASENAMES,
    MAVEN_PROJECT_BASENAMES,
    MavenPomDocument,
    has_maven_path_hints,
    is_probable_maven_source,
    module_aliases_for_path,
    module_name_from_path,
    normalize_identifier,
    parse_dependencies_only,
    parse_file,
    parse_maven_pom,
    resolve_project_path,
    strip_comments,
)

__all__ = [
    "MAVEN_CONFIG_BASENAMES",
    "MAVEN_PROJECT_BASENAMES",
    "MavenPomDocument",
    "has_maven_path_hints",
    "is_probable_maven_source",
    "module_aliases_for_path",
    "module_name_from_path",
    "normalize_identifier",
    "parse_dependencies_only",
    "parse_file",
    "parse_maven_pom",
    "resolve_project_path",
    "strip_comments",
]

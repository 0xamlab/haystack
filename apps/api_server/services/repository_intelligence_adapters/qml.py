from __future__ import annotations

from pathlib import Path

from apps.api_server.services.repository_intelligence_adapters import (
    qml_analysis_support as analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    qml_primitives as primitives,
)

QML_SUFFIXES = primitives.QML_SUFFIXES
QML_CONFIG_BASENAMES = primitives.QML_CONFIG_BASENAMES

strip_comments = primitives.strip_comments
has_qml_path_hints = primitives.has_qml_path_hints
is_probable_qml_source = primitives.is_probable_qml_source
iter_import_entries = primitives.iter_import_entries
iter_qmldir_exports = primitives.iter_qmldir_exports
iter_qmldir_module_names = primitives.iter_qmldir_module_names
iter_symbol_entries = primitives.iter_symbol_entries
iter_reference_names = primitives.iter_reference_names
module_name_from_path = primitives.module_name_from_path
module_aliases_for_path = analysis_support.module_aliases_for_path
resolve_import = analysis_support.resolve_import
parse_dependencies_only = analysis_support.parse_dependencies_only
parse_file = analysis_support.parse_file


def is_probable_qml_config(*, path: Path, text: str) -> bool:
    return path.name.lower() in QML_CONFIG_BASENAMES and is_probable_qml_source(path=path, text=text)

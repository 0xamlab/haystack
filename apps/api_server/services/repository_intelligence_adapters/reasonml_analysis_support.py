from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    reasonml_primitives as repository_reasonml_primitives,
)
from apps.api_server.services.repository_intelligence_adapters import (
    rescript_analysis_support as repository_rescript_analysis_support,
)

StableIdentifier = repository_reasonml_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_reasonml_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_reasonml_primitives.ResolveSuffixMatch

REASONML_SUFFIXES = repository_reasonml_primitives.REASONML_SUFFIXES
REASONML_CONFIG_BASENAMES = repository_reasonml_primitives.REASONML_CONFIG_BASENAMES
_CollectedSymbol = repository_reasonml_primitives._CollectedSymbol
_CALL_RE = repository_reasonml_primitives._CALL_RE
_MODULE_ALIAS_RE = repository_reasonml_primitives._MODULE_ALIAS_RE
_MODULE_DECL_RE = repository_reasonml_primitives._MODULE_DECL_RE
_OPEN_RE = repository_reasonml_primitives._OPEN_RE
_QUALIFIED_REFERENCE_RE = repository_reasonml_primitives._QUALIFIED_REFERENCE_RE
_RESERVED_SYMBOL_NAMES = repository_reasonml_primitives._RESERVED_SYMBOL_NAMES
_TYPE_REFERENCE_RE = repository_reasonml_primitives._TYPE_REFERENCE_RE
_VALUE_REFERENCE_RE = repository_reasonml_primitives._VALUE_REFERENCE_RE
_line_count = repository_reasonml_primitives._line_count
_line_number = repository_reasonml_primitives._line_number
_collect_symbols = repository_rescript_analysis_support._collect_symbols
has_reasonml_path_hints = repository_reasonml_primitives.has_reasonml_path_hints
is_probable_reasonml_config = repository_reasonml_primitives.is_probable_reasonml_config
is_probable_reasonml_source = repository_reasonml_primitives.is_probable_reasonml_source
iter_symbol_entries = repository_reasonml_primitives.iter_symbol_entries
module_name_from_path = repository_reasonml_primitives.module_name_from_path
strip_comments = repository_reasonml_primitives.strip_comments
extract_import_bindings = repository_rescript_analysis_support.extract_import_bindings
parse_dependencies_only = repository_rescript_analysis_support.parse_dependencies_only
parse_file = repository_rescript_analysis_support.parse_file


def _without_suffix_path(path: PurePosixPath) -> str:
    return str(path.with_suffix("")) if path.suffix else str(path)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in REASONML_SUFFIXES:
        return set()
    aliases = {
        file_path,
        _without_suffix_path(path),
        _without_suffix_path(path).replace("/", "."),
        path.stem,
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not is_probable_reasonml_source(path=Path(file_path), text=text):
        return {alias for alias in aliases if alias}
    for collected_symbol in _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    ):
        aliases.add(collected_symbol.symbol.symbol_name)
        aliases.update(collected_symbol.qualified_names)
    return {alias for alias in aliases if alias}


def resolve_import(
    import_target: str,
    module_index: dict[str, str],
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(import_target or "").strip()
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    module_path = normalized_target.replace(".", "/")
    candidate_keys = [
        normalized_target,
        module_path,
        f"{module_path}.re",
        f"{module_path}.rei",
        f"src/{module_path}.re",
        f"src/{module_path}.rei",
        f"lib/{module_path}.re",
        f"lib/{module_path}.rei",
        f"test/{module_path}.re",
        f"test/{module_path}.rei",
        f"tests/{module_path}.re",
        f"tests/{module_path}.rei",
        f"examples/{module_path}.re",
        f"examples/{module_path}.rei",
    ]
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if not normalized_candidate:
            continue
        resolved = module_index.get(normalized_candidate)
        if resolved is not None:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            f"{module_path}.re",
            f"/{module_path}.re",
            f"{module_path}.rei",
            f"/{module_path}.rei",
        ],
    )

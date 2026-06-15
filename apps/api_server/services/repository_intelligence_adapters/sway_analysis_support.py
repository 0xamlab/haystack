from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    rust_language as repository_rust_language,
)
from apps.api_server.services.repository_intelligence_adapters import (
    sway_primitives as repository_sway_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_sway_primitives.StableIdentifier

SWAY_SUFFIXES = repository_sway_primitives.SWAY_SUFFIXES
SWAY_CONFIG_BASENAMES = repository_sway_primitives.SWAY_CONFIG_BASENAMES
strip_comments = repository_sway_primitives.strip_comments
has_sway_path_hints = repository_sway_primitives.has_sway_path_hints
is_probable_sway_source = repository_sway_primitives.is_probable_sway_source
is_probable_sway_config = repository_sway_primitives.is_probable_sway_config
module_name_from_path = repository_sway_primitives.module_name_from_path
declared_symbol_names = repository_sway_primitives.declared_symbol_names


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    normalized_path = PurePosixPath(file_path)
    if normalized_path.suffix.lower() not in SWAY_SUFFIXES:
        return set()
    without_suffix = normalized_path.with_suffix("")
    module_name = module_name_from_path(file_path)
    aliases = {
        file_path,
        str(without_suffix),
        str(without_suffix).replace("/", "."),
        normalized_path.stem,
        module_name,
    }
    if normalized_path.stem in {"lib", "main", "mod"}:
        parent = str(normalized_path.parent)
        if parent and parent != ".":
            aliases.add(parent)
            aliases.add(parent.replace("/", "."))
        if normalized_path.stem in {"lib", "main"}:
            aliases.add("crate")
    try:
        source_text = (root_path / file_path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {alias for alias in aliases if alias}
    for symbol_name in declared_symbol_names(source_text):
        aliases.add(symbol_name)
        if module_name:
            aliases.add(f"{module_name}.{symbol_name}")
    return {alias for alias in aliases if alias}


def resolve_import(
    *,
    current_file: str,
    module_path: str,
    module_index: dict[str, str],
) -> str | None:
    return repository_rust_language.resolve_module_path(
        current_file=current_file,
        module_path=module_path,
        module_index=module_index,
    )


def resolve_child_module(
    *,
    current_file: str,
    module_name: str,
    module_index: dict[str, str],
) -> str | None:
    return repository_rust_language.resolve_child_module(
        current_file=current_file,
        module_name=module_name,
        module_index=module_index,
    )


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: repository_sway_primitives.NormalizeRepositoryRelativePath,
    resolve_suffix_match: repository_sway_primitives.ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    del normalize_repository_relative_path, resolve_suffix_match
    normalized_path = PurePosixPath(file_path)
    if (
        normalized_path.suffix.lower() not in SWAY_SUFFIXES
        and normalized_path.name.lower() not in SWAY_CONFIG_BASENAMES
    ) or normalized_path.name.lower() in SWAY_CONFIG_BASENAMES:
        return ()
    return repository_rust_language.parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_module_path=resolve_import,
        resolve_child_module=resolve_child_module,
    )


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: repository_sway_primitives.NormalizeRepositoryRelativePath,
    resolve_suffix_match: repository_sway_primitives.ResolveSuffixMatch,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    del normalize_repository_relative_path, resolve_suffix_match
    normalized_path = PurePosixPath(file_path)
    if (
        normalized_path.suffix.lower() not in SWAY_SUFFIXES
        and normalized_path.name.lower() not in SWAY_CONFIG_BASENAMES
    ) or normalized_path.name.lower() in SWAY_CONFIG_BASENAMES:
        return (), (), ()
    return repository_rust_language.parse_file(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_module_path=resolve_import,
        resolve_child_module=resolve_child_module,
    )

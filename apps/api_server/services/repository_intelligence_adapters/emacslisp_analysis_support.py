from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    emacslisp_primitives as repository_emacslisp_primitives,
)

StableIdentifier = repository_emacslisp_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_emacslisp_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_emacslisp_primitives.ResolveSuffixMatch

_KNOWN_EMACSLISP_SUFFIXES = repository_emacslisp_primitives._KNOWN_EMACSLISP_SUFFIXES
_EMACSLISP_MANIFEST_BASENAMES = (
    repository_emacslisp_primitives._EMACSLISP_MANIFEST_BASENAMES
)
_EMACSLISP_SOURCE_ROOTS = repository_emacslisp_primitives._EMACSLISP_SOURCE_ROOTS
_DEFINITION_HEAD_KINDS = repository_emacslisp_primitives._DEFINITION_HEAD_KINDS
_IMPORT_FORM_HEADS = repository_emacslisp_primitives._IMPORT_FORM_HEADS
_UNQUALIFIED_REFERENCE_RE = repository_emacslisp_primitives._UNQUALIFIED_REFERENCE_RE
RESERVED_SYMBOL_NAMES = repository_emacslisp_primitives.RESERVED_SYMBOL_NAMES
_extract_top_level_forms = repository_emacslisp_primitives._extract_top_level_forms
_form_head = repository_emacslisp_primitives._form_head
_normalize_repository_relative_path = (
    repository_emacslisp_primitives._normalize_repository_relative_path
)
_parse_form = repository_emacslisp_primitives._parse_form
_path_aliases = repository_emacslisp_primitives._path_aliases
_quoted_form_symbol = repository_emacslisp_primitives._quoted_form_symbol
_string_or_symbol_value = repository_emacslisp_primitives._string_or_symbol_value
collect_symbol_entries = repository_emacslisp_primitives.collect_symbol_entries
has_emacslisp_path_hints = repository_emacslisp_primitives.has_emacslisp_path_hints
is_probable_emacslisp_source = repository_emacslisp_primitives.is_probable_emacslisp_source
normalize_identifier = repository_emacslisp_primitives.normalize_identifier
normalize_symbol_name = repository_emacslisp_primitives.normalize_symbol_name
provided_features = repository_emacslisp_primitives.provided_features
strip_comments = repository_emacslisp_primitives.strip_comments


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if (
        path.suffix.lower() not in _KNOWN_EMACSLISP_SUFFIXES
        and path.name.lower() not in _EMACSLISP_MANIFEST_BASENAMES
    ):
        return set()
    aliases = set(_path_aliases(path))
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not text or not is_probable_emacslisp_source(path=Path(file_path), text=text):
        return aliases
    aliases.update(provided_features(text))
    for symbol_entry in collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    ):
        aliases.update(str(alias).lower() for alias in symbol_entry["qualified_names"] if alias)
    return {alias for alias in aliases if alias}


def _candidate_import_keys(import_target: str, *, current_file: str) -> tuple[str, ...]:
    normalized_target = normalize_identifier(import_target)
    if not normalized_target:
        return ()
    current_parent = PurePosixPath(current_file).parent
    raw_candidates = [normalized_target]
    if not PurePosixPath(normalized_target).suffix:
        raw_candidates.append(f"{normalized_target}.el")
    candidate_keys: list[str] = []
    seen_candidates: set[str] = set()
    for raw_candidate in raw_candidates:
        for candidate in (
            raw_candidate,
            str(current_parent / raw_candidate),
            *(f"{source_root}/{raw_candidate}" for source_root in _EMACSLISP_SOURCE_ROOTS),
        ):
            normalized_candidate = _normalize_repository_relative_path(candidate).lower()
            if not normalized_candidate or normalized_candidate in seen_candidates:
                continue
            seen_candidates.add(normalized_candidate)
            candidate_keys.append(normalized_candidate)
    return tuple(candidate_keys)


def _candidate_target_names(
    target_file: str,
    symbol_name: str,
    *,
    feature_names: tuple[str, ...] = (),
) -> tuple[str, ...]:
    normalized_symbol_name = normalize_symbol_name(symbol_name)
    if not normalized_symbol_name:
        return ()
    aliases = {normalized_symbol_name}
    path = PurePosixPath(target_file)
    for path_alias in _path_aliases(path):
        normalized_path_alias = normalize_identifier(path_alias)
        if normalized_path_alias:
            aliases.add(f"{normalized_path_alias}.{normalized_symbol_name}")
    for feature_name in feature_names:
        normalized_feature_name = normalize_identifier(feature_name)
        if normalized_feature_name:
            aliases.add(f"{normalized_feature_name}.{normalized_symbol_name}")
    return tuple(sorted(alias for alias in aliases if alias))


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    candidate_keys = _candidate_import_keys(import_target, current_file=current_file)
    if not candidate_keys:
        return None
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key).lower()
        direct_match = module_index.get(normalized_candidate)
        if direct_match is not None:
            return direct_match
    return resolve_suffix_match(module_index=module_index, suffixes=candidate_keys)


def _require_targets(parsed_form: Any) -> tuple[str, ...]:
    targets: list[str] = []
    seen_targets: set[str] = set()
    if _form_head(parsed_form) != "require":
        return ()
    for spec in parsed_form[1:]:
        target_name = _quoted_form_symbol(spec)
        if not target_name or target_name in seen_targets:
            continue
        seen_targets.add(target_name)
        targets.append(target_name)
    return tuple(targets)


def _extract_import_context(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[
    tuple[dict[str, Any], ...],
    dict[str, dict[str, Any]],
    dict[str, tuple[str, ...]],
    tuple[str, ...],
]:
    dependency_entries: list[dict[str, Any]] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    import_bindings: dict[str, dict[str, Any]] = {}
    imported_feature_names: dict[str, set[str]] = {}
    imported_files: list[str] = []

    def _register_dependency(target_file: str | None, target_symbol: str, line_no: int) -> None:
        dependency_key = (target_file, target_symbol, "imports")
        if dependency_key in dependency_keys:
            return
        dependency_keys.add(dependency_key)
        dependency_entries.append(
            {
                "dependency_edge_id": stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": target_symbol,
                        "line": line_no,
                    },
                ),
                "source_file": file_path,
                "target_file": target_file,
                "target_symbol": target_symbol,
                "dependency_type": "imports",
            }
        )

    for line_no, form_text in _extract_top_level_forms(text):
        parsed_form = _parse_form(form_text)
        head = _form_head(parsed_form)
        if head not in _IMPORT_FORM_HEADS:
            continue
        import_targets: list[tuple[str, str | None]] = []
        if head == "require":
            import_targets.extend((target, None) for target in _require_targets(parsed_form))
        elif head in {"load", "load-library"} and len(parsed_form) >= 2:
            import_target = _string_or_symbol_value(parsed_form[1])
            if import_target:
                import_targets.append((import_target, None))
        elif head == "use-package" and len(parsed_form) >= 2:
            import_target = normalize_identifier(str(parsed_form[1]))
            if import_target:
                import_targets.append((import_target, None))
        elif head == "autoload" and len(parsed_form) >= 3:
            local_name = _quoted_form_symbol(parsed_form[1])
            import_target = _string_or_symbol_value(parsed_form[2])
            if import_target:
                import_targets.append((import_target, local_name or None))
        for import_target, local_name in import_targets:
            target_file = resolve_import(
                current_file=file_path,
                import_target=import_target,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
            _register_dependency(target_file, import_target, line_no)
            if isinstance(target_file, str) and target_file not in imported_files:
                imported_files.append(target_file)
            if isinstance(target_file, str):
                imported_feature_names.setdefault(target_file, set()).add(import_target)
            if local_name and isinstance(target_file, str):
                import_bindings[normalize_symbol_name(local_name)] = {
                    "target_file": target_file,
                    "target_names": _candidate_target_names(
                        target_file,
                        local_name,
                        feature_names=(import_target,),
                    ),
                }
    return (
        tuple(dependency_entries),
        import_bindings,
        {
            target_file: tuple(sorted(feature_names))
            for target_file, feature_names in imported_feature_names.items()
        },
        tuple(imported_files),
    )


def _is_candidate_reference_symbol(symbol_name: str) -> bool:
    normalized = normalize_identifier(symbol_name)
    if not normalized:
        return False
    if normalized.startswith(":") or normalized.startswith("&"):
        return False
    return normalized not in RESERVED_SYMBOL_NAMES


def _resolve_reference_binding(
    *,
    reference_name: str,
    import_bindings: dict[str, dict[str, Any]],
    imported_feature_names: dict[str, tuple[str, ...]],
    imported_files: tuple[str, ...],
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[str | None, tuple[str, ...]]:
    normalized_reference_name = normalize_symbol_name(reference_name)
    binding = import_bindings.get(normalized_reference_name)
    if binding is not None:
        target_file = binding.get("target_file")
        if isinstance(target_file, str):
            target_names = tuple(
                str(name)
                for name in binding.get("target_names", ())
                if str(name).strip()
            )
            return target_file, target_names
    if not _is_candidate_reference_symbol(normalized_reference_name):
        return None, ()
    for target_file in imported_files:
        target_names = _candidate_target_names(
            target_file,
            normalized_reference_name,
            feature_names=imported_feature_names.get(target_file, ()),
        )
        for candidate_name in target_names:
            direct_match = module_index.get(candidate_name)
            if direct_match == target_file:
                return target_file, target_names
            resolved_match = resolve_suffix_match(
                module_index=module_index,
                suffixes=(normalize_repository_relative_path(candidate_name),),
            )
            if resolved_match == target_file:
                return target_file, target_names
        if module_index.get(normalized_reference_name) == target_file:
            return target_file, target_names
    return None, ()


def _reference_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    import_bindings: dict[str, dict[str, Any]],
    imported_feature_names: dict[str, tuple[str, ...]],
    imported_files: tuple[str, ...],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[dict[str, Any], ...]:
    bindings: list[dict[str, Any]] = []
    seen_bindings: set[tuple[int, str, tuple[str, ...]]] = set()
    for start_line, form_text in _extract_top_level_forms(text):
        parsed_form = _parse_form(form_text)
        head = _form_head(parsed_form)
        if head not in _DEFINITION_HEAD_KINDS:
            continue
        defined_symbol = normalize_symbol_name(str(parsed_form[1])) if len(parsed_form) >= 2 else ""
        for match in _UNQUALIFIED_REFERENCE_RE.finditer(form_text):
            symbol_name = normalize_symbol_name(str(match.group("name") or ""))
            if (
                not _is_candidate_reference_symbol(symbol_name)
                or symbol_name in {head, defined_symbol}
            ):
                continue
            target_file, target_names = _resolve_reference_binding(
                reference_name=symbol_name,
                import_bindings=import_bindings,
                imported_feature_names=imported_feature_names,
                imported_files=imported_files,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
            if target_file is None or target_file == file_path:
                continue
            line_no = start_line + form_text.count("\n", 0, match.start())
            binding_key = (line_no, target_file, tuple(target_names))
            if binding_key in seen_bindings:
                continue
            seen_bindings.add(binding_key)
            bindings.append(
                {
                    "line_no": line_no,
                    "target_file": target_file,
                    "target_names": tuple(target_names),
                    "target_symbol": normalize_symbol_name(
                        target_names[0] if target_names else symbol_name
                    ),
                }
            )
    return tuple(bindings)


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[dict[str, Any], ...]:
    dependency_entries, import_bindings, imported_feature_names, imported_files = (
        _extract_import_context(
            file_path,
            text,
            module_index,
            stable_identifier=stable_identifier,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
    )
    dependencies = list(dependency_entries)
    dependency_keys = {
        (entry["target_file"], entry["target_symbol"], entry["dependency_type"])
        for entry in dependencies
    }
    for binding in _reference_bindings(
        file_path,
        text,
        module_index,
        import_bindings=import_bindings,
        imported_feature_names=imported_feature_names,
        imported_files=imported_files,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    ):
        dependency_key = (binding["target_file"], binding["target_symbol"], "references")
        if dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        dependencies.append(
            {
                "dependency_edge_id": stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": binding["target_names"],
                        "line": binding["line_no"],
                        "kind": "form_reference",
                    },
                ),
                "source_file": file_path,
                "target_file": binding["target_file"],
                "target_symbol": binding["target_symbol"],
                "dependency_type": "references",
            }
        )
    return tuple(dependencies)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    symbol_entries = collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    )
    symbols = tuple(
        {
            "symbol_id": str(entry["symbol_id"]),
            "symbol_name": str(entry["symbol_name"]),
            "symbol_kind": str(entry["symbol_kind"]),
            "start_line": int(entry["start_line"]),
            "end_line": int(entry["end_line"]),
            "signature": str(entry["signature"]),
        }
        for entry in symbol_entries
    )
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    _, import_bindings, imported_feature_names, imported_files = _extract_import_context(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )

    def _symbol_for_line(line_no: int) -> dict[str, Any] | None:
        for symbol_entry in reversed(symbol_entries):
            if int(symbol_entry["start_line"]) <= line_no <= int(symbol_entry["end_line"]):
                return symbol_entry
        return None

    reference_candidates: dict[str, dict[str, Any]] = {}
    for binding in _reference_bindings(
        file_path,
        text,
        module_index,
        import_bindings=import_bindings,
        imported_feature_names=imported_feature_names,
        imported_files=imported_files,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    ):
        source_symbol = _symbol_for_line(int(binding["line_no"]))
        if source_symbol is None:
            continue
        edge_id = stable_identifier(
            "ref",
            {
                "source_symbol_id": source_symbol["symbol_id"],
                "target_file": binding["target_file"],
                "target_names": binding["target_names"],
                "type": "references_symbol",
            },
        )
        reference_candidates.setdefault(
            edge_id,
            {
                "reference_edge_id": edge_id,
                "source_symbol_id": str(source_symbol["symbol_id"]),
                "source_file": file_path,
                "target_symbol_id": None,
                "target_file": str(binding["target_file"]),
                "target_names": tuple(binding["target_names"]) or (str(binding["target_symbol"]),),
                "reference_type": "references_symbol",
            },
        )

    return (
        symbols,
        tuple(dependencies),
        tuple(reference_candidates.values()),
    )

from __future__ import annotations

import bisect
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    scheme_primitives as repository_scheme_primitives,
)

StableIdentifier = repository_scheme_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_scheme_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_scheme_primitives.ResolveSuffixMatch

_KNOWN_SCHEME_SUFFIXES = repository_scheme_primitives._KNOWN_SCHEME_SUFFIXES
_SCHEME_MANIFEST_BASENAMES = repository_scheme_primitives._SCHEME_MANIFEST_BASENAMES
_IMPORT_FORM_HEADS = repository_scheme_primitives._IMPORT_FORM_HEADS
_LOAD_FORM_HEADS = repository_scheme_primitives._LOAD_FORM_HEADS
_IMPORT_WRAPPER_HEADS = repository_scheme_primitives._IMPORT_WRAPPER_HEADS
_QUALIFIED_REFERENCE_RE = repository_scheme_primitives._QUALIFIED_REFERENCE_RE
_UNQUALIFIED_REFERENCE_RE = repository_scheme_primitives._UNQUALIFIED_REFERENCE_RE
_candidate_import_keys = repository_scheme_primitives._candidate_import_keys
_candidate_target_names = repository_scheme_primitives._candidate_target_names
_declared_library_aliases = repository_scheme_primitives._declared_library_aliases
_extract_top_level_forms = repository_scheme_primitives._extract_top_level_forms
_prepared_top_level_forms = repository_scheme_primitives._prepared_top_level_forms
_form_head = repository_scheme_primitives._form_head
_import_entries = repository_scheme_primitives._import_entries
_is_candidate_reference_symbol = (
    repository_scheme_primitives._is_candidate_reference_symbol
)
_load_targets = repository_scheme_primitives._load_targets
_normalize_repository_relative_path = (
    repository_scheme_primitives._normalize_repository_relative_path
)
_parse_form = repository_scheme_primitives._parse_form
_path_aliases = repository_scheme_primitives._path_aliases
collect_symbol_entries = repository_scheme_primitives.collect_symbol_entries
has_scheme_path_hints = repository_scheme_primitives.has_scheme_path_hints
is_probable_scheme_source = repository_scheme_primitives.is_probable_scheme_source
normalize_identifier = repository_scheme_primitives.normalize_identifier
normalize_symbol_name = repository_scheme_primitives.normalize_symbol_name
strip_comments = repository_scheme_primitives.strip_comments


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
    include_symbol_aliases: bool = True,
) -> set[str]:
    path = PurePosixPath(file_path)
    if (
        path.suffix.lower() not in _KNOWN_SCHEME_SUFFIXES
        and path.name.lower() not in _SCHEME_MANIFEST_BASENAMES
    ):
        return set()
    aliases = set(_path_aliases(path))
    loaded_text = text
    if loaded_text is None:
        try:
            loaded_text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            loaded_text = ""
    stripped_text = strip_comments(loaded_text) if loaded_text else ""
    if not loaded_text or not is_probable_scheme_source(
        path=Path(file_path),
        text=loaded_text,
        stripped_text=stripped_text,
    ):
        return aliases
    prepared_forms = _prepared_top_level_forms(loaded_text, stripped_text=stripped_text)
    library_aliases = _declared_library_aliases(
        loaded_text,
        stripped_text=stripped_text,
        prepared_forms=prepared_forms,
    )
    aliases.update(library_aliases)
    if not include_symbol_aliases:
        return {alias for alias in aliases if alias}
    for symbol_entry in collect_symbol_entries(
        loaded_text,
        file_path=file_path,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
        library_aliases=library_aliases,
    ):
        aliases.update(str(alias).lower() for alias in symbol_entry["qualified_names"] if alias)
    return {alias for alias in aliases if alias}


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


def _iter_nested_import_forms(parsed_form: Any) -> tuple[Any, ...]:
    import_forms: list[Any] = []

    def _visit(node: Any) -> None:
        if not isinstance(node, list) or not node:
            return
        head = _form_head(node)
        if head in _IMPORT_FORM_HEADS | _LOAD_FORM_HEADS:
            import_forms.append(node)
        for child in node[1:]:
            _visit(child)

    _visit(parsed_form)
    return tuple(import_forms)


def _extract_import_context(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    prepared_forms: tuple[tuple[int, str, Any], ...] | None = None,
) -> tuple[
    tuple[dict[str, Any], ...],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    tuple[dict[str, str], ...],
]:
    dependency_entries: list[dict[str, Any]] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    import_bindings: dict[str, dict[str, Any]] = {}
    prefix_bindings: dict[str, dict[str, Any]] = {}
    imported_files: list[dict[str, str]] = []

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

    for line_no, _form_text, parsed_form in (
        prepared_forms
        if prepared_forms is not None
        else tuple(
            (line_no, form_text, _parse_form(form_text))
            for line_no, form_text in _extract_top_level_forms(text)
        )
    ):
        for nested_form in _iter_nested_import_forms(parsed_form):
            head = _form_head(nested_form)
            if head in _IMPORT_FORM_HEADS:
                for spec in nested_form[1:]:
                    for entry in _import_entries(spec):
                        import_target = str(entry["import_target"])
                        target_file = resolve_import(
                            current_file=file_path,
                            import_target=import_target,
                            module_index=module_index,
                            normalize_repository_relative_path=normalize_repository_relative_path,
                            resolve_suffix_match=resolve_suffix_match,
                        )
                        _register_dependency(target_file, import_target, line_no)
                        if isinstance(target_file, str) and {
                            "target_file": target_file,
                            "import_target": import_target,
                        } not in imported_files:
                            imported_files.append(
                                {
                                    "target_file": target_file,
                                    "import_target": import_target,
                                }
                            )
                        prefix = str(entry.get("prefix") or "")
                        if prefix and target_file is not None:
                            prefix_bindings[prefix] = {
                                "target_file": target_file,
                                "import_target": import_target,
                            }
                        for local_name, source_name in entry.get("bindings", ()):
                            normalized_local_name = normalize_symbol_name(str(local_name))
                            normalized_source_name = normalize_symbol_name(str(source_name))
                            if not normalized_local_name:
                                continue
                            import_bindings[normalized_local_name] = {
                                "target_file": target_file,
                                "target_names": (
                                    ()
                                    if target_file is None
                                    else _candidate_target_names(
                                        target_file,
                                        normalized_source_name,
                                        import_target=import_target,
                                    )
                                ),
                            }
                continue
            if head in _LOAD_FORM_HEADS:
                for load_target in _load_targets(nested_form):
                    target_file = resolve_import(
                        current_file=file_path,
                        import_target=load_target,
                        module_index=module_index,
                        normalize_repository_relative_path=normalize_repository_relative_path,
                        resolve_suffix_match=resolve_suffix_match,
                    )
                    _register_dependency(target_file, load_target, line_no)
                    if isinstance(target_file, str) and {
                        "target_file": target_file,
                        "import_target": load_target,
                    } not in imported_files:
                        imported_files.append(
                            {
                                "target_file": target_file,
                                "import_target": load_target,
                            }
                        )
    return (
        tuple(dependency_entries),
        import_bindings,
        prefix_bindings,
        tuple(imported_files),
    )


def _resolve_reference_binding(
    *,
    reference_name: str,
    import_bindings: dict[str, dict[str, Any]],
    prefix_bindings: dict[str, dict[str, Any]],
    imported_files: tuple[dict[str, str], ...],
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
    match = _QUALIFIED_REFERENCE_RE.search(reference_name)
    if match is not None:
        prefix = normalize_identifier(str(match.group("prefix") or "")).rstrip(":")
        symbol_name = normalize_symbol_name(str(match.group("name") or ""))
        if prefix and symbol_name and prefix in prefix_bindings:
            target_file = str(prefix_bindings[prefix]["target_file"])
            import_target = str(prefix_bindings[prefix].get("import_target") or "")
            return target_file, _candidate_target_names(
                target_file,
                symbol_name,
                import_target=import_target or None,
            )
    if not _is_candidate_reference_symbol(normalized_reference_name):
        return None, ()
    for imported_entry in imported_files:
        target_file = str(imported_entry["target_file"])
        import_target = str(imported_entry.get("import_target") or "")
        target_names = _candidate_target_names(
            target_file,
            normalized_reference_name,
            import_target=import_target or None,
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
    prefix_bindings: dict[str, dict[str, Any]],
    imported_files: tuple[dict[str, str], ...],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    symbol_entries: list[dict[str, Any]] | None = None,
    stripped_text: str | None = None,
) -> tuple[dict[str, Any], ...]:
    bindings: list[dict[str, Any]] = []
    seen_bindings: set[tuple[int, str, tuple[str, ...]]] = set()
    resolved_reference_cache: dict[str, tuple[str | None, tuple[str, ...]]] = {}
    resolved_symbol_entries = (
        symbol_entries
        if symbol_entries is not None
        else collect_symbol_entries(
            text,
            file_path=file_path,
            stable_identifier=lambda *_args, **_kwargs: "",
            stripped_text=stripped_text,
        )
    )
    normalized_text = stripped_text if stripped_text is not None else strip_comments(text)
    lines = normalized_text.splitlines(keepends=True)
    line_offsets: list[int] = []
    current_offset = 0
    for line in lines:
        line_offsets.append(current_offset)
        current_offset += len(line)
    if not line_offsets:
        line_offsets.append(0)

    def _resolved_binding(reference_name: str) -> tuple[str | None, tuple[str, ...]]:
        cached_binding = resolved_reference_cache.get(reference_name)
        if cached_binding is not None:
            return cached_binding
        resolved_binding = _resolve_reference_binding(
            reference_name=reference_name,
            import_bindings=import_bindings,
            prefix_bindings=prefix_bindings,
            imported_files=imported_files,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        resolved_reference_cache[reference_name] = resolved_binding
        return resolved_binding

    def _line_no_for_offset(offset: int) -> int:
        return bisect.bisect_right(line_offsets, offset)

    def _line_slice(start_line: int, end_line: int) -> tuple[int, str]:
        start_index = line_offsets[max(0, start_line - 1)]
        if end_line < len(line_offsets):
            end_index = line_offsets[max(0, end_line)]
        else:
            end_index = len(normalized_text)
        return start_index, normalized_text[start_index:end_index]

    for symbol_entry in resolved_symbol_entries:
        symbol_start = int(symbol_entry["start_line"])
        symbol_end = int(symbol_entry["end_line"])
        slice_offset, slice_text = _line_slice(symbol_start, symbol_end)
        qualified_spans: list[tuple[int, int]] = []
        for match in _QUALIFIED_REFERENCE_RE.finditer(slice_text):
            prefix = normalize_identifier(str(match.group("prefix") or "")).rstrip(":")
            symbol_name = normalize_symbol_name(str(match.group("name") or ""))
            if not prefix or not _is_candidate_reference_symbol(symbol_name):
                continue
            qualified_spans.append(match.span())
            target_file, target_names = _resolved_binding(
                f"{prefix}:{symbol_name}",
            )
            if target_file is None or target_file == file_path:
                continue
            line_no = _line_no_for_offset(slice_offset + match.start())
            binding_key = (line_no, target_file, tuple(target_names))
            if binding_key in seen_bindings:
                continue
            seen_bindings.add(binding_key)
            bindings.append(
                {
                    "line_no": line_no,
                    "target_file": target_file,
                    "target_names": tuple(target_names),
                    "target_symbol": normalize_symbol_name(target_names[0]),
                }
            )
        for match in _UNQUALIFIED_REFERENCE_RE.finditer(slice_text):
            if any(start <= match.start() < end for start, end in qualified_spans):
                continue
            symbol_name = normalize_symbol_name(str(match.group("name") or ""))
            if not _is_candidate_reference_symbol(symbol_name):
                continue
            target_file, target_names = _resolved_binding(symbol_name)
            if target_file is None or target_file == file_path:
                continue
            line_no = _line_no_for_offset(slice_offset + match.start())
            binding_key = (line_no, target_file, tuple(target_names))
            if binding_key in seen_bindings:
                continue
            seen_bindings.add(binding_key)
            bindings.append(
                {
                    "line_no": line_no,
                    "target_file": target_file,
                    "target_names": tuple(target_names),
                    "target_symbol": normalize_symbol_name(target_names[0]),
                }
            )
    return tuple(bindings)


def _prepared_analysis_context(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[str, tuple[tuple[int, str, Any], ...], tuple[str, ...], list[dict[str, Any]]]:
    stripped_text = strip_comments(text)
    prepared_forms = _prepared_top_level_forms(text, stripped_text=stripped_text)
    library_aliases = _declared_library_aliases(
        text,
        stripped_text=stripped_text,
        prepared_forms=prepared_forms,
    )
    symbol_entries = collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
        library_aliases=library_aliases,
    )
    return stripped_text, prepared_forms, library_aliases, symbol_entries


def _build_dependencies_with_context(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    stripped_text: str,
    prepared_forms: tuple[tuple[int, str, Any], ...],
    symbol_entries: list[dict[str, Any]],
) -> tuple[
    tuple[dict[str, Any], ...],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    tuple[dict[str, str], ...],
]:
    dependency_entries, import_bindings, prefix_bindings, imported_files = (
        _extract_import_context(
            file_path,
            text,
            module_index,
            stable_identifier=stable_identifier,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
            prepared_forms=prepared_forms,
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
        prefix_bindings=prefix_bindings,
        imported_files=imported_files,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        symbol_entries=symbol_entries,
        stripped_text=stripped_text,
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
    return tuple(dependencies), import_bindings, prefix_bindings, imported_files


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[dict[str, Any], ...]:
    stripped_text, prepared_forms, _library_aliases, symbol_entries = _prepared_analysis_context(
        file_path=file_path,
        text=text,
        stable_identifier=lambda *_args, **_kwargs: "",
    )
    dependencies, _import_bindings, _prefix_bindings, _imported_files = (
        _build_dependencies_with_context(
            file_path=file_path,
            text=text,
            module_index=module_index,
            stable_identifier=stable_identifier,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
            stripped_text=stripped_text,
            prepared_forms=prepared_forms,
            symbol_entries=symbol_entries,
        )
    )
    return dependencies


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    stripped_text, prepared_forms, _library_aliases, symbol_entries = _prepared_analysis_context(
        file_path=file_path,
        text=text,
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
    dependencies, import_bindings, prefix_bindings, imported_files = _build_dependencies_with_context(
        file_path=file_path,
        text=text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        stripped_text=stripped_text,
        prepared_forms=prepared_forms,
        symbol_entries=symbol_entries,
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
        prefix_bindings=prefix_bindings,
        imported_files=imported_files,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        symbol_entries=symbol_entries,
        stripped_text=stripped_text,
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

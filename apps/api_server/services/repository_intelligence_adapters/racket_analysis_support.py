from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    racket_primitives as repository_racket_primitives,
)

StableIdentifier = repository_racket_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_racket_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_racket_primitives.ResolveSuffixMatch

_KNOWN_RACKET_SUFFIXES = repository_racket_primitives._KNOWN_RACKET_SUFFIXES
_RACKET_MANIFEST_BASENAMES = repository_racket_primitives._RACKET_MANIFEST_BASENAMES
_REQUIRE_FORM_HEADS = repository_racket_primitives._REQUIRE_FORM_HEADS
_QUALIFIED_REFERENCE_RE = repository_racket_primitives._QUALIFIED_REFERENCE_RE
_UNQUALIFIED_REFERENCE_RE = repository_racket_primitives._UNQUALIFIED_REFERENCE_RE
_candidate_import_keys = repository_racket_primitives._candidate_import_keys
_candidate_target_names = repository_racket_primitives._candidate_target_names
_extract_top_level_forms = repository_racket_primitives._extract_top_level_forms
_form_head = repository_racket_primitives._form_head
_is_candidate_reference_symbol = (
    repository_racket_primitives._is_candidate_reference_symbol
)
_normalize_repository_relative_path = (
    repository_racket_primitives._normalize_repository_relative_path
)
_parse_form = repository_racket_primitives._parse_form
_path_aliases = repository_racket_primitives._path_aliases
_require_entries = repository_racket_primitives._require_entries
collect_symbol_entries = repository_racket_primitives.collect_symbol_entries
has_racket_path_hints = repository_racket_primitives.has_racket_path_hints
is_probable_racket_source = repository_racket_primitives.is_probable_racket_source
normalize_identifier = repository_racket_primitives.normalize_identifier
normalize_symbol_name = repository_racket_primitives.normalize_symbol_name
strip_comments = repository_racket_primitives.strip_comments


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if (
        path.suffix.lower() not in _KNOWN_RACKET_SUFFIXES
        and path.name.lower() not in _RACKET_MANIFEST_BASENAMES
    ):
        return set()
    aliases = set(_path_aliases(path))
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not text or not is_probable_racket_source(path=Path(file_path), text=text):
        return aliases
    for symbol_entry in collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
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
    dict[str, dict[str, Any]],
    tuple[str, ...],
]:
    dependency_entries: list[dict[str, Any]] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    import_bindings: dict[str, dict[str, Any]] = {}
    prefix_bindings: dict[str, dict[str, Any]] = {}
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
        if _form_head(parsed_form) not in _REQUIRE_FORM_HEADS:
            continue
        for spec in parsed_form[1:]:
            for entry in _require_entries(spec):
                import_target = str(entry["import_target"])
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
                prefix = str(entry.get("prefix") or "")
                if prefix and target_file is not None:
                    prefix_bindings[prefix] = {"target_file": target_file}
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
                            else _candidate_target_names(target_file, normalized_source_name)
                        ),
                    }
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
    match = _QUALIFIED_REFERENCE_RE.search(reference_name)
    if match is not None:
        prefix = normalize_identifier(str(match.group("prefix") or "")).rstrip(":")
        symbol_name = normalize_symbol_name(str(match.group("name") or ""))
        if prefix and symbol_name and prefix in prefix_bindings:
            target_file = str(prefix_bindings[prefix]["target_file"])
            return target_file, _candidate_target_names(target_file, symbol_name)
    if not _is_candidate_reference_symbol(normalized_reference_name):
        return None, ()
    for target_file in imported_files:
        target_names = _candidate_target_names(target_file, normalized_reference_name)
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
    imported_files: tuple[str, ...],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[dict[str, Any], ...]:
    bindings: list[dict[str, Any]] = []
    seen_bindings: set[tuple[int, str, tuple[str, ...]]] = set()
    symbol_entries = collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=lambda *_args, **_kwargs: "",
    )
    stripped_text = strip_comments(text)
    lines = stripped_text.splitlines(keepends=True)
    line_offsets: list[int] = []
    current_offset = 0
    for line in lines:
        line_offsets.append(current_offset)
        current_offset += len(line)
    if not line_offsets:
        line_offsets.append(0)

    def _line_slice(start_line: int, end_line: int) -> tuple[int, str]:
        start_index = line_offsets[max(0, start_line - 1)]
        if end_line < len(line_offsets):
            end_index = line_offsets[max(0, end_line)]
        else:
            end_index = len(stripped_text)
        return start_index, stripped_text[start_index:end_index]

    for symbol_entry in symbol_entries:
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
            target_file, target_names = _resolve_reference_binding(
                reference_name=f"{prefix}:{symbol_name}",
                import_bindings=import_bindings,
                prefix_bindings=prefix_bindings,
                imported_files=imported_files,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
            if target_file is None or target_file == file_path:
                continue
            line_no = stripped_text.count("\n", 0, slice_offset + match.start()) + 1
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
            target_file, target_names = _resolve_reference_binding(
                reference_name=symbol_name,
                import_bindings=import_bindings,
                prefix_bindings=prefix_bindings,
                imported_files=imported_files,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
            if target_file is None or target_file == file_path:
                continue
            line_no = stripped_text.count("\n", 0, slice_offset + match.start()) + 1
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


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[dict[str, Any], ...]:
    dependency_entries, import_bindings, prefix_bindings, imported_files = (
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
        prefix_bindings=prefix_bindings,
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
    _, import_bindings, prefix_bindings, imported_files = _extract_import_context(
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
        prefix_bindings=prefix_bindings,
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

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters.lisp_support import (
    _DEFINITION_HEAD_KINDS,
    _KNOWN_LISP_SUFFIXES,
    _LISP_MARKER_RE,
    _LOAD_FORM_HEADS,
    _PACKAGE_FORM_HEADS,
    _PACKAGE_IMPORT_OPTION_HEADS,
    _PACKAGE_LOCAL_NICKNAME_HEADS,
    _PACKAGE_USE_OPTION_HEADS,
    _QUALIFIED_REFERENCE_RE,
    _UNQUALIFIED_REFERENCE_RE,
    RESERVED_SYMBOL_NAMES,
    NormalizeRepositoryRelativePath,
    ResolveSuffixMatch,
    StableIdentifier,
    _extract_top_level_forms,
    _form_head,
    _normalize_keyword,
    _normalize_repository_relative_path,
    _package_symbol_name,
    _parse_form,
    _path_aliases,
    normalize_identifier,
    normalize_package_name,
    normalize_symbol_name,
    project_component_entries,
    project_system_names,
    strip_comments,
)


def _package_form_bindings(
    parsed_form: Any,
) -> tuple[
    str,
    tuple[str, ...],
    tuple[tuple[str, tuple[str, ...]], ...],
    dict[str, str],
]:
    if _form_head(parsed_form) not in _PACKAGE_FORM_HEADS or len(parsed_form) < 2:
        return "", (), (), {}
    package_name = normalize_package_name(str(parsed_form[1]))
    used_packages: list[str] = []
    imported_specs: list[tuple[str, tuple[str, ...]]] = []
    local_nicknames: dict[str, str] = {}
    for option in parsed_form[2:]:
        if not isinstance(option, list) or not option:
            continue
        option_head = _normalize_keyword(str(option[0]))
        if option_head in _PACKAGE_USE_OPTION_HEADS:
            for value in option[1:]:
                target_package = normalize_package_name(str(value))
                if target_package:
                    used_packages.append(target_package)
            continue
        if option_head in _PACKAGE_IMPORT_OPTION_HEADS and len(option) >= 2:
            target_package = normalize_package_name(str(option[1]))
            imported_names = tuple(
                name
                for value in option[2:]
                if (name := normalize_symbol_name(str(value)))
            )
            if target_package:
                imported_specs.append((target_package, imported_names))
            continue
        if option_head in _PACKAGE_LOCAL_NICKNAME_HEADS:
            for nickname_pair in option[1:]:
                if not isinstance(nickname_pair, list) or len(nickname_pair) < 2:
                    continue
                alias = normalize_package_name(str(nickname_pair[0]))
                target_package = normalize_package_name(str(nickname_pair[1]))
                if alias and target_package:
                    local_nicknames[alias] = target_package
    return (
        package_name,
        tuple(dict.fromkeys(package for package in used_packages if package)),
        tuple(imported_specs),
        local_nicknames,
    )


def _current_package_name(text: str) -> str:
    package_name = ""
    for _line_no, form_text in _extract_top_level_forms(text):
        parsed_form = _parse_form(form_text)
        head = _form_head(parsed_form)
        if head in _PACKAGE_FORM_HEADS:
            candidate = normalize_package_name(str(parsed_form[1])) if len(parsed_form) >= 2 else ""
            if candidate and not package_name:
                package_name = candidate
        if head == "in-package" and len(parsed_form) >= 2:
            candidate = normalize_package_name(str(parsed_form[1]))
            if candidate:
                return candidate
    return package_name


def _load_targets(parsed_form: Any) -> tuple[str, ...]:
    head = _form_head(parsed_form)
    if head not in _LOAD_FORM_HEADS or len(parsed_form) < 2:
        return ()
    target_value = parsed_form[1]
    if isinstance(target_value, list):
        targets = [
            normalize_identifier(str(value))
            for value in target_value
            if normalize_identifier(str(value))
        ]
        return tuple(dict.fromkeys(targets))
    target = normalize_identifier(str(target_value))
    return (target,) if target else ()


def _candidate_import_keys(import_target: str, *, current_file: str) -> tuple[str, ...]:
    normalized_target = normalize_package_name(import_target)
    if not normalized_target:
        normalized_target = normalize_identifier(import_target)
    if not normalized_target:
        return ()
    current_parent = PurePosixPath(current_file).parent
    pathified_target = normalized_target.replace(".", "/")
    raw_candidates = [normalized_target, pathified_target]
    if not PurePosixPath(normalized_target).suffix:
        raw_candidates.extend(f"{normalized_target}{suffix}" for suffix in _KNOWN_LISP_SUFFIXES)
        raw_candidates.extend(f"{pathified_target}{suffix}" for suffix in _KNOWN_LISP_SUFFIXES)
        raw_candidates.append(f"{normalized_target}.asd")
    candidate_keys: list[str] = []
    seen_candidates: set[str] = set()
    for raw_candidate in raw_candidates:
        for candidate in (
            raw_candidate,
            str(current_parent / raw_candidate),
            f"src/{raw_candidate}",
            f"lib/{raw_candidate}",
            f"systems/{raw_candidate}",
            f"lisp/{raw_candidate}",
        ):
            normalized_candidate = _normalize_repository_relative_path(candidate).lower()
            if not normalized_candidate or normalized_candidate in seen_candidates:
                continue
            seen_candidates.add(normalized_candidate)
            candidate_keys.append(normalized_candidate)
    return tuple(candidate_keys)


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


def _qualified_target_names(package_name: str, symbol_name: str) -> tuple[str, ...]:
    qualified_names: list[str] = []
    seen_names: set[str] = set()
    for candidate_name in (
        symbol_name,
        f"{package_name}.{symbol_name}" if package_name else "",
        f"{package_name}:{symbol_name}" if package_name else "",
        f"{package_name}::{symbol_name}" if package_name else "",
    ):
        normalized_name = normalize_identifier(candidate_name)
        if not normalized_name or normalized_name in seen_names:
            continue
        seen_names.add(normalized_name)
        qualified_names.append(normalized_name)
    return tuple(qualified_names)


def _is_candidate_reference_symbol(symbol_name: str) -> bool:
    normalized = normalize_identifier(symbol_name)
    if not normalized:
        return False
    if normalized.startswith(":") or normalized.startswith("&"):
        return False
    return normalized not in RESERVED_SYMBOL_NAMES


def _resolve_reference_binding(
    *,
    current_file: str,
    reference_name: str,
    current_package: str,
    used_packages: tuple[str, ...],
    package_aliases: dict[str, str],
    import_bindings: dict[str, dict[str, Any]],
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[str | None, tuple[str, ...]]:
    binding = import_bindings.get(normalize_symbol_name(reference_name))
    if binding is not None:
        target_file = binding.get("target_file")
        if isinstance(target_file, str):
            return target_file, tuple(
                str(name)
                for name in binding.get("target_names", ())
                if str(name).strip()
            )
    package_name, symbol_name = _package_symbol_name(reference_name)
    if not symbol_name or not _is_candidate_reference_symbol(symbol_name):
        return None, ()
    candidate_packages: list[str] = []
    if package_name:
        candidate_packages.append(package_aliases.get(package_name, package_name))
    elif current_package:
        candidate_packages.append(current_package)
        candidate_packages.extend(used_packages)
    candidate_names: list[str] = []
    seen_names: set[str] = set()
    if not candidate_packages:
        candidate_packages = [""]
    for candidate_package in candidate_packages:
        for candidate_name in _qualified_target_names(candidate_package, symbol_name):
            if candidate_name in seen_names:
                continue
            seen_names.add(candidate_name)
            candidate_names.append(candidate_name)
            direct_match = module_index.get(candidate_name)
            if direct_match is not None and direct_match != current_file:
                return direct_match, tuple(_qualified_target_names(candidate_package, symbol_name))
    if package_name:
        target_file = resolve_import(
            current_file=current_file,
            import_target=package_aliases.get(package_name, package_name),
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        if target_file is not None and target_file != current_file:
            resolved_package = package_aliases.get(package_name, package_name)
            return target_file, _qualified_target_names(resolved_package, symbol_name)
    if current_package:
        target_file = resolve_suffix_match(
            module_index=module_index,
            suffixes=tuple(
                normalize_repository_relative_path(name)
                for name in _qualified_target_names(current_package, symbol_name)
            ),
        )
        if target_file is not None and target_file != current_file:
            return target_file, _qualified_target_names(current_package, symbol_name)
    return None, ()


def _definition_name(parsed_form: Any) -> str:
    if not isinstance(parsed_form, list) or len(parsed_form) < 2:
        return ""
    head = _form_head(parsed_form)
    if head not in _DEFINITION_HEAD_KINDS:
        return ""
    name_value = parsed_form[1]
    if isinstance(name_value, list):
        if not name_value:
            return ""
        return normalize_symbol_name(str(name_value[0]))
    return normalize_symbol_name(str(name_value))


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    stripped_text = strip_comments(text)
    current_package = _current_package_name(text)
    file_alias = normalize_identifier(PurePosixPath(file_path).stem)
    final_line = len(stripped_text.splitlines()) if stripped_text else 1
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, int]] = set()
    for line_no, form_text in _extract_top_level_forms(text):
        parsed_form = _parse_form(form_text)
        head = _form_head(parsed_form)
        symbol_kind = _DEFINITION_HEAD_KINDS.get(head)
        symbol_name = _definition_name(parsed_form)
        if symbol_kind is None or not symbol_name:
            continue
        symbol_key = (symbol_name, line_no)
        if symbol_key in seen_symbol_keys:
            continue
        seen_symbol_keys.add(symbol_key)
        qualified_names = set(_qualified_target_names(current_package, symbol_name))
        if file_alias and file_alias != symbol_name:
            qualified_names.add(f"{file_alias}.{symbol_name}")
        symbol_entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": symbol_name,
                        "kind": symbol_kind,
                        "line": line_no,
                    },
                ),
                "symbol_name": symbol_name,
                "symbol_kind": symbol_kind,
                "start_line": line_no,
                "end_line": line_no,
                "signature": form_text.splitlines()[0].strip(),
                "qualified_names": tuple(sorted(name for name in qualified_names if name)),
            }
        )
    for index, entry in enumerate(symbol_entries):
        if index + 1 < len(symbol_entries):
            entry["end_line"] = max(
                int(symbol_entries[index + 1]["start_line"]) - 1,
                int(entry["start_line"]),
            )
        else:
            entry["end_line"] = final_line
    return symbol_entries


def is_probable_lisp_source(*, path: Path, text: str) -> bool:
    suffix = path.suffix.lower()
    if suffix not in _KNOWN_LISP_SUFFIXES:
        return False
    stripped_text = strip_comments(text)
    if suffix == ".asd":
        return bool(
            re.search(
                r"\(\s*(?:asdf:defsystem|defsystem)\b",
                stripped_text,
                flags=re.IGNORECASE,
            )
        )
    return bool(_LISP_MARKER_RE.search(stripped_text))


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_LISP_SUFFIXES:
        return set()
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not text or not is_probable_lisp_source(path=Path(file_path), text=text):
        return set()
    aliases = set(_path_aliases(path))
    if path.suffix.lower() == ".asd":
        aliases.update(project_system_names(text))
        return {alias for alias in aliases if alias}
    for line_no, form_text in _extract_top_level_forms(text):
        del line_no
        parsed_form = _parse_form(form_text)
        if _form_head(parsed_form) in _PACKAGE_FORM_HEADS:
            package_name, _used, _imports, _nicknames = _package_form_bindings(parsed_form)
            if package_name:
                aliases.add(package_name)
    for symbol_entry in collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    ):
        aliases.update(str(alias).lower() for alias in symbol_entry["qualified_names"] if alias)
    return {alias for alias in aliases if alias}


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
    str,
    tuple[str, ...],
    dict[str, str],
]:
    if PurePosixPath(file_path).suffix.lower() == ".asd":
        dependency_entries: list[dict[str, Any]] = []
        dependency_keys: set[tuple[str | None, str, str]] = set()
        component_entries = project_component_entries(text, manifest_path=file_path)
        component_lookup = {
            str(entry["component_name"]): str(entry["path"])
            for entry in component_entries
            if str(entry["component_name"])
        }
        for entry in component_entries:
            target_file = str(entry["path"])
            if not target_file:
                continue
            dependency_key = (target_file, str(entry["component_name"]), "imports")
            if dependency_key not in dependency_keys:
                dependency_keys.add(dependency_key)
                dependency_entries.append(
                    {
                        "dependency_edge_id": stable_identifier(
                            "dep",
                            {
                                "file_path": file_path,
                                "target": target_file,
                                "line": 1,
                            },
                        ),
                        "source_file": file_path,
                        "target_file": target_file,
                        "target_symbol": str(entry["component_name"]),
                        "dependency_type": "imports",
                    }
                )
            for dependency_name in entry["depends_on_names"]:
                dependent_file = component_lookup.get(str(dependency_name))
                if dependent_file is None:
                    continue
                dependency_key = (dependent_file, str(dependency_name), "references")
                if dependency_key in dependency_keys:
                    continue
                dependency_keys.add(dependency_key)
                dependency_entries.append(
                    {
                        "dependency_edge_id": stable_identifier(
                            "dep",
                            {
                                "file_path": file_path,
                                "target": dependent_file,
                                "line": 1,
                                "kind": "component_depends_on",
                            },
                        ),
                        "source_file": file_path,
                        "target_file": dependent_file,
                        "target_symbol": str(dependency_name),
                        "dependency_type": "references",
                    }
                )
        for system_name in project_system_names(text):
            target_file = resolve_import(
                current_file=file_path,
                import_target=system_name,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
            if target_file is None or target_file == file_path:
                continue
            dependency_key = (target_file, system_name, "imports")
            if dependency_key in dependency_keys:
                continue
            dependency_keys.add(dependency_key)
            dependency_entries.append(
                {
                    "dependency_edge_id": stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": system_name,
                            "line": 1,
                            "kind": "load_system",
                        },
                    ),
                    "source_file": file_path,
                    "target_file": target_file,
                    "target_symbol": system_name,
                    "dependency_type": "imports",
                }
            )
        return tuple(dependency_entries), {}, "", (), {}

    current_package = _current_package_name(text)
    used_packages: list[str] = []
    package_aliases: dict[str, str] = {}
    import_bindings: dict[str, dict[str, Any]] = {}
    dependency_entries: list[dict[str, Any]] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()

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

    def _apply_package_bindings(
        *,
        line_no: int,
        package_name: str,
        form_used_packages: tuple[str, ...],
        imported_specs: tuple[tuple[str, tuple[str, ...]], ...],
        local_nicknames: dict[str, str],
    ) -> None:
        nonlocal current_package
        if package_name and not current_package:
            current_package = package_name
        for used_package in form_used_packages:
            target_file = resolve_import(
                current_file=file_path,
                import_target=used_package,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
            _register_dependency(target_file, used_package, line_no)
            used_packages.append(used_package)
        for imported_package, imported_names in imported_specs:
            target_file = resolve_import(
                current_file=file_path,
                import_target=imported_package,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
            _register_dependency(target_file, imported_package, line_no)
            for imported_name in imported_names:
                import_bindings.setdefault(
                    imported_name,
                    {
                        "alias": imported_name,
                        "target_file": target_file,
                        "target_names": _qualified_target_names(imported_package, imported_name),
                    },
                )
        for alias, target_package in local_nicknames.items():
            package_aliases[alias] = target_package
            target_file = resolve_import(
                current_file=file_path,
                import_target=target_package,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
            _register_dependency(target_file, target_package, line_no)

    for line_no, form_text in _extract_top_level_forms(text):
        parsed_form = _parse_form(form_text)
        head = _form_head(parsed_form)
        if head in _PACKAGE_FORM_HEADS:
            package_name, form_used_packages, imported_specs, local_nicknames = (
                _package_form_bindings(parsed_form)
            )
            _apply_package_bindings(
                line_no=line_no,
                package_name=package_name,
                form_used_packages=form_used_packages,
                imported_specs=imported_specs,
                local_nicknames=local_nicknames,
            )
            continue
        if head == "in-package" and len(parsed_form) >= 2:
            candidate = normalize_package_name(str(parsed_form[1]))
            if candidate:
                current_package = candidate
            continue
        for load_target in _load_targets(parsed_form):
            target_file = resolve_import(
                current_file=file_path,
                import_target=load_target,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
            _register_dependency(target_file, load_target, line_no)

    normalized_used_packages = tuple(dict.fromkeys(package for package in used_packages if package))
    if current_package:
        package_aliases.setdefault(current_package, current_package)
    return (
        tuple(dependency_entries),
        import_bindings,
        current_package,
        normalized_used_packages,
        package_aliases,
    )


def _reference_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    import_bindings: dict[str, dict[str, Any]],
    current_package: str,
    used_packages: tuple[str, ...],
    package_aliases: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[dict[str, Any], ...]:
    if PurePosixPath(file_path).suffix.lower() == ".asd":
        return ()
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
            symbol_name = normalize_symbol_name(str(match.group("name") or ""))
            package_name = normalize_package_name(str(match.group("package") or ""))
            if not package_name or not _is_candidate_reference_symbol(symbol_name):
                continue
            qualified_spans.append(match.span())
            target_file, target_names = _resolve_reference_binding(
                current_file=file_path,
                reference_name=f"{package_name}:{symbol_name}",
                current_package=current_package,
                used_packages=used_packages,
                package_aliases=package_aliases,
                import_bindings=import_bindings,
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
                current_file=file_path,
                reference_name=symbol_name,
                current_package=current_package,
                used_packages=used_packages,
                package_aliases=package_aliases,
                import_bindings=import_bindings,
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
    dependency_entries, import_bindings, current_package, used_packages, package_aliases = (
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
        current_package=current_package,
        used_packages=used_packages,
        package_aliases=package_aliases,
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
    dependency_entries, import_bindings, current_package, used_packages, package_aliases = (
        _extract_import_context(
            file_path,
            text,
            module_index,
            stable_identifier=stable_identifier,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
    )
    dependencies = list(
        parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=stable_identifier,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
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
        current_package=current_package,
        used_packages=used_packages,
        package_aliases=package_aliases,
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
                "target_names": tuple(binding["target_names"]),
                "reference_type": "references_symbol",
            },
        )
    return (
        symbols,
        tuple(dependencies),
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )

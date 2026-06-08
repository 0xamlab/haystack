from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    vala_primitives as repository_vala_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_vala_primitives.StableIdentifier
ResolveSuffixMatch = repository_vala_primitives.ResolveSuffixMatch
ResolveDirectoryPrefixMatch = repository_vala_primitives.ResolveDirectoryPrefixMatch

_BUILTIN_TYPE_NAMES = repository_vala_primitives._BUILTIN_TYPE_NAMES
_INSTANCE_ASSIGN_RE = repository_vala_primitives._INSTANCE_ASSIGN_RE
_KNOWN_SUFFIXES = repository_vala_primitives._KNOWN_SUFFIXES
_METHOD_DECL_RE = repository_vala_primitives._METHOD_DECL_RE
_NAMESPACE_RE = repository_vala_primitives._NAMESPACE_RE
_NEW_REFERENCE_RE = repository_vala_primitives._NEW_REFERENCE_RE
_QUALIFIED_REFERENCE_RE = repository_vala_primitives._QUALIFIED_REFERENCE_RE
_RESERVED_SYMBOL_NAMES = repository_vala_primitives._RESERVED_SYMBOL_NAMES
_TYPE_DECL_RE = repository_vala_primitives._TYPE_DECL_RE
_USING_RE = repository_vala_primitives._USING_RE
has_vala_path_hints = repository_vala_primitives.has_vala_path_hints
is_probable_vala_source = repository_vala_primitives.is_probable_vala_source
normalize_symbol_name = repository_vala_primitives.normalize_symbol_name
normalize_target = repository_vala_primitives.normalize_target
split_relation_targets = repository_vala_primitives.split_relation_targets
strip_comments = repository_vala_primitives.strip_comments
without_suffix_aliases = repository_vala_primitives.without_suffix_aliases


def namespace_paths(text: str) -> tuple[str, ...]:
    namespace_entries = _collect_symbol_entries(text, file_path="", stable_identifier=lambda *_: "")
    namespaces = {
        str(entry["namespace"]).lower()
        for entry in namespace_entries
        if entry["namespace"]
    }
    return tuple(sorted(namespace for namespace in namespaces if namespace))


def _line_count(text: str) -> int:
    return max(1, len(text.splitlines()))


def _namespace_for_symbols(namespace_stack: list[dict[str, Any]]) -> str:
    if not namespace_stack:
        return ""
    return str(namespace_stack[-1]["name"])


def _collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, str, int]] = set()
    namespace_stack: list[dict[str, Any]] = []
    type_stack: list[dict[str, Any]] = []
    brace_depth = 0
    final_line = _line_count(text)
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        while namespace_stack and brace_depth < int(namespace_stack[-1]["depth"]):
            namespace_stack.pop()
        while type_stack and brace_depth < int(type_stack[-1]["depth"]):
            type_stack.pop()

        stripped_line = raw_line.strip()
        if not stripped_line:
            continue
        opens = raw_line.count("{")
        closes = raw_line.count("}")
        namespace_match = _NAMESPACE_RE.match(stripped_line)
        if namespace_match is not None:
            target = normalize_target(str(namespace_match.group("target") or ""))
            if target:
                parent_namespace = _namespace_for_symbols(namespace_stack)
                if "." in target or not parent_namespace:
                    qualified_namespace = target
                else:
                    qualified_namespace = f"{parent_namespace}.{target}"
                namespace_stack.append(
                    {
                        "depth": max(0, brace_depth + opens - closes),
                        "name": qualified_namespace,
                    }
                )
            brace_depth = max(0, brace_depth + opens - closes)
            continue

        current_namespace = _namespace_for_symbols(namespace_stack)
        type_match = _TYPE_DECL_RE.match(stripped_line)
        if type_match is not None:
            symbol_name = normalize_symbol_name(str(type_match.group("name") or ""))
            if symbol_name and symbol_name.lower() not in _RESERVED_SYMBOL_NAMES:
                qualified_names = {symbol_name}
                if current_namespace:
                    qualified_names.add(f"{current_namespace}.{symbol_name}")
                parent_symbol_id = (
                    str(type_stack[-1]["symbol_id"]) if type_stack else None
                )
                symbol_key = ("type", symbol_name.lower(), line_no)
                if symbol_key not in seen_symbol_keys:
                    seen_symbol_keys.add(symbol_key)
                    symbol_id = stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "name": symbol_name,
                            "line": line_no,
                            "kind": "type",
                        },
                    )
                    symbol_entries.append(
                        {
                            "symbol_id": symbol_id,
                            "symbol_name": symbol_name,
                            "symbol_kind": "type",
                            "start_line": line_no,
                            "end_line": line_no,
                            "signature": stripped_line,
                            "qualified_names": tuple(sorted(qualified_names)),
                            "namespace": current_namespace,
                            "parent_symbol_id": parent_symbol_id,
                        }
                    )
                    type_stack.append(
                        {
                            "depth": max(0, brace_depth + opens - closes),
                            "qualified_name": (
                                f"{current_namespace}.{symbol_name}"
                                if current_namespace
                                else symbol_name
                            ),
                            "symbol_id": symbol_id,
                        }
                    )
            brace_depth = max(0, brace_depth + opens - closes)
            continue

        method_match = _METHOD_DECL_RE.match(stripped_line)
        if method_match is not None:
            symbol_name = normalize_symbol_name(str(method_match.group("name") or ""))
            if symbol_name and symbol_name.lower() not in _RESERVED_SYMBOL_NAMES:
                qualified_names = {symbol_name}
                parent_symbol_id = None
                if type_stack:
                    qualified_names.add(
                        f"{type_stack[-1]['qualified_name']}.{symbol_name}"
                    )
                    parent_symbol_id = str(type_stack[-1]["symbol_id"])
                elif current_namespace:
                    qualified_names.add(f"{current_namespace}.{symbol_name}")
                symbol_kind = "method" if type_stack else "function"
                symbol_key = (symbol_kind, symbol_name.lower(), line_no)
                if symbol_key not in seen_symbol_keys:
                    seen_symbol_keys.add(symbol_key)
                    symbol_entries.append(
                        {
                            "symbol_id": stable_identifier(
                                "sym",
                                {
                                    "file_path": file_path,
                                    "name": symbol_name,
                                    "line": line_no,
                                    "kind": symbol_kind,
                                },
                            ),
                            "symbol_name": symbol_name,
                            "symbol_kind": symbol_kind,
                            "start_line": line_no,
                            "end_line": line_no,
                            "signature": stripped_line,
                            "qualified_names": tuple(sorted(qualified_names)),
                            "namespace": current_namespace,
                            "parent_symbol_id": parent_symbol_id,
                        }
                    )
        brace_depth = max(0, brace_depth + opens - closes)

    for index, entry in enumerate(symbol_entries):
        if index + 1 < len(symbol_entries):
            entry["end_line"] = max(
                int(symbol_entries[index + 1]["start_line"]) - 1,
                int(entry["start_line"]),
            )
        else:
            entry["end_line"] = final_line
    return symbol_entries


def _symbol_from_entry(entry: dict[str, Any]) -> _Symbol:
    return _Symbol(
        symbol_id=str(entry["symbol_id"]),
        symbol_name=str(entry["symbol_name"]),
        symbol_kind=str(entry["symbol_kind"]),
        start_line=int(entry["start_line"]),
        end_line=int(entry["end_line"]),
        parent_symbol_id=(
            str(entry["parent_symbol_id"])
            if entry["parent_symbol_id"] is not None
            else None
        ),
        signature=str(entry["signature"]) if entry["signature"] is not None else None,
    )


def _dependency_from_entry(entry: dict[str, Any]) -> _Dependency:
    return _Dependency(
        dependency_edge_id=str(entry["dependency_edge_id"]),
        source_file=str(entry["source_file"]),
        target_file=str(entry["target_file"]) if entry["target_file"] is not None else None,
        target_symbol=(
            str(entry["target_symbol"]) if entry["target_symbol"] is not None else None
        ),
        dependency_type=str(entry["dependency_type"]),
    )


def _symbol_reference_from_entry(
    entry: dict[str, Any],
) -> _SymbolReferenceCandidate:
    return _SymbolReferenceCandidate(
        reference_edge_id=str(entry["reference_edge_id"]),
        source_symbol_id=str(entry["source_symbol_id"]),
        source_file=str(entry["source_file"]),
        target_symbol_id=(
            str(entry["target_symbol_id"])
            if entry["target_symbol_id"] is not None
            else None
        ),
        target_file=str(entry["target_file"]) if entry["target_file"] is not None else None,
        target_names=tuple(str(name) for name in entry["target_names"]),
        reference_type=str(entry["reference_type"]),
    )


def _source_symbol_id_for_line(
    *,
    line_number: int,
    symbol_entries: tuple[dict[str, Any], ...],
) -> str | None:
    matching_symbols = [
        symbol_entry
        for symbol_entry in symbol_entries
        if int(symbol_entry["start_line"]) <= line_number <= int(symbol_entry["end_line"])
    ]
    if not matching_symbols:
        return None
    ranked_symbols = sorted(
        matching_symbols,
        key=lambda entry: (
            0 if str(entry["symbol_kind"]) != "type" else 1,
            int(entry["end_line"]) - int(entry["start_line"]),
            int(entry["start_line"]),
            str(entry["symbol_id"]),
        ),
    )
    return str(ranked_symbols[0]["symbol_id"])


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_SUFFIXES:
        return set()
    aliases = {
        file_path,
        file_path.lower(),
        path.stem,
        path.stem.lower(),
        *without_suffix_aliases(path),
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {alias for alias in aliases if alias}
    if not is_probable_vala_source(path=Path(file_path), text=text):
        return {alias for alias in aliases if alias}
    stripped_text = strip_comments(text)
    aliases.update(namespace_paths(stripped_text))
    for symbol_entry in _collect_symbol_entries(
        stripped_text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    ):
        aliases.update(
            str(alias)
            for alias in symbol_entry["qualified_names"]
            if str(alias).strip()
        )
        aliases.update(
            str(alias).lower()
            for alias in symbol_entry["qualified_names"]
            if str(alias).strip()
        )
        symbol_name = str(symbol_entry["symbol_name"])
        aliases.add(symbol_name)
        aliases.add(symbol_name.lower())
    return {alias for alias in aliases if alias}


def resolve_import(
    import_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
    resolve_directory_prefix_match: ResolveDirectoryPrefixMatch,
) -> str | None:
    normalized_target = normalize_target(import_target)
    if not normalized_target:
        return None
    canonical_target = normalized_target.lower()
    direct_match = module_index.get(canonical_target)
    if direct_match is not None:
        return direct_match
    path_target = canonical_target.replace(".", "/")
    resolved = resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            canonical_target,
            path_target,
            f"{path_target}.vala",
            f"{path_target}.vapi",
            f"{canonical_target.split('.')[-1]}.vala",
            f"{canonical_target.split('.')[-1]}.vapi",
        ],
    )
    if resolved is not None:
        return resolved
    return resolve_directory_prefix_match(
        module_index=module_index,
        prefixes=[path_target, f"src/{path_target}"],
    )


def resolve_same_namespace_reference(
    *,
    current_file: str,
    current_namespace: str,
    type_name: str,
    module_index: dict[str, str],
    resolve_import: Any,
) -> str | None:
    normalized_type = normalize_target(type_name).lower()
    normalized_namespace = normalize_target(current_namespace).lower()
    if not normalized_type or not normalized_namespace:
        return None
    resolved = resolve_import(f"{normalized_namespace}.{normalized_type}", module_index)
    if resolved is None or resolved == current_file:
        return None
    return resolved


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: Any,
) -> tuple[
    tuple[dict[str, Any], ...],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    str,
]:
    dependencies: list[dict[str, Any]] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    import_bindings: dict[str, dict[str, Any]] = {}
    instance_bindings: dict[str, dict[str, Any]] = {}
    for match in _USING_RE.finditer(text):
        import_target = normalize_target(str(match.group("target") or ""))
        if not import_target:
            continue
        canonical_target = import_target.lower()
        target_symbol = import_target.rsplit(".", 1)[-1]
        target_symbol_key = target_symbol.lower()
        target_file = resolve_import(import_target, module_index)
        dependency_key = (target_file, target_symbol_key, "imports")
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                {
                    "dependency_edge_id": stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": canonical_target,
                            "line": match.start(),
                        },
                    ),
                    "source_file": file_path,
                    "target_file": target_file,
                    "target_symbol": target_symbol,
                    "dependency_type": "imports",
                }
            )
        for binding_alias in {canonical_target, target_symbol_key}:
            if not binding_alias:
                continue
            import_bindings.setdefault(
                binding_alias,
                {
                    "alias": binding_alias,
                    "target_file": target_file,
                    "target_names": (target_symbol,),
                },
            )
    current_namespace_entries = namespace_paths(text)
    current_namespace = current_namespace_entries[-1] if current_namespace_entries else ""
    for match in _INSTANCE_ASSIGN_RE.finditer(text):
        alias = normalize_symbol_name(str(match.group("alias") or "")).lower()
        type_name = normalize_target(str(match.group("type_name") or ""))
        if not alias or not type_name:
            continue
        canonical_target = type_name.lower()
        if "." in canonical_target:
            target_file = resolve_import(canonical_target, module_index)
        else:
            binding = import_bindings.get(canonical_target)
            target_file = str(binding["target_file"]) if binding is not None else None
            if target_file is None:
                target_file = resolve_same_namespace_reference(
                    current_file=file_path,
                    current_namespace=current_namespace,
                    type_name=canonical_target,
                    module_index=module_index,
                    resolve_import=resolve_import,
                )
        if target_file is None:
            continue
        instance_bindings[alias] = {
            "alias": alias,
            "target_file": target_file,
            "target_names": (type_name.rsplit(".", 1)[-1],),
        }
    return tuple(dependencies), import_bindings, instance_bindings, current_namespace


def _relation_targets_from_text(text: str) -> tuple[tuple[int, tuple[str, ...]], ...]:
    targets: list[tuple[int, tuple[str, ...]]] = []
    for match in _TYPE_DECL_RE.finditer(text):
        relation_targets = split_relation_targets(str(match.group("relations") or ""))
        if relation_targets:
            line_number = text.count("\n", 0, match.start()) + 1
            targets.append((line_number, relation_targets))
    return tuple(targets)


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: Any,
) -> tuple[_Dependency, ...]:
    if not is_probable_vala_source(path=Path(file_path), text=text):
        return ()
    stripped_text = strip_comments(text)
    dependencies, import_bindings, _, current_namespace = extract_import_bindings(
        file_path,
        stripped_text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
    )
    dependency_entries = list(dependencies)
    dependency_keys = {
        (entry["target_file"], entry["target_symbol"], entry["dependency_type"])
        for entry in dependency_entries
    }
    declared_type_names = {
        str(entry["symbol_name"]).lower()
        for entry in _collect_symbol_entries(
            stripped_text,
            file_path=file_path,
            stable_identifier=stable_identifier,
        )
        if str(entry["symbol_kind"]) == "type"
    }
    for line_number, relation_targets in _relation_targets_from_text(stripped_text):
        for raw_target in relation_targets:
            canonical_target = normalize_target(raw_target).lower()
            leaf_name = raw_target.rsplit(".", 1)[-1]
            leaf_name_key = leaf_name.lower()
            if (
                not canonical_target
                or leaf_name_key in _BUILTIN_TYPE_NAMES
                or leaf_name_key in declared_type_names
            ):
                continue
            if "." in canonical_target:
                target_file = resolve_import(canonical_target, module_index)
            else:
                binding = import_bindings.get(leaf_name_key)
                target_file = str(binding["target_file"]) if binding is not None else None
                if target_file is None:
                    target_file = resolve_same_namespace_reference(
                        current_file=file_path,
                        current_namespace=current_namespace,
                        type_name=leaf_name_key,
                        module_index=module_index,
                        resolve_import=resolve_import,
                    )
            dependency_key = (target_file, leaf_name_key, "references")
            if (
                target_file is None
                or target_file == file_path
                or dependency_key in dependency_keys
            ):
                continue
            dependency_keys.add(dependency_key)
            dependency_entries.append(
                {
                    "dependency_edge_id": stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": canonical_target,
                            "line": line_number,
                        },
                    ),
                    "source_file": file_path,
                    "target_file": target_file,
                    "target_symbol": leaf_name,
                    "dependency_type": "references",
                }
            )
    for match in _NEW_REFERENCE_RE.finditer(stripped_text):
        raw_target = normalize_target(str(match.group("name") or ""))
        if not raw_target:
            continue
        canonical_target = raw_target.lower()
        leaf_name = raw_target.rsplit(".", 1)[-1]
        leaf_name_key = leaf_name.lower()
        if leaf_name_key in _BUILTIN_TYPE_NAMES or leaf_name_key in declared_type_names:
            continue
        if "." in canonical_target:
            target_file = resolve_import(canonical_target, module_index)
        else:
            binding = import_bindings.get(leaf_name_key)
            target_file = str(binding["target_file"]) if binding is not None else None
            if target_file is None:
                target_file = resolve_same_namespace_reference(
                    current_file=file_path,
                    current_namespace=current_namespace,
                    type_name=leaf_name_key,
                    module_index=module_index,
                    resolve_import=resolve_import,
                )
        dependency_key = (target_file, leaf_name_key, "references")
        if (
            target_file is None
            or target_file == file_path
            or dependency_key in dependency_keys
        ):
            continue
        dependency_keys.add(dependency_key)
        dependency_entries.append(
            {
                "dependency_edge_id": stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": canonical_target,
                        "line": match.start(),
                    },
                ),
                "source_file": file_path,
                "target_file": target_file,
                "target_symbol": leaf_name,
                "dependency_type": "references",
                }
            )
    return tuple(_dependency_from_entry(entry) for entry in dependency_entries)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: Any,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    if not is_probable_vala_source(path=Path(file_path), text=text):
        return (), (), ()
    stripped_text = strip_comments(text)
    symbol_entries = tuple(
        _collect_symbol_entries(
            stripped_text,
            file_path=file_path,
            stable_identifier=stable_identifier,
        )
    )
    _, import_bindings, instance_bindings, current_namespace = extract_import_bindings(
        file_path=file_path,
        text=stripped_text,
        module_index=module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
    )
    declared_symbol_names = {
        str(symbol_entry["symbol_name"]).lower()
        for symbol_entry in symbol_entries
    }
    reference_candidates: dict[str, dict[str, Any]] = {}
    lines = stripped_text.splitlines()
    for symbol_entry in symbol_entries:
        start_line = int(symbol_entry["start_line"])
        end_line = int(symbol_entry["end_line"])
        symbol_name = str(symbol_entry["symbol_name"])
        snippet = "\n".join(lines[start_line - 1 : end_line])
        for match in _QUALIFIED_REFERENCE_RE.finditer(snippet):
            alias = str(match.group("alias") or "").strip().lower()
            target_name = normalize_symbol_name(str(match.group("name") or ""))
            if not alias or not target_name or target_name.lower() == symbol_name.lower():
                continue
            binding = instance_bindings.get(alias) or import_bindings.get(alias)
            target_file = str(binding["target_file"]) if binding is not None else None
            if target_file is None:
                target_file = resolve_import(f"{alias}.{target_name}", module_index)
            if target_file is None or target_file == file_path:
                continue
            source_symbol_id = _source_symbol_id_for_line(
                line_number=start_line + snippet.count("\n", 0, match.start()),
                symbol_entries=symbol_entries,
            )
            if source_symbol_id is None:
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": source_symbol_id,
                    "target_file": target_file,
                    "target_names": (target_name,),
                    "type": "references_symbol",
                },
            )
            reference_candidates.setdefault(
                edge_id,
                {
                    "reference_edge_id": edge_id,
                    "source_symbol_id": source_symbol_id,
                    "source_file": file_path,
                    "target_symbol_id": None,
                    "target_file": target_file,
                    "target_names": (target_name,),
                    "reference_type": "references_symbol",
                },
            )
        for match in _NEW_REFERENCE_RE.finditer(snippet):
            raw_target = normalize_target(str(match.group("name") or ""))
            if not raw_target:
                continue
            canonical_target = raw_target.lower()
            leaf_name = raw_target.rsplit(".", 1)[-1]
            leaf_name_key = leaf_name.lower()
            if (
                leaf_name_key in _BUILTIN_TYPE_NAMES
                or leaf_name_key in declared_symbol_names
                or leaf_name_key == symbol_name.lower()
            ):
                continue
            if "." in canonical_target:
                target_file = resolve_import(canonical_target, module_index)
            else:
                binding = import_bindings.get(leaf_name_key)
                target_file = str(binding["target_file"]) if binding is not None else None
                if target_file is None:
                    target_file = resolve_same_namespace_reference(
                        current_file=file_path,
                        current_namespace=current_namespace,
                        type_name=leaf_name_key,
                        module_index=module_index,
                        resolve_import=resolve_import,
                    )
            if target_file is None or target_file == file_path:
                continue
            source_symbol_id = _source_symbol_id_for_line(
                line_number=start_line + snippet.count("\n", 0, match.start()),
                symbol_entries=symbol_entries,
            )
            if source_symbol_id is None:
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": source_symbol_id,
                    "target_file": target_file,
                    "target_names": (leaf_name,),
                    "type": "references_symbol",
                },
            )
            reference_candidates.setdefault(
                edge_id,
                {
                    "reference_edge_id": edge_id,
                    "source_symbol_id": source_symbol_id,
                    "source_file": file_path,
                    "target_symbol_id": None,
                    "target_file": target_file,
                    "target_names": (leaf_name,),
                    "reference_type": "references_symbol",
                },
            )
    return (
        tuple(_symbol_from_entry(entry) for entry in symbol_entries),
        parse_dependencies_only(
            file_path,
            stripped_text,
            module_index,
            stable_identifier=stable_identifier,
            resolve_import=resolve_import,
        ),
        tuple(
            _symbol_reference_from_entry(reference_candidates[key])
            for key in sorted(reference_candidates)
        ),
    )

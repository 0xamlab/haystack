from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    hack_primitives as repository_hack_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_hack_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_hack_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_hack_primitives.ResolveSuffixMatch

HACK_FILE_SUFFIXES = repository_hack_primitives.HACK_FILE_SUFFIXES
HACK_CONFIG_BASENAMES = repository_hack_primitives.HACK_CONFIG_BASENAMES
HACK_OPEN_TAG_RE = repository_hack_primitives.HACK_OPEN_TAG_RE
HACK_DECLARATION_RE = repository_hack_primitives.HACK_DECLARATION_RE
HACK_FUNCTION_HINT_RE = repository_hack_primitives.HACK_FUNCTION_HINT_RE
HACK_TYPE_HINT_RE = repository_hack_primitives.HACK_TYPE_HINT_RE
INCLUDE_RE = repository_hack_primitives.INCLUDE_RE
TYPE_DECL_RE = repository_hack_primitives.TYPE_DECL_RE
FUNCTION_DECL_RE = repository_hack_primitives.FUNCTION_DECL_RE
USE_RE = repository_hack_primitives.USE_RE
QUALIFIED_REFERENCE_RE = repository_hack_primitives.QUALIFIED_REFERENCE_RE
TYPE_REFERENCE_RE = repository_hack_primitives.TYPE_REFERENCE_RE
VARIABLE_TYPE_TOKEN_RE = repository_hack_primitives.VARIABLE_TYPE_TOKEN_RE
RESERVED_SYMBOL_NAMES = repository_hack_primitives.RESERVED_SYMBOL_NAMES

strip_comments = repository_hack_primitives.strip_comments
has_hack_path_hints = repository_hack_primitives.has_hack_path_hints
parse_hack_autoload_roots = repository_hack_primitives.parse_hack_autoload_roots
current_namespace = repository_hack_primitives.current_namespace
leading_docblock = repository_hack_primitives.leading_docblock
symbol_declaration_header = repository_hack_primitives.symbol_declaration_header
doc_type_tokens = repository_hack_primitives.doc_type_tokens
type_tokens_from_header = repository_hack_primitives.type_tokens_from_header
_symbol_entries = repository_hack_primitives._symbol_entries


def is_probable_hack_source(*, path: Path, text: str) -> bool:
    lowered_name = path.name.lower()
    lowered_suffix = path.suffix.lower()
    stripped_text = strip_comments(text)
    lowered_text = stripped_text.lower()
    if lowered_name == ".hhconfig":
        return bool(stripped_text.strip())
    if lowered_name in {"hhvm.autoload", "hh_autoload.json"}:
        return bool(parse_hack_autoload_roots(text) or stripped_text.strip())
    if HACK_OPEN_TAG_RE.search(text) is not None:
        return True
    if lowered_suffix == ".php":
        return False
    if lowered_suffix not in HACK_FILE_SUFFIXES:
        return False
    return (
        HACK_DECLARATION_RE.search(stripped_text) is not None
        or HACK_FUNCTION_HINT_RE.search(stripped_text) is not None
        or HACK_TYPE_HINT_RE.search(lowered_text) is not None
        or current_namespace(stripped_text) != ""
    )


def module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    path = PurePosixPath(file_path)
    lowered_name = path.name.lower()
    if lowered_name in HACK_CONFIG_BASENAMES:
        return {file_path}
    if path.suffix.lower() not in HACK_FILE_SUFFIXES:
        return set()
    aliases: set[str] = set()
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not is_probable_hack_source(path=Path(file_path), text=text):
        return set()
    aliases.add(file_path)
    namespace = current_namespace(text)
    for regex in (TYPE_DECL_RE, FUNCTION_DECL_RE):
        for match in regex.finditer(text):
            symbol_name = str(match.group("name") or "").strip()
            if not symbol_name:
                continue
            aliases.add(symbol_name)
            if namespace:
                aliases.add(f"{namespace}\\{symbol_name}")
    without_suffix_path = str(path.with_suffix(""))
    if without_suffix_path:
        aliases.add(without_suffix_path)
        aliases.add(without_suffix_path.replace("/", "\\"))
        aliases.add(without_suffix_path.replace("/", "."))
    if path.stem:
        aliases.add(path.stem)
    return {alias for alias in aliases if alias}


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = import_target.strip()
    if not normalized_target:
        return None
    if (
        "/" in normalized_target
        or normalized_target.endswith(tuple(HACK_FILE_SUFFIXES))
        or normalized_target.startswith(".")
    ):
        current_dir = PurePosixPath(current_file).parent
        relative_base = normalize_repository_relative_path(str(current_dir / normalized_target))
        candidate_keys = [
            key
            for key in (
                relative_base,
                *(
                    f"{relative_base}{suffix}"
                    for suffix in sorted(HACK_FILE_SUFFIXES)
                    if relative_base
                ),
            )
            if key
        ]
    else:
        namespace_path = normalized_target.replace("\\", "/")
        candidate_keys = [
            namespace_path,
            *(f"{namespace_path}{suffix}" for suffix in sorted(HACK_FILE_SUFFIXES)),
        ]
    for candidate_key in candidate_keys:
        resolved = module_index.get(candidate_key)
        if resolved is not None:
            return resolved
    normalized_path = normalized_target.replace("\\", "/")
    leaf_name = normalized_target.split("\\")[-1]
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            normalized_path,
            *(f"{normalized_path}{suffix}" for suffix in sorted(HACK_FILE_SUFFIXES)),
            *(f"{leaf_name}{suffix}" for suffix in sorted(HACK_FILE_SUFFIXES)),
        ],
    )


def resolve_same_namespace_reference(
    *,
    current_namespace: str,
    target_name: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_name = target_name.strip()
    if not current_namespace or not normalized_name:
        return None
    return resolve_import(
        current_file="",
        import_target=f"{current_namespace}\\{normalized_name}",
        module_index=module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )


def resolve_reference_target(
    *,
    current_file: str,
    token: str,
    import_bindings: dict[str, _ImportedSymbolBinding],
    current_namespace: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[str | None, tuple[str, ...]]:
    normalized_token = token.lstrip("\\").strip()
    if not normalized_token or normalized_token in RESERVED_SYMBOL_NAMES:
        return None, ()
    if "\\" in normalized_token:
        target_file = resolve_import(
            current_file=current_file,
            import_target=normalized_token,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        return target_file, (normalized_token.split("\\")[-1],)
    binding = import_bindings.get(normalized_token)
    if binding is not None:
        return binding.target_file, binding.target_names or (normalized_token,)
    target_file = resolve_same_namespace_reference(
        current_namespace=current_namespace,
        target_name=normalized_token,
        module_index=module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    return target_file, (normalized_token,)


def iter_reference_targets(
    *,
    file_path: str,
    symbol_name: str,
    snippet: str,
    leading_docblock_text: str,
    import_bindings: dict[str, _ImportedSymbolBinding],
    current_namespace: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    targets: list[tuple[str, tuple[str, ...]]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()

    def add_target(
        token: str,
        *,
        explicit_target_names: tuple[str, ...] | None = None,
    ) -> None:
        target_file, target_names = resolve_reference_target(
            current_file=file_path,
            token=token,
            import_bindings=import_bindings,
            current_namespace=current_namespace,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        if target_file is None or target_file == file_path:
            return
        resolved_target_names = explicit_target_names or target_names
        if (
            not resolved_target_names
            or symbol_name in resolved_target_names
            or any(target_name in RESERVED_SYMBOL_NAMES for target_name in resolved_target_names)
        ):
            return
        target_key = (target_file, tuple(resolved_target_names))
        if target_key in seen:
            return
        seen.add(target_key)
        targets.append(target_key)

    for match in QUALIFIED_REFERENCE_RE.finditer(snippet):
        alias = str(match.group("alias") or "").strip()
        target_name = str(match.group("name") or "").strip()
        if not alias or alias in RESERVED_SYMBOL_NAMES:
            continue
        add_target(alias, explicit_target_names=(target_name, alias))

    for match in TYPE_REFERENCE_RE.finditer(snippet):
        type_name = str(match.group("name") or "").strip()
        if type_name:
            add_target(type_name)

    declaration_header = symbol_declaration_header(snippet)
    for token in type_tokens_from_header(declaration_header):
        if token != symbol_name:
            add_target(token)

    for match in VARIABLE_TYPE_TOKEN_RE.finditer(snippet):
        token = str(match.group("name") or "").lstrip("\\").strip()
        if token and token != symbol_name:
            add_target(token)

    for token in doc_type_tokens(leading_docblock_text):
        if token != symbol_name:
            add_target(token)

    return tuple(targets)


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding], str]:
    dependencies: list[_Dependency] = []
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    dependency_keys: set[tuple[str | None, str]] = set()
    namespace = current_namespace(text)
    for match in INCLUDE_RE.finditer(text):
        import_target = str(match.group("target") or "").strip()
        if not import_target:
            continue
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target)
        if dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {"file_path": file_path, "target": import_target, "line": match.start()},
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=PurePosixPath(import_target).name,
                dependency_type="imports",
            )
        )
    for match in USE_RE.finditer(text):
        import_target = str(match.group("target") or "").strip()
        if not import_target:
            continue
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target)
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {"file_path": file_path, "target": import_target, "line": match.start()},
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=import_target.split("\\")[-1],
                    dependency_type="imports",
                )
            )
        binding_alias = str(match.group("alias") or "").strip() or import_target.split("\\")[-1]
        for alias in sorted({binding_alias, import_target.split("\\")[-1]}):
            if not alias:
                continue
            import_bindings.setdefault(
                alias,
                _ImportedSymbolBinding(
                    alias=alias,
                    target_file=target_file,
                    target_names=(import_target.split("\\")[-1],),
                ),
            )
    return tuple(dependencies), import_bindings, namespace


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    dependencies, import_bindings, namespace = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    dependency_entries = list(dependencies)
    dependency_keys = {
        (dependency.target_file, dependency.target_symbol, dependency.dependency_type)
        for dependency in dependency_entries
    }
    lines = text.splitlines()
    for entry in _symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=None,
        include_symbol_kind_in_key=True,
    ):
        snippet = "\n".join(lines[int(entry["start_line"]) - 1 : int(entry["end_line"])])
        leading_docblock_text = leading_docblock(text, offset=int(entry["match_start"]))
        for target_file, target_names in iter_reference_targets(
            file_path=file_path,
            symbol_name=str(entry["symbol_name"]),
            snippet=snippet,
            leading_docblock_text=leading_docblock_text,
            import_bindings=import_bindings,
            current_namespace=namespace,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        ):
            dependency_key = (target_file, target_names[0], "references")
            if dependency_key in dependency_keys:
                continue
            dependency_keys.add(dependency_key)
            dependency_entries.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target_file": target_file,
                            "target_names": target_names,
                            "line": int(entry["start_line"]),
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=target_names[0],
                    dependency_type="references",
                )
            )
    return tuple(dependency_entries)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    symbol_entries = _symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
        include_symbol_kind_in_key=True,
    )
    symbols = tuple(
        _Symbol(
            symbol_id=str(entry["symbol_id"]),
            symbol_name=str(entry["symbol_name"]),
            symbol_kind=str(entry["symbol_kind"]),
            start_line=int(entry["start_line"]),
            end_line=int(entry["end_line"]),
            parent_symbol_id=None,
            signature=str(entry["signature"]),
        )
        for entry in symbol_entries
    )
    dependencies, import_bindings, namespace = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    symbol_ids_by_name = {symbol.symbol_name: symbol.symbol_id for symbol in symbols}
    lines = text.splitlines()
    leading_docblocks_by_symbol_id = {
        str(entry["symbol_id"]): leading_docblock(text, offset=int(entry["match_start"]))
        for entry in symbol_entries
    }
    for symbol in symbols:
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for target_file, target_names in iter_reference_targets(
            file_path=file_path,
            symbol_name=symbol.symbol_name,
            snippet=snippet,
            leading_docblock_text=leading_docblocks_by_symbol_id.get(symbol.symbol_id, ""),
            import_bindings=import_bindings,
            current_namespace=namespace,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        ):
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol.symbol_id,
                    "target_file": target_file,
                    "target_names": target_names,
                    "type": "references_symbol",
                },
            )
            reference_candidates.setdefault(
                edge_id,
                _SymbolReferenceCandidate(
                    reference_edge_id=edge_id,
                    source_symbol_id=symbol.symbol_id,
                    source_file=file_path,
                    target_symbol_id=None,
                    target_file=target_file,
                    target_names=target_names,
                    reference_type="references_symbol",
                ),
            )
        if symbol.symbol_kind == "function":
            for target_name, target_symbol_id in symbol_ids_by_name.items():
                if (
                    target_symbol_id == symbol.symbol_id
                    or target_name in RESERVED_SYMBOL_NAMES
                ):
                    continue
                if re.search(
                    rf"(?<![:\\$>])\b{re.escape(target_name)}\s*\(",
                    snippet,
                ) is None:
                    continue
                edge_id = stable_identifier(
                    "ref",
                    {
                        "source_symbol_id": symbol.symbol_id,
                        "target_symbol_id": target_symbol_id,
                        "type": "references_symbol",
                    },
                )
                reference_candidates.setdefault(
                    edge_id,
                    _SymbolReferenceCandidate(
                        reference_edge_id=edge_id,
                        source_symbol_id=symbol.symbol_id,
                        source_file=file_path,
                        target_symbol_id=target_symbol_id,
                        target_file=file_path,
                        target_names=(target_name,),
                        reference_type="references_symbol",
                    ),
                )
    return (
        symbols,
        dependencies,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )

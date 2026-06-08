from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str | None]
ResolveSuffixMatch = Callable[..., str | None]
ModuleIndexValues = Callable[[dict[str, str]], Sequence[str]]
ModuleIndexAliasesForFile = Callable[[dict[str, str], str], set[str]]

REQUIRE_RE = re.compile(
    r"^\s*require\s*(?:\(\s*)?['\"](?P<target>[^'\"]+)['\"]",
    re.MULTILINE,
)
TYPE_DECL_RE = re.compile(
    r"^\s*(?P<kind>module|class|struct|record|enum|annotation|alias)\s+"
    r"(?P<name>[A-Z][A-Za-z0-9_]*(?:::[A-Z][A-Za-z0-9_]*)*)\b",
    re.MULTILINE,
)
FUNCTION_DECL_RE = re.compile(
    r"^\s*def\s+(?:self\.)?(?P<name>[a-z_][A-Za-z0-9_!?=]*)\b",
    re.MULTILINE,
)
QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Z][A-Za-z0-9_]*(?:::[A-Z][A-Za-z0-9_]*)*)\s*\.\s*"
    r"(?P<name>[a-z_][A-Za-z0-9_!?=]*)\b"
)
INCLUDE_EXTEND_RE = re.compile(
    r"^\s*(?:include|extend|prepend)\s+(?P<name>[A-Z][A-Za-z0-9_]*(?:::[A-Z][A-Za-z0-9_]*)*)\b",
    re.MULTILINE,
)
INHERITANCE_RE = re.compile(
    r"^\s*(?:class|struct|record|enum|annotation)\s+[A-Z][A-Za-z0-9_]*(?:::[A-Z][A-Za-z0-9_]*)*"
    r"\s*<\s*(?P<name>[A-Z][A-Za-z0-9_]*(?:::[A-Z][A-Za-z0-9_]*)*)\b",
    re.MULTILINE,
)
TYPE_TOKEN_RE = re.compile(
    r"\b(?P<name>[A-Z][A-Za-z0-9_]*(?:::[A-Z][A-Za-z0-9_]*)*)\b"
)
CONSTANT_ALIAS_RE = re.compile(
    r"^[A-Z][A-Za-z0-9_]*(?:::[A-Z][A-Za-z0-9_]*)*$"
)
RESERVED_SYMBOL_NAMES = frozenset(
    {
        "abstract",
        "alias",
        "annotation",
        "asm",
        "begin",
        "break",
        "case",
        "class",
        "def",
        "do",
        "else",
        "elsif",
        "end",
        "ensure",
        "enum",
        "extend",
        "for",
        "fun",
        "if",
        "in",
        "include",
        "lib",
        "macro",
        "module",
        "next",
        "nil",
        "of",
        "out",
        "pointerof",
        "private",
        "protected",
        "record",
        "require",
        "rescue",
        "return",
        "select",
        "self",
        "sizeof",
        "struct",
        "super",
        "then",
        "true",
        "type",
        "typeof",
        "union",
        "unless",
        "until",
        "verbatim",
        "when",
        "while",
        "with",
        "yield",
    }
)


def _camelize_identifier(value: str) -> str:
    normalized_value = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    if not normalized_value:
        return ""
    return "".join(piece.capitalize() for piece in normalized_value.split("_") if piece)


def is_constant_alias(value: str) -> bool:
    return CONSTANT_ALIAS_RE.fullmatch(value.strip()) is not None


def declared_type_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix != ".cr":
        return set()
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    aliases: set[str] = set()
    for match in TYPE_DECL_RE.finditer(text):
        symbol_name = str(match.group("name") or "").strip()
        if not is_constant_alias(symbol_name):
            continue
        aliases.add(symbol_name)
        aliases.add(symbol_name.rsplit("::", 1)[-1])
    return aliases


def constant_aliases_for_file(file_path: str) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix != ".cr":
        return set()
    parts = list(path.parts)
    root_index = next(
        (index for index, part in enumerate(parts[:-1]) if part in {"src", "lib"}),
        None,
    )
    relevant_parts = parts[root_index + 1 :] if root_index is not None else parts
    if not relevant_parts:
        return set()
    namespace_parts = [_camelize_identifier(part) for part in relevant_parts[:-1] if part]
    stem_alias = _camelize_identifier(path.stem)
    if stem_alias:
        if namespace_parts and namespace_parts[-1] == stem_alias:
            full_parts = namespace_parts
        else:
            full_parts = [*namespace_parts, stem_alias]
    else:
        full_parts = namespace_parts
    aliases: set[str] = set()
    if full_parts:
        aliases.add("::".join(full_parts))
        aliases.add(full_parts[-1])
    return {alias for alias in aliases if alias}


def resolve_import_targets(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    module_index_values: ModuleIndexValues,
) -> tuple[str | None, ...]:
    normalized_target = import_target.strip().replace("\\", "/")
    if not normalized_target:
        return ()
    recursive_wildcard = normalized_target.endswith("/**")
    wildcard = recursive_wildcard or normalized_target.endswith("/*")
    base_target = normalized_target[:-3] if recursive_wildcard else normalized_target[:-2]
    base_target = base_target.rstrip("/") if wildcard else normalized_target
    candidate_keys: list[str] = []
    if base_target.startswith("."):
        current_dir = PurePosixPath(current_file).parent
        relative_base = normalize_repository_relative_path(str(current_dir / base_target))
        if relative_base:
            candidate_keys.extend((relative_base, f"{relative_base}.cr"))
    else:
        candidate_keys.extend(
            (
                base_target,
                f"{base_target}.cr",
                f"src/{base_target}",
                f"src/{base_target}.cr",
                f"lib/{base_target}",
                f"lib/{base_target}.cr",
            )
        )
    if wildcard:
        prefixes = [
            normalized_key.rstrip("/")
            for candidate_key in candidate_keys
            if candidate_key
            and (
                normalized_key := normalize_repository_relative_path(candidate_key)
            )
        ]
        matches = [
            file_path
            for file_path in module_index_values(module_index)
            if file_path.endswith(".cr")
            and any(file_path.startswith(f"{prefix}/") for prefix in prefixes)
        ]
        return tuple(dict.fromkeys(matches))
    for candidate_key in candidate_keys:
        if not candidate_key:
            continue
        resolved = module_index.get(candidate_key)
        if resolved is not None:
            return (resolved,)
    resolved = resolve_suffix_match(
        module_index=module_index,
        suffixes=[f"{base_target}.cr", base_target],
    )
    return (resolved,) if resolved is not None else ()


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    module_index_values: ModuleIndexValues,
    module_index_aliases_for_file: ModuleIndexAliasesForFile,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    dependency_keys: set[tuple[str | None, str]] = set()
    for match in REQUIRE_RE.finditer(text):
        import_target = str(match.group("target") or "").strip()
        if not import_target:
            continue
        target_files = resolve_import_targets(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
            module_index_values=module_index_values,
        ) or (None,)
        for target_file in target_files:
            dependency_key = (target_file, import_target)
            if dependency_key in dependency_keys:
                continue
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": import_target,
                            "target_file": target_file,
                            "line": match.start(),
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=PurePosixPath(import_target.rstrip("/*")).name or None,
                    dependency_type="imports",
                )
            )
            if target_file is None:
                continue
            aliases = {
                alias
                for alias in (
                    module_index_aliases_for_file(module_index, target_file)
                    | constant_aliases_for_file(target_file)
                )
                if is_constant_alias(alias)
            }
            for alias in sorted(aliases):
                import_bindings.setdefault(
                    alias,
                    _ImportedSymbolBinding(
                        alias=alias,
                        target_file=target_file,
                        target_names=(),
                    ),
                )
    return tuple(dependencies), import_bindings


def resolve_reference_target(
    *,
    reference_name: str,
    import_bindings: dict[str, _ImportedSymbolBinding],
    module_index: dict[str, str],
) -> tuple[str | None, tuple[str, ...]]:
    normalized_name = reference_name.strip()
    if not normalized_name or not is_constant_alias(normalized_name):
        return None, ()
    leaf_name = normalized_name.rsplit("::", 1)[-1]
    binding = import_bindings.get(normalized_name) or import_bindings.get(leaf_name)
    if binding is not None and binding.target_file is not None:
        if normalized_name != leaf_name:
            return binding.target_file, (normalized_name, leaf_name)
        return binding.target_file, (leaf_name,)
    target_file = module_index.get(normalized_name) or module_index.get(leaf_name)
    if target_file is None:
        return None, ()
    if normalized_name != leaf_name:
        return target_file, (normalized_name, leaf_name)
    return target_file, (leaf_name,)


def iter_reference_targets(
    *,
    file_path: str,
    symbol_name: str,
    snippet: str,
    import_bindings: dict[str, _ImportedSymbolBinding],
    module_index: dict[str, str],
) -> tuple[tuple[str | None, tuple[str, ...]], ...]:
    reference_targets: list[tuple[str | None, tuple[str, ...]]] = []
    seen_targets: set[tuple[str | None, tuple[str, ...]]] = set()

    def add_target(target_file: str | None, target_names: tuple[str, ...]) -> None:
        if not target_names:
            return
        leaf_name = target_names[-1]
        if target_file == file_path and leaf_name == symbol_name:
            return
        target_key = (target_file, target_names)
        if target_key in seen_targets:
            return
        seen_targets.add(target_key)
        reference_targets.append(target_key)

    def add_reference(reference_name: str) -> None:
        target_file, target_names = resolve_reference_target(
            reference_name=reference_name,
            import_bindings=import_bindings,
            module_index=module_index,
        )
        add_target(target_file, target_names)

    for match in QUALIFIED_REFERENCE_RE.finditer(snippet):
        alias = str(match.group("alias") or "").strip()
        target_name = str(match.group("name") or "").strip()
        alias_target_file, alias_target_names = resolve_reference_target(
            reference_name=alias,
            import_bindings=import_bindings,
            module_index=module_index,
        )
        if target_name == "new":
            add_reference(alias)
            continue
        if (
            alias_target_file is not None
            and target_name
            and target_name not in RESERVED_SYMBOL_NAMES
        ):
            add_target(alias_target_file, (target_name,))
            continue
        if target_name and target_name not in RESERVED_SYMBOL_NAMES:
            add_reference(target_name)

    for regex in (INCLUDE_EXTEND_RE, INHERITANCE_RE, TYPE_TOKEN_RE):
        for match in regex.finditer(snippet):
            reference_name = str(match.group("name") or "").strip()
            if reference_name and reference_name not in RESERVED_SYMBOL_NAMES:
                add_reference(reference_name)

    return tuple(reference_targets)


def _symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier | None,
    include_kind_in_key: bool,
) -> list[dict[str, Any]]:
    lines = text.splitlines()
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, int] | tuple[str, int, str]] = set()
    for regex, symbol_kind in (
        (TYPE_DECL_RE, "type"),
        (FUNCTION_DECL_RE, "function"),
    ):
        for match in regex.finditer(text):
            symbol_name = str(match.group("name") or "").strip()
            if not symbol_name or symbol_name in RESERVED_SYMBOL_NAMES:
                continue
            line_no = text.count("\n", 0, match.start()) + 1
            symbol_key: tuple[str, int] | tuple[str, int, str]
            if include_kind_in_key:
                symbol_key = (symbol_name, line_no, symbol_kind)
            else:
                symbol_key = (symbol_name, line_no)
            if symbol_key in seen_symbol_keys:
                continue
            seen_symbol_keys.add(symbol_key)
            entry: dict[str, Any] = {
                "symbol_name": symbol_name,
                "symbol_kind": symbol_kind,
                "start_line": line_no,
                "end_line": line_no,
                "signature": symbol_name,
            }
            if stable_identifier is not None:
                entry["symbol_id"] = stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": symbol_name,
                        "line": line_no,
                        "kind": symbol_kind,
                    },
                )
            symbol_entries.append(entry)
    symbol_entries.sort(key=lambda entry: int(entry["start_line"]))
    final_line = len(lines) if lines else 1
    for index, entry in enumerate(symbol_entries):
        if index + 1 < len(symbol_entries):
            entry["end_line"] = max(
                int(symbol_entries[index + 1]["start_line"]) - 1,
                int(entry["start_line"]),
            )
        else:
            entry["end_line"] = final_line
    return symbol_entries


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    module_index_values: ModuleIndexValues,
    module_index_aliases_for_file: ModuleIndexAliasesForFile,
) -> tuple[_Dependency, ...]:
    dependencies, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        module_index_values=module_index_values,
        module_index_aliases_for_file=module_index_aliases_for_file,
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
        include_kind_in_key=True,
    ):
        snippet = "\n".join(lines[int(entry["start_line"]) - 1 : int(entry["end_line"])])
        for target_file, target_names in iter_reference_targets(
            file_path=file_path,
            symbol_name=str(entry["symbol_name"]),
            snippet=snippet,
            import_bindings=import_bindings,
            module_index=module_index,
        ):
            if target_file is None:
                continue
            target_symbol = next(
                (
                    name
                    for name in reversed(target_names)
                    if name and name not in RESERVED_SYMBOL_NAMES
                ),
                None,
            )
            if target_symbol is None:
                continue
            dependency_key = (target_file, target_symbol, "references")
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
                    target_symbol=target_symbol,
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
    module_index_values: ModuleIndexValues,
    module_index_aliases_for_file: ModuleIndexAliasesForFile,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    symbol_entries = _symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
        include_kind_in_key=False,
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
    dependencies, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        module_index_values=module_index_values,
        module_index_aliases_for_file=module_index_aliases_for_file,
    )
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    symbol_ids_by_name = {symbol.symbol_name: symbol.symbol_id for symbol in symbols}
    lines = text.splitlines()
    for symbol in symbols:
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for target_file, target_names in iter_reference_targets(
            file_path=file_path,
            symbol_name=symbol.symbol_name,
            snippet=snippet,
            import_bindings=import_bindings,
            module_index=module_index,
        ):
            target_symbol_id = next(
                (
                    symbol_ids_by_name[name]
                    for name in reversed(target_names)
                    if name in symbol_ids_by_name
                ),
                None,
            )
            if target_symbol_id is not None and target_symbol_id != symbol.symbol_id:
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
                        target_names=(target_names[-1],),
                        reference_type="references_symbol",
                    ),
                )
                continue
            if target_file is None:
                continue
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
    return (
        symbols,
        dependencies,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )

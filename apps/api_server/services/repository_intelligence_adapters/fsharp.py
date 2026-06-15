from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _ModuleIndexLookup,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]
ResolveDirectoryPrefixMatch = Callable[[dict[str, str], Sequence[str]], str | None]
ResolveImportTarget = Callable[[str], str | None]
ResolveContextTarget = Callable[[Sequence[str], Sequence[str], str], str | None]

RESERVED_SYMBOL_NAMES = frozenset(
    {
        "abstract",
        "and",
        "as",
        "assert",
        "base",
        "class",
        "default",
        "delegate",
        "do",
        "done",
        "downcast",
        "downto",
        "elif",
        "else",
        "end",
        "exception",
        "extern",
        "false",
        "finally",
        "for",
        "fun",
        "function",
        "global",
        "if",
        "in",
        "inherit",
        "inline",
        "interface",
        "internal",
        "lazy",
        "let",
        "match",
        "member",
        "module",
        "mutable",
        "namespace",
        "new",
        "null",
        "of",
        "open",
        "or",
        "override",
        "private",
        "public",
        "rec",
        "return",
        "sig",
        "static",
        "struct",
        "then",
        "to",
        "true",
        "try",
        "type",
        "upcast",
        "use",
        "val",
        "void",
        "when",
        "while",
        "with",
        "yield",
    }
)
OPEN_RE = re.compile(
    r"^\s*open\s+(?:type\s+)?(?P<target>(?:global\.)?[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*)\s*$",
    re.MULTILINE,
)
NAMESPACE_RE = re.compile(
    r"^\s*namespace\s+(?P<target>(?:global\.)?[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*)\s*$",
    re.MULTILINE,
)
MODULE_RE = re.compile(
    r"^\s*module\s+(?:rec\s+)?(?:(?:public|private|internal)\s+)?"
    r"(?P<target>(?:global\.)?[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*)\s*(?:=\s*)?$",
    re.MULTILINE,
)
TYPE_DECL_RE = re.compile(
    r"^\s*(?:type|and)\s+(?:(?:public|private|internal)\s+)?"
    r"(?P<name>(?:``[^`]+``)|[A-Z][A-Za-z0-9_']*)\b",
    re.MULTILINE,
)
LET_DECL_RE = re.compile(
    r"^\s*let\s+"
    r"(?:(?:inline|rec|mutable|private|internal|public|global|static|abstract|override|default)\s+)*"
    r"(?:(?:\((?P<operator>[^)\r\n]+)\))|(?P<name>``[^`]+``|[A-Za-z_][A-Za-z0-9_']*))",
    re.MULTILINE,
)
QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Z][A-Za-z0-9_']*(?:\.[A-Z][A-Za-z0-9_']*)*)\.(?P<name>[A-Za-z_][A-Za-z0-9_']*)\b"
)
TYPE_REFERENCE_RE = re.compile(r"\b(?P<name>[A-Z][A-Za-z0-9_']*)\b")


def normalize_symbol_name(raw_name: str) -> str:
    normalized_name = raw_name.strip()
    if normalized_name.startswith("``") and normalized_name.endswith("``"):
        normalized_name = normalized_name[2:-2].strip()
    if normalized_name.startswith("(") and normalized_name.endswith(")"):
        normalized_name = normalized_name[1:-1].strip()
    return normalized_name


def normalize_target(raw_target: str) -> str:
    normalized_target = raw_target.strip()
    if normalized_target.startswith("global."):
        normalized_target = normalized_target.removeprefix("global.").strip()
    return normalized_target


def path_aliases(file_path: str) -> set[str]:
    path = PurePosixPath(file_path)
    aliases: set[str] = set()
    source_parts = list(path.parts)
    for source_root in ("src", "app", "lib"):
        if source_root not in source_parts:
            continue
        root_index = source_parts.index(source_root)
        module_parts = list(source_parts[root_index + 1 :])
        if not module_parts:
            continue
        module_parts[-1] = PurePosixPath(module_parts[-1]).stem
        aliases.add(".".join(part for part in module_parts if part))
        break
    return {alias for alias in aliases if alias}


@lru_cache(maxsize=32_768)
def _normalize_lookup_path(raw_path: str) -> str:
    return str(raw_path or "").strip().replace("\\", "/").strip("/")


def _dedupe_lowered_lookup_candidates(*candidates: str) -> tuple[str, ...]:
    normalized_candidates: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized_candidate = _normalize_lookup_path(candidate)
        if not normalized_candidate:
            continue
        lowered_candidate = normalized_candidate.lower()
        if lowered_candidate in seen:
            continue
        seen.add(lowered_candidate)
        normalized_candidates.append(lowered_candidate)
    return tuple(normalized_candidates)


@lru_cache(maxsize=32_768)
def _import_lookup_suffixes(normalized_target: str) -> tuple[str, ...]:
    namespace_path = normalized_target.replace(".", "/")
    leaf_name = normalized_target.rsplit(".", 1)[-1]
    return _dedupe_lowered_lookup_candidates(
        normalized_target,
        namespace_path,
        f"{namespace_path}.fs",
        f"{namespace_path}.fsi",
        f"{namespace_path}.fsx",
        f"{leaf_name}.fs",
        f"{leaf_name}.fsi",
        f"{leaf_name}.fsx",
    )


@lru_cache(maxsize=32_768)
def _import_lookup_prefixes(normalized_target: str) -> tuple[str, ...]:
    namespace_path = normalized_target.replace(".", "/")
    return _dedupe_lowered_lookup_candidates(
        namespace_path,
        f"src/{namespace_path}",
        f"app/{namespace_path}",
        f"lib/{namespace_path}",
    )


@lru_cache(maxsize=32_768)
def _context_lookup_suffixes(normalized_target: str) -> tuple[str, ...]:
    return _dedupe_lowered_lookup_candidates(
        f"{normalized_target}.fs",
        f"{normalized_target}.fsi",
        f"{normalized_target}.fsx",
    )


def _build_module_index_lookup(module_index: dict[str, str]) -> _ModuleIndexLookup:
    values = tuple(sorted(set(module_index.values())))
    exact_paths: dict[str, str] = {}
    suffix_paths: dict[str, str] = {}
    directory_suffix_paths: dict[str, str] = {}
    for file_path in values:
        normalized_file_path = _normalize_lookup_path(file_path)
        if not normalized_file_path:
            continue
        lowered_file_path = normalized_file_path.lower()
        exact_paths.setdefault(lowered_file_path, normalized_file_path)
        path_parts = PurePosixPath(lowered_file_path).parts
        for start in range(len(path_parts)):
            suffix_paths.setdefault("/".join(path_parts[start:]), normalized_file_path)
        directory_parts = path_parts[:-1]
        for start in range(len(directory_parts)):
            directory_suffix_paths.setdefault(
                "/".join(directory_parts[start:]),
                normalized_file_path,
            )
    return _ModuleIndexLookup(
        values=values,
        exact_paths=exact_paths,
        suffix_paths=suffix_paths,
        directory_suffix_paths=directory_suffix_paths,
    )


def _resolve_suffix_from_lookup(
    *,
    module_index_lookup: _ModuleIndexLookup,
    suffixes: Sequence[str],
) -> str | None:
    for suffix in suffixes:
        if not suffix:
            continue
        direct_match = module_index_lookup.exact_paths.get(suffix)
        if direct_match is not None:
            return direct_match
        suffix_match = module_index_lookup.suffix_paths.get(suffix)
        if suffix_match is not None:
            return suffix_match
    return None


def _resolve_directory_prefix_from_lookup(
    *,
    module_index_lookup: _ModuleIndexLookup,
    prefixes: Sequence[str],
) -> str | None:
    for prefix in prefixes:
        if not prefix:
            continue
        prefix_match = module_index_lookup.directory_suffix_paths.get(prefix)
        if prefix_match is not None:
            return prefix_match
    return None


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, str, int]] = set()
    current_namespaces: list[str] = []
    current_module_path: str | None = None
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        stripped_line = raw_line.strip()
        if not stripped_line or stripped_line.startswith(
            ("//", "///", "#if", "#else", "#endif")
        ):
            continue
        namespace_match = NAMESPACE_RE.match(stripped_line)
        if namespace_match is not None:
            current_namespaces = [normalize_target(namespace_match.group("target"))]
            current_module_path = None
            continue
        module_match = MODULE_RE.match(stripped_line)
        symbol_kind: str | None = None
        symbol_name: str | None = None
        qualified_names: set[str] = set()
        if module_match is not None:
            raw_target = normalize_target(module_match.group("target"))
            if not raw_target:
                continue
            if "." in raw_target:
                current_module_path = raw_target
            elif current_namespaces:
                current_module_path = f"{current_namespaces[-1]}.{raw_target}"
            else:
                current_module_path = raw_target
            symbol_kind = "module"
            symbol_name = raw_target.rsplit(".", 1)[-1]
            qualified_names.add(raw_target)
            qualified_names.add(current_module_path)
        else:
            type_match = TYPE_DECL_RE.match(stripped_line)
            if type_match is not None:
                symbol_kind = "type"
                symbol_name = normalize_symbol_name(type_match.group("name"))
            else:
                let_match = LET_DECL_RE.match(stripped_line)
                if let_match is not None:
                    symbol_kind = "function"
                    raw_symbol_name = let_match.group("name") or let_match.group(
                        "operator"
                    )
                    symbol_name = normalize_symbol_name(raw_symbol_name or "")
        if symbol_kind is None or symbol_name is None or not symbol_name:
            continue
        if symbol_name in RESERVED_SYMBOL_NAMES:
            continue
        qualified_names.add(symbol_name)
        for namespace in current_namespaces:
            if namespace:
                qualified_names.add(f"{namespace}.{symbol_name}")
        if current_module_path:
            qualified_names.add(f"{current_module_path}.{symbol_name}")
        symbol_key = (symbol_kind, symbol_name, line_no)
        if symbol_key in seen_symbol_keys:
            continue
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
                "signature": symbol_name,
                "qualified_names": tuple(
                    sorted(name for name in qualified_names if name)
                ),
            }
        )
    final_line = len(text.splitlines()) if text else 1
    for index, entry in enumerate(symbol_entries):
        if index + 1 < len(symbol_entries):
            entry["end_line"] = max(
                int(symbol_entries[index + 1]["start_line"]) - 1,
                int(entry["start_line"]),
            )
        else:
            entry["end_line"] = final_line
    return symbol_entries


def namespaces_from_text(text: str) -> tuple[str, ...]:
    namespaces: list[str] = []
    seen: set[str] = set()
    for match in NAMESPACE_RE.finditer(text):
        namespace_target = normalize_target(match.group("target"))
        if not namespace_target or namespace_target in seen:
            continue
        seen.add(namespace_target)
        namespaces.append(namespace_target)
    return tuple(namespaces)


def open_targets(text: str) -> tuple[str, ...]:
    targets: list[str] = []
    seen: set[str] = set()
    for match in OPEN_RE.finditer(text):
        open_target = normalize_target(match.group("target"))
        if not open_target or open_target in seen:
            continue
        seen.add(open_target)
        targets.append(open_target)
    return tuple(targets)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
    include_symbol_aliases: bool = True,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix not in {".fs", ".fsi", ".fsx"}:
        return set()
    aliases = path_aliases(file_path)
    effective_text = text
    if effective_text is None:
        try:
            effective_text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            effective_text = ""
    namespaces = namespaces_from_text(effective_text)
    aliases.update(namespaces)
    for namespace in namespaces:
        aliases.add(f"{namespace}.{path.stem}")
    if include_symbol_aliases:
        for symbol_entry in collect_symbol_entries(
            effective_text,
            file_path=file_path,
            stable_identifier=stable_identifier,
        ):
            aliases.update(symbol_entry["qualified_names"])
    return {alias for alias in aliases if alias}


def resolve_import(
    import_target: str,
    *,
    module_index: dict[str, str],
    module_index_lookup: _ModuleIndexLookup | None,
    resolve_suffix_match: ResolveSuffixMatch,
    resolve_directory_prefix_match: ResolveDirectoryPrefixMatch,
) -> str | None:
    normalized_target = normalize_target(import_target)
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    resolved = None
    suffixes = _import_lookup_suffixes(normalized_target)
    if module_index_lookup is not None:
        resolved = _resolve_suffix_from_lookup(
            module_index_lookup=module_index_lookup,
            suffixes=suffixes,
        )
    if resolved is None and module_index_lookup is None:
        resolved = resolve_suffix_match(
            module_index=module_index,
            suffixes=suffixes,
        )
    if resolved is not None:
        return resolved
    prefixes = _import_lookup_prefixes(normalized_target)
    if module_index_lookup is not None:
        resolved = _resolve_directory_prefix_from_lookup(
            module_index_lookup=module_index_lookup,
            prefixes=prefixes,
        )
        if resolved is not None:
            return resolved
        return None
    return resolve_directory_prefix_match(
        module_index=module_index,
        prefixes=prefixes,
    )


def resolve_context_reference(
    *,
    current_namespaces: Sequence[str],
    opened_namespaces: Sequence[str],
    target_name: str,
    module_index: dict[str, str],
    module_index_lookup: _ModuleIndexLookup | None,
    resolve_suffix_match: ResolveSuffixMatch,
    resolve_directory_prefix_match: ResolveDirectoryPrefixMatch,
) -> str | None:
    normalized_target = normalize_target(target_name)
    if not normalized_target:
        return None
    resolved = resolve_import(
        normalized_target,
        module_index=module_index,
        module_index_lookup=module_index_lookup,
        resolve_suffix_match=resolve_suffix_match,
        resolve_directory_prefix_match=resolve_directory_prefix_match,
    )
    if resolved is not None:
        return resolved
    current_namespace_tuple = (
        current_namespaces if isinstance(current_namespaces, tuple) else tuple(current_namespaces)
    )
    opened_namespace_tuple = (
        opened_namespaces if isinstance(opened_namespaces, tuple) else tuple(opened_namespaces)
    )
    for namespace in current_namespace_tuple + opened_namespace_tuple:
        resolved = resolve_import(
            f"{namespace}.{normalized_target}",
            module_index=module_index,
            module_index_lookup=module_index_lookup,
            resolve_suffix_match=resolve_suffix_match,
            resolve_directory_prefix_match=resolve_directory_prefix_match,
        )
        if resolved is not None:
            return resolved
    suffixes = _context_lookup_suffixes(normalized_target)
    if module_index_lookup is not None:
        resolved = _resolve_suffix_from_lookup(
            module_index_lookup=module_index_lookup,
            suffixes=suffixes,
        )
        if resolved is not None:
            return resolved
        return None
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes)


def _build_cached_resolvers(
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
    resolve_directory_prefix_match: ResolveDirectoryPrefixMatch,
) -> tuple[ResolveImportTarget, ResolveContextTarget]:
    module_index_lookup = _build_module_index_lookup(module_index)
    import_cache: dict[str, str | None] = {}
    context_cache: dict[tuple[tuple[str, ...], tuple[str, ...], str], str | None] = {}
    context_suffix_cache: dict[str, str | None] = {}

    def resolve_import_target(import_target: str) -> str | None:
        normalized_target = normalize_target(import_target)
        if not normalized_target:
            return None
        if normalized_target in import_cache:
            return import_cache[normalized_target]
        resolved = resolve_import(
            normalized_target,
            module_index=module_index,
            module_index_lookup=module_index_lookup,
            resolve_suffix_match=resolve_suffix_match,
            resolve_directory_prefix_match=resolve_directory_prefix_match,
        )
        import_cache[normalized_target] = resolved
        return resolved

    def resolve_context_target(
        current_namespaces: Sequence[str],
        opened_namespaces: Sequence[str],
        target_name: str,
    ) -> str | None:
        normalized_target = normalize_target(target_name)
        if not normalized_target:
            return None
        cache_key = (
            current_namespaces
            if isinstance(current_namespaces, tuple)
            else tuple(current_namespaces),
            opened_namespaces
            if isinstance(opened_namespaces, tuple)
            else tuple(opened_namespaces),
            normalized_target,
        )
        if cache_key in context_cache:
            return context_cache[cache_key]
        current_namespace_tuple, opened_namespace_tuple, _ = cache_key
        resolved = resolve_import_target(normalized_target)
        if resolved is None:
            for namespace in current_namespace_tuple + opened_namespace_tuple:
                resolved = resolve_import_target(f"{namespace}.{normalized_target}")
                if resolved is not None:
                    break
        if resolved is None:
            resolved = context_suffix_cache.get(normalized_target)
            if normalized_target not in context_suffix_cache:
                suffixes = _context_lookup_suffixes(normalized_target)
                if module_index_lookup is not None:
                    resolved = _resolve_suffix_from_lookup(
                        module_index_lookup=module_index_lookup,
                        suffixes=suffixes,
                    )
                else:
                    resolved = resolve_suffix_match(
                        module_index=module_index,
                        suffixes=suffixes,
                    )
                context_suffix_cache[normalized_target] = resolved
        context_cache[cache_key] = resolved
        return resolved

    return resolve_import_target, resolve_context_target


def extract_import_bindings(
    file_path: str,
    text: str,
    *,
    stable_identifier: StableIdentifier,
    resolve_import_target: ResolveImportTarget,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding], tuple[str, ...]]:
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    opened_namespaces = open_targets(text)
    for match in OPEN_RE.finditer(text):
        import_target = normalize_target(match.group("target"))
        if not import_target:
            continue
        target_file = resolve_import_target(import_target)
        dependency_key = (target_file, import_target, "imports")
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": import_target,
                            "line": match.start(),
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=import_target.rsplit(".", 1)[-1],
                    dependency_type="imports",
                )
            )
        short_name = import_target.rsplit(".", 1)[-1]
        for alias in (short_name, import_target):
            if not alias:
                continue
            import_bindings.setdefault(
                alias,
                _ImportedSymbolBinding(
                    alias=alias,
                    target_file=target_file,
                    target_names=(),
                ),
            )
    return tuple(dependencies), import_bindings, opened_namespaces


def _append_type_reference_dependencies(
    *,
    dependencies: tuple[_Dependency, ...],
    import_bindings: dict[str, _ImportedSymbolBinding],
    opened_namespaces: Sequence[str],
    current_namespaces: Sequence[str],
    declared_symbol_names: set[str],
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
    resolve_context_target: ResolveContextTarget,
) -> tuple[_Dependency, ...]:
    dependency_entries = list(dependencies)
    dependency_keys = {
        (dependency.target_file, dependency.target_symbol, dependency.dependency_type)
        for dependency in dependency_entries
    }
    resolved_type_targets: dict[str, str | None] = {}
    imported_short_names = {
        alias
        for alias in import_bindings
        if "." not in alias and alias not in RESERVED_SYMBOL_NAMES
    }
    for match in TYPE_REFERENCE_RE.finditer(text):
        type_name = normalize_symbol_name(match.group("name"))
        if (
            not type_name
            or type_name in RESERVED_SYMBOL_NAMES
            or type_name in declared_symbol_names
            or type_name in imported_short_names
        ):
            continue
        target_file = resolved_type_targets.get(type_name)
        if type_name not in resolved_type_targets:
            target_file = resolve_context_target(
                current_namespaces,
                opened_namespaces,
                type_name,
            )
            resolved_type_targets[type_name] = target_file
        dependency_key = (target_file, type_name, "references")
        if target_file is None or target_file == file_path or dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        dependency_entries.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {"file_path": file_path, "target": type_name, "line": match.start()},
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=type_name,
                dependency_type="references",
            )
        )
    return tuple(dependency_entries)


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
    resolve_directory_prefix_match: ResolveDirectoryPrefixMatch,
) -> tuple[_Dependency, ...]:
    resolve_import_target, resolve_context_target = _build_cached_resolvers(
        module_index=module_index,
        resolve_suffix_match=resolve_suffix_match,
        resolve_directory_prefix_match=resolve_directory_prefix_match,
    )
    dependencies, import_bindings, opened_namespaces = extract_import_bindings(
        file_path,
        text,
        stable_identifier=stable_identifier,
        resolve_import_target=resolve_import_target,
    )
    declared_symbol_names = {
        str(entry["symbol_name"])
        for entry in collect_symbol_entries(
            text,
            file_path=file_path,
            stable_identifier=stable_identifier,
        )
    }
    current_namespaces = namespaces_from_text(text)
    return _append_type_reference_dependencies(
        dependencies=dependencies,
        import_bindings=import_bindings,
        opened_namespaces=opened_namespaces,
        current_namespaces=current_namespaces,
        declared_symbol_names=declared_symbol_names,
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
        resolve_context_target=resolve_context_target,
    )


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
    resolve_directory_prefix_match: ResolveDirectoryPrefixMatch,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    resolve_import_target, resolve_context_target = _build_cached_resolvers(
        module_index=module_index,
        resolve_suffix_match=resolve_suffix_match,
        resolve_directory_prefix_match=resolve_directory_prefix_match,
    )
    symbol_entries = collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
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
    dependencies, import_bindings, opened_namespaces = extract_import_bindings(
        file_path,
        text,
        stable_identifier=stable_identifier,
        resolve_import_target=resolve_import_target,
    )
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    current_namespaces = tuple(namespaces_from_text(text))
    resolved_alias_targets: dict[str, str | None] = {}
    lines = text.splitlines()
    for symbol in symbols:
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for match in QUALIFIED_REFERENCE_RE.finditer(snippet):
            alias = normalize_target(match.group("alias"))
            target_name = normalize_symbol_name(match.group("name"))
            if not alias or not target_name:
                continue
            binding = import_bindings.get(alias)
            target_file = binding.target_file if binding is not None else None
            if target_file is None:
                target_file = resolved_alias_targets.get(alias)
                if alias not in resolved_alias_targets:
                    target_file = resolve_context_target(
                        current_namespaces,
                        opened_namespaces,
                        alias,
                    )
                    resolved_alias_targets[alias] = target_file
            if target_file is None:
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol.symbol_id,
                    "target_file": target_file,
                    "target_names": (target_name,),
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
                    target_names=(target_name,),
                    reference_type="references_symbol",
                ),
            )
    dependency_entries = _append_type_reference_dependencies(
        dependencies=dependencies,
        import_bindings=import_bindings,
        opened_namespaces=opened_namespaces,
        current_namespaces=current_namespaces,
        declared_symbol_names={str(entry["symbol_name"]) for entry in symbol_entries},
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
        resolve_context_target=resolve_context_target,
    )
    return (
        symbols,
        dependency_entries,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )

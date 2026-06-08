from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]
ModuleIndexAliasesForFile = Callable[[dict[str, str], str], set[str]]

IMPORT_LINE_RE = re.compile(r"^\s*import\s+(?P<body>.+)$", re.MULTILINE)
FROM_IMPORT_RE = re.compile(
    r"^\s*from\s+(?P<target>[A-Za-z0-9_./]+)\s+import\s+(?P<body>.+)$",
    re.MULTILINE,
)
INCLUDE_LINE_RE = re.compile(r"^\s*include\s+(?P<body>.+)$", re.MULTILINE)
GROUPED_IMPORT_RE = re.compile(
    r"^(?P<prefix>[A-Za-z0-9_./]+)\s*/\s*\[(?P<body>[^\]]+)\]$"
)
FUNCTION_DECL_RE = re.compile(
    r"^\s*(?:proc|func|method|template|macro|iterator|converter)\s+`?(?P<name>[A-Za-z_][A-Za-z0-9_]*)`?\*?"
    r"(?:\[[^\]]*\])?\s*\(",
    re.MULTILINE,
)
TYPE_DECL_RE = re.compile(
    r"^\s*type\s+(?P<name>[A-Z][A-Za-z0-9_]*)\*?\s*(?:\[[^\]]*\])?\s*=",
    re.MULTILINE,
)
QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
CALL_RE = re.compile(r"\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
RESERVED_SYMBOL_NAMES = frozenset(
    {
        "addr",
        "and",
        "as",
        "asm",
        "bind",
        "block",
        "break",
        "case",
        "cast",
        "concept",
        "const",
        "continue",
        "converter",
        "defer",
        "discard",
        "distinct",
        "div",
        "do",
        "elif",
        "else",
        "end",
        "enum",
        "except",
        "export",
        "finally",
        "for",
        "from",
        "func",
        "if",
        "import",
        "in",
        "include",
        "interface",
        "is",
        "isnot",
        "iterator",
        "let",
        "macro",
        "method",
        "mixin",
        "mod",
        "nil",
        "not",
        "notin",
        "object",
        "of",
        "or",
        "out",
        "proc",
        "ptr",
        "raise",
        "ref",
        "return",
        "shl",
        "shr",
        "static",
        "template",
        "try",
        "tuple",
        "type",
        "using",
        "var",
        "when",
        "while",
        "xor",
        "yield",
    }
)


def is_declared_symbol_alias(value: str) -> bool:
    normalized = value.strip()
    return bool(
        normalized
        and normalized not in RESERVED_SYMBOL_NAMES
        and "/" not in normalized
        and "." not in normalized
        and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", normalized)
    )


def declared_symbol_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix != ".nim":
        return set()
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    aliases: set[str] = set()
    for regex in (FUNCTION_DECL_RE, TYPE_DECL_RE):
        for match in regex.finditer(text):
            symbol_name = str(match.group("name") or "").strip()
            if is_declared_symbol_alias(symbol_name):
                aliases.add(symbol_name)
    return aliases


def module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    del root_path
    path = PurePosixPath(file_path)
    if path.suffix != ".nim":
        return set()
    aliases: set[str] = {str(path.with_suffix(""))}
    source_parts = list(path.parts)
    for source_root in ("src", "lib", "source"):
        if source_root not in source_parts:
            continue
        root_index = source_parts.index(source_root)
        module_parts = list(source_parts[root_index + 1 :])
        if not module_parts:
            continue
        module_parts[-1] = PurePosixPath(module_parts[-1]).stem
        slash_alias = "/".join(part for part in module_parts if part)
        dot_alias = ".".join(part for part in module_parts if part)
        if slash_alias:
            aliases.add(slash_alias)
        if dot_alias:
            aliases.add(dot_alias)
        break
    return {alias for alias in aliases if alias}


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = import_target.strip().replace("\\", "/")
    if not normalized_target:
        return None
    current_dir = normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    candidate_keys: list[str] = []
    direct_match = module_index.get(normalized_target)
    if direct_match is not None and direct_match != current_file:
        return direct_match
    if current_dir:
        relative_base = normalize_repository_relative_path(
            str(PurePosixPath(current_dir) / normalized_target)
        )
        if relative_base:
            candidate_keys.extend((relative_base, f"{relative_base}.nim"))
    candidate_keys.extend(
        (
            normalized_target,
            f"{normalized_target}.nim",
            normalized_target.replace(".", "/"),
            f"{normalized_target.replace('.', '/')}.nim",
            f"src/{normalized_target}",
            f"src/{normalized_target}.nim",
            f"src/{normalized_target.replace('.', '/')}.nim",
            f"lib/{normalized_target}",
            f"lib/{normalized_target}.nim",
        )
    )
    for candidate_key in candidate_keys:
        if not candidate_key:
            continue
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved != current_file:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=(
            f"{normalized_target}.nim",
            normalized_target,
            f"{normalized_target.replace('.', '/')}.nim",
            normalized_target.replace(".", "/"),
        ),
    )


def split_import_items(raw_body: str) -> tuple[str, ...]:
    body = raw_body.split("#", 1)[0].strip()
    if not body:
        return ()
    items: list[str] = []
    current: list[str] = []
    bracket_depth = 0
    for char in body:
        if char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth = max(bracket_depth - 1, 0)
        if char == "," and bracket_depth == 0:
            candidate = "".join(current).strip()
            if candidate:
                items.append(candidate)
            current = []
            continue
        current.append(char)
    candidate = "".join(current).strip()
    if candidate:
        items.append(candidate)
    return tuple(items)


def normalize_import_target(raw_target: str) -> str:
    target = raw_target.strip().split(" except ", 1)[0].strip()
    target = target.split(" as ", 1)[0].strip()
    return target


def expand_import_targets(raw_body: str) -> tuple[str, ...]:
    targets: list[str] = []
    for item in split_import_items(raw_body):
        normalized_item = normalize_import_target(item)
        if not normalized_item:
            continue
        grouped_match = GROUPED_IMPORT_RE.match(normalized_item)
        if grouped_match is not None:
            prefix = grouped_match.group("prefix").strip().rstrip("/")
            for raw_name in split_import_items(grouped_match.group("body")):
                normalized_name = normalize_import_target(raw_name)
                if normalized_name:
                    targets.append(f"{prefix}/{normalized_name}")
            continue
        targets.append(normalized_item)
    return tuple(dict.fromkeys(targets))


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    module_index_aliases_for_file: ModuleIndexAliasesForFile,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    dependency_keys: set[tuple[str | None, str, str]] = set()
    for match in IMPORT_LINE_RE.finditer(text):
        for import_target in expand_import_targets(match.group("body")):
            target_file = resolve_import(
                current_file=file_path,
                import_target=import_target,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
            dependency_key = (target_file, import_target, "import")
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
            binding_alias = PurePosixPath(import_target).name
            if binding_alias:
                import_bindings.setdefault(
                    binding_alias,
                    _ImportedSymbolBinding(
                        alias=binding_alias,
                        target_file=target_file,
                        target_names=(),
                    ),
                )
            if target_file is not None:
                for alias in sorted(module_index_aliases_for_file(module_index, target_file)):
                    if not is_declared_symbol_alias(alias):
                        continue
                    import_bindings.setdefault(
                        alias,
                        _ImportedSymbolBinding(
                            alias=alias,
                            target_file=target_file,
                            target_names=(alias,),
                        ),
                    )
    for match in FROM_IMPORT_RE.finditer(text):
        import_target = normalize_import_target(match.group("target"))
        if not import_target:
            continue
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target, "from_import")
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
                    target_symbol=PurePosixPath(import_target).name,
                    dependency_type="imports",
                )
            )
        imported_names: list[str] = []
        for raw_name in split_import_items(match.group("body")):
            normalized_name = normalize_import_target(raw_name)
            if (
                normalized_name
                and normalized_name not in RESERVED_SYMBOL_NAMES
                and normalized_name not in imported_names
            ):
                imported_names.append(normalized_name)
                import_bindings.setdefault(
                    normalized_name,
                    _ImportedSymbolBinding(
                        alias=normalized_name,
                        target_file=target_file,
                        target_names=(normalized_name,),
                    ),
                )
        module_alias = PurePosixPath(import_target).name
        if module_alias:
            import_bindings.setdefault(
                module_alias,
                _ImportedSymbolBinding(
                    alias=module_alias,
                    target_file=target_file,
                    target_names=tuple(imported_names),
                ),
            )
    for match in INCLUDE_LINE_RE.finditer(text):
        for import_target in split_import_items(match.group("body")):
            normalized_target = normalize_import_target(import_target)
            if not normalized_target:
                continue
            target_file = resolve_import(
                current_file=file_path,
                import_target=normalized_target,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
            dependency_key = (target_file, normalized_target, "include")
            if dependency_key in dependency_keys:
                continue
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": normalized_target,
                            "line": match.start(),
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=PurePosixPath(normalized_target).name,
                    dependency_type="imports",
                )
            )
    return tuple(dependencies), import_bindings


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
    module_index_aliases_for_file: ModuleIndexAliasesForFile,
) -> tuple[_Dependency, ...]:
    dependencies, _bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
        module_index_aliases_for_file=module_index_aliases_for_file,
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
    module_index_aliases_for_file: ModuleIndexAliasesForFile,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    lines = text.splitlines()
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_names: set[str] = set()
    for regex, symbol_kind in (
        (FUNCTION_DECL_RE, "function"),
        (TYPE_DECL_RE, "type"),
    ):
        for match in regex.finditer(text):
            symbol_name = match.group("name")
            if (
                not symbol_name
                or symbol_name in seen_symbol_names
                or symbol_name in RESERVED_SYMBOL_NAMES
            ):
                continue
            seen_symbol_names.add(symbol_name)
            line_no = text.count("\n", 0, match.start()) + 1
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
                }
            )
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
        module_index_aliases_for_file=module_index_aliases_for_file,
    )
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    symbol_ids_by_name = {symbol.symbol_name: symbol.symbol_id for symbol in symbols}
    for symbol in symbols:
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for match in QUALIFIED_REFERENCE_RE.finditer(snippet):
            binding = import_bindings.get(match.group("alias"))
            if binding is None or binding.target_file is None:
                continue
            target_name = match.group("name")
            if target_name in RESERVED_SYMBOL_NAMES:
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol.symbol_id,
                    "target_file": binding.target_file,
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
                    target_file=binding.target_file,
                    target_names=(target_name,),
                    reference_type="references_symbol",
                ),
            )
        for match in CALL_RE.finditer(snippet):
            target_name = match.group("name")
            if target_name in RESERVED_SYMBOL_NAMES:
                continue
            target_symbol_id = symbol_ids_by_name.get(target_name)
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
                        target_names=(target_name,),
                        reference_type="references_symbol",
                    ),
                )
                continue
            binding = import_bindings.get(target_name)
            if (
                binding is None
                or binding.target_file is None
                or target_name not in binding.target_names
            ):
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol.symbol_id,
                    "target_file": binding.target_file,
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
                    target_file=binding.target_file,
                    target_names=(target_name,),
                    reference_type="references_symbol",
                ),
            )
    return (
        symbols,
        dependencies,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )

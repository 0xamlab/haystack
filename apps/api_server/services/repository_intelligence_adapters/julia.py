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

PROJECT_NAME_RE = re.compile(
    r'^\s*name\s*=\s*"(?P<name>[A-Za-z_][A-Za-z0-9_!]*)"\s*$',
    re.MULTILINE,
)
MODULE_DECL_RE = re.compile(
    r"^\s*(?:baremodule|module)\s+(?P<name>[A-Z][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
INCLUDE_RE = re.compile(
    r"""\binclude\s*\(\s*["'](?P<target>[^"']+\.jl)["']\s*\)""",
    re.MULTILINE,
)
IMPORT_RE = re.compile(
    r"^\s*(?P<kind>using|import)\s+(?P<body>.+?)\s*$",
    re.MULTILINE,
)
FUNCTION_DECL_RE = re.compile(
    r"^\s*function\s+(?P<name>[A-Za-z_][A-Za-z0-9_!?']*)\b",
    re.MULTILINE,
)
SHORT_FUNCTION_DECL_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_!?']*)\s*\([^=\n]*\)\s*=",
    re.MULTILINE,
)
TYPE_DECL_RE = re.compile(
    r"^\s*(?:abstract\s+type|primitive\s+type|mutable\s+struct|struct)\s+"
    r"(?P<name>[A-Z][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_!?']*)\s*\("
)
CALL_RE = re.compile(r"\b(?P<name>[A-Za-z_][A-Za-z0-9_!?']*)\s*\(")
RESERVED_SYMBOL_NAMES = frozenset(
    {
        "baremodule",
        "begin",
        "break",
        "catch",
        "const",
        "continue",
        "do",
        "else",
        "elseif",
        "end",
        "false",
        "finally",
        "for",
        "function",
        "if",
        "import",
        "include",
        "let",
        "local",
        "macro",
        "module",
        "quote",
        "return",
        "struct",
        "true",
        "try",
        "using",
        "while",
    }
)


def project_name_from_text(text: str) -> str | None:
    project_match = PROJECT_NAME_RE.search(text)
    if project_match is None:
        return None
    project_name = str(project_match.group("name") or "").strip()
    return project_name or None


def package_context_for_path(
    *,
    root_path: Path,
    file_path: str,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> tuple[str | None, str | None]:
    path = PurePosixPath(file_path)
    for parent in (path.parent, *path.parents):
        normalized_parent = normalize_repository_relative_path(str(parent))
        if normalized_parent == file_path:
            continue
        base_path = root_path if normalized_parent in {"", "."} else root_path / normalized_parent
        project_path = base_path / "Project.toml"
        if not project_path.exists():
            continue
        package_name: str | None = None
        try:
            package_name = project_name_from_text(
                project_path.read_text(encoding="utf-8", errors="replace")
            )
        except OSError:
            package_name = None
        if not package_name:
            parent_name = (
                PurePosixPath(normalized_parent).name if normalized_parent else root_path.name
            )
            package_name = parent_name or None
        return ("" if normalized_parent in {"", "."} else normalized_parent, package_name)
    return None, None


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() != ".jl":
        return set()
    aliases: set[str] = set()
    if path.stem:
        aliases.add(path.stem)
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    for match in MODULE_DECL_RE.finditer(text):
        module_name = str(match.group("name") or "").strip()
        if module_name:
            aliases.add(module_name)
    package_root, package_name = package_context_for_path(
        root_path=root_path,
        file_path=file_path,
        normalize_repository_relative_path=normalize_repository_relative_path,
    )
    if package_name:
        aliases.add(package_name)
    source_parts = list(path.parts)
    if "src" in source_parts:
        src_index = source_parts.index("src")
        relative_parts = list(source_parts[src_index + 1 :])
        if relative_parts:
            relative_parts[-1] = PurePosixPath(relative_parts[-1]).stem
            if package_name and relative_parts[0] == package_name:
                aliases.add(".".join(part for part in relative_parts if part))
            elif package_name and len(relative_parts) == 1:
                aliases.add(f"{package_name}.{relative_parts[0]}")
    if package_root is not None and package_name and path.stem == package_name:
        aliases.add(package_name)
    return {alias for alias in aliases if alias}


def resolve_include(
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
    current_dir = PurePosixPath(current_file).parent
    resolved_path = normalize_repository_relative_path(str(current_dir / normalized_target))
    if not resolved_path:
        return None
    candidate_keys = {
        resolved_path,
        resolved_path.replace("/", "."),
        str(PurePosixPath(resolved_path).with_suffix("")),
        str(PurePosixPath(resolved_path).with_suffix("")).replace("/", "."),
    }
    for candidate_key in candidate_keys:
        target_file = module_index.get(candidate_key)
        if target_file is not None:
            return target_file
    return resolve_suffix_match(module_index=module_index, suffixes=[resolved_path])


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = import_target.strip().lstrip(".")
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None and direct_match != current_file:
        return direct_match
    last_segment = normalized_target.split(".")[-1]
    direct_last_segment = module_index.get(last_segment)
    if direct_last_segment is not None and direct_last_segment != current_file:
        return direct_last_segment
    module_path = normalized_target.replace(".", "/")
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            f"{module_path}.jl",
            f"src/{module_path}.jl",
            f"src/{last_segment}.jl",
        ],
    )


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    import_bindings: dict[str, _ImportedSymbolBinding] = {}

    for match in INCLUDE_RE.finditer(text):
        import_target = str(match.group("target") or "").strip()
        if not import_target:
            continue
        target_file = resolve_include(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": import_target,
                        "line": match.start(),
                        "type": "imports",
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=PurePosixPath(import_target).stem,
                dependency_type="imports",
            )
        )

    for match in IMPORT_RE.finditer(text):
        body = re.sub(r"#.*$", "", str(match.group("body") or "")).strip()
        if not body:
            continue
        if ":" in body:
            module_part, names_part = body.split(":", 1)
            import_target = module_part.strip()
            if not import_target:
                continue
            target_file = resolve_import(
                current_file=file_path,
                import_target=import_target,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": import_target,
                            "line": match.start(),
                            "type": "imports",
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=import_target.split(".")[-1].lstrip("."),
                    dependency_type="imports",
                )
            )
            for raw_name in names_part.split(","):
                normalized_name = raw_name.strip()
                if not normalized_name:
                    continue
                if " as " in normalized_name:
                    source_name, alias_name = re.split(r"\s+as\s+", normalized_name, maxsplit=1)
                else:
                    source_name, alias_name = normalized_name, normalized_name
                source_name = source_name.strip()
                alias_name = alias_name.strip()
                if not source_name or not alias_name:
                    continue
                dependencies.append(
                    _Dependency(
                        dependency_edge_id=stable_identifier(
                            "dep",
                            {
                                "file_path": file_path,
                                "target": import_target,
                                "symbol": source_name,
                                "line": match.start(),
                                "type": "imports",
                            },
                        ),
                        source_file=file_path,
                        target_file=target_file,
                        target_symbol=source_name,
                        dependency_type="imports",
                    )
                )
                import_bindings[alias_name] = _ImportedSymbolBinding(
                    alias=alias_name,
                    target_file=target_file,
                    target_names=(source_name,),
                )
            continue
        for raw_target in body.split(","):
            import_target = raw_target.strip()
            if not import_target:
                continue
            target_file = resolve_import(
                current_file=file_path,
                import_target=import_target,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
            alias_name = import_target.lstrip(".").split(".")[-1]
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": import_target,
                            "line": match.start(),
                            "type": "imports",
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=alias_name,
                    dependency_type="imports",
                )
            )
            import_bindings[alias_name] = _ImportedSymbolBinding(
                alias=alias_name,
                target_file=target_file,
                target_names=(),
            )

    return tuple(dependencies), import_bindings


def is_operational_reference_name(target_name: str) -> bool:
    normalized_name = target_name.strip()
    if not normalized_name:
        return False
    first_character = normalized_name[0]
    return first_character == "_" or first_character.islower()


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    dependencies, _bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
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
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    lines = text.splitlines()
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, int]] = set()
    for regex, symbol_kind in (
        (MODULE_DECL_RE, "module"),
        (TYPE_DECL_RE, "type"),
        (FUNCTION_DECL_RE, "function"),
        (SHORT_FUNCTION_DECL_RE, "function"),
    ):
        for match in regex.finditer(text):
            symbol_name = str(match.group("name") or "").strip()
            if not symbol_name or symbol_name in RESERVED_SYMBOL_NAMES:
                continue
            line_no = text.count("\n", 0, match.start()) + 1
            symbol_key = (symbol_name, line_no)
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
    )
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    declared_symbol_names = {symbol.symbol_name for symbol in symbols}
    for symbol in symbols:
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for match in QUALIFIED_REFERENCE_RE.finditer(snippet):
            binding = import_bindings.get(match.group("alias"))
            if binding is None or binding.target_file is None:
                continue
            target_name = str(match.group("name") or "").strip()
            if (
                not target_name
                or target_name in RESERVED_SYMBOL_NAMES
                or not is_operational_reference_name(target_name)
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
        for match in CALL_RE.finditer(snippet):
            target_name = str(match.group("name") or "").strip()
            binding = import_bindings.get(target_name)
            if (
                not target_name
                or binding is None
                or binding.target_file is None
                or target_name in RESERVED_SYMBOL_NAMES
                or not is_operational_reference_name(target_name)
                or target_name in declared_symbol_names
                or (binding.target_names and target_name not in binding.target_names)
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

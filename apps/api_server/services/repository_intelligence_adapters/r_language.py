from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

PACKAGE_RE = re.compile(
    r"^\s*Package\s*:\s*(?P<name>[A-Za-z][A-Za-z0-9._]*)\s*$",
    re.MULTILINE,
)
SOURCE_RE = re.compile(
    r"""\bsource\s*\(\s*["'](?P<target>[^"']+)["']""",
    re.MULTILINE,
)
LIBRARY_RE = re.compile(
    r"\b(?:library|require)\s*\(\s*(?:package\s*=\s*)?(?P<target>[A-Za-z][A-Za-z0-9._]*)",
    re.MULTILINE,
)
NAMESPACE_CALL_RE = re.compile(
    r"\b(?P<pkg>[A-Za-z][A-Za-z0-9._]*)::(?P<private>:)?(?P<name>[A-Za-z.][A-Za-z0-9._]*)\b"
)
FUNCTION_DECL_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z.][A-Za-z0-9._]*)\s*(?:<-|=)\s*function\s*\(",
    re.MULTILINE,
)
CALL_RE = re.compile(r"(?<!:)\b(?P<name>[A-Za-z.][A-Za-z0-9._]*)\s*\(")
RESERVED_SYMBOL_NAMES = frozenset(
    {
        "break",
        "else",
        "FALSE",
        "for",
        "function",
        "if",
        "Inf",
        "library",
        "NA",
        "NA_character_",
        "NA_complex_",
        "NA_integer_",
        "NA_real_",
        "NaN",
        "next",
        "NULL",
        "repeat",
        "require",
        "return",
        "source",
        "switch",
        "TRUE",
        "while",
    }
)
BUILTIN_SYMBOL_NAMES = frozenset(
    {
        "abs",
        "all",
        "any",
        "as.character",
        "as.list",
        "assign",
        "attr",
        "attributes",
        "c",
        "class",
        "environment",
        "eval",
        "exists",
        "factor",
        "file.exists",
        "format",
        "get",
        "grep",
        "gsub",
        "identical",
        "inherits",
        "is.factor",
        "is.list",
        "is.na",
        "is.null",
        "isTRUE",
        "length",
        "levels",
        "list",
        "log",
        "match",
        "max",
        "mean",
        "message",
        "min",
        "names",
        "ncol",
        "nrow",
        "order",
        "parse",
        "paste",
        "paste0",
        "plot",
        "print",
        "range",
        "round",
        "seq_along",
        "seq_len",
        "sort",
        "sprintf",
        "stop",
        "sub",
        "sum",
        "summary",
        "tolower",
        "toupper",
        "transform",
        "unique",
        "warning",
    }
)


def package_name_from_text(text: str) -> str | None:
    package_match = PACKAGE_RE.search(text)
    if package_match is None:
        return None
    package_name = str(package_match.group("name") or "").strip()
    return package_name or None


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
        description_path = base_path / "DESCRIPTION"
        namespace_path = base_path / "NAMESPACE"
        if not description_path.exists() and not namespace_path.exists():
            continue
        package_name: str | None = None
        if description_path.exists():
            try:
                package_name = package_name_from_text(
                    description_path.read_text(encoding="utf-8", errors="replace")
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
    if path.suffix.lower() != ".r":
        return set()
    aliases: set[str] = set()
    if path.stem:
        aliases.add(path.stem)
    package_root, package_name = package_context_for_path(
        root_path=root_path,
        file_path=file_path,
        normalize_repository_relative_path=normalize_repository_relative_path,
    )
    if package_name:
        aliases.add(package_name)
        if path.stem:
            aliases.add(f"{package_name}::{path.stem}")
    if package_root is not None:
        relative_path = (
            file_path
            if package_root in {"", "."}
            else normalize_repository_relative_path(
                str(PurePosixPath(file_path).relative_to(PurePosixPath(package_root)))
            )
        )
        if relative_path:
            aliases.add(relative_path)
            aliases.add(str(PurePosixPath(relative_path).with_suffix("")))
    elif path.stem:
        aliases.add(str(path.with_suffix("")))
    return {alias for alias in aliases if alias}


def is_operational_reference_name(target_name: str) -> bool:
    normalized_name = target_name.strip()
    if not normalized_name:
        return False
    if normalized_name in RESERVED_SYMBOL_NAMES:
        return False
    return normalized_name not in BUILTIN_SYMBOL_NAMES


def extend_module_index_with_package_symbol_aliases(
    *,
    root_path: Path,
    file_paths: Sequence[str],
    index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> None:
    symbol_files: defaultdict[str, set[str]] = defaultdict(set)
    for file_path in file_paths:
        if PurePosixPath(file_path).suffix.lower() != ".r":
            continue
        package_root, _package_name = package_context_for_path(
            root_path=root_path,
            file_path=file_path,
            normalize_repository_relative_path=normalize_repository_relative_path,
        )
        if package_root is None:
            continue
        try:
            text = (root_path / file_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in FUNCTION_DECL_RE.finditer(text):
            symbol_name = str(match.group("name") or "").strip()
            if not is_operational_reference_name(symbol_name):
                continue
            symbol_files[symbol_name].add(file_path)
    for symbol_name, resolved_files in sorted(symbol_files.items()):
        if len(resolved_files) != 1:
            continue
        index.setdefault(symbol_name, next(iter(resolved_files)))


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
    current_dir = PurePosixPath(current_file).parent
    candidate_keys: list[str] = [normalized_target]
    candidate_paths = [
        normalize_repository_relative_path(str(current_dir / normalized_target)),
        normalize_repository_relative_path(normalized_target),
    ]
    for candidate_path in candidate_paths:
        if not candidate_path:
            continue
        candidate_keys.extend(
            (
                candidate_path,
                str(PurePosixPath(candidate_path).with_suffix("")),
            )
        )
    if "/" not in normalized_target and not normalized_target.lower().endswith(".r"):
        candidate_keys.extend(
            (
                f"{normalized_target}.R",
                f"{normalized_target}.r",
                f"R/{normalized_target}.R",
                f"R/{normalized_target}.r",
            )
        )
    for candidate_key in candidate_keys:
        if not candidate_key:
            continue
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved != current_file:
            return resolved
    target_name = PurePosixPath(normalized_target).name
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            normalized_target,
            f"{normalized_target}.R",
            f"{normalized_target}.r",
            f"/{target_name}",
            f"/{target_name}.R",
            f"/{target_name}.r",
        ],
    )


def extract_dependency_candidates(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    for match in SOURCE_RE.finditer(text):
        import_target = str(match.group("target") or "").strip()
        target_file = resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target, "imports")
        if not import_target or dependency_key in dependency_keys:
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
                target_symbol=PurePosixPath(import_target).stem or None,
                dependency_type="imports",
            )
        )
    for match in LIBRARY_RE.finditer(text):
        import_target = str(match.group("target") or "").strip()
        dependency_key = (None, import_target, "imports")
        if not import_target or dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {"file_path": file_path, "target": import_target, "line": match.start()},
                ),
                source_file=file_path,
                target_file=None,
                target_symbol=import_target,
                dependency_type="imports",
            )
        )
    return tuple(dependencies)


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    dependencies = list(
        extract_dependency_candidates(
            file_path,
            text,
            module_index,
            stable_identifier=stable_identifier,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
    )
    dependency_keys = {
        (dependency.target_file, dependency.target_symbol, dependency.dependency_type)
        for dependency in dependencies
    }
    declared_symbol_names = {
        str(match.group("name") or "").strip()
        for match in FUNCTION_DECL_RE.finditer(text)
        if str(match.group("name") or "").strip()
    }
    for match in CALL_RE.finditer(text):
        target_name = str(match.group("name") or "").strip()
        if not is_operational_reference_name(target_name) or target_name in declared_symbol_names:
            continue
        target_file = module_index.get(target_name)
        dependency_key = (target_file, target_name, "references")
        if target_file is None or target_file == file_path or dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {"file_path": file_path, "target": target_name, "type": "references"},
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_name,
                dependency_type="references",
            )
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
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    lines = text.splitlines()
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_names: set[str] = set()
    for match in FUNCTION_DECL_RE.finditer(text):
        symbol_name = str(match.group("name") or "").strip()
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
                        "kind": "function",
                    },
                ),
                "symbol_name": symbol_name,
                "symbol_kind": "function",
                "start_line": line_no,
                "end_line": line_no,
                "signature": symbol_name,
            }
        )
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
    dependencies = extract_dependency_candidates(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    symbol_ids_by_name = {symbol.symbol_name: symbol.symbol_id for symbol in symbols}
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    for symbol in symbols:
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for match in CALL_RE.finditer(snippet):
            target_name = str(match.group("name") or "").strip()
            target_symbol_id = symbol_ids_by_name.get(target_name)
            if (
                not is_operational_reference_name(target_name)
                or target_symbol_id is None
                or target_symbol_id == symbol.symbol_id
            ):
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

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

DOT_SOURCE_RE = re.compile(
    r"^\s*\.\s+(?P<target>(?:\"[^\"]+\"|'[^']+'|[^\s#;]+))",
    re.MULTILINE,
)
IMPORT_MODULE_RE = re.compile(
    r"^\s*Import-Module\s+(?:-Name\s+)?(?P<target>(?:\"[^\"]+\"|'[^']+'|[^\s#;]+))",
    re.MULTILINE | re.IGNORECASE,
)
USING_MODULE_RE = re.compile(
    r"^\s*using\s+module\s+(?P<target>(?:\"[^\"]+\"|'[^']+'|[^\s#;]+))",
    re.MULTILINE | re.IGNORECASE,
)
FUNCTION_DECL_RE = re.compile(
    r"^\s*(?:function|filter)\s+(?P<name>[A-Za-z_][A-Za-z0-9_-]*)\b",
    re.MULTILINE | re.IGNORECASE,
)
TYPE_DECL_RE = re.compile(
    r"^\s*(?P<kind>class|enum)\s+(?P<name>[A-Z][A-Za-z0-9_]*)\b",
    re.MULTILINE | re.IGNORECASE,
)
COMMAND_NAME_RE = re.compile(
    r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*(?:-[A-Za-z_][A-Za-z0-9_]*)?)\b"
)
TYPE_REFERENCE_RE = re.compile(r"\[(?P<name>[A-Z][A-Za-z0-9_]*)\]")
SOURCE_SUFFIXES = (".ps1", ".psm1", ".psd1")
RESERVED_SYMBOL_NAMES = frozenset(
    {
        "begin",
        "break",
        "catch",
        "class",
        "continue",
        "data",
        "do",
        "dynamicparam",
        "else",
        "elseif",
        "end",
        "enum",
        "exit",
        "filter",
        "finally",
        "for",
        "foreach",
        "from",
        "function",
        "if",
        "in",
        "param",
        "process",
        "return",
        "switch",
        "throw",
        "trap",
        "try",
        "until",
        "using",
        "while",
        "workflow",
    }
)
BUILTIN_COMMAND_NAMES = frozenset(
    {
        "Add-Member",
        "ConvertFrom-Json",
        "ConvertTo-Json",
        "Export-ModuleMember",
        "ForEach-Object",
        "Get-ChildItem",
        "Get-Command",
        "Get-Content",
        "Get-Item",
        "Get-ItemProperty",
        "Get-Location",
        "Get-Module",
        "Get-Variable",
        "Import-Module",
        "Join-Path",
        "New-Item",
        "New-ModuleManifest",
        "New-Object",
        "Out-Null",
        "Remove-Item",
        "Resolve-Path",
        "Select-Object",
        "Set-Location",
        "Set-StrictMode",
        "Sort-Object",
        "Split-Path",
        "Test-Path",
        "Where-Object",
        "Write-Debug",
        "Write-Error",
        "Write-Host",
        "Write-Output",
        "Write-Verbose",
        "Write-Warning",
    }
)
BUILTIN_TYPE_NAMES = frozenset(
    {
        "Array",
        "Boolean",
        "Byte",
        "Double",
        "Guid",
        "Hashtable",
        "Int",
        "Int16",
        "Int32",
        "Int64",
        "Object",
        "PSCustomObject",
        "PSObject",
        "ScriptBlock",
        "Single",
        "String",
        "Uri",
        "Version",
    }
)


def prefer_code_target(
    resolved_file: str | None,
    module_index: dict[str, str],
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> str | None:
    if resolved_file is None or not resolved_file.endswith(".psd1"):
        return resolved_file
    manifest_path = PurePosixPath(resolved_file)
    for suffix in (".psm1", ".ps1"):
        sibling_path = normalize_repository_relative_path(str(manifest_path.with_suffix(suffix)))
        if not sibling_path:
            continue
        sibling_match = module_index.get(sibling_path)
        if sibling_match is not None:
            return sibling_match
    return resolved_file


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = import_target.strip().strip("\"'").replace("\\", "/")
    normalized_target = re.sub(
        r"^\$(?:\{?[A-Za-z_][A-Za-z0-9_:]*\}?)[/\\]",
        "",
        normalized_target,
    )
    if (
        not normalized_target
        or normalized_target.startswith("/")
        or normalized_target.startswith("~")
        or "$" in normalized_target
        or "`" in normalized_target
        or "*" in normalized_target
        or "?" in normalized_target
    ):
        return None
    direct_match = prefer_code_target(
        module_index.get(normalized_target),
        module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
    )
    if direct_match is not None and direct_match != current_file:
        return direct_match
    current_dir = normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    candidate_keys: list[str] = []
    target_path = PurePosixPath(normalized_target)
    if current_dir:
        relative_base = normalize_repository_relative_path(
            str(PurePosixPath(current_dir) / normalized_target)
        )
        if relative_base:
            candidate_keys.append(relative_base)
            if PurePosixPath(relative_base).suffix.lower() not in SOURCE_SUFFIXES:
                candidate_keys.extend(f"{relative_base}{suffix}" for suffix in SOURCE_SUFFIXES)
    candidate_keys.append(normalized_target)
    if target_path.suffix.lower() not in SOURCE_SUFFIXES:
        candidate_keys.extend(f"{normalized_target}{suffix}" for suffix in SOURCE_SUFFIXES)
        candidate_keys.append(target_path.name)
        candidate_keys.extend(f"{target_path.name}{suffix}" for suffix in SOURCE_SUFFIXES)
    seen_keys: set[str] = set()
    ordered_candidates: list[str] = []
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if not normalized_candidate or normalized_candidate in seen_keys:
            continue
        seen_keys.add(normalized_candidate)
        ordered_candidates.append(normalized_candidate)
    for candidate_key in ordered_candidates:
        resolved = prefer_code_target(
            module_index.get(candidate_key),
            module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
        )
        if resolved is not None and resolved != current_file:
            return resolved
    suffixes = [*ordered_candidates, target_path.name, target_path.stem]
    if target_path.suffix.lower() not in SOURCE_SUFFIXES:
        suffixes.extend(f"{target_path.name}{suffix}" for suffix in SOURCE_SUFFIXES)
        suffixes.extend(f"{target_path.stem}{suffix}" for suffix in SOURCE_SUFFIXES)
    resolved = resolve_suffix_match(module_index=module_index, suffixes=suffixes)
    return prefer_code_target(
        resolved,
        module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
    )


def is_operational_reference_name(name: str) -> bool:
    normalized_name = name.strip()
    lower_name = normalized_name.lower()
    return bool(
        normalized_name
        and lower_name not in RESERVED_SYMBOL_NAMES
        and normalized_name not in BUILTIN_COMMAND_NAMES
        and normalized_name not in BUILTIN_TYPE_NAMES
    )


def extract_import_targets(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], tuple[str, ...]]:
    dependencies: list[_Dependency] = []
    target_files: list[str] = []
    seen_targets: set[tuple[str, str | None]] = set()
    for match in (
        list(DOT_SOURCE_RE.finditer(text))
        + list(IMPORT_MODULE_RE.finditer(text))
        + list(USING_MODULE_RE.finditer(text))
    ):
        raw_target = str(match.group("target") or "").strip()
        if not raw_target:
            continue
        target_file = resolve_import(
            current_file=file_path,
            import_target=raw_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (raw_target, target_file)
        if dependency_key in seen_targets:
            continue
        seen_targets.add(dependency_key)
        if target_file is not None:
            target_files.append(target_file)
        target_name = PurePosixPath(raw_target.strip("\"'")).stem
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {"file_path": file_path, "target": raw_target, "line": match.start()},
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_name or None,
                dependency_type="imports",
            )
        )
    return tuple(dependencies), tuple(dict.fromkeys(target_files))


def iter_reference_target_names(snippet: str) -> Iterable[str]:
    for raw_line in snippet.splitlines():
        stripped_line = raw_line.split("#", 1)[0].strip()
        if not stripped_line:
            continue
        lower_line = stripped_line.lower()
        for type_match in TYPE_REFERENCE_RE.finditer(stripped_line):
            target_name = str(type_match.group("name") or "").strip()
            if is_operational_reference_name(target_name):
                yield target_name
        if lower_line.startswith(
            ("function ", "filter ", "class ", "enum ", "using module ", "import-module ")
        ):
            continue
        if stripped_line.startswith(". "):
            continue
        for segment in re.split(r"[|;]", stripped_line):
            normalized_segment = segment.strip()
            if not normalized_segment:
                continue
            normalized_segment = normalized_segment.lstrip("(&")
            command_match = COMMAND_NAME_RE.match(normalized_segment)
            if command_match is None:
                continue
            target_name = str(command_match.group("name") or "").strip()
            if is_operational_reference_name(target_name):
                yield target_name


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, int, str]] = set()
    for match in FUNCTION_DECL_RE.finditer(text):
        symbol_name = str(match.group("name") or "").strip()
        if not is_operational_reference_name(symbol_name):
            continue
        line_no = text.count("\n", 0, match.start()) + 1
        symbol_key = ("function", symbol_name, line_no)
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
    for match in TYPE_DECL_RE.finditer(text):
        symbol_name = str(match.group("name") or "").strip()
        symbol_kind = str(match.group("kind") or "").strip().lower() or "type"
        if not is_operational_reference_name(symbol_name):
            continue
        line_no = text.count("\n", 0, match.start()) + 1
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
            }
        )
    symbol_entries.sort(key=lambda entry: (int(entry["start_line"]), str(entry["symbol_name"])))
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


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    dependencies, imported_target_files = extract_import_targets(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    if len(imported_target_files) != 1:
        return dependencies
    dependency_candidates = list(dependencies)
    seen_keys = {
        (dependency.target_file, dependency.target_symbol, dependency.dependency_type)
        for dependency in dependency_candidates
    }
    target_file = imported_target_files[0]
    for target_name in iter_reference_target_names(text):
        dependency_key = (target_file, target_name, "references")
        if dependency_key in seen_keys:
            continue
        seen_keys.add(dependency_key)
        dependency_candidates.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": target_file,
                        "symbol": target_name,
                        "kind": "references",
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_name,
                dependency_type="references",
            )
        )
    return tuple(dependency_candidates)


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
    dependencies, imported_target_files = extract_import_targets(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    lines = text.splitlines()
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    for symbol in symbols:
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for target_name in iter_reference_target_names(snippet):
            for target_file in imported_target_files:
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
    return (
        symbols,
        dependencies,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )

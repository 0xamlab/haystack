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

SOURCE_RE = re.compile(
    r"^\s*(?:source|\.)\s+(?P<target>(?:\"[^\"]+\"|'[^']+'|[^\s#;&|]+))",
    re.MULTILINE,
)
FUNCTION_DECL_RE = re.compile(
    r"^\s*(?:function\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?:\(\s*\))?\s*\{",
    re.MULTILINE,
)
COMMAND_SUBSTITUTION_RE = re.compile(r"\$\(\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
ASSIGNMENT_PREFIX_RE = re.compile(
    r"^(?:[A-Za-z_][A-Za-z0-9_]*=(?:\"[^\"]*\"|'[^']*'|[^\s;|&]+)\s+)+"
)
COMMAND_NAME_RE = re.compile(r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b")
SOURCE_SUFFIXES = (".sh", ".bash", ".zsh", ".ksh", ".zsh-theme")
CONTROL_PREFIXES = (
    "!",
    "builtin",
    "command",
    "elif",
    "else",
    "if",
    "then",
    "time",
    "until",
    "while",
)
RESERVED_SYMBOL_NAMES = frozenset(
    {
        "case",
        "coproc",
        "do",
        "done",
        "elif",
        "else",
        "esac",
        "fi",
        "for",
        "function",
        "if",
        "in",
        "select",
        "then",
        "time",
        "until",
        "while",
    }
)
BUILTIN_COMMAND_NAMES = frozenset(
    {
        ".",
        ":",
        "alias",
        "autoload",
        "bg",
        "bind",
        "break",
        "builtin",
        "caller",
        "cd",
        "command",
        "compdef",
        "compgen",
        "complete",
        "compopt",
        "continue",
        "declare",
        "dirs",
        "disown",
        "echo",
        "emulate",
        "enable",
        "eval",
        "exec",
        "exit",
        "export",
        "false",
        "fc",
        "fg",
        "float",
        "functions",
        "getopts",
        "hash",
        "help",
        "history",
        "integer",
        "jobs",
        "kill",
        "let",
        "local",
        "logout",
        "mapfile",
        "noglob",
        "popd",
        "printf",
        "pushd",
        "pwd",
        "read",
        "readonly",
        "return",
        "set",
        "shift",
        "shopt",
        "source",
        "suspend",
        "test",
        "times",
        "trap",
        "true",
        "type",
        "typeset",
        "ulimit",
        "umask",
        "unalias",
        "unset",
        "wait",
        "whence",
        "zle",
    }
)


def is_operational_reference_name(name: str) -> bool:
    normalized_name = name.strip()
    if not normalized_name:
        return False
    lower_name = normalized_name.lower()
    return lower_name not in RESERVED_SYMBOL_NAMES and lower_name not in BUILTIN_COMMAND_NAMES


def resolve_source(
    *,
    current_file: str,
    source_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = source_target.strip().strip("\"'").replace("\\", "/")
    normalized_target = re.sub(
        r"^\$(?:\{[A-Za-z_][A-Za-z0-9_]*\}|[A-Za-z_][A-Za-z0-9_]*)/",
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
        or normalized_target.startswith("<(")
    ):
        return None
    direct_match = module_index.get(normalized_target)
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
    seen_keys: set[str] = set()
    ordered_candidates: list[str] = []
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if not normalized_candidate or normalized_candidate in seen_keys:
            continue
        seen_keys.add(normalized_candidate)
        ordered_candidates.append(normalized_candidate)
    for candidate_key in ordered_candidates:
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved != current_file:
            return resolved
    suffixes = [*ordered_candidates, target_path.name]
    if target_path.suffix.lower() not in SOURCE_SUFFIXES:
        suffixes.extend(f"{target_path.name}{suffix}" for suffix in SOURCE_SUFFIXES)
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes)


def extract_source_targets(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], tuple[str, ...]]:
    dependencies: list[_Dependency] = []
    seen_dependency_keys: set[tuple[str, int]] = set()
    sourced_target_files: list[str] = []
    seen_target_files: set[str] = set()
    for match in SOURCE_RE.finditer(text):
        raw_target = str(match.group("target") or "").strip()
        normalized_target = raw_target.strip("\"'")
        if not normalized_target:
            continue
        dependency_key = (normalized_target, match.start())
        if dependency_key in seen_dependency_keys:
            continue
        seen_dependency_keys.add(dependency_key)
        target_file = resolve_source(
            current_file=file_path,
            source_target=normalized_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {"file_path": file_path, "target": normalized_target, "line": match.start()},
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=PurePosixPath(normalized_target).stem or normalized_target,
                dependency_type="imports",
            )
        )
        if target_file is not None and target_file not in seen_target_files:
            seen_target_files.add(target_file)
            sourced_target_files.append(target_file)
    return tuple(dependencies), tuple(sourced_target_files)


def iter_reference_target_names(snippet: str) -> Iterable[str]:
    seen_names: set[str] = set()
    for match in COMMAND_SUBSTITUTION_RE.finditer(snippet):
        target_name = str(match.group("name") or "").strip()
        if not is_operational_reference_name(target_name) or target_name in seen_names:
            continue
        seen_names.add(target_name)
        yield target_name
    for raw_line in snippet.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or FUNCTION_DECL_RE.match(line) or SOURCE_RE.match(line):
            continue
        for segment in re.split(r"\s*(?:&&|\|\||;|\|)\s*", line):
            command_segment = segment.strip()
            if not command_segment:
                continue
            while True:
                stripped_segment = command_segment.lstrip()
                if stripped_segment.startswith("$("):
                    command_segment = stripped_segment[2:].lstrip()
                    continue
                prefix_removed = False
                for prefix in CONTROL_PREFIXES:
                    if prefix == "!":
                        if stripped_segment.startswith("!"):
                            command_segment = stripped_segment[1:].lstrip()
                            prefix_removed = True
                            break
                    elif stripped_segment.startswith(f"{prefix} "):
                        command_segment = stripped_segment[len(prefix) :].lstrip()
                        prefix_removed = True
                        break
                if prefix_removed:
                    continue
                break
            command_segment = ASSIGNMENT_PREFIX_RE.sub("", command_segment).lstrip()
            if not command_segment or command_segment.startswith(
                ("local ", "readonly ", "typeset ", "declare ", "integer ", "float ")
            ):
                continue
            command_match = COMMAND_NAME_RE.match(command_segment)
            if command_match is None:
                continue
            target_name = str(command_match.group("name") or "").strip()
            if not is_operational_reference_name(target_name) or target_name in seen_names:
                continue
            seen_names.add(target_name)
            yield target_name


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, int]] = set()
    for match in FUNCTION_DECL_RE.finditer(text):
        symbol_name = str(match.group("name") or "").strip()
        if not is_operational_reference_name(symbol_name):
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
    dependencies, sourced_target_files = extract_source_targets(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    if len(sourced_target_files) != 1:
        return dependencies
    dependency_candidates = list(dependencies)
    seen_keys = {
        (dependency.target_file, dependency.target_symbol, dependency.dependency_type)
        for dependency in dependency_candidates
    }
    target_file = sourced_target_files[0]
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
    dependencies, sourced_target_files = extract_source_targets(
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
            for target_file in sourced_target_files:
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

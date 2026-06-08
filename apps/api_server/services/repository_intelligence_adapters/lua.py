from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _JSImportBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[..., str | None]

REQUIRE_RE = re.compile(
    r"\brequire\b\s*(?:\(\s*)?['\"](?P<target>[^'\"]+)['\"]",
    re.MULTILINE,
)
REQUIRE_BINDING_RE = re.compile(
    r"^\s*(?:local\s+)?(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"require\b\s*(?:\(\s*)?['\"](?P<target>[^'\"]+)['\"]\s*\)?"
    r"(?:\.(?P<member>[A-Za-z_][A-Za-z0-9_]*))?",
    re.MULTILINE,
)
FUNCTION_DECL_RE = re.compile(
    r"^\s*(?:local\s+)?function\s+"
    r"(?P<target>[A-Za-z_][A-Za-z0-9_]*(?:[.:][A-Za-z_][A-Za-z0-9_]*)*)\s*\(",
    re.MULTILINE,
)
FUNCTION_ASSIGN_RE = re.compile(
    r"^\s*(?P<target>[A-Za-z_][A-Za-z0-9_]*(?:[.:][A-Za-z_][A-Za-z0-9_]*)*)\s*=\s*function\s*\(",
    re.MULTILINE,
)
QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)[.:](?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
IMPORTED_CALL_RE = re.compile(r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
RESERVED_SYMBOL_NAMES = frozenset(
    {
        "and",
        "break",
        "do",
        "else",
        "elseif",
        "end",
        "false",
        "for",
        "function",
        "if",
        "in",
        "local",
        "nil",
        "not",
        "or",
        "repeat",
        "return",
        "self",
        "then",
        "true",
        "until",
        "while",
    }
)


def module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    del root_path
    path = PurePosixPath(file_path)
    if path.suffix != ".lua":
        return set()
    aliases: set[str] = set()
    without_suffix_path = str(path.with_suffix(""))
    if without_suffix_path:
        aliases.add(without_suffix_path)
        aliases.add(without_suffix_path.replace("/", "."))
    source_parts = list(path.parts)
    for source_root in ("lua", "lib", "src", "app"):
        if source_root not in source_parts:
            continue
        root_index = source_parts.index(source_root)
        module_parts = list(source_parts[root_index + 1 :])
        if not module_parts:
            continue
        stem = PurePosixPath(module_parts[-1]).stem
        if stem == "init":
            module_parts = module_parts[:-1]
        else:
            module_parts[-1] = stem
        if not module_parts:
            continue
        module_path = "/".join(part for part in module_parts if part)
        if not module_path:
            continue
        aliases.add(module_path)
        aliases.add(module_path.replace("/", "."))
        break
    if path.stem == "init":
        parent = str(path.parent)
        if parent and parent != ".":
            aliases.add(parent)
            aliases.add(parent.replace("/", "."))
    return {alias for alias in aliases if alias not in {".", "/"}}


def resolve_import(
    import_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = import_target.strip()
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    module_path = normalized_target.replace(".", "/")
    candidate_keys = [
        normalized_target,
        module_path,
        f"{module_path}.lua",
        f"{module_path}/init.lua",
        f"lua/{module_path}",
        f"lua/{module_path}.lua",
        f"lua/{module_path}/init.lua",
        f"lib/{module_path}",
        f"lib/{module_path}.lua",
        f"lib/{module_path}/init.lua",
        f"src/{module_path}",
        f"src/{module_path}.lua",
        f"src/{module_path}/init.lua",
    ]
    for candidate_key in candidate_keys:
        resolved = module_index.get(candidate_key)
        if resolved is not None:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            f"{module_path}.lua",
            f"{module_path}/init.lua",
            module_path,
            normalized_target,
        ],
    )


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _JSImportBinding]]:
    dependencies: list[_Dependency] = []
    bindings: dict[str, _JSImportBinding] = {}
    seen_dependency_keys: set[tuple[str, int]] = set()
    for match in REQUIRE_RE.finditer(text):
        import_target = match.group("target")
        dependency_key = (import_target, match.start())
        if dependency_key in seen_dependency_keys:
            continue
        seen_dependency_keys.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {"file_path": file_path, "target": import_target, "line": match.start()},
                ),
                source_file=file_path,
                target_file=resolve_import(
                    import_target,
                    module_index=module_index,
                    resolve_suffix_match=resolve_suffix_match,
                ),
                target_symbol=PurePosixPath(import_target.replace(".", "/")).name,
                dependency_type="imports",
            )
        )
    for match in REQUIRE_BINDING_RE.finditer(text):
        alias = match.group("alias")
        import_target = match.group("target")
        target_member = str(match.group("member") or "").strip()
        bindings[alias] = _JSImportBinding(
            alias=alias,
            target_file=resolve_import(
                import_target,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            ),
            target_names=((target_member,) if target_member else ()),
        )
    return tuple(dependencies), bindings


def iter_reference_targets(
    snippet: str,
    bindings: dict[str, _JSImportBinding],
) -> Iterable[tuple[_JSImportBinding, str]]:
    for match in QUALIFIED_REFERENCE_RE.finditer(snippet):
        binding = bindings.get(match.group("alias"))
        if binding is None or binding.target_file is None:
            continue
        target_name = str(match.group("name") or "").strip()
        if not target_name or target_name in RESERVED_SYMBOL_NAMES:
            continue
        yield binding, target_name
    for match in IMPORTED_CALL_RE.finditer(snippet):
        binding = bindings.get(match.group("alias"))
        if binding is None or binding.target_file is None or not binding.target_names:
            continue
        for target_name in binding.target_names:
            if not target_name or target_name in RESERVED_SYMBOL_NAMES:
                continue
            yield binding, target_name


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, int]] = set()
    matches = [
        *((match.start(), match.group("target")) for match in FUNCTION_DECL_RE.finditer(text)),
        *((match.start(), match.group("target")) for match in FUNCTION_ASSIGN_RE.finditer(text)),
    ]
    for offset, raw_target in sorted(matches):
        normalized_target = raw_target.strip()
        if not normalized_target:
            continue
        symbol_name = re.split(r"[.:]", normalized_target)[-1].strip()
        if not symbol_name or symbol_name in RESERVED_SYMBOL_NAMES:
            continue
        line_no = text.count("\n", 0, offset) + 1
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
                "signature": normalized_target,
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
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    dependencies, bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
    )
    dependency_candidates = list(dependencies)
    seen_keys = {
        (dependency.target_file, dependency.target_symbol, dependency.dependency_type)
        for dependency in dependency_candidates
    }
    for binding, target_name in iter_reference_targets(text, bindings):
        dependency_key = (binding.target_file, target_name, "references")
        if dependency_key in seen_keys:
            continue
        seen_keys.add(dependency_key)
        dependency_candidates.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": binding.target_file,
                        "symbol": target_name,
                        "kind": "references",
                    },
                ),
                source_file=file_path,
                target_file=binding.target_file,
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
    dependencies, bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
    )
    lines = text.splitlines()
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    for symbol in symbols:
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for binding, target_name in iter_reference_targets(snippet, bindings):
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

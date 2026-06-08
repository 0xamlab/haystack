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
ResolveModule = Callable[[str, dict[str, str]], str | None]
ResolveInclude = Callable[..., str | None]

MODULE_RE = re.compile(
    r"^-module\((?P<name>[a-z][A-Za-z0-9_@]*)\)\.",
    re.MULTILINE,
)
INCLUDE_RE = re.compile(
    r"^-include\([\"'](?P<target>[^\"']+\.hrl)[\"']\)\.",
    re.MULTILINE,
)
INCLUDE_LIB_RE = re.compile(
    r"^-include_lib\([\"'](?P<target>[^\"']+\.hrl)[\"']\)\.",
    re.MULTILINE,
)
IMPORT_RE = re.compile(
    r"^-import\((?P<module>[a-z][A-Za-z0-9_@]*),\s*\[(?P<functions>[^\]]*)\]\)\.",
    re.MULTILINE,
)
FUNCTION_DECL_RE = re.compile(
    r"^(?P<name>[a-z][A-Za-z0-9_@]*)\s*\([^)\n]*\)\s*(?:when\s+.*)?->",
    re.MULTILINE,
)
QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<module>[a-z][A-Za-z0-9_@]*)\:(?P<name>[a-z][A-Za-z0-9_@]*)\s*\("
)
RESERVED_SYMBOL_NAMES = frozenset(
    {
        "after",
        "and",
        "band",
        "begin",
        "bnot",
        "bor",
        "bsl",
        "bsr",
        "bxor",
        "case",
        "catch",
        "cond",
        "div",
        "end",
        "fun",
        "if",
        "let",
        "not",
        "of",
        "or",
        "receive",
        "rem",
        "try",
        "when",
        "xor",
    }
)


def module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix not in {".erl", ".hrl"}:
        return set()
    aliases: set[str] = set()
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    module_match = MODULE_RE.search(text)
    if module_match is not None:
        aliases.add(module_match.group("name"))
    without_suffix_path = str(path.with_suffix(""))
    if without_suffix_path:
        aliases.add(without_suffix_path)
        aliases.add(without_suffix_path.replace("/", "."))
    source_parts = list(path.parts)
    for marker in ("src", "include"):
        if marker not in source_parts:
            continue
        marker_index = source_parts.index(marker)
        module_parts = list(source_parts[marker_index + 1 : -1])
        stem = path.stem
        if stem != "init":
            module_parts.append(stem)
        if module_parts:
            aliases.add("/".join(module_parts))
            aliases.add(".".join(module_parts))
        break
    return {alias for alias in aliases if alias}


def resolve_module(
    import_target: str,
    module_index: dict[str, str],
    *,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = import_target.strip()
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None and direct_match.endswith(".erl"):
        return direct_match
    candidate_keys = [
        normalized_target,
        f"{normalized_target}.erl",
        f"src/{normalized_target}.erl",
        f"apps/{normalized_target}/src/{normalized_target}.erl",
        normalized_target.replace(".", "/"),
        f"{normalized_target.replace('.', '/')}.erl",
        f"src/{normalized_target.replace('.', '/')}.erl",
    ]
    for candidate_key in candidate_keys:
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved.endswith(".erl"):
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            f"{normalized_target}.erl",
            f"src/{normalized_target}.erl",
            f"{normalized_target.replace('.', '/')}.erl",
            f"src/{normalized_target.replace('.', '/')}.erl",
        ],
    )


def resolve_include(
    *,
    current_file: str,
    import_target: str,
    is_lib: bool,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = import_target.strip().replace("\\", "/")
    if not normalized_target:
        return None
    candidate_keys: list[str] = []
    target_path = PurePosixPath(normalized_target)
    if is_lib:
        candidate_keys.extend(
            [
                normalized_target,
                f"apps/{normalized_target}",
                f"deps/{normalized_target}",
                f"lib/{normalized_target}",
            ]
        )
        tail_parts = target_path.parts[-2:]
        if tail_parts:
            candidate_keys.append("/".join(tail_parts))
        candidate_keys.append(f"include/{target_path.name}")
    else:
        current_dir = PurePosixPath(current_file).parent
        relative_base = normalize_repository_relative_path(str(current_dir / normalized_target))
        if relative_base:
            candidate_keys.append(relative_base)
        candidate_keys.extend([normalized_target, f"include/{target_path.name}"])
    for candidate_key in candidate_keys:
        if not candidate_key:
            continue
        resolved = module_index.get(candidate_key)
        if resolved is not None:
            return resolved
    suffixes = [normalized_target, target_path.name]
    if len(target_path.parts) >= 2:
        suffixes.append("/".join(target_path.parts[-2:]))
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes)


def extract_dependencies(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_module: ResolveModule,
    resolve_include: ResolveInclude,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    dependency_keys: set[tuple[str | None, str, str]] = set()
    for match in INCLUDE_RE.finditer(text):
        import_target = str(match.group("target") or "").strip()
        target_file = resolve_include(
            current_file=file_path,
            import_target=import_target,
            is_lib=False,
            module_index=module_index,
        )
        dependency_key = (target_file, import_target, "include")
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
                target_symbol=PurePosixPath(import_target).stem,
                dependency_type="imports",
            )
        )
    for match in INCLUDE_LIB_RE.finditer(text):
        import_target = str(match.group("target") or "").strip()
        target_file = resolve_include(
            current_file=file_path,
            import_target=import_target,
            is_lib=True,
            module_index=module_index,
        )
        dependency_key = (target_file, import_target, "include_lib")
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
                target_symbol=PurePosixPath(import_target).stem,
                dependency_type="imports",
            )
        )
    for match in IMPORT_RE.finditer(text):
        import_target = str(match.group("module") or "").strip()
        target_file = resolve_module(import_target, module_index)
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
                target_symbol=import_target,
                dependency_type="imports",
            )
        )
        import_bindings[import_target] = _ImportedSymbolBinding(
            alias=import_target,
            target_file=target_file,
            target_names=(),
        )
    for match in QUALIFIED_REFERENCE_RE.finditer(text):
        import_target = str(match.group("module") or "").strip()
        target_file = resolve_module(import_target, module_index)
        dependency_key = (target_file, import_target, "qualified")
        if target_file is None or dependency_key in dependency_keys:
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
                target_symbol=str(match.group("name") or "").strip(),
                dependency_type="references",
            )
        )
        import_bindings.setdefault(
            import_target,
            _ImportedSymbolBinding(alias=import_target, target_file=target_file, target_names=()),
        )
    return tuple(dependencies), import_bindings


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_module: ResolveModule,
    resolve_include: ResolveInclude,
) -> tuple[_Dependency, ...]:
    dependencies, _bindings = extract_dependencies(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_module=resolve_module,
        resolve_include=resolve_include,
    )
    return dependencies


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_module: ResolveModule,
    resolve_include: ResolveInclude,
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
    dependencies, _bindings = extract_dependencies(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_module=resolve_module,
        resolve_include=resolve_include,
    )
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    for symbol in symbols:
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for match in QUALIFIED_REFERENCE_RE.finditer(snippet):
            target_module = str(match.group("module") or "").strip()
            target_name = str(match.group("name") or "").strip()
            target_file = resolve_module(target_module, module_index)
            if target_file is None or not target_name:
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
    return (
        symbols,
        dependencies,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )

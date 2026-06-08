from __future__ import annotations

import re
from collections import defaultdict
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

MODULE_RE = re.compile(
    r"^\s*>?\s*module\s+(?P<name>[A-Z][A-Za-z0-9_']*(?:\.[A-Z][A-Za-z0-9_']*)*)\b",
    re.MULTILINE,
)
IMPORT_RE = re.compile(
    r'^\s*>?\s*import\s+(?:{-#\s*SOURCE\s*#-}\s*)?(?:safe\s+)?'
    r'(?P<qualified>qualified\s+)?(?:"[^"]+"\s+)?'
    r'(?P<target>[A-Z][A-Za-z0-9_\']*(?:\.[A-Z][A-Za-z0-9_\']*)*)'
    r'(?:\s+as\s+(?P<alias>[A-Z][A-Za-z0-9_\']*(?:\.[A-Z][A-Za-z0-9_\']*)*))?'
    r'(?P<rest>.*)$',
    re.MULTILINE,
)
TYPE_DECL_RE = re.compile(
    r"^(?P<kind>data|newtype|type|class)\s+(?P<name>[A-Z][A-Za-z0-9_']*)\b"
)
FUNCTION_DECL_RE = re.compile(
    r"^(?P<name>[a-z_][A-Za-z0-9_']*)\b(?:\s+[^=]*)?\s*(?:::|=)"
)
QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Z][A-Za-z0-9_']*(?:\.[A-Z][A-Za-z0-9_']*)*)\.(?P<name>[A-Za-z_][A-Za-z0-9_']*)\b"
)
TYPE_REFERENCE_RE = re.compile(r"\b(?P<name>[A-Z][A-Za-z0-9_']*)\b")
CALL_RE = re.compile(
    r"(?<![.'])\b(?P<name>[a-z_][A-Za-z0-9_']*)\b(?=\s*(?:[$(]|\s+[A-Za-z_(\"']))"
)
RESERVED_SYMBOL_NAMES = frozenset(
    {
        "case",
        "class",
        "data",
        "default",
        "deriving",
        "do",
        "else",
        "foreign",
        "if",
        "import",
        "in",
        "infix",
        "infixl",
        "infixr",
        "instance",
        "let",
        "module",
        "newtype",
        "of",
        "then",
        "type",
        "where",
    }
)


def normalize_source_line(line: str) -> str:
    return re.sub(r"^\s*>\s?", "", line).strip()


def is_top_level_source_line(raw_line: str) -> bool:
    bird_match = re.match(r"^\s*>\s?(?P<body>.*)$", raw_line)
    if bird_match is not None:
        body = str(bird_match.group("body") or "")
        return body == body.lstrip()
    return raw_line == raw_line.lstrip()


def module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix not in {".hs", ".hsc", ".lhs"}:
        return set()
    aliases: set[str] = set()
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    module_match = MODULE_RE.search(text)
    if module_match is not None:
        aliases.add(module_match.group("name"))
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
    if path.stem == "Main":
        aliases.add("Main")
    return {alias for alias in aliases if alias}


def candidate_module_keys(
    import_target: str,
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> tuple[str, ...]:
    normalized_target = import_target.strip()
    if not normalized_target:
        return ()
    module_path = normalized_target.replace(".", "/")
    candidate_keys = [
        normalized_target,
        module_path,
        f"{module_path}.hs",
        f"{module_path}.hsc",
        f"{module_path}.lhs",
        f"src/{module_path}.hs",
        f"src/{module_path}.hsc",
        f"src/{module_path}.lhs",
        f"app/{module_path}.hs",
        f"app/{module_path}.hsc",
        f"app/{module_path}.lhs",
        f"lib/{module_path}.hs",
        f"lib/{module_path}.hsc",
        f"lib/{module_path}.lhs",
    ]
    seen: set[str] = set()
    ordered: list[str] = []
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if normalized_candidate and normalized_candidate not in seen:
            seen.add(normalized_candidate)
            ordered.append(normalized_candidate)
    return tuple(ordered)


def resolve_import(
    import_target: str,
    module_index: dict[str, str],
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> str | None:
    normalized_target = import_target.strip()
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    for candidate_key in candidate_module_keys(
        normalized_target,
        normalize_repository_relative_path=normalize_repository_relative_path,
    ):
        resolved = module_index.get(candidate_key)
        if resolved is not None:
            return resolved
    return None


def extract_imported_names(rest: str) -> tuple[str, ...]:
    normalized_rest = rest.strip()
    if not normalized_rest or normalized_rest.startswith("hiding"):
        return ()
    opening_index = normalized_rest.find("(")
    if opening_index < 0:
        return ()
    depth = 0
    closing_index = -1
    for index in range(opening_index, len(normalized_rest)):
        character = normalized_rest[index]
        if character == "(":
            depth += 1
        elif character == ")":
            depth = max(0, depth - 1)
            if depth == 0:
                closing_index = index
                break
    if closing_index <= opening_index:
        return ()
    body = normalized_rest[opening_index + 1 : closing_index]
    names: list[str] = []
    current: list[str] = []
    depth = 0
    for character in body:
        if character == "," and depth == 0:
            candidate = "".join(current).strip()
            if candidate:
                names.append(candidate)
            current = []
            continue
        if character == "(":
            depth += 1
        elif character == ")":
            depth = max(0, depth - 1)
        current.append(character)
    candidate = "".join(current).strip()
    if candidate:
        names.append(candidate)
    normalized_names: list[str] = []
    for raw_name in names:
        item = raw_name.strip()
        if not item or item == "..":
            continue
        if item.startswith("pattern "):
            item = item.removeprefix("pattern ").strip()
        item = item.split("::", 1)[0].strip()
        item = item.split("(", 1)[0].strip()
        if not item or not re.match(r"^[A-Za-z_][A-Za-z0-9_']*$", item):
            continue
        normalized_names.append(item)
    return tuple(dict.fromkeys(normalized_names))


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: Callable[[str, dict[str, str]], str | None],
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding], tuple[str, ...]]:
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    unqualified_import_targets: set[str] = set()
    for match in IMPORT_RE.finditer(text):
        import_target = match.group("target").strip()
        if not import_target:
            continue
        target_file = resolve_import(import_target, module_index)
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
                target_symbol=import_target.rsplit(".", 1)[-1],
                dependency_type="imports",
            )
        )
        if not match.group("qualified") and target_file is not None:
            unqualified_import_targets.add(target_file)
        if match.group("qualified") or match.group("alias"):
            binding_alias = (match.group("alias") or import_target).strip()
            if binding_alias:
                import_bindings[binding_alias] = _ImportedSymbolBinding(
                    alias=binding_alias,
                    target_file=target_file,
                    target_names=(),
                )
        imported_names = extract_imported_names(str(match.group("rest") or ""))
        if target_file is None:
            continue
        for imported_name in imported_names:
            import_bindings.setdefault(
                imported_name,
                _ImportedSymbolBinding(
                    alias=imported_name,
                    target_file=target_file,
                    target_names=(imported_name,),
                ),
            )
    return tuple(dependencies), import_bindings, tuple(sorted(unqualified_import_targets))


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: Callable[[str, dict[str, str]], str | None],
) -> tuple[_Dependency, ...]:
    dependencies, _import_bindings, _unqualified_import_targets = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
    )
    return dependencies


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: Callable[[str, dict[str, str]], str | None],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_names: set[str] = set()
    lines = text.splitlines()
    for line_no, raw_line in enumerate(lines, start=1):
        if not is_top_level_source_line(raw_line):
            continue
        normalized_line = normalize_source_line(raw_line)
        if not normalized_line or normalized_line.startswith(("--", "{-")):
            continue
        if normalized_line.startswith(("module ", "import ")):
            continue
        symbol_name: str | None = None
        symbol_kind: str | None = None
        type_match = TYPE_DECL_RE.match(normalized_line)
        if type_match is not None:
            symbol_name = type_match.group("name")
            symbol_kind = type_match.group("kind")
        else:
            function_match = FUNCTION_DECL_RE.match(normalized_line)
            if function_match is not None:
                symbol_name = function_match.group("name")
                symbol_kind = "function"
        if (
            symbol_name is None
            or symbol_name in seen_symbol_names
            or symbol_name in RESERVED_SYMBOL_NAMES
        ):
            continue
        seen_symbol_names.add(symbol_name)
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
    symbols_by_name: dict[str, list[_Symbol]] = defaultdict(list)
    for symbol in symbols:
        symbols_by_name[symbol.symbol_name].append(symbol)
    dependencies, import_bindings, unqualified_import_targets = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
    )
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}

    def _record_reference_candidate(
        *,
        source_symbol_id: str,
        target_symbol_id: str | None,
        target_file: str | None,
        target_names: tuple[str, ...],
    ) -> None:
        edge_id = stable_identifier(
            "ref",
            {
                "source_symbol_id": source_symbol_id,
                "target_symbol_id": target_symbol_id,
                "target_file": target_file,
                "target_names": target_names,
                "type": "references_symbol",
            },
        )
        reference_candidates.setdefault(
            edge_id,
            _SymbolReferenceCandidate(
                reference_edge_id=edge_id,
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=target_symbol_id,
                target_file=target_file,
                target_names=target_names,
                reference_type="references_symbol",
            ),
        )

    for symbol in symbols:
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for match in QUALIFIED_REFERENCE_RE.finditer(snippet):
            binding = import_bindings.get(match.group("alias"))
            if binding is None:
                continue
            target_name = match.group("name")
            _record_reference_candidate(
                source_symbol_id=symbol.symbol_id,
                target_symbol_id=None,
                target_file=binding.target_file,
                target_names=(target_name,),
            )
        for match in TYPE_REFERENCE_RE.finditer(snippet):
            target_name = str(match.group("name") or "").strip()
            if not target_name or target_name in RESERVED_SYMBOL_NAMES:
                continue
            for target_symbol in symbols_by_name.get(target_name, ()):
                if target_symbol.symbol_id == symbol.symbol_id:
                    continue
                _record_reference_candidate(
                    source_symbol_id=symbol.symbol_id,
                    target_symbol_id=target_symbol.symbol_id,
                    target_file=file_path,
                    target_names=(target_symbol.symbol_name,),
                )
            for target_file in unqualified_import_targets:
                _record_reference_candidate(
                    source_symbol_id=symbol.symbol_id,
                    target_symbol_id=None,
                    target_file=target_file,
                    target_names=(target_name,),
                )
        for match in CALL_RE.finditer(snippet):
            target_name = str(match.group("name") or "").strip()
            if not target_name or target_name in RESERVED_SYMBOL_NAMES:
                continue
            binding = import_bindings.get(target_name)
            if binding is not None and binding.target_file is not None and binding.target_names:
                _record_reference_candidate(
                    source_symbol_id=symbol.symbol_id,
                    target_symbol_id=None,
                    target_file=binding.target_file,
                    target_names=binding.target_names,
                )
            for target_symbol in symbols_by_name.get(target_name, ()):
                if target_symbol.symbol_id == symbol.symbol_id:
                    continue
                _record_reference_candidate(
                    source_symbol_id=symbol.symbol_id,
                    target_symbol_id=target_symbol.symbol_id,
                    target_file=file_path,
                    target_names=(target_symbol.symbol_name,),
                )
            for target_file in unqualified_import_targets:
                _record_reference_candidate(
                    source_symbol_id=symbol.symbol_id,
                    target_symbol_id=None,
                    target_file=target_file,
                    target_names=(target_name,),
                )
    return (
        symbols,
        dependencies,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )

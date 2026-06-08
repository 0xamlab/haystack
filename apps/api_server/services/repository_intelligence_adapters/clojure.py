from __future__ import annotations

import re
from collections.abc import Callable, Iterable
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

NS_RE = re.compile(
    r"^\s*\(ns\s+(?P<target>[A-Za-z][A-Za-z0-9_.-]*)\b",
    re.MULTILINE,
)
REQUIRE_VECTOR_RE = re.compile(
    r"\[\s*(?P<target>[a-z][A-Za-z0-9_.-]*)(?P<rest>(?:[^\[\]]|\[[^\]]*\])*)\]",
    re.MULTILINE,
)
ALIAS_RE = re.compile(r":as\s+(?P<alias>[A-Za-z][A-Za-z0-9_.-]*)")
REFER_RE = re.compile(
    r":refer(?:-macros)?\s+\[(?P<names>[^\]]+)\]",
    re.MULTILINE,
)
DEF_DECL_RE = re.compile(
    r"^\s*\((?P<kind>defn-|defn|defmacro|defmulti|defmethod|defprotocol|defrecord|deftype|defonce|def)\s+"
    r"(?P<name>[A-Za-z*!_?<>.+-][A-Za-z0-9*!_?<>.+-]*)\b",
    re.MULTILINE,
)
QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z][A-Za-z0-9_.-]*)/(?P<name>[A-Za-z*!_?<>.+-][A-Za-z0-9*!_?<>.+-]*)\b"
)
UNQUALIFIED_REFERENCE_RE = re.compile(
    r"\(\s*(?P<name>[A-Za-z*!_?<>.+-][A-Za-z0-9*!_?<>.+-]*)\b"
)
RESERVED_SYMBOL_NAMES = frozenset(
    {
        "def",
        "defmacro",
        "defmethod",
        "defmulti",
        "defn",
        "defn-",
        "defonce",
        "defprotocol",
        "defrecord",
        "deftype",
        "fn",
        "if",
        "let",
        "loop",
        "ns",
        "quote",
        "recur",
        "set!",
        "throw",
        "try",
        "var",
        "when",
    }
)


def extract_ns_form(text: str) -> str:
    start_match = NS_RE.search(text)
    if start_match is None:
        return ""
    start_index = start_match.start()
    depth = 0
    in_string = False
    escaped = False
    for index in range(start_index, len(text)):
        character = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
            continue
        if character == "(":
            depth += 1
            continue
        if character == ")":
            depth -= 1
            if depth == 0:
                return text[start_index : index + 1]
    return text[start_index:]


def namespace_path(namespace_target: str) -> str:
    normalized_target = namespace_target.strip()
    if not normalized_target:
        return ""
    return "/".join(segment.replace("-", "_") for segment in normalized_target.split("."))


def module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix not in {".clj", ".cljc", ".cljs"}:
        return set()
    aliases: set[str] = set()
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    namespace_match = NS_RE.search(text)
    if namespace_match is not None:
        aliases.add(namespace_match.group("target"))
    source_parts = list(path.parts)
    source_root_prefixes = (
        ("src", "main", "clojure"),
        ("src", "clj"),
        ("src", "cljs"),
        ("src", "cljc"),
        ("src",),
        ("lib",),
    )
    for source_root_parts in source_root_prefixes:
        prefix_length = len(source_root_parts)
        if (
            len(source_parts) <= prefix_length
            or tuple(source_parts[:prefix_length]) != source_root_parts
        ):
            continue
        namespace_parts = list(source_parts[prefix_length:-1])
        namespace_parts.append(path.stem.replace("_", "-"))
        aliases.add(".".join(part.replace("_", "-") for part in namespace_parts if part))
        break
    return {alias for alias in aliases if alias}


def resolve_import(
    import_target: str,
    module_index: dict[str, str],
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = import_target.strip()
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    normalized_namespace_path = namespace_path(normalized_target)
    if not normalized_namespace_path:
        return None
    candidate_keys: list[str] = [normalized_namespace_path]
    for extension in (".clj", ".cljc", ".cljs"):
        candidate_keys.extend(
            (
                f"{normalized_namespace_path}{extension}",
                f"src/{normalized_namespace_path}{extension}",
                f"src/main/clojure/{normalized_namespace_path}{extension}",
                f"src/clj/{normalized_namespace_path}{extension}",
                f"src/cljs/{normalized_namespace_path}{extension}",
                f"src/cljc/{normalized_namespace_path}{extension}",
                f"lib/{normalized_namespace_path}{extension}",
            )
        )
    normalized_candidate_keys = tuple(
        dict.fromkeys(
            normalize_repository_relative_path(candidate_key)
            for candidate_key in candidate_keys
            if normalize_repository_relative_path(candidate_key)
        )
    )
    for candidate_key in normalized_candidate_keys:
        resolved = module_index.get(candidate_key)
        if resolved is not None:
            return resolved
    return resolve_suffix_match(module_index=module_index, suffixes=normalized_candidate_keys)


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: Callable[[str, dict[str, str]], str | None],
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    ns_form = extract_ns_form(text)
    if not ns_form:
        return (), {}
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    ambiguous_bindings: set[str] = set()

    def _register_import_binding(binding: _ImportedSymbolBinding) -> None:
        existing = import_bindings.get(binding.alias)
        if existing is None:
            import_bindings[binding.alias] = binding
            return
        if existing == binding:
            return
        ambiguous_bindings.add(binding.alias)

    for match in REQUIRE_VECTOR_RE.finditer(ns_form):
        import_target = match.group("target").strip()
        if not import_target:
            continue
        rest = match.group("rest") or ""
        if (
            "." not in import_target
            and "-" not in import_target
            and ":as" not in rest
            and ":refer" not in rest
            and module_index.get(import_target) is None
        ):
            continue
        target_file = resolve_import(import_target, module_index)
        dependency_key = (target_file, import_target, "imports")
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
                    target_symbol=import_target.rsplit(".", 1)[-1],
                    dependency_type="imports",
                )
            )
        alias_match = ALIAS_RE.search(rest)
        candidate_aliases = {
            import_target,
            import_target.rsplit(".", 1)[-1],
        }
        if alias_match is not None:
            candidate_aliases.add(alias_match.group("alias"))
        for alias in sorted(
            candidate_alias for candidate_alias in candidate_aliases if candidate_alias
        ):
            _register_import_binding(
                _ImportedSymbolBinding(
                    alias=alias,
                    target_file=target_file,
                    target_names=(),
                )
            )
        for refer_match in REFER_RE.finditer(rest):
            referred_names = re.findall(
                r"[A-Za-z*!_?<>.+-][A-Za-z0-9*!_?<>.+-]*",
                refer_match.group("names"),
            )
            for referred_name in referred_names:
                if referred_name in RESERVED_SYMBOL_NAMES:
                    continue
                _register_import_binding(
                    _ImportedSymbolBinding(
                        alias=referred_name,
                        target_file=target_file,
                        target_names=(referred_name,),
                    )
                )
    for alias in ambiguous_bindings:
        import_bindings.pop(alias, None)
    return tuple(dependencies), import_bindings


def iter_reference_targets(
    snippet: str,
    import_bindings: dict[str, _ImportedSymbolBinding],
) -> Iterable[tuple[_ImportedSymbolBinding, str]]:
    for match in QUALIFIED_REFERENCE_RE.finditer(snippet):
        binding = import_bindings.get(match.group("alias"))
        if binding is None or binding.target_file is None:
            continue
        target_name = match.group("name")
        if not target_name or target_name in RESERVED_SYMBOL_NAMES:
            continue
        yield binding, target_name
    for match in UNQUALIFIED_REFERENCE_RE.finditer(snippet):
        binding = import_bindings.get(match.group("name"))
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
    lines = text.splitlines()
    symbol_entries: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(lines, start=1):
        match = DEF_DECL_RE.match(raw_line)
        if match is None:
            continue
        symbol_name = match.group("name")
        if not symbol_name or symbol_name in RESERVED_SYMBOL_NAMES:
            continue
        raw_kind = match.group("kind")
        symbol_kind = {
            "def": "variable",
            "defn": "function",
            "defn-": "function",
            "defonce": "variable",
            "defmacro": "macro",
            "defmulti": "function",
            "defmethod": "function",
            "defprotocol": "protocol",
            "defrecord": "record",
            "deftype": "type",
        }.get(raw_kind, "symbol")
        symbol_entries.append(
            {
                "symbol_id": stable_identifier(
                    "symbol",
                    {"file_path": file_path, "name": symbol_name, "line": line_number},
                ),
                "symbol_name": symbol_name,
                "symbol_kind": symbol_kind,
                "start_line": line_number,
                "end_line": line_number,
                "signature": raw_line.strip(),
            }
        )
    if not symbol_entries:
        return []
    final_line = len(lines)
    for index, entry in enumerate(symbol_entries):
        next_start_line = (
            int(symbol_entries[index + 1]["start_line"])
            if index + 1 < len(symbol_entries)
            else final_line + 1
        )
        entry["end_line"] = max(int(entry["start_line"]), next_start_line - 1)
    return symbol_entries


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: Callable[[str, dict[str, str]], str | None],
) -> tuple[_Dependency, ...]:
    dependencies, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
    )
    dependency_candidates = list(dependencies)
    seen_keys = {
        (dependency.target_file, dependency.target_symbol, dependency.dependency_type)
        for dependency in dependency_candidates
    }
    for binding, target_name in iter_reference_targets(text, import_bindings):
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
    resolve_import: Callable[[str, dict[str, str]], str | None],
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
    dependencies, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
    )
    lines = text.splitlines()
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    for symbol in symbols:
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for binding, target_name in iter_reference_targets(snippet, import_bindings):
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

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable, Sequence
from pathlib import PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str | None]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]
ResolveInclude = Callable[..., str | None]

INCLUDE_RE = re.compile(
    r'^\s*#\s*include\s*[<"](?P<target>[^">]+)[">]',
    re.MULTILINE,
)
ATTRIBUTE_RE = re.compile(
    r"__attribute__\s*\(\([\s\S]{0,200}?\)\)|\[\[[\s\S]{0,200}?\]\]"
)
TYPE_DECL_RE = re.compile(
    r"^\s*(?:template\s*<[^>{;]+>\s*)?(?:class|struct|union|enum(?:\s+class)?)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
FUNCTION_DECL_RE = re.compile(
    r"^\s*(?P<prefix>(?:(?:template\s*<[^>{;]+>\s*)?"
    r"(?:(?:inline|static|constexpr|consteval|constinit|virtual|explicit|friend|extern|typename|auto|signed|unsigned|short|long|mutable)\s+)*"
    r"(?:[A-Za-z_~][A-Za-z0-9_:<>,*&\[\]\s]+?\s+)))"
    r"(?P<name>[A-Za-z_~][A-Za-z0-9_:]*)\s*\([^;{}]*\)\s*"
    r"(?:const\b|noexcept\b(?:\([^)]*\))?|override\b|final\b|->[^;{]+|requires\b[^{;]+|\s)*"
    r"[;{]\s*$",
    re.MULTILINE,
)
SCOPED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)::(?P<name>[A-Za-z_~][A-Za-z0-9_]*)\b"
)
CALL_RE = re.compile(r"\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")

NON_OPERATIONAL_REFERENCE_NAMES = frozenset(
    {
        "assert",
        "case",
        "catch",
        "co_await",
        "co_return",
        "co_yield",
        "constexpr",
        "decltype",
        "delete",
        "do",
        "else",
        "for",
        "if",
        "new",
        "noexcept",
        "offsetof",
        "reinterpret_cast",
        "return",
        "sizeof",
        "static_assert",
        "switch",
        "throw",
        "typeid",
        "va_arg",
        "va_copy",
        "va_end",
        "va_start",
        "while",
    }
)
DECLARATION_PREFIX_KEYWORDS = frozenset(
    {
        "break",
        "case",
        "catch",
        "co_return",
        "continue",
        "delete",
        "do",
        "else",
        "for",
        "goto",
        "if",
        "new",
        "return",
        "sizeof",
        "static_assert",
        "switch",
        "throw",
        "typeid",
        "while",
    }
)


def _replace_with_spaces(value: str) -> str:
    return "".join("\n" if character == "\n" else " " for character in value)


def candidate_module_keys(
    base_path: str,
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> tuple[str, ...]:
    normalized_base = normalize_repository_relative_path(base_path)
    if not normalized_base:
        return ()
    suffix = PurePosixPath(normalized_base).suffix.lower()
    if suffix in {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".ipp", ".tpp"}:
        seen: set[str] = set()
        ordered: list[str] = []
        for candidate in (
            normalized_base,
            normalize_repository_relative_path(str(PurePosixPath(normalized_base).with_suffix(""))),
        ):
            if candidate and candidate not in seen:
                seen.add(candidate)
                ordered.append(candidate)
        return tuple(ordered)
    candidates = [normalized_base]
    candidates.extend(
        f"{normalized_base}{suffix}"
        for suffix in (".h", ".hh", ".hpp", ".hxx", ".ipp", ".tpp", ".c", ".cc", ".cpp", ".cxx")
    )
    return tuple(dict.fromkeys(candidates))


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
    candidate_keys: list[str] = []
    current_dir = normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    relative_base = normalize_repository_relative_path(
        str(PurePosixPath(current_dir) / normalized_target)
    )
    if relative_base:
        candidate_keys.extend(
            candidate_module_keys(
                relative_base,
                normalize_repository_relative_path=normalize_repository_relative_path,
            )
        )
    direct_match = module_index.get(normalized_target)
    if direct_match is not None and direct_match != current_file:
        return direct_match
    if not normalized_target.startswith(".") and not normalized_target.startswith("/"):
        candidate_keys.extend(
            candidate_module_keys(
                normalized_target,
                normalize_repository_relative_path=normalize_repository_relative_path,
            )
        )
        for prefix in ("include", "src", "source", "sources", "lib"):
            candidate_keys.extend(
                candidate_module_keys(
                    f"{prefix}/{normalized_target}",
                    normalize_repository_relative_path=normalize_repository_relative_path,
                )
            )
    for candidate_key in candidate_keys:
        if not candidate_key:
            continue
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved != current_file:
            return resolved
    resolved = resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            normalized_target,
            PurePosixPath(normalized_target).name,
            str(PurePosixPath(normalized_target).with_suffix("")),
        ],
    )
    if resolved is not None and resolved != current_file:
        return resolved
    return None


def strip_comments(text: str) -> str:
    return re.sub(
        r"//[^\n]*|/\*.*?\*/",
        lambda match: _replace_with_spaces(match.group(0)),
        text,
        flags=re.MULTILINE | re.DOTALL,
    )


def strip_attributes(text: str) -> str:
    return ATTRIBUTE_RE.sub(lambda match: _replace_with_spaces(match.group(0)), text)


def normalize_symbol_name(symbol_name: str) -> str:
    normalized_name = symbol_name.strip()
    if not normalized_name:
        return ""
    return normalized_name.rsplit("::", 1)[-1]


def is_macro_like_symbol_name(symbol_name: str) -> bool:
    normalized_name = normalize_symbol_name(symbol_name)
    if not normalized_name:
        return False
    if normalized_name.startswith("__"):
        return True
    letters = [character for character in normalized_name if character.isalpha()]
    return "_" in normalized_name and bool(letters) and all(
        character.isupper() for character in letters
    )


def is_operational_reference_name(target_name: str) -> bool:
    normalized_name = normalize_symbol_name(target_name)
    if not normalized_name:
        return False
    if is_macro_like_symbol_name(normalized_name):
        return False
    return normalized_name not in NON_OPERATIONAL_REFERENCE_NAMES


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_include: ResolveInclude,
) -> tuple[_Dependency, ...]:
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str]] = set()
    for match in INCLUDE_RE.finditer(text):
        import_target = str(match.group("target") or "").strip()
        if not import_target:
            continue
        target_file = resolve_include(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
        )
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
                target_symbol=PurePosixPath(import_target).name,
                dependency_type="imports",
            )
        )
    return tuple(dependencies)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_include: ResolveInclude,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    sanitized_text = strip_attributes(strip_comments(text))
    lines = sanitized_text.splitlines()
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, int, str]] = set()

    for regex, symbol_kind in (
        (TYPE_DECL_RE, "type"),
        (FUNCTION_DECL_RE, "function"),
    ):
        for match in regex.finditer(sanitized_text):
            normalized_name = normalize_symbol_name(str(match.group("name") or ""))
            if not normalized_name or is_macro_like_symbol_name(normalized_name):
                continue
            line_no = sanitized_text.count("\n", 0, match.start()) + 1
            line_text = lines[line_no - 1].strip() if line_no - 1 < len(lines) else ""
            if symbol_kind == "function":
                prefix = str(match.groupdict().get("prefix") or "")
                if "=" in prefix:
                    continue
                prefix_tokens = {
                    token
                    for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", prefix)
                    if token
                }
                if prefix_tokens & DECLARATION_PREFIX_KEYWORDS:
                    continue
                if line_text.startswith(
                    (
                        "return ",
                        "co_return ",
                        "throw ",
                        "if ",
                        "for ",
                        "while ",
                        "switch ",
                        "catch ",
                        "static_assert",
                    )
                ):
                    continue
            symbol_key = (normalized_name, line_no, symbol_kind)
            if symbol_key in seen_symbol_keys:
                continue
            seen_symbol_keys.add(symbol_key)
            symbol_entries.append(
                {
                    "symbol_id": stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "name": normalized_name,
                            "line": line_no,
                            "kind": symbol_kind,
                        },
                    ),
                    "symbol_name": normalized_name,
                    "symbol_kind": symbol_kind,
                    "start_line": line_no,
                    "end_line": line_no,
                    "signature": normalized_name,
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
    dependencies = parse_dependencies_only(
        file_path,
        sanitized_text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_include=resolve_include,
    )
    symbols_by_name: defaultdict[str, list[_Symbol]] = defaultdict(list)
    for symbol in symbols:
        symbols_by_name[symbol.symbol_name].append(symbol)
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}

    def _add_reference_candidate(
        *,
        source_symbol: _Symbol,
        target_file: str | None,
        target_names: tuple[str, ...],
    ) -> None:
        if target_file is None:
            return
        normalized_names = tuple(
            normalized_name
            for normalized_name in (normalize_symbol_name(name) for name in target_names)
            if normalized_name and is_operational_reference_name(normalized_name)
        )
        if not normalized_names:
            return
        edge_id = stable_identifier(
            "ref",
            {
                "source_symbol_id": source_symbol.symbol_id,
                "target_file": target_file,
                "target_names": normalized_names,
                "type": "references_symbol",
            },
        )
        reference_candidates.setdefault(
            edge_id,
            _SymbolReferenceCandidate(
                reference_edge_id=edge_id,
                source_symbol_id=source_symbol.symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=target_file,
                target_names=normalized_names,
                reference_type="references_symbol",
            ),
        )

    for symbol in symbols:
        snippet = "\n".join(lines[max(symbol.start_line - 1, 0) : min(symbol.end_line, len(lines))])
        for match in SCOPED_REFERENCE_RE.finditer(snippet):
            target_name = normalize_symbol_name(str(match.group("name") or ""))
            if not is_operational_reference_name(target_name):
                continue
            for target_symbol in symbols_by_name.get(target_name, ()):
                if target_symbol.symbol_id == symbol.symbol_id:
                    continue
                edge_id = stable_identifier(
                    "ref",
                    {
                        "source_symbol_id": symbol.symbol_id,
                        "target_symbol_id": target_symbol.symbol_id,
                        "type": "references_symbol",
                    },
                )
                reference_candidates.setdefault(
                    edge_id,
                    _SymbolReferenceCandidate(
                        reference_edge_id=edge_id,
                        source_symbol_id=symbol.symbol_id,
                        source_file=file_path,
                        target_symbol_id=target_symbol.symbol_id,
                        target_file=file_path,
                        target_names=(target_symbol.symbol_name,),
                        reference_type="references_symbol",
                    ),
                )
            for dependency in dependencies:
                _add_reference_candidate(
                    source_symbol=symbol,
                    target_file=dependency.target_file,
                    target_names=(target_name,),
                )
        for match in CALL_RE.finditer(snippet):
            target_name = normalize_symbol_name(str(match.group("name") or ""))
            if not is_operational_reference_name(target_name):
                continue
            if match.start() > 0 and snippet[match.start() - 1] in {".", ":", ">"}:
                continue
            for target_symbol in symbols_by_name.get(target_name, ()):
                if target_symbol.symbol_id == symbol.symbol_id:
                    continue
                edge_id = stable_identifier(
                    "ref",
                    {
                        "source_symbol_id": symbol.symbol_id,
                        "target_symbol_id": target_symbol.symbol_id,
                        "type": "references_symbol",
                    },
                )
                reference_candidates.setdefault(
                    edge_id,
                    _SymbolReferenceCandidate(
                        reference_edge_id=edge_id,
                        source_symbol_id=symbol.symbol_id,
                        source_file=file_path,
                        target_symbol_id=target_symbol.symbol_id,
                        target_file=file_path,
                        target_names=(target_symbol.symbol_name,),
                        reference_type="references_symbol",
                    ),
                )
            for dependency in dependencies:
                _add_reference_candidate(
                    source_symbol=symbol,
                    target_file=dependency.target_file,
                    target_names=(target_name,),
                )

    return (
        symbols,
        dependencies,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )

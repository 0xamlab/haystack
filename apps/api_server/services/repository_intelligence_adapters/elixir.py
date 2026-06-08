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
ResolveSuffixMatch = Callable[..., str | None]

IMPORT_RE = re.compile(
    r"^\s*(?P<kind>alias|import|use|require)\s+(?P<target>[A-Z][A-Za-z0-9_\.]+)(?P<rest>[^\n]*)",
    re.MULTILINE,
)
GROUP_IMPORT_RE = re.compile(
    r"^\s*(?P<kind>alias|import|use|require)\s+(?P<prefix>[A-Z][A-Za-z0-9_\.]+)\.\{(?P<names>[A-Za-z0-9_,\s]+)\}(?P<rest>[^\n]*)",
    re.MULTILINE,
)
AS_ALIAS_RE = re.compile(r"\bas:\s*(?P<alias>[A-Z][A-Za-z0-9_\.]+)")
MODULE_DECL_RE = re.compile(
    r"^\s*def(?:module|protocol|impl|exception)\s+(?P<name>[A-Z][A-Za-z0-9_\.]*)\b",
    re.MULTILINE,
)
FUNCTION_DECL_RE = re.compile(
    r"^\s*def(?:p|macro|macrop|guard|guardp|delegate)?\s+(?P<name>[a-z_][A-Za-z0-9_!?]*)\b",
    re.MULTILINE,
)
QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Z][A-Za-z0-9_]*(?:\.[A-Z][A-Za-z0-9_]*)*)\.(?P<name>[a-z_][A-Za-z0-9_!?]*)\s*\("
)
CALL_RE = re.compile(r"\b(?P<name>[a-z_][A-Za-z0-9_!?]*)\s*\(")
RESERVED_SYMBOL_NAMES = frozenset(
    {
        "__call__",
        "__dir__",
        "__env__",
        "__module__",
        "alias",
        "after",
        "and",
        "case",
        "catch",
        "cond",
        "def",
        "defdelegate",
        "defexception",
        "defguard",
        "defguardp",
        "defimpl",
        "defmacro",
        "defmacrop",
        "defmodule",
        "defoverridable",
        "defp",
        "defprotocol",
        "defstruct",
        "do",
        "else",
        "end",
        "false",
        "fn",
        "for",
        "if",
        "import",
        "in",
        "nil",
        "not",
        "or",
        "quote",
        "raise",
        "receive",
        "require",
        "rescue",
        "reraise",
        "super",
        "throw",
        "true",
        "try",
        "unless",
        "unquote",
        "unquote_splicing",
        "use",
        "when",
        "with",
    }
)


def _camelize_identifier(value: str) -> str:
    normalized_value = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    if not normalized_value:
        return ""
    return "".join(piece.capitalize() for piece in normalized_value.split("_") if piece)


def module_path_variants(import_target: str) -> tuple[str, ...]:
    normalized_target = import_target.strip()
    if not normalized_target:
        return ()
    snake_segments = [
        re.sub(r"(?<!^)(?=[A-Z])", "_", segment).lower()
        for segment in normalized_target.split(".")
        if segment
    ]
    if not snake_segments:
        return ()

    partitions: list[tuple[str, ...]] = []

    def _walk(index: int, groups: list[str]) -> None:
        if index >= len(snake_segments):
            partitions.append(tuple(groups))
            return
        next_segment = snake_segments[index]
        _walk(index + 1, [*groups, next_segment])
        _walk(index + 1, [*groups[:-1], f"{groups[-1]}_{next_segment}"])

    _walk(1, [snake_segments[0]])

    ordered_variants: list[str] = []
    seen_variants: set[str] = set()
    for groups in sorted(
        partitions,
        key=lambda value: (
            len(value[-1].split("_")) != 1,
            len(snake_segments) - len(value),
            "/".join(value),
        ),
    ):
        candidate = "/".join(groups)
        if candidate in seen_variants:
            continue
        seen_variants.add(candidate)
        ordered_variants.append(candidate)
    return tuple(ordered_variants)


def module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix not in {".ex", ".exs"}:
        return set()
    aliases: set[str] = set()
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    for match in MODULE_DECL_RE.finditer(text):
        module_name = str(match.group("name") or "").strip()
        if not module_name:
            continue
        aliases.add(module_name)
        aliases.add(module_name.rsplit(".", 1)[-1])
    source_parts = list(path.parts)
    marker_index = next(
        (index for index, part in enumerate(source_parts[:-1]) if part in {"lib", "test"}),
        None,
    )
    relevant_parts = source_parts[marker_index + 1 :] if marker_index is not None else source_parts
    camelized_parts: list[str] = []
    for raw_part in relevant_parts:
        stem = PurePosixPath(raw_part).stem if raw_part == source_parts[-1] else raw_part
        pieces = [
            _camelize_identifier(piece)
            for piece in re.split(r"[^A-Za-z0-9_]+", stem)
            if piece
        ]
        camelized_parts.extend(piece for piece in pieces if piece)
    if camelized_parts:
        aliases.add(".".join(camelized_parts))
        aliases.add(camelized_parts[-1])
    without_suffix_path = str(path.with_suffix(""))
    if without_suffix_path:
        aliases.add(without_suffix_path)
        aliases.add(without_suffix_path.replace("/", "."))
    return {alias for alias in aliases if alias}


def resolve_import(
    import_target: str,
    module_index: dict[str, str],
    *,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = import_target.strip()
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    lowered_path = normalized_target.replace(".", "/").lower()
    path_variants = module_path_variants(normalized_target)
    candidate_keys = [
        lowered_path,
        f"{lowered_path}.ex",
        f"{lowered_path}.exs",
        f"lib/{lowered_path}",
        f"lib/{lowered_path}.ex",
        f"lib/{lowered_path}.exs",
    ]
    for path_variant in path_variants:
        candidate_keys.extend(
            (
                path_variant,
                f"{path_variant}.ex",
                f"{path_variant}.exs",
                f"lib/{path_variant}",
                f"lib/{path_variant}.ex",
                f"lib/{path_variant}.exs",
            )
        )
    for candidate_key in candidate_keys:
        resolved = module_index.get(candidate_key)
        if resolved is not None:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            f"{lowered_path}.ex",
            f"{lowered_path}.exs",
            lowered_path,
            *(
                suffix
                for path_variant in path_variants
                for suffix in (f"{path_variant}.ex", f"{path_variant}.exs", path_variant)
            ),
        ],
    )


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    dependency_keys: set[tuple[str | None, str]] = set()
    for match in GROUP_IMPORT_RE.finditer(text):
        prefix = str(match.group("prefix") or "").strip()
        if not prefix:
            continue
        for raw_name in str(match.group("names") or "").split(","):
            alias_name = raw_name.strip()
            if not alias_name:
                continue
            import_target = f"{prefix}.{alias_name}"
            target_file = resolve_import(
                import_target,
                module_index,
                resolve_suffix_match=resolve_suffix_match,
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
                    target_symbol=alias_name,
                    dependency_type="imports",
                )
            )
            for binding_alias in sorted({alias_name, import_target}):
                import_bindings.setdefault(
                    binding_alias,
                    _ImportedSymbolBinding(
                        alias=binding_alias,
                        target_file=target_file,
                        target_names=(),
                    ),
                )
    for match in IMPORT_RE.finditer(text):
        import_target = str(match.group("target") or "").strip()
        if not import_target:
            continue
        target_file = resolve_import(
            import_target,
            module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (target_file, import_target)
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
        alias_candidates = {import_target, import_target.rsplit(".", 1)[-1]}
        alias_match = AS_ALIAS_RE.search(str(match.group("rest") or ""))
        if alias_match is not None:
            explicit_alias = str(alias_match.group("alias") or "").strip()
            if explicit_alias:
                alias_candidates.add(explicit_alias)
                alias_candidates.add(explicit_alias.rsplit(".", 1)[-1])
        for binding_alias in sorted(alias for alias in alias_candidates if alias):
            import_bindings.setdefault(
                binding_alias,
                _ImportedSymbolBinding(
                    alias=binding_alias,
                    target_file=target_file,
                    target_names=(),
                ),
            )
    return tuple(dependencies), import_bindings


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    dependencies, _import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
    )
    return dependencies


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
    lines = text.splitlines()
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, int, str]] = set()
    for regex, symbol_kind in (
        (MODULE_DECL_RE, "type"),
        (FUNCTION_DECL_RE, "function"),
    ):
        for match in regex.finditer(text):
            raw_name = str(match.group("name") or "").strip()
            symbol_name = raw_name.rsplit(".", 1)[-1] if symbol_kind == "type" else raw_name
            if not symbol_name or symbol_name in RESERVED_SYMBOL_NAMES:
                continue
            line_no = text.count("\n", 0, match.start()) + 1
            symbol_key = (symbol_name, line_no, symbol_kind)
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
                    "signature": raw_name,
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
        resolve_suffix_match=resolve_suffix_match,
    )
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    symbol_ids_by_name = {symbol.symbol_name: symbol.symbol_id for symbol in symbols}
    for symbol in symbols:
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for match in QUALIFIED_REFERENCE_RE.finditer(snippet):
            alias = str(match.group("alias") or "").strip()
            target_name = str(match.group("name") or "").strip()
            binding = import_bindings.get(alias)
            if (
                binding is None
                or binding.target_file is None
                or not target_name
                or target_name in RESERVED_SYMBOL_NAMES
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
            if (
                not target_name
                or target_name in RESERVED_SYMBOL_NAMES
                or symbol_ids_by_name.get(target_name) in {None, symbol.symbol_id}
            ):
                continue
            if match.start() > 0 and snippet[match.start() - 1] in {".", ":"}:
                continue
            target_symbol_id = symbol_ids_by_name[target_name]
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

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
ResolveModule = Callable[[str, dict[str, str]], str | None]

OPEN_RE = re.compile(
    r"^\s*open!?\s+(?P<target>[A-Z][A-Za-z0-9_']*(?:\.[A-Z][A-Za-z0-9_']*)*)",
    re.MULTILINE,
)
INCLUDE_RE = re.compile(
    r"^\s*include\s+(?P<target>[A-Z][A-Za-z0-9_']*(?:\.[A-Z][A-Za-z0-9_']*)*)",
    re.MULTILINE,
)
MODULE_ALIAS_RE = re.compile(
    r"^\s*module\s+(?P<name>[A-Z][A-Za-z0-9_']*)\s*=\s*(?P<target>[A-Z][A-Za-z0-9_']*(?:\.[A-Z][A-Za-z0-9_']*)*)",
    re.MULTILINE,
)
LET_DECL_RE = re.compile(
    r"^\s*let(?:\s+rec)?\s+(?P<name>[a-z_][A-Za-z0-9_']*)\b",
    re.MULTILINE,
)
TYPE_DECL_RE = re.compile(
    r"^\s*type\s+(?P<name>[a-z_][A-Za-z0-9_']*)\b",
    re.MULTILINE,
)
MODULE_DECL_RE = re.compile(
    r"^\s*module(?:\s+type)?\s+(?P<name>[A-Z][A-Za-z0-9_']*)\b",
    re.MULTILINE,
)
QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Z][A-Za-z0-9_']*(?:\.[A-Z][A-Za-z0-9_']*)*)\.(?P<name>[a-z_][A-Za-z0-9_']*)\b"
)
RESERVED_SYMBOL_NAMES = frozenset(
    {
        "and",
        "as",
        "assert",
        "begin",
        "class",
        "constraint",
        "do",
        "done",
        "downto",
        "else",
        "end",
        "exception",
        "external",
        "false",
        "for",
        "fun",
        "function",
        "functor",
        "if",
        "in",
        "include",
        "inherit",
        "initializer",
        "land",
        "lazy",
        "let",
        "lor",
        "lsl",
        "lsr",
        "lxor",
        "match",
        "method",
        "mod",
        "module",
        "mutable",
        "new",
        "nonrec",
        "object",
        "of",
        "open",
        "or",
        "private",
        "rec",
        "sig",
        "struct",
        "then",
        "to",
        "true",
        "try",
        "type",
        "val",
        "virtual",
        "when",
        "while",
        "with",
    }
)


def module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix not in {".ml", ".mli"}:
        return set()
    aliases: set[str] = set()
    stem = path.stem
    if stem:
        aliases.add(stem[0].upper() + stem[1:])
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    for match in MODULE_DECL_RE.finditer(text):
        module_name = str(match.group("name") or "").strip()
        if module_name:
            aliases.add(module_name)
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
    module_tail = normalized_target.rsplit(".", 1)[-1]
    candidate_keys = [
        normalized_target,
        module_tail,
        module_tail.replace("__", "_"),
        normalized_target.replace(".", "/"),
        f"{normalized_target}.ml",
        f"{normalized_target}.mli",
        f"{normalized_target.replace('.', '/')}.ml",
        f"{normalized_target.replace('.', '/')}.mli",
    ]
    for candidate_key in candidate_keys:
        if not candidate_key:
            continue
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved.endswith((".ml", ".mli")):
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            f"{module_tail}.ml",
            f"{module_tail}.mli",
            f"/{module_tail}.ml",
            f"/{module_tail}.mli",
        ],
    )


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_module: ResolveModule,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}

    def _register_binding(
        *,
        import_target: str,
        line_offset: int,
        dependency_kind: str,
        binding_aliases: tuple[str, ...] = (),
    ) -> None:
        normalized_target = import_target.strip()
        if not normalized_target:
            return
        target_file = resolve_module(normalized_target, module_index)
        dependency_key = (target_file, normalized_target, dependency_kind)
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": normalized_target,
                            "kind": dependency_kind,
                            "line": line_offset,
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=normalized_target.rsplit(".", 1)[-1],
                    dependency_type="imports",
                )
            )
        alias_candidates = {
            normalized_target,
            normalized_target.rsplit(".", 1)[-1],
            *binding_aliases,
        }
        for binding_alias in sorted(alias for alias in alias_candidates if alias):
            import_bindings.setdefault(
                binding_alias,
                _ImportedSymbolBinding(
                    alias=binding_alias,
                    target_file=target_file,
                    target_names=(),
                ),
            )

    for regex, dependency_kind in ((OPEN_RE, "open"), (INCLUDE_RE, "include")):
        for match in regex.finditer(text):
            _register_binding(
                import_target=str(match.group("target") or "").strip(),
                line_offset=match.start(),
                dependency_kind=dependency_kind,
            )
    for match in MODULE_ALIAS_RE.finditer(text):
        _register_binding(
            import_target=str(match.group("target") or "").strip(),
            line_offset=match.start(),
            dependency_kind="module_alias",
            binding_aliases=(str(match.group("name") or "").strip(),),
        )
    for match in QUALIFIED_REFERENCE_RE.finditer(text):
        _register_binding(
            import_target=str(match.group("alias") or "").strip(),
            line_offset=match.start(),
            dependency_kind="qualified_reference",
        )
    return tuple(dependencies), import_bindings


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_module: ResolveModule,
) -> tuple[_Dependency, ...]:
    dependencies, _bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_module=resolve_module,
    )
    return dependencies


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_module: ResolveModule,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    lines = text.splitlines()
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_names: set[str] = set()
    for regex, symbol_kind in (
        (LET_DECL_RE, "value"),
        (TYPE_DECL_RE, "type"),
        (MODULE_DECL_RE, "module"),
    ):
        for match in regex.finditer(text):
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
        resolve_module=resolve_module,
    )
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    for symbol in symbols:
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for match in QUALIFIED_REFERENCE_RE.finditer(snippet):
            target_alias = str(match.group("alias") or "").strip()
            target_name = str(match.group("name") or "").strip()
            if not target_alias or not target_name or target_name in RESERVED_SYMBOL_NAMES:
                continue
            binding = import_bindings.get(target_alias)
            target_file = (
                binding.target_file
                if binding is not None
                else resolve_module(target_alias, module_index)
            )
            if target_file is None:
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

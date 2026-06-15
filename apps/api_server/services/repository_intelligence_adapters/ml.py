from __future__ import annotations

from bisect import bisect_right
from functools import lru_cache
import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

_KNOWN_ML_SUFFIXES = (".sml", ".sig", ".fun")
_ML_SOURCE_ROOTS = (
    "src",
    "lib",
    "basis",
    "compiler",
    "mlsource",
    "source",
    "pluto",
    "example",
    "examples",
    "bootstrap",
)
RESERVED_SYMBOL_NAMES = frozenset(
    {
        "abstype",
        "and",
        "as",
        "case",
        "datatype",
        "do",
        "else",
        "end",
        "eqtype",
        "exception",
        "fn",
        "fun",
        "functor",
        "handle",
        "if",
        "in",
        "include",
        "infix",
        "infixr",
        "let",
        "local",
        "nonfix",
        "of",
        "op",
        "open",
        "orelse",
        "raise",
        "rec",
        "sharing",
        "sig",
        "signature",
        "struct",
        "structure",
        "then",
        "type",
        "val",
        "where",
        "with",
        "withtype",
    }
)
_MODULE_NAME_RE = r"[A-Z][A-Za-z0-9_']*(?:\.[A-Z][A-Za-z0-9_']*)*"
MODULE_DECL_RE = re.compile(
    r"^\s*(?P<kind>structure|signature|functor)\s+(?P<name>[A-Z][A-Za-z0-9_']*)\b",
    re.MULTILINE,
)
MODULE_ALIAS_RE = re.compile(
    rf"^\s*structure\s+(?P<name>[A-Z][A-Za-z0-9_']*)\s*=\s*(?P<target>{_MODULE_NAME_RE})\b",
    re.MULTILINE,
)
OPEN_RE = re.compile(r"^\s*open\s+(?P<body>.+)$", re.MULTILINE)
FUN_DECL_RE = re.compile(
    r"^\s*fun\b(?:\s+rec\b)?\s+(?P<name>[a-z_][A-Za-z0-9_']*)\b",
    re.MULTILINE,
)
VAL_DECL_RE = re.compile(
    r"^\s*val\b(?:\s+rec\b)?\s+(?P<name>[a-z_][A-Za-z0-9_']*)\b",
    re.MULTILINE,
)
TYPE_DECL_RE = re.compile(
    r"^\s*(?:datatype|abstype|type|eqtype|exception)\s+(?P<name>[A-Za-z_][A-Za-z0-9_']*)\b",
    re.MULTILINE,
)
QUALIFIED_REFERENCE_RE = re.compile(
    rf"\b(?P<alias>{_MODULE_NAME_RE})\.(?P<name>[A-Za-z_][A-Za-z0-9_']*)\b"
)
UNQUALIFIED_CALL_RE = re.compile(
    r"(?<!\.)\b(?P<name>[a-z_][A-Za-z0-9_']*)\b\s*(?=\()"
)


@lru_cache(maxsize=1024)
def strip_comments(text: str) -> str:
    chars: list[str] = []
    index = 0
    depth = 0
    while index < len(text):
        next_two = text[index : index + 2]
        if depth > 0:
            if next_two == "(*":
                depth += 1
                chars.extend((" ", " "))
                index += 2
                continue
            if next_two == "*)":
                depth = max(0, depth - 1)
                chars.extend((" ", " "))
                index += 2
                continue
            chars.append("\n" if text[index] == "\n" else " ")
            index += 1
            continue
        if next_two == "(*":
            depth = 1
            chars.extend((" ", " "))
            index += 2
            continue
        chars.append(text[index])
        index += 1
    return "".join(chars)


@lru_cache(maxsize=1024)
def _line_start_offsets(text: str) -> tuple[int, ...]:
    offsets = [0]
    start = 0
    while True:
        newline_index = text.find("\n", start)
        if newline_index < 0:
            break
        offsets.append(newline_index + 1)
        start = newline_index + 1
    return tuple(offsets)


def _line_number(text: str, index: int) -> int:
    bounded_index = max(0, min(index, len(text)))
    return bisect_right(_line_start_offsets(text), bounded_index)


def normalize_target(raw_target: str) -> str:
    return str(raw_target or "").strip().strip("();,")


def normalize_symbol_name(raw_name: str) -> str:
    return str(raw_name or "").strip().strip("();,")


def declared_module_names(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[str, ...]:
    names: list[str] = []
    seen: set[str] = set()
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    for match in MODULE_DECL_RE.finditer(stripped_text):
        name = normalize_symbol_name(str(match.group("name") or ""))
        canonical_name = name.lower()
        if not name or canonical_name in seen:
            continue
        seen.add(canonical_name)
        names.append(name)
    return tuple(names)


def _path_aliases(path: PurePosixPath) -> set[str]:
    without_suffix = str(path.with_suffix("")).lower()
    aliases = {
        str(path).lower(),
        without_suffix,
        without_suffix.replace("/", "."),
        path.stem.lower(),
    }
    source_parts = list(path.parts)
    for source_root in _ML_SOURCE_ROOTS:
        if source_root not in source_parts:
            continue
        root_index = source_parts.index(source_root)
        module_parts = list(source_parts[root_index + 1 :])
        if not module_parts:
            continue
        module_parts[-1] = PurePosixPath(module_parts[-1]).stem.lower()
        slash_alias = "/".join(part for part in module_parts if part)
        dot_alias = ".".join(part for part in module_parts if part)
        if slash_alias:
            aliases.add(slash_alias)
        if dot_alias:
            aliases.add(dot_alias)
        break
    return {alias for alias in aliases if alias and alias not in {".", "/"}}


def _open_targets(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[str, ...]:
    targets: list[str] = []
    seen: set[str] = set()
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    for match in OPEN_RE.finditer(stripped_text):
        body = str(match.group("body") or "")
        for target_match in re.finditer(_MODULE_NAME_RE, body):
            target = normalize_target(str(target_match.group(0) or ""))
            canonical_target = target.lower()
            if not target or canonical_target in seen:
                continue
            seen.add(canonical_target)
            targets.append(target)
    return tuple(targets)


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
    stripped_text: str | None = None,
    module_names: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, str, int]] = set()
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    module_names = (
        tuple(module_names)
        if module_names is not None
        else declared_module_names(text, stripped_text=stripped_text)
    )
    file_alias = PurePosixPath(file_path).stem.lower()
    final_line = max(1, stripped_text.count("\n") + 1) if stripped_text else 1
    for regex, symbol_kind in (
        (MODULE_DECL_RE, "module"),
        (FUN_DECL_RE, "function"),
        (VAL_DECL_RE, "value"),
        (TYPE_DECL_RE, "type"),
    ):
        for match in regex.finditer(stripped_text):
            symbol_name = normalize_symbol_name(str(match.group("name") or ""))
            canonical_symbol_name = symbol_name.lower()
            if not symbol_name or canonical_symbol_name in RESERVED_SYMBOL_NAMES:
                continue
            line_no = _line_number(stripped_text, match.start())
            symbol_key = (symbol_kind, canonical_symbol_name, line_no)
            if symbol_key in seen_symbol_keys:
                continue
            seen_symbol_keys.add(symbol_key)
            qualified_names = {canonical_symbol_name}
            if symbol_kind != "module":
                for module_name in module_names:
                    qualified_names.add(f"{module_name.lower()}.{canonical_symbol_name}")
                if not module_names and file_alias and file_alias != canonical_symbol_name:
                    qualified_names.add(f"{file_alias}.{canonical_symbol_name}")
            symbol_entries.append(
                {
                    "symbol_id": stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "name": symbol_name,
                            "kind": symbol_kind,
                            "line": line_no,
                        },
                    ),
                    "symbol_name": symbol_name,
                    "symbol_kind": symbol_kind,
                    "start_line": line_no,
                    "end_line": line_no,
                    "signature": str(match.group(0) or "").strip(),
                    "qualified_names": tuple(sorted(qualified_names)),
                }
            )
    symbol_entries.sort(key=lambda entry: (int(entry["start_line"]), str(entry["symbol_name"])))
    for index, entry in enumerate(symbol_entries):
        if index + 1 < len(symbol_entries):
            entry["end_line"] = max(
                int(symbol_entries[index + 1]["start_line"]) - 1,
                int(entry["start_line"]),
            )
        else:
            entry["end_line"] = final_line
    return symbol_entries


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
    include_symbol_aliases: bool = True,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_ML_SUFFIXES:
        return set()
    aliases = set(_path_aliases(path))
    source_text = text
    if source_text is None:
        try:
            source_text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return aliases
    assert source_text is not None
    stripped_text = strip_comments(source_text)
    module_names = declared_module_names(source_text, stripped_text=stripped_text)
    for module_name in module_names:
        aliases.add(module_name.lower())
    if not include_symbol_aliases:
        return {alias for alias in aliases if alias}
    for symbol_entry in collect_symbol_entries(
        source_text,
        file_path=file_path,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
        module_names=module_names,
    ):
        aliases.update(str(alias).lower() for alias in symbol_entry["qualified_names"] if alias)
    return {alias for alias in aliases if alias}


def _candidate_import_keys(import_target: str) -> tuple[str, ...]:
    normalized_target = normalize_target(import_target)
    if not normalized_target:
        return ()
    canonical_target = normalized_target.lower()
    module_path = canonical_target.replace(".", "/")
    module_tail = canonical_target.rsplit(".", 1)[-1]
    candidate_keys = [
        canonical_target,
        module_tail,
        module_path,
        f"{module_path}.sml",
        f"{module_path}.sig",
        f"{module_path}.fun",
        f"src/{module_path}.sml",
        f"src/{module_path}.sig",
        f"src/{module_path}.fun",
        f"lib/{module_path}.sml",
        f"lib/{module_path}.sig",
        f"lib/{module_path}.fun",
        f"basis/{module_path}.sml",
        f"basis/{module_path}.sig",
        f"basis/{module_path}.fun",
        f"compiler/{module_path}.sml",
        f"compiler/{module_path}.sig",
        f"compiler/{module_path}.fun",
        f"{module_tail}.sml",
        f"{module_tail}.sig",
        f"{module_tail}.fun",
    ]
    seen: set[str] = set()
    ordered: list[str] = []
    for candidate_key in candidate_keys:
        normalized_candidate = candidate_key.strip().lower()
        if not normalized_candidate or normalized_candidate in seen:
            continue
        seen.add(normalized_candidate)
        ordered.append(normalized_candidate)
    return tuple(ordered)


def resolve_import(
    import_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    candidate_keys = _candidate_import_keys(import_target)
    if not candidate_keys:
        return None
    for candidate_key in candidate_keys:
        direct_match = module_index.get(candidate_key)
        if direct_match is not None:
            return direct_match
    return resolve_suffix_match(module_index=module_index, suffixes=candidate_keys)


def _extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: Callable[[str, dict[str, str]], str | None],
    stripped_text: str | None = None,
    opened_targets: Sequence[str] | None = None,
) -> tuple[tuple[dict[str, Any], ...], dict[str, dict[str, Any]]]:
    dependency_specs: list[dict[str, Any]] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    import_bindings: dict[str, dict[str, Any]] = {}
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    opened_targets = (
        tuple(opened_targets)
        if opened_targets is not None
        else _open_targets(text, stripped_text=stripped_text)
    )

    for target in opened_targets:
        canonical_target = target.lower()
        target_tail = canonical_target.rsplit(".", 1)[-1]
        target_file = resolve_import(target, module_index)
        dependency_key = (target_file, target_tail, "open")
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependency_specs.append(
                {
                    "dependency_edge_id": stable_identifier(
                        "dep",
                        {"file_path": file_path, "target": canonical_target, "kind": "open"},
                    ),
                    "source_file": file_path,
                    "target_file": target_file,
                    "target_symbol": target_tail,
                    "dependency_type": "open",
                }
            )
        import_bindings.setdefault(
            target_tail,
            {
                "alias": target_tail,
                "target_file": target_file,
                "target_names": (),
            },
        )

    for match in MODULE_ALIAS_RE.finditer(stripped_text):
        alias = normalize_symbol_name(str(match.group("name") or ""))
        target = normalize_target(str(match.group("target") or ""))
        if not alias or not target:
            continue
        alias_key = alias.lower()
        target_file = resolve_import(target, module_index)
        target_tail = target.lower().rsplit(".", 1)[-1]
        dependency_key = (target_file, target_tail, "module_alias")
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependency_specs.append(
                {
                    "dependency_edge_id": stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": target.lower(),
                            "alias": alias_key,
                            "kind": "module_alias",
                        },
                    ),
                    "source_file": file_path,
                    "target_file": target_file,
                    "target_symbol": target_tail,
                    "dependency_type": "module_alias",
                }
            )
        import_bindings.setdefault(
            alias_key,
            {
                "alias": alias_key,
                "target_file": target_file,
                "target_names": (),
            },
        )

    for match in QUALIFIED_REFERENCE_RE.finditer(stripped_text):
        alias = normalize_target(str(match.group("alias") or "")).lower()
        if not alias or alias in RESERVED_SYMBOL_NAMES:
            continue
        binding = import_bindings.get(alias)
        target_file = (
            binding["target_file"]
            if binding is not None
            else resolve_import(alias, module_index)
        )
        dependency_key = (target_file, alias.rsplit(".", 1)[-1], "references")
        if target_file is None or target_file == file_path or dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        dependency_specs.append(
            {
                "dependency_edge_id": stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": alias,
                        "kind": "qualified_reference",
                        "offset": match.start(),
                    },
                ),
                "source_file": file_path,
                "target_file": target_file,
                "target_symbol": alias.rsplit(".", 1)[-1],
                "dependency_type": "references",
            }
        )
    return tuple(dependency_specs), import_bindings


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: Callable[[str, dict[str, str]], str | None],
) -> tuple[dict[str, Any], ...]:
    stripped_text = strip_comments(text)
    dependency_specs, _import_bindings = _extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
        stripped_text=stripped_text,
        opened_targets=_open_targets(text, stripped_text=stripped_text),
    )
    return dependency_specs


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: Callable[[str, dict[str, str]], str | None],
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    stripped_text = strip_comments(text)
    module_names = declared_module_names(text, stripped_text=stripped_text)
    opened_targets = _open_targets(text, stripped_text=stripped_text)
    symbol_entries = collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
        module_names=module_names,
    )
    dependency_specs, import_bindings = _extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
        stripped_text=stripped_text,
        opened_targets=opened_targets,
    )
    reference_specs: dict[str, dict[str, Any]] = {}
    lines = stripped_text.splitlines()
    single_import_binding = (
        next(iter(import_bindings.values())) if len(import_bindings) == 1 else None
    )
    for symbol_entry in symbol_entries:
        snippet = "\n".join(
            lines[int(symbol_entry["start_line"]) - 1 : int(symbol_entry["end_line"])]
        )
        symbol_name_key = str(symbol_entry["symbol_name"]).lower()
        for match in QUALIFIED_REFERENCE_RE.finditer(snippet):
            alias = normalize_target(str(match.group("alias") or "")).lower()
            target_name = normalize_symbol_name(str(match.group("name") or ""))
            if (
                not alias
                or not target_name
                or alias in RESERVED_SYMBOL_NAMES
                or target_name.lower() in RESERVED_SYMBOL_NAMES
            ):
                continue
            binding = import_bindings.get(alias)
            target_file = (
                binding["target_file"]
                if binding is not None
                else resolve_import(alias, module_index)
            )
            if target_file is None or target_file == file_path:
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol_entry["symbol_id"],
                    "target_file": target_file,
                    "target_names": (target_name,),
                    "type": "references_symbol",
                },
            )
            reference_specs.setdefault(
                edge_id,
                {
                    "reference_edge_id": edge_id,
                    "source_symbol_id": symbol_entry["symbol_id"],
                    "source_file": file_path,
                    "target_symbol_id": None,
                    "target_file": target_file,
                    "target_names": (target_name,),
                    "reference_type": "references_symbol",
                },
            )
        if single_import_binding is None:
            continue
        target_file = single_import_binding["target_file"]
        if target_file is None or target_file == file_path:
            continue
        for match in UNQUALIFIED_CALL_RE.finditer(snippet):
            target_name = normalize_symbol_name(str(match.group("name") or ""))
            target_name_key = target_name.lower()
            if (
                not target_name
                or target_name_key in RESERVED_SYMBOL_NAMES
                or target_name_key == symbol_name_key
            ):
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol_entry["symbol_id"],
                    "target_file": target_file,
                    "target_names": (target_name,),
                    "type": "references_symbol",
                },
            )
            reference_specs.setdefault(
                edge_id,
                {
                    "reference_edge_id": edge_id,
                    "source_symbol_id": symbol_entry["symbol_id"],
                    "source_file": file_path,
                    "target_symbol_id": None,
                    "target_file": target_file,
                    "target_names": (target_name,),
                    "reference_type": "references_symbol",
                },
            )
    return (
        tuple(symbol_entries),
        dependency_specs,
        tuple(reference_specs[key] for key in sorted(reference_specs)),
    )

from __future__ import annotations

from bisect import bisect_right
from functools import lru_cache
import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from . import sql as sql_adapter

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

RESERVED_SYMBOL_NAMES = frozenset(
    set(sql_adapter.RESERVED_SYMBOL_NAMES)
    | {
        "begin",
        "body",
        "cursor",
        "declare",
        "elsif",
        "exception",
        "execute",
        "immediate",
        "is",
        "loop",
        "package",
        "pragma",
        "raise",
        "record",
        "return",
        "trigger",
    }
)
IDENTIFIER_SEGMENT_PATTERN = sql_adapter.IDENTIFIER_SEGMENT_PATTERN
COMPOUND_IDENTIFIER_PATTERN = sql_adapter.COMPOUND_IDENTIFIER_PATTERN
CREATE_DECL_RE = re.compile(
    r"\bcreate\s+(?:or\s+replace\s+)?(?:editionable\s+|noneditionable\s+)?"
    r"(?P<kind>package(?:\s+body)?|procedure|function|trigger|type|materialized\s+view|table|view)\s+"
    r"(?P<name>"
    + COMPOUND_IDENTIFIER_PATTERN
    + r")",
    re.IGNORECASE,
)
ROUTINE_DECL_RE = re.compile(
    r"^\s*(?P<kind>procedure|function)\s+(?P<name>" + IDENTIFIER_SEGMENT_PATTERN + r")\b",
    re.IGNORECASE | re.MULTILINE,
)
RELATION_REFERENCE_RE = re.compile(
    r"\b(?:from|join|insert\s+into|update|delete\s+from|merge\s+into|truncate\s+table|"
    r"alter\s+table|references)\s+(?:only\s+)?(?P<name>"
    + COMPOUND_IDENTIFIER_PATTERN
    + r")",
    re.IGNORECASE,
)
CALL_RE = re.compile(
    r"\b(?:call|exec|execute)\s+(?P<name>" + COMPOUND_IDENTIFIER_PATTERN + r")\s*\(",
    re.IGNORECASE,
)
UNQUALIFIED_CALL_RE = re.compile(
    r"(?<![.$A-Za-z0-9_])(?P<name>" + IDENTIFIER_SEGMENT_PATTERN + r")\s*\(",
    re.IGNORECASE,
)
QUALIFIED_CALL_RE = re.compile(
    r"\b(?P<name>"
    + IDENTIFIER_SEGMENT_PATTERN
    + r"(?:\s*\.\s*"
    + IDENTIFIER_SEGMENT_PATTERN
    + r"){1,2})\s*(?:\(|;)",
    re.IGNORECASE,
)
FALLBACK_SYMBOL_RE = sql_adapter.FALLBACK_SYMBOL_RE
_KNOWN_PLSQL_SUFFIXES = (".pkb", ".pks", ".pls", ".prc", ".fnc", ".trg")
_KNOWN_PLSQL_IMPORT_SUFFIXES = (".pks", ".pkb", ".pls", ".prc", ".fnc", ".trg")


def strip_comments(text: str) -> str:
    return sql_adapter.strip_comments(text)


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


def _line_number(text: str, offset: int) -> int:
    bounded_offset = max(0, min(offset, len(text)))
    return bisect_right(_line_start_offsets(text), bounded_offset)


def normalize_identifier(raw_name: str) -> str:
    return sql_adapter.normalize_identifier(raw_name)


def symbol_name_parts(symbol_name: str) -> tuple[str, str]:
    return sql_adapter.symbol_name_parts(symbol_name)


def _preferred_resolution_suffixes(
    normalized_target: str,
    leaf_name: str,
    *,
    suffix_order: Sequence[str],
) -> list[str]:
    namespace_path = normalized_target.replace(".", "/")
    suffixes: list[str] = []
    for suffix in (*suffix_order, ".sql"):
        for base in (normalized_target, namespace_path, leaf_name):
            if base:
                suffixes.append(f"{base}{suffix}")
    return suffixes


def _cached_import_resolver(
    resolve_import: Callable[[str, dict[str, str]], str | None],
) -> Callable[[str, dict[str, str]], str | None]:
    cache: dict[str, str | None] = {}

    def _resolve(import_target: str, module_index: dict[str, str]) -> str | None:
        if import_target in cache:
            return cache[import_target]
        resolved = resolve_import(import_target, module_index)
        cache[import_target] = resolved
        return resolved

    return _resolve


def _cached_target_resolver(
    resolve_target: Callable[[str, dict[str, str]], str | None],
) -> Callable[[str, dict[str, str]], str | None]:
    cache: dict[str, str | None] = {}

    def _resolve(reference_target: str, module_index: dict[str, str]) -> str | None:
        if reference_target in cache:
            return cache[reference_target]
        resolved = resolve_target(reference_target, module_index)
        cache[reference_target] = resolved
        return resolved

    return _resolve


def resolve_import(
    import_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target, leaf_name = symbol_name_parts(import_target)
    if not normalized_target:
        return None
    resolved = resolve_suffix_match(
        module_index=module_index,
        suffixes=_preferred_resolution_suffixes(
            normalized_target,
            leaf_name,
            suffix_order=_KNOWN_PLSQL_IMPORT_SUFFIXES,
        ),
    )
    if resolved is not None:
        return resolved
    for candidate in (normalized_target, leaf_name):
        if not candidate:
            continue
        direct_match = module_index.get(candidate)
        if direct_match is not None:
            return direct_match
    return None


def resolve_target(
    reference_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target, leaf_name = symbol_name_parts(reference_target)
    if not normalized_target:
        return None
    for candidate in (normalized_target, leaf_name):
        if not candidate:
            continue
        direct_match = module_index.get(candidate)
        if direct_match is not None:
            return direct_match
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=_preferred_resolution_suffixes(
            normalized_target,
            leaf_name,
            suffix_order=_KNOWN_PLSQL_SUFFIXES,
        ),
    )


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
    stripped_text: str | None = None,
) -> list[dict[str, Any]]:
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, str, int]] = set()
    create_declarations: dict[int, list[tuple[str, str, str, str]]] = {}
    current_package = ""
    final_line = max(1, stripped_text.count("\n") + 1) if stripped_text else 1

    for match in CREATE_DECL_RE.finditer(stripped_text):
        normalized_name, leaf_name = symbol_name_parts(str(match.group("name") or ""))
        if (
            not normalized_name
            or not leaf_name
            or leaf_name in RESERVED_SYMBOL_NAMES
        ):
            continue
        raw_kind = re.sub(r"\s+", " ", str(match.group("kind") or "").strip().lower())
        symbol_kind = (
            "module"
            if raw_kind.startswith("package")
            else "function"
            if raw_kind in {"function", "procedure", "trigger"}
            else "type"
        )
        line_no = _line_number(stripped_text, match.start())
        signature = str(match.group(0) or "").strip()
        create_declarations.setdefault(line_no, []).append(
            (raw_kind, normalized_name, leaf_name, signature)
        )

    for line_no, raw_line in enumerate(stripped_text.splitlines(), start=1):
        for raw_kind, normalized_name, leaf_name, signature in create_declarations.get(line_no, []):
            qualified_names = {leaf_name, normalized_name}
            if raw_kind == "package body":
                qualified_names.add(f"{normalized_name}.body")
                current_package = normalized_name
            elif raw_kind == "package":
                current_package = normalized_name
            symbol_kind = (
                "module"
                if raw_kind.startswith("package")
                else "function"
                if raw_kind in {"function", "procedure", "trigger"}
                else "type"
            )
            symbol_key = (symbol_kind, normalized_name, line_no)
            if symbol_key in seen_symbol_keys:
                continue
            seen_symbol_keys.add(symbol_key)
            symbol_entries.append(
                {
                    "symbol_id": stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "name": leaf_name,
                            "kind": symbol_kind,
                            "line": line_no,
                        },
                    ),
                    "symbol_name": leaf_name,
                    "symbol_kind": symbol_kind,
                    "start_line": line_no,
                    "end_line": final_line,
                    "signature": signature,
                    "qualified_names": tuple(sorted(qualified_names)),
                }
            )

        routine_match = ROUTINE_DECL_RE.match(raw_line.strip())
        if routine_match is None:
            continue
        normalized_name, leaf_name = symbol_name_parts(str(routine_match.group("name") or ""))
        if (
            not normalized_name
            or not leaf_name
            or leaf_name in RESERVED_SYMBOL_NAMES
        ):
            continue
        qualified_names = {leaf_name, normalized_name}
        if current_package:
            qualified_names.add(f"{current_package}.{leaf_name}")
        symbol_key = ("function", normalized_name, line_no)
        if symbol_key in seen_symbol_keys:
            continue
        seen_symbol_keys.add(symbol_key)
        symbol_entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": leaf_name,
                        "kind": "function",
                        "line": line_no,
                    },
                ),
                "symbol_name": leaf_name,
                "symbol_kind": "function",
                "start_line": line_no,
                "end_line": final_line,
                "signature": raw_line.strip(),
                "qualified_names": tuple(sorted(qualified_names)),
            }
        )

    if not symbol_entries:
        fallback_name = PurePosixPath(file_path).stem.lower()
        fallback_text = stripped_text.lower()
        if FALLBACK_SYMBOL_RE.fullmatch(fallback_name) and any(
            token in fallback_text
            for token in ("declare", "begin", "create ", "select ", "insert ", "update ")
        ):
            symbol_entries.append(
                {
                    "symbol_id": stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "name": fallback_name,
                            "kind": "type",
                            "line": 1,
                        },
                    ),
                    "symbol_name": fallback_name,
                    "symbol_kind": "type",
                    "start_line": 1,
                    "end_line": final_line,
                    "signature": fallback_name,
                    "qualified_names": (fallback_name,),
                }
            )

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
) -> set[str]:
    path = PurePosixPath(file_path)
    suffix_lower = path.suffix.lower()
    if suffix_lower not in _KNOWN_PLSQL_SUFFIXES:
        return set()

    has_sibling_spec = suffix_lower == ".pkb" and (root_path / path.with_suffix(".pks")).is_file()
    aliases = {file_path.lower()}
    if not has_sibling_spec:
        without_suffix_path = str(path.with_suffix("")).lower()
        aliases.update(
            {
                path.stem.lower(),
                without_suffix_path,
                without_suffix_path.replace("/", "."),
            }
        )

    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {alias for alias in aliases if alias and alias not in {".", "/"}}

    symbol_entries = collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    )
    if not has_sibling_spec:
        for symbol_entry in symbol_entries:
            aliases.update(
                str(alias).lower()
                for alias in symbol_entry["qualified_names"]
                if alias
            )
    if suffix_lower == ".pkb":
        package_names = [
            str(entry["symbol_name"]).lower()
            for entry in symbol_entries
            if str(entry["symbol_kind"]) == "module"
        ]
        for package_name in package_names:
            aliases.add(f"{package_name}.body")
            for symbol_entry in symbol_entries:
                if str(symbol_entry["symbol_kind"]) == "module":
                    continue
                symbol_name = str(symbol_entry["symbol_name"]).lower()
                if symbol_name:
                    aliases.add(f"{package_name}.body.{symbol_name}")
    return {alias for alias in aliases if alias and alias not in {".", "/"}}


def iter_package_body_imports(text: str) -> tuple[tuple[int, str], ...]:
    stripped_text = strip_comments(text)
    return _iter_package_body_imports_from_stripped_text(stripped_text)


def _iter_package_body_imports_from_stripped_text(
    stripped_text: str,
) -> tuple[tuple[int, str], ...]:
    imports: list[tuple[int, str]] = []
    for match in CREATE_DECL_RE.finditer(stripped_text):
        raw_kind = re.sub(r"\s+", " ", str(match.group("kind") or "").strip().lower())
        if raw_kind != "package body":
            continue
        normalized_name, _leaf_name = symbol_name_parts(str(match.group("name") or ""))
        if not normalized_name:
            continue
        line_no = _line_number(stripped_text, match.start())
        imports.append((line_no, normalized_name))
    return tuple(imports)


def iter_reference_targets(text: str) -> tuple[tuple[int, str, str], ...]:
    stripped_text = strip_comments(text)
    return _iter_reference_targets_from_stripped_text(stripped_text)


def _iter_reference_targets_from_stripped_text(
    stripped_text: str,
) -> tuple[tuple[int, str, str], ...]:
    targets: list[tuple[int, str, str]] = []
    for regex, kind in (
        (RELATION_REFERENCE_RE, "relation"),
        (CALL_RE, "call"),
        (UNQUALIFIED_CALL_RE, "call"),
        (QUALIFIED_CALL_RE, "qualified_call"),
    ):
        for match in regex.finditer(stripped_text):
            target_name = str(match.group("name") or "").strip()
            if not target_name:
                continue
            line_no = _line_number(stripped_text, match.start())
            targets.append((line_no, kind, target_name))
    return tuple(dict.fromkeys(targets))


def _parse_dependencies_only_from_stripped_text(
    file_path: str,
    stripped_text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: Callable[[str, dict[str, str]], str | None],
    resolve_target: Callable[[str, dict[str, str]], str | None],
) -> tuple[dict[str, Any], ...]:
    dependency_entries: list[dict[str, Any]] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    for line_no, import_target in _iter_package_body_imports_from_stripped_text(stripped_text):
        normalized_target, leaf_name = symbol_name_parts(import_target)
        if not normalized_target or not leaf_name:
            continue
        target_file = resolve_import(import_target, module_index)
        dependency_key = (target_file, leaf_name, "imports")
        if (
            target_file is None
            or target_file == file_path
            or dependency_key in dependency_keys
        ):
            continue
        dependency_keys.add(dependency_key)
        dependency_entries.append(
            {
                "dependency_edge_id": stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": normalized_target,
                        "line": line_no,
                        "kind": "package_body_import",
                    },
                ),
                "source_file": file_path,
                "target_file": target_file,
                "target_symbol": leaf_name,
                "dependency_type": "imports",
            }
        )
    for line_no, reference_kind, raw_target in _iter_reference_targets_from_stripped_text(
        stripped_text
    ):
        normalized_target, leaf_name = symbol_name_parts(raw_target)
        if (
            not normalized_target
            or not leaf_name
            or leaf_name in RESERVED_SYMBOL_NAMES
        ):
            continue
        target_file = resolve_target(raw_target, module_index)
        dependency_key = (target_file, leaf_name, "references")
        if (
            target_file is None
            or target_file == file_path
            or dependency_key in dependency_keys
        ):
            continue
        dependency_keys.add(dependency_key)
        dependency_entries.append(
            {
                "dependency_edge_id": stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": normalized_target,
                        "line": line_no,
                        "kind": reference_kind,
                    },
                ),
                "source_file": file_path,
                "target_file": target_file,
                "target_symbol": leaf_name,
                "dependency_type": "references",
            }
        )
    return tuple(dependency_entries)


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: Callable[[str, dict[str, str]], str | None],
    resolve_target: Callable[[str, dict[str, str]], str | None],
) -> tuple[dict[str, Any], ...]:
    stripped_text = strip_comments(text)
    return _parse_dependencies_only_from_stripped_text(
        file_path,
        stripped_text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=_cached_import_resolver(resolve_import),
        resolve_target=_cached_target_resolver(resolve_target),
    )


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: Callable[[str, dict[str, str]], str | None],
    resolve_target: Callable[[str, dict[str, str]], str | None],
) -> tuple[
    list[dict[str, Any]],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
]:
    stripped_text = strip_comments(text)
    resolve_import_cached = _cached_import_resolver(resolve_import)
    resolve_target_cached = _cached_target_resolver(resolve_target)
    symbol_entries = collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    )
    reference_candidates: dict[str, dict[str, Any]] = {}
    # Collect references from the full stripped text ONCE (reusing the cached line-offset
    # table) and bucket each by line into the symbol whose [start_line, end_line] span
    # contains it — instead of re-deriving line offsets on a per-symbol snippet substring,
    # which created a second _line_start_offsets cache key per symbol. The line number is
    # only used to attribute the reference to its enclosing symbol.
    references_by_line = _iter_reference_targets_from_stripped_text(stripped_text)
    for symbol_entry in symbol_entries:
        start_line = int(symbol_entry["start_line"])
        end_line = int(symbol_entry["end_line"])
        symbol_name = str(symbol_entry["symbol_name"]).lower()
        symbol_id = str(symbol_entry["symbol_id"])
        for reference_line, reference_kind, raw_target in references_by_line:
            if reference_line < start_line or reference_line > end_line:
                continue
            normalized_target, leaf_name = symbol_name_parts(raw_target)
            if (
                not normalized_target
                or not leaf_name
                or leaf_name in RESERVED_SYMBOL_NAMES
                or leaf_name == symbol_name
            ):
                continue
            target_file = resolve_target_cached(raw_target, module_index)
            if target_file is None or target_file == file_path:
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol_id,
                    "target_file": target_file,
                    "target_names": (leaf_name,),
                    "type": "references_symbol",
                    "kind": reference_kind,
                },
            )
            reference_candidates.setdefault(
                edge_id,
                {
                    "reference_edge_id": edge_id,
                    "source_symbol_id": symbol_id,
                    "source_file": file_path,
                    "target_symbol_id": None,
                    "target_file": target_file,
                    "target_names": (leaf_name,),
                    "reference_type": "references_symbol",
                },
            )
    return (
        symbol_entries,
        _parse_dependencies_only_from_stripped_text(
            file_path,
            stripped_text,
            module_index,
            stable_identifier=stable_identifier,
            resolve_import=resolve_import_cached,
            resolve_target=resolve_target_cached,
        ),
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )

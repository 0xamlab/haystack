from __future__ import annotations

from bisect import bisect_right
import re
from collections.abc import Callable, Sequence
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

RESERVED_SYMBOL_NAMES = frozenset(
    {
        "abort",
        "and",
        "array",
        "by",
        "call",
        "cards",
        "data",
        "delete",
        "display",
        "do",
        "else",
        "end",
        "filename",
        "format",
        "from",
        "goto",
        "if",
        "in",
        "include",
        "input",
        "keep",
        "length",
        "libname",
        "macro",
        "mend",
        "merge",
        "not",
        "or",
        "options",
        "output",
        "proc",
        "put",
        "quit",
        "rename",
        "retain",
        "return",
        "run",
        "select",
        "set",
        "stop",
        "then",
        "update",
        "until",
        "value",
        "var",
        "when",
        "where",
        "while",
    }
)
RESERVED_MACRO_CALL_NAMES = frozenset(
    {
        "bquote",
        "cmpres",
        "do",
        "else",
        "end",
        "eval",
        "global",
        "goto",
        "if",
        "include",
        "index",
        "length",
        "let",
        "local",
        "lowcase",
        "macro",
        "mend",
        "nrquote",
        "nrstr",
        "put",
        "qscan",
        "quote",
        "return",
        "scan",
        "str",
        "substr",
        "superq",
        "symexist",
        "sysfunc",
        "sysget",
        "then",
        "unquote",
        "upcase",
    }
)
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
COMPOUND_IDENTIFIER_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$"
)
BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
STATEMENT_COMMENT_RE = re.compile(r"^\s*\*[^;\n]*;", re.MULTILINE)
MACRO_DECL_RE = re.compile(
    r"^\s*%macro\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE | re.IGNORECASE,
)
FCMP_ROUTINE_DECL_RE = re.compile(
    r"^\s*(?P<kind>function|subroutine)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE | re.IGNORECASE,
)
DATA_DECL_RE = re.compile(
    r"^\s*data\s+(?P<name>[A-Za-z_][A-Za-z0-9_\.]*)\b",
    re.MULTILINE | re.IGNORECASE,
)
INCLUDE_RE = re.compile(
    r"^\s*%include\s+(?:(?P<quote>['\"])(?P<quoted_target>[^'\"]+)(?P=quote)|"
    r"(?P<raw_target>[^;\n]+))\s*;",
    re.MULTILINE | re.IGNORECASE,
)
MACRO_CALL_RE = re.compile(
    r"(?<![A-Za-z0-9_])%(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b(?=\s*(?:\(|;))",
    re.IGNORECASE,
)
_KNOWN_SAS_SUFFIXES = (".sas",)


def _replace_preserving_newlines(match: re.Match[str]) -> str:
    return "".join("\n" if character == "\n" else " " for character in match.group(0))


@lru_cache(maxsize=256)
def strip_comments(text: str) -> str:
    without_block_comments = BLOCK_COMMENT_RE.sub(_replace_preserving_newlines, text)
    return STATEMENT_COMMENT_RE.sub(_replace_preserving_newlines, without_block_comments)


def normalize_identifier(raw_name: str) -> str:
    return raw_name.strip().strip("%").strip().lower()


def normalize_target(raw_target: str) -> str:
    normalized_target = raw_target.strip().strip("\"'")
    normalized_target = normalized_target.replace("\\", "/")
    return normalized_target.strip()


def _normalize_repository_relative_path(value: str) -> str:
    raw_parts = PurePosixPath(str(value).replace("\\", "/")).parts
    normalized_parts: list[str] = []
    for part in raw_parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if normalized_parts:
                normalized_parts.pop()
            continue
        normalized_parts.append(part)
    return "/".join(normalized_parts)


@lru_cache(maxsize=256)
def _line_start_offsets(text: str) -> tuple[int, ...]:
    offsets = [0]
    for index, character in enumerate(text):
        if character == "\n":
            offsets.append(index + 1)
    return tuple(offsets)


def _line_number(text: str, offset: int) -> int:
    bounded_offset = max(0, min(offset, len(text)))
    return bisect_right(_line_start_offsets(text), bounded_offset)


@lru_cache(maxsize=256)
def _collect_symbol_metadata(
    stripped_text: str,
) -> tuple[tuple[str, str, int, str, tuple[str, ...]], ...]:
    symbol_metadata: list[tuple[str, str, int, str, tuple[str, ...]]] = []
    seen_symbol_keys: set[tuple[str, str, int]] = set()

    for regex, symbol_kind in (
        (MACRO_DECL_RE, "function"),
        (FCMP_ROUTINE_DECL_RE, "function"),
        (DATA_DECL_RE, "type"),
    ):
        for match in regex.finditer(stripped_text):
            raw_name = str(match.group("name") or "")
            normalized_name = normalize_identifier(raw_name)
            if not normalized_name:
                continue
            leaf_name = normalized_name.rsplit(".", 1)[-1]
            if (
                not leaf_name
                or leaf_name in RESERVED_SYMBOL_NAMES
                or not (
                    IDENTIFIER_RE.fullmatch(leaf_name)
                    if "." not in normalized_name
                    else COMPOUND_IDENTIFIER_RE.fullmatch(normalized_name)
                )
            ):
                continue
            line_no = _line_number(stripped_text, match.start())
            symbol_key = (symbol_kind, normalized_name, line_no)
            if symbol_key in seen_symbol_keys:
                continue
            seen_symbol_keys.add(symbol_key)
            qualified_names = (normalized_name, leaf_name) if (
                symbol_kind == "type" and "." in normalized_name
            ) else (leaf_name,)
            symbol_metadata.append(
                (
                    symbol_kind,
                    leaf_name,
                    line_no,
                    str(match.group(0) or "").strip(),
                    tuple(sorted(set(qualified_names))),
                )
            )
    return tuple(symbol_metadata)


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
    stripped_text: str | None = None,
) -> list[dict[str, Any]]:
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    symbol_entries: list[dict[str, Any]] = []
    final_line = len(stripped_text.splitlines()) if stripped_text else 1

    for symbol_kind, leaf_name, line_no, signature, qualified_names in (
        _collect_symbol_metadata(stripped_text)
    ):
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
                "qualified_names": qualified_names,
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
    text: str | None = None,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_SAS_SUFFIXES:
        return set()

    aliases = {
        file_path.lower(),
        path.stem.lower(),
    }
    without_suffix_path = str(path.with_suffix("")).lower()
    aliases.add(without_suffix_path)
    aliases.add(without_suffix_path.replace("/", "."))

    if text is None:
        try:
            text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return {alias for alias in aliases if alias and alias not in {".", "/"}}
    stripped_text = strip_comments(text)

    for symbol_entry in collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    ):
        aliases.update(
            str(alias).lower() for alias in symbol_entry["qualified_names"] if alias
        )
    return {alias for alias in aliases if alias and alias not in {".", "/"}}


def iter_include_targets(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[int, str], ...]:
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    return _iter_include_targets_cached(stripped_text)


@lru_cache(maxsize=256)
def _iter_include_targets_cached(stripped_text: str) -> tuple[tuple[int, str], ...]:
    targets: list[tuple[int, str]] = []
    seen_targets: set[tuple[int, str]] = set()
    for match in INCLUDE_RE.finditer(stripped_text):
        raw_target = str(match.group("quoted_target") or match.group("raw_target") or "")
        normalized_target = normalize_target(raw_target)
        if not normalized_target:
            continue
        line_no = _line_number(stripped_text, match.start())
        target_key = (line_no, normalized_target.lower())
        if target_key in seen_targets:
            continue
        seen_targets.add(target_key)
        targets.append((line_no, normalized_target))
    return tuple(targets)


def iter_reference_targets(
    text: str,
    *,
    stripped_text: str | None = None,
    text_is_stripped: bool = False,
) -> tuple[tuple[int, str, str], ...]:
    if stripped_text is None:
        stripped_text = text if text_is_stripped else strip_comments(text)
    return _iter_reference_targets_cached(stripped_text)


@lru_cache(maxsize=256)
def _iter_reference_targets_cached(stripped_text: str) -> tuple[tuple[int, str, str], ...]:
    targets: list[tuple[int, str, str]] = []
    seen_targets: set[tuple[int, str, str]] = set()
    for match in MACRO_CALL_RE.finditer(stripped_text):
        normalized_target = normalize_identifier(str(match.group("name") or ""))
        if not normalized_target or normalized_target in RESERVED_MACRO_CALL_NAMES:
            continue
        line_no = _line_number(stripped_text, match.start())
        target_key = (line_no, "macro_call", normalized_target)
        if target_key in seen_targets:
            continue
        seen_targets.add(target_key)
        targets.append((line_no, "macro_call", normalized_target))
    return tuple(targets)


def resolve_include(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_target(import_target)
    if (
        not normalized_target
        or normalized_target.startswith("/")
        or "$" in normalized_target
        or "&" in normalized_target
        or "%" in normalized_target
        or "(" in normalized_target
        or ")" in normalized_target
        or normalized_target.lower().startswith(("http://", "https://"))
    ):
        return None

    current_dir = _normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    candidate_keys: list[str] = []
    if current_dir:
        relative_target = _normalize_repository_relative_path(
            str(PurePosixPath(current_dir) / normalized_target)
        )
        if relative_target:
            candidate_keys.append(relative_target)
            if PurePosixPath(relative_target).suffix.lower() not in _KNOWN_SAS_SUFFIXES:
                candidate_keys.append(f"{relative_target}.sas")

    normalized_path = _normalize_repository_relative_path(normalized_target)
    if normalized_path:
        candidate_keys.append(normalized_path)
        if PurePosixPath(normalized_path).suffix.lower() not in _KNOWN_SAS_SUFFIXES:
            candidate_keys.append(f"{normalized_path}.sas")

    target_name = PurePosixPath(normalized_target).name
    if target_name:
        candidate_keys.append(target_name)
        if PurePosixPath(target_name).suffix.lower() not in _KNOWN_SAS_SUFFIXES:
            candidate_keys.append(f"{target_name}.sas")

    seen_keys: set[str] = set()
    ordered_candidates: list[str] = []
    for candidate_key in candidate_keys:
        normalized_candidate = _normalize_repository_relative_path(candidate_key)
        if not normalized_candidate or normalized_candidate in seen_keys:
            continue
        seen_keys.add(normalized_candidate)
        ordered_candidates.append(normalized_candidate)

    for candidate_key in ordered_candidates:
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved != current_file:
            return resolved

    return resolve_suffix_match(
        module_index=module_index,
        suffixes=tuple(dict.fromkeys(ordered_candidates)),
    )


def resolve_target(
    reference_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_identifier(reference_target)
    if (
        not normalized_target
        or normalized_target in RESERVED_SYMBOL_NAMES
        or normalized_target in RESERVED_MACRO_CALL_NAMES
    ):
        return None

    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match

    return resolve_suffix_match(
        module_index=module_index,
        suffixes=(
            normalized_target,
            f"{normalized_target}.sas",
            f"macros/{normalized_target}.sas",
            f"src/{normalized_target}.sas",
        ),
    )


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_include: Callable[[str, str, dict[str, str]], str | None],
    resolve_target: Callable[[str, dict[str, str]], str | None],
    stripped_text: str | None = None,
    include_targets: tuple[tuple[int, str], ...] | None = None,
    reference_targets: tuple[tuple[int, str, str], ...] | None = None,
) -> tuple[dict[str, Any], ...]:
    stripped_text = strip_comments(text) if stripped_text is None else stripped_text
    dependency_entries: list[dict[str, Any]] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()

    for line_no, import_target in (
        include_targets
        if include_targets is not None
        else iter_include_targets(text, stripped_text=stripped_text)
    ):
        target_file = resolve_include(file_path, import_target, module_index)
        target_symbol = normalize_identifier(PurePosixPath(import_target).stem)
        dependency_key = (target_file, target_symbol, "imports")
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
                        "target": import_target,
                        "line": line_no,
                        "kind": "include",
                    },
                ),
                "source_file": file_path,
                "target_file": target_file,
                "target_symbol": target_symbol or PurePosixPath(import_target).name.lower(),
                "dependency_type": "imports",
            }
        )

    for line_no, reference_kind, raw_target in (
        reference_targets
        if reference_targets is not None
        else iter_reference_targets(text, stripped_text=stripped_text)
    ):
        normalized_target = normalize_identifier(raw_target)
        if not normalized_target:
            continue
        target_file = resolve_target(raw_target, module_index)
        dependency_key = (target_file, normalized_target, "references")
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
                "target_symbol": normalized_target,
                "dependency_type": "references",
            }
        )

    return tuple(dependency_entries)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_include: Callable[[str, str, dict[str, str]], str | None],
    resolve_target: Callable[[str, dict[str, str]], str | None],
) -> tuple[
    list[dict[str, Any]],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
]:
    stripped_text = strip_comments(text)
    symbol_entries = collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    )
    reference_candidates: dict[str, dict[str, Any]] = {}
    include_targets = iter_include_targets(text, stripped_text=stripped_text)
    reference_targets = iter_reference_targets(text, stripped_text=stripped_text)

    for symbol_entry in symbol_entries:
        start_line = int(symbol_entry["start_line"])
        end_line = int(symbol_entry["end_line"])
        symbol_name = normalize_identifier(str(symbol_entry["symbol_name"]))
        symbol_id = str(symbol_entry["symbol_id"])

        for line_no, _reference_kind, raw_target in reference_targets:
            if line_no < start_line or line_no > end_line:
                continue
            normalized_target = normalize_identifier(raw_target)
            if not normalized_target or normalized_target == symbol_name:
                continue
            target_file = resolve_target(raw_target, module_index)
            if target_file is None or target_file == file_path:
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol_id,
                    "target_file": target_file,
                    "target_names": (normalized_target,),
                    "type": "references_symbol",
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
                    "target_names": (normalized_target,),
                    "reference_type": "references_symbol",
                },
            )

    return (
        symbol_entries,
        parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=stable_identifier,
            resolve_include=resolve_include,
            resolve_target=resolve_target,
            stripped_text=stripped_text,
            include_targets=include_targets,
            reference_targets=reference_targets,
        ),
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )

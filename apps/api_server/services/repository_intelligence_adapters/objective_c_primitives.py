from __future__ import annotations

from bisect import bisect_right
from functools import lru_cache
import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

_KNOWN_OBJECTIVE_C_SUFFIXES = (".h", ".m", ".mm", ".pch")
_FORWARD_DECL_RE = re.compile(r"^\s*@(?:class|protocol)\b.*;\s*$", re.IGNORECASE)
_END_RE = re.compile(r"^\s*@end\b", re.IGNORECASE)
_IMPORT_RE = re.compile(
    r'^\s*#\s*(?:import|include)\s*[<"](?P<target>[^">]+)[">]',
    re.IGNORECASE | re.MULTILINE,
)
_OBJECTIVE_C_MARKER_RE = re.compile(
    r"^\s*#\s*import\b"
    r"|^\s*@import\b"
    r"|^\s*@(?:interface|implementation|protocol|property|class|dynamic|synthesize|"
    r"autoreleasepool|end)\b"
    r"|^\s*NS_ASSUME_NONNULL_(?:BEGIN|END)\b"
    r"|^\s*(?:FOUNDATION_EXPORT|UIKIT_EXTERN)\b",
    re.IGNORECASE | re.MULTILINE,
)
_METHOD_SIGNATURE_START_RE = re.compile(r"^\s*[+-]\s*\([^)]*\)")
_METHOD_SIGNATURE_CAPTURE_RE = re.compile(r"^[+-]\s*\([^)]*\)\s*(?P<body>.+)$")
_MESSAGE_SEND_LEXICAL_HINT_RE = re.compile(
    r"\[\s*[A-Za-z_][A-Za-z0-9_]*\s+[A-Za-z_]",
    re.DOTALL,
)
_TYPE_DECL_RE = re.compile(
    r"^\s*@(?P<kind>interface|implementation|protocol)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\s*\((?P<category>[^)]*)\))?",
    re.IGNORECASE,
)
_MESSAGE_SEND_RE = re.compile(
    r"\[\s*(?P<receiver>[A-Za-z_][A-Za-z0-9_]*)\s+(?P<body>[^\[\]]+?)\]",
    re.DOTALL,
)
_TYPE_REFERENCE_TOKEN_RE = re.compile(r"\b[A-Z][A-Za-z0-9_]*\b")
_STRING_LITERAL_RE = re.compile(
    r'@"(?:\\.|[^"\\])*"|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
    re.MULTILINE,
)
_RESERVED_REFERENCE_NAMES = frozenset({"self", "super", "nil", "yes", "no", "null"})
_SANITIZED_TEXT_CACHE_LIMIT = 128
_SANITIZED_TEXT_CACHE: dict[str, str] = {}


def _replace_with_spaces(value: str) -> str:
    return "".join("\n" if character == "\n" else " " for character in value)


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


def normalize_identifier(raw_name: str) -> str:
    normalized = re.sub(r"\s+", "", str(raw_name or "").strip())
    return normalized.strip("*").lower()


def _normalize_import_target(raw_target: str) -> str:
    normalized = str(raw_target or "").strip().strip("<>\"'").replace("\\", "/")
    return _normalize_repository_relative_path(normalized).lower()


def _normalize_type_symbol_name(raw_name: str, category_name: str | None = None) -> str:
    normalized_name = normalize_identifier(raw_name)
    normalized_category = normalize_identifier(str(category_name or ""))
    if normalized_name and normalized_category:
        return f"{normalized_name}+{normalized_category}"
    return normalized_name


def _is_macro_like_name(raw_name: str) -> bool:
    normalized = str(raw_name or "").strip()
    if not normalized:
        return False
    letters = [character for character in normalized if character.isalpha()]
    return bool(letters) and "_" in normalized and all(
        character.isupper() for character in letters
    )


def _normalize_selector_from_body(raw_body: str) -> str:
    body = re.sub(r"\s+", " ", str(raw_body or "")).strip()
    if not body:
        return ""
    selector_segments = [
        normalize_identifier(segment)
        for segment in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*:", body)
    ]
    if selector_segments:
        return "".join(f"{segment}:" for segment in selector_segments if segment)
    token_match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", body)
    if token_match is None:
        return ""
    return normalize_identifier(token_match.group(1))


@lru_cache(maxsize=1024)
def strip_comments(text: str) -> str:
    return re.sub(
        r"//[^\n]*|/\*.*?\*/",
        lambda match: _replace_with_spaces(match.group(0)),
        text,
        flags=re.MULTILINE | re.DOTALL,
    )


@lru_cache(maxsize=1024)
def strip_string_literals(text: str) -> str:
    return _STRING_LITERAL_RE.sub(
        lambda match: _replace_with_spaces(match.group(0)),
        text,
    )


def clear_sanitize_text_cache() -> None:
    _SANITIZED_TEXT_CACHE.clear()


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


def sanitize_text(text: str) -> str:
    cached = _SANITIZED_TEXT_CACHE.get(text)
    if cached is not None:
        return cached
    sanitized_text = strip_string_literals(strip_comments(text))
    if len(_SANITIZED_TEXT_CACHE) >= _SANITIZED_TEXT_CACHE_LIMIT:
        oldest_key = next(iter(_SANITIZED_TEXT_CACHE))
        _SANITIZED_TEXT_CACHE.pop(oldest_key, None)
    _SANITIZED_TEXT_CACHE[text] = sanitized_text
    return sanitized_text


def _has_objective_c_lexical_hints(text: str) -> bool:
    if not text:
        return False
    if "@" in text:
        return True
    if "#" in text and "import" in text.lower():
        return True
    if "FOUNDATION_EXPORT" in text or "UIKIT_EXTERN" in text:
        return True
    if "NS_ASSUME_NONNULL_" in text:
        return True
    if "+ (" in text or "- (" in text or "+(" in text or "-(" in text:
        return True
    if "[" in text and "]" in text:
        return bool(_MESSAGE_SEND_LEXICAL_HINT_RE.search(text))
    return False


def has_objective_c_markers(text: str) -> bool:
    if not _has_objective_c_lexical_hints(text):
        return False
    return bool(_OBJECTIVE_C_MARKER_RE.search(sanitize_text(text)))


def is_probable_objective_c_source(*, path: PurePosixPath | Path | str, text: str) -> bool:
    normalized_path = PurePosixPath(str(path).replace("\\", "/"))
    suffix = normalized_path.suffix.lower()
    if suffix not in _KNOWN_OBJECTIVE_C_SUFFIXES:
        return False
    if suffix == ".mm":
        return True
    if not _has_objective_c_lexical_hints(text):
        return False
    sanitized_text = sanitize_text(text)
    if _OBJECTIVE_C_MARKER_RE.search(sanitized_text):
        return True
    if _METHOD_SIGNATURE_START_RE.search(sanitized_text):
        return True
    return bool(_MESSAGE_SEND_RE.search(sanitized_text))


def _finalize_method_symbol(
    *,
    file_path: str,
    current_type_name: str | None,
    start_line: int,
    signature: str,
    stable_identifier: StableIdentifier,
    seen_method_keys: set[tuple[str | None, str]],
    symbol_entries: list[dict[str, Any]],
) -> None:
    signature_match = _METHOD_SIGNATURE_CAPTURE_RE.match(signature)
    if signature_match is None:
        return
    selector_name = _normalize_selector_from_body(signature_match.group("body"))
    if not selector_name:
        return
    symbol_key = (current_type_name, selector_name)
    if symbol_key in seen_method_keys:
        return
    seen_method_keys.add(symbol_key)
    qualified_names = {selector_name}
    if current_type_name:
        qualified_names.add(f"{current_type_name}.{selector_name}")
    symbol_entries.append(
        {
            "symbol_id": stable_identifier(
                "sym",
                {
                    "file_path": file_path,
                    "name": selector_name,
                    "kind": "function",
                    "line": start_line,
                },
            ),
            "symbol_name": selector_name,
            "symbol_kind": "function",
            "start_line": start_line,
            "end_line": start_line,
            "signature": signature,
            "qualified_names": tuple(sorted(qualified_names)),
        }
    )


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    sanitized_lines = sanitize_text(text).splitlines()
    symbol_entries: list[dict[str, Any]] = []
    seen_type_names: set[str] = set()
    seen_method_keys: set[tuple[str | None, str]] = set()
    type_stack: list[str] = []
    pending_method_start_line: int | None = None
    pending_method_lines: list[str] = []

    for line_no, raw_line in enumerate(sanitized_lines, start=1):
        stripped_line = raw_line.strip()
        if pending_method_start_line is not None:
            pending_method_lines.append(raw_line)
            if ";" in raw_line or "{" in raw_line:
                _finalize_method_symbol(
                    file_path=file_path,
                    current_type_name=type_stack[-1] if type_stack else None,
                    start_line=pending_method_start_line,
                    signature=re.sub(r"\s+", " ", " ".join(pending_method_lines)).strip(),
                    stable_identifier=stable_identifier,
                    seen_method_keys=seen_method_keys,
                    symbol_entries=symbol_entries,
                )
                pending_method_start_line = None
                pending_method_lines = []
            continue

        if not stripped_line:
            continue
        if _END_RE.match(stripped_line):
            if type_stack:
                type_stack.pop()
            continue
        if _FORWARD_DECL_RE.match(stripped_line):
            continue

        type_match = _TYPE_DECL_RE.match(stripped_line)
        if type_match is not None:
            raw_kind = str(type_match.group("kind") or "").strip().lower()
            raw_name = str(type_match.group("name") or "")
            raw_category_name = str(type_match.group("category") or "")
            normalized_name = _normalize_type_symbol_name(raw_name, raw_category_name)
            if normalized_name and normalized_name not in seen_type_names:
                seen_type_names.add(normalized_name)
                qualified_names = {normalized_name}
                if not raw_category_name:
                    qualified_names.add(normalize_identifier(raw_name))
                symbol_entries.append(
                    {
                        "symbol_id": stable_identifier(
                            "sym",
                            {
                                "file_path": file_path,
                                "name": normalized_name,
                                "kind": "interface" if raw_kind == "protocol" else "type",
                                "line": line_no,
                            },
                        ),
                        "symbol_name": normalized_name,
                        "symbol_kind": "interface" if raw_kind == "protocol" else "type",
                        "start_line": line_no,
                        "end_line": line_no,
                        "signature": stripped_line,
                        "qualified_names": tuple(sorted(qualified_names)),
                    }
                )
            if normalized_name:
                type_stack.append(normalized_name)
            continue

        if _METHOD_SIGNATURE_START_RE.match(raw_line):
            pending_method_start_line = line_no
            pending_method_lines = [raw_line]
            if ";" in raw_line or "{" in raw_line:
                _finalize_method_symbol(
                    file_path=file_path,
                    current_type_name=type_stack[-1] if type_stack else None,
                    start_line=pending_method_start_line,
                    signature=re.sub(r"\s+", " ", raw_line).strip(),
                    stable_identifier=stable_identifier,
                    seen_method_keys=seen_method_keys,
                    symbol_entries=symbol_entries,
                )
                pending_method_start_line = None
                pending_method_lines = []

    final_line = len(sanitized_lines) if sanitized_lines else 1
    for index, entry in enumerate(symbol_entries):
        if index + 1 < len(symbol_entries):
            entry["end_line"] = max(
                int(symbol_entries[index + 1]["start_line"]) - 1,
                int(entry["start_line"]),
            )
        else:
            entry["end_line"] = final_line
    return symbol_entries


def iter_import_targets(text: str) -> tuple[tuple[int, str], ...]:
    sanitized_text = strip_comments(text)
    targets: list[tuple[int, str]] = []
    seen_targets: set[tuple[int, str]] = set()
    for match in _IMPORT_RE.finditer(sanitized_text):
        normalized_target = _normalize_import_target(str(match.group("target") or ""))
        if not normalized_target:
            continue
        line_no = _line_number(text, match.start())
        target_key = (line_no, normalized_target)
        if target_key in seen_targets:
            continue
        seen_targets.add(target_key)
        targets.append((line_no, normalized_target))
    return tuple(targets)


def iter_message_sends(text: str) -> tuple[tuple[int, str, str], ...]:
    sanitized_text = sanitize_text(text)
    references: list[tuple[int, str, str]] = []
    seen_references: set[tuple[int, str, str]] = set()
    for match in _MESSAGE_SEND_RE.finditer(sanitized_text):
        receiver = normalize_identifier(str(match.group("receiver") or ""))
        selector_name = _normalize_selector_from_body(str(match.group("body") or ""))
        if (
            not receiver
            or receiver in _RESERVED_REFERENCE_NAMES
            or _is_macro_like_name(receiver)
        ):
            continue
        target_name = selector_name or receiver
        line_no = _line_number(text, match.start())
        reference_key = (line_no, receiver, target_name)
        if reference_key in seen_references:
            continue
        seen_references.add(reference_key)
        references.append((line_no, receiver, target_name))
    return tuple(references)


def iter_type_reference_tokens(text: str) -> tuple[tuple[int, str], ...]:
    sanitized_text = sanitize_text(text)
    tokens: list[tuple[int, str]] = []
    seen_tokens: set[tuple[int, str]] = set()
    for match in _TYPE_REFERENCE_TOKEN_RE.finditer(sanitized_text):
        raw_token = str(match.group(0) or "").strip()
        normalized_token = normalize_identifier(raw_token)
        if (
            not normalized_token
            or normalized_token in _RESERVED_REFERENCE_NAMES
            or _is_macro_like_name(raw_token)
        ):
            continue
        line_no = _line_number(text, match.start())
        token_key = (line_no, normalized_token)
        if token_key in seen_tokens:
            continue
        seen_tokens.add(token_key)
        tokens.append((line_no, normalized_token))
    return tuple(tokens)


def _candidate_import_suffixes(base_path: str) -> tuple[str, ...]:
    normalized_base = _normalize_repository_relative_path(base_path.lower())
    if not normalized_base:
        return ()
    suffix = PurePosixPath(normalized_base).suffix.lower()
    if suffix in _KNOWN_OBJECTIVE_C_SUFFIXES:
        return tuple(
            dict.fromkeys(
                (
                    normalized_base,
                    _normalize_repository_relative_path(
                        str(PurePosixPath(normalized_base).with_suffix(""))
                    ).lower(),
                )
            )
        )
    return tuple(
        dict.fromkeys(
            (
                normalized_base,
                f"{normalized_base}.h",
                f"{normalized_base}.pch",
                f"{normalized_base}.m",
                f"{normalized_base}.mm",
            )
        )
    )

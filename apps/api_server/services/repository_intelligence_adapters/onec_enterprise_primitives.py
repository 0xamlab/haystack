from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[..., str | None]

ONEC_ENTERPRISE_SUFFIXES = frozenset({".bsl", ".os"})

_IMPORT_RE = re.compile(
    r"^\s*#(?:Использовать|Use)\s+(?P<target>[^\s;]+)",
    re.IGNORECASE | re.MULTILINE,
)
_DECL_RE = re.compile(
    r"^\s*(?P<kind>Функция|Процедура|Function|Procedure)\s+"
    r"(?P<name>[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*)",
    re.MULTILINE,
)
_CALL_RE = re.compile(
    r"(?<![.A-Za-zА-Яа-яЁё0-9_])(?P<name>[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*)\s*\("
)
_MARKER_RE = re.compile(
    r"(?is)(?:^\s*#(?:Использовать|Use)\s+[^\s;]+|^\s*(?:Функция|Процедура|Function|Procedure)\s+[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*)",
    re.MULTILINE,
)
_END_MARKERS = {
    "function": re.compile(r"^\s*(?:КонецФункции|EndFunction)\b", re.IGNORECASE | re.MULTILINE),
    "procedure": re.compile(
        r"^\s*(?:КонецПроцедуры|EndProcedure)\b",
        re.IGNORECASE | re.MULTILINE,
    ),
}
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "do",
        "each",
        "else",
        "enddo",
        "endforeach",
        "endif",
        "endfunction",
        "endprocedure",
        "exception",
        "for",
        "function",
        "if",
        "new",
        "not",
        "procedure",
        "return",
        "then",
        "var",
        "while",
        "вызватьисключение",
        "для",
        "если",
        "иначе",
        "каждого",
        "конецесли",
        "конецпроцедуры",
        "конецфункции",
        "не",
        "новый",
        "перем",
        "по",
        "попытка",
        "процедура",
        "тогда",
        "функция",
        "цикл",
        "экспорт",
        "исключение",
        "конецпопытки",
        "конеццикла",
        "возврат",
    }
)


def _strip_inline_comment(raw_line: str) -> str:
    chars: list[str] = []
    in_string = False
    string_char = ""
    for index, character in enumerate(raw_line):
        if in_string:
            chars.append(character)
            if character == string_char:
                in_string = False
                string_char = ""
            continue
        if character in {'"', "'"}:
            chars.append(character)
            in_string = True
            string_char = character
            continue
        if character == "/" and index + 1 < len(raw_line) and raw_line[index + 1] == "/":
            break
        chars.append(character)
    return "".join(chars)


def strip_comments(text: str) -> str:
    normalized_text = text.lstrip("\ufeff")
    return "\n".join(_strip_inline_comment(line) for line in normalized_text.splitlines())


def _line_number(text: str, index: int) -> int:
    bounded_index = max(0, min(index, len(text)))
    return text.count("\n", 0, bounded_index) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def has_onec_enterprise_path_hints(path: Path | PurePosixPath | str) -> bool:
    return PurePosixPath(path).suffix.lower() in ONEC_ENTERPRISE_SUFFIXES


def is_probable_onec_enterprise_source(*, path: Path | PurePosixPath | str, text: str) -> bool:
    if not has_onec_enterprise_path_hints(path):
        return False
    stripped_text = strip_comments(text).strip()
    if not stripped_text:
        return False
    return bool(_MARKER_RE.search(stripped_text))


def _normalize_import_target(raw_target: str) -> str:
    normalized_target = str(raw_target or "").strip().strip('"').strip("'")
    return normalized_target.replace("\\", "/")


def import_targets_for_text(text: str) -> tuple[tuple[str, int], ...]:
    targets: list[tuple[str, int]] = []
    seen_targets: set[tuple[str, int]] = set()
    for match in _IMPORT_RE.finditer(strip_comments(text)):
        target_name = _normalize_import_target(str(match.group("target") or ""))
        if not target_name:
            continue
        entry = (target_name, _line_number(text, match.start()))
        if entry in seen_targets:
            continue
        seen_targets.add(entry)
        targets.append(entry)
    return tuple(targets)


def _declaration_kind(raw_kind: str) -> str:
    normalized_kind = str(raw_kind or "").strip().lower()
    return "function" if normalized_kind in {"функция", "function"} else "procedure"


def _find_symbol_end_line(text: str, match: re.Match[str], *, symbol_kind: str) -> int:
    end_marker = _END_MARKERS[symbol_kind]
    trailing_match = end_marker.search(text, match.end())
    if trailing_match is None:
        return _line_count(text)
    return _line_number(text, trailing_match.start())


def iter_declared_symbol_entries(
    *,
    text: str,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> tuple[dict[str, object], ...]:
    stripped_text = strip_comments(text)
    entries: list[dict[str, object]] = []
    seen_names: set[tuple[str, int]] = set()
    for match in _DECL_RE.finditer(stripped_text):
        symbol_name = str(match.group("name") or "").strip()
        if not symbol_name:
            continue
        start_line = _line_number(stripped_text, match.start())
        dedupe_key = (symbol_name.lower(), start_line)
        if dedupe_key in seen_names:
            continue
        seen_names.add(dedupe_key)
        symbol_kind = _declaration_kind(str(match.group("kind") or ""))
        entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "symbol_name": symbol_name,
                        "symbol_kind": symbol_kind,
                        "start_line": start_line,
                    },
                ),
                "symbol_name": symbol_name,
                "symbol_kind": symbol_kind,
                "start_line": start_line,
                "end_line": _find_symbol_end_line(
                    stripped_text,
                    match,
                    symbol_kind=symbol_kind,
                ),
                "signature": match.group(0).strip(),
            }
        )
    return tuple(
        sorted(entries, key=lambda entry: (int(entry["start_line"]), str(entry["symbol_name"])))
    )


def iter_reference_targets(
    text: str,
    *,
    declared_symbol_entries: tuple[dict[str, object], ...],
) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    declaration_start_lines = {
        (str(entry["symbol_name"]).lower(), int(entry["start_line"]))
        for entry in declared_symbol_entries
    }
    targets: list[tuple[str, int]] = []
    seen_targets: set[tuple[str, int]] = set()
    for match in _CALL_RE.finditer(stripped_text):
        target_name = str(match.group("name") or "").strip()
        if not target_name or target_name.lower() in _RESERVED_REFERENCE_NAMES:
            continue
        line_number = _line_number(stripped_text, match.start())
        if (target_name.lower(), line_number) in declaration_start_lines:
            continue
        entry = (target_name, line_number)
        if entry in seen_targets:
            continue
        seen_targets.add(entry)
        targets.append(entry)
    return tuple(targets)


def path_aliases_for_file(file_path: str) -> set[str]:
    path = PurePosixPath(file_path)
    aliases = {
        file_path,
        path.stem,
        path.stem.lower(),
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
    }
    return {alias for alias in aliases if alias}


def resolve_target(
    target_name: str,
    module_index: dict[str, str],
    *,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = _normalize_import_target(target_name)
    if not normalized_target:
        return None
    for candidate_key in (
        normalized_target,
        normalized_target.lower(),
    ):
        if candidate_key in module_index:
            return module_index[candidate_key]
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            normalized_target,
            normalized_target.lower(),
            f"{normalized_target}.os",
            f"{normalized_target.lower()}.os",
            f"{normalized_target}.bsl",
            f"{normalized_target.lower()}.bsl",
            f"/{normalized_target}.os",
            f"/{normalized_target.lower()}.os",
            f"/{normalized_target}.bsl",
            f"/{normalized_target.lower()}.bsl",
        ],
    )


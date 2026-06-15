from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import c_family as c_family_adapter
from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]

ANGELSCRIPT_SUFFIXES = frozenset({".as"})
_PATH_HINT_PARTS = frozenset({"angelscript"})
_INCLUDE_RE = re.compile(r'^\s*#\s*include\s*[<"](?P<target>[^">]+)[">]', re.MULTILINE)
_IMPORT_RE = re.compile(
    r"^\s*import\s+(?:(?:const\s+)?[A-Za-z_][A-Za-z0-9_:<>@&*\s]*\s+)?"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\([^;{}]*\)\s*"
    r"(?:const\b\s*)?from\s+[\"'](?P<module>[^\"']+)[\"']\s*;?",
    re.MULTILINE,
)
_NAMESPACE_RE = re.compile(
    r"^\s*namespace\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\{",
    re.MULTILINE,
)
_TYPE_DECL_RE = re.compile(
    r"^\s*(?:(?:shared|external|abstract|final|mixin|private|protected)\s+)*"
    r"(?P<kind>class|interface|enum|funcdef)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
    r"(?:\s*:\s*(?P<bases>[^\n{]+))?",
    re.MULTILINE,
)
_FUNCTION_DECL_RE = re.compile(
    r"^\s*(?P<prefix>(?:(?:shared|external|final|abstract|private|protected|const|"
    r"explicit|property|virtual|override|in|out|inout)\s+)*"
    r"(?:[A-Za-z_][A-Za-z0-9_:<>@&*\[\]]*\s+)+)"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\([^;{}]*\)\s*"
    r"(?:const\b\s*)?(?:\{|$)",
    re.MULTILINE,
)
_SCOPED_CALL_RE = re.compile(
    r"\b(?P<qualifier>[A-Za-z_][A-Za-z0-9_:]*)::(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_CALL_RE = re.compile(r"\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_ANGELSCRIPT_FEATURE_RE = re.compile(
    r"(?mi)^\s*#\s*include\s*[<\"][^\">]+[\">]"
    r"|^\s*import\s+.+\s+from\s+[\"'][^\"']+[\"']\s*;?"
    r"|^\s*namespace\s+[A-Za-z_][A-Za-z0-9_]*\s*\{"
    r"|^\s*(?:(?:shared|external|abstract|final|mixin)\s+)*(?:class|interface|enum|funcdef)\s+[A-Za-z_][A-Za-z0-9_]*\b"
    r"|^\s*(?:(?:shared|external|final|abstract|private|protected|const|explicit|property|virtual|override|in|out|inout)\s+)*(?:void|bool|int\d*|uint\d*|float|double|string|array<[^>\n]+>|dictionary|ref|any|[A-Za-z_][A-Za-z0-9_:<>@&*\[\]]+)\s+[A-Za-z_][A-Za-z0-9_]*\s*\("
    r"|\b[A-Za-z_][A-Za-z0-9_:<>]*@\s+[A-Za-z_][A-Za-z0-9_]*\b"
    r"|&(?:in|out|inout)\b",
)
_ACTIONSCRIPT_CONFLICT_RE = re.compile(
    r"(?mi)\bpackage\b"
    r"|^\s*import\s+[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_*]*)+\s*;"
    r"|^\s*(?:public|internal|private|protected)\s+(?:class|interface|function|var|const)\b"
    r"|\bfunction\s+[A-Za-z_][A-Za-z0-9_]*\s*\([^)]*\)\s*:\s*[A-Za-z_][A-Za-z0-9_.<>]*"
    r"|\b(?:var|const)\s+[A-Za-z_][A-Za-z0-9_]*\s*:\s*[A-Za-z_][A-Za-z0-9_.<>]*",
)
_DECLARATION_PREFIX_KEYWORDS = frozenset(
    {
        "break",
        "case",
        "catch",
        "continue",
        "delete",
        "do",
        "else",
        "for",
        "if",
        "new",
        "return",
        "switch",
        "throw",
        "while",
    }
)
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "array",
        "assert",
        "bool",
        "case",
        "cast",
        "catch",
        "class",
        "const",
        "continue",
        "delete",
        "dictionary",
        "do",
        "double",
        "else",
        "enum",
        "false",
        "float",
        "for",
        "funcdef",
        "if",
        "import",
        "in",
        "inout",
        "int",
        "int8",
        "int16",
        "int32",
        "int64",
        "interface",
        "is",
        "mixin",
        "namespace",
        "new",
        "null",
        "out",
        "override",
        "private",
        "property",
        "return",
        "shared",
        "string",
        "super",
        "switch",
        "this",
        "true",
        "uint",
        "uint8",
        "uint16",
        "uint32",
        "uint64",
        "void",
        "while",
    }
)

strip_comments = c_family_adapter.strip_comments


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


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, offset)) + 1


def _ordered_names(*values: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        normalized = str(raw_value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def normalize_symbol_name(symbol_name: str) -> str:
    normalized_name = str(symbol_name or "").strip()
    if not normalized_name:
        return ""
    return normalized_name.rsplit("::", 1)[-1]


def has_angelscript_path_hints(path: Path | PurePosixPath) -> bool:
    pure_path = PurePosixPath(path)
    if pure_path.suffix.lower() not in ANGELSCRIPT_SUFFIXES:
        return False
    lowered_parts = {part.lower() for part in pure_path.parts}
    return bool(lowered_parts & _PATH_HINT_PARTS)


def is_probable_angelscript_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in ANGELSCRIPT_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    if _ACTIONSCRIPT_CONFLICT_RE.search(stripped_text):
        return False
    if _ANGELSCRIPT_FEATURE_RE.search(stripped_text):
        return True
    return has_angelscript_path_hints(normalized_path)


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    return ".".join(without_suffix.parts) if without_suffix.parts else without_suffix.stem


def candidate_module_keys(
    base_path: str,
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> tuple[str, ...]:
    normalized_base = normalize_repository_relative_path(base_path)
    if not normalized_base:
        return ()
    suffix = PurePosixPath(normalized_base).suffix.lower()
    if suffix in ANGELSCRIPT_SUFFIXES:
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
    candidates.extend(f"{normalized_base}{suffix}" for suffix in sorted(ANGELSCRIPT_SUFFIXES))
    return tuple(dict.fromkeys(candidates))


def resolve_include(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(import_target or "").strip()
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
        for prefix in (
            "script",
            "scripts",
            "Data/Scripts",
            "bin/Data/Scripts",
            "src",
            "source",
            "lib",
        ):
            candidate_keys.extend(
                candidate_module_keys(
                    f"{prefix}/{normalized_target}",
                    normalize_repository_relative_path=normalize_repository_relative_path,
                )
            )
        for prefix in ("Data", "bin", "source", "lib"):
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


def resolve_named_target(
    *,
    target_name: str,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(target_name or "").strip()
    if not normalized_target:
        return None
    candidate_aliases = _ordered_names(
        normalized_target,
        normalized_target.replace("::", "."),
        normalized_target.replace("::", "/"),
        normalize_symbol_name(normalized_target),
    )
    for candidate_alias in candidate_aliases:
        direct_match = module_index.get(candidate_alias)
        if direct_match is not None:
            return direct_match
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=tuple(
            _ordered_names(
                f"{normalize_symbol_name(normalized_target)}.as",
                normalize_symbol_name(normalized_target),
            )
        ),
    )


def namespace_name(text: str) -> str:
    match = _NAMESPACE_RE.search(text)
    if match is None:
        return ""
    return str(match.group("name") or "").strip()


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int, str], ...]:
    stripped_text = strip_comments(text)
    namespace = namespace_name(stripped_text)
    entries: list[tuple[str, str, int, str]] = []
    seen_entries: set[tuple[str, str, int]] = set()
    for match in _TYPE_DECL_RE.finditer(stripped_text):
        symbol_name = normalize_symbol_name(str(match.group("name") or ""))
        if not symbol_name:
            continue
        symbol_kind = str(match.group("kind") or "type").strip().lower()
        line_number = _line_number(stripped_text, match.start())
        qualified_name = (
            f"{namespace}::{symbol_name}" if namespace and "::" not in symbol_name else symbol_name
        )
        entry_key = (symbol_name, symbol_kind, line_number)
        if entry_key in seen_entries:
            continue
        seen_entries.add(entry_key)
        entries.append((symbol_name, symbol_kind, line_number, qualified_name))
    for match in _FUNCTION_DECL_RE.finditer(stripped_text):
        symbol_name = normalize_symbol_name(str(match.group("name") or ""))
        if not symbol_name:
            continue
        prefix = str(match.group("prefix") or "")
        prefix_tokens = {
            token for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", prefix) if token
        }
        if prefix_tokens & _DECLARATION_PREFIX_KEYWORDS:
            continue
        line_number = _line_number(stripped_text, match.start())
        qualified_name = (
            f"{namespace}::{symbol_name}" if namespace and "::" not in symbol_name else symbol_name
        )
        entry_key = (symbol_name, "function", line_number)
        if entry_key in seen_entries:
            continue
        seen_entries.add(entry_key)
        entries.append((symbol_name, "function", line_number, qualified_name))
    return tuple(sorted(entries, key=lambda item: (item[2], item[1], item[0])))


def iter_dependency_entries(
    text: str,
) -> tuple[tuple[str, str, str | None, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, str | None, int]] = []
    for match in _INCLUDE_RE.finditer(stripped_text):
        target = str(match.group("target") or "").strip()
        if not target:
            continue
        entries.append(("include", target, PurePosixPath(target).stem, _line_number(stripped_text, match.start())))
    for match in _IMPORT_RE.finditer(stripped_text):
        target = str(match.group("module") or "").strip()
        imported_name = normalize_symbol_name(str(match.group("name") or ""))
        if not target or not imported_name:
            continue
        entries.append(("import", target, imported_name, _line_number(stripped_text, match.start())))
    for match in _TYPE_DECL_RE.finditer(stripped_text):
        raw_bases = str(match.group("bases") or "").strip()
        if not raw_bases:
            continue
        line_number = _line_number(stripped_text, match.start())
        for raw_base in raw_bases.split(","):
            candidate_base = str(raw_base or "").strip()
            if not candidate_base:
                continue
            normalized_base = normalize_symbol_name(candidate_base.split()[-1].strip("&*@"))
            if not normalized_base:
                continue
            entries.append(("extends", normalized_base, normalized_base, line_number))
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str | None, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str | None, str, int]] = []
    for match in _SCOPED_CALL_RE.finditer(stripped_text):
        qualifier = normalize_symbol_name(str(match.group("qualifier") or ""))
        target_name = normalize_symbol_name(str(match.group("name") or ""))
        if not qualifier or not target_name or target_name in _RESERVED_REFERENCE_NAMES:
            continue
        entries.append((qualifier, target_name, _line_number(stripped_text, match.start())))
    for match in _CALL_RE.finditer(stripped_text):
        target_name = normalize_symbol_name(str(match.group("name") or ""))
        if not target_name or target_name in _RESERVED_REFERENCE_NAMES:
            continue
        if match.start() > 0 and stripped_text[match.start() - 1] in {".", ":", ">"}:
            continue
        entries.append((None, target_name, _line_number(stripped_text, match.start())))
    return tuple(entries)


def source_symbol_name_for_line(
    symbol_entries: Iterable[tuple[str, str, int, str]],
    *,
    line_number: int,
) -> str | None:
    active_name: str | None = None
    active_line = -1
    for symbol_name, _symbol_kind, symbol_line, _qualified_name in symbol_entries:
        if symbol_line > line_number:
            break
        if symbol_line >= active_line:
            active_name = symbol_name
            active_line = symbol_line
    return active_name


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    module_name = module_name_from_path(file_path)
    line_count = max(1, text.count("\n") + 1)
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "symbol",
            {"file_path": file_path, "symbol_name": module_name, "kind": "angelscript"},
        ),
        symbol_name=module_name,
        symbol_kind="angelscript",
        start_line=1,
        end_line=line_count,
        parent_symbol_id=None,
        signature=f"angelscript {module_name}".strip(),
    )
    module_symbol_id = module_symbol.symbol_id
    symbols = [module_symbol]
    for symbol_name, symbol_kind, line_number, qualified_name in iter_symbol_entries(text):
        signature = (
            f"function {qualified_name}"
            if symbol_kind == "function"
            else f"{symbol_kind} {qualified_name}"
        )
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "symbol",
                    {
                        "file_path": file_path,
                        "symbol_name": symbol_name,
                        "line": line_number,
                        "kind": symbol_kind,
                    },
                ),
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                start_line=line_number,
                end_line=line_number,
                parent_symbol_id=module_symbol_id,
                signature=signature,
            )
        )
    return tuple(symbols)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    normalized_path = _normalize_repository_relative_path(file_path)
    if not normalized_path:
        return set()
    path = PurePosixPath(normalized_path)
    if path.suffix.lower() not in ANGELSCRIPT_SUFFIXES:
        return set()
    try:
        text = (root_path / normalized_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    if not is_probable_angelscript_source(path=path, text=text):
        return set()
    aliases = {
        normalized_path,
        path.name,
        path.stem,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
        module_name_from_path(normalized_path),
    }
    namespace = namespace_name(strip_comments(text))
    if namespace:
        aliases.update({namespace, f"namespace:{namespace}"})
    for symbol_name, symbol_kind, _line_number_value, qualified_name in iter_symbol_entries(text):
        aliases.update(
            {
                symbol_name,
                qualified_name,
                qualified_name.replace("::", "."),
                f"{symbol_kind}:{symbol_name}",
                f"{symbol_kind}:{qualified_name}",
            }
        )
    return {alias for alias in aliases if alias}

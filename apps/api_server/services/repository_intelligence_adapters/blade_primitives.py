from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

BLADE_SUFFIX = ".blade.php"
_COMMON_MODULE_ROOTS = (
    ("resources", "views"),
    ("views",),
)
_COMMENT_RE = re.compile(r"\{\{--.*?--\}\}", re.S)
_DIRECTIVE_CALL_RE = re.compile(
    r"""@(?P<name>extends|include|includeIf|includeWhen|includeUnless|includeFirst|each|component|livewire)\s*\(\s*['"](?P<target>[^'"]+)['"]""",
    re.S,
)
_COMPONENT_TAG_RE = re.compile(r"</?\s*x-(?P<name>[A-Za-z0-9_.:-]+)")
_SECTION_RE = re.compile(r"""@section\s*\(\s*['"](?P<name>[^'"]+)['"]""")
_PUSH_RE = re.compile(r"""@(?P<kind>push|prepend)\s*\(\s*['"](?P<name>[^'"]+)['"]""")
_YIELD_RE = re.compile(r"""@(?P<kind>yield|stack)\s*\(\s*['"](?P<name>[^'"]+)['"]""")
_LIKELY_BLADE_MARKERS = ("{{", "{!!", "@extends", "@include", "@section", "@yield", "@component", "<x-")
_COMPONENT_PREFIX_DIRS = ("components", "resources/views/components", "views/components")
_RESOLVER_DIRS = (
    "resources/views",
    "views",
    "resources/views/components",
    "resources/views/layouts",
    "resources/views/partials",
    "resources/views/includes",
    "components",
    "layouts",
    "partials",
    "includes",
)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def strip_comments(text: str) -> str:
    return _COMMENT_RE.sub(
        lambda match: "".join("\n" if char == "\n" else " " for char in match.group(0)),
        text,
    )


def has_blade_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).name.lower().endswith(BLADE_SUFFIX)


def is_probable_blade_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if not has_blade_path_hints(normalized_path) or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return True if any(marker in stripped_text for marker in _LIKELY_BLADE_MARKERS) else True


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip()


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


def _strip_blade_suffix(file_path: str) -> str:
    normalized_path = _normalize_repository_relative_path(file_path)
    lowered_path = normalized_path.lower()
    if lowered_path.endswith(BLADE_SUFFIX):
        return normalized_path[: -len(BLADE_SUFFIX)]
    return normalized_path


def module_name_from_path(file_path: str) -> str:
    normalized_without_suffix = PurePosixPath(_strip_blade_suffix(file_path))
    parts = list(normalized_without_suffix.parts)
    lowered_parts = [part.lower() for part in parts]
    for common_root in _COMMON_MODULE_ROOTS:
        root_length = len(common_root)
        if tuple(lowered_parts[:root_length]) == common_root:
            parts = parts[root_length:]
            break
    return ".".join(parts) if parts else normalized_without_suffix.name


def _normalize_import_target(value: str) -> str:
    target = normalize_identifier(value)
    if not target:
        return ""
    namespace, separator, remainder = target.partition("::")
    if separator:
        target = f"{namespace}/{remainder}"
    return target.replace(".", "/")


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _DIRECTIVE_CALL_RE.finditer(stripped_text):
        directive_name = normalize_identifier(str(match.group("name") or "")).lower()
        import_target = normalize_identifier(str(match.group("target") or ""))
        if not directive_name or not import_target:
            continue
        dependency_kind = "component" if directive_name in {"component", "livewire"} else "template"
        line_number = stripped_text.count("\n", 0, match.start()) + 1
        item = (dependency_kind, import_target, line_number)
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    for match in _COMPONENT_TAG_RE.finditer(stripped_text):
        import_target = normalize_identifier(str(match.group("name") or ""))
        if not import_target:
            continue
        line_number = stripped_text.count("\n", 0, match.start()) + 1
        item = ("component", import_target, line_number)
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for pattern, default_kind in ((_SECTION_RE, "section"), (_PUSH_RE, "")):
        for match in pattern.finditer(stripped_text):
            symbol_name = normalize_identifier(str(match.group("name") or ""))
            symbol_kind = default_kind or normalize_identifier(str(match.group("kind") or ""))
            if not symbol_name or not symbol_kind:
                continue
            item = (
                symbol_name,
                symbol_kind,
                stripped_text.count("\n", 0, match.start()) + 1,
            )
            if item in seen:
                continue
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _YIELD_RE.finditer(stripped_text):
        target_name = normalize_identifier(str(match.group("name") or ""))
        if not target_name:
            continue
        item = (target_name, stripped_text.count("\n", 0, match.start()) + 1)
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


def source_symbol_name_for_line(
    symbol_entries: Iterable[tuple[str, str, int]],
    *,
    line_number: int,
) -> str | None:
    active_name: str | None = None
    active_line = -1
    for symbol_name, _symbol_kind, start_line in symbol_entries:
        if start_line <= line_number and start_line >= active_line:
            active_name = symbol_name
            active_line = start_line
    return active_name


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    normalized_path = _normalize_repository_relative_path(file_path)
    if not normalized_path or not has_blade_path_hints(PurePosixPath(normalized_path)):
        return set()
    aliases = {
        normalized_path,
        PurePosixPath(normalized_path).name,
        _strip_blade_suffix(normalized_path),
        _strip_blade_suffix(normalized_path).replace("/", "."),
    }
    try:
        text = (root_path / normalized_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if text and not is_probable_blade_source(path=normalized_path, text=text):
        return {alias for alias in aliases if alias}
    module_name = module_name_from_path(normalized_path)
    if module_name:
        aliases.add(module_name)
    return {alias for alias in aliases if alias}


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    dependency_kind: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = _normalize_import_target(import_target)
    if not normalized_target:
        return None
    current_parent = PurePosixPath(_strip_blade_suffix(current_file)).parent
    candidates: list[str] = [normalized_target]
    if normalized_target.startswith("../") or normalized_target.startswith("./") or "/" in normalized_target:
        candidates.append(str(current_parent / normalized_target))
    if dependency_kind == "component":
        candidates.extend(f"{directory}/{normalized_target}" for directory in _COMPONENT_PREFIX_DIRS)
    candidates.extend(f"{directory}/{normalized_target}" for directory in _RESOLVER_DIRS)
    if not any(candidate.lower().endswith(BLADE_SUFFIX) for candidate in candidates):
        candidates.extend(f"{candidate}{BLADE_SUFFIX}" for candidate in tuple(candidates))
    seen_candidates: set[str] = set()
    for candidate in candidates:
        normalized_candidate = normalize_repository_relative_path(candidate)
        if not normalized_candidate or normalized_candidate in seen_candidates:
            continue
        seen_candidates.add(normalized_candidate)
        module_target = module_index.get(normalized_candidate)
        if module_target:
            return module_target
        if normalized_candidate.lower().endswith(BLADE_SUFFIX):
            if normalized_candidate in module_index.values():
                return normalized_candidate
        module_target = module_index.get(module_name_from_path(normalized_candidate))
        if module_target:
            return module_target
    suffixes = tuple(
        f"/{PurePosixPath(candidate).name}"
        for candidate in seen_candidates
        if candidate.lower().endswith(BLADE_SUFFIX)
    )
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes) if suffixes else None


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    normalized_path = _normalize_repository_relative_path(file_path)
    if not normalized_path:
        return ()
    line_count = max(1, len(text.splitlines()) or 1)
    module_name = (
        module_name_from_path(normalized_path)
        or PurePosixPath(_strip_blade_suffix(normalized_path)).name
        or "template"
    )
    symbols: list[_Symbol] = [
        _Symbol(
            symbol_id=stable_identifier(
                "sym",
                {
                    "file_path": normalized_path,
                    "symbol_name": module_name,
                    "symbol_kind": "blade",
                },
            ),
            symbol_name=module_name,
            symbol_kind="blade",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"blade {module_name}",
        )
    ]
    seen: set[tuple[str, str]] = {(module_name, "blade")}
    for symbol_name, symbol_kind, line_number in iter_symbol_entries(text):
        key = (symbol_name, symbol_kind)
        if key in seen:
            continue
        seen.add(key)
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "sym",
                    {
                        "file_path": normalized_path,
                        "symbol_name": symbol_name,
                        "symbol_kind": symbol_kind,
                    },
                ),
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                start_line=line_number,
                end_line=line_number,
                parent_symbol_id=symbols[0].symbol_id,
                signature=f"{symbol_kind} {symbol_name}",
            )
        )
    return tuple(symbols)

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

EARTHLY_BASENAMES = frozenset({"earthfile"})
_COMMENT_RE = re.compile(r"(?m)#.*$")
_DIRECTIVE_RE = re.compile(
    r"(?mi)^\s*(?:VERSION|PROJECT|FROM|COPY|RUN|BUILD|DO|WITH(?:\s+DOCKER)?|SAVE\s+(?:ARTIFACT|IMAGE)|IMPORT|FUNCTION|ARG|ENV|ENTRYPOINT)\b"
)
_TARGET_RE = re.compile(r"(?mi)^(?P<name>[A-Za-z0-9][A-Za-z0-9_.-]*)\s*:\s*(?:#.*)?$")
_IMPORT_RE = re.compile(
    r"(?mi)^\s*IMPORT\s+(?P<target>[^#\n]+?)\s+AS\s+(?P<alias>[A-Za-z_][A-Za-z0-9_-]*)\s*$"
)
_TARGET_REF_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])(?P<ref>(?:[A-Za-z0-9_./-]+)?\+[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_./-]+)?)"
)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def strip_comments(text: str) -> str:
    return _COMMENT_RE.sub("", text)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip()


def has_earthly_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).name.lower() in EARTHLY_BASENAMES


def is_probable_earthly_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_earthly_path_hints(path) or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return _DIRECTIVE_RE.search(stripped_text) is not None or _TARGET_RE.search(stripped_text) is not None


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    if normalized_path.name.lower() in EARTHLY_BASENAMES:
        parent = normalized_path.parent
        if parent.parts and str(parent) != ".":
            return ".".join(parent.parts)
        return "Earthfile"
    without_suffix = normalized_path.with_suffix("")
    return ".".join(without_suffix.parts) if without_suffix.parts else without_suffix.stem


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def clean_import_target(value: str) -> str:
    cleaned = normalize_identifier(value)
    if not cleaned or "$" in cleaned or "://" in cleaned:
        return ""
    return cleaned


def clean_target_reference(value: str) -> str:
    cleaned = normalize_identifier(value)
    while cleaned and cleaned[-1] in {",", ")", "]", "}", ";"}:
        cleaned = cleaned[:-1].rstrip()
    if not cleaned or "$" in cleaned or "://" in cleaned:
        return ""
    return cleaned


def _candidate_earthly_paths(normalized_candidate: str) -> tuple[str, ...]:
    path = PurePosixPath(normalized_candidate)
    if path.name.lower() in EARTHLY_BASENAMES:
        return (normalized_candidate,)
    return (
        normalized_candidate,
        str(path / "Earthfile"),
        str(path / "earthfile"),
    )


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    cleaned_target = clean_import_target(import_target)
    if not cleaned_target:
        return None
    candidate_path = PurePosixPath(cleaned_target)
    current_dir = PurePosixPath(current_file).parent
    normalized_candidate = normalize_repository_relative_path(
        candidate_path if candidate_path.is_absolute() else current_dir / candidate_path
    )
    if not normalized_candidate:
        return None
    direct_match = module_index.get(normalized_candidate)
    if direct_match is not None:
        return direct_match
    earthly_candidates = _candidate_earthly_paths(normalized_candidate)
    resolved_match = resolve_suffix_match(module_index=module_index, suffixes=earthly_candidates)
    if resolved_match is not None:
        return resolved_match
    for candidate in earthly_candidates:
        direct_match = module_index.get(candidate)
        if direct_match is not None:
            return direct_match
    return None


def _split_target_reference(target_reference: str) -> tuple[str, str] | None:
    cleaned = clean_target_reference(target_reference)
    if not cleaned or "+" not in cleaned:
        return None
    locator, target_segment = cleaned.rsplit("+", 1)
    target_name = normalize_identifier(target_segment.split("/", 1)[0])
    if not target_name:
        return None
    return locator, target_name


def resolve_target_reference(
    *,
    current_file: str,
    target_reference: str,
    module_index: dict[str, str],
    import_aliases: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[str | None, str | None]:
    split_reference = _split_target_reference(target_reference)
    if split_reference is None:
        return None, None
    locator, target_name = split_reference
    if not locator:
        return current_file, target_name
    # A remote/registry target can't resolve to a local Earthfile. Detect ANY remote host
    # (repo-agnostic: a dotted host segment before the first "/", e.g. github.com/…, gitlab.com/…)
    # plus ":"-tagged registry refs — not a single hardcoded host.
    _locator_head = locator.split("/", 1)[0]
    _is_remote_host = "/" in locator and "." in _locator_head and _locator_head not in (".", "..")
    if _is_remote_host or ":" in locator:
        return None, None
    if locator in import_aliases:
        return import_aliases[locator], target_name
    locator_path = PurePosixPath(locator.lstrip("/")) if locator.startswith("/") else PurePosixPath(locator)
    current_dir = PurePosixPath(current_file).parent
    normalized_candidate = normalize_repository_relative_path(
        locator_path if locator.startswith("/") else current_dir / locator_path
    )
    if not normalized_candidate:
        return None, None
    earthly_candidates = _candidate_earthly_paths(normalized_candidate)
    direct_match = module_index.get(normalized_candidate)
    if direct_match is not None:
        return direct_match, target_name
    resolved_match = resolve_suffix_match(module_index=module_index, suffixes=earthly_candidates)
    if resolved_match is not None:
        return resolved_match, target_name
    for candidate in earthly_candidates:
        direct_match = module_index.get(candidate)
        if direct_match is not None:
            return direct_match, target_name
    return None, target_name


def iter_import_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    stripped_text = strip_comments(text)
    for match in _IMPORT_RE.finditer(stripped_text):
        import_target = clean_import_target(match.group("target") or "")
        import_alias = normalize_identifier(match.group("alias") or "")
        if not import_target or not import_alias:
            continue
        line_number = stripped_text.count("\n", 0, match.start()) + 1
        entries.append((import_alias, import_target, line_number))
    return tuple(entries)


def _dependency_kind_for_line(line: str) -> str:
    normalized_line = line.strip()
    if not normalized_line:
        return "target"
    prefix = normalized_line.split(None, 1)[0].upper()
    return {
        "FROM": "from_target",
        "COPY": "copy_target",
        "BUILD": "build_target",
        "DO": "do_target",
        "WITH": "with_target",
        "ARG": "arg_target",
    }.get(prefix, "target")


def iter_target_reference_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    stripped_text = strip_comments(text)
    for line_number, line in enumerate(stripped_text.splitlines(), start=1):
        if "--secret" in line or "type=secret" in line:
            continue
        dependency_kind = _dependency_kind_for_line(line)
        for match in _TARGET_REF_RE.finditer(line):
            target_reference = clean_target_reference(match.group("ref") or "")
            if not target_reference:
                continue
            entries.append((dependency_kind, target_reference, line_number))
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for match in _TARGET_RE.finditer(stripped_text):
        name = normalize_identifier(match.group("name") or "")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        entries.append((name, "target", stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(entries)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del root_path, stable_identifier
    normalized_path = PurePosixPath(file_path)
    if normalized_path.name.lower() not in EARTHLY_BASENAMES:
        return set()
    aliases = {file_path, normalized_path.name, normalized_path.name.lower(), module_name_from_path(file_path)}
    parent_path = str(normalized_path.parent)
    if parent_path and parent_path != ".":
        aliases.add(parent_path)
        aliases.add(parent_path.replace("/", "."))
        aliases.add(normalized_path.parent.name)
    return {alias for alias in aliases if alias}


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    module_name = module_name_from_path(file_path)
    line_count = _line_count(text)
    symbols = [
        _Symbol(
            symbol_id=stable_identifier(
                "symbol",
                {"file_path": file_path, "symbol_name": module_name, "kind": "earthly"},
            ),
            symbol_name=module_name,
            symbol_kind="earthly",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"earthly {module_name}".strip(),
        )
    ]
    module_symbol_id = symbols[0].symbol_id
    for symbol_name, symbol_kind, line_number in iter_symbol_entries(text):
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "symbol",
                    {"file_path": file_path, "symbol_name": symbol_name, "kind": symbol_kind},
                ),
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                start_line=line_number,
                end_line=line_number,
                parent_symbol_id=module_symbol_id,
                signature=f"{symbol_kind} {symbol_name}".strip(),
            )
        )
    return tuple(symbols)

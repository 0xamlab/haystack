from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str | PurePosixPath], str | None]
ResolveSuffixMatch = Callable[..., str | None]

BQN_SUFFIXES = frozenset({".bqn"})
_COMMON_MODULE_ROOTS = frozenset(
    {"benchmark", "benchmarks", "doc", "docs", "example", "examples", "src", "test", "tests"}
)
_LINE_COMMENT_RE = re.compile(r"(?m)^\s*#.*$")
_IMPORT_RE = re.compile(
    r'(?m)^\s*(?:(?P<binding>[A-Za-z][A-Za-z0-9_]*)\s*←\s*)?(?:(?P<context>[A-Za-z][A-Za-z0-9_]*)\s+)?•Import\s+"(?P<target>[^"\n]+)"'
)
_SYMBOL_ASSIGN_RE = re.compile(r"(?m)^\s*(?P<name>[A-Za-z][A-Za-z0-9_]*)\s*(?:←|⇐)")
_REFERENCE_RE = re.compile(r"(?P<name>[A-Za-z][A-Za-z0-9_]*)")
_PROBABLE_SOURCE_RE = re.compile(r"(?m)(←|⇐|•Import|•Out|•args|[⟨⟩‿⌜⊸𝕩𝕨𝔽𝔾𝕊])")
_RESERVED_REFERENCE_NAMES = frozenset({"Import"})


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t\f"
    )
    return control_count > max(2, len(sample) // 32)


def strip_comments(text: str) -> str:
    return _LINE_COMMENT_RE.sub("", text)


def has_bqn_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in BQN_SUFFIXES


def is_probable_bqn_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_bqn_path_hints(path) or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return _PROBABLE_SOURCE_RE.search(text) is not None or _PROBABLE_SOURCE_RE.search(
        stripped_text
    ) is not None


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    while parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    return ".".join(parts) if parts else without_suffix.stem


def candidate_module_keys(
    base_path: str,
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> tuple[str, ...]:
    normalized_base = normalize_repository_relative_path(base_path)
    if not normalized_base:
        return ()
    suffix = PurePosixPath(normalized_base).suffix.lower()
    if suffix == ".bqn":
        without_suffix = normalize_repository_relative_path(
            str(PurePosixPath(normalized_base).with_suffix(""))
        )
        return tuple(
            candidate
            for candidate in (normalized_base, without_suffix)
            if candidate
        )
    return tuple(
        dict.fromkeys(
            (
                normalized_base,
                f"{normalized_base}.bqn",
            )
        )
    )


def iter_dependency_entries(text: str) -> tuple[tuple[str, str | None, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str | None, int]] = []
    for match in _IMPORT_RE.finditer(stripped_text):
        target = str(match.group("target") or "").strip()
        if not target:
            continue
        binding = str(match.group("binding") or "").strip() or None
        line_number = stripped_text.count("\n", 0, match.start()) + 1
        entries.append((target, binding, line_number))
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen_names: set[str] = set()
    for target, binding, line_number in iter_dependency_entries(stripped_text):
        del target
        if binding and binding not in seen_names:
            seen_names.add(binding)
            entries.append((binding, "import_binding", line_number))
    for match in _SYMBOL_ASSIGN_RE.finditer(stripped_text):
        name = str(match.group("name") or "").strip()
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        entries.append((name, "assignment", stripped_text.count("\n", 0, match.start()) + 1))
    return tuple(sorted(entries, key=lambda entry: (entry[2], entry[0], entry[1])))


def iter_reference_entries(text: str) -> tuple[tuple[str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, int]] = []
    seen_entries: set[tuple[str, int]] = set()
    for line_number, raw_line in enumerate(stripped_text.splitlines(), start=1):
        line = _IMPORT_RE.sub("", raw_line, count=1)
        line = _SYMBOL_ASSIGN_RE.sub("", line, count=1)
        for match in _REFERENCE_RE.finditer(line):
            name = str(match.group("name") or "").strip()
            if not name or name in _RESERVED_REFERENCE_NAMES:
                continue
            entry = (name, line_number)
            if entry in seen_entries:
                continue
            seen_entries.add(entry)
            entries.append(entry)
    return tuple(entries)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    normalized_path = PurePosixPath(file_path)
    if normalized_path.suffix.lower() not in BQN_SUFFIXES:
        return set()
    aliases = {
        file_path,
        normalized_path.name,
        normalized_path.stem,
        str(normalized_path.with_suffix("")),
        str(normalized_path.with_suffix("")).replace("/", "."),
        module_name_from_path(file_path),
    }
    try:
        text = (root_path / normalized_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    for symbol_name, _kind, _line in iter_symbol_entries(text):
        aliases.add(symbol_name)
    return {alias for alias in aliases if alias}


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    module_name = module_name_from_path(file_path)
    line_count = max(1, text.count("\n") + 1)
    symbols = [
        _Symbol(
            symbol_id=stable_identifier(
                "symbol",
                {"file_path": file_path, "symbol_name": module_name, "kind": "bqn"},
            ),
            symbol_name=module_name,
            symbol_kind="bqn",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"bqn {module_name}".strip(),
        )
    ]
    module_symbol_id = symbols[0].symbol_id
    for symbol_name, symbol_kind, line_number in iter_symbol_entries(text):
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "symbol",
                    {
                        "file_path": file_path,
                        "symbol_name": symbol_name,
                        "kind": symbol_kind,
                    },
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


def resolve_import_module(
    import_target: str,
    current_file: str,
    module_index: dict[str, str],
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = import_target.strip()
    if not normalized_target:
        return None
    candidate_keys: list[str] = []
    current_dir = normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    if current_dir:
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
    candidate_keys.extend(
        candidate_module_keys(
            normalized_target,
            normalize_repository_relative_path=normalize_repository_relative_path,
        )
    )
    for prefix in ("src", "lib", "libs", "benchmark", "benchmarks", "examples", "tests"):
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


def source_symbol_name_for_line(
    symbol_entries: tuple[tuple[str, str, int], ...],
    *,
    line_number: int,
) -> str | None:
    current_name: str | None = None
    for symbol_name, _symbol_kind, symbol_line in symbol_entries:
        if symbol_line > line_number:
            break
        current_name = symbol_name
    return current_name

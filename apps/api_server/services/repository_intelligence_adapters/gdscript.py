from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".gd"})
_CLASS_NAME_RE = re.compile(
    r"^\s*(?:@[A-Za-z_][A-Za-z0-9_.]*\s*)*class_name\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
_EXTENDS_RE = re.compile(r"^\s*extends\s+(?P<target>.+)$", re.MULTILINE)
_FUNCTION_DECL_RE = re.compile(
    r"^\s*(?:static\s+)?func\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.MULTILINE,
)
_SIGNAL_DECL_RE = re.compile(
    r"^\s*signal\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
_RESOURCE_CALL_RE = re.compile(
    r"\b(?:preload|load)\(\s*['\"](?P<target>[^'\"]+)['\"]\s*\)"
)
_RESOURCE_BINDING_RE = re.compile(
    r"^\s*(?:@[A-Za-z_][A-Za-z0-9_.]*\s*)*"
    r"(?:const|var)\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)[^\n=]*?(?::=|=)\s*"
    r"(?:preload|load)\(\s*['\"](?P<target>[^'\"]+)['\"]\s*\)",
    re.MULTILINE,
)
_QUALIFIED_CALL_RE = re.compile(
    r"\b(?P<owner>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_RESOURCE_PATH_RE = re.compile(r"res://(?P<path>[^'\"]+)")
_TEST_PATH_PARTS = frozenset({"test", "tests"})
_RESERVED_REFERENCE_OWNERS = frozenset({"super"})
_RESERVED_REFERENCE_NAMES = frozenset(
    {
        "assert",
        "await",
        "breakpoint",
        "load",
        "preload",
        "print",
        "print_debug",
        "print_rich",
        "print_stack",
        "printerr",
        "printraw",
        "prints",
        "printt",
        "push_error",
        "push_warning",
    }
)


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    start_line: int
    end_line: int


@dataclass(frozen=True)
class _Binding:
    alias: str
    target_file: str | None
    target_class_name: str | None


def strip_comments(text: str) -> str:
    stripped_lines: list[str] = []
    for raw_line in text.splitlines():
        in_single = False
        in_double = False
        escape = False
        output_chars: list[str] = []
        for char in raw_line:
            if escape:
                output_chars.append(char)
                escape = False
                continue
            if char == "\\" and (in_single or in_double):
                output_chars.append(char)
                escape = True
                continue
            if char == '"' and not in_single:
                in_double = not in_double
                output_chars.append(char)
                continue
            if char == "'" and not in_double:
                in_single = not in_single
                output_chars.append(char)
                continue
            if char == "#" and not in_single and not in_double:
                break
            output_chars.append(char)
        stripped_lines.append("".join(output_chars))
    return "\n".join(stripped_lines)


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


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


def _current_class_name(*, file_path: str, text: str) -> str:
    match = _CLASS_NAME_RE.search(text)
    if match is not None:
        normalized = str(match.group("name") or "").strip()
        if normalized:
            return normalized
    return PurePosixPath(file_path).stem


def _class_line(text: str) -> int:
    match = _CLASS_NAME_RE.search(text)
    if match is None:
        return 1
    return _line_number(text, match.start())


def _normalize_resource_path(
    raw_path: str,
    *,
    file_path: str,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> str | None:
    normalized = str(raw_path or "").strip().strip('"').strip("'")
    if not normalized or normalized.startswith("uid://"):
        return None
    if normalized.startswith("res://"):
        normalized = normalized.removeprefix("res://")
    else:
        normalized = str(PurePosixPath(file_path).parent / normalized)
    normalized = normalize_repository_relative_path(normalized)
    if not normalized:
        return None
    return normalized


def _resolve_resource_target(
    raw_path: str,
    *,
    file_path: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[str | None, str | None]:
    normalized_path = _normalize_resource_path(
        raw_path,
        file_path=file_path,
        normalize_repository_relative_path=normalize_repository_relative_path,
    )
    if normalized_path is None:
        return None, None
    direct_target = module_index.get(normalized_path)
    if direct_target is None:
        direct_target = module_index.get(f"res://{normalized_path}")
    if direct_target is None:
        direct_target = resolve_suffix_match(
            module_index=module_index,
            suffixes=[normalized_path, f"res://{normalized_path}"],
        )
    target_symbol = PurePosixPath(normalized_path).stem
    return direct_target or normalized_path, target_symbol


def _resolve_named_target(
    target_name: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[str | None, str | None]:
    normalized_target = str(target_name or "").strip()
    if not normalized_target:
        return None, None
    for candidate in (
        f"class:{normalized_target}",
        normalized_target,
    ):
        resolved = module_index.get(candidate)
        if resolved is not None:
            return resolved, normalized_target
    resolved = resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            f"{normalized_target}.gd",
            normalized_target,
        ],
    )
    if resolved is None:
        return None, None
    return resolved, normalized_target


def has_gdscript_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def is_probable_gdscript_source(*, path: Path | PurePosixPath, text: str) -> bool:
    del text
    return has_gdscript_path_hints(path)


def is_probable_operational_entrypoint(*, path: Path | PurePosixPath, text: str) -> bool:
    del text
    candidate_path = PurePosixPath(path)
    if candidate_path.suffix.lower() not in _KNOWN_SUFFIXES:
        return False
    basename = candidate_path.name.lower()
    if basename.startswith("test_") or basename.endswith("_test.gd"):
        return False
    if {part.lower() for part in candidate_path.parts} & _TEST_PATH_PARTS:
        return False
    return True


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_SUFFIXES:
        return set()
    aliases = {
        file_path,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
        path.stem,
        f"res://{file_path}",
        f"res://{str(path.with_suffix(''))}",
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {alias for alias in aliases if alias}
    stripped_text = strip_comments(text)
    class_name = _current_class_name(file_path=file_path, text=stripped_text)
    aliases.update({class_name, f"class:{class_name}"})
    for signal_match in _SIGNAL_DECL_RE.finditer(stripped_text):
        signal_name = str(signal_match.group("name") or "").strip()
        if not signal_name:
            continue
        aliases.update({signal_name, f"signal:{signal_name}", f"{class_name}.{signal_name}"})
    for function_match in _FUNCTION_DECL_RE.finditer(stripped_text):
        function_name = str(function_match.group("name") or "").strip()
        if not function_name:
            continue
        aliases.update({function_name, f"{class_name}.{function_name}"})
    return {alias for alias in aliases if alias}


def _collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[tuple[_Symbol, ...], tuple[_CollectedSymbol, ...]]:
    class_name = _current_class_name(file_path=file_path, text=text)
    final_line = len(text.splitlines()) if text else 1
    class_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "name": class_name,
                "kind": "class",
                "line": _class_line(text),
            },
        ),
        symbol_name=class_name,
        symbol_kind="class",
        start_line=_class_line(text),
        end_line=final_line,
        parent_symbol_id=None,
        signature=class_name,
    )
    symbols: list[_Symbol] = [class_symbol]
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=class_symbol,
            start_line=class_symbol.start_line,
            end_line=final_line,
        )
    ]
    function_matches = list(_FUNCTION_DECL_RE.finditer(text))
    for index, match in enumerate(function_matches):
        function_name = str(match.group("name") or "").strip()
        if not function_name:
            continue
        start_line = _line_number(text, match.start())
        if index + 1 < len(function_matches):
            end_line = max(_line_number(text, function_matches[index + 1].start()) - 1, start_line)
        else:
            end_line = final_line
        function_symbol = _Symbol(
            symbol_id=stable_identifier(
                "sym",
                {
                    "file_path": file_path,
                    "name": function_name,
                    "kind": "function",
                    "line": start_line,
                },
            ),
            symbol_name=function_name,
            symbol_kind="function",
            start_line=start_line,
            end_line=end_line,
            parent_symbol_id=class_symbol.symbol_id,
            signature=function_name,
        )
        symbols.append(function_symbol)
        collected_symbols.append(
            _CollectedSymbol(
                symbol=function_symbol,
                start_line=start_line,
                end_line=end_line,
            )
        )
    return tuple(symbols), tuple(collected_symbols)


def _source_symbol_id_for_line(
    *,
    line_no: int,
    collected_symbols: tuple[_CollectedSymbol, ...],
) -> str | None:
    matching_symbols = [
        collected_symbol
        for collected_symbol in collected_symbols
        if collected_symbol.start_line <= line_no <= collected_symbol.end_line
    ]
    if not matching_symbols:
        return None
    matching_symbols.sort(
        key=lambda collected_symbol: (
            0 if collected_symbol.symbol.symbol_kind == "function" else 1,
            -collected_symbol.start_line,
        )
    )
    return matching_symbols[0].symbol.symbol_id


def _build_resource_bindings(
    *,
    file_path: str,
    text: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> dict[str, _Binding]:
    bindings: dict[str, _Binding] = {}
    for match in _RESOURCE_BINDING_RE.finditer(text):
        alias = str(match.group("alias") or "").strip()
        if not alias:
            continue
        target_file, target_class_name = _resolve_resource_target(
            str(match.group("target") or ""),
            file_path=file_path,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        bindings[alias] = _Binding(
            alias=alias,
            target_file=target_file,
            target_class_name=target_class_name,
        )
    return bindings


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    path = PurePosixPath(file_path)
    if not is_probable_gdscript_source(path=path, text=text):
        return ()
    stripped_text = strip_comments(text)
    dependencies: list[_Dependency] = []
    seen_dependency_keys: set[tuple[str | None, str | None, str, int]] = set()

    for match in _EXTENDS_RE.finditer(stripped_text):
        line_no = _line_number(stripped_text, match.start())
        raw_target = str(match.group("target") or "").strip()
        target_file: str | None = None
        target_symbol: str | None = None
        resource_match = _RESOURCE_PATH_RE.search(raw_target)
        if resource_match is not None:
            target_file, target_symbol = _resolve_resource_target(
                resource_match.group(0),
                file_path=file_path,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
        else:
            extends_target = raw_target.split("#", 1)[0].strip()
            extends_target = re.split(r"\s+", extends_target, maxsplit=1)[0].strip()
            if extends_target:
                target_file, target_symbol = _resolve_named_target(
                    extends_target,
                    module_index=module_index,
                    resolve_suffix_match=resolve_suffix_match,
                )
        if target_file is None and target_symbol is None:
            continue
        dependency_key = (target_file, target_symbol, "extends", line_no)
        if dependency_key in seen_dependency_keys:
            continue
        seen_dependency_keys.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "line": line_no,
                        "target": target_file or target_symbol,
                        "type": "extends",
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_symbol,
                dependency_type="extends",
            )
        )

    for match in _RESOURCE_CALL_RE.finditer(stripped_text):
        line_no = _line_number(stripped_text, match.start())
        target_file, target_symbol = _resolve_resource_target(
            str(match.group("target") or ""),
            file_path=file_path,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        if target_file is None and target_symbol is None:
            continue
        dependency_key = (target_file, target_symbol, "imports", line_no)
        if dependency_key in seen_dependency_keys:
            continue
        seen_dependency_keys.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "line": line_no,
                        "target": target_file or target_symbol,
                        "type": "imports",
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_symbol,
                dependency_type="imports",
            )
        )

    return tuple(dependencies)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    path = PurePosixPath(file_path)
    if not is_probable_gdscript_source(path=path, text=text):
        return (), (), ()
    stripped_text = strip_comments(text)
    class_name = _current_class_name(file_path=file_path, text=stripped_text)
    symbols, collected_symbols = _collect_symbols(
        file_path=file_path,
        text=stripped_text,
        stable_identifier=stable_identifier,
    )
    bindings = _build_resource_bindings(
        file_path=file_path,
        text=stripped_text,
        module_index=module_index,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    dependencies = parse_dependencies_only(
        file_path,
        stripped_text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    reference_candidates: list[_SymbolReferenceCandidate] = []
    seen_reference_keys: set[tuple[str | None, tuple[str, ...], str, int]] = set()

    for match in _QUALIFIED_CALL_RE.finditer(stripped_text):
        owner = str(match.group("owner") or "").strip()
        name = str(match.group("name") or "").strip()
        if (
            not owner
            or not name
            or owner in _RESERVED_REFERENCE_OWNERS
            or name in _RESERVED_REFERENCE_NAMES
        ):
            continue
        line_no = _line_number(stripped_text, match.start())
        source_symbol_id = _source_symbol_id_for_line(
            line_no=line_no,
            collected_symbols=collected_symbols,
        )
        if source_symbol_id is None:
            continue
        target_file: str | None = None
        target_names: tuple[str, ...] = ()
        if owner == "self" or owner == class_name:
            target_file = file_path
            if name == "new":
                target_names = _ordered_names(class_name, f"class:{class_name}")
            else:
                target_names = _ordered_names(name, f"{class_name}.{name}")
        elif owner in bindings:
            binding = bindings[owner]
            target_file = binding.target_file
            if name == "new":
                target_names = _ordered_names(
                    binding.target_class_name or owner,
                    f"class:{binding.target_class_name or owner}",
                )
            else:
                target_names = _ordered_names(name)
        else:
            resolved_file, resolved_symbol = _resolve_named_target(
                owner,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
            if resolved_file is None and resolved_symbol is None:
                continue
            target_file = resolved_file
            if name == "new":
                target_names = _ordered_names(owner, f"class:{owner}", resolved_symbol or "")
            else:
                target_names = _ordered_names(name, f"{owner}.{name}")
        reference_key = (target_file, target_names, source_symbol_id, line_no)
        if not target_names or reference_key in seen_reference_keys:
            continue
        seen_reference_keys.add(reference_key)
        reference_candidates.append(
            _SymbolReferenceCandidate(
                reference_edge_id=stable_identifier(
                    "ref",
                    {
                        "file_path": file_path,
                        "line": line_no,
                        "symbol_id": source_symbol_id,
                        "target": ".".join(target_names),
                        "type": "references_symbol",
                    },
                ),
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=target_file,
                target_names=target_names,
                reference_type="references_symbol",
            )
        )

    return symbols, dependencies, tuple(reference_candidates)

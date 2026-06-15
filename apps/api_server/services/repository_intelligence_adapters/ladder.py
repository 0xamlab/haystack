from __future__ import annotations

import html
import re
from bisect import bisect_right
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = Callable[[str, Any], str]

_KNOWN_SUFFIXES = frozenset({".l5x"})
_XML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_RSLOGIX_ROOT_RE = re.compile(r"<RSLogix5000Content\b", re.IGNORECASE)
_RSLOGIX_ROOT_TAG_RE = re.compile(
    r"<RSLogix5000Content\b(?P<attrs>[^>]*)>",
    re.IGNORECASE,
)
_RLL_HINT_RE = re.compile(r"<Routine\b[^>]*\bType=(['\"])RLL\1", re.IGNORECASE)
_RLL_CONTENT_RE = re.compile(r"<RLLContent\b", re.IGNORECASE)
_XML_ATTR_RE = re.compile(
    r"(?P<name>[A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*(?P<quote>['\"])(?P<value>.*?)(?P=quote)",
    re.DOTALL,
)
_CONTROLLER_RE = re.compile(r"<Controller\b(?P<attrs>[^>]*)>", re.IGNORECASE)
_PROGRAM_RE = re.compile(
    r"<Program\b(?P<attrs>[^>]*)>(?P<body>.*?)</Program>",
    re.IGNORECASE | re.DOTALL,
)
_ADD_ON_INSTRUCTION_RE = re.compile(
    r"<AddOnInstructionDefinition\b(?P<attrs>[^>]*)>(?P<body>.*?)</AddOnInstructionDefinition>",
    re.IGNORECASE | re.DOTALL,
)
_ROUTINE_RE = re.compile(
    r"<Routine\b(?P<attrs>[^>]*)>(?P<body>.*?)</Routine>",
    re.IGNORECASE | re.DOTALL,
)
_RUNG_RE = re.compile(r"<Rung\b[^>]*>(?P<body>.*?)</Rung>", re.IGNORECASE | re.DOTALL)
_TEXT_RE = re.compile(r"<Text\b[^>]*>(?P<body>.*?)</Text>", re.IGNORECASE | re.DOTALL)
_JSR_TARGET_RE = re.compile(
    r"\bJSR\s*\(\s*(?P<target>[A-Za-z_][A-Za-z0-9_.$-]*)",
    re.IGNORECASE,
)
_INSTRUCTION_CALL_RE = re.compile(
    r"(?<![\w.])(?P<name>[A-Za-z_][A-Za-z0-9_.$-]*)\s*\(",
    re.IGNORECASE,
)
_OPERATIONAL_TARGET_TYPES = frozenset(
    {"addoninstructiondefinition", "controller", "program", "routine"}
)
_ROOT_TAG_SCAN_CHARS = 4096


@dataclass(frozen=True)
class _CollectedSymbol:
    symbol: _Symbol
    qualified_names: tuple[str, ...]
    body_text: str


def _strip_xml_comments(text: str) -> str:
    if "<!--" not in text:
        return text
    return _strip_xml_comments_cached(text)


@lru_cache(maxsize=2048)
def _strip_xml_comments_cached(text: str) -> str:
    return _XML_COMMENT_RE.sub("", text)


def _normalize_name(raw_value: str) -> str:
    return str(raw_value or "").strip().strip('"').strip("'")


def _root_tag_scan_text(text: str, *, stripped_text: str | None = None) -> str:
    if stripped_text is not None:
        return stripped_text
    head_text = text[:_ROOT_TAG_SCAN_CHARS]
    if "<!--" in head_text:
        return _strip_xml_comments(head_text)
    return head_text


def _parse_attrs(attrs_text: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for match in _XML_ATTR_RE.finditer(attrs_text):
        attrs[str(match.group("name") or "").strip().lower()] = _normalize_name(
            str(match.group("value") or "")
        )
    return attrs


@lru_cache(maxsize=4096)
def _line_start_offsets(text: str) -> tuple[int, ...]:
    offsets = [0]
    for index, character in enumerate(text):
        if character == "\n":
            offsets.append(index + 1)
    return tuple(offsets)


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return bisect_right(_line_start_offsets(text), offset)


def _ordered_names(*values: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        normalized = _normalize_name(raw_value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def _normalized_text_body(raw_value: str) -> str:
    value = str(raw_value or "").strip()
    if value.startswith("<![CDATA[") and value.endswith("]]>"):
        value = value[9:-3]
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def _rung_texts(section_body: str) -> tuple[str, ...]:
    texts: list[str] = []
    for rung_match in _RUNG_RE.finditer(section_body):
        text_match = _TEXT_RE.search(str(rung_match.group("body") or ""))
        if text_match is None:
            continue
        normalized = _normalized_text_body(str(text_match.group("body") or ""))
        if normalized:
            texts.append(normalized)
    return tuple(texts)


def is_probable_ladder_source(
    *,
    path: Path,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    if path.suffix.lower() != ".l5x":
        return False
    normalized_text = _root_tag_scan_text(text, stripped_text=stripped_text)
    return bool(_RSLOGIX_ROOT_RE.search(normalized_text))


def target_type_for_text(text: str, *, stripped_text: str | None = None) -> str:
    normalized_text = _root_tag_scan_text(text, stripped_text=stripped_text)
    root_match = _RSLOGIX_ROOT_TAG_RE.search(normalized_text)
    if root_match is None:
        return ""
    attrs = _parse_attrs(str(root_match.group("attrs") or ""))
    return _normalize_name(attrs.get("targettype", "")).lower()


def is_probable_operational_entrypoint(
    *,
    path: Path,
    text: str,
    stripped_text: str | None = None,
) -> bool:
    target_type = target_type_for_text(text, stripped_text=stripped_text)
    if target_type in _OPERATIONAL_TARGET_TYPES:
        return True
    if target_type:
        return False
    normalized_text = stripped_text if stripped_text is not None else _strip_xml_comments(text)
    if not is_probable_ladder_source(path=path, text=text, stripped_text=normalized_text):
        return False
    return bool(_RLL_HINT_RE.search(normalized_text) or _RLL_CONTENT_RE.search(normalized_text))


def _collect_routine_symbols(
    *,
    full_text: str,
    file_path: str,
    container_name: str | None,
    controller_name: str | None,
    container_body: str,
    body_offset: int,
    stable_identifier: StableIdentifier,
) -> list[_CollectedSymbol]:
    collected: list[_CollectedSymbol] = []
    for routine_match in _ROUTINE_RE.finditer(container_body):
        attrs = _parse_attrs(str(routine_match.group("attrs") or ""))
        routine_name = _normalize_name(attrs.get("name", ""))
        if not routine_name:
            continue
        routine_body = str(routine_match.group("body") or "")
        routine_type = _normalize_name(attrs.get("type", "")).upper()
        rung_text = "\n".join(_rung_texts(routine_body))
        if routine_type != "RLL" and not rung_text and not _RLL_CONTENT_RE.search(routine_body):
            continue
        global_start = body_offset + routine_match.start()
        global_end = body_offset + routine_match.end()
        start_line = _line_number(full_text, global_start)
        end_line = max(_line_number(full_text, global_end), start_line)
        qualified_names = _ordered_names(
            routine_name,
            f"{container_name}.{routine_name}" if container_name else "",
            (
                f"{controller_name}.{container_name}.{routine_name}"
                if controller_name and container_name
                else ""
            ),
        )
        collected.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "name": routine_name,
                            "kind": "function",
                            "line": start_line,
                        },
                    ),
                    symbol_name=routine_name,
                    symbol_kind="function",
                    start_line=start_line,
                    end_line=end_line,
                    parent_symbol_id=None,
                    signature=qualified_names[0] if qualified_names else routine_name,
                ),
                qualified_names=qualified_names,
                body_text=rung_text,
            )
        )
    return collected


def _is_aliasable_routine(*, routine_type: str, routine_body: str) -> bool:
    return bool(
        routine_type == "RLL"
        or _RLL_CONTENT_RE.search(routine_body)
        or _RUNG_RE.search(routine_body)
    )


def _collect_routine_aliases(
    *,
    container_name: str | None,
    controller_name: str | None,
    container_body: str,
) -> tuple[tuple[str, ...], ...]:
    qualified_names: list[tuple[str, ...]] = []
    for routine_match in _ROUTINE_RE.finditer(container_body):
        attrs = _parse_attrs(str(routine_match.group("attrs") or ""))
        routine_name = _normalize_name(attrs.get("name", ""))
        if not routine_name:
            continue
        routine_body = str(routine_match.group("body") or "")
        routine_type = _normalize_name(attrs.get("type", "")).upper()
        if not _is_aliasable_routine(routine_type=routine_type, routine_body=routine_body):
            continue
        qualified_names.append(
            _ordered_names(
                routine_name,
                f"{container_name}.{routine_name}" if container_name else "",
                (
                    f"{controller_name}.{container_name}.{routine_name}"
                    if controller_name and container_name
                    else ""
                ),
            )
        )
    return tuple(qualified_names)


def _symbol_aliases(stripped_text: str) -> tuple[str, ...]:
    aliases: list[str] = []
    seen_aliases: set[str] = set()

    def _add_names(*names: str) -> None:
        for name in _ordered_names(*names):
            if name in seen_aliases:
                continue
            seen_aliases.add(name)
            aliases.append(name)

    controller_name: str | None = None
    controller_match = _CONTROLLER_RE.search(stripped_text)
    if controller_match is not None:
        controller_attrs = _parse_attrs(str(controller_match.group("attrs") or ""))
        controller_name = _normalize_name(controller_attrs.get("name", ""))
        if controller_name:
            _add_names(controller_name)

    for program_match in _PROGRAM_RE.finditer(stripped_text):
        attrs = _parse_attrs(str(program_match.group("attrs") or ""))
        program_name = _normalize_name(attrs.get("name", ""))
        if not program_name:
            continue
        _add_names(
            program_name,
            f"{controller_name}.{program_name}" if controller_name else "",
        )
        for qualified_names in _collect_routine_aliases(
            container_name=program_name,
            controller_name=controller_name,
            container_body=str(program_match.group("body") or ""),
        ):
            _add_names(*qualified_names)

    for instruction_match in _ADD_ON_INSTRUCTION_RE.finditer(stripped_text):
        attrs = _parse_attrs(str(instruction_match.group("attrs") or ""))
        instruction_name = _normalize_name(attrs.get("name", ""))
        if not instruction_name:
            continue
        _add_names(
            instruction_name,
            f"{controller_name}.{instruction_name}" if controller_name else "",
        )
        for qualified_names in _collect_routine_aliases(
            container_name=instruction_name,
            controller_name=controller_name,
            container_body=str(instruction_match.group("body") or ""),
        ):
            _add_names(*qualified_names)

    return tuple(aliases)


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> tuple[_CollectedSymbol, ...]:
    stripped_text = _strip_xml_comments(text)
    collected: list[_CollectedSymbol] = []
    controller_name: str | None = None
    controller_match = _CONTROLLER_RE.search(stripped_text)
    if controller_match is not None:
        controller_attrs = _parse_attrs(str(controller_match.group("attrs") or ""))
        controller_name = _normalize_name(controller_attrs.get("name", ""))
        if controller_name:
            controller_line = _line_number(stripped_text, controller_match.start())
            collected.append(
                _CollectedSymbol(
                    symbol=_Symbol(
                        symbol_id=stable_identifier(
                            "sym",
                            {
                                "file_path": file_path,
                                "name": controller_name,
                                "kind": "module",
                                "line": controller_line,
                            },
                        ),
                        symbol_name=controller_name,
                        symbol_kind="module",
                        start_line=controller_line,
                        end_line=controller_line,
                        parent_symbol_id=None,
                        signature=controller_name,
                    ),
                    qualified_names=_ordered_names(controller_name),
                    body_text="",
                )
            )
    for program_match in _PROGRAM_RE.finditer(stripped_text):
        attrs = _parse_attrs(str(program_match.group("attrs") or ""))
        program_name = _normalize_name(attrs.get("name", ""))
        if not program_name:
            continue
        program_start = _line_number(stripped_text, program_match.start())
        program_end = max(_line_number(stripped_text, program_match.end()), program_start)
        collected.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "name": program_name,
                            "kind": "program",
                            "line": program_start,
                        },
                    ),
                    symbol_name=program_name,
                    symbol_kind="program",
                    start_line=program_start,
                    end_line=program_end,
                    parent_symbol_id=None,
                    signature=program_name,
                ),
                qualified_names=_ordered_names(
                    program_name,
                    f"{controller_name}.{program_name}" if controller_name else "",
                ),
                body_text="",
            )
        )
        collected.extend(
            _collect_routine_symbols(
                full_text=stripped_text,
                file_path=file_path,
                container_name=program_name,
                controller_name=controller_name,
                container_body=str(program_match.group("body") or ""),
                body_offset=program_match.start("body"),
                stable_identifier=stable_identifier,
            )
        )
    for instruction_match in _ADD_ON_INSTRUCTION_RE.finditer(stripped_text):
        attrs = _parse_attrs(str(instruction_match.group("attrs") or ""))
        instruction_name = _normalize_name(attrs.get("name", ""))
        if not instruction_name:
            continue
        instruction_body = str(instruction_match.group("body") or "")
        instruction_start = _line_number(stripped_text, instruction_match.start())
        instruction_end = max(
            _line_number(stripped_text, instruction_match.end()),
            instruction_start,
        )
        routine_symbols = _collect_routine_symbols(
            full_text=stripped_text,
            file_path=file_path,
            container_name=instruction_name,
            controller_name=controller_name,
            container_body=instruction_body,
            body_offset=instruction_match.start("body"),
            stable_identifier=stable_identifier,
        )
        collected.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "name": instruction_name,
                            "kind": "function",
                            "line": instruction_start,
                        },
                    ),
                    symbol_name=instruction_name,
                    symbol_kind="function",
                    start_line=instruction_start,
                    end_line=instruction_end,
                    parent_symbol_id=None,
                    signature=instruction_name,
                ),
                qualified_names=_ordered_names(
                    instruction_name,
                    f"{controller_name}.{instruction_name}" if controller_name else "",
                ),
                body_text="\n".join(
                    symbol_entry.body_text
                    for symbol_entry in routine_symbols
                    if symbol_entry.body_text
                ),
            )
        )
        collected.extend(routine_symbols)
    return tuple(
        sorted(
            collected,
            key=lambda entry: (
                int(entry.symbol.start_line),
                str(entry.symbol.symbol_kind),
                str(entry.symbol.symbol_name),
            ),
        )
    )


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_SUFFIXES:
        return set()
    aliases = {
        file_path,
        path.stem,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
    }
    if text is None:
        try:
            text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
    stripped_text = _strip_xml_comments(text) if text else ""
    if not is_probable_ladder_source(
        path=Path(file_path),
        text=text,
        stripped_text=stripped_text,
    ):
        return {alias for alias in aliases if alias}
    aliases.update(_symbol_aliases(stripped_text))
    return {alias for alias in aliases if alias}


def _resolve_target_file(target_name: str, *, module_index: dict[str, str]) -> str | None:
    normalized = _normalize_name(target_name)
    if not normalized:
        return None
    for candidate in (normalized, normalized.replace("::", ".")):
        resolved = module_index.get(candidate)
        if resolved is not None:
            return resolved
    lowered_target = normalized.lower()
    for alias, resolved in module_index.items():
        if alias.lower() == lowered_target:
            return resolved
    return None


def _reference_targets(body_text: str) -> tuple[str, ...]:
    targets: list[str] = []
    seen: set[str] = set()
    for match in _JSR_TARGET_RE.finditer(body_text):
        target_name = _normalize_name(str(match.group("target") or ""))
        canonical_name = target_name.lower()
        if not target_name or canonical_name in seen:
            continue
        seen.add(canonical_name)
        targets.append(target_name)
    for match in _INSTRUCTION_CALL_RE.finditer(body_text):
        target_name = _normalize_name(str(match.group("name") or ""))
        canonical_name = target_name.lower()
        if not target_name or canonical_name == "jsr" or canonical_name in seen:
            continue
        seen.add(canonical_name)
        targets.append(target_name)
    return tuple(targets)


def _collect_references(
    *,
    file_path: str,
    symbols: tuple[_CollectedSymbol, ...],
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
) -> tuple[tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    symbol_lookup: dict[str, list[_Symbol]] = defaultdict(list)
    for symbol_entry in symbols:
        symbol_lookup[symbol_entry.symbol.symbol_name.lower()].append(symbol_entry.symbol)

    dependencies: dict[str, _Dependency] = {}
    references: dict[str, _SymbolReferenceCandidate] = {}
    for symbol_entry in symbols:
        if not symbol_entry.body_text:
            continue
        source_symbol = symbol_entry.symbol
        for target_name in _reference_targets(symbol_entry.body_text):
            canonical_target = target_name.lower()
            if canonical_target == source_symbol.symbol_name.lower():
                continue
            local_matches = tuple(symbol_lookup.get(canonical_target, ()))
            target_file: str | None = None
            target_names: tuple[str, ...] = ()
            if local_matches:
                target_file = file_path
                target_names = _ordered_names(*(match.symbol_name for match in local_matches))
            else:
                target_file = _resolve_target_file(target_name, module_index=module_index)
                if target_file is None:
                    continue
                target_names = _ordered_names(target_name)
                if target_file == file_path:
                    continue
            if not target_names:
                continue
            reference_edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": source_symbol.symbol_id,
                    "target_file": target_file,
                    "target_names": target_names,
                    "type": "references_symbol",
                },
            )
            references.setdefault(
                reference_edge_id,
                _SymbolReferenceCandidate(
                    reference_edge_id=reference_edge_id,
                    source_symbol_id=source_symbol.symbol_id,
                    source_file=file_path,
                    target_symbol_id=None,
                    target_file=target_file,
                    target_names=target_names,
                    reference_type="references_symbol",
                ),
            )
            if target_file == file_path:
                continue
            dependency_edge_id = stable_identifier(
                "dep",
                {
                    "file_path": file_path,
                    "target_file": target_file,
                    "target_names": target_names,
                    "type": "references",
                },
            )
            dependencies.setdefault(
                dependency_edge_id,
                _Dependency(
                    dependency_edge_id=dependency_edge_id,
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=target_names[0],
                    dependency_type="references",
                ),
            )
    return (
        tuple(dependencies[key] for key in sorted(dependencies)),
        tuple(references[key] for key in sorted(references)),
    )


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
) -> tuple[_Dependency, ...]:
    symbols = collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    )
    dependencies, _references = _collect_references(
        file_path=file_path,
        symbols=symbols,
        module_index=module_index,
        stable_identifier=stable_identifier,
    )
    return dependencies


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    collected_symbols = collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    )
    dependencies, references = _collect_references(
        file_path=file_path,
        symbols=collected_symbols,
        module_index=module_index,
        stable_identifier=stable_identifier,
    )
    return (
        tuple(entry.symbol for entry in collected_symbols),
        dependencies,
        references,
    )

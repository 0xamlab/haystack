from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    smalltalk_primitives as repository_smalltalk_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_smalltalk_primitives.StableIdentifier

_CLASS_MESSAGE_SEND_RE = repository_smalltalk_primitives._CLASS_MESSAGE_SEND_RE
_TONEL_METHOD_RE = repository_smalltalk_primitives._TONEL_METHOD_RE
class_name_for_path = repository_smalltalk_primitives.class_name_for_path
filetree_selector_from_text = repository_smalltalk_primitives.filetree_selector_from_text
has_smalltalk_path_hints = repository_smalltalk_primitives.has_smalltalk_path_hints
is_class_side_header = repository_smalltalk_primitives.is_class_side_header
is_probable_smalltalk_source = (
    repository_smalltalk_primitives.is_probable_smalltalk_source
)
normalize_selector = repository_smalltalk_primitives.normalize_selector
owner_name_from_header = repository_smalltalk_primitives.owner_name_from_header
package_name_for_path = repository_smalltalk_primitives.package_name_for_path
path_aliases = repository_smalltalk_primitives.path_aliases
selector_from_header = repository_smalltalk_primitives.selector_from_header
strip_comments = repository_smalltalk_primitives.strip_comments
tonel_metadata = repository_smalltalk_primitives.tonel_metadata


def _line_number(text: str, offset: int) -> int:
    bounded_offset = max(0, min(offset, len(text)))
    return text.count("\n", 0, bounded_offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _lookup_target_file(module_index: dict[str, str], target_name: str) -> str | None:
    normalized_target = str(target_name or "").strip()
    if not normalized_target:
        return None
    return module_index.get(normalized_target) or module_index.get(normalized_target.lower())


def _symbol_from_entry(entry: dict[str, Any]) -> _Symbol:
    return _Symbol(
        symbol_id=str(entry["symbol_id"]),
        symbol_name=str(entry["symbol_name"]),
        symbol_kind=str(entry["symbol_kind"]),
        start_line=int(entry["start_line"]),
        end_line=int(entry["end_line"]),
        parent_symbol_id=(
            str(entry["parent_symbol_id"])
            if entry["parent_symbol_id"] is not None
            else None
        ),
        signature=str(entry["signature"]) if entry["signature"] is not None else None,
    )


def _dependency_from_entry(entry: dict[str, Any]) -> _Dependency:
    return _Dependency(
        dependency_edge_id=str(entry["dependency_edge_id"]),
        source_file=str(entry["source_file"]),
        target_file=str(entry["target_file"]) if entry["target_file"] is not None else None,
        target_symbol=(
            str(entry["target_symbol"]) if entry["target_symbol"] is not None else None
        ),
        dependency_type=str(entry["dependency_type"]),
    )


def _symbol_reference_from_entry(entry: dict[str, Any]) -> _SymbolReferenceCandidate:
    return _SymbolReferenceCandidate(
        reference_edge_id=str(entry["reference_edge_id"]),
        source_symbol_id=str(entry["source_symbol_id"]),
        source_file=str(entry["source_file"]),
        target_symbol_id=None,
        target_file=str(entry["target_file"]) if entry["target_file"] is not None else None,
        target_names=tuple(str(name) for name in entry["target_names"]),
        reference_type=str(entry["reference_type"]),
    )


def _class_message_entries(
    *,
    text: str,
    source_file: str,
    module_index: dict[str, str],
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen_entries: set[tuple[str | None, str | None]] = set()
    for match in _CLASS_MESSAGE_SEND_RE.finditer(text):
        target_class = str(match.group("class_name") or "").strip()
        selector = normalize_selector(str(match.group("message") or ""))
        if not target_class:
            continue
        target_file = _lookup_target_file(module_index, target_class)
        target_symbol = selector or target_class
        key = (target_file, target_symbol)
        if key in seen_entries:
            continue
        seen_entries.add(key)
        entries.append(
            {
                "dependency_edge_id": stable_identifier(
                    "dep",
                    {
                        "file_path": source_file,
                        "line": _line_number(text, match.start()),
                        "target_class": target_class,
                        "target_symbol": target_symbol,
                        "type": "references",
                    },
                ),
                "source_file": source_file,
                "target_file": target_file,
                "target_symbol": target_symbol,
                "dependency_type": "references",
            }
        )
    return entries


def _collect_symbol_entries(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    source_text = strip_comments(text)
    metadata = tonel_metadata(source_text)
    symbol_entries: list[dict[str, Any]] = []
    file_line_count = _line_count(source_text)

    package_name = (
        str(metadata.get("package") or metadata.get("category") or "").strip()
        or package_name_for_path(file_path)
    )
    owner_class = str(metadata.get("name") or "").strip() or class_name_for_path(file_path)
    class_symbol_id: str | None = None

    if metadata.get("kind") == "package" and package_name:
        symbol_entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": package_name,
                        "kind": "module",
                        "line": 1,
                    },
                ),
                "symbol_name": package_name,
                "symbol_kind": "module",
                "start_line": 1,
                "end_line": file_line_count,
                "signature": f"Package {package_name}",
                "parent_symbol_id": None,
            }
        )

    if metadata.get("kind") == "class" and owner_class:
        class_symbol_id = stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "name": owner_class,
                "kind": "type",
                "line": 1,
            },
        )
        symbol_entries.append(
            {
                "symbol_id": class_symbol_id,
                "symbol_name": owner_class,
                "symbol_kind": "type",
                "start_line": 1,
                "end_line": file_line_count,
                "signature": f"Class {owner_class}",
                "parent_symbol_id": None,
            }
        )

    tonel_method_matches = list(_TONEL_METHOD_RE.finditer(source_text))
    if tonel_method_matches:
        for index, match in enumerate(tonel_method_matches):
            header = str(match.group("header") or "").strip()
            selector = selector_from_header(header)
            owner_name = owner_name_from_header(header) or owner_class
            if not selector:
                continue
            start_line = _line_number(source_text, match.start())
            end_line = (
                _line_number(source_text, tonel_method_matches[index + 1].start()) - 1
                if index + 1 < len(tonel_method_matches)
                else file_line_count
            )
            symbol_entries.append(
                {
                    "symbol_id": stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "name": selector,
                            "kind": "method",
                            "line": start_line,
                            "owner": owner_name,
                            "class_side": is_class_side_header(header),
                        },
                    ),
                    "symbol_name": selector,
                    "symbol_kind": "method",
                    "start_line": start_line,
                    "end_line": max(start_line, end_line),
                    "signature": header,
                    "parent_symbol_id": class_symbol_id if owner_name == owner_class else None,
                }
            )
        return symbol_entries

    selector = filetree_selector_from_text(source_text)
    if owner_class and selector:
        symbol_entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": selector,
                        "kind": "method",
                        "line": 1,
                        "owner": owner_class,
                    },
                ),
                "symbol_name": selector,
                "symbol_kind": "method",
                "start_line": 1,
                "end_line": file_line_count,
                "signature": selector,
                "parent_symbol_id": None,
            }
        )
    return symbol_entries


def _method_reference_contexts(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> dict[str, tuple[int, str]]:
    source_text = strip_comments(text)
    contexts: dict[str, tuple[int, str]] = {}
    owner_class = str(tonel_metadata(source_text).get("name") or "").strip() or class_name_for_path(
        file_path
    )
    tonel_method_matches = list(_TONEL_METHOD_RE.finditer(source_text))
    if tonel_method_matches:
        for index, match in enumerate(tonel_method_matches):
            header = str(match.group("header") or "").strip()
            selector = selector_from_header(header)
            owner_name = owner_name_from_header(header) or owner_class
            if not selector:
                continue
            body_start_offset = match.end()
            body_end_offset = (
                tonel_method_matches[index + 1].start()
                if index + 1 < len(tonel_method_matches)
                else len(source_text)
            )
            body_start_line = _line_number(source_text, body_start_offset)
            symbol_id = stable_identifier(
                "sym",
                {
                    "file_path": file_path,
                    "name": selector,
                    "kind": "method",
                    "line": _line_number(source_text, match.start()),
                    "owner": owner_name,
                    "class_side": is_class_side_header(header),
                },
            )
            contexts[symbol_id] = (body_start_line, source_text[body_start_offset:body_end_offset])
        return contexts

    selector = filetree_selector_from_text(source_text)
    if owner_class and selector:
        lines = source_text.splitlines()
        nonempty_line_indexes = [index for index, line in enumerate(lines) if line.strip()]
        header_line_index = nonempty_line_indexes[1] if len(nonempty_line_indexes) >= 2 else 0
        symbol_id = stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "name": selector,
                "kind": "method",
                "line": 1,
                "owner": owner_class,
            },
        )
        contexts[symbol_id] = (
            header_line_index + 2,
            "\n".join(lines[header_line_index + 1 :]),
        )
    return contexts


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    aliases = set(path_aliases(file_path))
    try:
        text = (root_path / PurePosixPath(file_path)).read_text(
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return aliases
    if not is_probable_smalltalk_source(path=Path(file_path), text=text):
        return aliases
    metadata = tonel_metadata(text)
    package_name = (
        str(metadata.get("package") or metadata.get("category") or "").strip()
        or package_name_for_path(file_path)
    )
    owner_class = str(metadata.get("name") or "").strip() or class_name_for_path(file_path)
    if package_name:
        aliases.add(package_name)
        aliases.add(package_name.lower())
    if owner_class:
        aliases.add(owner_class)
        aliases.add(owner_class.lower())
        if package_name:
            aliases.add(f"{package_name}.{owner_class}")
            aliases.add(f"{package_name.lower()}.{owner_class.lower()}")
    for symbol_entry in _collect_symbol_entries(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    ):
        symbol_name = str(symbol_entry["symbol_name"])
        aliases.add(symbol_name)
        aliases.add(symbol_name.lower())
        if owner_class and symbol_entry["symbol_kind"] == "method":
            aliases.add(f"{owner_class}.{symbol_name}")
            aliases.add(f"{owner_class.lower()}.{symbol_name.lower()}")
    return {alias for alias in aliases if alias}


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
) -> tuple[_Dependency, ...]:
    if not is_probable_smalltalk_source(path=Path(file_path), text=text):
        return ()
    source_text = strip_comments(text)
    metadata = tonel_metadata(source_text)
    dependency_entries: list[dict[str, Any]] = []
    seen_dependency_keys: set[tuple[str | None, str | None, str]] = set()

    owner_class = str(metadata.get("name") or "").strip() or class_name_for_path(file_path)
    superclass_name = str(metadata.get("superclass") or "").strip()
    if metadata.get("kind") == "class" and superclass_name:
        target_file = _lookup_target_file(module_index, superclass_name)
        dependency_key = (target_file, superclass_name, "inherits")
        if dependency_key not in seen_dependency_keys:
            seen_dependency_keys.add(dependency_key)
            dependency_entries.append(
                {
                    "dependency_edge_id": stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target_class": superclass_name,
                            "type": "inherits",
                        },
                    ),
                    "source_file": file_path,
                    "target_file": target_file,
                    "target_symbol": superclass_name,
                    "dependency_type": "inherits",
                }
            )

    for dependency_entry in _class_message_entries(
        text=source_text,
        source_file=file_path,
        module_index=module_index,
        stable_identifier=stable_identifier,
    ):
        dependency_key = (
            dependency_entry["target_file"],
            dependency_entry["target_symbol"],
            dependency_entry["dependency_type"],
        )
        if dependency_key in seen_dependency_keys:
            continue
        target_file = str(dependency_entry["target_file"] or "")
        if target_file == file_path and owner_class:
            continue
        seen_dependency_keys.add(dependency_key)
        dependency_entries.append(dependency_entry)
    return tuple(_dependency_from_entry(entry) for entry in dependency_entries)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    if not is_probable_smalltalk_source(path=Path(file_path), text=text):
        return (), (), ()
    symbol_entries = tuple(
        _collect_symbol_entries(
            file_path=file_path,
            text=text,
            stable_identifier=stable_identifier,
        )
    )
    method_reference_contexts = _method_reference_contexts(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    )
    symbols = tuple(_symbol_from_entry(entry) for entry in symbol_entries)
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
    )

    reference_entries: list[dict[str, Any]] = []
    seen_reference_keys: set[tuple[str, str | None, tuple[str, ...], str]] = set()
    for symbol_entry in symbol_entries:
        if str(symbol_entry["symbol_kind"]) != "method":
            continue
        symbol_id = str(symbol_entry["symbol_id"])
        body_start_line, body_text = method_reference_contexts.get(
            symbol_id,
            (int(symbol_entry["start_line"]), ""),
        )
        if not body_text.strip():
            continue
        for match in _CLASS_MESSAGE_SEND_RE.finditer(body_text):
            target_class = str(match.group("class_name") or "").strip()
            selector = normalize_selector(str(match.group("message") or ""))
            if not target_class:
                continue
            target_file = _lookup_target_file(module_index, target_class)
            target_names = tuple(name for name in (selector, target_class) if name)
            reference_key = (
                str(symbol_entry["symbol_id"]),
                target_file,
                target_names,
                "references_symbol",
            )
            if reference_key in seen_reference_keys:
                continue
            seen_reference_keys.add(reference_key)
            reference_entries.append(
                {
                    "reference_edge_id": stable_identifier(
                        "ref",
                        {
                            "file_path": file_path,
                            "line": body_start_line + _line_number(body_text, match.start()) - 1,
                            "source_symbol": symbol_entry["symbol_name"],
                            "target_class": target_class,
                            "target_selector": selector,
                            "type": "references_symbol",
                        },
                    ),
                    "source_symbol_id": symbol_id,
                    "source_file": file_path,
                    "target_file": target_file,
                    "target_names": target_names,
                    "reference_type": "references_symbol",
                }
            )
    return (
        symbols,
        dependencies,
        tuple(_symbol_reference_from_entry(entry) for entry in reference_entries),
    )

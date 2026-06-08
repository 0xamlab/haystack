from __future__ import annotations

import html
import re
from collections.abc import Callable
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

_KNOWN_SUFFIXES = frozenset({".ctl", ".lvclass", ".lvlib", ".lvproj", ".vi", ".vim", ".vit"})
_XML_SUFFIXES = frozenset({".lvclass", ".lvlib", ".lvproj"})
_BINARY_SUFFIXES = frozenset({".ctl", ".vi", ".vim", ".vit"})
_XML_ROOT_BY_SUFFIX = {
    ".lvclass": "lvclass",
    ".lvlib": "library",
    ".lvproj": "project",
}
_XML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_BINARY_PROPERTY_RE = re.compile(
    r"<Property\b[^>]*\bType=(['\"])Bin\1[^>]*>.*?</Property>",
    re.IGNORECASE | re.DOTALL,
)
_ROOT_RE = re.compile(r"<(?P<name>Project|Library|LVClass)\b", re.IGNORECASE)
_ITEM_RE = re.compile(r"<Item\b(?P<attrs>[^>]*)>", re.IGNORECASE)
_ATTR_RE = re.compile(
    r"(?P<name>[A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*(?P<quote>['\"])(?P<value>.*?)(?P=quote)",
    re.DOTALL,
)
_BINARY_MAGIC_RE = re.compile(r"^\ufeff?RSRC(?:\r?\n)", re.IGNORECASE)


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


def _normalize_name(raw_value: str) -> str:
    return html.unescape(str(raw_value or "").strip().strip('"').strip("'"))


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


def _line_number(text: str, offset: int) -> int:
    if offset <= 0:
        return 1
    return text.count("\n", 0, offset) + 1


def _strip_nonstructural_xml(text: str) -> str:
    without_comments = _XML_COMMENT_RE.sub(
        lambda match: _replace_with_spaces(str(match.group(0) or "")),
        text,
    )
    return _BINARY_PROPERTY_RE.sub(
        lambda match: _replace_with_spaces(str(match.group(0) or "")),
        without_comments,
    )


def _xml_root_name(text: str) -> str:
    normalized_text = _strip_nonstructural_xml(str(text or "")).lstrip("\ufeff").lstrip()
    match = _ROOT_RE.search(normalized_text)
    if match is None:
        return ""
    return str(match.group("name") or "").strip().lower()


def _parse_attrs(attrs_text: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for match in _ATTR_RE.finditer(attrs_text):
        attrs[str(match.group("name") or "").strip().lower()] = _normalize_name(
            str(match.group("value") or "")
        )
    return attrs


def _artifact_symbol_kind(path: PurePosixPath) -> str:
    suffix = path.suffix.lower()
    if suffix == ".ctl":
        return "type"
    if suffix == ".lvclass":
        return "class"
    if suffix in {".lvlib", ".lvproj"}:
        return "module"
    return "function"


def _item_target_names(*, item_name: str, target_file: str) -> tuple[str, ...]:
    target_path = PurePosixPath(target_file)
    return _ordered_names(
        _normalize_name(item_name),
        _normalize_name(PurePosixPath(item_name).stem),
        target_path.stem,
    )


def is_probable_labview_source(*, path: PurePosixPath | Path | str, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    suffix = normalized_path.suffix.lower()
    if suffix not in _KNOWN_SUFFIXES:
        return False
    if suffix in _XML_SUFFIXES:
        return _xml_root_name(text) == _XML_ROOT_BY_SUFFIX[suffix]
    if suffix in _BINARY_SUFFIXES:
        normalized_text = str(text or "").lstrip("\ufeff")
        return bool(_BINARY_MAGIC_RE.match(normalized_text))
    return False


def project_item_entries(
    text: str,
    *,
    manifest_path: str,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> tuple[dict[str, Any], ...]:
    current_path = PurePosixPath(manifest_path)
    current_dir = current_path.parent
    stripped_text = _strip_nonstructural_xml(str(text or ""))
    entries: list[dict[str, Any]] = []
    for match in _ITEM_RE.finditer(stripped_text):
        attrs = _parse_attrs(str(match.group("attrs") or ""))
        raw_url = str(attrs.get("url") or "").strip()
        if not raw_url:
            continue
        resolved_path = normalize_repository_relative_path(str(current_dir / raw_url))
        if not resolved_path:
            continue
        target_suffix = PurePosixPath(resolved_path).suffix.lower()
        if target_suffix not in _KNOWN_SUFFIXES:
            continue
        entries.append(
            {
                "item_name": attrs.get("name") or PurePosixPath(resolved_path).name,
                "item_type": str(attrs.get("type") or "").strip(),
                "target_file": resolved_path,
                "line": _line_number(stripped_text, match.start()),
            }
        )
    return tuple(entries)


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
        path.stem,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if not is_probable_labview_source(path=path, text=text):
        return {alias for alias in aliases if alias}
    return {alias for alias in aliases if alias}


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_repository_relative_path(
        str(PurePosixPath(current_file).parent / import_target)
    )
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    return resolve_suffix_match(module_index=module_index, suffixes=[normalized_target])


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
    if (
        not is_probable_labview_source(path=path, text=text)
        or path.suffix.lower() not in _XML_SUFFIXES
    ):
        return ()
    dependencies: list[_Dependency] = []
    seen_dependencies: set[tuple[str | None, str | None, str]] = set()
    for entry in project_item_entries(
        text,
        manifest_path=file_path,
        normalize_repository_relative_path=normalize_repository_relative_path,
    ):
        target_path = str(entry["target_file"])
        target_file = module_index.get(target_path) or resolve_suffix_match(
            module_index=module_index,
            suffixes=[target_path],
        )
        target_names = _item_target_names(
            item_name=str(entry["item_name"]),
            target_file=target_path,
        )
        dependency_key = (target_file, target_names[0] if target_names else None, "imports")
        if dependency_key in seen_dependencies:
            continue
        seen_dependencies.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": str(entry["target_file"]),
                        "line": int(entry["line"]),
                        "type": "imports",
                    },
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_names[0] if target_names else None,
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
    if not is_probable_labview_source(path=path, text=text):
        return (), (), ()
    line_count = max(str(text or "").count("\n") + 1, 1)
    primary_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "name": path.stem,
                "kind": _artifact_symbol_kind(path),
                "line": 1,
            },
        ),
        symbol_name=path.stem,
        symbol_kind=_artifact_symbol_kind(path),
        start_line=1,
        end_line=line_count,
        parent_symbol_id=None,
        signature=str(path.with_suffix("")),
    )
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    if path.suffix.lower() not in _XML_SUFFIXES:
        return (primary_symbol,), dependencies, ()
    reference_candidates: dict[tuple[str | None, tuple[str, ...]], _SymbolReferenceCandidate] = {}
    for entry in project_item_entries(
        text,
        manifest_path=file_path,
        normalize_repository_relative_path=normalize_repository_relative_path,
    ):
        target_path = str(entry["target_file"])
        target_file = module_index.get(target_path) or resolve_suffix_match(
            module_index=module_index,
            suffixes=[target_path],
        )
        target_names = _item_target_names(
            item_name=str(entry["item_name"]),
            target_file=target_path,
        )
        key = (target_file, target_names)
        if key in reference_candidates:
            continue
        reference_candidates[key] = _SymbolReferenceCandidate(
            reference_edge_id=stable_identifier(
                "ref",
                {
                    "file_path": file_path,
                    "symbol_id": primary_symbol.symbol_id,
                    "target": target_path,
                    "line": int(entry["line"]),
                    "type": "references_symbol",
                },
            ),
            source_symbol_id=primary_symbol.symbol_id,
            source_file=file_path,
            target_symbol_id=None,
            target_file=target_file,
            target_names=target_names,
            reference_type="references_symbol",
        )
    return (
        (primary_symbol,),
        dependencies,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )

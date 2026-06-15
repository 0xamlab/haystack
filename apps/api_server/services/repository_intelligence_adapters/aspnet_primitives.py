from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any, Callable

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

ASPNET_SUFFIXES = frozenset({".asax", ".ascx", ".ashx", ".asmx", ".aspx", ".master"})
_SERVER_COMMENT_RE = re.compile(r"<%--[\s\S]*?--%>")
_HTML_COMMENT_RE = re.compile(r"<!--(?!\s*#include\b)[\s\S]*?-->")
_DIRECTIVE_RE = re.compile(r"<%@\s*(?P<kind>[A-Za-z]+)\s*(?P<body>.*?)%>", re.I | re.S)
_ATTRIBUTE_RE = re.compile(
    r"""(?P<name>[A-Za-z][A-Za-z0-9]*)\s*=\s*(?P<quote>["'])(?P<value>.*?)(?P=quote)""",
    re.S,
)
_INCLUDE_RE = re.compile(
    r"""<!--\s*#include\s+(?P<kind>file|virtual)\s*=\s*(?P<quote>["'])(?P<target>.*?)(?P=quote)\s*-->""",
    re.I | re.S,
)
_CONTENT_PLACEHOLDER_RE = re.compile(
    r"""<asp:ContentPlaceHolder\b[^>]*\bID\s*=\s*(?P<quote>["'])(?P<identifier>[^"']+)(?P=quote)[^>]*>""",
    re.I,
)
_CONTENT_PLACEHOLDER_REFERENCE_RE = re.compile(
    r"""\bContentPlaceHolderID\s*=\s*(?P<quote>["'])(?P<identifier>[^"']+)(?P=quote)""",
    re.I,
)
_REGISTERED_CONTROL_USAGE_RE = re.compile(
    r"""<(?P<prefix>[A-Za-z_][A-Za-z0-9_-]*):(?P<tag>[A-Za-z_][A-Za-z0-9_-]*)\b""",
    re.I,
)
_RUNAT_SERVER_RE = re.compile(r"""runat\s*=\s*(?P<quote>["'])server(?P=quote)""", re.I)
_CLASS_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def strip_comments(text: str) -> str:
    def _preserve_newlines(match: re.Match[str]) -> str:
        return "".join("\n" if character == "\n" else " " for character in match.group(0))

    stripped = _SERVER_COMMENT_RE.sub(_preserve_newlines, text)
    return _HTML_COMMENT_RE.sub(_preserve_newlines, stripped)


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip()


def has_aspnet_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in ASPNET_SUFFIXES


def _directive_attributes(body: str) -> dict[str, str]:
    return {
        str(match.group("name") or "").strip().lower(): normalize_identifier(
            str(match.group("value") or "")
        )
        for match in _ATTRIBUTE_RE.finditer(body)
        if normalize_identifier(str(match.group("name") or ""))
    }


def iter_directive_entries(text: str) -> tuple[tuple[str, dict[str, str], int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, dict[str, str], int]] = []
    for match in _DIRECTIVE_RE.finditer(stripped_text):
        kind = normalize_identifier(str(match.group("kind") or "")).lower()
        if not kind:
            continue
        entries.append(
            (
                kind,
                _directive_attributes(str(match.group("body") or "")),
                _line_number(stripped_text, match.start()),
            )
        )
    return tuple(entries)


def primary_directive_kind(text: str) -> str | None:
    for kind, _attrs, _line_number in iter_directive_entries(text):
        if kind in {"application", "control", "master", "page", "webhandler", "webservice"}:
            return kind
    return None


def is_probable_aspnet_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in ASPNET_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    if primary_directive_kind(stripped_text) is not None:
        return True
    lower_text = stripped_text.lower()
    return bool(
        _RUNAT_SERVER_RE.search(stripped_text)
        and (
            "<asp:" in lower_text
            or normalized_path.suffix.lower() in {".ascx", ".master"}
            or "<%" in stripped_text
        )
    )


def _path_aliases(file_path: str) -> set[str]:
    normalized_path = str(PurePosixPath(file_path))
    path = PurePosixPath(normalized_path)
    without_suffix = path.with_suffix("")
    aliases = {
        normalized_path,
        path.name,
        path.stem,
        str(without_suffix),
        str(without_suffix).replace("/", "."),
    }
    if without_suffix.parent not in {PurePosixPath("."), PurePosixPath("")}:
        aliases.add(without_suffix.name)
    return {alias for alias in aliases if alias}


def path_aliases_for_file(file_path: str) -> set[str]:
    return _path_aliases(file_path)


def module_name_from_path(file_path: str) -> str:
    without_suffix = PurePosixPath(file_path).with_suffix("")
    return str(without_suffix).replace("/", ".")


def iter_declared_alias_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for kind, attributes, line_number in iter_directive_entries(text):
        for attribute_name in ("inherits", "classname"):
            candidate = normalize_identifier(attributes.get(attribute_name, ""))
            if not candidate or not _CLASS_NAME_RE.match(candidate):
                continue
            for alias_name in {candidate, candidate.rsplit(".", 1)[-1]}:
                item = (alias_name, "class", line_number)
                if item not in seen:
                    seen.add(item)
                    entries.append(item)
        if kind == "register":
            tag_prefix = normalize_identifier(attributes.get("tagprefix", "")).lower()
            tag_name = normalize_identifier(attributes.get("tagname", ""))
            if tag_prefix and tag_name:
                item = (f"{tag_prefix}:{tag_name}", "registered_control", line_number)
                if item not in seen:
                    seen.add(item)
                    entries.append(item)
    stripped_text = strip_comments(text)
    for match in _CONTENT_PLACEHOLDER_RE.finditer(stripped_text):
        identifier = normalize_identifier(str(match.group("identifier") or ""))
        if not identifier:
            continue
        item = (identifier, "content_placeholder", _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    return iter_declared_alias_entries(text)


def iter_dependency_entries(text: str) -> tuple[tuple[str, str, str | None, int], ...]:
    entries: list[tuple[str, str, str | None, int]] = []
    seen: set[tuple[str, str, str | None, int]] = set()
    for kind, attributes, line_number in iter_directive_entries(text):
        if kind in {"page", "master"}:
            master_page = normalize_identifier(attributes.get("masterpagefile", ""))
            if master_page:
                item = ("master_page", master_page, None, line_number)
                if item not in seen:
                    seen.add(item)
                    entries.append(item)
        if kind in {"application", "control", "master", "page", "webhandler", "webservice"}:
            for attribute_name in ("codebehind", "codefile", "src"):
                source_path = normalize_identifier(attributes.get(attribute_name, ""))
                if not source_path or "/" not in source_path and "." not in source_path:
                    continue
                item = ("codebehind", source_path, None, line_number)
                if item not in seen:
                    seen.add(item)
                    entries.append(item)
        if kind == "register":
            source_path = normalize_identifier(attributes.get("src", ""))
            tag_prefix = normalize_identifier(attributes.get("tagprefix", "")).lower()
            tag_name = normalize_identifier(attributes.get("tagname", ""))
            target_symbol = f"{tag_prefix}:{tag_name}" if tag_prefix and tag_name else None
            if source_path:
                item = ("register_control", source_path, target_symbol, line_number)
                if item not in seen:
                    seen.add(item)
                    entries.append(item)
        if kind == "reference":
            for attribute_name, dependency_kind in (
                ("page", "reference_page"),
                ("control", "reference_control"),
                ("virtualpath", "reference_virtual"),
            ):
                target_path = normalize_identifier(attributes.get(attribute_name, ""))
                if not target_path:
                    continue
                item = (dependency_kind, target_path, None, line_number)
                if item not in seen:
                    seen.add(item)
                    entries.append(item)
        if kind == "mastertype":
            target_path = normalize_identifier(attributes.get("virtualpath", ""))
            if target_path:
                item = ("master_type", target_path, None, line_number)
                if item not in seen:
                    seen.add(item)
                    entries.append(item)
        if kind == "previouspagetype":
            target_path = normalize_identifier(attributes.get("virtualpath", ""))
            if target_path:
                item = ("previous_page_type", target_path, None, line_number)
                if item not in seen:
                    seen.add(item)
                    entries.append(item)
    for match in _INCLUDE_RE.finditer(text):
        include_kind = normalize_identifier(str(match.group("kind") or "")).lower()
        target_path = normalize_identifier(str(match.group("target") or ""))
        if not include_kind or not target_path:
            continue
        item = (f"include_{include_kind}", target_path, None, _line_number(text, match.start()))
        if item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str, str | None, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str | None, str, int]] = []
    seen: set[tuple[str, str | None, str, int]] = set()
    for kind, attributes, line_number in iter_directive_entries(stripped_text):
        for attribute_name in ("inherits", "classname"):
            class_name = normalize_identifier(attributes.get(attribute_name, ""))
            if not class_name or not _CLASS_NAME_RE.match(class_name):
                continue
            item = ("class_reference", None, class_name, line_number)
            if item not in seen:
                seen.add(item)
                entries.append(item)
    for match in _CONTENT_PLACEHOLDER_REFERENCE_RE.finditer(stripped_text):
        placeholder_name = normalize_identifier(str(match.group("identifier") or ""))
        if not placeholder_name:
            continue
        item = ("content_placeholder_reference", None, placeholder_name, _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            entries.append(item)
    for match in _REGISTERED_CONTROL_USAGE_RE.finditer(stripped_text):
        prefix = normalize_identifier(str(match.group("prefix") or "")).lower()
        tag_name = normalize_identifier(str(match.group("tag") or ""))
        if not prefix or not tag_name or prefix == "asp":
            continue
        item = ("registered_control_reference", prefix, tag_name, _line_number(stripped_text, match.start()))
        if item not in seen:
            seen.add(item)
            entries.append(item)
    return tuple(entries)


def source_symbol_name_for_line(
    symbol_entries: tuple[tuple[str, str, int], ...],
    *,
    line_number: int,
) -> str | None:
    current_symbol_name: str | None = None
    for symbol_name, _symbol_kind, symbol_line in symbol_entries:
        if symbol_line <= line_number:
            current_symbol_name = symbol_name
    return current_symbol_name


def normalize_target_path(value: str) -> str:
    normalized = normalize_identifier(value).replace("\\", "/")
    normalized = normalized.split("?", 1)[0].split("#", 1)[0]
    if normalized.startswith("~/"):
        normalized = normalized[2:]
    elif normalized.startswith("~"):
        normalized = normalized[1:]
    return normalized.lstrip("/")


def resolve_target(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_target_path(import_target)
    if not normalized_target:
        return None
    target_path = PurePosixPath(normalized_target)
    current_dir = normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    candidate_keys: list[str] = []
    if normalized_target:
        candidate_keys.append(normalized_target)
    if current_dir and not normalized_target.startswith("/"):
        candidate_keys.append(
            normalize_repository_relative_path(str(PurePosixPath(current_dir) / normalized_target))
        )
    if target_path.name:
        candidate_keys.append(target_path.name)
        candidate_keys.append(target_path.stem)
    seen: set[str] = set()
    ordered_candidates: list[str] = []
    for candidate in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate)
        if not normalized_candidate or normalized_candidate in seen:
            continue
        seen.add(normalized_candidate)
        ordered_candidates.append(normalized_candidate)
        direct_match = module_index.get(normalized_candidate)
        if direct_match is not None:
            return direct_match
    return resolve_suffix_match(module_index=module_index, suffixes=ordered_candidates)

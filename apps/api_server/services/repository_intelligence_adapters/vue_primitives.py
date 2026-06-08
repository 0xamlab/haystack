from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import _Symbol

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

VUE_SUFFIXES = frozenset({".vue"})
_COMMON_MODULE_ROOTS = frozenset(
    {"app", "components", "composables", "layouts", "pages", "src", "views"}
)
_SCRIPT_BLOCK_RE = re.compile(r"<script\b[^>]*>(?P<body>.*?)</script>", re.I | re.S)
_TEMPLATE_BLOCK_RE = re.compile(r"<template\b[^>]*>(?P<body>.*?)</template>", re.I | re.S)
_COMMENT_RE = re.compile(r"<!--.*?-->|/\*.*?\*/|//[^\n]*", re.S)
_IMPORT_RE = re.compile(
    r"import\s+(?P<bindings>.+?)\s+from\s+['\"](?P<target>[^'\"]+)['\"]",
    re.S,
)
_JS_IDENTIFIER_RE = re.compile(r"(?<![\w$])(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)")
_TEMPLATE_TAG_RE = re.compile(r"<(?P<tag>[A-Za-z][A-Za-z0-9_-]*)\b")
_RESERVED_TEMPLATE_TAGS = frozenset(
    {
        "component",
        "keepalive",
        "router-link",
        "router-view",
        "slot",
        "suspense",
        "teleport",
        "template",
        "transition",
        "transition-group",
    }
)
_RESOLVER_DIRS = ("src/components", "components", "src/layouts", "layouts", "src/pages", "pages", "src/views", "views")


def strip_comments(text: str) -> str:
    return _COMMENT_RE.sub(lambda match: "".join("\n" if char == "\n" else " " for char in match.group(0)), text)


def has_vue_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in VUE_SUFFIXES


def _extract_script_blocks(text: str) -> tuple[str, ...]:
    return tuple(str(match.group("body") or "") for match in _SCRIPT_BLOCK_RE.finditer(text))


def extract_template_block(text: str) -> str:
    match = _TEMPLATE_BLOCK_RE.search(text)
    return str(match.group("body") or "") if match else ""


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def is_probable_vue_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in VUE_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    return any(marker in stripped_text.lower() for marker in ("<template", "<script", "<style"))


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


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    if parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    return ".".join(parts) if parts else without_suffix.name


def _normalized_template_tag_name(value: str) -> str:
    cleaned = normalize_identifier(value).replace(":", "-")
    if not cleaned:
        return ""
    parts = [part for part in cleaned.split("-") if part]
    if not parts:
        return cleaned
    return "".join(part[:1].upper() + part[1:] for part in parts)


def _import_binding_names(bindings_text: str) -> tuple[str, ...]:
    normalized_bindings = " ".join(str(bindings_text or "").replace("\n", " ").split())
    if not normalized_bindings:
        return ()
    names: list[str] = []
    seen: set[str] = set()
    remainder = normalized_bindings
    if not remainder.startswith("{") and "," in remainder:
        default_part, remainder = remainder.split(",", 1)
        default_name = normalize_identifier(default_part)
        if default_name and default_name not in seen:
            seen.add(default_name)
            names.append(default_name)
    elif not remainder.startswith("{") and not remainder.startswith("*"):
        default_name = normalize_identifier(remainder)
        if default_name:
            return (default_name,)
    if remainder.startswith("*"):
        as_match = re.search(r"\bas\s+(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)", remainder)
        alias_name = normalize_identifier(as_match.group("name") if as_match else "")
        if alias_name and alias_name not in seen:
            seen.add(alias_name)
            names.append(alias_name)
        return tuple(names)
    named_match = re.search(r"\{(?P<body>.*?)\}", remainder)
    if not named_match:
        return tuple(names)
    for raw_entry in str(named_match.group("body") or "").split(","):
        entry = normalize_identifier(raw_entry)
        if not entry:
            continue
        if " as " in entry:
            _, alias_name = entry.split(" as ", 1)
            entry = normalize_identifier(alias_name)
        if entry and entry not in seen:
            seen.add(entry)
            names.append(entry)
    return tuple(names)


def iter_import_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for script_text in _extract_script_blocks(stripped_text):
        for match in _IMPORT_RE.finditer(script_text):
            import_target = normalize_identifier(str(match.group("target") or ""))
            if not import_target:
                continue
            line_number = stripped_text.count("\n", 0, match.start()) + 1
            for binding_name in _import_binding_names(str(match.group("bindings") or "")):
                item = (binding_name, import_target, line_number)
                if item in seen:
                    continue
                seen.add(item)
                entries.append(item)
    return tuple(entries)


def iter_template_component_references(text: str) -> tuple[tuple[str, int], ...]:
    template_text = strip_comments(extract_template_block(text))
    if not template_text:
        return ()
    entries: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _TEMPLATE_TAG_RE.finditer(template_text):
        raw_tag = normalize_identifier(str(match.group("tag") or ""))
        if not raw_tag:
            continue
        lowered_tag = raw_tag.lower()
        if lowered_tag in _RESERVED_TEMPLATE_TAGS or "-" not in raw_tag and not raw_tag[:1].isupper():
            continue
        tag_name = _normalized_template_tag_name(raw_tag)
        if not tag_name:
            continue
        line_number = template_text.count("\n", 0, match.start()) + 1
        item = (tag_name, line_number)
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in VUE_SUFFIXES:
        return set()
    normalized_path = _normalize_repository_relative_path(file_path)
    if not normalized_path:
        return set()
    aliases = {
        normalized_path,
        path.name,
        path.stem,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if text and not is_probable_vue_source(path=path, text=text):
        return {alias for alias in aliases if alias}
    module_name = module_name_from_path(normalized_path)
    if module_name:
        aliases.add(module_name)
        aliases.add(module_name.replace("/", "."))
    return {alias for alias in aliases if alias}


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_identifier(import_target).replace("\\", "/")
    if (
        not normalized_target
        or normalized_target.startswith("/")
        or normalized_target.startswith("http:")
        or normalized_target.startswith("https:")
        or normalized_target.startswith("@")
    ):
        return None
    current_parent = PurePosixPath(current_file).parent
    candidate_keys = [normalized_target]
    candidate_keys.append(str(current_parent / normalized_target))
    if "/" not in normalized_target and not normalized_target.startswith("."):
        candidate_keys.extend(f"{directory}/{normalized_target}" for directory in _RESOLVER_DIRS)
    normalized_candidates: list[str] = []
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if normalized_candidate:
            normalized_candidates.append(normalized_candidate)
            if PurePosixPath(normalized_candidate).suffix.lower() not in VUE_SUFFIXES:
                normalized_candidates.append(f"{normalized_candidate}.vue")
                normalized_candidates.append(f"{normalized_candidate}/index.vue")
    seen_candidates: set[str] = set()
    for candidate in normalized_candidates:
        if candidate in seen_candidates:
            continue
        seen_candidates.add(candidate)
        direct_match = module_index.get(candidate) or module_index.get(candidate.replace("/", "."))
        if direct_match:
            return direct_match
    suffixes = tuple(f"/{PurePosixPath(candidate).name}" for candidate in seen_candidates)
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes) if suffixes else None


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    line_count = max(1, text.count("\n") + 1)
    module_symbol_name = PurePosixPath(file_path).stem or module_name_from_path(file_path) or "component"
    return (
        _Symbol(
            symbol_id=stable_identifier(
                "sym",
                {
                    "file_path": file_path,
                    "symbol_name": module_symbol_name,
                    "symbol_kind": "vue",
                },
            ),
            symbol_name=module_symbol_name,
            symbol_kind="vue",
            start_line=1,
            end_line=line_count,
            parent_symbol_id=None,
            signature=f"vue {module_symbol_name}",
        ),
    )

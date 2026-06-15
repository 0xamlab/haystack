from __future__ import annotations

import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

ASTRO_SUFFIXES = frozenset({".astro"})
_COMMON_MODULE_ROOTS = frozenset({"src", "components", "layouts", "pages", "content"})
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---(?:\s*\n|$)", re.S)
# Closing tag uses \s* before > to tolerate browser-permissive malformed end tags
# like </script > or </script\n>. Fixes py/bad-tag-filter (CodeQL).
_SCRIPT_BLOCK_RE = re.compile(r"<script\b[^>]*>(?P<body>.*?)</script\s*>", re.I | re.S)
_STYLE_BLOCK_RE = re.compile(r"<style\b[^>]*>.*?</style\s*>", re.I | re.S)
_COMMENT_RE = re.compile(r"<!--.*?-->|/\*.*?\*/|//[^\n]*", re.S)
_IMPORT_RE = re.compile(
    r"import\s+(?:type\s+)?(?P<bindings>.+?)\s+from\s+['\"](?P<target>[^'\"]+)['\"]",
    re.S,
)
_TAG_RE = re.compile(r"<(?P<tag>[A-Za-z][A-Za-z0-9_:.-]*)\b")
_RESERVED_TAGS = frozenset({"Fragment", "html", "head", "body", "meta", "link", "script", "style", "slot"})
_ASTRO_IMPORT_ROOT_PREFIXES = (
    ("@/", "src/"),
    ("~/", "src/"),
    ("@components/", "src/components/"),
    ("@layouts/", "src/layouts/"),
    ("@pages/", "src/pages/"),
    ("@content/", "src/content/"),
)
_ASTRO_IMPORTABLE_SUFFIXES = (
    ".astro",
    ".ts",
    ".js",
    ".tsx",
    ".jsx",
    ".mjs",
    ".cjs",
    ".md",
    ".mdx",
    ".svelte",
    ".vue",
)


def strip_comments(text: str) -> str:
    return _COMMENT_RE.sub(
        lambda match: "".join("\n" if character == "\n" else " " for character in match.group(0)),
        text,
    )


def has_astro_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in ASTRO_SUFFIXES


def _frontmatter_block(text: str) -> tuple[str, int]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return "", -1
    return str(match.group("body") or ""), match.start("body")


def _extract_script_blocks(text: str) -> tuple[tuple[str, int], ...]:
    return tuple((str(match.group("body") or ""), match.start("body")) for match in _SCRIPT_BLOCK_RE.finditer(text))


def _template_body(text: str) -> str:
    template_text = strip_comments(text)
    template_text = _FRONTMATTER_RE.sub("", template_text, count=1)
    template_text = _SCRIPT_BLOCK_RE.sub("", template_text)
    template_text = _STYLE_BLOCK_RE.sub("", template_text)
    return template_text


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def is_probable_astro_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in ASTRO_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped = strip_comments(text)
    if not stripped.strip():
        return False
    lowered = stripped.lower()
    return any(
        marker in lowered for marker in ("---", "<astro:", "client:", "server:", "set:html", "astro.")
    ) or "<" in stripped


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


def _append_unique(ordered: list[str], seen: set[str], value: str) -> None:
    normalized = str(value or "").strip()
    if normalized and normalized not in seen:
        seen.add(normalized)
        ordered.append(normalized)


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    if parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    return ".".join(parts) if parts else without_suffix.name


@lru_cache(maxsize=32_768)
def _resolve_import_candidates(
    current_file: str,
    import_target: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    normalized_current_file = _normalize_repository_relative_path(current_file)
    normalized_target = str(import_target or "").strip()
    if (
        not normalized_target
        or normalized_target.startswith(("http://", "https://", "//"))
        or normalized_target.startswith("astro:")
    ):
        return (), ()

    current_parent = (
        normalized_current_file.rsplit("/", 1)[0]
        if "/" in normalized_current_file
        else ""
    )
    base_targets: list[str] = []
    seen_base_targets: set[str] = set()
    for prefix, replacement in _ASTRO_IMPORT_ROOT_PREFIXES:
        if normalized_target.startswith(prefix):
            _append_unique(
                base_targets,
                seen_base_targets,
                _normalize_repository_relative_path(
                    f"{replacement}{normalized_target[len(prefix):]}"
                ),
            )
            break
    else:
        if normalized_target.startswith("."):
            relative_target = (
                f"{current_parent}/{normalized_target}"
                if current_parent
                else normalized_target
            )
            _append_unique(
                base_targets,
                seen_base_targets,
                _normalize_repository_relative_path(relative_target),
            )
        else:
            _append_unique(base_targets, seen_base_targets, normalized_target)
            if current_parent:
                _append_unique(
                    base_targets,
                    seen_base_targets,
                    _normalize_repository_relative_path(
                        f"{current_parent}/{normalized_target}"
                    ),
                )

    normalized_target_name = normalized_target.rsplit("/", 1)[-1]
    normalized_target_dotted = normalized_target.replace("/", ".")
    direct_candidates: list[str] = []
    seen_direct_candidates: set[str] = set()
    for base_target in base_targets:
        normalized_base = _normalize_repository_relative_path(base_target)
        if not normalized_base:
            continue
        base_name = normalized_base.rsplit("/", 1)[-1]
        _append_unique(direct_candidates, seen_direct_candidates, normalized_base)
        _append_unique(
            direct_candidates,
            seen_direct_candidates,
            normalized_base.replace("/", "."),
        )
        _append_unique(direct_candidates, seen_direct_candidates, base_name)
        _append_unique(
            direct_candidates,
            seen_direct_candidates,
            normalized_target_dotted,
        )
        _append_unique(
            direct_candidates,
            seen_direct_candidates,
            normalized_target_name,
        )
        if "." in base_name:
            suffix = base_name[base_name.rfind(".") :]
            base_directory = normalized_base.rsplit("/", 1)[0] if "/" in normalized_base else ""
            _append_unique(
                direct_candidates,
                seen_direct_candidates,
                f"{base_directory}/index{suffix}" if base_directory else f"index{suffix}",
            )
            continue
        for suffix in _ASTRO_IMPORTABLE_SUFFIXES:
            _append_unique(
                direct_candidates,
                seen_direct_candidates,
                f"{normalized_base}{suffix}",
            )
            _append_unique(
                direct_candidates,
                seen_direct_candidates,
                f"{normalized_base}/index{suffix}",
            )

    suffix_candidates: list[str] = []
    seen_suffix_candidates: set[str] = set()
    for candidate in direct_candidates:
        _append_unique(
            suffix_candidates,
            seen_suffix_candidates,
            f"/{candidate.rsplit('/', 1)[-1]}",
        )
    return tuple(direct_candidates), tuple(suffix_candidates)


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
    import_sources: list[tuple[str, int]] = []
    frontmatter_text, frontmatter_offset = _frontmatter_block(stripped_text)
    if frontmatter_text:
        import_sources.append((frontmatter_text, frontmatter_offset))
    import_sources.extend(_extract_script_blocks(stripped_text))
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for source_text, source_offset in import_sources:
        for match in _IMPORT_RE.finditer(source_text):
            import_target = normalize_identifier(str(match.group("target") or ""))
            if not import_target:
                continue
            line_number = stripped_text.count("\n", 0, source_offset + match.start()) + 1
            for binding_name in _import_binding_names(str(match.group("bindings") or "")):
                item = (binding_name, import_target, line_number)
                if item in seen:
                    continue
                seen.add(item)
                entries.append(item)
    return tuple(entries)


def _is_component_tag(raw_tag: str) -> bool:
    if not raw_tag or raw_tag.startswith("astro:") or raw_tag in _RESERVED_TAGS:
        return False
    first_segment = raw_tag.split(".", 1)[0]
    return first_segment[:1].isupper()


def iter_component_references(text: str) -> tuple[tuple[str, int], ...]:
    template_text = _template_body(text)
    if not template_text.strip():
        return ()
    entries: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for match in _TAG_RE.finditer(template_text):
        raw_tag = normalize_identifier(str(match.group("tag") or ""))
        if not _is_component_tag(raw_tag):
            continue
        line_number = template_text.count("\n", 0, match.start()) + 1
        item = (raw_tag, line_number)
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
    if path.suffix.lower() not in ASTRO_SUFFIXES:
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
    module_name = module_name_from_path(normalized_path)
    if module_name:
        aliases.add(module_name)
        aliases.add(module_name.replace("/", "."))
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if text and not is_probable_astro_source(path=path, text=text):
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
    normalized_target = str(import_target or "").strip()
    normalized_current_file = normalize_repository_relative_path(current_file)
    candidate_keys, suffixes = _resolve_import_candidates(
        normalized_current_file,
        normalized_target,
    )
    if not candidate_keys:
        return None
    for candidate_key in candidate_keys:
        target_file = module_index.get(candidate_key)
        if target_file is not None and target_file != normalized_current_file:
            return target_file
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes)

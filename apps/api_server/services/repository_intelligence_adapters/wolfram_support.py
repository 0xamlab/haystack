from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]
NormalizeRepositoryRelativePath = Callable[[str], str]

_KNOWN_WOLFRAM_SUFFIXES = frozenset({".m", ".wl", ".wls"})
_WOLFRAM_SOURCE_ROOTS = ("Kernel", "Resources", "Packages", "Applications")
_QUALIFIED_SYMBOL_RE = re.compile(
    r"\b(?P<name>(?:[A-Za-z$][A-Za-z0-9$]*`)+[A-Za-z$][A-Za-z0-9$]*)\b"
)
_BEGIN_PACKAGE_RE = re.compile(
    r"\b(?P<head>BeginPackage|Package)\s*\[\s*\"(?P<context>[^\"]+)\"",
    re.IGNORECASE,
)
_BEGIN_PACKAGE_IMPORTS_RE = re.compile(
    r"\bBeginPackage\s*\[\s*\"[^\"]+\"\s*,\s*\{(?P<body>.*?)\}\s*\]",
    re.IGNORECASE | re.DOTALL,
)
_IMPORT_CONTEXT_RE = re.compile(
    r"\b(?P<head>Get|Needs)\s*\[\s*\"(?P<target>[^\"]+)\"(?:\s*->\s*None)?\s*\]",
    re.IGNORECASE,
)
_RELATIVE_GET_RE = re.compile(
    r"\bGet\s*\[\s*FileNameJoin\s*(?:@)?\s*\[\s*\{\s*"
    r"DirectoryName\s*(?:@|\[\s*)\s*\$InputFileName(?:\s*,\s*\d+)?\s*\]?\s*,\s*"
    r"\"(?P<target>[^\"]+\.(?:m|wl|wls))\"\s*\}\s*\]\s*\]",
    re.IGNORECASE | re.DOTALL,
)
_MESSAGE_DEF_RE = re.compile(
    r"^\s*(?P<name>(?:[A-Za-z$][A-Za-z0-9$]*`)*[A-Za-z$][A-Za-z0-9$]*)\s*::\s*"
    r"(?P<tag>[A-Za-z$][A-Za-z0-9$]*)\s*=",
    re.MULTILINE,
)
_FUNCTION_DEF_RE = re.compile(
    r"^\s*(?P<name>(?:[A-Za-z$][A-Za-z0-9$]*`)*[A-Za-z$][A-Za-z0-9$]*)\s*"
    r"\[[^\n]*?\]\s*(?::=|=)",
    re.MULTILINE,
)
_VARIABLE_DEF_RE = re.compile(
    r"^\s*(?P<name>(?:[A-Za-z$][A-Za-z0-9$]*`)*[A-Za-z$][A-Za-z0-9$]*)\s*(?::=|=)",
    re.MULTILINE,
)
_DECLARATION_RE = re.compile(
    r"^\s*(?P<name>(?:[A-Za-z$][A-Za-z0-9$]*`)*[A-Za-z$][A-Za-z0-9$]*)\s*;\s*$",
    re.MULTILINE,
)
_UNQUALIFIED_CALL_RE = re.compile(r"\b(?P<name>[A-Za-z$][A-Za-z0-9$]*)\s*(?=\[)")
_STRING_RE = re.compile(r'"(?P<value>[^"]+)"')
_KERNEL_EXTENSION_START_RE = re.compile(r"\{\s*\"Kernel\"\s*,", re.IGNORECASE)
_ROOT_RULE_RE = re.compile(r"(?:(?:\"Root\")|Root)\s*->\s*\"(?P<root>[^\"]+)\"")
_CONTEXT_RULE_RE = re.compile(
    r"(?:(?:\"Context\")|Context)\s*->\s*\{(?P<body>.*?)\}",
    re.IGNORECASE | re.DOTALL,
)
_WOLFRAM_MARKER_RE = re.compile(
    r"\b(?:BeginPackage|EndPackage|Begin|End|Get|Needs|PacletObject|Paclet|"
    r"Module|Block|With|FileNameJoin)\s*\[|::usage\b",
    re.IGNORECASE,
)
_PATH_HINT_PARTS = frozenset({"kernel", "paclets"})
_PUBLIC_CONTEXT_STRIP_SUFFIXES = ("`Private`", "`Internal`")
RESERVED_SYMBOL_NAMES = frozenset(
    {
        "$aborted",
        "$context",
        "$contextpath",
        "$failed",
        "$inputfilename",
        "$installationdirectory",
        "$operatingsystem",
        "$systemshell",
        "$systemwordlength",
        "$versionnumber",
        "association",
        "begin",
        "beginpackage",
        "block",
        "directoryname",
        "end",
        "endpackage",
        "environment",
        "failureq",
        "filenamejoin",
        "get",
        "if",
        "linkclose",
        "linklaunch",
        "linkread",
        "linkreadyq",
        "linkwrite",
        "module",
        "needs",
        "paclet",
        "pacletinstall",
        "pacletobject",
        "quiet",
        "return",
        "runprocess",
        "stringcontainsq",
        "stringjoin",
        "stringq",
        "stringsplit",
        "stringtrim",
        "switch",
        "toexpression",
        "tostring",
        "while",
        "with",
    }
)


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


def strip_comments(text: str) -> str:
    output: list[str] = []
    index = 0
    comment_depth = 0
    in_string = False
    escaped = False
    while index < len(text):
        character = text[index]
        next_character = text[index + 1] if index + 1 < len(text) else ""
        if comment_depth:
            if character == "(" and next_character == "*":
                comment_depth += 1
                output.extend((" ", " "))
                index += 2
                continue
            if character == "*" and next_character == ")":
                comment_depth = max(0, comment_depth - 1)
                output.extend((" ", " "))
                index += 2
                continue
            output.append("\n" if character == "\n" else " ")
            index += 1
            continue
        if in_string:
            output.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            index += 1
            continue
        if character == '"':
            in_string = True
            output.append(character)
            index += 1
            continue
        if character == "(" and next_character == "*":
            comment_depth = 1
            output.extend((" ", " "))
            index += 2
            continue
        output.append(character)
        index += 1
    return "".join(output)


def normalize_context_name(raw_name: str) -> str:
    normalized = str(raw_name or "").strip().strip("'\"")
    if not normalized:
        return ""
    parts = [part for part in normalized.split("`") if part]
    if not parts:
        return ""
    return "`".join(parts) + "`"


def normalize_symbol_name(raw_name: str) -> str:
    normalized = str(raw_name or "").strip().strip("'\"")
    if not normalized:
        return ""
    parts = [part for part in normalized.split("`") if part]
    return parts[-1] if parts else ""


def _canonical_symbol_name(raw_name: str) -> str:
    return normalize_symbol_name(raw_name).lower()


def _split_qualified_symbol(raw_name: str) -> tuple[str, str]:
    normalized = str(raw_name or "").strip().strip("'\"")
    if not normalized:
        return "", ""
    parts = [part for part in normalized.split("`") if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return "", parts[0]
    return "`".join(parts[:-1]) + "`", parts[-1]


def _strip_public_context_suffix(context_name: str) -> str:
    normalized = normalize_context_name(context_name)
    if not normalized:
        return ""
    for suffix in _PUBLIC_CONTEXT_STRIP_SUFFIXES:
        if normalized.endswith(suffix):
            normalized = normalized.removesuffix(suffix) + "`"
            break
    return normalized


def _qualify_symbol(current_package: str, raw_name: str) -> str:
    normalized_name = str(raw_name or "").strip().strip("'\"")
    if not normalized_name:
        return ""
    if "`" in normalized_name:
        context_name, symbol_name = _split_qualified_symbol(normalized_name)
        if not symbol_name:
            return ""
        return f"{context_name}{symbol_name}" if context_name else symbol_name
    if current_package:
        return f"{current_package}{normalized_name}"
    return normalized_name


def _package_file_context(context_name: str, stem: str) -> tuple[str, ...]:
    base_context = _strip_public_context_suffix(context_name)
    if not base_context or not stem:
        return ()
    return (
        f"{base_context}{stem}`",
        f"{base_context}{stem}",
    )


def _path_aliases(path: PurePosixPath) -> set[str]:
    aliases = {
        str(path),
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
        path.stem,
    }
    source_parts = list(path.parts)
    for source_root in _WOLFRAM_SOURCE_ROOTS:
        if source_root not in source_parts:
            continue
        root_index = source_parts.index(source_root)
        derived_parts = list(source_parts[root_index + 1 : -1])
        derived_parts.append(path.stem)
        module_path = "/".join(part for part in derived_parts if part)
        if module_path:
            aliases.add(module_path)
            aliases.add(module_path.replace("/", "."))
        break
    return {alias for alias in aliases if alias and alias not in {".", "/"}}


def _begin_package_context(text: str) -> str:
    match = _BEGIN_PACKAGE_RE.search(text)
    if match is None:
        return ""
    return normalize_context_name(str(match.group("context") or ""))


def _qualified_symbol_contexts(text: str) -> tuple[str, ...]:
    contexts: list[str] = []
    seen_contexts: set[str] = set()
    for match in _QUALIFIED_SYMBOL_RE.finditer(text):
        context_name, _symbol_name = _split_qualified_symbol(str(match.group("name") or ""))
        normalized_context = _strip_public_context_suffix(context_name)
        if not normalized_context or normalized_context in seen_contexts:
            continue
        seen_contexts.add(normalized_context)
        contexts.append(normalized_context)
    return tuple(contexts)


def _dominant_context(text: str) -> str:
    contexts = Counter(_qualified_symbol_contexts(text))
    if not contexts:
        return ""
    return str(
        max(
            contexts.items(),
            key=lambda item: (
                item[1],
                item[0].count("`"),
                len(item[0]),
                item[0],
            ),
        )[0]
    )


def _current_package_context(text: str) -> str:
    explicit_context = _begin_package_context(text)
    if explicit_context:
        return explicit_context
    return _dominant_context(text)


def _extract_begin_package_imports(text: str) -> tuple[str, ...]:
    imports: list[str] = []
    seen_imports: set[str] = set()
    for match in _BEGIN_PACKAGE_IMPORTS_RE.finditer(text):
        body = str(match.group("body") or "")
        for string_match in _STRING_RE.finditer(body):
            context_name = normalize_context_name(str(string_match.group("value") or ""))
            if not context_name or context_name in seen_imports:
                continue
            seen_imports.add(context_name)
            imports.append(context_name)
    return tuple(imports)


def _extract_context_import_targets(text: str) -> tuple[tuple[str, str, int], ...]:
    targets: list[tuple[str, str, int]] = []
    seen_targets: set[tuple[str, str, int]] = set()
    for match in _IMPORT_CONTEXT_RE.finditer(text):
        head = str(match.group("head") or "").strip().lower()
        target = str(match.group("target") or "").strip()
        if not target:
            continue
        line_no = text.count("\n", 0, match.start()) + 1
        key = (head, target, line_no)
        if key in seen_targets:
            continue
        seen_targets.add(key)
        targets.append(key)
    return tuple(targets)


def _extract_relative_file_targets(text: str) -> tuple[tuple[str, int], ...]:
    targets: list[tuple[str, int]] = []
    seen_targets: set[tuple[str, int]] = set()
    for match in _RELATIVE_GET_RE.finditer(text):
        target = str(match.group("target") or "").strip()
        if not target:
            continue
        line_no = text.count("\n", 0, match.start()) + 1
        key = (target, line_no)
        if key in seen_targets:
            continue
        seen_targets.add(key)
        targets.append(key)
    return tuple(targets)


def _extract_declared_symbols(
    text: str,
    *,
    current_package: str,
    include_message_definitions: bool = True,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_symbols: set[tuple[str, int]] = set()
    patterns: list[tuple[re.Pattern[str], str]] = []
    if include_message_definitions:
        patterns.append((_MESSAGE_DEF_RE, "function"))
    patterns.extend(
        (
            (_FUNCTION_DEF_RE, "function"),
            (_VARIABLE_DEF_RE, "variable"),
            (_DECLARATION_RE, "variable"),
        )
    )
    for pattern, symbol_kind in patterns:
        for match in pattern.finditer(text):
            raw_name = str(match.group("name") or "").strip()
            qualified_name = _qualify_symbol(current_package, raw_name)
            symbol_name = normalize_symbol_name(qualified_name)
            canonical_name = symbol_name.lower()
            if not symbol_name or canonical_name in RESERVED_SYMBOL_NAMES:
                continue
            line_no = text.count("\n", 0, match.start()) + 1
            symbol_key = (qualified_name or symbol_name, line_no)
            if symbol_key in seen_symbols:
                continue
            seen_symbols.add(symbol_key)
            context_name, _resolved_symbol_name = _split_qualified_symbol(qualified_name)
            qualified_names = {
                symbol_name,
                qualified_name,
            }
            if context_name:
                qualified_names.add(f"{context_name}{symbol_name}")
            candidates.append(
                {
                    "symbol_name": symbol_name,
                    "qualified_name": qualified_name,
                    "symbol_kind": symbol_kind,
                    "start_line": line_no,
                    "signature": str(match.group(0) or "").strip(),
                    "qualified_names": tuple(sorted(name for name in qualified_names if name)),
                }
            )
    candidates.sort(key=lambda entry: (int(entry["start_line"]), str(entry["qualified_name"])))
    final_line = len(text.splitlines()) if text else 1
    for index, entry in enumerate(candidates):
        if index + 1 < len(candidates):
            entry["end_line"] = max(
                int(candidates[index + 1]["start_line"]) - 1,
                int(entry["start_line"]),
            )
        else:
            entry["end_line"] = final_line
    return candidates


def _resolve_import_target(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(import_target or "").strip().strip("'\"")
    if not normalized_target:
        return None
    current_dir = PurePosixPath(current_file).parent
    if PurePosixPath(normalized_target).suffix.lower() in _KNOWN_WOLFRAM_SUFFIXES:
        candidate_paths = []
        if not PurePosixPath(normalized_target).is_absolute():
            candidate_paths.append(
                normalize_repository_relative_path(str(current_dir / normalized_target))
            )
        candidate_paths.append(normalize_repository_relative_path(normalized_target))
        for candidate_path in candidate_paths:
            if not candidate_path:
                continue
            direct_match = module_index.get(candidate_path)
            if direct_match is not None and direct_match != current_file:
                return direct_match
        suffix_match = resolve_suffix_match(
            module_index=module_index,
            suffixes=tuple(candidate_path for candidate_path in candidate_paths if candidate_path),
        )
        if suffix_match is not None and suffix_match != current_file:
            return suffix_match
        leaf_name = PurePosixPath(normalized_target).name
        if leaf_name:
            leaf_match = resolve_suffix_match(module_index=module_index, suffixes=(leaf_name,))
            if leaf_match is not None and leaf_match != current_file:
                return leaf_match
        return None

    context_name = normalize_context_name(normalized_target)
    candidate_keys: list[str] = []
    if context_name:
        candidate_keys.extend((context_name, context_name.rstrip("`")))
        leaf_name = context_name.rstrip("`").split("`")[-1]
        if leaf_name:
            candidate_keys.extend((leaf_name, f"{leaf_name}`"))
            for suffix in sorted(_KNOWN_WOLFRAM_SUFFIXES):
                candidate_keys.append(f"{leaf_name}{suffix}")
    else:
        candidate_keys.append(normalized_target)

    seen_candidates: set[str] = set()
    for candidate_key in candidate_keys:
        if not candidate_key or candidate_key in seen_candidates:
            continue
        seen_candidates.add(candidate_key)
        direct_match = module_index.get(candidate_key)
        if direct_match is not None and direct_match != current_file:
            return direct_match

    leaf_suffixes = tuple(
        candidate_key
        for candidate_key in candidate_keys
        if candidate_key.lower().endswith(tuple(sorted(_KNOWN_WOLFRAM_SUFFIXES)))
    )
    if leaf_suffixes:
        suffix_match = resolve_suffix_match(module_index=module_index, suffixes=leaf_suffixes)
        if suffix_match is not None and suffix_match != current_file:
            return suffix_match
    return None


def _resolve_reference_target(
    *,
    current_file: str,
    symbol_name: str,
    current_package: str,
    imported_contexts: tuple[str, ...],
    module_index: dict[str, str],
) -> tuple[str | None, tuple[str, ...]]:
    normalized_name = str(symbol_name or "").strip()
    if not normalized_name:
        return None, ()

    candidate_names: list[str] = []
    if "`" in normalized_name:
        candidate_names.append(_qualify_symbol("", normalized_name))
    else:
        if current_package:
            candidate_names.append(f"{current_package}{normalized_name}")
        for imported_context in imported_contexts:
            candidate_names.append(f"{imported_context}{normalized_name}")
        candidate_names.append(normalized_name)

    seen_names: set[str] = set()
    ordered_candidates: list[str] = []
    for candidate_name in candidate_names:
        if not candidate_name or candidate_name in seen_names:
            continue
        seen_names.add(candidate_name)
        ordered_candidates.append(candidate_name)
    for candidate_name in ordered_candidates:
        direct_match = module_index.get(candidate_name)
        if direct_match is not None and direct_match != current_file:
            return direct_match, tuple(ordered_candidates)
    return None, tuple(ordered_candidates)


def _reference_names(text: str) -> tuple[tuple[str, int], ...]:
    references: list[tuple[str, int]] = []
    seen_references: set[tuple[str, int]] = set()
    for match in _QUALIFIED_SYMBOL_RE.finditer(text):
        name = str(match.group("name") or "").strip()
        if not name:
            continue
        key = (name, match.start())
        if key in seen_references:
            continue
        seen_references.add(key)
        references.append(key)
    for match in _UNQUALIFIED_CALL_RE.finditer(text):
        name = str(match.group("name") or "").strip()
        if not name or name.lower() in RESERVED_SYMBOL_NAMES:
            continue
        key = (name, match.start())
        if key in seen_references:
            continue
        seen_references.add(key)
        references.append(key)
    return tuple(references)


def _extract_kernel_extension_bodies(text: str) -> tuple[str, ...]:
    bodies: list[str] = []
    stripped_text = strip_comments(text)
    for match in _KERNEL_EXTENSION_START_RE.finditer(stripped_text):
        start_index = match.start()
        depth = 0
        in_string = False
        escaped = False
        end_index = start_index
        while end_index < len(stripped_text):
            character = stripped_text[end_index]
            if in_string:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == '"':
                    in_string = False
                end_index += 1
                continue
            if character == '"':
                in_string = True
                end_index += 1
                continue
            if character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    end_index += 1
                    bodies.append(stripped_text[start_index:end_index])
                    break
            end_index += 1
    return tuple(bodies)


def paclet_kernel_entries(
    text: str,
    *,
    manifest_path: str,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> tuple[dict[str, Any], ...]:
    normalized_manifest_path = normalize_repository_relative_path(manifest_path)
    project_dir = PurePosixPath(normalized_manifest_path).parent
    entries: list[dict[str, Any]] = []
    for body in _extract_kernel_extension_bodies(text):
        root_match = _ROOT_RULE_RE.search(body)
        raw_root = str(root_match.group("root") or "").strip() if root_match is not None else ""
        relative_root = raw_root or "Kernel"
        resolved_root = normalize_repository_relative_path(str(project_dir / relative_root))
        contexts: list[str] = []
        context_rule_match = _CONTEXT_RULE_RE.search(body)
        if context_rule_match is not None:
            for string_match in _STRING_RE.finditer(str(context_rule_match.group("body") or "")):
                normalized_context = normalize_context_name(str(string_match.group("value") or ""))
                if normalized_context:
                    contexts.append(normalized_context)
        entries.append(
            {
                "root_path": resolved_root,
                "contexts": tuple(dict.fromkeys(contexts)),
            }
        )
    return tuple(entries)


def has_wolfram_path_hints(path: PurePosixPath | Path | str) -> bool:
    normalized_path = PurePosixPath(str(path).replace("\\", "/"))
    suffix = normalized_path.suffix.lower()
    lowered_parts = [part.lower() for part in normalized_path.parts]
    if suffix in {".wl", ".wls"}:
        return True
    if suffix != ".m":
        return False
    lowered_name = normalized_path.name.lower()
    if lowered_name in {"pacletinfo.m", "init.m"}:
        return True
    return bool(set(lowered_parts) & _PATH_HINT_PARTS)


def is_probable_wolfram_source(*, path: PurePosixPath | Path | str, text: str) -> bool:
    normalized_path = PurePosixPath(str(path).replace("\\", "/"))
    suffix = normalized_path.suffix.lower()
    if suffix not in _KNOWN_WOLFRAM_SUFFIXES:
        return False
    if suffix in {".wl", ".wls"}:
        return True
    if has_wolfram_path_hints(normalized_path):
        return True
    stripped_text = strip_comments(text)
    score = 0
    if _WOLFRAM_MARKER_RE.search(stripped_text):
        score += 2
    if _BEGIN_PACKAGE_RE.search(stripped_text):
        score += 2
    if _IMPORT_CONTEXT_RE.search(stripped_text):
        score += 1
    if _RELATIVE_GET_RE.search(stripped_text):
        score += 1
    if _QUALIFIED_SYMBOL_RE.search(stripped_text):
        score += 1
    return score >= 2

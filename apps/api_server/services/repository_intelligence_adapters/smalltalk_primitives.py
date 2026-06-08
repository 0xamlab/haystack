from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]

_KNOWN_SUFFIXES = frozenset({".st"})
_TONEL_CLASS_RE = re.compile(r"(?ms)^Class\s*\{(?P<body>.*?)^\}")
_TONEL_EXTENSION_RE = re.compile(r"(?ms)^Extension\s*\{(?P<body>.*?)^\}")
_TONEL_PACKAGE_RE = re.compile(r"(?m)^Package\s*\{\s*#name\s*:\s*'(?P<name>[^']+)'\s*\}")
_TONEL_FIELD_RE = re.compile(r"#(?P<name>[A-Za-z0-9_]+)\s*:\s*'(?P<value>[^']*)'")
_TONEL_METHOD_RE = re.compile(
    r"(?m)^(?:\{\s*#category\s*:\s*'[^']*'\s*\}\s*\n)?"
    r"(?P<header>[A-Z][A-Za-z0-9_]*(?:\s+class)?\s*>>\s*[^\[\n]+?)\s*\["
)
_CLASS_MESSAGE_SEND_RE = re.compile(
    r"(?<![#A-Za-z0-9])(?P<class_name>[A-Z][A-Za-z0-9_]*)\s+"
    r"(?P<message>(?:[a-z][A-Za-z0-9_]*:?\s*)+)"
)


def strip_comments(text: str) -> str:
    output: list[str] = []
    in_comment = False
    for character in text:
        if in_comment:
            if character == '"':
                in_comment = False
                output.append(" ")
            elif character == "\n":
                output.append("\n")
            else:
                output.append(" ")
            continue
        if character == '"':
            in_comment = True
            output.append(" ")
            continue
        output.append(character)
    return "".join(output)


def has_smalltalk_path_hints(path: Path) -> bool:
    if path.suffix.lower() not in _KNOWN_SUFFIXES:
        return False
    if path.name == "package.st":
        return True
    if path.name.endswith((".class.st", ".extension.st", ".trait.st")):
        return True
    return any(
        part.endswith((".package", ".class", ".trait"))
        or part in {"instance", "class"}
        for part in path.parts
    )


def is_probable_smalltalk_source(*, path: Path, text: str) -> bool:
    if path.suffix.lower() not in _KNOWN_SUFFIXES:
        return False
    if has_smalltalk_path_hints(path):
        return True
    stripped_text = strip_comments(text)
    if _TONEL_CLASS_RE.search(stripped_text):
        return True
    if _TONEL_EXTENSION_RE.search(stripped_text):
        return True
    if _TONEL_PACKAGE_RE.search(stripped_text):
        return True
    return bool(_TONEL_METHOD_RE.search(stripped_text))


def tonel_metadata(text: str) -> dict[str, str]:
    stripped_text = strip_comments(text)
    package_match = _TONEL_PACKAGE_RE.search(stripped_text)
    if package_match is not None:
        return {
            "kind": "package",
            "name": str(package_match.group("name") or "").strip(),
        }
    for kind, pattern in (("class", _TONEL_CLASS_RE), ("extension", _TONEL_EXTENSION_RE)):
        match = pattern.search(stripped_text)
        if match is None:
            continue
        body = str(match.group("body") or "")
        metadata = {"kind": kind}
        for field_match in _TONEL_FIELD_RE.finditer(body):
            field_name = str(field_match.group("name") or "").strip().lower()
            field_value = str(field_match.group("value") or "").strip()
            if field_name and field_value:
                metadata[field_name] = field_value
        return metadata
    return {}


def package_name_for_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    for part in path.parts:
        if part.endswith(".package"):
            return part[: -len(".package")]
    parent_name = path.parent.name
    if parent_name and parent_name not in {"instance", "class"}:
        return parent_name
    return ""


def class_name_for_path(file_path: str) -> str:
    path = PurePosixPath(file_path)
    if path.name.endswith(".class.st"):
        return path.name[: -len(".class.st")]
    if path.name.endswith(".trait.st"):
        return path.name[: -len(".trait.st")]
    if path.name.endswith(".extension.st"):
        return path.name[: -len(".extension.st")]
    for part in reversed(path.parts):
        if part.endswith(".class"):
            return part[: -len(".class")]
        if part.endswith(".trait"):
            return part[: -len(".trait")]
    return ""


def owner_name_from_header(header: str) -> str:
    normalized_header = str(header or "").strip()
    if ">>" not in normalized_header:
        return ""
    return normalized_header.split(">>", 1)[0].strip().removesuffix(" class").strip()


def is_class_side_header(header: str) -> bool:
    normalized_header = str(header or "").strip()
    return normalized_header.split(">>", 1)[0].strip().endswith(" class")


def normalize_selector(value: str) -> str:
    normalized_value = str(value or "").strip()
    if not normalized_value:
        return ""
    keyword_parts = re.findall(r"([A-Za-z0-9_]+:)", normalized_value)
    if keyword_parts:
        return "".join(keyword_parts)
    return normalized_value.split()[0].strip()


def selector_from_header(header: str) -> str:
    normalized_header = str(header or "").strip()
    if ">>" not in normalized_header:
        return ""
    return normalize_selector(normalized_header.split(">>", 1)[1].strip())


def filetree_selector_from_text(text: str) -> str:
    nonempty_lines = [line.strip() for line in strip_comments(text).splitlines() if line.strip()]
    if len(nonempty_lines) < 2:
        return ""
    return normalize_selector(nonempty_lines[1])


def path_aliases(file_path: str) -> set[str]:
    path = PurePosixPath(file_path)
    aliases = {file_path, file_path.lower()}
    without_suffix_path = str(path.with_suffix(""))
    if without_suffix_path:
        aliases.add(without_suffix_path)
        aliases.add(without_suffix_path.replace("/", "."))
        aliases.add(without_suffix_path.lower())
        aliases.add(without_suffix_path.replace("/", ".").lower())
    package_name = package_name_for_path(file_path)
    if package_name:
        aliases.add(package_name)
        aliases.add(package_name.lower())
    class_name = class_name_for_path(file_path)
    if class_name:
        aliases.add(class_name)
        aliases.add(class_name.lower())
        if package_name:
            aliases.add(f"{package_name}.{class_name}")
            aliases.add(f"{package_name.lower()}.{class_name.lower()}")
    return {alias for alias in aliases if alias}

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]
ResolveDirectoryPrefixMatch = Callable[[dict[str, str], Sequence[str]], str | None]
ResolveImport = Callable[[str, dict[str, str]], str | None]

RESERVED_SYMBOL_NAMES = frozenset(
    {
        "addhandler",
        "alias",
        "and",
        "as",
        "boolean",
        "byref",
        "byte",
        "byval",
        "call",
        "case",
        "catch",
        "char",
        "class",
        "const",
        "continue",
        "date",
        "decimal",
        "default",
        "delegate",
        "dim",
        "do",
        "double",
        "each",
        "else",
        "elseif",
        "end",
        "enum",
        "event",
        "exit",
        "false",
        "finally",
        "for",
        "friend",
        "function",
        "get",
        "global",
        "handles",
        "if",
        "implements",
        "imports",
        "in",
        "inherits",
        "integer",
        "interface",
        "is",
        "isnot",
        "let",
        "long",
        "loop",
        "me",
        "mod",
        "module",
        "mustinherit",
        "mustoverride",
        "mybase",
        "myclass",
        "namespace",
        "narrowing",
        "new",
        "next",
        "not",
        "nothing",
        "notinheritable",
        "notoverridable",
        "object",
        "of",
        "on",
        "operator",
        "option",
        "optional",
        "or",
        "orelse",
        "overloads",
        "overridable",
        "overrides",
        "paramarray",
        "partial",
        "private",
        "property",
        "protected",
        "public",
        "raiseevent",
        "readonly",
        "redim",
        "removehandler",
        "resume",
        "return",
        "sbyte",
        "select",
        "set",
        "shadows",
        "shared",
        "short",
        "single",
        "static",
        "step",
        "stop",
        "string",
        "structure",
        "sub",
        "synclock",
        "then",
        "throw",
        "to",
        "true",
        "try",
        "uinteger",
        "ulong",
        "ushort",
        "using",
        "variant",
        "wend",
        "when",
        "while",
        "widening",
        "with",
        "withevents",
        "writeonly",
        "xor",
    }
)
BUILTIN_TYPE_NAMES = frozenset(
    {
        "boolean",
        "byte",
        "char",
        "date",
        "decimal",
        "double",
        "integer",
        "long",
        "object",
        "sbyte",
        "short",
        "single",
        "string",
        "uinteger",
        "ulong",
        "ushort",
    }
)
IMPORTS_RE = re.compile(
    r"^\s*Imports\s+(?:(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*)?"
    r"(?P<target>[A-Za-z_][A-Za-z0-9_\.]*)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
NAMESPACE_RE = re.compile(
    r"^\s*Namespace\s+(?P<target>[A-Za-z_][A-Za-z0-9_\.]*)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
END_NAMESPACE_RE = re.compile(
    r"^\s*End\s+Namespace\b",
    re.MULTILINE | re.IGNORECASE,
)
TYPE_DECL_RE = re.compile(
    r"^\s*(?:(?:Public|Private|Friend|Protected|Partial|NotInheritable|MustInherit|"
    r"Shadows|Overloads|Overrides|Default|Static|Shared|ReadOnly|WriteOnly)\s+)*"
    r"(?:Class|Interface|Structure|Module|Enum|Delegate)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE | re.IGNORECASE,
)
FUNCTION_DECL_RE = re.compile(
    r"^\s*(?:(?:Public|Private|Friend|Protected|Partial|Shared|Async|Iterator|"
    r"Overrides|Overloads|Default|MustOverride|NotOverridable|Overridable|Static|"
    r"Shadows|ReadOnly|WriteOnly)\s+)*(?:Sub|Function)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE | re.IGNORECASE,
)
QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)
TYPE_REFERENCE_RE = re.compile(
    r"\b(?:New|As|Inherits|Implements)\s+(?P<name>[A-Za-z_][A-Za-z0-9_\.]*)\b",
    re.IGNORECASE,
)


def normalize_target(raw_target: str) -> str:
    normalized_target = raw_target.strip()
    if normalized_target.lower().startswith("global."):
        normalized_target = normalized_target[7:].strip()
    return normalized_target.strip(".")


def normalize_symbol_name(raw_name: str) -> str:
    return raw_name.strip()


def namespace_paths(text: str) -> tuple[str, ...]:
    namespace_paths_list: list[str] = []
    namespace_stack: list[str] = []
    seen_paths: set[str] = set()
    for raw_line in text.splitlines():
        stripped_line = raw_line.split("'", 1)[0].strip()
        if not stripped_line:
            continue
        if END_NAMESPACE_RE.match(stripped_line):
            if namespace_stack:
                namespace_stack.pop()
            continue
        namespace_match = NAMESPACE_RE.match(stripped_line)
        if namespace_match is None:
            continue
        target = normalize_target(str(namespace_match.group("target") or ""))
        if not target:
            continue
        if "." in target or not namespace_stack:
            current_namespace = target
        else:
            current_namespace = f"{namespace_stack[-1]}.{target}"
        namespace_stack.append(current_namespace)
        canonical_namespace = current_namespace.lower()
        if canonical_namespace not in seen_paths:
            seen_paths.add(canonical_namespace)
            namespace_paths_list.append(canonical_namespace)
    return tuple(namespace_paths_list)


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, str, int]] = set()
    namespace_stack: list[str] = []
    final_line = len(text.splitlines()) if text else 1
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        stripped_line = raw_line.split("'", 1)[0].strip()
        if not stripped_line:
            continue
        if END_NAMESPACE_RE.match(stripped_line):
            if namespace_stack:
                namespace_stack.pop()
            continue
        namespace_match = NAMESPACE_RE.match(stripped_line)
        if namespace_match is not None:
            target = normalize_target(str(namespace_match.group("target") or ""))
            if not target:
                continue
            if "." in target or not namespace_stack:
                namespace_stack.append(target)
            else:
                namespace_stack.append(f"{namespace_stack[-1]}.{target}")
            continue
        symbol_kind: str | None = None
        symbol_name: str | None = None
        type_match = TYPE_DECL_RE.match(stripped_line)
        if type_match is not None:
            symbol_kind = "type"
            symbol_name = normalize_symbol_name(str(type_match.group("name") or ""))
        else:
            function_match = FUNCTION_DECL_RE.match(stripped_line)
            if function_match is not None:
                symbol_kind = "function"
                symbol_name = normalize_symbol_name(
                    str(function_match.group("name") or "")
                )
        if symbol_kind is None or symbol_name is None or not symbol_name:
            continue
        canonical_symbol_name = symbol_name.lower()
        if canonical_symbol_name in RESERVED_SYMBOL_NAMES:
            continue
        qualified_names = {canonical_symbol_name}
        if namespace_stack:
            qualified_names.add(f"{namespace_stack[-1].lower()}.{canonical_symbol_name}")
        symbol_key = (symbol_kind, canonical_symbol_name, line_no)
        if symbol_key in seen_symbol_keys:
            continue
        seen_symbol_keys.add(symbol_key)
        symbol_entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": symbol_name,
                        "line": line_no,
                        "kind": symbol_kind,
                    },
                ),
                "symbol_name": symbol_name,
                "symbol_kind": symbol_kind,
                "start_line": line_no,
                "end_line": line_no,
                "signature": stripped_line,
                "qualified_names": tuple(sorted(qualified_names)),
            }
        )
    for index, entry in enumerate(symbol_entries):
        if index + 1 < len(symbol_entries):
            entry["end_line"] = max(
                int(symbol_entries[index + 1]["start_line"]) - 1,
                int(entry["start_line"]),
            )
        else:
            entry["end_line"] = final_line
    return symbol_entries


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() != ".vb":
        return set()
    aliases = {
        file_path.lower(),
        path.stem.lower(),
    }
    without_suffix_path = str(path.with_suffix("")).lower()
    aliases.add(without_suffix_path)
    aliases.add(without_suffix_path.replace("/", "."))
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {alias for alias in aliases if alias}
    namespace_path_entries = namespace_paths(text)
    aliases.update(namespace_path_entries)
    for namespace_path in namespace_path_entries:
        aliases.add(f"{namespace_path}.{path.stem.lower()}")
    for symbol_entry in collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    ):
        aliases.update(
            str(alias).lower() for alias in symbol_entry["qualified_names"] if alias
        )
    return {alias for alias in aliases if alias}


def resolve_import(
    import_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
    resolve_directory_prefix_match: ResolveDirectoryPrefixMatch,
) -> str | None:
    normalized_target = normalize_target(import_target)
    if not normalized_target:
        return None
    canonical_target = normalized_target.lower()
    direct = module_index.get(canonical_target)
    if direct is not None:
        return direct
    namespace_path = canonical_target.replace(".", "/")
    resolved = resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            canonical_target,
            namespace_path,
            f"{namespace_path}.vb",
            f"{canonical_target.split('.')[-1]}.vb",
        ],
    )
    if resolved is not None:
        return resolved
    return resolve_directory_prefix_match(
        module_index=module_index,
        prefixes=[namespace_path, f"src/{namespace_path}"],
    )


def resolve_same_namespace_reference(
    *,
    current_file: str,
    current_namespace: str,
    type_name: str,
    module_index: dict[str, str],
    resolve_import: ResolveImport,
) -> str | None:
    normalized_type = normalize_target(type_name).lower()
    if not normalized_type or not current_namespace:
        return None
    resolved = resolve_import(f"{current_namespace}.{normalized_type}", module_index)
    if resolved is None or resolved == current_file:
        return None
    return resolved


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
) -> tuple[
    tuple[dict[str, Any], ...],
    dict[str, dict[str, Any]],
    str,
]:
    dependencies: list[dict[str, Any]] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    import_bindings: dict[str, dict[str, Any]] = {}
    for match in IMPORTS_RE.finditer(text):
        import_target = normalize_target(str(match.group("target") or ""))
        if not import_target:
            continue
        canonical_target = import_target.lower()
        target_symbol = import_target.rsplit(".", 1)[-1]
        target_symbol_key = target_symbol.lower()
        target_file = resolve_import(import_target, module_index)
        dependency_key = (target_file, target_symbol_key, "imports")
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                {
                    "dependency_edge_id": stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": canonical_target,
                            "line": match.start(),
                        },
                    ),
                    "source_file": file_path,
                    "target_file": target_file,
                    "target_symbol": target_symbol,
                    "dependency_type": "imports",
                }
            )
        alias = str(match.group("alias") or "").strip().lower()
        binding_aliases = {canonical_target, target_symbol_key}
        if alias:
            binding_aliases.add(alias)
        for binding_alias in binding_aliases:
            if not binding_alias:
                continue
            import_bindings.setdefault(
                binding_alias,
                {
                    "alias": binding_alias,
                    "target_file": target_file,
                    "target_names": (target_symbol,),
                },
            )
    namespace_path_entries = namespace_paths(text)
    current_namespace = namespace_path_entries[-1] if namespace_path_entries else ""
    return tuple(dependencies), import_bindings, current_namespace


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
) -> tuple[dict[str, Any], ...]:
    dependencies, import_bindings, current_namespace = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
    )
    dependency_entries = list(dependencies)
    dependency_keys = {
        (entry["target_file"], entry["target_symbol"], entry["dependency_type"])
        for entry in dependency_entries
    }
    declared_type_names = {
        str(entry["symbol_name"]).lower()
        for entry in collect_symbol_entries(
            text,
            file_path=file_path,
            stable_identifier=stable_identifier,
        )
        if str(entry["symbol_kind"]) == "type"
    }
    for match in TYPE_REFERENCE_RE.finditer(text):
        raw_target = normalize_target(str(match.group("name") or ""))
        if not raw_target:
            continue
        canonical_target = raw_target.lower()
        leaf_name = raw_target.rsplit(".", 1)[-1]
        leaf_name_key = leaf_name.lower()
        if (
            leaf_name_key in RESERVED_SYMBOL_NAMES
            or leaf_name_key in BUILTIN_TYPE_NAMES
            or leaf_name_key in declared_type_names
        ):
            continue
        if "." in canonical_target:
            target_file = resolve_import(canonical_target, module_index)
        else:
            binding = import_bindings.get(leaf_name_key)
            target_file = str(binding["target_file"]) if binding is not None else None
            if target_file is None:
                target_file = resolve_same_namespace_reference(
                    current_file=file_path,
                    current_namespace=current_namespace,
                    type_name=leaf_name_key,
                    module_index=module_index,
                    resolve_import=resolve_import,
                )
        dependency_key = (target_file, leaf_name_key, "references")
        if (
            target_file is None
            or target_file == file_path
            or dependency_key in dependency_keys
        ):
            continue
        dependency_keys.add(dependency_key)
        dependency_entries.append(
            {
                "dependency_edge_id": stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": canonical_target,
                        "line": match.start(),
                    },
                ),
                "source_file": file_path,
                "target_file": target_file,
                "target_symbol": leaf_name,
                "dependency_type": "references",
            }
        )
    return tuple(dependency_entries)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
) -> tuple[
    list[dict[str, Any]],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
]:
    symbol_entries = collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    )
    _, import_bindings, current_namespace = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
    )
    reference_candidates: dict[str, dict[str, Any]] = {}
    lines = text.splitlines()
    for symbol_entry in symbol_entries:
        start_line = int(symbol_entry["start_line"])
        end_line = int(symbol_entry["end_line"])
        symbol_name = str(symbol_entry["symbol_name"])
        symbol_id = str(symbol_entry["symbol_id"])
        snippet = "\n".join(lines[start_line - 1 : end_line])
        for match in QUALIFIED_REFERENCE_RE.finditer(snippet):
            alias = str(match.group("alias") or "").strip().lower()
            target_name = normalize_symbol_name(str(match.group("name") or ""))
            if not alias or not target_name:
                continue
            binding = import_bindings.get(alias)
            target_file = str(binding["target_file"]) if binding is not None else None
            if target_file is None:
                target_file = resolve_import(f"{alias}.{target_name}", module_index)
            if target_file is None or target_file == file_path:
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol_id,
                    "target_file": target_file,
                    "target_names": (target_name,),
                    "type": "references_symbol",
                },
            )
            reference_candidates.setdefault(
                edge_id,
                {
                    "reference_edge_id": edge_id,
                    "source_symbol_id": symbol_id,
                    "source_file": file_path,
                    "target_symbol_id": None,
                    "target_file": target_file,
                    "target_names": (target_name,),
                    "reference_type": "references_symbol",
                },
            )
        for match in TYPE_REFERENCE_RE.finditer(snippet):
            raw_target = normalize_target(str(match.group("name") or ""))
            if not raw_target:
                continue
            canonical_target = raw_target.lower()
            leaf_name = raw_target.rsplit(".", 1)[-1]
            leaf_name_key = leaf_name.lower()
            if (
                leaf_name_key in RESERVED_SYMBOL_NAMES
                or leaf_name_key in BUILTIN_TYPE_NAMES
                or leaf_name_key == symbol_name.lower()
            ):
                continue
            if "." in canonical_target:
                target_file = resolve_import(canonical_target, module_index)
            else:
                binding = import_bindings.get(leaf_name_key)
                target_file = str(binding["target_file"]) if binding is not None else None
                if target_file is None:
                    target_file = resolve_same_namespace_reference(
                        current_file=file_path,
                        current_namespace=current_namespace,
                        type_name=leaf_name_key,
                        module_index=module_index,
                        resolve_import=resolve_import,
                    )
            if target_file is None or target_file == file_path:
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol_id,
                    "target_file": target_file,
                    "target_names": (leaf_name,),
                    "type": "references_symbol",
                },
            )
            reference_candidates.setdefault(
                edge_id,
                {
                    "reference_edge_id": edge_id,
                    "source_symbol_id": symbol_id,
                    "source_file": file_path,
                    "target_symbol_id": None,
                    "target_file": target_file,
                    "target_names": (leaf_name,),
                    "reference_type": "references_symbol",
                },
            )
    return (
        symbol_entries,
        parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=stable_identifier,
            resolve_import=resolve_import,
        ),
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )

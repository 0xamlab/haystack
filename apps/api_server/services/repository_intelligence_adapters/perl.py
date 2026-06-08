from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

PACKAGE_RE = re.compile(
    r"^\s*package\s+(?P<target>[A-Za-z_][A-Za-z0-9_:]*)\s*;",
    re.MULTILINE,
)
USE_STATEMENT_RE = re.compile(
    r"^\s*use\s+(?P<target>[A-Za-z_][A-Za-z0-9_:]*)(?P<body>[^\n;]*);",
    re.MULTILINE,
)
USE_RE = re.compile(
    r"^\s*use\s+(?P<target>[A-Za-z_][A-Za-z0-9_:]*)",
    re.MULTILINE,
)
REQUIRE_RE = re.compile(
    r"^\s*require\s+(?:(?P<quote>['\"])(?P<target>[^'\"]+)(?P=quote)|(?P<bare>[A-Za-z_][A-Za-z0-9_:./-]*))\s*;",
    re.MULTILINE,
)
SUB_DECL_RE = re.compile(r"^\s*sub\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b", re.MULTILINE)
QUALIFIED_REFERENCE_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_:]*)->(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
)
CALL_RE = re.compile(r"\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
QUOTED_ARG_RE = re.compile(r"'([^']+)'|\"([^\"]+)\"")
SIMPLE_ARG_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_:]*\b")
IGNORED_IMPORT_TARGETS = frozenset(
    {
        "5.010",
        "5.012",
        "5.014",
        "5.016",
        "5.018",
        "5.020",
        "5.022",
        "5.024",
        "5.026",
        "5.028",
        "5.030",
        "5.032",
        "5.034",
        "strict",
        "warnings",
        "utf8",
        "feature",
        "constant",
        "lib",
        "parent",
        "base",
    }
)
RESERVED_SYMBOL_NAMES = frozenset(
    {
        "BEGIN",
        "CHECK",
        "CORE",
        "DESTROY",
        "END",
        "INIT",
        "UNITCHECK",
        "and",
        "cmp",
        "do",
        "else",
        "elsif",
        "eq",
        "for",
        "foreach",
        "ge",
        "gt",
        "if",
        "isa",
        "le",
        "lock",
        "lt",
        "my",
        "ne",
        "not",
        "or",
        "our",
        "package",
        "require",
        "return",
        "state",
        "sub",
        "undef",
        "unless",
        "until",
        "use",
        "while",
        "xor",
    }
)


def module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix not in {".pl", ".pm", ".psgi"}:
        return set()
    aliases: set[str] = set()
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    for match in PACKAGE_RE.finditer(text):
        package_name = str(match.group("target") or "").strip()
        if package_name:
            aliases.add(package_name)
    source_parts = list(path.parts)
    for source_root in ("lib", "script", "scripts", "bin", "app"):
        if source_root not in source_parts:
            continue
        root_index = source_parts.index(source_root)
        module_parts = list(source_parts[root_index + 1 :])
        if not module_parts:
            continue
        module_parts[-1] = PurePosixPath(module_parts[-1]).stem
        module_name = "::".join(part for part in module_parts if part)
        if module_name:
            aliases.add(module_name)
        break
    if path.stem:
        aliases.add(path.stem)
    return {alias for alias in aliases if alias}


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = import_target.strip()
    if not normalized_target:
        return None
    current_dir = PurePosixPath(current_file).parent
    module_path = normalized_target.replace("::", "/")
    candidate_keys: list[str] = [normalized_target]
    if (
        normalized_target.startswith(".")
        or "/" in normalized_target
        or normalized_target.endswith((".pl", ".pm", ".psgi"))
    ):
        relative_base = normalize_repository_relative_path(str(current_dir / normalized_target))
        if relative_base:
            candidate_keys.extend(
                (
                    relative_base,
                    f"{relative_base}.pl",
                    f"{relative_base}.pm",
                    f"{relative_base}.psgi",
                )
            )
    else:
        candidate_keys.extend(
            (
                module_path,
                f"{module_path}.pm",
                f"{module_path}.pl",
                f"lib/{module_path}.pm",
                f"lib/{module_path}.pl",
                f"script/{module_path}.pl",
                f"bin/{module_path}.pl",
            )
        )
    for candidate_key in candidate_keys:
        if not candidate_key:
            continue
        resolved = module_index.get(candidate_key)
        if resolved is not None and resolved != current_file:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            f"{module_path}.pm",
            f"{module_path}.pl",
            f"{module_path}.psgi",
            f"/{PurePosixPath(module_path).name}.pm",
            f"/{PurePosixPath(module_path).name}.pl",
            f"/{PurePosixPath(module_path).name}.psgi",
        ],
    )


def extract_use_args(body: str) -> tuple[str, ...]:
    normalized_body = body.strip()
    if not normalized_body:
        return ()
    args: list[str] = []
    seen: set[str] = set()

    def _append_arg(value: str) -> None:
        normalized_value = value.strip()
        if not normalized_value or normalized_value in seen:
            return
        seen.add(normalized_value)
        args.append(normalized_value)

    scrubbed_body = normalized_body
    cursor = 0
    paired_delimiters = {"(": ")", "[": "]", "{": "}", "<": ">"}
    while True:
        qw_index = scrubbed_body.find("qw", cursor)
        if qw_index < 0:
            break
        delimiter_index = qw_index + 2
        while delimiter_index < len(scrubbed_body) and scrubbed_body[delimiter_index].isspace():
            delimiter_index += 1
        if delimiter_index >= len(scrubbed_body):
            break
        opener = scrubbed_body[delimiter_index]
        if opener.isalnum() or opener == "_":
            cursor = delimiter_index
            continue
        closer = paired_delimiters.get(opener, opener)
        content_start = delimiter_index + 1
        content_end = scrubbed_body.find(closer, content_start)
        if content_end < 0:
            break
        for token in scrubbed_body[content_start:content_end].split():
            _append_arg(token)
        scrubbed_body = (
            scrubbed_body[:qw_index]
            + (" " * (content_end + 1 - qw_index))
            + scrubbed_body[content_end + 1 :]
        )
        cursor = qw_index + 1

    for match in QUOTED_ARG_RE.finditer(scrubbed_body):
        _append_arg(str(match.group(1) or match.group(2) or ""))
    scrubbed_body = QUOTED_ARG_RE.sub(" ", scrubbed_body)
    for token in SIMPLE_ARG_RE.findall(scrubbed_body):
        if token in {"qw", "use"}:
            continue
        _append_arg(token)
    return tuple(args)


def is_package_like(value: str) -> bool:
    normalized = value.strip()
    return bool(
        normalized
        and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_:]*", normalized)
        and ("::" in normalized or normalized[0].isupper())
    )


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str, str, str | None]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    ambiguous_bindings: set[str] = set()

    def _register_dependency(
        *,
        import_target: str,
        line_offset: int,
        dependency_type: str,
        target_symbol: str | None = None,
        ignore_pragma: bool = False,
    ) -> str | None:
        normalized_target = import_target.strip()
        if not normalized_target:
            return None
        if ignore_pragma and normalized_target in IGNORED_IMPORT_TARGETS:
            return None
        target_file = resolve_import(
            current_file=file_path,
            import_target=normalized_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        normalized_symbol = (target_symbol or normalized_target.rsplit("::", 1)[-1]).strip() or None
        dependency_key = (
            target_file,
            normalized_target,
            dependency_type,
            normalized_symbol,
        )
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                _Dependency(
                    dependency_edge_id=stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": normalized_target,
                            "symbol": normalized_symbol,
                            "kind": dependency_type,
                            "line": line_offset,
                        },
                    ),
                    source_file=file_path,
                    target_file=target_file,
                    target_symbol=normalized_symbol,
                    dependency_type=dependency_type,
                )
            )
        return target_file

    def _register_import_binding(binding: _ImportedSymbolBinding) -> None:
        existing = import_bindings.get(binding.alias)
        if existing is None:
            import_bindings[binding.alias] = binding
            return
        if existing == binding:
            return
        ambiguous_bindings.add(binding.alias)

    for match in USE_STATEMENT_RE.finditer(text):
        import_target = str(match.group("target") or "").strip()
        if not import_target:
            continue
        target_file = _register_dependency(
            import_target=import_target,
            line_offset=match.start(),
            dependency_type="imports",
            ignore_pragma=True,
        )
        for imported_name in extract_use_args(str(match.group("body") or "")):
            if (
                not imported_name
                or imported_name in RESERVED_SYMBOL_NAMES
                or imported_name.startswith(("-", ":"))
            ):
                continue
            if is_package_like(imported_name):
                _register_dependency(
                    import_target=imported_name,
                    line_offset=match.start(),
                    dependency_type="references",
                )
                continue
            if target_file is None:
                continue
            _register_import_binding(
                _ImportedSymbolBinding(
                    alias=imported_name,
                    target_file=target_file,
                    target_names=(imported_name,),
                )
            )

    for match in REQUIRE_RE.finditer(text):
        _register_dependency(
            import_target=str(match.group("target") or match.group("bare") or "").strip(),
            line_offset=match.start(),
            dependency_type="imports",
            ignore_pragma=True,
        )

    for alias in ambiguous_bindings:
        import_bindings.pop(alias, None)
    return tuple(dependencies), import_bindings


def iter_imported_symbol_targets(
    snippet: str,
    import_bindings: dict[str, _ImportedSymbolBinding],
) -> Iterable[tuple[_ImportedSymbolBinding, str, int]]:
    for match in CALL_RE.finditer(snippet):
        binding = import_bindings.get(str(match.group("name") or "").strip())
        if binding is None or binding.target_file is None or not binding.target_names:
            continue
        for target_name in binding.target_names:
            if target_name and target_name not in RESERVED_SYMBOL_NAMES:
                yield binding, target_name, match.start()


def extract_dependency_candidates(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding]]:
    dependencies, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    dependency_list = list(dependencies)
    dependency_keys = {
        (dependency.target_file, dependency.target_symbol, dependency.dependency_type)
        for dependency in dependency_list
    }

    def _register_reference_dependency(
        *,
        import_target: str,
        line_offset: int,
        target_name: str,
        target_file: str | None = None,
    ) -> None:
        resolved_target_file = target_file or resolve_import(
            current_file=file_path,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        dependency_key = (resolved_target_file, target_name, "references")
        if dependency_key in dependency_keys:
            return
        dependency_keys.add(dependency_key)
        dependency_list.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": import_target,
                        "symbol": target_name,
                        "kind": "references",
                        "line": line_offset,
                    },
                ),
                source_file=file_path,
                target_file=resolved_target_file,
                target_symbol=target_name,
                dependency_type="references",
            )
        )

    for match in QUALIFIED_REFERENCE_RE.finditer(text):
        alias = str(match.group("alias") or "").strip()
        target_name = str(match.group("name") or "").strip()
        if not alias or not target_name or target_name in RESERVED_SYMBOL_NAMES:
            continue
        _register_reference_dependency(
            import_target=alias,
            line_offset=match.start(),
            target_name=target_name,
        )
    for binding, target_name, line_offset in iter_imported_symbol_targets(text, import_bindings):
        _register_reference_dependency(
            import_target=binding.alias,
            line_offset=line_offset,
            target_name=target_name,
            target_file=binding.target_file,
        )
    return tuple(dependency_list), import_bindings


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    dependencies, _ = extract_dependency_candidates(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    return dependencies


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
    lines = text.splitlines()
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_names: set[str] = set()
    for match in SUB_DECL_RE.finditer(text):
        symbol_name = str(match.group("name") or "").strip()
        if (
            not symbol_name
            or symbol_name in seen_symbol_names
            or symbol_name in RESERVED_SYMBOL_NAMES
        ):
            continue
        seen_symbol_names.add(symbol_name)
        line_no = text.count("\n", 0, match.start()) + 1
        symbol_entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": symbol_name,
                        "line": line_no,
                        "kind": "function",
                    },
                ),
                "symbol_name": symbol_name,
                "symbol_kind": "function",
                "start_line": line_no,
                "end_line": line_no,
                "signature": symbol_name,
            }
        )
    final_line = len(lines) if lines else 1
    for index, entry in enumerate(symbol_entries):
        if index + 1 < len(symbol_entries):
            entry["end_line"] = max(
                int(symbol_entries[index + 1]["start_line"]) - 1,
                int(entry["start_line"]),
            )
        else:
            entry["end_line"] = final_line
    symbols = tuple(
        _Symbol(
            symbol_id=str(entry["symbol_id"]),
            symbol_name=str(entry["symbol_name"]),
            symbol_kind=str(entry["symbol_kind"]),
            start_line=int(entry["start_line"]),
            end_line=int(entry["end_line"]),
            parent_symbol_id=None,
            signature=str(entry["signature"]),
        )
        for entry in symbol_entries
    )
    dependencies, import_bindings = extract_dependency_candidates(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    for symbol in symbols:
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for match in QUALIFIED_REFERENCE_RE.finditer(snippet):
            alias = str(match.group("alias") or "").strip()
            target_name = str(match.group("name") or "").strip()
            if not alias or not target_name or target_name in RESERVED_SYMBOL_NAMES:
                continue
            target_file = resolve_import(
                current_file=file_path,
                import_target=alias,
                module_index=module_index,
                normalize_repository_relative_path=normalize_repository_relative_path,
                resolve_suffix_match=resolve_suffix_match,
            )
            if target_file is None:
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol.symbol_id,
                    "target_file": target_file,
                    "target_names": (target_name,),
                    "type": "references_symbol",
                },
            )
            reference_candidates.setdefault(
                edge_id,
                _SymbolReferenceCandidate(
                    reference_edge_id=edge_id,
                    source_symbol_id=symbol.symbol_id,
                    source_file=file_path,
                    target_symbol_id=None,
                    target_file=target_file,
                    target_names=(target_name,),
                    reference_type="references_symbol",
                ),
            )
        for binding, target_name, _ in iter_imported_symbol_targets(snippet, import_bindings):
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol.symbol_id,
                    "target_file": binding.target_file,
                    "target_names": (target_name,),
                    "type": "references_symbol",
                },
            )
            reference_candidates.setdefault(
                edge_id,
                _SymbolReferenceCandidate(
                    reference_edge_id=edge_id,
                    source_symbol_id=symbol.symbol_id,
                    source_file=file_path,
                    target_symbol_id=None,
                    target_file=binding.target_file,
                    target_names=(target_name,),
                    reference_type="references_symbol",
                ),
            )
    return (
        symbols,
        dependencies,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _FileAnalysis,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str | None]
IsTestPath = Callable[[str], bool]
PreferNonTestPackageCandidates = Callable[..., Sequence[tuple[str, _Symbol]]]
BestPackageSymbolTarget = Callable[..., tuple[str, _Symbol] | None]

FUNC_DECL_RE = re.compile(
    r"^\s*func\s*(?:\([^)]*\)\s*)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
)
TYPE_DECL_RE = re.compile(
    r"^\s*type\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
)
IMPORT_SPEC_RE = re.compile(
    r'^\s*(?:(?P<alias>[A-Za-z_\.][A-Za-z0-9_\.]*)\s+)?\"(?P<path>[^\"]+)\"',
)
PACKAGE_RE = re.compile(
    r"^\s*package\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
SELECTOR_CALL_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*\.\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
)
CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
BUILTIN_CALL_NAMES = frozenset(
    {
        "append",
        "cap",
        "clear",
        "close",
        "complex",
        "copy",
        "delete",
        "func",
        "if",
        "imag",
        "len",
        "make",
        "max",
        "min",
        "new",
        "panic",
        "print",
        "println",
        "real",
        "recover",
        "return",
        "switch",
        "for",
    }
)


def current_package(text: str) -> str:
    match = PACKAGE_RE.search(text)
    if match is None:
        return ""
    return str(match.group("name") or "").strip()


def declared_symbol_names(text: str) -> tuple[str, ...]:
    symbol_names: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        stripped_line = line.strip()
        symbol_name: str | None = None
        symbol_match = FUNC_DECL_RE.match(stripped_line)
        if symbol_match is not None:
            symbol_name = str(symbol_match.group("name") or "").strip()
        else:
            type_match = TYPE_DECL_RE.match(stripped_line)
            if type_match is not None:
                symbol_name = str(type_match.group("name") or "").strip()
        if not symbol_name or symbol_name in seen:
            continue
        seen.add(symbol_name)
        symbol_names.append(symbol_name)
    return tuple(symbol_names)


def package_symbol_alias(
    *,
    file_path: str,
    package_name: str,
    symbol_name: str,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> str:
    package_dir = normalize_repository_relative_path(str(PurePosixPath(file_path).parent))
    package_root = package_dir if package_dir not in {"", "."} else "."
    return f"go::{package_root}::{package_name}::{symbol_name}"


def is_operational_reference_name(target_name: str) -> bool:
    normalized_name = target_name.strip()
    if not normalized_name:
        return False
    return normalized_name not in BUILTIN_CALL_NAMES


def extract_import_specs(text: str) -> list[tuple[str | None, str]]:
    imports: list[tuple[str | None, str]] = []
    in_block = False
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if in_block:
            if stripped == ")":
                in_block = False
                continue
            match = IMPORT_SPEC_RE.match(stripped)
            if match is not None:
                imports.append((match.group("alias"), match.group("path")))
            continue
        if stripped == "import(" or stripped == "import (":
            in_block = True
            continue
        if not stripped.startswith("import "):
            continue
        spec = stripped.removeprefix("import ").strip()
        if spec == "(":
            in_block = True
            continue
        match = IMPORT_SPEC_RE.match(spec)
        if match is not None:
            imports.append((match.group("alias"), match.group("path")))
    return imports


def _candidate_module_keys(
    base_path: str,
    *,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> tuple[str, ...]:
    normalized_base = normalize_repository_relative_path(base_path)
    if not normalized_base:
        return ()
    return tuple(
        dict.fromkeys(
            (
                normalized_base,
                normalized_base.replace("/", "."),
            )
        )
    )


def _is_package_directory_alias(import_target: str, resolved_path: str) -> bool:
    path = PurePosixPath(resolved_path)
    parent_name = path.parent.name.strip()
    return bool(parent_name) and parent_name == import_target


def resolve_import(
    *,
    import_target: str,
    module_index: dict[str, str],
    workspace_go_module_index: dict[str, tuple[str, ...]],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> str | None:
    direct_match = module_index.get(import_target)
    if direct_match is not None and (
        "/" in import_target
        or "." in import_target
        or _is_package_directory_alias(import_target, direct_match)
    ):
        return direct_match
    for module_name in sorted(workspace_go_module_index, key=len, reverse=True):
        if import_target != module_name and not import_target.startswith(f"{module_name}/"):
            continue
        subpath = import_target[len(module_name) :].lstrip("/")
        for module_root in workspace_go_module_index[module_name]:
            candidate_base = (
                f"{module_root}/{subpath}"
                if subpath and module_root
                else subpath or module_root
            )
            for candidate_key in _candidate_module_keys(
                candidate_base,
                normalize_repository_relative_path=normalize_repository_relative_path,
            ):
                resolved = module_index.get(candidate_key)
                if resolved is not None:
                    return resolved
    return None


def extend_module_index_with_package_symbol_aliases(
    *,
    root_path: Path,
    file_paths: Sequence[str],
    index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    is_test_path: IsTestPath,
) -> None:
    symbol_files: defaultdict[str, set[str]] = defaultdict(set)
    for file_path in file_paths:
        if PurePosixPath(file_path).suffix.lower() != ".go" or is_test_path(file_path):
            continue
        try:
            text = (root_path / file_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        package_name = current_package(text)
        if not package_name:
            continue
        for symbol_name in declared_symbol_names(text):
            if not is_operational_reference_name(symbol_name):
                continue
            symbol_files[
                package_symbol_alias(
                    file_path=file_path,
                    package_name=package_name,
                    symbol_name=symbol_name,
                    normalize_repository_relative_path=normalize_repository_relative_path,
                )
            ].add(file_path)
    for symbol_alias, resolved_files in sorted(symbol_files.items()):
        if len(resolved_files) != 1:
            continue
        resolved_file = next(iter(resolved_files))
        index.setdefault(symbol_alias, resolved_file)


def augment_package_symbol_references(
    *,
    analyses: Sequence[_FileAnalysis],
    stable_identifier: StableIdentifier,
    prefer_non_test_package_candidates: PreferNonTestPackageCandidates,
    best_package_symbol_target: BestPackageSymbolTarget,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> list[_FileAnalysis]:
    package_context_by_file: dict[str, str] = {}
    symbols_by_package_and_name: dict[tuple[str, str], list[tuple[str, _Symbol]]] = defaultdict(
        list
    )
    for analysis in analyses:
        if analysis.language != "go" or not analysis.symbols:
            continue
        text = analysis.text_payload.decode("utf-8", errors="replace")
        package_name = current_package(text)
        if not package_name:
            continue
        package_key = package_symbol_alias(
            file_path=analysis.file_path,
            package_name=package_name,
            symbol_name="",
            normalize_repository_relative_path=normalize_repository_relative_path,
        ).rsplit("::", 1)[0]
        package_context_by_file[analysis.file_path] = package_key
        for symbol in analysis.symbols:
            symbols_by_package_and_name[(package_key, symbol.symbol_name)].append(
                (analysis.file_path, symbol)
            )

    updated_analyses: list[_FileAnalysis] = []
    for analysis in analyses:
        if analysis.language != "go" or not analysis.symbols:
            updated_analyses.append(analysis)
            continue
        package_key = package_context_by_file.get(analysis.file_path)
        if not package_key:
            updated_analyses.append(analysis)
            continue
        text = analysis.text_payload.decode("utf-8", errors="replace")
        lines = text.splitlines()
        reference_candidates: dict[str, _SymbolReferenceCandidate] = {
            candidate.reference_edge_id: candidate for candidate in analysis.symbol_references
        }
        for symbol in analysis.symbols:
            snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
            for match in CALL_RE.finditer(snippet):
                target_name = match.group(1)
                if (
                    (match.start() > 0 and snippet[match.start() - 1] == ".")
                    or not is_operational_reference_name(target_name)
                ):
                    continue
                target_candidates = prefer_non_test_package_candidates(
                    source_file=analysis.file_path,
                    candidates=symbols_by_package_and_name.get((package_key, target_name), ()),
                )
                target_candidate = best_package_symbol_target(
                    source_file=analysis.file_path,
                    source_symbol_id=symbol.symbol_id,
                    candidates=target_candidates,
                )
                if target_candidate is None:
                    continue
                target_file, target_symbol = target_candidate
                edge_id = stable_identifier(
                    "ref",
                    {
                        "source_symbol_id": symbol.symbol_id,
                        "target_symbol_id": target_symbol.symbol_id,
                        "type": "references_symbol",
                    },
                )
                reference_candidates.setdefault(
                    edge_id,
                    _SymbolReferenceCandidate(
                        reference_edge_id=edge_id,
                        source_symbol_id=symbol.symbol_id,
                        source_file=analysis.file_path,
                        target_symbol_id=target_symbol.symbol_id,
                        target_file=target_file,
                        target_names=(target_symbol.symbol_name,),
                        reference_type="references_symbol",
                    ),
                )
        updated_analyses.append(
            _FileAnalysis(
                file_path=analysis.file_path,
                language=analysis.language,
                byte_size=analysis.byte_size,
                line_count=analysis.line_count,
                content_hash=analysis.content_hash,
                text_payload=analysis.text_payload,
                symbols=analysis.symbols,
                dependencies=analysis.dependencies,
                symbol_references=tuple(
                    reference_candidates[key] for key in sorted(reference_candidates)
                ),
            )
        )
    return updated_analyses


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    workspace_go_module_index: dict[str, tuple[str, ...]],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> tuple[_Dependency, ...]:
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    for alias, import_path in extract_import_specs(text):
        alias_name = alias or import_path.rstrip("/").rsplit("/", 1)[-1]
        target_file = resolve_import(
            import_target=import_path,
            module_index=module_index,
            workspace_go_module_index=workspace_go_module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
        )
        dependency_key = (target_file, alias_name, "imports")
        if dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {"file_path": file_path, "target": import_path, "alias": alias_name},
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=alias_name,
                dependency_type="imports",
            )
        )

    current_package_name = current_package(text)
    declared_names = set(declared_symbol_names(text))
    for match in CALL_RE.finditer(text):
        target_name = match.group(1)
        if (
            target_name in declared_names
            or not is_operational_reference_name(target_name)
            or (match.start() > 0 and text[match.start() - 1] == ".")
        ):
            continue
        target_file = module_index.get(
            package_symbol_alias(
                file_path=file_path,
                package_name=current_package_name,
                symbol_name=target_name,
                normalize_repository_relative_path=normalize_repository_relative_path,
            )
        )
        if target_file is None or target_file == file_path:
            continue
        dependency_key = (target_file, target_name, "references")
        if dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {"file_path": file_path, "target": target_name, "kind": "same_package"},
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_name,
                dependency_type="references",
            )
        )
    return tuple(dependencies)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    workspace_go_module_index: dict[str, tuple[str, ...]],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    symbols: list[_Symbol] = []
    dependencies: list[_Dependency] = []
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    symbols_by_name: dict[str, list[_Symbol]] = defaultdict(list)
    current_package_name = current_package(text)
    lines = text.splitlines()
    brace_depth = 0
    pending_symbol_index: int | None = None
    symbol_stack: list[dict[str, Any]] = []

    def _set_symbol_end(index: int, end_line: int) -> None:
        symbols[index] = _Symbol(**(symbols[index].__dict__ | {"end_line": end_line}))

    def _close_completed_symbols(line_no: int, current_depth: int) -> None:
        while symbol_stack and current_depth < int(symbol_stack[-1]["exit_depth"]):
            completed = symbol_stack.pop()
            _set_symbol_end(int(completed["index"]), line_no)

    for line_no, line in enumerate(lines, start=1):
        stripped_line = line.strip()
        starting_depth = brace_depth
        open_count = line.count("{")
        close_count = line.count("}")
        ending_depth = max(0, starting_depth + open_count - close_count)
        if pending_symbol_index is None:
            symbol_match = FUNC_DECL_RE.match(stripped_line)
            symbol_kind = None
            symbol_name = None
            if symbol_match is not None:
                symbol_kind = "method" if "(" in stripped_line.partition("func")[2] else "function"
                symbol_name = symbol_match.group("name")
            else:
                type_match = TYPE_DECL_RE.match(stripped_line)
                if type_match is not None:
                    symbol_kind = "type"
                    symbol_name = type_match.group("name")
            if symbol_kind is not None and symbol_name is not None:
                symbol = _Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "name": symbol_name,
                            "line": line_no,
                            "kind": symbol_kind,
                        },
                    ),
                    symbol_name=symbol_name,
                    symbol_kind=symbol_kind,
                    start_line=line_no,
                    end_line=line_no,
                    parent_symbol_id=None,
                    signature=symbol_name,
                )
                symbols.append(symbol)
                symbols_by_name[symbol_name].append(symbol)
                symbol_index = len(symbols) - 1
                if ending_depth > starting_depth:
                    symbol_stack.append({"index": symbol_index, "exit_depth": ending_depth})
                else:
                    pending_symbol_index = symbol_index
        brace_depth = ending_depth
        if pending_symbol_index is not None and brace_depth > starting_depth:
            symbol_stack.append({"index": pending_symbol_index, "exit_depth": brace_depth})
            pending_symbol_index = None
        _close_completed_symbols(line_no, brace_depth)

    final_line = len(lines) if lines else 1
    for stack_entry in symbol_stack:
        _set_symbol_end(int(stack_entry["index"]), final_line)
    if pending_symbol_index is not None:
        _set_symbol_end(pending_symbol_index, final_line)

    for alias, import_path in extract_import_specs(text):
        alias_name = alias or import_path.rstrip("/").rsplit("/", 1)[-1]
        target_file = resolve_import(
            import_target=import_path,
            module_index=module_index,
            workspace_go_module_index=workspace_go_module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
        )
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {"file_path": file_path, "target": import_path, "alias": alias_name},
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=alias_name,
                dependency_type="imports",
            )
        )
        import_bindings[alias_name] = _ImportedSymbolBinding(
            alias=alias_name,
            target_file=target_file,
            target_names=(alias_name,),
        )

    for symbol in symbols:
        snippet = "\n".join(lines[max(symbol.start_line - 1, 0) : min(symbol.end_line, len(lines))])
        for match in SELECTOR_CALL_RE.finditer(snippet):
            binding = import_bindings.get(match.group("alias"))
            if binding is None:
                continue
            target_name = match.group("name")
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
        for match in CALL_RE.finditer(snippet):
            target_name = match.group(1)
            if match.start() > 0 and snippet[match.start() - 1] == ".":
                continue
            if not is_operational_reference_name(target_name):
                continue
            for target_symbol in symbols_by_name.get(target_name, ()):
                if target_symbol.symbol_id == symbol.symbol_id:
                    continue
                edge_id = stable_identifier(
                    "ref",
                    {
                        "source_symbol_id": symbol.symbol_id,
                        "target_symbol_id": target_symbol.symbol_id,
                        "type": "references_symbol",
                    },
                )
                reference_candidates.setdefault(
                    edge_id,
                    _SymbolReferenceCandidate(
                        reference_edge_id=edge_id,
                        source_symbol_id=symbol.symbol_id,
                        source_file=file_path,
                        target_symbol_id=target_symbol.symbol_id,
                        target_file=file_path,
                        target_names=(target_symbol.symbol_name,),
                        reference_type="references_symbol",
                    ),
                )
            if not current_package_name:
                continue
            target_file = module_index.get(
                package_symbol_alias(
                    file_path=file_path,
                    package_name=current_package_name,
                    symbol_name=target_name,
                    normalize_repository_relative_path=normalize_repository_relative_path,
                )
            )
            if target_file is None or target_file == file_path:
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

    return (
        tuple(symbols),
        tuple(dependencies),
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )

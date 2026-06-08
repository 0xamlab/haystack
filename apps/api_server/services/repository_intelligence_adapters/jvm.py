from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _ImportedSymbolBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

CollectTypeSymbolEntries = Callable[..., list[dict[str, Any]]]
ResolveSuffixMatch = Callable[..., str | None]
StableIdentifier = Callable[[str, Any], str]
ImportBindingsResult = tuple[tuple[_Dependency, ...], dict[str, _ImportedSymbolBinding], str]

PACKAGE_RE = re.compile(
    r"^\s*package\s+(?P<target>[A-Za-z_][A-Za-z0-9_\.]*)\s*;?",
    re.MULTILINE,
)
IMPORT_RE = re.compile(
    r"^\s*import\s+(?:static\s+)?(?P<target>[A-Za-z_][A-Za-z0-9_\.]*)(?:\.(?:\*|_))?"
    r"(?:\s+as\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*))?\s*;?\s*$",
    re.MULTILINE,
)
TYPE_DECL_RE = re.compile(
    r"^\s*(?:(?:public|protected|private|internal|open|final|abstract|sealed|data|enum|annotation)\s+)*"
    r"(?:class|interface|record|object|enum|trait)\s+(?P<name>[A-Z][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)
TYPE_REFERENCE_RE = re.compile(r"\b(?P<name>[A-Z][A-Za-z0-9_]*)\b")
SCALA_PACKAGE_OBJECT_RE = re.compile(
    r"^\s*package\s+object\s+(?P<target>[A-Za-z_][A-Za-z0-9_\.]*)\s*\{?",
    re.MULTILINE,
)
SCALA_PACKAGE_RE = re.compile(
    r"^\s*package\s+(?!object\b)(?P<target>[A-Za-z_][A-Za-z0-9_\.]*)\s*(?:\{|$)",
    re.MULTILINE,
)
SCALA_IMPORT_RE = re.compile(
    r"^\s*import\s+(?P<target>[A-Za-z_][A-Za-z0-9_\.]*)(?:\._)?\s*$",
    re.MULTILINE,
)
SCALA_GROUPED_IMPORT_RE = re.compile(
    r"^\s*import\s+(?P<prefix>[A-Za-z_][A-Za-z0-9_\.]*)\.\{(?P<items>[^}]+)\}\s*$",
    re.MULTILINE,
)
SCALA_TYPE_DECL_RE = re.compile(
    r"^\s*(?:(?:case|sealed|abstract|final|implicit|lazy|private|protected)\s+)*"
    r"(?:class|trait|object|enum)\s+(?P<name>[A-Z][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)


def resolve_import(
    import_target: str,
    module_index: dict[str, str],
    *,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = import_target.strip()
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    normalized_path = normalized_target.replace(".", "/")
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            normalized_path,
            f"{normalized_path}.java",
            f"{normalized_path}.kt",
            f"{normalized_path}.kts",
            f"{normalized_path}.scala",
            f"{normalized_path}/package.scala",
        ],
    )


def scala_current_package(text: str) -> str:
    package_object_match = SCALA_PACKAGE_OBJECT_RE.search(text)
    if package_object_match is not None:
        return package_object_match.group("target")
    package_match = SCALA_PACKAGE_RE.search(text)
    if package_match is None:
        return ""
    return package_match.group("target")


def iter_scala_import_targets(
    text: str,
    *,
    current_package: str,
) -> tuple[str, ...]:
    targets: list[str] = []
    seen: set[str] = set()

    def _add(raw_target: str) -> None:
        normalized_target = raw_target.strip()
        if not normalized_target:
            return
        if normalized_target.endswith("._"):
            normalized_target = normalized_target[:-2]
        candidate_targets = [normalized_target]
        if "." not in normalized_target and current_package:
            candidate_targets.insert(0, f"{current_package}.{normalized_target}")
        for candidate_target in candidate_targets:
            if candidate_target and candidate_target not in seen:
                seen.add(candidate_target)
                targets.append(candidate_target)

    for match in SCALA_IMPORT_RE.finditer(text):
        _add(match.group("target"))
    for match in SCALA_GROUPED_IMPORT_RE.finditer(text):
        prefix = match.group("prefix").strip()
        for raw_item in match.group("items").split(","):
            item = raw_item.strip()
            if not item:
                continue
            if "=>" in item:
                item = item.split("=>", 1)[0].strip()
            if item == "_":
                _add(prefix)
                continue
            if item.startswith("given "):
                item = item[6:].strip()
            if not item or item == "_":
                continue
            _add(f"{prefix}.{item}")
    return tuple(targets)


def scala_package_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix != ".scala":
        return set()
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    current_package = scala_current_package(text)
    if not current_package:
        return set()
    if path.stem == "package":
        return {current_package}
    return {f"{current_package}.{path.stem}"}


def declared_type_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix not in {".java", ".kt", ".kts", ".scala", ".groovy"}:
        return set()
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    if path.suffix == ".scala":
        current_package = scala_current_package(text)
        declared_type_pattern = SCALA_TYPE_DECL_RE
    else:
        package_match = PACKAGE_RE.search(text)
        current_package = package_match.group("target") if package_match else ""
        declared_type_pattern = TYPE_DECL_RE
    aliases: set[str] = set()
    for match in declared_type_pattern.finditer(text):
        symbol_name = str(match.group("name") or "").strip()
        if not symbol_name:
            continue
        if current_package:
            aliases.add(f"{current_package}.{symbol_name}")
        elif "." not in symbol_name:
            aliases.add(symbol_name)
    return aliases


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    language: str,
    stable_identifier: StableIdentifier,
    resolve_import: Callable[[str, dict[str, str]], str | None],
) -> ImportBindingsResult:
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    import_bindings: dict[str, _ImportedSymbolBinding] = {}
    if language == "scala":
        current_package = scala_current_package(text)
        import_specs = tuple(
            (import_target, None)
            for import_target in iter_scala_import_targets(
                text,
                current_package=current_package,
            )
        )
    else:
        package_match = PACKAGE_RE.search(text)
        current_package = package_match.group("target") if package_match else ""
        import_specs = tuple(
            (
                str(match.group("target") or "").strip(),
                str(match.group("alias") or "").strip() or None,
            )
            for match in IMPORT_RE.finditer(text)
            if str(match.group("target") or "").strip()
        )
    for import_index, (import_target, import_alias) in enumerate(import_specs):
        target_symbol = import_target.rsplit(".", 1)[-1]
        target_file = resolve_import(import_target, module_index)
        dependency_key = (target_file, target_symbol, "imports")
        if dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {"file_path": file_path, "target": import_target, "index": import_index},
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=target_symbol,
                dependency_type="imports",
            )
        )
        import_bindings.setdefault(
            target_symbol,
            _ImportedSymbolBinding(
                alias=target_symbol,
                target_file=target_file,
                target_names=(target_symbol,),
            ),
        )
        if import_alias is not None:
            import_bindings.setdefault(
                import_alias,
                _ImportedSymbolBinding(
                    alias=import_alias,
                    target_file=target_file,
                    target_names=(target_symbol,),
                ),
            )
    return tuple(dependencies), import_bindings, current_package


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    language: str,
    collect_type_symbol_entries: CollectTypeSymbolEntries,
    stable_identifier: StableIdentifier,
    extract_import_bindings: Callable[..., ImportBindingsResult],
    resolve_import: Callable[[str, dict[str, str]], str | None],
) -> tuple[_Dependency, ...]:
    dependencies, import_bindings, current_package = extract_import_bindings(
        file_path,
        text,
        module_index,
        language=language,
    )
    dependency_entries = list(dependencies)
    dependency_keys = {
        (dependency.target_file, dependency.target_symbol, dependency.dependency_type)
        for dependency in dependency_entries
    }
    if not current_package:
        return tuple(dependency_entries)
    declared_type_pattern = SCALA_TYPE_DECL_RE if language == "scala" else TYPE_DECL_RE
    declared_type_names = {
        str(entry["symbol_name"])
        for entry in collect_type_symbol_entries(
            text,
            file_path=file_path,
            regex=declared_type_pattern,
        )
    }
    imported_short_names = {
        alias
        for alias in import_bindings
        if "." not in alias and alias not in declared_type_names
    }
    for match in TYPE_REFERENCE_RE.finditer(text):
        type_name = match.group("name")
        if type_name in declared_type_names or type_name in imported_short_names:
            continue
        import_target = f"{current_package}.{type_name}"
        target_file = resolve_import(import_target, module_index)
        if target_file is None or target_file == file_path:
            continue
        dependency_key = (target_file, type_name, "references")
        if dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        dependency_entries.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {"file_path": file_path, "target": import_target, "line": match.start()},
                ),
                source_file=file_path,
                target_file=target_file,
                target_symbol=type_name,
                dependency_type="references",
            )
        )
    return tuple(dependency_entries)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    language: str,
    collect_type_symbol_entries: CollectTypeSymbolEntries,
    stable_identifier: StableIdentifier,
    extract_import_bindings: Callable[..., ImportBindingsResult],
    resolve_import: Callable[[str, dict[str, str]], str | None],
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    declared_type_pattern = SCALA_TYPE_DECL_RE if language == "scala" else TYPE_DECL_RE
    symbol_entries = collect_type_symbol_entries(
        text,
        file_path=file_path,
        regex=declared_type_pattern,
    )
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
    declared_symbol_names = {symbol.symbol_name for symbol in symbols}
    _, import_bindings, current_package = extract_import_bindings(
        file_path,
        text,
        module_index,
        language=language,
    )
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    lines = text.splitlines()
    for symbol in symbols:
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for match in TYPE_REFERENCE_RE.finditer(snippet):
            type_name = match.group("name")
            if type_name in declared_symbol_names or type_name == symbol.symbol_name:
                continue
            binding = import_bindings.get(type_name)
            target_file = binding.target_file if binding is not None else None
            target_names = binding.target_names if binding is not None else (type_name,)
            if target_file is None and current_package:
                target_file = resolve_import(f"{current_package}.{type_name}", module_index)
            if target_file is None or target_file == file_path:
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol.symbol_id,
                    "target_file": target_file,
                    "target_names": target_names,
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
                    target_names=target_names,
                    reference_type="references_symbol",
                ),
            )
    return (
        symbols,
        parse_dependencies_only(
            file_path,
            text,
            module_index,
            language=language,
            collect_type_symbol_entries=collect_type_symbol_entries,
            stable_identifier=stable_identifier,
            extract_import_bindings=extract_import_bindings,
            resolve_import=resolve_import,
        ),
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )

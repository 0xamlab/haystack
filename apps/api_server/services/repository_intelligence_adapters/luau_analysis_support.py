from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    luau_primitives as repository_luau_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _JSImportBinding,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_luau_primitives.StableIdentifier
ResolveSuffixMatch = repository_luau_primitives.ResolveSuffixMatch
REQUIRE_RE = repository_luau_primitives.REQUIRE_RE
REQUIRE_BINDING_RE = repository_luau_primitives.REQUIRE_BINDING_RE
SCRIPT_REQUIRE_RE = repository_luau_primitives.SCRIPT_REQUIRE_RE
SCRIPT_REQUIRE_BINDING_RE = repository_luau_primitives.SCRIPT_REQUIRE_BINDING_RE
TS_IMPORT_RE = repository_luau_primitives.TS_IMPORT_RE
TS_IMPORT_BINDING_RE = repository_luau_primitives.TS_IMPORT_BINDING_RE
QUALIFIED_REFERENCE_RE = repository_luau_primitives.QUALIFIED_REFERENCE_RE
IMPORTED_CALL_RE = repository_luau_primitives.IMPORTED_CALL_RE
RESERVED_SYMBOL_NAMES = repository_luau_primitives.RESERVED_SYMBOL_NAMES
collect_symbol_entries = repository_luau_primitives.collect_symbol_entries
has_luau_path_hints = repository_luau_primitives.has_luau_path_hints
is_probable_luau_source = repository_luau_primitives.is_probable_luau_source
strip_comments = repository_luau_primitives.strip_comments

_WALLY_PACKAGE_NAME_RE = re.compile(
    r"(?ms)^\s*\[package\]\s.*?^\s*name\s*=\s*['\"](?P<name>[^'\"]+)['\"]"
)


def _normalize_module_parts(parts: list[str]) -> tuple[str, ...]:
    if not parts:
        return ()
    normalized_parts = [part for part in parts if part and part != "."]
    if not normalized_parts:
        return ()
    stem = PurePosixPath(normalized_parts[-1]).stem
    if stem == "init":
        normalized_parts = normalized_parts[:-1]
    else:
        normalized_parts[-1] = stem
    return tuple(part for part in normalized_parts if part)


def repository_root_relative_path(root_path: Path, project_root: Path) -> str:
    try:
        relative_path = project_root.relative_to(root_path)
    except ValueError:
        return ""
    return str(relative_path).replace("\\", "/").strip("/")


def repository_relative_from_prefix(file_path: str, prefix: str) -> str:
    if not prefix:
        return file_path
    prefix_with_slash = f"{prefix}/"
    if file_path.startswith(prefix_with_slash):
        return file_path[len(prefix_with_slash) :]
    return file_path


def _manifest_ancestors(root_path: Path, file_path: str) -> tuple[Path, ...]:
    absolute_path = (root_path / PurePosixPath(file_path)).resolve()
    root_resolved = root_path.resolve()
    ancestors: list[Path] = []
    for candidate in [absolute_path.parent, *absolute_path.parents]:
        if candidate == root_resolved or root_resolved in candidate.parents:
            ancestors.append(candidate)
        if candidate == root_resolved:
            break
    return tuple(ancestors)


def _find_luau_project_root(root_path: Path, file_path: str) -> Path:
    for candidate in _manifest_ancestors(root_path, file_path):
        if any(
            (candidate / manifest_name).is_file()
            for manifest_name in ("wally.toml", "default.project.json", "aftman.toml", "pesde.toml")
        ):
            return candidate
    return root_path


def _wally_package_name(project_root: Path) -> str | None:
    manifest_path = project_root / "wally.toml"
    try:
        text = manifest_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = _WALLY_PACKAGE_NAME_RE.search(text)
    if match is None:
        return None
    package_name = str(match.group("name") or "").strip()
    if not package_name:
        return None
    return package_name.rsplit("/", 1)[-1]


def module_aliases_for_path(*, root_path: Path, file_path: str) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in {".lua", ".luau"}:
        return set()
    project_root = _find_luau_project_root(root_path, file_path)
    project_root_relative = repository_root_relative_path(root_path, project_root)
    project_relative_path = (
        repository_relative_from_prefix(file_path, project_root_relative)
        if project_root_relative
        else file_path
    )
    project_relative = PurePosixPath(project_relative_path)
    aliases = {file_path, str(path.with_suffix("")), str(project_relative.with_suffix(""))}
    aliases.update(
        {
            str(path.with_suffix("")).replace("/", "."),
            str(project_relative.with_suffix("")).replace("/", "."),
            path.stem,
            project_relative.stem,
        }
    )
    source_parts = list(project_relative.parts)
    for source_root in ("src", "lib", "modules", "scripts", "server", "client", "shared", "app", "lua"):
        if source_root not in source_parts:
            continue
        root_index = source_parts.index(source_root)
        module_parts = _normalize_module_parts(list(source_parts[root_index + 1 :]))
        if not module_parts:
            continue
        module_path = "/".join(module_parts)
        aliases.update({module_path, module_path.replace("/", "."), f"{source_root}/{module_path}"})
        aliases.add(f"@{source_root}/{module_path}")
        break
    if path.stem == "init":
        parent = str(project_relative.parent)
        if parent and parent != ".":
            aliases.update({parent, parent.replace("/", "."), f"@{parent}"})
    package_name = _wally_package_name(project_root)
    if package_name and project_relative_path in {
        f"src/{package_name}.luau",
        f"src/{package_name}.lua",
        "src/init.luau",
        "src/init.lua",
        "init.luau",
        "init.lua",
    }:
        aliases.add(f"@{package_name}")
        aliases.add(package_name)
    return {alias for alias in aliases if alias and alias not in {".", "/", "@"}}


def _candidate_module_keys(base_path: str) -> tuple[str, ...]:
    normalized = str(PurePosixPath(base_path)).strip()
    if not normalized:
        return ()
    return (
        normalized,
        f"{normalized}.luau",
        f"{normalized}.lua",
        f"{normalized}/init.luau",
        f"{normalized}/init.lua",
    )


def _resolve_script_target(file_path: str, target: str) -> tuple[str, ...]:
    current_dir = PurePosixPath(file_path).parent
    parts = [part for part in target.split(".") if part]
    if not parts or parts[0] != "script":
        return ()
    parts = parts[1:]
    while parts and parts[0] == "Parent":
        current_dir = current_dir.parent
        parts = parts[1:]
    if not parts:
        return ()
    return _candidate_module_keys(str(current_dir.joinpath(*parts)))


def resolve_import(
    file_path: str,
    import_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = str(import_target or "").strip()
    if not normalized_target:
        return None
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match
    candidate_keys: list[str] = []
    if normalized_target.startswith("script."):
        candidate_keys.extend(_resolve_script_target(file_path, normalized_target))
    elif normalized_target.startswith(("./", "../")):
        base_path = str(PurePosixPath(file_path).parent.joinpath(normalized_target))
        candidate_keys.extend(_candidate_module_keys(base_path))
    else:
        candidate_keys.extend(_candidate_module_keys(normalized_target))
        if normalized_target.startswith("@"):
            candidate_keys.extend(_candidate_module_keys(normalized_target[1:]))
        if "/" not in normalized_target and "." in normalized_target and not normalized_target.startswith("@"):
            candidate_keys.extend(_candidate_module_keys(normalized_target.replace(".", "/")))
        module_path = normalized_target.replace(".", "/") if "." in normalized_target else normalized_target
        for source_root in ("src", "lib", "modules", "scripts", "server", "client", "shared", "app", "lua", "lune/modules"):
            candidate_keys.extend(_candidate_module_keys(f"{source_root}/{module_path}"))
    ordered_candidates: list[str] = []
    seen: set[str] = set()
    for candidate in candidate_keys:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        ordered_candidates.append(candidate)
    for candidate_key in ordered_candidates:
        resolved = module_index.get(candidate_key)
        if resolved is not None:
            return resolved
    return resolve_suffix_match(module_index=module_index, suffixes=ordered_candidates)


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[tuple[_Dependency, ...], dict[str, _JSImportBinding]]:
    dependencies: list[_Dependency] = []
    bindings: dict[str, _JSImportBinding] = {}
    seen_dependency_keys: set[tuple[str, int]] = set()

    def _append_dependency(import_target: str, offset: int) -> None:
        dependency_key = (import_target, offset)
        if dependency_key in seen_dependency_keys:
            return
        seen_dependency_keys.add(dependency_key)
        dependencies.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {"file_path": file_path, "target": import_target, "line": offset},
                ),
                source_file=file_path,
                target_file=resolve_import(
                    file_path,
                    import_target,
                    module_index=module_index,
                    resolve_suffix_match=resolve_suffix_match,
                ),
                target_symbol=PurePosixPath(import_target.replace(".", "/")).name,
                dependency_type="imports",
            )
        )

    for match in REQUIRE_RE.finditer(text):
        _append_dependency(str(match.group("target") or ""), match.start())
    for match in SCRIPT_REQUIRE_RE.finditer(text):
        _append_dependency(str(match.group("target") or ""), match.start())
    for match in TS_IMPORT_RE.finditer(text):
        _append_dependency(str(match.group("target") or ""), match.start())

    for pattern in (REQUIRE_BINDING_RE, SCRIPT_REQUIRE_BINDING_RE, TS_IMPORT_BINDING_RE):
        for match in pattern.finditer(text):
            alias = str(match.group("alias") or "").strip()
            import_target = str(match.group("target") or "").strip()
            if not alias or not import_target:
                continue
            target_member = str(match.groupdict().get("member") or "").strip()
            bindings[alias] = _JSImportBinding(
                alias=alias,
                target_file=resolve_import(
                    file_path,
                    import_target,
                    module_index=module_index,
                    resolve_suffix_match=resolve_suffix_match,
                ),
                target_names=((target_member,) if target_member else (PurePosixPath(import_target).stem or alias,)),
            )
    return tuple(dependencies), bindings


def iter_reference_targets(
    snippet: str,
    bindings: dict[str, _JSImportBinding],
) -> tuple[tuple[_JSImportBinding, str], ...]:
    targets: list[tuple[_JSImportBinding, str]] = []
    for match in QUALIFIED_REFERENCE_RE.finditer(snippet):
        binding = bindings.get(match.group("alias"))
        if binding is None or binding.target_file is None:
            continue
        target_name = str(match.group("name") or "").strip()
        if not target_name or target_name in RESERVED_SYMBOL_NAMES:
            continue
        targets.append((binding, target_name))
    for match in IMPORTED_CALL_RE.finditer(snippet):
        binding = bindings.get(match.group("alias"))
        if binding is None or binding.target_file is None or not binding.target_names:
            continue
        for target_name in binding.target_names:
            if not target_name or target_name in RESERVED_SYMBOL_NAMES:
                continue
            targets.append((binding, target_name))
    return tuple(targets)


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    dependencies, bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
    )
    dependency_candidates = list(dependencies)
    seen_keys = {
        (dependency.target_file, dependency.target_symbol, dependency.dependency_type)
        for dependency in dependency_candidates
    }
    for binding, target_name in iter_reference_targets(text, bindings):
        dependency_key = (binding.target_file, target_name, "references")
        if dependency_key in seen_keys:
            continue
        seen_keys.add(dependency_key)
        dependency_candidates.append(
            _Dependency(
                dependency_edge_id=stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": binding.target_file,
                        "symbol": target_name,
                        "kind": "references",
                    },
                ),
                source_file=file_path,
                target_file=binding.target_file,
                target_symbol=target_name,
                dependency_type="references",
            )
        )
    return tuple(dependency_candidates)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[
    tuple[_Symbol, ...],
    tuple[_Dependency, ...],
    tuple[_SymbolReferenceCandidate, ...],
]:
    symbol_entries = collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
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
    dependencies, bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_suffix_match=resolve_suffix_match,
    )
    lines = text.splitlines()
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}
    for symbol in symbols:
        snippet = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        for binding, target_name in iter_reference_targets(snippet, bindings):
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

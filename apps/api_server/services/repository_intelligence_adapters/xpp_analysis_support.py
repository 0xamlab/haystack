from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services.repository_intelligence_adapters import (
    xpp_primitives as repository_xpp_primitives,
)
from apps.api_server.services.repository_intelligence_contracts import (
    _Dependency,
    _Symbol,
    _SymbolReferenceCandidate,
)

StableIdentifier = repository_xpp_primitives.StableIdentifier
NormalizeRepositoryRelativePath = repository_xpp_primitives.NormalizeRepositoryRelativePath
ResolveSuffixMatch = repository_xpp_primitives.ResolveSuffixMatch

_KNOWN_SUFFIXES = repository_xpp_primitives._KNOWN_SUFFIXES
_line_count = repository_xpp_primitives._line_count
_line_number = repository_xpp_primitives._line_number
declared_object_name = repository_xpp_primitives.declared_object_name
has_xpp_path_hints = repository_xpp_primitives.has_xpp_path_hints
include_targets_for_document = repository_xpp_primitives.include_targets_for_document
instance_call_targets = repository_xpp_primitives.instance_call_targets
is_probable_xpp_descriptor_config = repository_xpp_primitives.is_probable_xpp_descriptor_config
is_probable_xpp_source = repository_xpp_primitives.is_probable_xpp_source
new_reference_targets = repository_xpp_primitives.new_reference_targets
parse_xpp_document = repository_xpp_primitives.parse_xpp_document
relation_targets_for_document = repository_xpp_primitives.relation_targets_for_document
static_call_targets = repository_xpp_primitives.static_call_targets
strip_comments = repository_xpp_primitives.strip_comments
typed_variable_bindings = repository_xpp_primitives.typed_variable_bindings
_CollectedSymbol = repository_xpp_primitives._CollectedSymbol


def _resolve_named_target(
    *,
    current_file: str,
    target_name: str,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[str | None, str]:
    normalized_target = str(target_name or "").strip()
    if not normalized_target:
        return None, ""
    direct_match = module_index.get(normalized_target)
    if direct_match is not None:
        return direct_match, normalized_target
    target_basename = normalized_target.rsplit(".", 1)[-1]
    if target_basename != normalized_target:
        direct_match = module_index.get(target_basename)
        if direct_match is not None:
            return direct_match, target_basename
    current_path = PurePosixPath(current_file)
    sibling_candidates = [
        str(current_path.with_name(f"{target_basename}.xml")),
        str(current_path.with_name(f"{target_basename}.xpp")),
        str(current_path.with_name(f"{target_basename}.xpo")),
    ]
    resolved = resolve_suffix_match(
        module_index=module_index,
        suffixes=[
            *sibling_candidates,
            f"/AxClass/{target_basename}.xml",
            f"/AxClassExtension/{target_basename}.xml",
            f"/{target_basename}.xpp",
            f"/{target_basename}.xpo",
            f"/{target_basename}.xml",
        ],
    )
    return resolved, target_basename


def _register_dependency(
    *,
    file_path: str,
    target_file: str | None,
    target_symbol: str | None,
    dependency_type: str,
    target_hint: str,
    line_no: int,
    stable_identifier: StableIdentifier,
    dependency_keys: set[tuple[str | None, str | None, str]],
    dependencies: list[_Dependency],
) -> None:
    dependency_key = (target_file, target_symbol, dependency_type)
    if dependency_key in dependency_keys:
        return
    dependency_keys.add(dependency_key)
    dependencies.append(
        _Dependency(
            dependency_edge_id=stable_identifier(
                "dep",
                {
                    "file_path": file_path,
                    "target": target_hint,
                    "symbol": target_symbol,
                    "line": line_no,
                    "type": dependency_type,
                },
            ),
            source_file=file_path,
            target_file=target_file,
            target_symbol=target_symbol,
            dependency_type=dependency_type,
        )
    )


def _collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_CollectedSymbol, ...]:
    document = parse_xpp_document(path=PurePosixPath(file_path), text=text)
    if document is None:
        return ()
    object_name = declared_object_name(document)
    if not object_name:
        return ()
    class_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {
                "file_path": file_path,
                "symbol_name": object_name,
                "symbol_kind": "class",
                "start_line": 1,
            },
        ),
        symbol_name=object_name,
        symbol_kind="class",
        start_line=1,
        end_line=document.line_count,
        parent_symbol_id=None,
        signature=f"class {object_name}",
    )
    collected_symbols: list[_CollectedSymbol] = [
        _CollectedSymbol(
            symbol=class_symbol,
            start_line=1,
            end_line=document.line_count,
        )
    ]
    for method in document.methods:
        method_end_line = max(method.start_line, method.start_line + _line_count(method.body) - 1)
        collected_symbols.append(
            _CollectedSymbol(
                symbol=_Symbol(
                    symbol_id=stable_identifier(
                        "sym",
                        {
                            "file_path": file_path,
                            "symbol_name": method.method_name,
                            "symbol_kind": "method",
                            "start_line": method.start_line,
                        },
                    ),
                    symbol_name=method.method_name,
                    symbol_kind="method",
                    start_line=method.start_line,
                    end_line=method_end_line,
                    parent_symbol_id=class_symbol.symbol_id,
                    signature=f"{object_name}.{method.method_name}",
                ),
                start_line=method.start_line,
                end_line=method_end_line,
            )
        )
    return tuple(collected_symbols)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_SUFFIXES:
        return set()
    source_text = text
    if source_text is None:
        try:
            source_text = (root_path / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return set()
    if is_probable_xpp_descriptor_config(path=path, text=source_text):
        return set()
    if not is_probable_xpp_source(path=path, text=source_text):
        return set()
    aliases = {
        file_path,
        str(path.with_suffix("")),
        path.stem,
    }
    collected_symbols = _collect_symbols(
        file_path=file_path,
        text=source_text,
        stable_identifier=stable_identifier,
    )
    class_name = ""
    for collected_symbol in collected_symbols:
        symbol = collected_symbol.symbol
        aliases.add(symbol.symbol_name)
        signature = str(symbol.signature or "").strip()
        if signature:
            aliases.add(signature)
        if symbol.symbol_kind == "class":
            class_name = symbol.symbol_name
        elif class_name:
            aliases.add(f"{class_name}.{symbol.symbol_name}")
            aliases.add(f"{class_name}::{symbol.symbol_name}")
    return {alias for alias in aliases if alias}


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> tuple[_Dependency, ...]:
    del normalize_repository_relative_path
    path = PurePosixPath(file_path)
    if is_probable_xpp_descriptor_config(path=path, text=text):
        return ()
    if not is_probable_xpp_source(path=path, text=text):
        return ()
    document = parse_xpp_document(path=path, text=text)
    if document is None:
        return ()
    dependencies: list[_Dependency] = []
    dependency_keys: set[tuple[str | None, str | None, str]] = set()
    for relation_target in relation_targets_for_document(document):
        target_file, target_symbol = _resolve_named_target(
            current_file=file_path,
            target_name=relation_target,
            module_index=module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        _register_dependency(
            file_path=file_path,
            target_file=target_file,
            target_symbol=target_symbol,
            dependency_type="extends",
            target_hint=relation_target,
            line_no=1,
            stable_identifier=stable_identifier,
            dependency_keys=dependency_keys,
            dependencies=dependencies,
        )
    for include_target, line_no in include_targets_for_document(document):
        target_file, target_symbol = _resolve_named_target(
            current_file=file_path,
            target_name=include_target,
            module_index=module_index,
            resolve_suffix_match=resolve_suffix_match,
        )
        _register_dependency(
            file_path=file_path,
            target_file=target_file,
            target_symbol=target_symbol,
            dependency_type="imports",
            target_hint=include_target,
            line_no=line_no,
            stable_identifier=stable_identifier,
            dependency_keys=dependency_keys,
            dependencies=dependencies,
        )
    for method in document.methods:
        variable_bindings = typed_variable_bindings(method.body)
        for target_name, line_offset in new_reference_targets(method.body):
            target_file, target_symbol = _resolve_named_target(
                current_file=file_path,
                target_name=target_name,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
            _register_dependency(
                file_path=file_path,
                target_file=target_file,
                target_symbol=target_symbol,
                dependency_type="references",
                target_hint=target_name,
                line_no=method.start_line + line_offset - 1,
                stable_identifier=stable_identifier,
                dependency_keys=dependency_keys,
                dependencies=dependencies,
            )
        for owner_name, method_name, line_offset in static_call_targets(method.body):
            target_file, target_symbol = _resolve_named_target(
                current_file=file_path,
                target_name=owner_name,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
            _register_dependency(
                file_path=file_path,
                target_file=target_file,
                target_symbol=method_name or target_symbol,
                dependency_type="references",
                target_hint=f"{owner_name}::{method_name}",
                line_no=method.start_line + line_offset - 1,
                stable_identifier=stable_identifier,
                dependency_keys=dependency_keys,
                dependencies=dependencies,
            )
        for owner_name, method_name, line_offset in instance_call_targets(method.body):
            target_type = variable_bindings.get(owner_name.lower())
            if not target_type:
                continue
            target_file, target_symbol = _resolve_named_target(
                current_file=file_path,
                target_name=target_type,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
            _register_dependency(
                file_path=file_path,
                target_file=target_file,
                target_symbol=method_name or target_symbol,
                dependency_type="references",
                target_hint=f"{owner_name}.{method_name}",
                line_no=method.start_line + line_offset - 1,
                stable_identifier=stable_identifier,
                dependency_keys=dependency_keys,
                dependencies=dependencies,
            )
    return tuple(dependencies)


def _source_symbol_id_for_line(
    *,
    line_no: int,
    symbols: tuple[_Symbol, ...],
) -> str | None:
    for symbol in symbols:
        if (
            symbol.symbol_kind == "method"
            and int(symbol.start_line) <= line_no <= int(symbol.end_line)
        ):
            return str(symbol.symbol_id)
    if symbols:
        return str(symbols[0].symbol_id)
    return None


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
    path = PurePosixPath(file_path)
    if is_probable_xpp_descriptor_config(path=path, text=text):
        return (), (), ()
    if not is_probable_xpp_source(path=path, text=text):
        return (), (), ()
    document = parse_xpp_document(path=path, text=text)
    if document is None:
        return (), (), ()
    collected_symbols = _collect_symbols(
        file_path=file_path,
        text=text,
        stable_identifier=stable_identifier,
    )
    symbols = tuple(collected_symbol.symbol for collected_symbol in collected_symbols)
    dependencies = parse_dependencies_only(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        normalize_repository_relative_path=normalize_repository_relative_path,
        resolve_suffix_match=resolve_suffix_match,
    )
    reference_candidates: dict[str, _SymbolReferenceCandidate] = {}

    def _register_reference(
        *,
        source_symbol_id: str | None,
        target_file: str | None,
        target_names: tuple[str, ...],
        line_no: int,
        target_hint: str,
    ) -> None:
        if source_symbol_id is None or not target_names:
            return
        if target_file == file_path:
            return
        edge_id = stable_identifier(
            "ref",
            {
                "file_path": file_path,
                "symbol_id": source_symbol_id,
                "target": target_hint,
                "target_file": target_file,
                "target_names": target_names,
                "line": line_no,
                "type": "references_symbol",
            },
        )
        reference_candidates.setdefault(
            edge_id,
            _SymbolReferenceCandidate(
                reference_edge_id=edge_id,
                source_symbol_id=source_symbol_id,
                source_file=file_path,
                target_symbol_id=None,
                target_file=target_file,
                target_names=target_names,
                reference_type="references_symbol",
            ),
        )

    if symbols:
        class_symbol_id = symbols[0].symbol_id
        for relation_target in relation_targets_for_document(document):
            target_file, target_symbol = _resolve_named_target(
                current_file=file_path,
                target_name=relation_target,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
            _register_reference(
                source_symbol_id=class_symbol_id,
                target_file=target_file,
                target_names=(target_symbol or relation_target,),
                line_no=1,
                target_hint=relation_target,
            )

    for method in document.methods:
        variable_bindings = typed_variable_bindings(method.body)
        for target_name, line_offset in new_reference_targets(method.body):
            target_file, target_symbol = _resolve_named_target(
                current_file=file_path,
                target_name=target_name,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
            _register_reference(
                source_symbol_id=_source_symbol_id_for_line(
                    line_no=method.start_line + line_offset - 1,
                    symbols=symbols,
                ),
                target_file=target_file,
                target_names=(target_symbol or target_name,),
                line_no=method.start_line + line_offset - 1,
                target_hint=target_name,
            )
        for owner_name, method_name, line_offset in static_call_targets(method.body):
            target_file, target_symbol = _resolve_named_target(
                current_file=file_path,
                target_name=owner_name,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
            _register_reference(
                source_symbol_id=_source_symbol_id_for_line(
                    line_no=method.start_line + line_offset - 1,
                    symbols=symbols,
                ),
                target_file=target_file,
                target_names=tuple(
                    name
                    for name in (method_name, f"{target_symbol or owner_name}.{method_name}")
                    if name
                ),
                line_no=method.start_line + line_offset - 1,
                target_hint=f"{owner_name}::{method_name}",
            )
        for owner_name, method_name, line_offset in instance_call_targets(method.body):
            target_type = variable_bindings.get(owner_name.lower())
            if not target_type:
                continue
            target_file, target_symbol = _resolve_named_target(
                current_file=file_path,
                target_name=target_type,
                module_index=module_index,
                resolve_suffix_match=resolve_suffix_match,
            )
            _register_reference(
                source_symbol_id=_source_symbol_id_for_line(
                    line_no=method.start_line + line_offset - 1,
                    symbols=symbols,
                ),
                target_file=target_file,
                target_names=tuple(
                    name
                    for name in (method_name, f"{target_symbol or target_type}.{method_name}")
                    if name
                ),
                line_no=method.start_line + line_offset - 1,
                target_hint=f"{owner_name}.{method_name}",
            )
    return (
        symbols,
        dependencies,
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )

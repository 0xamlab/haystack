from __future__ import annotations

from pathlib import Path, PurePosixPath

from apps.api_server.services import (
    repository_intelligence_contracts as repository_contracts,
)
from apps.api_server.services import (
    repository_intelligence_file_content as repository_file_content,
)
from apps.api_server.services.repository_intelligence_adapters import (
    scratch_primitives as repository_scratch_primitives,
)

_Dependency = repository_contracts._Dependency
_Symbol = repository_contracts._Symbol
_SymbolReferenceCandidate = repository_contracts._SymbolReferenceCandidate

StableIdentifier = repository_scratch_primitives.StableIdentifier
_KNOWN_SUFFIXES = repository_scratch_primitives._KNOWN_SUFFIXES
_ordered_names = repository_scratch_primitives._ordered_names
block_field_name = repository_scratch_primitives.block_field_name
broadcast_name_from_block = repository_scratch_primitives.broadcast_name_from_block
broadcast_names = repository_scratch_primitives.broadcast_names
custom_block_signatures = repository_scratch_primitives.custom_block_signatures
handler_symbol_name = repository_scratch_primitives.handler_symbol_name
has_scratch_path_hints = repository_scratch_primitives.has_scratch_path_hints
input_block_ids = repository_scratch_primitives.input_block_ids
is_probable_scratch_source = repository_scratch_primitives.is_probable_scratch_source
load_project_payload = repository_scratch_primitives.load_project_payload
procedure_signature_from_call = repository_scratch_primitives.procedure_signature_from_call
procedure_signature_from_definition = (
    repository_scratch_primitives.procedure_signature_from_definition
)
project_targets = repository_scratch_primitives.project_targets
target_blocks = repository_scratch_primitives.target_blocks
target_name = repository_scratch_primitives.target_name
top_level_event_blocks = repository_scratch_primitives.top_level_event_blocks
walk_script_block_ids = repository_scratch_primitives.walk_script_block_ids


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_SUFFIXES:
        return set()
    aliases = {
        file_path,
        path.stem,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
        f"project:{path.stem}",
    }
    try:
        text = repository_file_content.read_repository_text(root_path / path)
    except OSError:
        text = ""
    payload = load_project_payload(text)
    if payload is None:
        return {alias for alias in aliases if alias}
    for index, target in enumerate(project_targets(payload)):
        current_target_name = target_name(target, index)
        target_signatures = custom_block_signatures(target)
        target_broadcast_names = broadcast_names(target)
        aliases.update(
            _ordered_names(
                current_target_name,
                f"target:{current_target_name}",
                f"sprite:{current_target_name}",
            )
        )
        aliases.update(target_signatures)
        aliases.update(f"procedure:{signature}" for signature in target_signatures if signature)
        aliases.update(target_broadcast_names)
        aliases.update(
            f"broadcast:{broadcast_name}"
            for broadcast_name in target_broadcast_names
            if broadcast_name
        )
    return {alias for alias in aliases if alias}


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
) -> tuple[_Dependency, ...]:
    del file_path, module_index, stable_identifier
    payload = load_project_payload(text)
    if payload is None:
        return ()
    return ()


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
) -> tuple[tuple[_Symbol, ...], tuple[_Dependency, ...], tuple[_SymbolReferenceCandidate, ...]]:
    del module_index
    payload = load_project_payload(text)
    if payload is None:
        return (), (), ()

    line_count = max(1, text.count("\n") + (1 if text else 0))
    project_name = PurePosixPath(file_path).stem or "ScratchProject"
    symbols: list[_Symbol] = []
    reference_candidates: list[_SymbolReferenceCandidate] = []
    line_cursor = 1

    project_symbol_id = stable_identifier(
        "symbol",
        {"file_path": file_path, "name": project_name, "kind": "module"},
    )
    symbols.append(
        _Symbol(
            symbol_id=project_symbol_id,
            symbol_name=project_name,
            symbol_kind="module",
            start_line=line_cursor,
            end_line=line_count,
            parent_symbol_id=None,
            signature=None,
        )
    )
    line_cursor += 1

    broadcasts_by_name: dict[str, str] = {}
    for target in project_targets(payload):
        for broadcast_name in broadcast_names(target):
            if broadcast_name in broadcasts_by_name:
                continue
            broadcast_symbol_id = stable_identifier(
                "symbol",
                {
                    "file_path": file_path,
                    "name": broadcast_name,
                    "kind": "symbol",
                    "parent": project_symbol_id,
                },
            )
            broadcasts_by_name[broadcast_name] = broadcast_symbol_id
            symbols.append(
                _Symbol(
                    symbol_id=broadcast_symbol_id,
                    symbol_name=broadcast_name,
                    symbol_kind="symbol",
                    start_line=line_cursor,
                    end_line=line_cursor,
                    parent_symbol_id=project_symbol_id,
                    signature=None,
                )
            )
            line_cursor += 1

    seen_reference_keys: set[tuple[str, str | None, str | None]] = set()
    for index, target in enumerate(project_targets(payload)):
        current_target_name = target_name(target, index)
        current_target_kind = "module" if bool(target.get("isStage")) else "class"
        current_target_symbol_id = stable_identifier(
            "symbol",
            {
                "file_path": file_path,
                "name": current_target_name,
                "kind": current_target_kind,
                "parent": project_symbol_id,
            },
        )
        symbols.append(
            _Symbol(
                symbol_id=current_target_symbol_id,
                symbol_name=current_target_name,
                symbol_kind=current_target_kind,
                start_line=min(line_cursor, line_count),
                end_line=min(line_cursor, line_count),
                parent_symbol_id=project_symbol_id,
                signature=None,
            )
        )
        line_cursor += 1

        blocks = target_blocks(target)
        procedures_by_signature: dict[str, str] = {}
        owner_symbol_by_block_id: dict[str, str] = {}

        for block_id, block in blocks.items():
            if str(block.get("opcode") or "") != "procedures_definition":
                continue
            signature = procedure_signature_from_definition(blocks=blocks, block=block)
            if not signature:
                continue
            procedure_symbol_id = stable_identifier(
                "symbol",
                {
                    "file_path": file_path,
                    "name": signature,
                    "kind": "function",
                    "parent": current_target_symbol_id,
                },
            )
            procedures_by_signature[signature] = procedure_symbol_id
            symbols.append(
                _Symbol(
                    symbol_id=procedure_symbol_id,
                    symbol_name=signature,
                    symbol_kind="function",
                    start_line=min(line_cursor, line_count),
                    end_line=min(line_cursor, line_count),
                    parent_symbol_id=current_target_symbol_id,
                    signature=signature,
                )
            )
            line_cursor += 1
            for descendant_id in walk_script_block_ids(start_block_id=block_id, blocks=blocks):
                owner_symbol_by_block_id[descendant_id] = procedure_symbol_id

        for block_id, block in top_level_event_blocks(target):
            handler_name = handler_symbol_name(blocks=blocks, block=block)
            if not handler_name:
                continue
            handler_symbol_id = stable_identifier(
                "symbol",
                {
                    "file_path": file_path,
                    "name": handler_name,
                    "kind": "method",
                    "parent": current_target_symbol_id,
                    "block_id": block_id,
                },
            )
            symbols.append(
                _Symbol(
                    symbol_id=handler_symbol_id,
                    symbol_name=handler_name,
                    symbol_kind="method",
                    start_line=min(line_cursor, line_count),
                    end_line=min(line_cursor, line_count),
                    parent_symbol_id=current_target_symbol_id,
                    signature=None,
                )
            )
            line_cursor += 1
            for descendant_id in walk_script_block_ids(start_block_id=block_id, blocks=blocks):
                owner_symbol_by_block_id.setdefault(descendant_id, handler_symbol_id)

        for block_id, block in blocks.items():
            source_symbol_id = owner_symbol_by_block_id.get(block_id, current_target_symbol_id)
            opcode = str(block.get("opcode") or "").strip()
            if opcode == "procedures_call":
                signature = procedure_signature_from_call(block)
                if not signature:
                    continue
                target_symbol_id = procedures_by_signature.get(signature)
                reference_key = (source_symbol_id, target_symbol_id, signature)
                if reference_key in seen_reference_keys:
                    continue
                seen_reference_keys.add(reference_key)
                reference_candidates.append(
                    _SymbolReferenceCandidate(
                        reference_edge_id=stable_identifier(
                            "ref",
                            {
                                "file_path": file_path,
                                "symbol_id": source_symbol_id,
                                "target": signature,
                                "type": "references_symbol",
                            },
                        ),
                        source_symbol_id=source_symbol_id,
                        source_file=file_path,
                        target_symbol_id=target_symbol_id,
                        target_file=file_path if target_symbol_id is not None else None,
                        target_names=_ordered_names(signature, f"procedure:{signature}"),
                        reference_type="references_symbol",
                    )
                )
                continue
            if opcode not in {
                "event_broadcast",
                "event_broadcastandwait",
                "event_whenbroadcastreceived",
            }:
                continue
            broadcast_name = broadcast_name_from_block(blocks=blocks, block=block)
            if not broadcast_name:
                continue
            target_symbol_id = broadcasts_by_name.get(broadcast_name)
            reference_key = (source_symbol_id, target_symbol_id, broadcast_name)
            if reference_key in seen_reference_keys:
                continue
            seen_reference_keys.add(reference_key)
            reference_candidates.append(
                _SymbolReferenceCandidate(
                    reference_edge_id=stable_identifier(
                        "ref",
                        {
                            "file_path": file_path,
                            "symbol_id": source_symbol_id,
                            "target": broadcast_name,
                            "type": "references_symbol",
                        },
                    ),
                    source_symbol_id=source_symbol_id,
                    source_file=file_path,
                    target_symbol_id=target_symbol_id,
                    target_file=file_path if target_symbol_id is not None else None,
                    target_names=_ordered_names(
                        broadcast_name,
                        f"broadcast:{broadcast_name}",
                    ),
                    reference_type="references_symbol",
                )
            )

    return tuple(symbols), (), tuple(reference_candidates)

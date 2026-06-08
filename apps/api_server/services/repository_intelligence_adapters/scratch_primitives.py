from __future__ import annotations

import json
from collections.abc import Callable, Collection
from pathlib import Path, PurePosixPath
from typing import Any

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

_KNOWN_SUFFIXES = frozenset({".sb3"})
_HANDLER_OPCODE_NAMES = {
    "event_whenbackdropswitchesto": "when backdrop switches to",
    "event_whenbroadcastreceived": "when I receive",
    "event_whenflagclicked": "when flag clicked",
    "event_whengreaterthan": "when greater than",
    "event_whenkeypressed": "when key pressed",
    "event_whenstageclicked": "when stage clicked",
    "event_whenthisspriteclicked": "when this sprite clicked",
}


def _normalize_name(raw_value: Any) -> str:
    return str(raw_value or "").strip()


def _ordered_names(*values: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        normalized = _normalize_name(raw_value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def has_scratch_path_hints(path: Path | PurePosixPath) -> bool:
    return PurePosixPath(path).suffix.lower() in _KNOWN_SUFFIXES


def load_project_payload(text: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    targets = payload.get("targets")
    if not isinstance(targets, list):
        return None
    return payload


def is_probable_scratch_source(*, path: Path | PurePosixPath, text: str) -> bool:
    if not has_scratch_path_hints(Path(path)):
        return False
    payload = load_project_payload(text)
    return payload is not None and isinstance(payload.get("meta"), dict)


def project_targets(payload: dict[str, Any] | None) -> tuple[dict[str, Any], ...]:
    if not isinstance(payload, dict):
        return ()
    targets = payload.get("targets")
    if not isinstance(targets, list):
        return ()
    normalized_targets = [target for target in targets if isinstance(target, dict)]
    return tuple(normalized_targets)


def target_name(target: dict[str, Any], index: int) -> str:
    return _normalize_name(target.get("name")) or f"Target{index + 1}"


def target_blocks(target: dict[str, Any]) -> dict[str, dict[str, Any]]:
    blocks = target.get("blocks")
    if not isinstance(blocks, dict):
        return {}
    return {
        str(block_id): block
        for block_id, block in blocks.items()
        if isinstance(block_id, str) and isinstance(block, dict)
    }


def _looks_like_block_id(value: str) -> bool:
    normalized = _normalize_name(value)
    if not normalized:
        return False
    return any(not character.isalnum() for character in normalized)


def _block_reference(
    value: Any,
    *,
    known_block_ids: Collection[str] | None = None,
) -> str | None:
    if isinstance(value, str):
        normalized_value = _normalize_name(value)
        if _looks_like_block_id(normalized_value):
            return normalized_value
        if known_block_ids is not None and normalized_value in known_block_ids:
            return normalized_value
    if not isinstance(value, list | tuple):
        return None
    for item in reversed(value):
        resolved = _block_reference(item, known_block_ids=known_block_ids)
        if resolved:
            return resolved
    return None


def input_block_ids(
    block: dict[str, Any],
    *,
    known_block_ids: Collection[str] | None = None,
) -> tuple[str, ...]:
    inputs = block.get("inputs")
    if not isinstance(inputs, dict):
        return ()
    ordered: list[str] = []
    seen: set[str] = set()
    for value in inputs.values():
        resolved = _block_reference(value, known_block_ids=known_block_ids)
        if resolved and resolved not in seen:
            seen.add(resolved)
            ordered.append(resolved)
    return tuple(ordered)


def block_field_name(block: dict[str, Any], field_name: str) -> str:
    fields = block.get("fields")
    if not isinstance(fields, dict):
        return ""
    value = fields.get(field_name)
    if isinstance(value, list | tuple) and value:
        return _normalize_name(value[0])
    return _normalize_name(value)


def input_literal_name(block: dict[str, Any], input_name: str) -> str:
    inputs = block.get("inputs")
    if not isinstance(inputs, dict):
        return ""
    value = inputs.get(input_name)
    if not isinstance(value, list | tuple) or len(value) < 2:
        return ""
    nested = value[1]
    if isinstance(nested, list | tuple):
        if len(nested) >= 2:
            return _normalize_name(nested[1])
        if nested:
            return _normalize_name(nested[0])
    if isinstance(nested, str) and not _looks_like_block_id(nested):
        return _normalize_name(nested)
    return ""


def procedure_signature_from_definition(
    *,
    blocks: dict[str, dict[str, Any]],
    block: dict[str, Any],
) -> str:
    prototype_id = _block_reference(
        (block.get("inputs") or {}).get("custom_block"),
        known_block_ids=blocks,
    )
    if not prototype_id:
        return ""
    prototype = blocks.get(prototype_id) or {}
    mutation = prototype.get("mutation")
    if isinstance(mutation, dict):
        return _normalize_name(mutation.get("proccode"))
    return ""


def procedure_signature_from_call(block: dict[str, Any]) -> str:
    mutation = block.get("mutation")
    if not isinstance(mutation, dict):
        return ""
    return _normalize_name(mutation.get("proccode"))


def broadcast_name_from_block(
    *,
    blocks: dict[str, dict[str, Any]],
    block: dict[str, Any],
) -> str:
    direct_name = block_field_name(block, "BROADCAST_OPTION")
    if direct_name:
        return direct_name
    input_block_id = _block_reference(
        (block.get("inputs") or {}).get("BROADCAST_INPUT"),
        known_block_ids=blocks,
    )
    if input_block_id:
        referenced_block = blocks.get(input_block_id) or {}
        referenced_name = block_field_name(referenced_block, "BROADCAST_OPTION")
        if referenced_name:
            return referenced_name
    return input_literal_name(block, "BROADCAST_INPUT")


def broadcast_names(target: dict[str, Any]) -> tuple[str, ...]:
    names: list[str] = []
    seen: set[str] = set()
    broadcasts = target.get("broadcasts")
    if isinstance(broadcasts, dict):
        for value in broadcasts.values():
            normalized = _normalize_name(value)
            if normalized and normalized not in seen:
                seen.add(normalized)
                names.append(normalized)
    blocks = target_blocks(target)
    for block in blocks.values():
        opcode = _normalize_name(block.get("opcode"))
        if opcode not in {
            "event_broadcast",
            "event_broadcastandwait",
            "event_whenbroadcastreceived",
        }:
            continue
        normalized = broadcast_name_from_block(blocks=blocks, block=block)
        if normalized and normalized not in seen:
            seen.add(normalized)
            names.append(normalized)
    return tuple(names)


def custom_block_signatures(target: dict[str, Any]) -> tuple[str, ...]:
    blocks = target_blocks(target)
    signatures: list[str] = []
    seen: set[str] = set()
    for block in blocks.values():
        if _normalize_name(block.get("opcode")) != "procedures_definition":
            continue
        signature = procedure_signature_from_definition(blocks=blocks, block=block)
        if signature and signature not in seen:
            seen.add(signature)
            signatures.append(signature)
    return tuple(signatures)


def top_level_event_blocks(target: dict[str, Any]) -> tuple[tuple[str, dict[str, Any]], ...]:
    blocks = target_blocks(target)
    return tuple(
        (block_id, block)
        for block_id, block in blocks.items()
        if bool(block.get("topLevel"))
        and _normalize_name(block.get("opcode")).startswith("event_")
    )


def handler_symbol_name(
    *,
    blocks: dict[str, dict[str, Any]],
    block: dict[str, Any],
) -> str:
    opcode = _normalize_name(block.get("opcode"))
    base_name = _HANDLER_OPCODE_NAMES.get(opcode, opcode.replace("_", " "))
    if opcode == "event_whenbroadcastreceived":
        broadcast_name = broadcast_name_from_block(blocks=blocks, block=block)
        if broadcast_name:
            return f"{base_name} {broadcast_name}"
        return base_name
    if opcode == "event_whenkeypressed":
        key_name = block_field_name(block, "KEY_OPTION")
        if key_name:
            return f"{base_name} {key_name}"
        return base_name
    if opcode == "event_whenbackdropswitchesto":
        backdrop_name = block_field_name(block, "BACKDROP")
        if backdrop_name:
            return f"{base_name} {backdrop_name}"
        return base_name
    if opcode == "event_whengreaterthan":
        sensor_name = block_field_name(block, "WHENGREATERTHANMENU")
        if sensor_name:
            return f"{base_name} {sensor_name}"
        return base_name
    return base_name


def walk_script_block_ids(
    *,
    start_block_id: str,
    blocks: dict[str, dict[str, Any]],
) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    pending = [start_block_id]
    while pending:
        current_id = pending.pop()
        if current_id in seen:
            continue
        block = blocks.get(current_id)
        if block is None:
            continue
        seen.add(current_id)
        ordered.append(current_id)
        next_block_id = _block_reference(
            block.get("next"),
            known_block_ids=blocks,
        )
        if next_block_id:
            pending.append(next_block_id)
        for input_block_id in reversed(
            input_block_ids(block, known_block_ids=blocks)
        ):
            pending.append(input_block_id)
    return tuple(ordered)

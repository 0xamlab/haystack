from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from apps.api_server.services.cline_live_run_proof import LIVE_RUN_PROOF_PATH
from apps.api_server.services.cline_proof_common import read_json


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_or_none(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = read_json(path)
    return payload if isinstance(payload, dict) else {}


def _normalize_reference(entry: Any, *, source_artifact: str) -> dict[str, str] | None:
    if isinstance(entry, str):
        reference = _string_or_none(entry)
        if reference is None:
            return None
        return {"source_artifact": source_artifact, "reference": reference}
    if not isinstance(entry, dict):
        return None
    normalized = {"source_artifact": source_artifact}
    for field_name in ("reference", "run_id", "agent_run_id", "session_id", "run_dir"):
        value = _string_or_none(entry.get(field_name))
        if value is not None:
            normalized[field_name] = value
    return normalized if len(normalized) > 1 else None


def _dedupe_references(
    references: Iterable[dict[str, str]],
) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for reference in references:
        key = tuple(sorted(reference.items()))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(reference)
    return deduped


def _summary_artifact_references(path: Path) -> list[dict[str, str]]:
    payload = _load_json_object(path)
    references: list[dict[str, str]] = []
    source_artifact = str(path)
    for entry in _as_list(payload.get("agent_run_references")):
        normalized = _normalize_reference(entry, source_artifact=source_artifact)
        if normalized is not None:
            references.append(normalized)
    details = _as_dict(payload.get("details"))
    for entry in _as_list(details.get("agent_run_references")):
        normalized = _normalize_reference(entry, source_artifact=source_artifact)
        if normalized is not None:
            references.append(normalized)
    return references


def _live_run_proof_references(root: Path) -> list[dict[str, str]]:
    payload = _load_json_object(root / LIVE_RUN_PROOF_PATH)
    if not payload:
        return []
    reference = {"source_artifact": str((root / LIVE_RUN_PROOF_PATH).resolve())}
    for field_name in ("run_id", "agent_run_id", "session_id", "run_dir"):
        value = _string_or_none(payload.get(field_name))
        if value is not None:
            reference[field_name] = value
    return [reference] if len(reference) > 1 else []


def collect_agent_run_references(
    *,
    root: Path | str,
    summary_artifacts: Iterable[str],
) -> list[dict[str, str]]:
    resolved_root = Path(root).resolve()
    references: list[dict[str, str]] = []
    for summary_artifact in summary_artifacts:
        artifact_path = Path(summary_artifact)
        if not artifact_path.is_absolute():
            artifact_path = resolved_root / artifact_path
        references.extend(_summary_artifact_references(artifact_path))
    if not references:
        references.extend(_live_run_proof_references(resolved_root))
    return _dedupe_references(references)

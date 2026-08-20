from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import Any

from algenta.map_parsing import _parse_source
from algenta.runtime_connection_descriptors import normalize_local_runtime_source
from algenta.runtime_errors import RuntimeValidationError
from algenta.runtime_local_execution import (
    LocalSource,
    infer_numeric_fields,
    infer_typed_fields,
)
from algenta.runtime_model_source_registration import SourceRegistration
from algenta.runtime_source_naming import (
    runtime_source_name,
    unique_runtime_source_name,
)

LocalSourceInput = str | Path | list[dict[str, Any]] | Mapping[str, Any]


def register_local_source(
    local_sources: MutableMapping[str, LocalSource],
    source: LocalSourceInput | None,
    *,
    explicit_name: str | None,
    started_at: float,
) -> SourceRegistration:
    if source is None:
        raise RuntimeValidationError(
            "missing_local_source",
            "Runtime(mode='local') connect() requires a local source input.",
        )

    display_name = explicit_name or runtime_source_name(source, len(local_sources))
    try:
        normalized_source = (
            normalize_local_runtime_source(source) if isinstance(source, Mapping) else source
        )
        records = _parse_source(normalized_source)
    except (OSError, ValueError) as exc:
        raise RuntimeValidationError(
            "invalid_local_source",
            f"Unable to connect the local source: {exc}",
            {"name": display_name},
        ) from exc
    if not records:
        raise RuntimeValidationError(
            "empty_source",
            "Connected source is empty and cannot be queried.",
            {"name": display_name},
        )

    source_name = unique_runtime_source_name(
        source,
        len(local_sources),
        set(local_sources),
        explicit_name=explicit_name,
    )
    fields = _ordered_fields(records)
    numeric_fields = infer_numeric_fields(records, fields)
    typed_fields = infer_typed_fields(records, fields)
    dataset_id = _stable_hash({"source_name": source_name, "fields": fields})[:24]
    schema_revision = _stable_hash({"dataset_id": dataset_id, "fields": fields})
    local_sources[source_name] = LocalSource(
        name=source_name,
        records=records,
        fields=fields,
        schema_revision=schema_revision,
        dataset_id=dataset_id,
        numeric_fields=numeric_fields,
    )
    latency_ms = round((time.perf_counter() - started_at) * 1000, 3)
    return SourceRegistration(
        source_id=dataset_id,
        dataset_id=dataset_id,
        name=source_name,
        status="ready",
        ingest_mode="local",
        source_schema={"fields": list(fields), "typed_fields": typed_fields},
        planner_cache_hit=False,
        planner_schema_revision=schema_revision,
        planner_prewarm_ms=0.0,
        latency_ms=latency_ms,
        row_count=len(records),
        typed_fields=typed_fields,
    )


def _ordered_fields(records: list[dict[str, Any]]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for record in records:
        for field_name in record:
            if field_name in seen:
                continue
            seen.add(field_name)
            ordered.append(field_name)
    return tuple(ordered)


def _stable_hash(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()

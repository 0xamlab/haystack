from __future__ import annotations

from collections.abc import Callable
from typing import Any

from algenta.branding import source_bundle_banner, source_import_banner
from algenta.runtime_errors import AlgentaRuntimeError, RuntimeValidationError
from algenta.runtime_model_import_preview import (
    ImportBundlePreview,
    ImportFailure,
    ImportPreview,
)
from algenta.runtime_model_source_registration import SourceRegistration


def registration_preview_fields(registration: SourceRegistration) -> list[str]:
    if not isinstance(registration.source_schema, dict):
        return []
    raw_fields = registration.source_schema.get("fields", [])
    if isinstance(raw_fields, list):
        fields = [str(field) for field in raw_fields if str(field).strip()]
        if fields:
            return fields
    raw_columns = registration.source_schema.get("columns", [])
    if not isinstance(raw_columns, list):
        return []
    preview_fields: list[str] = []
    for column in raw_columns:
        if not isinstance(column, dict):
            continue
        name_value = column.get("name")
        if isinstance(name_value, str) and name_value.strip():
            preview_fields.append(name_value)
    return preview_fields


def build_import_preview(
    *,
    source: Any,
    registration: SourceRegistration,
    mode: str,
    source_ref: str | None,
    local_source_count: int,
    source_ref_label: Callable[[Any, int], str],
    runtime_source_name: Callable[[Any, int], str],
) -> ImportPreview:
    resolved_source_ref = source_ref or source_ref_label(source, local_source_count)
    preview = source_import_banner(
        source_name=registration.name or runtime_source_name(source, local_source_count),
        source_ref=resolved_source_ref,
        mode=mode,
        status=registration.status,
        row_count=registration.row_count,
        fields=registration_preview_fields(registration),
        schema_revision=registration.planner_schema_revision,
        latency_ms=registration.latency_ms,
    )
    return ImportPreview(registration=registration, preview=preview)


def build_import_bundle_preview(
    *,
    sources: list[Any],
    mode: str,
    names: list[str | None] | None,
    source_refs: list[str | None] | None,
    description: str | None,
    connect: Callable[..., SourceRegistration],
    source_ref_label: Callable[[Any, int], str],
    bundle_overlap_lines: Callable[[list[SourceRegistration]], list[str]],
) -> ImportBundlePreview:
    if names is not None and len(names) != len(sources):
        raise RuntimeValidationError(
            "invalid_names_length",
            "import_bundle_preview() names must match the number of sources.",
            {"sources": len(sources), "names": len(names)},
        )
    if source_refs is not None and len(source_refs) != len(sources):
        raise RuntimeValidationError(
            "invalid_source_refs_length",
            "import_bundle_preview() source_refs must match the number of sources.",
            {"sources": len(sources), "source_refs": len(source_refs)},
        )

    registrations: list[SourceRegistration] = []
    failures: list[ImportFailure] = []
    for index, source in enumerate(sources):
        source_name = names[index] if names is not None else None
        resolved_source_ref = (
            source_refs[index] if source_refs is not None else source_ref_label(source, index)
        )
        try:
            registrations.append(connect(source, name=source_name, description=description))
        except AlgentaRuntimeError as exc:
            failures.append(
                ImportFailure(
                    source_ref=resolved_source_ref,
                    code=exc.code,
                    message=str(exc),
                    name=source_name,
                )
            )

    preview = source_bundle_banner(
        mode=mode,
        imported_count=len(registrations),
        failure_count=len(failures),
        total_rows=sum(registration.row_count or 0 for registration in registrations),
        source_names=[
            registration.name or registration.dataset_id or "source"
            for registration in registrations
        ],
        overlaps=bundle_overlap_lines(registrations),
        failures=[f"{failure.name or failure.source_ref}: {failure.code}" for failure in failures],
    )
    return ImportBundlePreview(
        registrations=registrations,
        failures=failures,
        preview=preview,
    )


__all__ = [
    "build_import_bundle_preview",
    "build_import_preview",
    "registration_preview_fields",
]

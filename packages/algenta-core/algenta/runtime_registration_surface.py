from __future__ import annotations

from collections.abc import Mapping
from functools import cache
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any

from algenta.runtime_errors import RuntimeValidationError

if TYPE_CHECKING:
    from types import ModuleType

    from algenta.runtime_model_import_preview import (
        ImportBundlePreview,
        ImportPreview,
    )
    from algenta.runtime_model_source_registration import SourceRegistration

LocalSourceInput = str | Path | list[dict[str, Any]] | Mapping[str, Any]


@cache
def _runtime_bundle_overlap_module() -> ModuleType:
    return import_module("algenta.runtime_bundle_overlap")


@cache
def _runtime_connection_descriptors_module() -> ModuleType:
    return import_module("algenta.runtime_connection_descriptors")


@cache
def _runtime_import_preview_module() -> ModuleType:
    return import_module("algenta.runtime_import_preview")


@cache
def _runtime_local_registration_module() -> ModuleType:
    return import_module("algenta.runtime_local_registration")


@cache
def _runtime_model_source_registration_module() -> ModuleType:
    return import_module("algenta.runtime_model_source_registration")


@cache
def _runtime_source_naming_module() -> ModuleType:
    return import_module("algenta.runtime_source_naming")


def connect_runtime_source(
    runtime: Any,
    source: LocalSourceInput | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    connector_id: str | None = None,
    connector: Mapping[str, Any] | None = None,
    selection: Mapping[str, Any] | None = None,
    dataset_name: str | None = None,
    persist: bool = False,
    visibility: str | None = None,
    connection_name: str | None = None,
) -> SourceRegistration:
    start = runtime._perf_counter()
    if runtime._uses_api_transport():
        connection_descriptors = _runtime_connection_descriptors_module()
        registration_name = dataset_name or name
        if connector_id is not None or connector is not None:
            return runtime._connector_surface()._connect_saved_or_inline_connector_dataset(
                connector_id=connector_id,
                connector=connector,
                selection=selection,
                dataset_name=registration_name,
                description=description,
                persist=persist,
                visibility=visibility,
                connection_name=connection_name,
            )
        if not isinstance(source, Mapping):
            raise RuntimeValidationError(
                "api_connect_requires_source_descriptor",
                "API and self_hosted connect() expect a structured source descriptor.",
                {"expected": "dict", "received": type(source).__name__},
            )
        result = runtime._client().register_source(
            connection_descriptors.normalize_api_source_payload(
                source,
                explicit_name=registration_name,
            ),
            description=description,
        )
        registration = _runtime_model_source_registration_module().SourceRegistration.from_api(
            result
        )
        runtime._remember_api_registration(registration)
        return registration

    return _runtime_local_registration_module().register_local_source(
        runtime._local_sources,
        source,
        explicit_name=name,
        started_at=start,
    )


def connect_many_runtime_sources(
    runtime: Any,
    sources: list[LocalSourceInput],
    *,
    names: list[str | None] | None = None,
    description: str | None = None,
) -> list[SourceRegistration]:
    if names is not None and len(names) != len(sources):
        raise RuntimeValidationError(
            "invalid_names_length",
            "connect_many() names must match the number of sources.",
            {"sources": len(sources), "names": len(names)},
        )
    registrations: list[SourceRegistration] = []
    for index, source in enumerate(sources):
        source_name = names[index] if names is not None else None
        registrations.append(runtime.connect(source, name=source_name, description=description))
    return registrations


def build_runtime_import_preview(
    runtime: Any,
    source: LocalSourceInput,
    *,
    name: str | None = None,
    description: str | None = None,
    source_ref: str | None = None,
) -> ImportPreview:
    import_preview = _runtime_import_preview_module()
    source_naming = _runtime_source_naming_module()
    registration = runtime.connect(source, name=name, description=description)
    return import_preview.build_import_preview(
        source=source,
        registration=registration,
        mode=runtime._mode,
        source_ref=source_ref,
        local_source_count=len(runtime._local_sources),
        source_ref_label=source_naming.source_ref_label,
        runtime_source_name=source_naming.runtime_source_name,
    )


def build_runtime_import_bundle_preview(
    runtime: Any,
    sources: list[LocalSourceInput],
    *,
    names: list[str | None] | None = None,
    source_refs: list[str | None] | None = None,
    description: str | None = None,
) -> ImportBundlePreview:
    import_preview = _runtime_import_preview_module()
    source_naming = _runtime_source_naming_module()
    bundle_overlap = _runtime_bundle_overlap_module()
    return import_preview.build_import_bundle_preview(
        sources=sources,
        mode=runtime._mode,
        names=names,
        source_refs=source_refs,
        description=description,
        connect=runtime.connect,
        source_ref_label=source_naming.source_ref_label,
        bundle_overlap_lines=bundle_overlap.bundle_overlap_lines,
    )


__all__ = [
    "build_runtime_import_bundle_preview",
    "build_runtime_import_preview",
    "connect_many_runtime_sources",
    "connect_runtime_source",
]

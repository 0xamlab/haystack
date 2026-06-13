from __future__ import annotations

import hashlib
import os
import shutil
import tarfile
import tempfile
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from apps.api_server.schemas.repositories import RepositoryArtifactRef
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)
from apps.api_server.services.repository_intelligence_runtime import (
    _decision_plans_dir,
    _patch_impact_dir,
    _read_json,
    _simulations_dir,
    _snapshots_dir,
    _triage_dir,
)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_ref(
    *,
    artifact_id: str,
    artifact_kind: str,
    content_hash: str,
    storage_path: Path,
    created_at: datetime,
    schema_revision: str | None = None,
) -> RepositoryArtifactRef:
    return RepositoryArtifactRef(
        artifact_id=artifact_id,
        artifact_kind=artifact_kind,
        content_hash=content_hash,
        storage_path=str(storage_path),
        schema_revision=schema_revision,
        created_at=created_at,
    )


def _validated_archive_target(*, destination: Path, member_name: str, archive_path: Path) -> Path:
    resolved_destination = destination.resolve()
    target_path = (destination / member_name).resolve()
    if target_path != resolved_destination and resolved_destination not in target_path.parents:
        raise RepositoryIntelligenceError(
            code="unsafe_archive_path",
            message=f"Archive '{archive_path}' contains unsafe path '{member_name}'.",
            status_code=422,
        )
    return target_path


def _extract_tar_handle(
    *,
    handle: tarfile.TarFile,
    archive_path: Path,
    destination: Path,
) -> None:
    for member in handle.getmembers():
        target_path = _validated_archive_target(
            destination=destination,
            member_name=member.name,
            archive_path=archive_path,
        )
        if member.issym() or member.islnk():
            raise RepositoryIntelligenceError(
                code="unsafe_archive_member",
                message=f"Archive '{archive_path}' contains unsupported link '{member.name}'.",
                status_code=422,
            )
        if member.isdir():
            target_path.mkdir(parents=True, exist_ok=True)
            continue
        extracted = handle.extractfile(member)
        if extracted is None:
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with extracted, target_path.open("wb") as destination_handle:
            shutil.copyfileobj(extracted, destination_handle)


def _extract_tar(archive_path: Path, destination: Path) -> None:
    with tarfile.open(archive_path, "r:*") as handle:
        _extract_tar_handle(
            handle=handle,
            archive_path=archive_path,
            destination=destination,
        )


def _extract_zip(archive_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive_path) as handle:
        for member in handle.infolist():
            target_path = _validated_archive_target(
                destination=destination,
                member_name=member.filename,
                archive_path=archive_path,
            )
            if member.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with handle.open(member) as source_handle, target_path.open("wb") as destination_handle:
                shutil.copyfileobj(source_handle, destination_handle)


def _extract_archive(archive_path: Path, destination: Path) -> None:
    suffixes = archive_path.suffixes
    if suffixes[-2:] == [".tar", ".gz"] or archive_path.suffix in {".tar", ".tgz", ".gz"}:
        _extract_tar(archive_path, destination)
        return
    if archive_path.suffix == ".zip":
        _extract_zip(archive_path, destination)
        return
    raise RepositoryIntelligenceError(
        code="unsupported_archive_format",
        message=(
            f"Repository archive '{archive_path.name}' must be one of .zip, .tar, .tgz, or .tar.gz."
        ),
        status_code=422,
    )


def _require_safe_artifact_id(value: str, *, field: str) -> str:
    """Reject a client-supplied artifact id that could escape its org/repository directory.

    Cross-tenant guard: the local-FS manifest loaders join these ids straight into a path, so an
    unvalidated ``..``/``/`` would traverse out of the org dir into another tenant's. The s3 branch
    already validates via ``artifact_key``; this mirrors that guard (the same ``_KEY_SEGMENT``) for
    the local branch — no path separators, no ``..``."""
    from apps.api_server.services.repository_intelligence_object_store import _KEY_SEGMENT

    # _KEY_SEGMENT blocks '/' and '\\' (the cross-org escape), but '.' is a valid segment char so it
    # alone admits the dot-special segments '.'/'..'; for the local-FS join those are a parent-dir
    # traversal the S3 key context doesn't have, so reject them explicitly too.
    text = str(value or "")
    if not _KEY_SEGMENT.match(text) or text in (".", ".."):
        raise RepositoryIntelligenceError(
            code="invalid_artifact_id",
            message=f"{field} must match ^[A-Za-z0-9._:-]{{1,128}}$ and not be '.'/'..' (no path traversal).",
            status_code=422,
        )
    return value


def _snapshot_paths(org_id: str, repository_id: str, snapshot_id: str) -> dict[str, Path]:
    _require_safe_artifact_id(snapshot_id, field="snapshot_id")
    snapshot_dir = _snapshots_dir(org_id, repository_id) / snapshot_id
    return {
        "dir": snapshot_dir,
        "manifest": snapshot_dir / "snapshot.json",
        "source_archive": snapshot_dir / "source.tar",
        "snapshot_parquet": snapshot_dir / "repository_snapshot.parquet",
        "repository_graph_parquet": snapshot_dir / "repository_graph.parquet",
        "symbol_graph_parquet": snapshot_dir / "symbol_graph.parquet",
        "dependency_graph_parquet": snapshot_dir / "dependency_graph.parquet",
        "symbol_reference_parquet": snapshot_dir / "symbol_reference.parquet",
    }


def _fetch_source_archive_from_object_store(snapshot_manifest: dict[str, Any]) -> Path:
    """B8 cross-replica fallback: download a snapshot's source archive from the durable object
    store to a node-local scratch file. Used when the archive isn't present on this node — it was
    created on another replica, or the local volume was lost. Raises 410 when the manifest records
    no object-store key (a local-only snapshot whose volume is gone) or the object is missing."""
    key = snapshot_manifest.get("source_archive_object_key")
    if not key:
        raise RepositoryIntelligenceError(
            code="snapshot_source_unavailable",
            message=(
                "Repository snapshot source archive is not present on this node and the manifest "
                "records no object-store key to recover it from."
            ),
            status_code=410,
        )
    from apps.api_server.services.repository_intelligence_object_store import get_object_store

    data = get_object_store().get_bytes(str(key))
    if data is None:
        raise RepositoryIntelligenceError(
            code="snapshot_source_unavailable",
            message=(
                f"Repository snapshot source archive object '{key}' was not found in the object "
                "store."
            ),
            status_code=410,
        )
    handle = tempfile.NamedTemporaryFile(
        prefix="algenta-repository-source-", suffix=".tar", delete=False
    )
    try:
        handle.write(data)
    finally:
        handle.close()
    return Path(handle.name)


@contextmanager
def materialized_snapshot(snapshot_manifest: dict[str, Any]) -> Iterator[Path]:
    temp_dir = Path(tempfile.mkdtemp(prefix="algenta-repository-snapshot-"))
    fetched_archive: Path | None = None
    try:
        archive_path = Path(snapshot_manifest["source_archive_path"])
        if not archive_path.exists():
            # B8: the local archive isn't on this node — recover it from the durable object store
            # using the key recorded at snapshot time (no-op gap in local-only deployments).
            fetched_archive = _fetch_source_archive_from_object_store(snapshot_manifest)
            archive_path = fetched_archive
        _extract_tar(archive_path, temp_dir)
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        if fetched_archive is not None:
            fetched_archive.unlink(missing_ok=True)


def _recover_manifest_from_object_store(
    *,
    org_id: str,
    repository_id: str,
    kind: str,
    artifact_id: str,
    not_found_code: str,
    not_found_message: str,
) -> dict[str, Any]:
    """B8 cross-replica fallback for a DURABLE manifest whose node-local copy is absent.

    Local mode: there is no durable object store to consult (``get_object_store()`` points at a
    different local tree than the legacy manifest dirs), so raise the caller's EXISTING 404 — local
    mode stays byte-for-byte backward compatible. s3 mode: re-derive the tenant-scoped key from
    server-derived identity and read it. Three distinguished outcomes:
      - genuine miss (object definitively absent) -> the SAME existing 404 (the re-derived key
        cannot prove the artifact ever existed, so 410 Gone is the wrong contract; an unknown id
        404s identically in local and s3, preserving cross-mode read parity);
      - object store UNAVAILABLE/DENIED (egress deny, connectivity, creds, bucket failure) -> a
        retryable 503, NEVER a 404/410 and NEVER a silent local fallback that masks data loss
        (this relies on S3Backend.get_bytes propagating availability faults rather than masking
        them as None);
      - recovered -> return it.
    The key is re-derived from identity (not read from the manifest) because the manifest is what
    we are recovering. A malformed artifact_id fails closed via artifact_key's ValueError."""
    from apps.api_server.services.repository_intelligence_object_store import (
        artifact_key,
        get_object_store,
        object_store_mode,
    )

    if object_store_mode() != "s3":
        raise RepositoryIntelligenceError(
            code=not_found_code, message=not_found_message, status_code=404
        )
    key = artifact_key(
        org_id=org_id, repository_id=repository_id, kind=kind, artifact_id=artifact_id
    )
    try:
        recovered = get_object_store().get_json(key)
    except RepositoryIntelligenceError:
        raise
    except Exception as exc:  # noqa: BLE001 — an availability fault is retryable, NOT 404/410
        raise RepositoryIntelligenceError(
            code=f"{kind}_manifest_store_unavailable",
            message=(
                f"the object store was unavailable while recovering '{artifact_id}': {exc}"
            ),
            status_code=503,
        ) from exc
    if recovered is None:
        raise RepositoryIntelligenceError(
            code=not_found_code, message=not_found_message, status_code=404
        )
    return recovered


def _materialize_snapshot_hydration_parquet(
    *,
    org_id: str,
    repository_id: str,
    snapshot_id: str,
    manifest: dict[str, Any],
    paths: dict[str, Path],
) -> None:
    """B8 cross-replica hydration: ensure the 3 Parquet artifacts that
    ``hydrate_snapshot_manifest`` reads (symbol_graph / dependency_graph / symbol_reference) are
    present node-locally, recovering each from the durable object store when absent, then rewrite
    the manifest's ``storage_path`` to the local path so hydrate reads the materialized file on THIS
    replica. Idempotent: an already-present local Parquet is reused (warm-replica fast path).

    Fails closed with a retryable 503: a missing object (``snapshot_hydration_unavailable``), an
    object-store availability fault (``snapshot_hydration_unavailable``), or a content-hash mismatch
    (``snapshot_hydration_corrupt``) — verified BEFORE the file is published so a bad download never
    lands as a poison cache. The download is published via temp-then-atomic-rename so a concurrent
    reader on this replica never sees a torn Parquet (which hydrate's unguarded read would 500 on)."""
    from apps.api_server.services.repository_intelligence_object_store import (
        artifact_key,
        get_object_store,
    )

    store = get_object_store()
    for artifact_field, paths_key in (
        ("symbol_graph_artifact", "symbol_graph_parquet"),
        ("dependency_graph_artifact", "dependency_graph_parquet"),
        ("symbol_reference_artifact", "symbol_reference_parquet"),
    ):
        local = paths[paths_key]
        if not local.exists():
            key = artifact_key(
                org_id=org_id,
                repository_id=repository_id,
                kind=paths_key,
                artifact_id=snapshot_id,
            )
            try:
                data = store.get_bytes(key)
            except RepositoryIntelligenceError:
                raise
            except Exception as exc:  # noqa: BLE001 — availability fault is retryable, not a miss
                raise RepositoryIntelligenceError(
                    code="snapshot_hydration_unavailable",
                    message=(
                        f"the object store was unavailable while recovering snapshot Parquet "
                        f"'{paths_key}' for '{snapshot_id}': {exc}"
                    ),
                    status_code=503,
                ) from exc
            if data is None:
                raise RepositoryIntelligenceError(
                    code="snapshot_hydration_unavailable",
                    message=(
                        f"snapshot Parquet '{paths_key}' for '{snapshot_id}' is not present on this "
                        "node and was not found in the object store."
                    ),
                    status_code=503,
                )
            expected = str((manifest.get(artifact_field) or {}).get("content_hash") or "")
            if hashlib.sha256(data).hexdigest() != expected:
                raise RepositoryIntelligenceError(
                    code="snapshot_hydration_corrupt",
                    message=(
                        f"snapshot Parquet '{paths_key}' for '{snapshot_id}' failed its content-hash "
                        "integrity check."
                    ),
                    status_code=503,
                )
            local.parent.mkdir(parents=True, exist_ok=True)
            tmp = local.with_name(local.name + ".tmp." + os.urandom(8).hex())
            try:
                tmp.write_bytes(data)
                os.replace(tmp, local)
            except OSError as exc:
                tmp.unlink(missing_ok=True)
                raise RepositoryIntelligenceError(
                    code="snapshot_hydration_unavailable",
                    message=(
                        f"failed to materialize snapshot Parquet '{paths_key}' for "
                        f"'{snapshot_id}': {exc}"
                    ),
                    status_code=503,
                ) from exc
        # Rewrite to the local materialized path: the recovered manifest carries the ORIGINAL node's
        # storage_path, which does not exist on this replica. The hydration LRU is keyed on
        # content_hash (not storage_path), so this rewrite is cache-safe.
        artifact = manifest.get(artifact_field)
        if isinstance(artifact, dict):
            artifact["storage_path"] = str(local)


def _load_snapshot_manifest(*, org_id: str, repository_id: str, snapshot_id: str) -> dict[str, Any]:
    from apps.api_server.services import repository_intelligence_manifest_reader as manifest_reader

    paths = _snapshot_paths(org_id, repository_id, snapshot_id)
    path = paths["manifest"]
    # AR-OPT-2: hydrate slim (v2) manifests from Parquet so downstream graph/decision consumers
    # always see the inline arrays; no-op for legacy v1 (inline) manifests.
    if path.exists():
        return manifest_reader.hydrate_snapshot_manifest(_read_json(path))
    # B8: local manifest absent on this node — recover from the durable object store (s3 mode) or
    # raise the existing 404 (local mode / genuine miss).
    manifest = _recover_manifest_from_object_store(
        org_id=org_id,
        repository_id=repository_id,
        kind="snapshots",
        artifact_id=snapshot_id,
        not_found_code="snapshot_not_found",
        not_found_message=f"Repository snapshot '{snapshot_id}' was not found.",
    )
    # A v2 (slim) manifest with files hydrates from 3 node-local Parquet (read unguarded by the
    # hydrator), which a fresh replica does not have — materialize them from the object store first,
    # or fail closed 503. v1 / empty-files manifests hydrate as a no-op and need no Parquet, so they
    # short-circuit (matching the hydrator's own early returns) without any object-store read.
    if manifest_reader.manifest_version(manifest) >= 2 and manifest.get("files"):
        _materialize_snapshot_hydration_parquet(
            org_id=org_id,
            repository_id=repository_id,
            snapshot_id=snapshot_id,
            manifest=manifest,
            paths=paths,
        )
    return manifest_reader.hydrate_snapshot_manifest(manifest)


def _load_triage_manifest(
    *, org_id: str, repository_id: str, evidence_bundle_ref: str
) -> dict[str, Any]:
    _require_safe_artifact_id(evidence_bundle_ref, field="workspace_evidence_bundle_ref")
    path = _triage_dir(org_id, repository_id) / f"{evidence_bundle_ref}.json"
    if path.exists():
        return _read_json(path)
    # B8: local copy absent on this node — recover from the durable object store (s3 mode) or raise
    # the existing 404 (local mode / genuine miss). The triage body is hydration-free, so the
    # recovered object is the complete manifest.
    return _recover_manifest_from_object_store(
        org_id=org_id,
        repository_id=repository_id,
        kind="triage",
        artifact_id=evidence_bundle_ref,
        not_found_code="workspace_evidence_bundle_not_found",
        not_found_message=f"Workspace evidence bundle '{evidence_bundle_ref}' was not found.",
    )


def _load_decision_plan_manifest(
    *, org_id: str, repository_id: str, decision_plan_id: str
) -> dict[str, Any]:
    _require_safe_artifact_id(decision_plan_id, field="decision_plan_id")
    path = _decision_plans_dir(org_id, repository_id) / f"{decision_plan_id}.json"
    if path.exists():
        return _read_json(path)
    # B8: local copy absent on this node — recover from the durable object store (s3 mode) or raise
    # the existing 404 (local mode / genuine miss). Hydration-free body recovers as-is.
    return _recover_manifest_from_object_store(
        org_id=org_id,
        repository_id=repository_id,
        kind="decision_plans",
        artifact_id=decision_plan_id,
        not_found_code="decision_plan_not_found",
        not_found_message=f"Repository decision plan '{decision_plan_id}' was not found.",
    )


def _load_patch_impact_manifest(
    *, org_id: str, repository_id: str, patch_impact_report_id: str
) -> dict[str, Any]:
    _require_safe_artifact_id(patch_impact_report_id, field="patch_impact_report_id")
    path = _patch_impact_dir(org_id, repository_id) / f"{patch_impact_report_id}.json"
    if path.exists():
        return _read_json(path)
    # B8: local copy absent on this node — recover from the durable object store (s3 mode) or raise
    # the existing 404 (local mode / genuine miss). Hydration-free body recovers as-is.
    return _recover_manifest_from_object_store(
        org_id=org_id,
        repository_id=repository_id,
        kind="patch_impacts",
        artifact_id=patch_impact_report_id,
        not_found_code="patch_impact_report_not_found",
        not_found_message=f"Patch impact report '{patch_impact_report_id}' was not found.",
    )


def _load_simulation_manifest(
    *, org_id: str, repository_id: str, simulation_id: str
) -> dict[str, Any]:
    _require_safe_artifact_id(simulation_id, field="simulation_id")
    path = _simulations_dir(org_id, repository_id) / f"{simulation_id}.json"
    if path.exists():
        return _read_json(path)
    # B8: local copy absent on this node — recover from the durable object store (s3 mode) or raise
    # the existing 404 (local mode / genuine miss). Hydration-free body recovers as-is.
    return _recover_manifest_from_object_store(
        org_id=org_id,
        repository_id=repository_id,
        kind="simulations",
        artifact_id=simulation_id,
        not_found_code="repository_simulation_not_found",
        not_found_message=f"Repository simulation '{simulation_id}' was not found.",
    )

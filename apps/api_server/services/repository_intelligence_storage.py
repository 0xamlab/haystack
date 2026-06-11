from __future__ import annotations

import hashlib
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


def _snapshot_paths(org_id: str, repository_id: str, snapshot_id: str) -> dict[str, Path]:
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


def _load_snapshot_manifest(*, org_id: str, repository_id: str, snapshot_id: str) -> dict[str, Any]:
    path = _snapshot_paths(org_id, repository_id, snapshot_id)["manifest"]
    if not path.exists():
        raise RepositoryIntelligenceError(
            code="snapshot_not_found",
            message=f"Repository snapshot '{snapshot_id}' was not found.",
            status_code=404,
        )
    # AR-OPT-2: hydrate slim (v2) manifests from Parquet so downstream graph/decision
    # consumers always see the inline arrays; no-op for legacy v1 (inline) manifests.
    from apps.api_server.services import repository_intelligence_manifest_reader

    return repository_intelligence_manifest_reader.hydrate_snapshot_manifest(_read_json(path))


def _load_triage_manifest(
    *, org_id: str, repository_id: str, evidence_bundle_ref: str
) -> dict[str, Any]:
    path = _triage_dir(org_id, repository_id) / f"{evidence_bundle_ref}.json"
    if not path.exists():
        raise RepositoryIntelligenceError(
            code="workspace_evidence_bundle_not_found",
            message=f"Workspace evidence bundle '{evidence_bundle_ref}' was not found.",
            status_code=404,
        )
    return _read_json(path)


def _load_decision_plan_manifest(
    *, org_id: str, repository_id: str, decision_plan_id: str
) -> dict[str, Any]:
    path = _decision_plans_dir(org_id, repository_id) / f"{decision_plan_id}.json"
    if not path.exists():
        raise RepositoryIntelligenceError(
            code="decision_plan_not_found",
            message=f"Repository decision plan '{decision_plan_id}' was not found.",
            status_code=404,
        )
    return _read_json(path)


def _load_patch_impact_manifest(
    *, org_id: str, repository_id: str, patch_impact_report_id: str
) -> dict[str, Any]:
    path = _patch_impact_dir(org_id, repository_id) / f"{patch_impact_report_id}.json"
    if not path.exists():
        raise RepositoryIntelligenceError(
            code="patch_impact_report_not_found",
            message=f"Patch impact report '{patch_impact_report_id}' was not found.",
            status_code=404,
        )
    return _read_json(path)


def _load_simulation_manifest(
    *, org_id: str, repository_id: str, simulation_id: str
) -> dict[str, Any]:
    path = _simulations_dir(org_id, repository_id) / f"{simulation_id}.json"
    if not path.exists():
        raise RepositoryIntelligenceError(
            code="repository_simulation_not_found",
            message=f"Repository simulation '{simulation_id}' was not found.",
            status_code=404,
        )
    return _read_json(path)

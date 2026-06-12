"""Backfill node-local repository-intelligence artifacts into the durable object store.

Snapshots / triage bundles / simulations created BEFORE B8 (or before ``ALGENTA_RI_OBJECT_STORE=s3``
was enabled) live only on the node that created them. The cross-replica durability guard
(repository_intelligence_lookup_store + the workflow mirrors) therefore refuses to advertise them to
sibling replicas — correct, but it means a cold sibling re-clones / re-triages / re-simulates them.

This one-shot job mirrors those local artifacts to the object store so they become recoverable from
any replica, and re-publishes their dedup lookups so cross-replica dedup is restored without waiting
for a re-creation:

  * snapshots  → manifest (kind=snapshots) + the 5 Parquet + source archive (kind=archives)
  * triage     → manifest (kind=triage)
  * simulations→ manifest (kind=simulations)
  * lookups    → snapshot_lookup / triage_lookup / simulation_lookup (simulation only when the
                 lookup pins an explicit seed AND runs — matching the deterministic-sharing gate)

Requires ``ALGENTA_RI_OBJECT_STORE=s3`` (the mirror helpers no-op in local mode). Idempotent — the
mirrors are PUTs, so re-running overwrites with identical bytes. The Parquet bytes on disk are the
exact bytes hashed into the manifest ``content_hash`` at creation, so the recovery-side sha256 check
matches by construction.

Usage:
  ./scripts/run_repo_python.sh scripts/backfill_repository_artifacts_to_object_store.py [ORG_ID] [--dry-run]

ORG_ID  restrict to one tenant (default: all tenants under the runtime dir).
--dry-run  enumerate + report what WOULD be mirrored without writing anything.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

_PARQUET_KINDS = (
    "snapshot_parquet",
    "symbol_graph_parquet",
    "dependency_graph_parquet",
    "repository_graph_parquet",
    "symbol_reference_parquet",
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _backfill_snapshot(*, org: str, repo: str, snapshot_id: str, dry_run: bool, stats: Counter) -> None:
    from apps.api_server.services import repository_intelligence_storage as storage
    from apps.api_server.services.repository_intelligence_snapshot_workflow import (
        _mirror_snapshot_manifest_to_object_store,
        _mirror_snapshot_parquet_to_object_store,
        _mirror_source_archive_to_object_store,
    )

    paths = storage._snapshot_paths(org, repo, snapshot_id)
    if not paths["manifest"].exists():
        return
    stats["snapshots_scanned"] += 1
    manifest = _read_json(paths["manifest"])
    parquet_by_kind = {
        kind: paths[kind].read_bytes() for kind in _PARQUET_KINDS if paths[kind].exists()
    }
    if dry_run:
        stats["snapshots_would_mirror"] += 1
        print(
            f"  [dry-run] snapshot {snapshot_id}: manifest + {len(parquet_by_kind)} parquet"
            f"{' + archive' if paths['source_archive'].exists() else ''}"
        )
        return
    try:
        if parquet_by_kind:
            _mirror_snapshot_parquet_to_object_store(
                org_id=org, repository_id=repo, snapshot_id=snapshot_id, parquet_by_kind=parquet_by_kind
            )
        _mirror_snapshot_manifest_to_object_store(
            org_id=org, repository_id=repo, snapshot_id=snapshot_id, manifest=manifest
        )
        if paths["source_archive"].exists():
            _mirror_source_archive_to_object_store(
                org_id=org, repository_id=repo, snapshot_id=snapshot_id,
                archive_path=paths["source_archive"],
            )
        stats["snapshots_mirrored"] += 1
    except Exception as exc:  # noqa: BLE001 — report + continue the backfill
        stats["snapshots_failed"] += 1
        print(f"  ERROR snapshot {snapshot_id}: {exc}", file=sys.stderr)
    # restore dedup: re-publish the snapshot's lookups (now that the artifacts are durable)
    _backfill_lookups(org=org, repo=repo, kind="snapshot_lookup", dry_run=dry_run, stats=stats)


def _backfill_triage(*, org: str, repo: str, repo_dir: Path, dry_run: bool, stats: Counter) -> None:
    from apps.api_server.services.repository_intelligence_graph_workflow import (
        _mirror_triage_manifest_to_object_store,
    )

    triage_dir = repo_dir / "triage"
    if not triage_dir.exists():
        return
    for manifest_path in sorted(triage_dir.glob("*.json")):
        ref = manifest_path.stem
        stats["triage_scanned"] += 1
        manifest = _read_json(manifest_path)
        if dry_run:
            stats["triage_would_mirror"] += 1
            print(f"  [dry-run] triage {ref}: manifest")
            continue
        try:
            _mirror_triage_manifest_to_object_store(
                org_id=org, repository_id=repo, evidence_bundle_ref=ref, manifest=manifest
            )
            stats["triage_mirrored"] += 1
        except Exception as exc:  # noqa: BLE001
            stats["triage_failed"] += 1
            print(f"  ERROR triage {ref}: {exc}", file=sys.stderr)
    _backfill_lookups(org=org, repo=repo, kind="triage_lookup", dry_run=dry_run, stats=stats)


def _backfill_simulations(*, org: str, repo: str, repo_dir: Path, dry_run: bool, stats: Counter) -> None:
    from apps.api_server.services.repository_intelligence_execution_workflow import (
        _mirror_simulation_manifest_to_object_store,
    )

    sims_dir = repo_dir / "simulations"
    if not sims_dir.exists():
        return
    for manifest_path in sorted(sims_dir.glob("*.json")):
        sim_id = manifest_path.stem
        stats["simulations_scanned"] += 1
        manifest = _read_json(manifest_path)
        if dry_run:
            stats["simulations_would_mirror"] += 1
            print(f"  [dry-run] simulation {sim_id}: manifest")
            continue
        try:
            _mirror_simulation_manifest_to_object_store(
                org_id=org, repository_id=repo, simulation_id=sim_id, manifest=manifest
            )
            stats["simulations_mirrored"] += 1
        except Exception as exc:  # noqa: BLE001
            stats["simulations_failed"] += 1
            print(f"  ERROR simulation {sim_id}: {exc}", file=sys.stderr)
    _backfill_lookups(org=org, repo=repo, kind="simulation_lookup", dry_run=dry_run, stats=stats)


def _backfill_lookups(*, org: str, repo: str, kind: str, dry_run: bool, stats: Counter) -> None:
    """Re-publish the local dedup lookups of one family to the shared index. simulation_lookup is
    only published when it pins an explicit seed AND runs (the deterministic-sharing gate)."""
    from apps.api_server.services import repository_intelligence_lookup_store as lookup_store
    from apps.api_server.services import repository_intelligence_runtime as runtime

    lookup_dir = {
        "snapshot_lookup": runtime._snapshot_lookup_dir,
        "triage_lookup": runtime._triage_lookup_dir,
        "simulation_lookup": runtime._simulation_lookup_dir,
    }[kind](org, repo)
    if not lookup_dir.exists():
        return
    for lookup_path in sorted(lookup_dir.glob("*.json")):
        payload = _read_json(lookup_path)
        if kind == "simulation_lookup" and (
            payload.get("seed") is None or payload.get("runs") is None
        ):
            stats["lookups_skipped_nondeterministic"] += 1
            continue
        stats[f"{kind}_scanned"] += 1
        if dry_run:
            stats[f"{kind}_would_mirror"] += 1
            continue
        try:
            lookup_store.mirror_lookup(
                org_id=org, repository_id=repo, kind=kind,
                lookup_key=lookup_path.stem, payload=payload,
            )
            stats[f"{kind}_mirrored"] += 1
        except Exception as exc:  # noqa: BLE001
            stats[f"{kind}_failed"] += 1
            print(f"  ERROR {kind} {lookup_path.stem}: {exc}", file=sys.stderr)


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    positionals = [a for a in argv if not a.startswith("-")]
    org_filter = positionals[0] if positionals else None

    from apps.api_server.services.repository_intelligence_object_store import object_store_mode
    from apps.api_server.services.repository_intelligence_runtime import _runtime_dir

    if object_store_mode() != "s3":
        print(
            "ALGENTA_RI_OBJECT_STORE is not 's3' — nothing to mirror (the object store is the local "
            "filesystem). Set ALGENTA_RI_OBJECT_STORE=s3 (+ the S3/MinIO settings) and re-run.",
            file=sys.stderr,
        )
        return 2

    ri_root = _runtime_dir() / "repository_intelligence"
    if not ri_root.exists():
        print(f"no repository-intelligence runtime dir at {ri_root}; nothing to do")
        return 0

    stats: Counter = Counter()
    mode = "DRY-RUN" if dry_run else "MIRROR"
    for org_dir in sorted(p for p in ri_root.iterdir() if p.is_dir()):
        if org_filter and org_dir.name != org_filter:
            continue
        for repo_dir in sorted(p for p in org_dir.iterdir() if p.is_dir()):
            org, repo = org_dir.name, repo_dir.name
            print(f"[{mode}] tenant={org} repo={repo}")
            snaps_dir = repo_dir / "snapshots"
            if snaps_dir.exists():
                for snap_dir in sorted(p for p in snaps_dir.iterdir() if p.is_dir()):
                    _backfill_snapshot(
                        org=org, repo=repo, snapshot_id=snap_dir.name, dry_run=dry_run, stats=stats
                    )
            _backfill_triage(org=org, repo=repo, repo_dir=repo_dir, dry_run=dry_run, stats=stats)
            _backfill_simulations(org=org, repo=repo, repo_dir=repo_dir, dry_run=dry_run, stats=stats)

    print(f"\n=== backfill {mode} summary ===")
    for key in sorted(stats):
        print(f"  {key}: {stats[key]}")
    failures = sum(v for k, v in stats.items() if k.endswith("_failed"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

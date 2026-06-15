#!/usr/bin/env python3
"""Codna competitor runner for the bake-off — the REAL Cline-SDK + Mojo path.

snapshot -> triage (Mojo-ranked; locates the bug from the failing-test signal)
-> verified_agentic plan (the Cline agent fixes the located symbol with the
injected evidence bundle, gated by the Mojo calibrated-risk hook) -> emit the
patch + token telemetry.

This is the path that makes Codna cheap: triage pinpoints the suspect file in
milliseconds for ~0 tokens, so the Cline agent edits one symbol instead of
exploring the whole repo. Emits JSON {timings, tokens, suspect_files, patch_diff}.

Requires: the agent-core (Cline) sidecar running, ALGENTA_AGENT_CORE_URL set,
ANTHROPIC_API_KEY (the agent's provider), ALGENTA_RUNTIME_DIR.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _connector(repo: Path) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        owner_key_id=None,
        connector_type=SimpleNamespace(value="local_repo"),
        config_json=json.dumps({"path": str(repo)}),
    )


async def _run(args: argparse.Namespace) -> dict:
    from apps.api_server.schemas.repositories import (
        RepositoryDiagnostic,
        RepositorySignals,
        RepositorySnapshotCreateRequest,
        RepositoryTriageRequest,
    )
    import os
    from functools import partial

    from apps.api_server.services import repository_intelligence_core as ri
    from apps.api_server.services import repository_intelligence_storage as storage
    from apps.api_server.services.repository_intelligence_agent_core_client import (
        run_agent_via_sidecar,
    )
    from apps.api_server.services.repository_intelligence_manifest_reader import (
        hydrate_snapshot_manifest,
    )
    from apps.api_server.services.repository_intelligence_verified_agentic import (
        _generate_verified_agentic_repository_patch_plan,
    )

    repo = Path(args.repo).resolve()
    conn = _connector(repo)
    org_id, repo_id = str(conn.org_id), str(conn.id)

    t0 = time.perf_counter()
    snap = ri.create_repository_snapshot(
        connector=conn,
        request=RepositorySnapshotCreateRequest(focus_paths=[args.focus]),
    )
    t_snap = time.perf_counter()

    signal = RepositorySignals(
        issue_text=args.issue,
        diagnostics=[
            RepositoryDiagnostic(path=args.diag_path, line=args.diag_line, message=args.issue)
        ],
    )
    triage = ri.triage_repository(
        connector=conn,
        request=RepositoryTriageRequest(snapshot_id=snap.snapshot_id, signals=signal),
    )
    t_triage = time.perf_counter()

    snap_manifest = hydrate_snapshot_manifest(
        storage._load_snapshot_manifest(
            org_id=org_id, repository_id=repo_id, snapshot_id=snap.snapshot_id
        )
    )
    triage_manifest = storage._load_triage_manifest(
        org_id=org_id,
        repository_id=repo_id,
        evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
    )

    # The Cline agent fix via the sidecar, with a generous timeout (the default
    # client timeout is 120s — too short for larger fixes). Returns patch_diff +
    # planner_usage telemetry.
    base = os.environ.get("ALGENTA_AGENT_CORE_URL")
    run_agent = (
        partial(run_agent_via_sidecar, base_url=base, timeout_s=float(args.agent_timeout))
        if base
        else None
    )
    plan = await _generate_verified_agentic_repository_patch_plan(
        model_id="repository.verified_agentic_v1",
        snapshot_manifest=snap_manifest,
        triage_manifest=triage_manifest,
        run_agent=run_agent,
    )
    t_plan = time.perf_counter()

    usage = plan.get("planner_usage", {}) or {}
    return {
        "snapshot_s": round(t_snap - t0, 3),
        "triage_s": round(t_triage - t_snap, 3),
        "agent_s": round(t_plan - t_triage, 3),
        "wall_s": round(t_plan - t0, 3),
        "suspect_files": list(triage_manifest.get("suspect_files", []))[:5],
        "tokens_in": usage.get("input_tokens"),
        "tokens_out": usage.get("output_tokens"),
        "cache_tokens": usage.get("cache_read_tokens"),
        "cost_usd": usage.get("cost_usd"),
        "patch_diff": plan.get("patch_diff", ""),
        "status": plan.get("status"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--repo", required=True, help="Path to the (buggy) repo checkout.")
    ap.add_argument("--focus", default="src", help="Top focus path for the snapshot.")
    ap.add_argument("--diag-path", required=True, help="File the failing test's traceback points at.")
    ap.add_argument("--diag-line", type=int, default=1)
    ap.add_argument("--issue", required=True, help="Failing-test summary (the triage signal).")
    ap.add_argument("--agent-timeout", type=int, default=300, help="Cline sidecar /run timeout (s).")
    ap.add_argument("--out", default="-", help="Write JSON result here ('-' = stdout).")
    args = ap.parse_args()

    try:
        result = asyncio.run(_run(args))
    except Exception as exc:  # noqa: BLE001 — emit a structured failure for the harness
        result = {"error": f"{type(exc).__name__}: {exc}"}

    payload = json.dumps(result, indent=2)
    if args.out == "-":
        print(payload)
    else:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
        print(f"wrote {args.out}")
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())

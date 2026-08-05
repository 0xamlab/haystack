"""The SDK usability audit, ratcheted into the repo's pytest graph.

Two layers, both fail-closed:

1. STATIC — every gate-level gap check (contract drift, silent visibility loss, surface
   leaks, test coverage, release-gate style) must pass. Checks that fail for known
   in-flight reasons are waived in ``scripts/sdk_audit_baseline.json``; the waiver list
   only ever SHRINKS (a waiver naming a check that now passes fails this suite, so fixes
   must delete their waiver — the same shape as ``scripts/capability_manifest_baseline.json``).

2. EXECUTED — when a compiled runtime worker exists, a canary sweep runs a handful of
   small modules through the real SDK path and asserts zero crashes and zero unexpected
   refusals. The full 5,700-function sweep lives in the sdk-audit workflow (a pytest
   graph is the wrong home for a half-hour battery); this canary is the tripwire that a
   worker-level regression exists at all.

JIT evidence does not count (docs/mojo/new-kernel-package-rules.md rule 1b): the canary
skips rather than fakes when no compiled worker is present, exactly like
``tests/integration/test_kernel_count_arg_robustness.py``.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_ALGENTA_PKG = _REPO_ROOT / "packages" / "algenta"
if str(_ALGENTA_PKG) not in sys.path:
    sys.path.insert(0, str(_ALGENTA_PKG))

import scripts.audit_gap_checks as gap_checks  # noqa: E402

_BASELINE_PATH = _REPO_ROOT / "scripts" / "sdk_audit_baseline.json"

_WORKER_CANDIDATES = (
    _REPO_ROOT / "mojo_build" / "audit-worker",
    _REPO_ROOT / "mojo_build" / "runtime-shards",
)


def _load_baseline() -> dict:
    payload = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    waived = payload.get("waived_gate_failures", [])
    if not isinstance(waived, list) or any(not isinstance(item, str) for item in waived):
        raise AssertionError("sdk_audit_baseline.json waived_gate_failures must be a string list")
    return {"waived_gate_failures": list(dict.fromkeys(waived))}


def test_baseline_shape() -> None:
    baseline = _load_baseline()
    assert isinstance(baseline["waived_gate_failures"], list)


def test_no_new_gate_failures() -> None:
    """Any gate failure not waived in the baseline is a regression this ratchet blocks."""
    report = gap_checks.run_all_checks()
    baseline = _load_baseline()
    waived = set(baseline["waived_gate_failures"])
    new_failures = sorted(
        check.check_id
        for check in report.checks
        if check.severity == "gate" and check.status == "fail" and check.check_id not in waived
    )
    assert not new_failures, (
        "new SDK audit gate failures (fix them, do NOT widen the baseline): "
        + ", ".join(new_failures)
    )


def test_no_stale_waivers() -> None:
    """A waiver whose check now passes must be deleted — the list only shrinks."""
    report = gap_checks.run_all_checks()
    failing = {
        check.check_id
        for check in report.checks
        if check.severity == "gate" and check.status == "fail"
    }
    baseline = _load_baseline()
    stale = sorted(set(baseline["waived_gate_failures"]) - failing)
    assert not stale, (
        "SDK audit waivers no longer needed (delete them from scripts/sdk_audit_baseline.json): "
        + ", ".join(stale)
    )


def _find_shards_dir() -> Path | None:
    env_override = os.environ.get("ALGENTA_AUDIT_WORKER")
    if env_override:
        return Path(env_override).parent
    for candidate in _WORKER_CANDIDATES:
        if (candidate / "runtime-shards.json").is_file():
            return candidate
    return None


@pytest.mark.skipif(
    _find_shards_dir() is None,
    reason="no compiled runtime shards; build with `make build-audit-worker`",
)
def test_canary_sweep_executes_cleanly() -> None:
    """A tiny real-execution sweep: zero crashes, zero unbuildable signatures, zero
    unexpected refusals across two small stable modules. The full battery runs in CI."""
    from algenta.mojo_runtime import MojoRuntime

    import scripts.audit_library_execution_sweep as sweep

    shards_dir = _find_shards_dir()
    shard_entries = sweep._resolve_shards(None)
    assert shard_entries, f"no usable worker under {shards_dir}"

    os.environ.setdefault("ALGENTA_RUNTIME_FALLBACK_MODE", "allow")
    records, _ = sweep._load_live_surface()
    canary_modules = {"boolean_algebra", "checksum"}
    canary_records = tuple(record for record in records if record.module in canary_modules)
    assert canary_records, "canary modules missing from the live inventory"

    runtime = MojoRuntime(mode="local", timeout=30.0)
    state = sweep.SweepState()
    # Sweep each canary module through the shard that owns it (single-binary layouts route
    # everything, sharded layouts pick the owning worker per module).
    for worker_path, shard_modules in shard_entries:
        owned = [
            record
            for record in canary_records
            if shard_modules is None or record.module in set(shard_modules)
        ]
        if not owned:
            continue
        os.environ["ALGENTA_NATIVE_WORKER"] = str(worker_path)
        from algenta.native import worker as native_worker

        native_worker.shutdown()
        assert runtime.health().get("status") == "ok", f"worker unhealthy: {worker_path}"
        sweep.run_sweep(
            tuple(owned),
            runtime=runtime,
            battery="all",
            state=state,
            determinism_sample=0,
            seed=20260804,
        )
    from algenta.native import worker as native_worker

    native_worker.shutdown()

    summary = sweep.summarize(state)
    blocked = {
        f"{item['module']}.{item['function']}: {item['classification']}"
        for item in summary["findings"]
    }
    assert not blocked, f"canary sweep findings: {sorted(blocked)}"
    assert summary["total_functions"] == len(canary_records), (
        f"canary sweep covered {summary['total_functions']} of {len(canary_records)} functions"
    )

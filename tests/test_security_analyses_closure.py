"""Closure re-proof tests — pure, with injected loaders. Closure is a SEPARATE judgment from
reachability: a sanitizer/barrier closes the obligation even if the op stays reachable."""
from __future__ import annotations

from types import SimpleNamespace

from apps.api_server.schemas.repositories import SecurityAnalysisClosureRequest
from apps.api_server.services.repository_intelligence_security_analysis_workflow import (
    analyze_repository_security_closure,
)

CONNECTOR = SimpleNamespace(org_id="org", id="repo")

ORIGINAL_PROOF = {
    "sinks": [{"uri": "db.py"}],
    "propagation_paths": [[{"from_file": "app.py", "to_file": "db.py", "edge_type": "reaches"}]],
}

DIFF_SANITIZED = (
    "diff --git a/db.py b/db.py\n--- a/db.py\n+++ b/db.py\n"
    "@@ -10 +10 @@\n-    cursor.execute('...' + u)\n+    cursor.execute('...', (u,))  # parameterized\n"
)
DIFF_TOUCH_NO_BARRIER = (
    "diff --git a/db.py b/db.py\n--- a/db.py\n+++ b/db.py\n@@ -10 +10 @@\n-    run(q)\n+    run(q2)\n"
)
DIFF_ELSEWHERE = (
    "diff --git a/other.py b/other.py\n--- a/other.py\n+++ b/other.py\n@@ -1 +1 @@\n-x\n+y\n"
)


def _close(*, patch_digest="sha256:p", diff=DIFF_SANITIZED, proof=ORIGINAL_PROOF):
    return analyze_repository_security_closure(
        connector=CONNECTOR,
        request=SecurityAnalysisClosureRequest(
            snapshot_id="snap", canonical_finding_id="sha256:f", patch_digest=patch_digest
        ),
        engine_revision="test",
        require_repository_connector=lambda c: None,
        load_security_proof_by_finding=lambda **_kw: proof,
        load_patch_diff_by_digest=lambda **_kw: diff,
    )


def test_sanitizer_on_path_closes_even_if_still_reachable():
    resp = _close(diff=DIFF_SANITIZED)
    assert resp.closure_status == "closed"
    assert resp.alternate_path_found is False


def test_path_touched_without_barrier_stays_open():
    assert _close(diff=DIFF_TOUCH_NO_BARRIER).closure_status == "open"


def test_patch_not_touching_path_is_open():
    assert _close(diff=DIFF_ELSEWHERE).closure_status == "open"


def test_missing_patch_digest_is_unknown():
    assert _close(patch_digest=None).closure_status == "unknown"


def test_unmatched_patch_diff_is_unknown():
    assert _close(diff=None).closure_status == "unknown"


def test_missing_original_obligation_is_unknown():
    assert _close(proof=None).closure_status == "unknown"

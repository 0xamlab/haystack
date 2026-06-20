"""Reachability classifier honesty tests — pure over in-memory snapshot manifests.

These assert the four-outcome contract codna's EngineAdapter relies on, especially the
load-bearing invariants: exploitable requires an independent path AND a complete envelope;
"no path" under an incomplete envelope is `unknown`, never `unreachable`.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.api_server.schemas.repositories import (
    PropagationEdge,
    SecurityFinding,
    SecurityFindingLocation,
)
from apps.api_server.services.repository_intelligence_security_analysis_workflow import (
    analyze_findings,
)

# route_index: language -> object with .route_kind. "rust" is on-matrix but NOT in the curated
# sound-taint set, so it can never reach a complete envelope.
ROUTE = {
    lang: SimpleNamespace(route_kind="workflow_special_case")
    for lang in ("python", "javascript", "typescript", "java", "go", "ruby", "php", "rust")
}


def _sym(sid, name, *, kind="function", start=1, end=50, sig=""):
    return {"symbol_id": sid, "symbol_name": name, "symbol_kind": kind,
            "start_line": start, "end_line": end, "parent_symbol_id": None, "signature": sig}


def _file(path, *, lang="python", symbols=None, deps=None, refs=None):
    return {"file_path": path, "language": lang, "symbols": symbols or [],
            "dependencies": deps or [], "symbol_references": refs or []}


def _manifest(*files):
    return {"files": list(files), "resolved_revision": "c0ffee", "content_hash": "sha256:tree"}


def _finding(uri, *, line=10, kind="taint", flows=None, cid=None):
    return SecurityFinding(
        canonical_id=cid or ("sha256:" + uri), rule_id="x/sqli", finding_kind=kind,
        severity="critical", primary_location=SecurityFindingLocation(uri=uri, start_line=line),
        code_flows=flows or [],
    )


def _classify(finding, manifest, taint=None):
    return analyze_findings([finding], manifest, route_index=ROUTE, taint_path_finder=taint)[0]


def _taint_path(**_kw):
    return [PropagationEdge(from_file="app.py", to_file="db.py", edge_type="taint")]


# app.py (entrypoint, by path) -> db.py (the sink). All edges internal -> complete envelope.
def _reachable_manifest(op_lang="python", extra_op_deps=None):
    return _manifest(
        _file("app.py", lang=op_lang, deps=[{"target_file": "db.py", "dependency_type": "imports"}]),
        _file("db.py", lang=op_lang, symbols=[_sym("s1", "run_query")],
              deps=list(extra_op_deps or [])),
    )


def test_production_reachable_by_default_no_taint_backend():
    proof = _classify(_finding("db.py"), _reachable_manifest())
    assert proof.classification == "production-reachable"
    assert proof.proof_type == "entrypoint_reachability"
    assert proof.analysis_envelope.is_complete_sound is True
    assert any(e.uri == "app.py" for e in proof.entrypoints)


def test_exploitable_only_with_independent_path_and_complete_envelope():
    proof = _classify(_finding("db.py"), _reachable_manifest(), taint=_taint_path)
    assert proof.classification == "exploitable"
    assert proof.proof_type == "dataflow"


def test_validated_path_under_incomplete_envelope_downgrades_never_exploitable():
    # op file has an edge leaving the snapshot -> envelope incomplete
    manifest = _reachable_manifest(extra_op_deps=[{"target_file": "vendor/ext.py", "dependency_type": "imports"}])
    proof = _classify(_finding("db.py"), manifest, taint=_taint_path)
    assert proof.classification != "exploitable"
    assert proof.classification == "production-reachable"  # still reachable
    assert proof.analysis_envelope.is_complete_sound is False
    assert "unresolved_edges_on_path" in proof.analysis_envelope.incomplete_reasons


def test_no_path_complete_envelope_is_unreachable():
    # a lib file no entrypoint reaches, fully internal -> proven unreachable
    manifest = _manifest(_file("lib/util.py", symbols=[_sym("s1", "helper")]))
    proof = _classify(_finding("lib/util.py"), manifest)
    assert proof.classification == "unreachable"
    assert proof.proof_type == "absence_proof"
    assert proof.analysis_envelope.is_complete_sound is True


def test_no_path_incomplete_envelope_is_unknown_never_unreachable():
    # same, but an unresolved external edge makes the envelope incomplete
    manifest = _manifest(
        _file("lib/util.py", symbols=[_sym("s1", "helper")],
              deps=[{"target_file": "vendor/ext.py", "dependency_type": "imports"}])
    )
    proof = _classify(_finding("lib/util.py"), manifest)
    assert proof.classification == "unknown"  # the central honesty invariant
    assert proof.classification != "unreachable"


def test_off_matrix_language_is_unknown():
    manifest = _manifest(_file("legacy/main.cbl", lang="cobol"))
    proof = _classify(_finding("legacy/main.cbl"), manifest)
    assert proof.classification == "unknown"
    assert proof.proof_type == "off_matrix"
    assert proof.analysis_envelope.is_complete_sound is False


def test_on_matrix_but_not_sound_language_cannot_be_unreachable():
    # rust is on the matrix but not in the curated sound-taint set -> envelope never complete.
    # Use a non-entrypoint path so the finding isn't simply production-reachable.
    manifest = _manifest(_file("src/helper.rs", lang="rust", symbols=[_sym("s1", "helper")]))
    proof = _classify(_finding("src/helper.rs", line=3), manifest)
    assert proof.classification == "unknown"  # not 'unreachable', because envelope is bounded
    assert proof.analysis_envelope.sound_language is False


def test_scanner_flow_alone_does_not_make_exploitable():
    flows = [[SecurityFindingLocation(uri="app.py", start_line=1),
              SecurityFindingLocation(uri="db.py", start_line=10)]]
    proof = _classify(_finding("db.py", flows=flows), _reachable_manifest())  # no taint backend
    assert proof.classification == "production-reachable"  # never exploitable from a scanner flow
    assert proof.scanner_flow_validation.provided is True
    assert proof.scanner_flow_validation.corroborates_engine_path is True  # files overlap the engine path


def test_finding_file_not_in_snapshot_is_unknown():
    proof = _classify(_finding("ghost.py"), _reachable_manifest())
    assert proof.classification == "unknown"
    assert proof.proof_type == "no_evidence"


@pytest.mark.parametrize("kind", ["secret", "sca", "config"])
def test_non_taint_kinds_never_unreachable_or_exploitable(kind):
    # a non-taint finding in an unreachable but complete-envelope file -> unknown, not unreachable
    manifest = _manifest(_file("lib/util.py", symbols=[_sym("s1", "helper")]))
    proof = _classify(_finding("lib/util.py", kind=kind), manifest, taint=_taint_path)
    assert proof.classification == "unknown"
    # and when reachable, it's production-reachable (never exploitable)
    reachable = _classify(_finding("db.py", kind=kind), _reachable_manifest(), taint=_taint_path)
    assert reachable.classification == "production-reachable"

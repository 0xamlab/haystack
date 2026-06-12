"""Regression guard: the snapshot cold-create path must call file_analysis_context_hash with only
kwargs the injected hash function actually accepts.

A previous change passed a `repository_root=` kwarg that the committed
repository_cache._file_analysis_context_hash did not accept, so every COLD snapshot creation (new
repo/revision, or a fresh replica on a lookup miss) raised TypeError. It slipped through CI because
the snapshot *service* tests that exercise cold-create are not in the CI test set, and locally the
extra kwarg happened to be accepted by an in-progress working-tree edit to the hash function.

This contract derives the call-site kwargs from the source (AST) and the accepted params from the
real function signature, so it catches ANY drift between the two without a heavy git-repo fixture —
no hardcoded names to bump (see the dynamic-count-tests rule)."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from apps.api_server.services import repository_intelligence_cache as repository_cache

_SNAPSHOT_WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / "apps/api_server/services/repository_intelligence_snapshot_workflow.py"
)


def _call_site_kwargs() -> set[str]:
    """Every keyword arg passed to any file_analysis_context_hash(...) call in the workflow."""
    tree = ast.parse(_SNAPSHOT_WORKFLOW.read_text(encoding="utf-8"))
    kwargs: set[str] = set()
    found = False
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "file_analysis_context_hash"
        ):
            found = True
            kwargs |= {kw.arg for kw in node.keywords if kw.arg is not None}
    assert found, "could not locate a file_analysis_context_hash(...) call in snapshot_workflow"
    return kwargs


def test_cold_create_passes_only_accepted_kwargs() -> None:
    accepted = set(inspect.signature(repository_cache._file_analysis_context_hash).parameters)
    passed = _call_site_kwargs()
    unexpected = passed - accepted
    assert not unexpected, (
        "snapshot cold-create passes kwargs the injected file-analysis hash function does not "
        f"accept (TypeError on every cold snapshot creation): {sorted(unexpected)}"
    )

"""Verified-agentic planner tier (forked-Cline agent-core; engine "cline_fork").

Extracted from repository_intelligence_planner_generation.py to keep that module
within the per-module line budget. The provider/deterministic tiers stay there and
import this tier; the names are re-exported from planner_generation for API/test
stability.
"""
from __future__ import annotations

import difflib
import os
from pathlib import Path
from typing import Any

from apps.api_server.services import (
    repository_intelligence_storage as repository_storage,
)
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)


# ─── verified_agentic planner tier (forked-Cline agent-core; engine "cline_fork") ──
#
# Instead of a single blind chat completion, this tier runs a headless agent loop
# inside the materialized checkout, with our token-compressed triage evidence +
# (optional) graph blast-radius injected so the agent skips repository exploration.
# Python — not the agent — is the source of truth for the diff: it is recomputed
# from before/after tree state. The Node sidecar is reached through the injected
# ``run_agent`` callable (``_DEFAULT_RUN_AGENT`` until the sidecar is wired), which
# keeps this seam testable without Node or a live model.

_VERIFIED_AGENTIC_MAX_CAPTURE_FILE_BYTES = 1_000_000

# AR-OPT-4 verified_agentic tool profile (carried in task_spec to the agent-core
# sidecar). Default is the controlled-risk profile: suppress repository exploration
# but keep an in-sandbox shell for post-patch validation. Override per deployment.
_AGENT_TOOL_PROFILE_ENV = "ALGENTA_REPOSITORY_AGENT_TOOL_PROFILE"
_AGENT_TOOL_PROFILES = ("no_exploration_local_validation", "no_exploration_no_shell")
_DEFAULT_AGENT_TOOL_PROFILE = "no_exploration_local_validation"


def _agent_tool_profile() -> str:
    value = os.environ.get(_AGENT_TOOL_PROFILE_ENV, _DEFAULT_AGENT_TOOL_PROFILE).strip()
    return value if value in _AGENT_TOOL_PROFILES else _DEFAULT_AGENT_TOOL_PROFILE


def _default_run_agent(
    *,
    working_dir: str,
    task_spec: dict[str, Any],
    injected_context: dict[str, Any],
    limits: dict[str, Any],
) -> dict[str, Any]:
    """Default agent runner: routes to the forked-Cline agent-core sidecar.

    When ``ALGENTA_AGENT_CORE_URL`` is set, POSTs the run to the sidecar over the
    loopback NDJSON contract (the sidecar mutates files under ``working_dir`` with
    the vendored Cline SDK; Python recomputes the authoritative diff). Otherwise
    raises 503. Kept monkeypatchable so the Python seam stays testable in isolation.
    """
    base_url = os.environ.get("ALGENTA_AGENT_CORE_URL")
    if base_url:
        from apps.api_server.services.repository_intelligence_agent_core_client import (
            run_agent_via_sidecar,
        )

        return run_agent_via_sidecar(
            working_dir=working_dir,
            task_spec=task_spec,
            injected_context=injected_context,
            limits=limits,
            base_url=base_url,
        )
    raise RepositoryIntelligenceError(
        code="repository_agent_core_unavailable",
        message=(
            "verified_agentic repository planning requires the agent-core sidecar "
            "(set ALGENTA_AGENT_CORE_URL), which is not configured in this deployment."
        ),
        status_code=503,
    )


_DEFAULT_RUN_AGENT = _default_run_agent
_DEFAULT_GRAPH_QUERY = None


def _capture_repository_tree_state(root_path: Path) -> dict[str, str]:
    """Snapshot the textual contents of every readable file under ``root_path``.

    Binary, oversized, symlinked, and VCS-internal files are skipped. Used to
    compute the authoritative diff in Python (the agent's own ``working_tree_diff``
    is advisory/debug only).
    """
    state: dict[str, str] = {}
    root_abs = root_path.resolve()
    for path in sorted(root_abs.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(root_abs).as_posix()
        if relative == ".git" or relative.startswith(".git/"):
            continue
        try:
            if path.stat().st_size > _VERIFIED_AGENTIC_MAX_CAPTURE_FILE_BYTES:
                continue
            state[relative] = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
    return state


def _unified_diff_from_tree_states(
    before: dict[str, str],
    after: dict[str, str],
) -> str:
    """Build a ``git apply``-able unified diff from before/after tree snapshots."""
    segments: list[str] = []
    for relative in sorted(set(before) | set(after)):
        old_text = before.get(relative)
        new_text = after.get(relative)
        if old_text == new_text:
            continue
        from_lines = old_text.splitlines(keepends=True) if old_text is not None else []
        to_lines = new_text.splitlines(keepends=True) if new_text is not None else []
        from_file = "/dev/null" if old_text is None else f"a/{relative}"
        to_file = "/dev/null" if new_text is None else f"b/{relative}"
        segments.append(
            "".join(
                difflib.unified_diff(
                    from_lines,
                    to_lines,
                    fromfile=from_file,
                    tofile=to_file,
                )
            )
        )
    return "".join(segments)


def _estimate_context_tokens(text: str) -> int:
    return max(1, (len(text.encode("utf-8")) + 3) // 4)


def _build_line_context_bundle(
    *,
    snapshot_manifest: dict[str, Any],
    triage_manifest: dict[str, Any],
    root_path: Path,
    top_k_files: int = 3,
    top_k_symbols_per_file: int = 3,
    max_lines_per_symbol: int = 120,
    max_total_context_tokens: int = 8_000,
) -> list[dict[str, Any]]:
    """AR-OPT-4: full line-context top-K bundle so the agent edits without exploring.

    For the top-ranked suspect files, attach the actual numbered source of the
    top symbols (diagnostic-touching first), plus nearest imports, enclosing
    symbol, and touching diagnostics. Deterministic and bounded by caps + a total
    token budget so it never balloons the agent prompt.
    """
    files_by_path = {
        str(file_entry["file_path"]): file_entry
        for file_entry in snapshot_manifest.get("files", [])
    }
    signals = triage_manifest.get("signals", {})
    raw_diagnostics = signals.get("diagnostics", []) if isinstance(signals, dict) else []
    diagnostics_by_path: dict[str, list[dict[str, Any]]] = {}
    for diagnostic in raw_diagnostics:
        if isinstance(diagnostic, dict) and diagnostic.get("path") is not None:
            diagnostics_by_path.setdefault(str(diagnostic["path"]), []).append(diagnostic)

    ranked_paths = [str(path) for path in triage_manifest.get("suspect_files", [])]
    if not ranked_paths:
        ranked_paths = [
            str(item.get("file_path"))
            for item in triage_manifest.get("evidence_items", [])
            if isinstance(item, dict) and item.get("file_path")
        ]
    # preserve rank order, dedupe, keep only files present in the snapshot
    seen: set[str] = set()
    ordered_files: list[str] = []
    for path in ranked_paths:
        if path in files_by_path and path not in seen:
            seen.add(path)
            ordered_files.append(path)
    ordered_files = ordered_files[:top_k_files]

    bundle: list[dict[str, Any]] = []
    total_tokens = 0
    for file_path in ordered_files:
        file_entry = files_by_path[file_path]
        try:
            source_lines = (root_path / file_path).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        symbols = [s for s in file_entry.get("symbols", []) if s.get("symbol_name")]
        symbols_by_id = {str(s.get("symbol_id")): s for s in symbols}
        nearest_imports = [
            str(dependency.get("target_file") or dependency.get("target_symbol") or "")
            for dependency in file_entry.get("dependencies", [])
        ]
        nearest_imports = [imp for imp in nearest_imports if imp][:5]
        file_diagnostics = diagnostics_by_path.get(file_path, [])
        diagnostic_lines = {
            int(d["line"]) for d in file_diagnostics if isinstance(d.get("line"), int)
        }

        def _symbol_priority(symbol: dict[str, Any]) -> tuple[int, int]:
            start = int(symbol.get("start_line") or 0)
            end = int(symbol.get("end_line") or start)
            touches = any(start <= line <= end for line in diagnostic_lines)
            return (0 if touches else 1, start)

        for symbol in sorted(symbols, key=_symbol_priority)[:top_k_symbols_per_file]:
            start = max(1, int(symbol.get("start_line") or 1))
            end = int(symbol.get("end_line") or start)
            end = min(max(end, start), start + max_lines_per_symbol - 1, len(source_lines))
            numbered_source = "\n".join(
                f"{line_no:>6}\t{source_lines[line_no - 1]}"
                for line_no in range(start, end + 1)
            )
            parent_id = symbol.get("parent_symbol_id")
            enclosing_symbol = (
                symbols_by_id.get(str(parent_id), {}).get("symbol_name")
                if parent_id is not None
                else None
            )
            touching = [
                str(d["message"])
                for d in file_diagnostics
                if isinstance(d.get("line"), int)
                and start <= int(d["line"]) <= end
                and d.get("message")
            ]
            entry = {
                "file_path": file_path,
                "language": str(file_entry.get("language") or ""),
                "symbol_name": str(symbol.get("symbol_name")),
                "symbol_kind": str(symbol.get("symbol_kind") or ""),
                "start_line": start,
                "end_line": end,
                "numbered_source": numbered_source,
                "nearest_imports": nearest_imports,
                "enclosing_symbol": enclosing_symbol,
                "touching_diagnostics": touching,
            }
            entry_tokens = _estimate_context_tokens(numbered_source) + 32
            if bundle and total_tokens + entry_tokens > max_total_context_tokens:
                return bundle
            bundle.append(entry)
            total_tokens += entry_tokens
    return bundle


async def _generate_verified_agentic_repository_patch_plan(
    *,
    model_id: str,
    snapshot_manifest: dict[str, Any],
    triage_manifest: dict[str, Any],
    run_agent: Any = None,
    graph_query: Any = None,
) -> dict[str, Any]:
    """Run the forked-Cline agent loop over the materialized checkout.

    Returns the same dict shape as the other planner tiers so all downstream
    decision-plan / simulate / apply code is unchanged. ``planner_engine`` and the
    agent provenance are included for the *internal* audit record only — the
    public ``RepositoryAnalysis`` mapping does not read them (red line #4).
    """
    run_agent = run_agent or _DEFAULT_RUN_AGENT
    if graph_query is None:
        graph_query = _DEFAULT_GRAPH_QUERY

    suspect_files = list(triage_manifest.get("suspect_files", []))
    suspect_symbols = list(triage_manifest.get("suspect_symbols", []))
    signals = triage_manifest.get("signals", {})

    injected_context: dict[str, Any] = {
        "evidence_items": triage_manifest.get("evidence_items", []),
        "suspect_files": suspect_files,
        "suspect_symbols": suspect_symbols,
        "signals": signals,
    }
    if graph_query is not None:
        try:
            injected_context["graph_blast_radius"] = graph_query(
                snapshot_manifest=snapshot_manifest,
                suspect_files=suspect_files,
                suspect_symbols=suspect_symbols,
            )
        except Exception:  # noqa: BLE001 — graph injection is best-effort context
            injected_context["graph_blast_radius"] = None

    task_spec = {
        "snapshot_id": snapshot_manifest["snapshot_id"],
        "resolved_revision": snapshot_manifest.get("resolved_revision"),
        "issue_text": signals.get("issue_text"),
        # AR-OPT-4: tell the agent-core which tool profile to enforce (suppress
        # exploration; shell only for controlled post-patch validation).
        "tool_profile": _agent_tool_profile(),
    }
    limits = {"token_budget": 6_000, "max_turns": 8}

    with repository_storage.materialized_snapshot(snapshot_manifest) as root_path:
        root_path = Path(root_path)
        before_state = _capture_repository_tree_state(root_path)
        # AR-OPT-4: attach the full line-context bundle so the agent edits the suspect
        # symbols directly instead of spending turns/tokens re-reading the repository.
        injected_context["context_bundle"] = _build_line_context_bundle(
            snapshot_manifest=snapshot_manifest,
            triage_manifest=triage_manifest,
            root_path=root_path,
        )
        agent_result = run_agent(
            working_dir=str(root_path),
            task_spec=task_spec,
            injected_context=injected_context,
            limits=limits,
        )
        if not isinstance(agent_result, dict):
            raise RepositoryIntelligenceError(
                code="repository_agent_invalid_result",
                message="verified_agentic agent runner returned a non-object result.",
                status_code=502,
            )
        # Python is the source of truth for the diff; any working_tree_diff the
        # agent returns is advisory/debug only and deliberately ignored here.
        after_state = _capture_repository_tree_state(root_path)

    status = str(agent_result.get("status") or "completed")
    patch_diff = _unified_diff_from_tree_states(before_state, after_state)

    if status in {"failed", "aborted"}:
        raise RepositoryIntelligenceError(
            code=f"repository_agent_{status}",
            message=f"verified_agentic agent run did not complete (status={status}).",
            status_code=502,
            details={"agent_run_id": agent_result.get("agent_run_id")},
        )
    if not patch_diff.strip():
        raise RepositoryIntelligenceError(
            code="repository_agent_no_change",
            message="verified_agentic agent run produced no file changes.",
            status_code=422,
            details={"agent_run_id": agent_result.get("agent_run_id")},
        )

    candidate_fixes = agent_result.get("candidate_fixes")
    if isinstance(candidate_fixes, str):
        candidate_fixes = [candidate_fixes]
    elif not isinstance(candidate_fixes, list):
        candidate_fixes = []

    try:
        confidence = float(agent_result.get("confidence"))
    except (TypeError, ValueError):
        confidence = 0.55
    confidence = min(max(confidence, 0.0), 1.0)

    return {
        "root_cause": str(agent_result.get("root_cause") or "").strip()
        or "Repository issue localized from the injected evidence bundle.",
        "candidate_fixes": candidate_fixes,
        "recommended_action": str(agent_result.get("recommended_action") or "").strip()
        or "Apply the agent-generated repository patch.",
        "rationale": str(agent_result.get("rationale") or "").strip()
        or (
            "Patch generated by the verified agentic planner over the injected "
            "repository evidence bundle and blast-radius."
        ),
        "confidence": confidence,
        "patch_diff": patch_diff,
        "planner_model_id": model_id,
        "planner_execution_mode": "verified_agentic",
        "planner_provider_backend": None,
        # Internal attribution / provenance only — NOT surfaced in the public DecisionPlan.
        "planner_engine": "cline_fork",
        "agent_run_id": agent_result.get("agent_run_id"),
        "transcript_ref": agent_result.get("transcript_ref"),
    }

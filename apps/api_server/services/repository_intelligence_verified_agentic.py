"""Verified-agentic planner tier (forked-Cline agent-core; engine "cline_fork").

Extracted from repository_intelligence_planner_generation.py to keep that module
within the per-module line budget. The provider/deterministic tiers stay there and
import this tier; the names are re-exported from planner_generation for API/test
stability.
"""
from __future__ import annotations

import asyncio
import difflib
import inspect
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from apps.api_server.services import (
    repository_intelligence_storage as repository_storage,
)
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)
from apps.api_server.services.tenant_keys import (
    require_per_tenant_keys,
    resolve_engine_api_key,
    resolve_provider_api_key,
)

logger = logging.getLogger(__name__)


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


def _agent_provider_key_fields() -> dict[str, Any]:
    """B10 PR11b: the per-tenant LLM-provider-key fields for task_spec.engine.

    Sends the org override ONLY (resolve_provider_api_key(None, backend) never borrows the
    decision-engine env key — the sidecar keeps its own env as the pooled fallback). In a
    multi-tenant deployment we also set the require flag so the sidecar fails closed instead of
    borrowing its shared env key. The backend default matches the agent-core default ("anthropic")
    so the lookup agrees with the provider the sidecar will actually use."""
    backend = os.environ.get("ALGENTA_AGENT_PROVIDER") or "anthropic"
    fields: dict[str, Any] = {}
    key = resolve_provider_api_key(None, backend)
    if key:
        fields["provider_api_key"] = key
    if require_per_tenant_keys():
        fields["require_provider_api_key"] = True
    return fields

# AR-OPT-4 verified_agentic tool profile (carried in task_spec to the agent-core
# sidecar). Default is the controlled-risk profile: suppress repository exploration
# but keep an in-sandbox shell for post-patch validation. Override per deployment.
_AGENT_TOOL_PROFILE_ENV = "ALGENTA_REPOSITORY_AGENT_TOOL_PROFILE"
_AGENT_TOOL_PROFILES = ("no_exploration_local_validation", "no_exploration_no_shell")
_DEFAULT_AGENT_TOOL_PROFILE = "no_exploration_local_validation"


def _agent_tool_profile() -> str:
    value = os.environ.get(_AGENT_TOOL_PROFILE_ENV, _DEFAULT_AGENT_TOOL_PROFILE).strip()
    return value if value in _AGENT_TOOL_PROFILES else _DEFAULT_AGENT_TOOL_PROFILE


async def _default_run_agent(
    *,
    working_dir: str,
    task_spec: dict[str, Any],
    injected_context: dict[str, Any],
    limits: dict[str, Any],
) -> dict[str, Any]:
    """Default agent runner: routes to the forked-Cline agent-core sidecar.

    When ``ALGENTA_AGENT_CORE_URL`` is set, POSTs the run to the sidecar over the
    loopback NDJSON contract via the async, egress-guarded client (the sidecar mutates
    files under ``working_dir`` with the vendored Cline SDK; Python recomputes the
    authoritative diff). Otherwise raises 503. Kept monkeypatchable so the Python seam
    stays testable in isolation.
    """
    base_url = os.environ.get("ALGENTA_AGENT_CORE_URL")
    if base_url:
        from apps.api_server.services.repository_intelligence_agent_core_client import (
            run_agent_via_sidecar,
        )

        return await run_agent_via_sidecar(
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


def _planner_usage_from_agent_result(agent_result: dict[str, Any]) -> dict[str, Any]:
    telemetry = agent_result.get("telemetry")
    if not isinstance(telemetry, dict):
        usage = agent_result.get("usage")
        if not isinstance(usage, dict):
            return {}
        telemetry = usage
    input_uncached = telemetry.get("tokens_in_uncached", telemetry.get("inputTokens", 0))
    output_tokens = telemetry.get("tokens_out", telemetry.get("outputTokens", 0))
    cache_read_tokens = telemetry.get("cache_read_tokens", telemetry.get("cacheReadTokens", 0))
    cache_write_tokens = telemetry.get(
        "cache_write_tokens",
        telemetry.get("cacheWriteTokens", 0),
    )
    if not any(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        for value in (
            input_uncached,
            output_tokens,
            cache_read_tokens,
            cache_write_tokens,
        )
    ):
        return {}
    return {
        "input_tokens": float(input_uncached) + float(cache_read_tokens) + float(cache_write_tokens),
        "output_tokens": float(output_tokens),
        "cache_read_tokens": float(cache_read_tokens),
        "cache_write_tokens": float(cache_write_tokens),
        "cost_usd": (
            float(telemetry["total_cost"])
            if isinstance(telemetry.get("total_cost"), (int, float))
            and not isinstance(telemetry.get("total_cost"), bool)
            else None
        ),
    }


def _assert_live_runtime(agent_result: dict[str, Any]) -> None:
    """A live decision plan must be backed by a REAL Cline run, never the offline stub
    (Wave B4 runtime truth). The stub self-identifies (terminal_state /
    artifacts.offline_contract_only); the real sidecar sends runtime.is_stub=false. Absent
    markers are treated as live (unit-test mocks). An explicit stub/offline marker on the
    live path is a hard failure — we never emit a stub-backed run as a live result. An
    offline-contract test opts out via ALGENTA_RUN_CLASS=offline_contract_only.
    """
    if os.environ.get("ALGENTA_RUN_CLASS") == "offline_contract_only":
        return
    runtime = agent_result.get("runtime")
    runtime = runtime if isinstance(runtime, dict) else {}
    artifacts = agent_result.get("artifacts")
    artifacts = artifacts if isinstance(artifacts, dict) else {}
    is_stub = bool(runtime.get("is_stub"))
    offline = (
        bool(runtime.get("offline_contract_only"))
        or bool(artifacts.get("offline_contract_only"))
        or agent_result.get("terminal_state") == "offline_contract_only"
    )
    if is_stub or offline:
        raise RepositoryIntelligenceError(
            code="repository_agent_runtime_not_live",
            message=(
                "verified_agentic produced a result from a stub/offline-contract agent run, "
                "not a live Cline runtime; refusing to emit it as a live decision plan."
            ),
            status_code=502,
            details={"agent_run_id": agent_result.get("agent_run_id")},
        )


def _capture_repository_tree_state(root_path: Path) -> dict[str, str]:
    """Snapshot the textual contents of every readable file under ``root_path``.

    Binary, oversized, symlinked, and VCS-internal files are skipped. Used to
    compute the authoritative diff in Python (the agent's own ``working_tree_diff``
    is advisory/debug only). Files are read with ``newline=""`` so CRLF/LF bytes
    are preserved exactly; newline normalization here would generate patches that
    cannot be validated against the materialized snapshot baseline later on.
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
            with path.open("r", encoding="utf-8", newline="") as handle:
                state[relative] = handle.read()
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
            sym_start = max(1, int(symbol.get("start_line") or 1))
            sym_end = max(int(symbol.get("end_line") or sym_start), sym_start)
            # Focus on the bug, language-agnostically: if a diagnostic touches this
            # symbol, center the window on it so a large symbol never buries the
            # failing line out of view; otherwise show the symbol head. Either way
            # cap to max_lines_per_symbol so one big symbol can't dominate (or blow
            # up) the bundle. Purely line-based — no per-language rules.
            touching_lines = sorted(
                line for line in diagnostic_lines if sym_start <= line <= sym_end
            )
            if touching_lines:
                focus = touching_lines[len(touching_lines) // 2]
                start = max(sym_start, focus - max_lines_per_symbol // 2)
                end = min(sym_end, len(source_lines), start + max_lines_per_symbol - 1)
                start = max(sym_start, end - max_lines_per_symbol + 1)
            else:
                start = sym_start
                end = min(sym_end, len(source_lines), sym_start + max_lines_per_symbol - 1)
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


def _dedupe_bundled_evidence(
    evidence_items: list[Any],
    context_bundle: list[dict[str, Any]],
) -> list[Any]:
    """Strip the redundant snippet from evidence items already carried in full by
    the context bundle.

    The bundle attaches the full numbered source for the top suspect
    (file, symbol) pairs. An evidence item for one of those same pairs would
    duplicate that code in the JSON-serialized prompt, so we replace its snippet
    with a pointer — keeping the item's ranking/diagnostic metadata while sending
    the code only once. Evidence on symbols the bundle does not cover is left
    intact (it is complementary, not redundant).
    """
    bundled = {
        (str(entry.get("file_path")), str(entry.get("symbol_name")))
        for entry in context_bundle
        if isinstance(entry, dict)
    }
    if not bundled:
        return evidence_items
    deduped: list[Any] = []
    for item in evidence_items:
        if (
            isinstance(item, dict)
            and item.get("snippet")
            and (str(item.get("file_path")), str(item.get("symbol_name"))) in bundled
        ):
            item = {**item, "snippet": "[full source in context_bundle]"}
        deduped.append(item)
    return deduped


def _agent_provider_chain() -> list[tuple[str | None, str | None]]:
    """BYOM failover chain: the primary provider/model + any in ALGENTA_AGENT_FALLBACK_MODELS
    ('openai-native:gpt-5.4,gemini:gemini-2.5-pro'). On overload/stall/failure of one provider the run
    fails over to the next — a single provider outage (e.g. an Anthropic 529) must not stall the fix.
    Codna is LLM-agnostic, so failover is just a config of which models to try, in order."""
    chain: list[tuple[str | None, str | None]] = [
        (os.environ.get("ALGENTA_AGENT_PROVIDER") or None, os.environ.get("ALGENTA_AGENT_MODEL") or None)
    ]
    for spec in (os.environ.get("ALGENTA_AGENT_FALLBACK_MODELS") or "").split(","):
        spec = spec.strip()
        if not spec:
            continue
        prov, _, model = spec.partition(":")
        chain.append((prov.strip() or None, model.strip() or None))
    return chain


def _materialized_snapshot_with_git_baseline(snapshot_manifest: dict[str, Any]):
    """Use the git-baseline materialization contract when the provider supports it.

    The production storage helper accepts ``git_baseline=...``. Some seam tests
    monkeypatch ``materialized_snapshot`` with older one-arg contextmanager fakes,
    so detect that explicitly instead of assuming every injected callable already
    speaks the newer kwarg.
    """
    materialize = repository_storage.materialized_snapshot
    if "git_baseline" in inspect.signature(materialize).parameters:
        return materialize(snapshot_manifest, git_baseline=True)
    return materialize(snapshot_manifest)


def _reset_worktree(root_path: Path) -> None:
    """Reset the materialized snapshot to its git baseline (materialized_snapshot(git_baseline=True)) so a
    failover attempt on a new provider starts clean, not from a prior attempt's partial edits."""
    for argv in (["reset", "--hard", "-q"], ["clean", "-fdq"]):
        try:
            subprocess.run(["git", "-C", str(root_path), *argv], check=False, capture_output=True, timeout=60)
        except Exception:  # noqa: BLE001 — best-effort
            pass


# Markers that distinguish a genuine LLM-PROVIDER failure (worth switching models for) from an
# infra/govern/tool abort (switching the model CANNOT fix it — so surface it, don't mask it). Misclassifying
# the latter as a provider failure is exactly what made a govern-hook connect abort look like "Anthropic
# keeps failing" and silently swap to another model.
_PROVIDER_FAILURE_MARKERS = (
    "overload", "529", "503", "service unavailable", "rate limit", "rate_limit", "429",
    "too many requests", "capacity", "insufficient_quota", "quota", "authentication error", "401",
    "invalid api key", "invalid_api_key", "model is currently", "upstream", "provider error",
)
_INFRA_ABORT_MARKERS = (  # NOT a provider problem; a model switch is pointless → surface the real error
    "govern", "unable to connect", "able to access the url", "simulate-patch", "plugin_evidence",
    "econnrefused", "connection refused", "agent_core", "agentruntimeabort",
)


def _is_provider_failure(text: str) -> bool:
    """True ONLY when a failure looks like a real LLM-provider problem (overload / rate-limit / auth /
    a hung model turn) worth failing over for. Govern/tool/connectivity aborts return False so the run
    surfaces the true error instead of pointlessly swapping providers and hiding it."""
    t = (text or "").lower()
    if any(m in t for m in _INFRA_ABORT_MARKERS):
        return False
    if any(m in t for m in _PROVIDER_FAILURE_MARKERS):
        return True
    return ("timeout" in t or "timed out" in t or "stall" in t)  # a hung turn, with no infra marker


async def _run_agent_with_failover(run_agent, *, working_dir, task_spec, injected_context, limits, root_path):
    """Run the agent, failing over across the BYOM provider chain ONLY on genuine provider errors
    (overload/rate-limit/auth/hung turn) so one provider's outage doesn't stall the run — while
    infra/govern/tool aborts are surfaced, NOT masked by a pointless model switch. Mutates
    task_spec.engine.provider/model per attempt; resets the worktree between attempts."""
    chain = _agent_provider_chain()
    engine_blk = task_spec.get("engine") if isinstance(task_spec.get("engine"), dict) else None
    last_exc: Exception | None = None
    for attempt, (prov, model) in enumerate(chain):
        if engine_blk is not None:
            if prov is not None:
                engine_blk["provider"] = prov
            if model is not None:
                engine_blk["model"] = model
        if attempt > 0:
            _reset_worktree(root_path)
            logger.warning("verified_agentic: failover -> provider=%s model=%s (attempt %d/%d)",
                           prov, model, attempt + 1, len(chain))
        try:
            if asyncio.iscoroutinefunction(run_agent):
                result = await run_agent(working_dir=working_dir, task_spec=task_spec,
                                         injected_context=injected_context, limits=limits)
            else:
                result = await asyncio.to_thread(run_agent, working_dir=working_dir, task_spec=task_spec,
                                                  injected_context=injected_context, limits=limits)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < len(chain) - 1 and _is_provider_failure(str(exc)):
                logger.warning("verified_agentic: provider=%s provider-error (%s); failing over", prov, exc)
                continue
            raise  # infra/transport/unknown — surface it, don't mask with a model switch
        status = str(result.get("status") or "completed") if isinstance(result, dict) else "failed"
        if status in {"failed", "aborted"}:
            reason = ""
            if isinstance(result, dict):
                reason = str(result.get("error") or result.get("error_message")
                             or result.get("abort_reason") or result.get("message") or "")
            if attempt < len(chain) - 1 and _is_provider_failure(reason):
                logger.warning("verified_agentic: provider=%s provider-error status=%s (%s); failing over",
                               prov, status, reason[:160])
                continue
            # NOT a provider failure (govern/tool/infra abort) — return it so the real error surfaces
            # downstream instead of being hidden behind a pointless provider swap.
            logger.error("verified_agentic: provider=%s status=%s is NOT a provider failure (%r) — "
                         "surfacing rather than failing over", prov, status, reason[:200])
        return result
    if last_exc:
        raise last_exc
    return None


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
    # Engine-behind wiring: when the LOCAL Algenta engine is reachable, hand the
    # agent-core its loopback URL + repo/snapshot ids + an engine api-key so the
    # Cline agent's Algenta tools (localize / graph_query / simulate_patch) can call
    # back into it. The LLM provider stays ANY (BYOM) — only the ENGINE is local.
    # Additive: without ALGENTA_ENGINE_URL the agent-core loads no Algenta tools and
    # behaves exactly as before.
    _engine_url = os.environ.get("ALGENTA_ENGINE_URL")
    if _engine_url:
        task_spec["engine"] = {
            "url": _engine_url,
            "repository_id": str(snapshot_manifest.get("repository_id") or ""),
            "snapshot_id": snapshot_manifest["snapshot_id"],
            # B10: resolve the engine key through the per-tenant seam (per-request org override >
            # single-tenant env; multi-tenant with no override fails closed to "" rather than
            # reusing the shared env key across tenants).
            "api_key": resolve_engine_api_key() or "",
            # LLM provider/model are deployment choice (any provider); None lets the
            # agent-core pick its configured default.
            "provider": os.environ.get("ALGENTA_AGENT_PROVIDER") or None,
            "model": os.environ.get("ALGENTA_AGENT_MODEL") or None,
            # B10 PR11b: the agent's own LLM key — per-tenant override + multi-tenant fail-closed
            # flag (override-only; the sidecar keeps its env as the pooled fallback).
            **_agent_provider_key_fields(),
        }
    # Agentic run bounds — NOT a wall clock. ``max_turns`` caps the agent's edit→verify
    # iterations; ``timeout_ms`` is the PER-TURN budget (one model turn + the tool calls it
    # drives — including a full test step), reset every turn. The agent-core sidecar's own
    # fallback is a stingy 150s per turn (a turn that runs a test suite blows past it and the
    # whole run is marked failed) — so we pass a generous, Cursor/Claude-Code-class default
    # here (10 min/turn, 24 turns) and let a harder fix converge instead of dying mid-iteration.
    # All three are env-tunable for heavier self-hosting; raising them costs tokens/latency,
    # never correctness. (Total run time is bounded by max_turns × turns actually taken, not a
    # single guillotine — the proper complement is sidecar heartbeats during long model calls.)
    limits = {
        "token_budget": int(os.environ.get("ALGENTA_AGENT_TOKEN_BUDGET", "6000")),
        "max_turns": int(os.environ.get("ALGENTA_AGENT_MAX_TURNS", "50")),
        "timeout_ms": int(os.environ.get("ALGENTA_AGENT_TURN_TIMEOUT_MS", "600000")),
    }

    with _materialized_snapshot_with_git_baseline(snapshot_manifest) as root_path:
        root_path = Path(root_path)
        before_state = _capture_repository_tree_state(root_path)
        # AR-OPT-4: attach the full line-context bundle so the agent edits the suspect
        # symbols directly instead of spending turns/tokens re-reading the repository.
        injected_context["context_bundle"] = _build_line_context_bundle(
            snapshot_manifest=snapshot_manifest,
            triage_manifest=triage_manifest,
            root_path=root_path,
        )
        # Don't send the same code twice: drop snippets the bundle already carries.
        injected_context["evidence_items"] = _dedupe_bundled_evidence(
            injected_context["evidence_items"],
            injected_context["context_bundle"],
        )
        # B2: the default runner is async + non-blocking (egress-guarded httpx, run in
        # the worker off the request path). Await it directly. A legacy SYNCHRONOUS
        # runner is kept off the event loop via to_thread (the A1 unconditional wrap is
        # gone — the async path no longer needs it).
        # BYOM failover: try the provider chain (primary + ALGENTA_AGENT_FALLBACK_MODELS), switching on
        # a stalled/failed provider so an Anthropic 529 overload doesn't stall the run — fall over to GPT/Gemini.
        agent_result = await _run_agent_with_failover(
            run_agent,
            working_dir=str(root_path),
            task_spec=task_spec,
            injected_context=injected_context,
            limits=limits,
            root_path=root_path,
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
    _assert_live_runtime(agent_result)
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
        "planner_usage": _planner_usage_from_agent_result(agent_result),
        "session_id": agent_result.get("session_id"),
        "runtime_kind": "cline",
        "runtime_provider": (
            telemetry.get("provider")
            if isinstance((telemetry := agent_result.get("telemetry")), dict)
            else None
        ),
        "runtime_model": telemetry.get("model") if isinstance(telemetry, dict) else None,
        # Internal attribution / provenance only — NOT surfaced in the public DecisionPlan.
        "planner_engine": "cline_fork",
        "agent_run_id": agent_result.get("agent_run_id"),
        "transcript_ref": agent_result.get("transcript_ref"),
    }

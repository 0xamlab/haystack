"""Embed the Codna SDK (local Mojo runtime) into repository triage ranking — the
core "DNA" integration.

This makes the heavy Codna engine a first-class, flag-gated ranking lane for the
/repositories pipeline, connecting through the LOCAL SDK runtime (the daemon
sidecar, or the in-process executor) rather than any cloud API. It degrades
gracefully: RRF fusion + graph proximity are pure Python, and the Mojo lane returns
``None`` whenever the runtime/library is unavailable so the caller falls back to the
deterministic Python heuristic.

Mojo lane (today): a bounded fuzzy keyword↔file-stem match via the dispatchable
``text.fuzzy.jaro_winkler_similarity`` kernel — fixing camelCase/snake_case recall
the exact-substring heuristic misses (e.g. ``authHandler`` ↔ ``auth_handler`` ≈ 0.95).
A batched ``vector_kernels.repo_ranker`` Mojo entrypoint can later replace the
per-candidate dispatch for production scale.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

_SDK_RANKING_ENV = "ALGENTA_REPOSITORIES_SDK_RANKING"
_SDK_RUNTIME_MODE_ENV = "ALGENTA_REPOSITORIES_SDK_RUNTIME_MODE"
# Production batched kernel: vector_kernels.repo_ranker.run_repo_rank ranks the whole
# candidate set in ONE Mojo dispatch (SIMD bigram-cosine + token-Jaccard; benchmarked
# at ~44 us / 50 candidates, well under 1 ms). Becomes dispatchable once the generated
# runtime dispatch is regenerated to include it (the kernel is registered in the
# inventory allowlist); until then the lane falls back to the Python heuristic.
_REPO_RANKER_LIBRARY = "vector_kernels.repo_ranker"
_REPO_RANKER_FUNCTION = "run_repo_rank"
_FUZZY_LIBRARY = "text.fuzzy"
_FUZZY_FUNCTION = "jaro_winkler_similarity"
_MAX_CANDIDATES = 256
_FUZZY_THRESHOLD = 0.84


def sdk_ranking_enabled() -> bool:
    """Whether the SDK/Mojo ranking lane is opted in (default off = pure-Python)."""
    return os.environ.get(_SDK_RANKING_ENV, "false").strip().lower() in {"1", "true", "yes", "on"}


_runtime_env_loaded = False


def _load_runtime_env() -> None:
    """Load ``$ALGENTA_RUNTIME_DIR/.env`` (the runtime's own credential file:
    ALGENTA_API_KEY, deployment profile, ...) into the process environment so the
    local Codna engine is authenticated rather than silently falling back to the
    Python heuristic. Existing os.environ values win (explicit config overrides the
    file); idempotent."""
    global _runtime_env_loaded
    if _runtime_env_loaded:
        return
    _runtime_env_loaded = True
    runtime_dir = os.environ.get("ALGENTA_RUNTIME_DIR") or str(
        Path.home() / ".algenta" / "runtime"
    )
    try:
        text = (Path(runtime_dir) / ".env").read_text()
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _default_runtime_mode() -> str:
    """Local-only default for the repositories lane: a warm daemon if one is up,
    else the in-process ``direct`` executor. Never cloud — repository intelligence
    is a local boundary (see project_sdk_transport_boundary), so the lane must not
    silently make network calls when no daemon is present."""
    try:
        from apps.runtime.client import DaemonClient

        if DaemonClient.is_daemon_running():
            return "local"
    except Exception:  # noqa: BLE001
        pass
    return "direct"


@lru_cache(maxsize=1)
def _runtime() -> Any | None:
    """Lazily construct the Codna SDK Runtime; None if the SDK isn't importable.

    Loads the runtime credential file first so the local engine is authenticated,
    and pins a local execution mode (daemon/direct) so the lane never degrades to a
    cloud call. If the preferred mode can't initialize, falls back to ``direct``."""
    _load_runtime_env()
    try:
        from apps.runtime.sdk import Runtime
    except Exception:  # noqa: BLE001 — SDK optional in some deployments
        return None
    mode = os.environ.get(_SDK_RUNTIME_MODE_ENV, "").strip().lower() or _default_runtime_mode()
    try:
        return Runtime(mode=mode)
    except Exception:  # noqa: BLE001
        if mode != "direct":
            try:
                return Runtime(mode="direct")
            except Exception:  # noqa: BLE001
                return None
        return None


def reset_runtime_cache() -> None:
    """Test hook: drop the cached Runtime (e.g. after changing the mode env)."""
    _runtime.cache_clear()


def reciprocal_rank_fusion(rankings: Sequence[Sequence[str]], *, k: int = 60) -> dict[str, float]:
    """Reciprocal Rank Fusion — fuse independent rankings whose raw scores are not
    comparable. Each ranking contributes ``1 / (k + rank)`` per item."""
    fused: defaultdict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            fused[str(item)] += 1.0 / (k + rank)
    return dict(fused)


def mojo_fuzzy_similarity(runtime: Any, left: str, right: str) -> float | None:
    """One real ``text.fuzzy.jaro_winkler_similarity`` dispatch; None on any failure."""
    try:
        outcome = runtime.execute(_FUZZY_LIBRARY, _FUZZY_FUNCTION, [left, right])
    except Exception:  # noqa: BLE001 — any dispatch failure -> caller falls back
        return None
    if not isinstance(outcome, dict) or not outcome.get("success"):
        return None
    value = outcome.get("result", outcome.get("result_json"))
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _file_stem(path: str) -> str:
    base = path.rsplit("/", 1)[-1]
    return base.rsplit(".", 1)[0].lower() if "." in base else base.lower()


def _dispatch_repo_ranker(
    runtime: Any,
    query_terms: Sequence[str],
    candidates: Sequence[dict[str, Any]],
    top_k: int,
) -> dict[str, float] | None:
    """Single batched dispatch to the production Mojo kernel (< 1 ms). None if the
    kernel isn't dispatchable yet (generated runtime dispatch not regenerated) or errors."""
    payload = json.dumps(
        {
            "query_terms": [str(t) for t in query_terms],
            "candidates": [
                {"path": str(c.get("path", "")), "text": str(c.get("text", c.get("path", "")))}
                for c in list(candidates)[:_MAX_CANDIDATES]
            ],
            "top_k": int(top_k),
        },
        separators=(",", ":"),
        ensure_ascii=True,
    )
    try:
        outcome = runtime.execute(_REPO_RANKER_LIBRARY, _REPO_RANKER_FUNCTION, payload)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(outcome, dict) or not outcome.get("success"):
        return None
    try:
        result = json.loads(outcome.get("result", outcome.get("result_json")) or "{}")
        return {str(m["path"]): float(m["score"]) for m in result.get("matches", [])}
    except (TypeError, ValueError, KeyError):
        return None


def _dispatch_fuzzy_fallback(
    runtime: Any, query_terms: Sequence[str], candidates: Sequence[dict[str, Any]]
) -> dict[str, float] | None:
    """Per-candidate text.fuzzy lane — dispatchable today (no regen needed); used when
    the batched repo_ranker kernel isn't yet wired into the generated dispatch."""
    terms = [t.lower() for t in dict.fromkeys(str(x).lower() for x in query_terms) if len(t) >= 3]
    terms = terms[:6]
    if not terms:
        return {}
    scores: dict[str, float] = {}
    dispatched = False
    for candidate in list(candidates)[:25]:
        path = str(candidate.get("path", ""))
        stem = _file_stem(path)
        if len(stem) < 3:
            continue
        best = 0.0
        for term in terms:
            sim = mojo_fuzzy_similarity(runtime, term, stem)
            if sim is None:
                continue
            dispatched = True
            best = max(best, sim)
        if best >= _FUZZY_THRESHOLD:
            scores[path] = round(best, 4)
    return scores if dispatched else None


def mojo_repo_rank_scores(
    *,
    query_terms: Sequence[str],
    candidates: Sequence[dict[str, Any]],
    top_k: int = _MAX_CANDIDATES,
) -> dict[str, float] | None:
    """Mojo-ranked ``{path: score}`` for the candidates, or ``None`` (-> Python
    heuristic) when the SDK is disabled/unavailable. Prefers the batched production
    kernel (one dispatch, < 1 ms); falls back to the per-candidate fuzzy lane that's
    dispatchable today."""
    if not sdk_ranking_enabled():
        return None
    runtime = _runtime()
    if runtime is None:
        return None
    batched = _dispatch_repo_ranker(runtime, query_terms, candidates, top_k)
    if batched is not None:
        return batched
    return _dispatch_fuzzy_fallback(runtime, query_terms, candidates)

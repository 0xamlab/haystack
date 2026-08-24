"""Fact-driven model onboarding — the loop that turns "a new model" into "a row
in the support matrix" with zero per-model code.

The onboarding decision is a pure function of the checkpoint's normalized fact
manifest and the declared capability table:

    resolve_config(source)   ->  the config declaration (HF repo or local path)
    onboard_facts(config)    ->  ModelFacts (normalized, family-tagged)
    backend_verdicts(facts)  ->  per-backend SUPPORTED / typed refusals
    staging_tier_gap(...)    ->  when the ONLY blocker is a staging tier, the
                                 exact tier to add so the model flips supported

Nothing here keys on a model name or brand: two checkpoints with identical
facts take identical paths, get identical verdicts, and emit identical rows.
That is the owner's "test and optimize once on hardware, then any model whose
facts fall in the proven envelope works" property, made executable.

The identity gate (`gate_backend`) reuses the existing engine doors rather than
forking them per model: the Metal arm drives the production SDK path
(`algenta.inference.decode`), the CUDA arm drives the fact-driven
`conform_generate_cuda` resident binary. Both compare greedy tokens against an
independent transformers fp32 CPU reference with sampling pinned
(`do_sample=False`, `repetition_penalty=1.0`) and classify a sub-noise flip as
a documented near-tie rather than a defect.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from algenta.model_capabilities import (
    BACKEND_FACT_RANGES,
    ModelFacts,
    TypedRefusal,
    extract_facts_from_config,
    refusals_for_facts,
    select_paths,
    stage_needed,
)

__all__ = [
    "OnboardVerdict",
    "resolve_config",
    "onboard_facts",
    "backend_verdicts",
    "staging_tier_gap",
    "backend_staging_ceiling",
    "emit_support_row",
    "emit_ledger",
]

# Backends the onboarding loop renders verdicts for, in the order the support
# matrix publishes them. Driven from the capability table, never hardcoded to a
# specific machine.
ONBOARD_BACKENDS: tuple[str, ...] = tuple(sorted(BACKEND_FACT_RANGES))

# The largest staging tier each backend can BUILD, set by its shared-memory
# budget — a hardware fact, not a per-model knob. Metal threadgroup memory is
# 32 KiB, so 6144 Float32 (24 KiB, leaving the 1 KiB reduction scratch) is the
# top buildable tier; a model staging above it is refused by the hardware, not
# by a missing build. NVIDIA's 163 KiB opt-in shared budget builds far higher
# (163 * 1024 // 4 Float32), which is why the large tiers live on the CUDA lane.
_BACKEND_STAGING_CEILING: dict[str, int] = {
    "metal": 6144,
    "cuda": 163 * 1024 // 4,
}


@dataclass(frozen=True)
class OnboardVerdict:
    """One backend's verdict for one fact set: the status, the typed refusals
    (empty when supported), and the kernel-path assignment when it applies."""

    backend: str
    status: str  # "supported" | "supported_pending_probe" | "refused"
    refusals: tuple[TypedRefusal, ...] = ()
    plan: str | None = None
    pending_probe: tuple[str, ...] = ()

    @property
    def supported(self) -> bool:
        return self.status in ("supported", "supported_pending_probe")


def resolve_config(source: str) -> tuple[dict[str, Any], str, Path | None]:
    """Resolve `source` into a config declaration.

    `source` is one of:
      * an existing directory carrying `config.json` (a local snapshot),
      * an existing `config.json` / `*.json` file,
      * a HuggingFace repo id (`org/name`) — `config.json` is fetched with the
        ambient `HF_TOKEN`/`HF_API_KEY` (gated repos included when the token is
        authorized).

    Returns `(config, source_desc, weights_dir)` where `weights_dir` is the
    directory holding the safetensors when the weights are present locally (so
    the tensor-level facts can be probed), else None. Never raises on a refused
    family — that is the verdict's job, not the resolver's."""
    from algenta.inference import _normalize_config  # local import: keep module light

    p = Path(source).expanduser()
    if p.is_dir() and (p / "config.json").is_file():
        config = _normalize_config(json.loads((p / "config.json").read_text(encoding="utf-8")))
        has_weights = (p / "model.safetensors").is_file() or (
            p / "model.safetensors.index.json"
        ).is_file()
        return config, str(p), (p if has_weights else None)
    if p.is_file() and p.suffix == ".json":
        config = _normalize_config(json.loads(p.read_text(encoding="utf-8")))
        return config, str(p), None

    # Treat anything else as a HuggingFace repo id.
    repo_id = source
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:  # pragma: no cover - huggingface_hub is a dep in practice
        raise RuntimeError(
            f"onboard: {source!r} is not a local checkpoint and huggingface_hub is not "
            "installed to fetch it"
        ) from exc
    token = os.environ.get("HF_TOKEN") or os.environ.get("HF_API_KEY") or None
    local_dir = Path("/tmp/onboard-models") / repo_id.replace("/", "__")
    snapshot_download(
        repo_id,
        local_dir=str(local_dir),
        allow_patterns=["*.json", "*.safetensors"],
        token=token,
    )
    config = _normalize_config(json.loads((local_dir / "config.json").read_text(encoding="utf-8")))
    has_weights = (local_dir / "model.safetensors").is_file() or (
        local_dir / "model.safetensors.index.json"
    ).is_file()
    return config, repo_id, (local_dir if has_weights else None)


def onboard_facts(config: dict[str, Any]) -> ModelFacts:
    """The normalized fact manifest for an onboarded config."""
    return extract_facts_from_config(config)


def _verdict_for_backend(facts: ModelFacts, backend: str) -> OnboardVerdict:
    refusals = refusals_for_facts(facts, backend=backend)
    if refusals:
        return OnboardVerdict(backend=backend, status="refused", refusals=tuple(refusals))
    # Probe facts (qk_norm/bias) may still be unknown for a config-only run.
    pending = tuple(
        name
        for name, value in (("has_qk_norm", facts.has_qk_norm), ("attention_bias", facts.attention_bias))
        if value is None
    )
    plan = select_paths(facts).plan
    status = "supported_pending_probe" if pending else "supported"
    return OnboardVerdict(backend=backend, status=status, plan=plan, pending_probe=pending)


def backend_verdicts(facts: ModelFacts, backends: tuple[str, ...] = ONBOARD_BACKENDS) -> dict[str, OnboardVerdict]:
    """The capability-table verdict for every backend the loop publishes."""
    return {backend: _verdict_for_backend(facts, backend) for backend in backends}


def staging_tier_gap(facts: ModelFacts, backend: str) -> int | None:
    """When the ONLY reason `backend` refuses these facts is the staging tier,
    the exact tier value that would flip the model to supported; otherwise None.

    This is the adaptive hook: a pure-staging refusal names the build-time
    specialization that closes the gap (as STAGE_8192 did for Llama-3.2), so the
    loop can add the tier, rebuild, and re-verdict without any per-model branch."""
    refusals = refusals_for_facts(facts, backend=backend)
    if len(refusals) == 1 and refusals[0].fact == "stage_needed":
        return stage_needed(facts)
    return None


def backend_staging_ceiling(backend: str) -> int:
    """The largest staging tier `backend` can build (its shared-memory budget).
    A pure-staging gap above this is a hardware limit, not a missing build."""
    return _BACKEND_STAGING_CEILING.get(backend, 0)


def _facts_brief(facts: ModelFacts) -> str:
    parts = [
        f"d{facts.hidden_size}",
        f"L{facts.num_hidden_layers}",
        f"hq{facts.num_attention_heads}",
        f"hkv{facts.num_key_value_heads}",
        f"dh{facts.head_dim}",
        f"dff{facts.intermediate_size}",
        f"rope={facts.rope_class}",
        f"tie={facts.tie_word_embeddings}",
        f"qkn={facts.has_qk_norm}",
        f"bias={facts.attention_bias}",
        f"act={facts.activation}",
    ]
    if facts.sliding_window is not None:
        parts.append(f"win={facts.sliding_window}")
    parts.append(f"family={facts.family}")
    return " ".join(parts)


def emit_support_row(model: str, facts: ModelFacts, verdicts: dict[str, OnboardVerdict]) -> str:
    """One markdown row of the support matrix: model, facts, per-backend verdict."""
    verdict_cells = []
    for backend in sorted(verdicts):
        v = verdicts[backend]
        if v.supported:
            cell = f"{backend}: supported" + (f" ({v.plan})" if v.plan else "")
        else:
            first = v.refusals[0]
            more = f" (+{len(v.refusals) - 1})" if len(v.refusals) > 1 else ""
            cell = f"{backend}: refused — {first.fact}={first.value}{more}"
        verdict_cells.append(cell)
    return f"| {model} | {_facts_brief(facts)} | {' · '.join(verdict_cells)} |"


def emit_ledger(
    model: str,
    facts: ModelFacts,
    verdicts: dict[str, OnboardVerdict],
    gates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The JSON ledger line: machine-readable onboarding record for this model."""
    return {
        "model": model,
        "facts": facts.as_dict(),
        "stage_needed": stage_needed(facts),
        "verdicts": {
            backend: {
                "status": v.status,
                "plan": v.plan,
                "refusals": [
                    {"fact": r.fact, "value": r.value, "supported": r.supported}
                    for r in v.refusals
                ],
            }
            for backend, v in verdicts.items()
        },
        "gates": gates or {},
    }

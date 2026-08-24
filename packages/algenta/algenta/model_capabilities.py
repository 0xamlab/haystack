"""The model support system, as declared facts — never family names.

Every kernel path in this engine either supports a range of architecture FACTS
(head_dim values, qk_norm 0/1, rope class, activation, bias, tie, GQA ratio,
alignment) or it does not. This module is the single declared source of that
truth:

* `ModelFacts` — the normalized fact manifest for one checkpoint, extracted
  from its own config declaration plus (when the weights are present) the
  tensors-are-the-truth probes. No fact here is ever guessed from a model NAME
  or a family string: two checkpoints with identical facts take identical paths.
* `KERNEL_PATH_CAPABILITIES` — the capability table: every kernel path that a
  session can dispatch, with the exact fact ranges it was built and validated
  for. Where a path genuinely supports only certain fact values (the steel
  attention-forge prefill kernels are structural d_head=128 / d_head=64; the
  d64 kernels implement the no-QK-norm pairing only), that restriction is DATA
  here, not prose in a branch.
* `refusals_for_facts` — the typed refusal computation. A checkpoint whose
  facts fall outside the table is refused with the exact fact, its value, and
  the supported range — never silently, never by name.
* `select_paths` — path selection as a PURE function of the facts (plus the
  pipeline availability of the target binary), mirroring the engine's own
  resolution order in `metaldispatch.session_prefill` closest-capability-first.

The engine's Mojo half (`metaldispatch.session_prefill`) enforces the SAME
gates from the SAME facts at session open; this module is the pre-flight
computation the conform CLI and the converter share, so a refusal happens at
the cheapest possible point (the config declaration) instead of after a
multi-gigabyte conversion. The synthetic fact-space battery
(`scripts/algenta_synthetic_battery.py`) is the proof the table is honest:
every fact combination it claims SUPPORTED runs token-identical to an
independent fp64 reference, and every combination it refuses is refused.

Facts the engine does not implement are REFUSED, never ignored. A config that
declares a sliding window, an attention-logit softcap, a non-SiLU activation,
a per-layer layer-type pattern, or a second rope base frequency would otherwise
run with the math silently dropped — fluent output, wrong model. The refusal is
the support boundary, and it is published as such.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

__all__ = [
    "ModelFacts",
    "TypedRefusal",
    "PathAssignment",
    "KERNEL_PATH_CAPABILITIES",
    "STRUCTURAL_FACT_RANGES",
    "BACKEND_FACT_RANGES",
    "STAGING_TIERS",
    "POWER_OF_TWO_HEAD_DIMS",
    "extract_facts_from_config",
    "refusals_for_facts",
    "unverified_facts",
    "select_paths",
    "stage_needed",
    "verdict_for_checkpoint",
]

# ── the fact ranges the whole engine family shares ───────────────────────────

# Metal threadgroup memory is 32 KiB (probed: M4 Max maxThreadgroupMemoryLength
# = 32768); the staging tier is the decode kernels' shared-memory ceiling in
# Float32 elements, so a Metal tier cannot exceed (32768 - scratch) / 4. The
# shipped tiers are residentk/contract.mojo's ALGENTA_STAGE_* builds: 3072
# (default), 6144 (-D ALGENTA_STAGE_6144), 8192 (-D ALGENTA_STAGE_8192, CUDA
# only -- Llama-3.2-1B/3B d_ff), 18944 (-D ALGENTA_STAGE_18944, the NVIDIA
# 163 KiB opt-in shared budget only). One binary per tier by design — the tier
# is a build-time specialization of `RESIDENT_MAX_D_MODEL`. The backend ranges
# below filter this list (Metal caps at 6144; 8192 fills NVIDIA's budget with
# no scratch room on Apple silicon).
STAGING_TIERS: tuple[int, ...] = (3072, 6144, 8192, 18944)

# head_dim values the parametric kernels cover: a multiple of the 32-wide warp
# (metaldispatch.session_prefill's `d_head % WARP_SIZE` gate), a power of two
# (the rope/sdpa halving-stride reduction), and at most the 256-thread
# threadgroup the one-threadgroup-per-head kernels run
# (residentk.contract.RESIDENT_MAX_HEAD_DIM).
POWER_OF_TWO_HEAD_DIMS: tuple[int, ...] = (32, 64, 128, 256)

# The structural fact ranges every path shares — the same values
# metaldispatch.session_prefill.__init__ and residentk.contract.residentk_
# dims_check enforce from the manifest at session open, declared here so the
# conform CLI can refuse BEFORE conversion instead of after it.
STRUCTURAL_FACT_RANGES: dict[str, str] = {
    "hidden_size": "positive, divisible by 32 (GEMM tile alignment)",
    "intermediate_size": "positive, divisible by 32 (GEMM tile alignment)",
    "num_attention_heads": "positive; an exact multiple of num_key_value_heads (integral GQA ratio)",
    "num_key_value_heads": "positive; divides num_attention_heads",
    "head_dim": "one of {32, 64, 128, 256} (multiple of 32, power of two, <= RESIDENT_MAX_HEAD_DIM=256)",
    "num_attention_heads*head_dim": "divisible by 32 (GEMM tile alignment)",
    "num_hidden_layers": "1..128 (residentk.contract.RESIDENT_MAX_LAYERS)",
    "vocab_size": "1..2097152 (residentk.contract.RESIDENT_MAX_VOCAB)",
    "activation": "silu (the fused SwiGLU FFN is the only FFN the kernels implement)",
    "sliding_window": "none (no kernel applies a window mask; a declared window is refused, never ignored)",
    "attention_logit_softcap": "none (no kernel applies a tanh softcap; refused, never ignored)",
    "final_logit_softcap": "none (refused, never ignored)",
    "layer_types": "none (per-layer local/global patterns are refused, never ignored)",
    "rope_class": "plain (rope_theta only) or llama3-scaled (rope_scaling rope_type='llama3') or explicit per-pair factors (a GGUF rope_freqs.weight)",
    "rope_theta": "a positive number",
    "attention_scale": "1/sqrt(head_dim) (a query_pre_attn_scalar different from head_dim changes the scale and is refused)",
}

# Per-hardware-family fact ranges: the SAME model facts can be supported on one
# backend and not another, because the backends wired different kernel sets.
#   metal — the metaldispatch resident session: no q/k/v projection bias add is
#           wired into any of its descriptor tables (the bias kernel landed for
#           the CUDA lane's five 7B paths, PR #821), and the staging tier
#           cannot exceed the 6144 tier inside Metal's 32 KiB threadgroup budget.
#           Runs the qwen3/llama decoder family only (the gemma3 kernels are a
#           CUDA-lane kernel set).
#   cuda  — the residentk CUDA sessions: q/k/v biases applied in all five 7B
#           paths (qwen2/qwen2.5 convention), staging tiers up to 18944, and
#           the gemma3 CUDA f32/f16 engine lane in addition to qwen3/llama.
BACKEND_FACT_RANGES: dict[str, dict[str, Any]] = {
    "metal": {
        "attention_bias": (0,),
        "staging_tiers": tuple(t for t in STAGING_TIERS if t <= 6144),
        "families": ("qwen3_llama",),
    },
    "cuda": {
        "attention_bias": (0, 1),
        "staging_tiers": STAGING_TIERS,
        "families": ("qwen3_llama", "gemma3"),
    },
}

# The Gemma 3 capability profile (Gemma 3 lane, PR #837): the facts that family
# SUPPORTS, declared so the conform verdict judges gemma3 checkpoints against
# their own engine lane instead of the qwen3/llama hazard gates. Sliding window,
# dual-theta rope, per-layer layer types and gelu_pytorch_tanh are gemma3
# FEATURES, not hazards; softcaps, q/k/v biases and any other activation are
# refused. The gemma3 CUDA session owns its own staging, so no metal staging-tier
# gate applies. head_dim 256 is the shipped gemma3 value (1B/4B/12B/27B).
GEMMA3_FACT_RANGES: dict[str, Any] = {
    "activation": ("gelu_pytorch_tanh",),
    "attention_bias": (0,),
    "rope_class": ("plain", "linear", "explicit_factors"),
    "sliding_window_required": True,
    "note": "CUDA-lane kernel set (f32/f16), correctness-gated on H100; window + local/global layer pattern + dual-theta rope implemented",
}

# ── the capability table: kernel path -> supported fact ranges ───────────────
#
# Each record declares the fact values the path was BUILT AND VALIDATED for —
# the exact gates metaldispatch.session_prefill resolves from at construction
# (`_AF_STRUCTURAL_D_HEAD` = 128, `_AF_STRUCTURAL_D_HEAD_F2` = 64, the qk_norm
# pairings, the pipeline-availability degradation order). A `None` value means
# "unconstrained by this path" (any legal fact value). Selection
# (`select_paths`) is a lookup into this table, closest-capability-first, in
# the engine's own resolution order.

KERNEL_PATH_CAPABILITIES: dict[str, dict[str, Any]] = {
    # -- prefill attention ---------------------------------------------------
    "prefill_attention/steel_grouped_fa_d128": {
        "head_dim": (128,),
        "qk_norm": (0, 1),
        "note": "attention-forge steel grouped-FA; norm-agnostic (the QK-norm lives in the kvprod)",
    },
    "prefill_attention/steel_grouped_fa_d64": {
        "head_dim": (64,),
        "qk_norm": (0,),
        "note": "d64 steel twin; validated pairing is no-QK-norm only",
    },
    "prefill_attention/parametric": {
        "head_dim": POWER_OF_TWO_HEAD_DIMS,
        "qk_norm": (0, 1),
        "note": "_pf_ropewrt + _pf_attn_tiled; any power-of-two d_head <= 256",
    },
    # -- decode attention (split-K flash-decoding partials) -------------------
    "decode_attention/splitk_f4u2": {
        "head_dim": (128,),
        "qk_norm": (0, 1),
        "note": "d_head//4 threads; norm-agnostic (reads packed KV the kvprod wrote)",
    },
    "decode_attention/splitk_f2s4k_kvprod_fused": {
        "head_dim": (64,),
        "qk_norm": (0,),
        "note": "kvprod-FUSED d64 partial; implements the no-QK-norm pairing only",
    },
    "decode_attention/splitk_f2s4": {
        "head_dim": (64,),
        "qk_norm": (0, 1),
        "note": "4-key-staged SIMD-K d64 partial; norm-agnostic (kvprod carries the flag)",
    },
    "decode_attention/splitk_f2": {
        "head_dim": (64,),
        "qk_norm": (0, 1),
        "note": "one-simdgroup d64 partial; norm-agnostic",
    },
    "decode_attention/batched_splitk_f4u2": {
        "head_dim": (128,),
        "qk_norm": (0, 1),
        "note": "batched d128 `_bat` partial at d_head//4 threads",
    },
    "decode_attention/batched_splitk_bf2u2": {
        "head_dim": (64,),
        "qk_norm": (0,),
        "note": "batched d64 partial at 32 threads; d64 pairing mirrors the AF gate",
    },
    "decode_attention/naive_native": {
        "head_dim": POWER_OF_TWO_HEAD_DIMS,
        "qk_norm": (0, 1),
        "note": "single-dispatch native decode attention (below-threshold depths)",
    },
    # -- KV producers ----------------------------------------------------------
    "kvprod/naive_flagged": {
        "head_dim": None,
        "qk_norm": (0, 1),
        "note": "takes the model's own qk_norm flag; both conventions",
    },
    "kvprod/v2": {
        "head_dim": (128,),
        "qk_norm": (1,),
        "note": "the V2 producer pair stays gated to qk_norm=1 + d128",
    },
    "decode_attention/i8kv_v4": {
        "head_dim": (128,),
        "qk_norm": (0, 1),
        "note": "int8-KV mirror decode; lane-x4 one-simdgroup, d128 only",
    },
    # -- GEMM tiers (all four GEMM-shaped roles; alignment-gated only) --------
    "gemm/original": {"head_dim": None, "qk_norm": None, "note": "always resolvable"},
    "gemm/bm64": {"head_dim": None, "qk_norm": None, "note": "qkv_proj role only"},
    "gemm/vecload4": {"head_dim": None, "qk_norm": None, "note": "per-role fallback inside the tier"},
    "gemm/msl_parity": {"head_dim": None, "qk_norm": None, "note": "per-role fallback inside the tier"},
    "gemm/msl_splitk": {"head_dim": None, "qk_norm": None, "note": "M divisible by 256 for the split tiles; d_ff divisible by 384"},
    # -- gemma3 CUDA lane (a distinct kernel set, not the metaldispatch paths) --
    "gemma3/cuda_session": {
        "head_dim": (256,),
        "qk_norm": (1,),
        "family": "gemma3",
        "note": "Gemma 3 CUDA f32/f16 engine (PR #837): sliding window + local/global layer "
        "pattern + dual-theta rope + gelu_pytorch_tanh + norm(1+w) convention; correctness-gated "
        "on H100. A separate kernel set from the qwen3/llama resident paths above.",
    },
}

# ── typed refusals ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TypedRefusal:
    """One exact reason a checkpoint's facts fall outside the capability table.

    `fact` names the fact, `value` is what the checkpoint declared, `supported`
    states the table's range in the same vocabulary the docs publish, and
    `detail` is the sentence a support matrix or an error message carries. A
    refusal is never a guess and never a family name — it is one fact, one
    value, one range."""

    fact: str
    value: Any
    supported: str
    detail: str

    def message(self) -> str:
        return (
            f"unsupported model: {self.fact}={self.value!r} is not supported "
            f"(supported: {self.supported}). {self.detail}"
        )


@dataclass(frozen=True)
class ModelFacts:
    """The normalized fact manifest of one checkpoint.

    Fields are facts, not names: `has_qk_norm`/`attention_bias` are None when
    no weights were probed (a config-only conform run states what the config
    declares and marks the probe facts unverified), 0/1 when the tensors were
    read. `rope_class` is one of "plain", "llama3", "explicit_factors", or the
    raw declared scheme name (which is then refused). `family` is the decoder
    capability family the checkpoint's own `model_type` declares ("qwen3_llama"
    or "gemma3") -- a FACT of the file that selects which profile of the
    capability table judges it: both families are judged by the same lookup,
    against different declared fact ranges."""

    hidden_size: int | None = None
    num_hidden_layers: int | None = None
    num_attention_heads: int | None = None
    num_key_value_heads: int | None = None
    head_dim: int | None = None
    intermediate_size: int | None = None
    vocab_size: int | None = None
    rope_theta: float | None = None
    rms_norm_eps: float | None = None
    rope_class: str = "plain"
    tie_word_embeddings: int = 1
    has_qk_norm: int | None = None
    attention_bias: int | None = None
    activation: str = "silu"
    sliding_window: int | None = None
    layer_types: tuple | None = None
    attention_softcap: float | None = None
    final_logit_softcap: float | None = None
    query_pre_attn_scalar: int | None = None
    partial_rotary_factor: float | None = None
    dual_theta_rope: bool = False
    eos_token_id: Any = None
    probed: bool = False
    family: str = "qwen3_llama"
    notes: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key in (
            "hidden_size",
            "num_hidden_layers",
            "num_attention_heads",
            "num_key_value_heads",
            "head_dim",
            "intermediate_size",
            "vocab_size",
            "rope_theta",
            "rms_norm_eps",
            "rope_class",
            "tie_word_embeddings",
            "has_qk_norm",
            "attention_bias",
            "activation",
            "sliding_window",
            "layer_types",
            "attention_softcap",
            "final_logit_softcap",
            "query_pre_attn_scalar",
            "partial_rotary_factor",
            "dual_theta_rope",
            "eos_token_id",
            "probed",
            "family",
        ):
            out[key] = getattr(self, key)
        return out


def _as_positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


def extract_facts_from_config(config: dict[str, Any]) -> ModelFacts:
    """Normalize a HuggingFace-style config declaration into `ModelFacts`.

    Derives what a family leaves implicit (`head_dim` = hidden_size //
    num_attention_heads when absent — an already-present head_dim is trusted,
    never re-derived, because Qwen3's is NOT that formula) and states what the
    config declares for every fact the capability table keys on. Never raises:
    missing/odd values stay in the facts as their declared value (or None) and
    `refusals_for_facts` is the single place that judges them. The decoder
    FAMILY is a fact of the file's own `model_type` ("gemma3"/"gemma3_text"
    -> the gemma3 profile; anything else the qwen3/llama profile) and selects
    which capability profile judges it."""
    model_type = str(config.get("model_type") or "")
    family = "gemma3" if model_type in ("gemma3", "gemma3_text") else "qwen3_llama"
    # Gemma 3 names the FFN activation `hidden_activation` (shipped value
    # gelu_pytorch_tanh); the qwen3/llama convention is `hidden_act` (silu).
    activation = config.get("hidden_act") or config.get("hidden_activation")
    facts = ModelFacts(
        hidden_size=_as_positive_int(config.get("hidden_size")),
        num_hidden_layers=_as_positive_int(config.get("num_hidden_layers")),
        num_attention_heads=_as_positive_int(config.get("num_attention_heads")),
        num_key_value_heads=_as_positive_int(config.get("num_key_value_heads")),
        head_dim=_as_positive_int(config.get("head_dim")),
        intermediate_size=_as_positive_int(config.get("intermediate_size")),
        vocab_size=_as_positive_int(config.get("vocab_size")),
        rms_norm_eps=config.get("rms_norm_eps"),
        activation=str(activation or ("gelu_pytorch_tanh" if family == "gemma3" else "silu")),
        tie_word_embeddings=1 if config.get("tie_word_embeddings", True) is True else 0,
        eos_token_id=config.get("eos_token_id"),
        family=family,
    )
    # Gemma 3 derives head_dim from the transformers class default (256), not
    # hidden_size // heads; the lifted gemma3_text config already carries an
    # explicit head_dim by validation time, so only the qwen3/llama family
    # uses the implicit derivation here.
    if (
        facts.head_dim is None
        and family == "qwen3_llama"
        and facts.hidden_size
        and facts.num_attention_heads
    ):
        facts = replace(facts, head_dim=facts.hidden_size // facts.num_attention_heads)
    rope_theta = config.get("rope_theta")
    if isinstance(rope_theta, int | float) and not isinstance(rope_theta, bool) and rope_theta > 0:
        facts = replace(facts, rope_theta=float(rope_theta))

    # Rope class: plain, the llama3 parametric scheme, or whatever the config
    # declares (refused downstream unless it is one of those two).
    rope_scaling = config.get("rope_scaling")
    if isinstance(rope_scaling, dict):
        rope_type = rope_scaling.get("rope_type", rope_scaling.get("type"))
        if rope_type is None or str(rope_type).lower() == "none":
            pass
        elif str(rope_type).lower() == "llama3":
            facts = replace(facts, rope_class="llama3")
        else:
            facts = replace(facts, rope_class=str(rope_type))

    # A second rope base (gemma3-style local/global dual theta) is a fact the
    # engine cannot represent — one rope table, one theta. Declared != ignored.
    for key in ("rope_local_base", "rope_theta_local"):
        local = config.get(key)
        if isinstance(local, int | float) and not isinstance(local, bool):
            if facts.rope_theta is None or float(local) != facts.rope_theta:
                facts = replace(facts, dual_theta_rope=True)

    # Sliding window: the effective window is the smallest positive declared
    # window; a window that covers the whole context is no window at all.
    window_candidates = []
    for key in ("sliding_window", "window_size"):
        value = config.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            window_candidates.append(value)
    if config.get("use_sliding_window") is False:
        window_candidates = []
    if window_candidates:
        window = min(window_candidates)
        max_pos = config.get("max_position_embeddings")
        if not (isinstance(max_pos, int) and not isinstance(max_pos, bool) and window >= max_pos):
            facts = replace(facts, sliding_window=window)

    layer_types = config.get("layer_types")
    if isinstance(layer_types, list) and layer_types:
        facts = replace(facts, layer_types=tuple(str(t) for t in layer_types))

    for key, attr in (
        ("attn_logit_softcapping", "attention_softcap"),
        ("final_logit_softcapping", "final_logit_softcap"),
    ):
        value = config.get(key)
        if isinstance(value, int | float) and not isinstance(value, bool) and value > 0:
            facts = replace(facts, **{attr: float(value)})

    scalar = config.get("query_pre_attn_scalar")
    if isinstance(scalar, int) and not isinstance(scalar, bool) and scalar > 0:
        facts = replace(facts, query_pre_attn_scalar=scalar)

    prf = config.get("partial_rotary_factor")
    if isinstance(prf, int | float) and not isinstance(prf, bool) and 0 < float(prf) < 1.0:
        facts = replace(facts, partial_rotary_factor=float(prf))

    return facts


def stage_needed(facts: ModelFacts) -> int | None:
    """The decode kernels' shared-memory staging requirement, derived from the
    model's own dims exactly as residentk.contract.residentk_dims_check does:
    max(d_model, h_q*d_head, d_ff)."""
    if not facts.hidden_size or not facts.intermediate_size:
        return None
    needed = max(facts.hidden_size, facts.intermediate_size)
    if facts.num_attention_heads and facts.head_dim:
        needed = max(needed, facts.num_attention_heads * facts.head_dim)
    return needed


def refusals_for_facts(
    facts: ModelFacts,
    *,
    backend: str = "metal",
    probed: bool | None = None,
    enforce_backend: bool = True,
) -> list[TypedRefusal]:
    """Every exact reason these facts fall outside the capability table, in a
    stable order (structural facts first, then family facts, then backend
    facts). An empty list means SUPPORTED for that backend.

    `backend` is the hardware family whose kernel set does the running
    ("metal" or "cuda" — see BACKEND_FACT_RANGES). `probed` overrides
    `facts.probed` for the weight-probe fact check (a conform run over a
    config.json alone passes probed=False).

    `enforce_backend=False` judges the structural + family fact ranges but NOT
    the backend-membership / bias / staging ranges. The converter's
    architecture gate uses it, because conversion is backend-agnostic (the
    gemma3 CUDA lane converts through the same door as the Metal path), so a
    family must not be refused there merely because one backend does not run
    it. The conform CLI and any backend-bound caller keep the default
    (`enforce_backend=True`) and get the full verdict."""

    refusals: list[TypedRefusal] = []

    def refuse(fact: str, value: Any, supported: str, detail: str) -> None:
        refusals.append(TypedRefusal(fact, value, supported, detail))

    def check_positive_int(name: str, value: Any) -> bool:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            refuse(name, value, STRUCTURAL_FACT_RANGES.get(name, "a positive int"), "the config must declare it as a positive int")
            return False
        return True

    ok_hidden = check_positive_int("hidden_size", facts.hidden_size)
    ok_layers = check_positive_int("num_hidden_layers", facts.num_hidden_layers)
    ok_hq = check_positive_int("num_attention_heads", facts.num_attention_heads)
    ok_dhead = check_positive_int("head_dim", facts.head_dim)
    ok_dff = check_positive_int("intermediate_size", facts.intermediate_size)
    ok_vocab = check_positive_int("vocab_size", facts.vocab_size)
    ok_hkv = check_positive_int("num_key_value_heads", facts.num_key_value_heads)

    if ok_hq and ok_hkv:
        h_kv = facts.num_key_value_heads
        if facts.num_attention_heads % h_kv != 0:
            refuse(
                "num_attention_heads/num_key_value_heads",
                f"{facts.num_attention_heads}/{h_kv}",
                STRUCTURAL_FACT_RANGES["num_attention_heads"],
                "GQA requires an integral group size",
            )

    if ok_hidden and facts.hidden_size % 32 != 0:
        refuse("hidden_size", facts.hidden_size, STRUCTURAL_FACT_RANGES["hidden_size"], "GEMM tile alignment")
    if ok_dff and facts.intermediate_size % 32 != 0:
        refuse("intermediate_size", facts.intermediate_size, STRUCTURAL_FACT_RANGES["intermediate_size"], "GEMM tile alignment")
    if ok_hq and ok_dhead and (facts.num_attention_heads * facts.head_dim) % 32 != 0:
        refuse(
            "num_attention_heads*head_dim",
            facts.num_attention_heads * facts.head_dim,
            STRUCTURAL_FACT_RANGES["num_attention_heads*head_dim"],
            "GEMM tile alignment",
        )
    if ok_dhead:
        if facts.head_dim % 32 != 0 or facts.head_dim & (facts.head_dim - 1) != 0 or facts.head_dim > 256:
            refuse(
                "head_dim",
                facts.head_dim,
                "{32, 64, 128, 256} — a multiple of 32, a power of two, and <= 256",
                "the rope/sdpa kernels reduce by halving a uniform stride across one warp-multiple, "
                "power-of-two threadgroup; the steel attention-forge paths cover 64 and 128",
            )
    if ok_layers and facts.num_hidden_layers > 128:
        refuse("num_hidden_layers", facts.num_hidden_layers, STRUCTURAL_FACT_RANGES["num_hidden_layers"], "resident session layer ceiling")
    if ok_vocab and facts.vocab_size > (1 << 21):
        refuse("vocab_size", facts.vocab_size, STRUCTURAL_FACT_RANGES["vocab_size"], "resident session vocabulary ceiling")

    # Family dispatch: the qwen3/llama hazard gates and the gemma3 capability
    # profile judge the SAME fact fields against different declared ranges. A
    # sliding window / dual-theta rope / per-layer layer-type pattern is a
    # gemma3 FEATURE (its CUDA lane implements them) but a silent-wrong-math
    # hazard for the qwen3/llama kernel set, which runs one uniform full-
    # attention, single-theta, SiLU stack.
    backend_ranges = BACKEND_FACT_RANGES.get(backend)
    if facts.family == "gemma3":
        g = GEMMA3_FACT_RANGES
        if facts.activation not in g["activation"]:
            refuse(
                "hidden_activation",
                facts.activation,
                "{" + ", ".join(g["activation"]) + "}",
                "the gemma3 lane implements the shipped gelu_pytorch_tanh FFN only; running a "
                "different activation would silently compute a different model",
            )
        if facts.attention_bias is not None and facts.attention_bias not in g["attention_bias"]:
            refuse(
                "attention_bias",
                facts.attention_bias,
                "{0} for the gemma3 lane",
                "gemma3 q/k/v projection biases are not applied; refused, never dropped",
            )
        if facts.attention_softcap is not None or facts.final_logit_softcap is not None:
            refuse(
                "logit_softcapping",
                facts.attention_softcap or facts.final_logit_softcap,
                "none (the gemma3 lane does not implement softcapping)",
                "a softcap is a gemma2 feature the gemma3 kernels do not apply; refused, never ignored",
            )
        if g["sliding_window_required"] and facts.sliding_window is None:
            refuse(
                "sliding_window",
                facts.sliding_window,
                "a positive window (gemma3 local/global attention requires it)",
                "the gemma3 lane runs the windowed local/global pattern; a checkpoint with no "
                "window fact cannot be validated against it",
            )
        if facts.rope_class not in g["rope_class"]:
            refuse(
                "rope_scaling",
                facts.rope_class,
                "{" + ", ".join(g["rope_class"]) + "} for the gemma3 lane",
                "only the shipped gemma3 rope (global linear scaling + local theta) is implemented",
            )
        # Backend gate: the gemma3 kernel set is CUDA-only; the Metal resident
        # path does not run the gemma3 family. Skipped when the caller is the
        # backend-agnostic converter gate (enforce_backend=False).
        if enforce_backend:
            if backend_ranges is None:
                refuse("backend", backend, "/".join(sorted(BACKEND_FACT_RANGES)), "unknown hardware family")
            elif facts.family not in backend_ranges["families"]:
                refuse(
                    "family",
                    facts.family,
                    "{" + ", ".join(backend_ranges["families"]) + f"}} on the {backend} backend",
                    "the gemma3 kernel set is the CUDA lane (f32/f16); the Metal resident dispatch "
                    "path runs the qwen3/llama family only",
                )
        return refusals

    if facts.activation != "silu":
        refuse(
            "hidden_act",
            facts.activation,
            STRUCTURAL_FACT_RANGES["activation"],
            "the fused gate/up + SwiGLU kernel is the only FFN the engine implements; running a "
            "different activation would silently compute a different model",
        )
    if facts.sliding_window is not None:
        refuse(
            "sliding_window",
            facts.sliding_window,
            STRUCTURAL_FACT_RANGES["sliding_window"],
            "no resident kernel applies a window mask; a declared window must be refused, "
            "never ignored (ignoring it runs full attention — fluent, wrong math)",
        )
    if facts.attention_softcap is not None:
        refuse(
            "attn_logit_softcapping",
            facts.attention_softcap,
            STRUCTURAL_FACT_RANGES["attention_logit_softcap"],
            "no kernel applies the tanh softcap; refused, never ignored",
        )
    if facts.final_logit_softcap is not None:
        refuse(
            "final_logit_softcapping",
            facts.final_logit_softcap,
            STRUCTURAL_FACT_RANGES["final_logit_softcap"],
            "refused, never ignored",
        )
    if facts.layer_types is not None:
        refuse(
            "layer_types",
            list(facts.layer_types),
            STRUCTURAL_FACT_RANGES["layer_types"],
            "the engine runs one uniform decoder stack; a per-layer local/global pattern is refused",
        )
    if facts.dual_theta_rope:
        refuse(
            "rope_theta",
            "dual-theta (local + global bases declared)",
            STRUCTURAL_FACT_RANGES["rope_class"],
            "the engine builds ONE rope table from ONE theta; a second base frequency is refused, never ignored",
        )
    rope_classes = ("plain", "llama3", "explicit_factors")
    if facts.rope_class not in rope_classes:
        refuse(
            "rope_scaling",
            facts.rope_class,
            STRUCTURAL_FACT_RANGES["rope_class"],
            "only the llama3 parametric scheme is implemented; running with an unimplemented "
            "scaling silently dropped would leave the rope unscaled",
        )
    if facts.rope_theta is None:
        refuse("rope_theta", facts.rope_theta, STRUCTURAL_FACT_RANGES["rope_theta"], "the rope table needs a positive base")
    if not isinstance(facts.rms_norm_eps, int | float) or isinstance(facts.rms_norm_eps, bool) or facts.rms_norm_eps < 0:
        refuse("rms_norm_eps", facts.rms_norm_eps, "a non-negative number", "the RMSNorm epsilon the kernels add")
    if facts.query_pre_attn_scalar is not None and ok_dhead and facts.query_pre_attn_scalar != facts.head_dim:
        refuse(
            "query_pre_attn_scalar",
            facts.query_pre_attn_scalar,
            STRUCTURAL_FACT_RANGES["attention_scale"],
            "the kernels scale attention by 1/sqrt(head_dim); a different scalar would silently rescale the logits",
        )
    if facts.partial_rotary_factor is not None:
        refuse(
            "partial_rotary_factor",
            facts.partial_rotary_factor,
            "1.0 (rope on the FULL head dimension)",
            "partial rotary embeddings rotate only part of each head; the engine rotates all of it",
        )

    # Backend-specific fact ranges. Skipped for the backend-agnostic converter
    # gate (enforce_backend=False): conversion must not refuse a family over
    # backend membership, bias availability, or staging tier -- those are facts
    # of the backend that RUNS the model, judged by the conform CLI and the
    # decode path.
    if not enforce_backend:
        return refusals
    if backend_ranges is None:
        refuse("backend", backend, "/".join(sorted(BACKEND_FACT_RANGES)), "unknown hardware family")
    else:
        if facts.family not in backend_ranges["families"]:
            refuse(
                "family",
                facts.family,
                "{" + ", ".join(backend_ranges["families"]) + f"}} on the {backend} backend",
                "this decoder family has no kernel set on the backend",
            )
        # The bias fact is judged only when it is KNOWN (probed from the
        # tensors, or declared by a GGUF's own metadata); a config-only verdict
        # leaves it None and reports the missing probe instead, never guessing.
        if facts.attention_bias is not None and facts.attention_bias not in backend_ranges["attention_bias"]:
            bias_range = ", ".join(str(b) for b in backend_ranges["attention_bias"])
            refuse(
                "attention_bias",
                facts.attention_bias,
                f"{{{bias_range}}} on the {backend} dispatch path",
                f"q/k/v projection biases are not applied by the {backend} resident descriptor tables "
                "(the CUDA lane applies them in all five 7B paths); running without them drops the "
                "biases silently — the exact 7B-lane hazard, refused instead",
            )
        needed = stage_needed(facts)
        if needed is not None:
            tiers = backend_ranges["staging_tiers"]
            if not any(needed <= tier for tier in tiers):
                refuse(
                    "stage_needed",
                    needed,
                    f"a staging tier in {{{', '.join(str(t) for t in tiers)}}} elements "
                    f"(max(d_model, h_q*head_dim, d_ff)) on the {backend} family",
                    "the decode kernels stage their largest vector in threadgroup memory; no shipped "
                    "build of this backend tiers the staging high enough for these dims "
                    "(build-time specialization, one binary per tier)",
                )

    return refusals


def unverified_facts(facts: ModelFacts, *, probed: bool | None = None) -> list[str]:
    """The tensor-level facts a config-only verdict could NOT verify (qk_norm
    and bias presence are facts of the WEIGHTS, never of the config -- some
    configs lie about or omit them). Empty once the checkpoint's tensors were
    probed. A conform run over config.json alone reports these as the probe it
    still owes; the verdict is pending, never a guess."""
    was_probed = facts.probed if probed is None else probed
    if was_probed:
        return []
    return [
        name
        for name, value in (("has_qk_norm", facts.has_qk_norm), ("attention_bias", facts.attention_bias))
        if value is None
    ]


# ── path selection: a pure lookup from facts + availability ──────────────────


@dataclass(frozen=True)
class PathAssignment:
    """The resolved kernel-path assignment for a supported fact set. Every
    layer runs the same paths (the facts are uniform across layers — a
    checkpoint whose layers differ is refused via layer_types), so one record
    covers all `num_hidden_layers` layers."""

    prefill_attention: str
    decode_attention: str
    decode_splitk_partial: str | None
    kv_producer: str
    gemm_tiers: tuple
    batched_decode: bool
    plan: str

    def per_layer(self, n_layers: int) -> list[dict[str, Any]]:
        record = {
            "prefill_attention": self.prefill_attention,
            "decode_attention": self.decode_attention,
            "decode_splitk_partial": self.decode_splitk_partial,
            "kv_producer": self.kv_producer,
            "gemm_tiers": list(self.gemm_tiers),
            "batched_decode": self.batched_decode,
        }
        return [{"layer": layer, **record} for layer in range(n_layers)]


def _path_available(name: str, facts: ModelFacts, availability: dict[str, bool]) -> bool:
    if not availability.get(name, True):
        return False
    caps = KERNEL_PATH_CAPABILITIES.get(name)
    if caps is None:
        return False
    for fact_name in ("head_dim", "qk_norm"):
        allowed = caps.get(fact_name)
        if allowed is None:
            continue
        value = facts.head_dim if fact_name == "head_dim" else facts.has_qk_norm
        if value is None:
            # An UNPROBED probe fact (config-only verdict): the path is selectable only when it
            # accepts EVERY legal value of the fact, so a pending probe can never flip the
            # assignment. (head_dim is structural -- never None once the facts passed the table.)
            if fact_name == "qk_norm" and set(allowed) >= {0, 1}:
                continue
            return False
        if value not in allowed:
            return False
    return True


def select_paths(
    facts: ModelFacts,
    *,
    availability: dict[str, bool] | None = None,
) -> PathAssignment:
    """Path selection as a pure function of the facts: closest-capability-
    first, in the engine's own resolution order, degrading along the SAME
    chain metaldispatch.session_prefill degrades (steel prefill -> parametric;
    f2s4k -> f2s4 -> f2 -> none). `availability` states which optional blob
    paths are linked into the target binary; absent entries default to
    available (the table-only view the docs publish).

    The gemma3 family runs its own CUDA-lane kernel set (not the metaldispatch
    resident paths this function otherwise resolves), so its assignment names
    that lane directly."""
    avail = dict(availability or {})

    if facts.family == "gemma3":
        return PathAssignment(
            prefill_attention="gemma3/cuda_session",
            decode_attention="gemma3/cuda_session",
            decode_splitk_partial=None,
            kv_producer="gemma3/cuda_session",
            gemm_tiers=("gemma3/cuda_session",),
            batched_decode=False,
            plan="gemma3_cuda_lane",
        )

    def pick(*candidates: str) -> str | None:
        for name in candidates:
            if _path_available(name, facts, avail):
                return name
        return None

    steel_prefill = pick(
        "prefill_attention/steel_grouped_fa_d128",
        "prefill_attention/steel_grouped_fa_d64",
    )
    prefill_attention = steel_prefill or "prefill_attention/parametric"

    splitk = pick(
        "decode_attention/splitk_f4u2",
        "decode_attention/splitk_f2s4k_kvprod_fused",
        "decode_attention/splitk_f2s4",
        "decode_attention/splitk_f2",
    )
    if steel_prefill is not None:
        plan = "grouped_fa_steel" if splitk else "grouped_fa_steel_naive_decode"
        decode_attention = "decode_attention/splitk_flash_decoding" if splitk else "decode_attention/naive_native"
    else:
        plan = "parametric_native_decode" if splitk else "parametric_off"
        decode_attention = "decode_attention/splitk_flash_decoding" if splitk else "decode_attention/naive_native"

    kv_producer = "kvprod/v2" if _path_available("kvprod/v2", facts, avail) else "kvprod/naive_flagged"

    batched = bool(
        pick(
            "decode_attention/batched_splitk_f4u2",
            "decode_attention/batched_splitk_bf2u2",
        )
    )

    gemm_tiers = tuple(
        name
        for name in ("gemm/msl_parity", "gemm/msl_splitk", "gemm/vecload4", "gemm/bm64", "gemm/original")
        if avail.get(name, True)
    )
    if not gemm_tiers:
        gemm_tiers = ("gemm/original",)

    return PathAssignment(
        prefill_attention=prefill_attention,
        decode_attention=decode_attention,
        decode_splitk_partial=splitk,
        kv_producer=kv_producer,
        gemm_tiers=gemm_tiers,
        batched_decode=batched,
        plan=plan,
    )


def verdict_for_checkpoint(
    checkpoint_dir: str | Path,
    *,
    backend: str = "metal",
) -> dict[str, Any]:
    """The conform computation for one checkpoint directory: facts -> refusals
    -> (when supported) the per-layer path assignment. Pure and side-effect
    free; the caller decides what to print or write. The safetensors probe
    facts (qk_norm / bias tensor presence and the unsupported-tensor sweep)
    are read from the checkpoint's own headers when the weights are present."""
    from algenta.inference import (  # local import: keeps this module dependency-light
        _detect_attention_bias,
        _detect_has_qk_norm,
        _detect_unsupported_tensors,
        _load_checkpoint_index,
        _normalize_config,
    )

    checkpoint_dir = Path(checkpoint_dir)
    config_path = checkpoint_dir / "config.json"
    if not config_path.is_file():
        return {
            "status": "refused",
            "model": str(checkpoint_dir),
            "backend": backend,
            "facts": None,
            "refusals": [
                TypedRefusal(
                    "config.json",
                    "missing",
                    "a HuggingFace checkpoint snapshot (config.json + safetensors)",
                    "the conform CLI reads the checkpoint's own config declaration",
                ).message()
            ],
        }
    config = _normalize_config(json.loads(config_path.read_text(encoding="utf-8")))
    facts = extract_facts_from_config(config)

    index = _load_checkpoint_index(checkpoint_dir)
    probed = index is not False  # None = single shard probed; dict = multi-shard probed
    if probed:
        facts = replace(
            facts,
            has_qk_norm=1 if _detect_has_qk_norm(checkpoint_dir, index if isinstance(index, dict) else None) else 0,
            attention_bias=1 if _detect_attention_bias(checkpoint_dir, index if isinstance(index, dict) else None) else 0,
            probed=True,
        )
        unsupported = _detect_unsupported_tensors(checkpoint_dir, index if isinstance(index, dict) else None)
        if unsupported:
            facts = replace(facts, notes=tuple(unsupported))

    refusal_list = refusals_for_facts(facts, backend=backend)
    for tensor_name in facts.notes:
        refusal_list.append(
            TypedRefusal(
                "unsupported_tensor",
                tensor_name,
                "only the manifest's required tensor set (no mlp/o_proj biases, no extra modules)",
                "the checkpoint carries weights the engine would silently drop; refused, never ignored",
            )
        )
    pending = unverified_facts(facts)

    result: dict[str, Any] = {
        "model": str(checkpoint_dir),
        "backend": backend,
        "facts": facts.as_dict(),
    }
    if refusal_list:
        result["status"] = "refused"
        result["refusals"] = [
            {
                "fact": refusal.fact,
                "value": refusal.value,
                "supported": refusal.supported,
                "detail": refusal.detail,
                "message": refusal.message(),
            }
            for refusal in refusal_list
        ]
        return result
    if pending:
        result["status"] = "supported_pending_probe"
        result["pending_probe"] = pending

    assignment = select_paths(facts)
    n_layers = facts.num_hidden_layers or 0
    result.setdefault("status", "supported")
    result["assignment"] = {
        "plan": assignment.plan,
        "prefill_attention": assignment.prefill_attention,
        "decode_attention": assignment.decode_attention,
        "decode_splitk_partial": assignment.decode_splitk_partial,
        "kv_producer": assignment.kv_producer,
        "gemm_tiers": list(assignment.gemm_tiers),
        "batched_decode": assignment.batched_decode,
        "layers": assignment.per_layer(n_layers),
    }
    result["stage_needed"] = stage_needed(facts)
    return result

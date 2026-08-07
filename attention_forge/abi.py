"""attention_forge.abi -- the Universal Mojo Attention Compiler's declarative ABI (Attention
Compiler Plan v1.0, Phase 0B). Three deliberately separate structures, not one:

  AttentionModelTraits    -- static, per-model. What a checkpoint IS.
  AttentionInvocation     -- runtime, per-call. What a specific dispatch NEEDS.
  AttentionKernelArtifactKey -- selects a PREBUILT artifact. Runtime never compiles a kernel; it
                                 looks one up.

Mixing these into one structure is the mistake this plan explicitly corrected for: static head
dimensions and runtime query counts have no business living in the same object, because the
artifact key that selects a compiled kernel must be a function of the STATIC traits (plus a
handful of tile/backend choices) and must NOT depend on `q_rows`/`pos_base`, which vary every
call and would otherwise force a cache/lookup keyed on values that don't actually change which
binary runs.

TransformerBlockSpec describes the non-attention half of a transformer block (norm, projections,
FFN, residual topology) -- attention_forge's own kernels don't consume it directly yet (that is
Phase 4/5's job), but the model importer produces both from the same source so a caller never
has to re-derive one from the other.

No field here is model-specific by name. Qwen3-0.6B is the first VALUE this ABI is populated
with, never a case this code branches on -- see model_importer.py's own docstring for why that
distinction is enforced mechanically, not just by convention.
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib
import json
from pathlib import Path
from typing import Optional


class HeadMappingClass(str, enum.Enum):
    """How query heads relate to KV heads. Plain MHA and MQA are the two extremes of GQA, not
    separate mechanisms -- but callers (and kernel generators) benefit from naming them, since
    "GQA with group size 1" reads as a typo for MHA and "GQA with group size = h_q" reads as a
    typo for MQA if left unnamed."""

    MHA = "mha"                    # group size 1: every query head owns its own KV head
    UNIFORM_GROUPED = "uniform_grouped"  # GQA: h_q divides evenly by h_kv, fixed group size
    MQA = "mqa"                    # group size = h_q: every query head shares the one KV head
    EXPLICIT_MAP = "explicit_map"  # nonuniform mapping, carried as an explicit table


class AttentionMode(str, enum.Enum):
    CAUSAL = "causal"
    BIDIRECTIONAL = "bidirectional"
    CROSS = "cross"
    SLIDING_WINDOW = "sliding_window"
    PREFIX_CAUSAL = "prefix_causal"
    ARBITRARY_MASK = "arbitrary_mask"


class PositionalTransform(str, enum.Enum):
    NONE = "none"
    ROPE = "rope"
    PARTIAL_ROPE = "partial_rope"
    NEOX_ROPE = "neox_rope"
    YARN_SCALED = "yarn_scaled"


class KVStorageClass(str, enum.Enum):
    CONTIGUOUS = "contiguous"
    PAGED = "paged"
    PACKED = "packed"
    QUANTIZED = "quantized"


class ScaleMode(str, enum.Enum):
    DEFAULT_INV_SQRT_D = "default_inv_sqrt_d"
    EXPLICIT = "explicit"


class NormKind(str, enum.Enum):
    RMSNORM = "rmsnorm"
    LAYERNORM = "layernorm"


class ProjectionLayout(str, enum.Enum):
    FUSED_QKV = "fused_qkv"
    SEPARATE_QKV = "separate_qkv"


class FFNKind(str, enum.Enum):
    SWIGLU = "swiglu"
    GEGLU = "geglu"
    GELU_MLP = "gelu_mlp"
    STANDARD_MLP = "standard_mlp"
    MOE = "moe"


@dataclasses.dataclass(frozen=True)
class AttentionModelTraits:
    """Static per-model facts. Everything here is a property of the CHECKPOINT, never of a
    particular call -- if a field's value could differ between two dispatches against the same
    loaded model, it belongs in AttentionInvocation instead, not here."""

    q_heads: int
    kv_heads: int
    head_mapping_class: HeadMappingClass

    qk_head_dim: int
    value_head_dim: int  # carried independently of qk_head_dim; equality is never assumed

    q_dtype: str
    kv_dtype: str
    output_dtype: str
    accumulator_dtype: str

    attention_mode: AttentionMode
    qk_norm: bool
    alibi: bool
    logit_softcap: Optional[float]
    attention_sinks: bool
    scale_mode: ScaleMode
    explicit_scale: Optional[float] = None

    positional_transform: PositionalTransform = PositionalTransform.ROPE
    rope_theta: Optional[float] = None

    kv_storage_class: KVStorageClass = KVStorageClass.CONTIGUOUS

    def __post_init__(self) -> None:
        if self.head_mapping_class == HeadMappingClass.UNIFORM_GROUPED:
            if self.kv_heads <= 0 or self.q_heads % self.kv_heads != 0:
                raise ValueError(
                    f"uniform_grouped requires q_heads % kv_heads == 0, got "
                    f"q_heads={self.q_heads} kv_heads={self.kv_heads}"
                )
        if self.head_mapping_class == HeadMappingClass.MHA and self.q_heads != self.kv_heads:
            raise ValueError("MHA requires q_heads == kv_heads")
        if self.head_mapping_class == HeadMappingClass.MQA and self.kv_heads != 1:
            raise ValueError("MQA requires kv_heads == 1")
        if self.qk_head_dim <= 0 or self.value_head_dim <= 0:
            raise ValueError("head dims must be positive")
        if self.scale_mode == ScaleMode.EXPLICIT and self.explicit_scale is None:
            raise ValueError("scale_mode=explicit requires explicit_scale")

    @property
    def group_size(self) -> int:
        """Query heads sharing one KV head. 1 for MHA, h_q for MQA."""
        if self.kv_heads <= 0:
            raise ValueError("group_size undefined for kv_heads<=0 (explicit_map)")
        return self.q_heads // self.kv_heads

    def to_json(self) -> dict:
        d = dataclasses.asdict(self)
        for k, v in list(d.items()):
            if isinstance(v, enum.Enum):
                d[k] = v.value
        return d

    @staticmethod
    def from_json(d: dict) -> "AttentionModelTraits":
        d = dict(d)
        d["head_mapping_class"] = HeadMappingClass(d["head_mapping_class"])
        d["attention_mode"] = AttentionMode(d["attention_mode"])
        d["scale_mode"] = ScaleMode(d["scale_mode"])
        d["positional_transform"] = PositionalTransform(d["positional_transform"])
        d["kv_storage_class"] = KVStorageClass(d["kv_storage_class"])
        return AttentionModelTraits(**d)


@dataclasses.dataclass(frozen=True)
class AttentionInvocation:
    """Runtime, per-call. Everything here is allowed to differ between two dispatches against the
    SAME loaded model -- this is deliberately NOT part of any kernel-selection cache key beyond
    the coarse buckets AttentionKernelArtifactKey itself captures (e.g. "small M" vs "large M")."""

    batch_size: int
    q_rows: int
    kv_rows: int
    pos_base: int

    q_stride: Optional[int] = None
    k_stride: Optional[int] = None
    v_stride: Optional[int] = None
    output_stride: Optional[int] = None

    page_table: Optional[object] = None
    explicit_mask: Optional[object] = None
    sequence_lengths: Optional[list] = None

    def __post_init__(self) -> None:
        if self.batch_size <= 0 or self.q_rows <= 0 or self.kv_rows <= 0:
            raise ValueError("batch_size, q_rows, kv_rows must be positive")
        if self.pos_base < 0:
            raise ValueError("pos_base must be >= 0")


@dataclasses.dataclass(frozen=True)
class AttentionKernelArtifactKey:
    """Selects a PREBUILT artifact. Runtime looks this up in a GeneratedKernelManifest; it never
    compiles or generates a kernel from it directly. Every field here must be knowable from
    AttentionModelTraits plus a small, finite set of tile/backend choices -- never from
    AttentionInvocation's own per-call fields, or the manifest lookup would thrash on every call
    with a different q_rows/pos_base.

    apple_gpu_family / kernel_abi_version / forge_toolchain_hash / source_hash exist because an
    exact function name alone cannot prove a cached metallib matches the current layout, ABI,
    device family, toolchain, and fast-math contract -- the exact gap this plan's own revision
    called out before Phase 0B started."""

    model_traits_subset: tuple  # a stable, hashable projection of the traits that matter for codegen
    query_tile: int
    key_tile: int
    h_tile: int
    simd_group_count: int
    is_matrix_path: bool  # False = vector/split-K family (Phase 3), True = matrix (Phase 1/2)
    is_split_k: bool
    math_mode: str  # e.g. "precise_exp" | "fast_exp2"
    kv_layout_version: int

    apple_gpu_family: str
    kernel_abi_version: int
    forge_toolchain_hash: str
    source_hash: str

    def cache_key(self) -> str:
        payload = json.dumps(dataclasses.asdict(self), sort_keys=True).encode()
        return hashlib.sha256(payload).hexdigest()[:16]


@dataclasses.dataclass(frozen=True)
class KVLayoutDescriptor:
    """Canonical attention-native KV layout (Plan v1.0, "The architecture" #6). Distinct from
    KVStorageClass (contiguous/paged/packed/quantized, a coarse storage strategy): this is the
    concrete tile geometry a specific kernel family reads, versioned via `layout_version` so a
    manifest entry can prove which layout its metallib was built to consume."""

    layout_version: int
    key_block_order: str    # e.g. "[kv_head][key_block][d_chunk][key_in_block]"
    value_block_order: str  # e.g. "[kv_head][key_block][key_in_block][d_chunk]"
    key_block_size: int
    dtype: str


@dataclasses.dataclass
class GeneratedKernelManifestEntry:
    """One row of the generated manifest: semantic key -> discovered symbol -> provenance. See
    generate_variants.py's own docstring for why `actual_metal_symbol` is a separate field from
    `requested_name` rather than an assumption that they match."""

    key: AttentionKernelArtifactKey
    requested_name: str
    actual_metal_symbol: Optional[str]
    metallib_sha256: Optional[str]
    source_sha256: str
    toolchain_sha256: str

    def to_json(self) -> dict:
        return {
            "key": dataclasses.asdict(self.key),
            "cache_key": self.key.cache_key(),
            "requested_name": self.requested_name,
            "actual_metal_symbol": self.actual_metal_symbol,
            "metallib_sha256": self.metallib_sha256,
            "source_sha256": self.source_sha256,
            "toolchain_sha256": self.toolchain_sha256,
        }


@dataclasses.dataclass(frozen=True)
class TransformerBlockSpec:
    """The non-attention half of a transformer block. Positional transform is deliberately NOT
    duplicated here -- AttentionModelTraits is its single authority, since RoPE/YaRN etc. are
    properties of how attention consumes Q/K, not of the block's own norm/FFN topology."""

    norm: NormKind
    projection_layout: ProjectionLayout
    ffn: FFNKind
    n_layers: int
    hidden_size: int
    intermediate_size: int
    vocab_size: int
    quantization_format: str = "none"

    def to_json(self) -> dict:
        d = dataclasses.asdict(self)
        d["norm"] = self.norm.value
        d["projection_layout"] = self.projection_layout.value
        d["ffn"] = self.ffn.value
        return d


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

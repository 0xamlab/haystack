"""Live execution core for the flagship Space's LLM Modules tab.

Same proven pattern as the Algenta LLM Modules satellite Space: every number
comes from executing the signed, bundled Mojo runtime (`algenta-runtime-native`,
verified against its signed manifest before first execution). Nothing is
simulated: the only Python-side math here is the explicitly-labeled demo
featurizer that turns text into toy embedding vectors (the runtime's
`embeddings` kernels then do all vector math on them).

The runtime's 22 LLM modules are pure compute kernels — no model weights and
no license token required.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from algenta.mojo_runtime import MojoRuntime

# --------------------------------------------------------------------------
# The 22 LLM modules (catalog metadata — probed live on 2026-09-20)
# --------------------------------------------------------------------------

FAMILIES: dict[str, list[str]] = {
    "tokenization": ["bpe_tokenizer", "text.tokenizer"],
    "retrieval": [
        "embeddings",
        "vector_search",
        "vector_similarity",
        "vector_kernels.ranker",
        "vector_kernels.table",
        "sparse_vector",
        "rerank_eval",
    ],
    "attention": [
        "flash_attention",
        "sparse_attention",
        "transformer_attention",
        "transformer_blocks",
    ],
    "serving": [
        "continuous_batching",
        "generation_loop",
        "inference_engine",
        "inference_cost_latency",
        "kv_cache",
        "paged_kv_cache",
        "speculative_decoding",
    ],
    "generation": ["llm_sampling"],
    "alignment": ["rlhf_dpo"],
}

MODULES_22: list[str] = [m for fam in FAMILIES.values() for m in fam]

PIP_LINE = "pip install algenta algenta-runtime-native  # CPython 3.14, linux x86_64 / macOS arm64"


# --------------------------------------------------------------------------
# Runtime access + per-call tracing
# --------------------------------------------------------------------------


@dataclass
class KernelCall:
    module: str
    function: str
    args: Any
    result: Any
    latency_ms: float
    wall_ms: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "function": self.function,
            "args": self.args,
            "result": self.result,
            "latency_ms": self.latency_ms,
            "wall_ms": self.wall_ms,
        }


_RT: MojoRuntime | None = None
_RT_LOCK = threading.Lock()


def runtime() -> MojoRuntime:
    global _RT
    if _RT is None:
        with _RT_LOCK:
            if _RT is None:
                _RT = MojoRuntime(mode="local", timeout=30.0)
    return _RT


def warm_runtime() -> None:
    """Spawn the bundled worker before the first visitor click."""
    try:
        runtime().execute("text.tokenizer", "word_tokenize", ["warm"])
    except Exception:  # noqa: BLE001 — the UI surfaces the real error per call
        pass


def runtime_module_count() -> int:
    """The full signed-runtime catalog size, computed live (643 on 1.0.5)."""
    return len(runtime().list_modules())


def kcall(trace: list[KernelCall], module: str, function: str, args: Any) -> Any:
    """Execute one kernel call, record it, and return the raw result (raises on failure)."""
    started = time.perf_counter()
    envelope = runtime().execute(module, function, args)
    wall_ms = (time.perf_counter() - started) * 1000.0
    if not envelope.get("success"):
        raise RuntimeError(
            f"{module}.{function} failed: {envelope.get('error') or envelope.get('error_code')}"
        )
    result = envelope["result"]
    trace.append(
        KernelCall(
            module=module,
            function=function,
            args=args,
            result=result,
            latency_ms=float(envelope.get("latency_ms", 0.0)),
            wall_ms=round(wall_ms, 3),
        )
    )
    return result


def trace_summary(trace: list[KernelCall]) -> str:
    total = sum(c.latency_ms for c in trace)
    modules = sorted({c.module for c in trace})
    return (
        f"**{len(trace)} live kernel calls** · total in-kernel {total:.2f} ms · "
        f"modules: {', '.join(f'`{m}`' for m in modules)}"
    )


def snippet_for(module: str, function: str, args: Any) -> str:
    return (
        f"# {PIP_LINE}\n"
        "from algenta import MojoRuntime\n\n"
        'rt = MojoRuntime(mode="local")\n'
        f"result = rt.execute({module!r}, {function!r}, {json.dumps(args)})\n"
        'print(result["result"])       # the kernel\'s return value\n'
        'print(result["latency_ms"])   # in-kernel time, measured by the wrapper\n'
        'print(result["engine_used"])  # "mojo"'
    )


# --------------------------------------------------------------------------
# Demo featurizer (HONESTLY LABELED — this is Python, not a neural embedder)
# --------------------------------------------------------------------------

EMBED_DIM = 64


def _hash_token(token: str) -> np.ndarray:
    """Deterministic signed projection of one token into R^EMBED_DIM (hashing trick).

    Demo featurization only: it lets a visitor rank a seeded mini-KB with the
    runtime's real vector kernels without shipping a neural embedding model.
    """
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    bits = np.frombuffer(digest, dtype=np.uint8)[: EMBED_DIM // 8]
    signs = np.unpackbits(bits)[:EMBED_DIM].astype(np.float64) * 2.0 - 1.0
    return signs


def _embed_tokens(tokens: list[str]) -> list[float]:
    if not tokens:
        return [0.0] * EMBED_DIM
    acc = np.zeros(EMBED_DIM, dtype=np.float64)
    for token in tokens:
        acc += _hash_token(token)
    return (acc / len(tokens)).tolist()


# Seeded mini knowledge base (8 docs, ecosystem facts).
KB_DOCS: list[dict[str, str]] = [
    {
        "id": "mojo-language",
        "text": "Mojo is a systems programming language for AI kernels with Python-like syntax, "
        "compiled to native code for CPUs and GPUs.",
    },
    {
        "id": "flash-attention",
        "text": "Flash attention computes exact attention with an online softmax recurrence, "
        "tiling blocks so the full attention matrix never materializes in memory.",
    },
    {
        "id": "kv-cache",
        "text": "A KV cache stores per-layer key and value tensors for every generated token, "
        "so decoding avoids recomputing attention over the whole prefix.",
    },
    {
        "id": "paged-kv",
        "text": "Paged KV-cache allocators manage the cache in fixed-size blocks like virtual "
        "memory pages, cutting fragmentation in serving systems.",
    },
    {
        "id": "continuous-batching",
        "text": "Continuous batching admits new requests at every decode iteration instead of "
        "waiting for a whole batch to finish, raising GPU utilization.",
    },
    {
        "id": "speculative-decoding",
        "text": "Speculative decoding drafts several tokens with a small model and verifies "
        "them in parallel with the large model, accepting the longest matching prefix.",
    },
    {
        "id": "dpo-alignment",
        "text": "Direct preference optimization trains a policy from chosen and rejected "
        "response pairs with a logistic loss, no separate reward model needed.",
    },
    {
        "id": "vector-search",
        "text": "Vector search indexes embedding vectors and answers nearest-neighbor queries "
        "with approximate indexes such as HNSW and IVF product quantization.",
    },
]

_kb_cache: dict[str, Any] | None = None
_kb_lock = threading.Lock()


def _kb_vectors(trace: list[KernelCall]) -> list[list[float]]:
    """Tokenize each KB doc with the runtime tokenizer and featurize it (demo embedder)."""
    global _kb_cache
    if _kb_cache is not None:
        return _kb_cache["vectors"]
    with _kb_lock:
        if _kb_cache is not None:
            return _kb_cache["vectors"]
        vectors: list[list[float]] = []
        doc_tokens: list[list[str]] = []
        for doc in KB_DOCS:
            tokens = kcall(trace, "text.tokenizer", "word_tokenize", [doc["text"]])
            tokens = [t for t in tokens if t.isalpha()]
            doc_tokens.append(tokens)
            vectors.append(_embed_tokens(tokens))
        _kb_cache = {"vectors": vectors, "tokens": doc_tokens}
        return vectors


# --------------------------------------------------------------------------
# Demo 1 — tokenize (text.tokenizer + bpe_tokenizer metrics)
# --------------------------------------------------------------------------


def demo_tokenize(text: str) -> dict[str, Any]:
    trace: list[KernelCall] = []
    words = kcall(trace, "text.tokenizer", "word_tokenize", [text])
    sentences = kcall(trace, "text.tokenizer", "sentence_tokenize", [text])
    freq = kcall(trace, "text.tokenizer", "token_frequency", [words])
    vocab = kcall(trace, "text.tokenizer", "vocabulary_size", [words])
    kept = kcall(trace, "text.tokenizer", "remove_stopwords", [words])
    bigrams = kcall(trace, "text.tokenizer", "word_ngrams", [words, 2])
    n_chars = float(len(text))
    n_tokens = float(len(words))
    compression = kcall(
        trace, "bpe_tokenizer", "tokenization_compression_ratio", [n_chars, n_tokens]
    )
    fertility = kcall(
        trace, "bpe_tokenizer", "vocab_fertility", [n_tokens, float(max(len(kept), 1))]
    )
    return {
        "trace": trace,
        "tokens": words,
        "sentences": sentences,
        "frequency": freq,
        "vocab_size": vocab,
        "content_tokens": kept,
        "bigrams": bigrams,
        "stats": {
            "chars": int(n_chars),
            "tokens": int(n_tokens),
            "compression_ratio_chars_per_token": compression,
            "fertility_tokens_per_content_word": fertility,
        },
        "snippet": snippet_for("text.tokenizer", "word_tokenize", [text]),
    }


# --------------------------------------------------------------------------
# Demo 2 — mini-KB retrieval (text.tokenizer + embeddings + sparse_vector)
# --------------------------------------------------------------------------


def demo_retrieve(query: str, top_k: int = 3) -> dict[str, Any]:
    trace: list[KernelCall] = []
    doc_vectors = _kb_vectors(trace)
    q_tokens = [t for t in kcall(trace, "text.tokenizer", "word_tokenize", [query]) if t.isalpha()]
    q_vec = _embed_tokens(q_tokens)
    q_norm = kcall(trace, "embeddings", "normalize_vector", [q_vec])
    doc_norms = [kcall(trace, "embeddings", "normalize_vector", [v]) for v in doc_vectors]
    scores = [kcall(trace, "embeddings", "cosine_similarity", [q_norm, dv]) for dv in doc_norms]
    top_idx = kcall(trace, "embeddings", "k_nearest_neighbors", [q_norm, doc_norms, int(top_k)])
    ranked = [
        {"rank": r + 1, "doc_id": KB_DOCS[i]["id"], "cosine": scores[i], "text": KB_DOCS[i]["text"]}
        for r, i in enumerate(top_idx)
    ]
    # Cross-check the top-1 pair with the sparse kernels (dense→sparse→sparse cosine).
    q_sparse = kcall(trace, "sparse_vector", "dense_to_sparse", [q_norm])
    d_sparse = kcall(trace, "sparse_vector", "dense_to_sparse", [doc_norms[top_idx[0]]])
    sparse_cosine = kcall(
        trace,
        "sparse_vector",
        "sv_cosine",
        [[int(x) for x in q_sparse[0]], q_sparse[1], [int(x) for x in d_sparse[0]], d_sparse[1]],
    )
    ranked[0]["sparse_cosine_crosscheck"] = sparse_cosine
    return {
        "trace": trace,
        "query_tokens": q_tokens,
        "ranked": ranked,
        "all_scores": {KB_DOCS[i]["id"]: scores[i] for i in range(len(KB_DOCS))},
        "snippet": snippet_for(
            "embeddings", "k_nearest_neighbors", ["<query vector>", "<doc vectors>", int(top_k)]
        ),
    }


# --------------------------------------------------------------------------
# Demo 3 — attention lab (flash/transformer kernels vs naive numpy, live)
# --------------------------------------------------------------------------

ATTN_SEQ = 8
ATTN_DIM = 8
ATTN_SEED = 7


def _naive_attention(q: np.ndarray, k: np.ndarray, v: np.ndarray) -> np.ndarray:
    d = q.shape[1]
    scores = q @ k.T / np.sqrt(d)
    mask = np.triu(np.ones_like(scores, dtype=bool), k=1)
    scores = np.where(mask, -1e9, scores)
    weights = np.exp(scores - scores.max(axis=-1, keepdims=True))
    weights /= weights.sum(axis=-1, keepdims=True)
    return weights @ v


def demo_attention() -> dict[str, Any]:
    trace: list[KernelCall] = []
    rng = np.random.default_rng(ATTN_SEED)
    q = rng.normal(size=(ATTN_SEQ, ATTN_DIM))
    k = rng.normal(size=(ATTN_SEQ, ATTN_DIM))
    v = rng.normal(size=(ATTN_SEQ, ATTN_DIM))

    t0 = time.perf_counter()
    ref = _naive_attention(q, k, v)
    numpy_ms = (time.perf_counter() - t0) * 1000.0

    t0 = time.perf_counter()
    out = np.zeros((ATTN_SEQ, ATTN_DIM), dtype=np.float64)
    n_calls_before = len(trace)
    for i in range(ATTN_SEQ):
        # Pass 1 — flash online-softmax recurrence over the (masked) score row.
        # State inits mirror the flash-attention algorithm (m = -inf, l = 0);
        # every update step below is a real kernel call.
        scores_row: list[float] = []
        run_max = -1e30
        run_sum = 0.0
        for j in range(ATTN_SEQ):
            dot = kcall(trace, "embeddings", "dot_product", [q[i].tolist(), k[j].tolist()])
            raw = kcall(
                trace,
                "transformer_attention",
                "scaled_dot_product_attention",
                [dot, float(ATTN_DIM)],
            )
            mask = kcall(trace, "transformer_attention", "causal_mask_value", [float(i), float(j)])
            score = raw + mask  # mask is additive: 0.0 in-window, -1e9 outside
            scores_row.append(score)
            new_max = kcall(trace, "flash_attention", "flash_block_max", [run_max, score])
            run_sum = kcall(
                trace, "flash_attention", "flash_block_sum_exp", [run_sum, run_max, new_max, score]
            )
            run_max = new_max
        # Pass 2 — stable softmax weights, then weight·V accumulated by vector kernels.
        acc = [0.0] * ATTN_DIM
        for j in range(ATTN_SEQ):
            weight = kcall(
                trace,
                "transformer_attention",
                "attention_softmax_stable",
                [scores_row[j], run_max, run_sum],
            )
            scaled = kcall(trace, "embeddings", "vector_scale", [v[j].tolist(), weight])
            acc = kcall(trace, "embeddings", "vector_add", [acc, scaled])
        out[i] = acc
    # One sparse-attention mask row for module coverage (local window, last query row).
    window_masks = [
        kcall(
            trace,
            "sparse_attention",
            "local_window_mask",
            [float(ATTN_SEQ - 1), float(j), 4.0, 0.0],
        )
        for j in range(ATTN_SEQ)
    ]
    phi = kcall(trace, "sparse_attention", "linear_attention_kernel", [0.75])
    mojo_ms = (time.perf_counter() - t0) * 1000.0

    parity = float(np.max(np.abs(out - ref)))
    return {
        "trace": trace,
        "kernel_calls": len(trace) - n_calls_before,
        "numpy_ms": round(numpy_ms, 3),
        "mojo_ms": round(mojo_ms, 1),
        "parity_max_abs_diff": parity,
        "match": bool(parity < 1e-9),
        "shape": f"{ATTN_SEQ} tokens × {ATTN_DIM} dims, causal, seed {ATTN_SEED}",
        "out_row_last": out[-1].round(6).tolist(),
        "ref_row_last": ref[-1].round(6).tolist(),
        "window_masks_row_last": window_masks,
        "linear_attention_phi_0.75": phi,
        "snippet": snippet_for(
            "flash_attention", "flash_block_sum_exp", ["sum", "old_max", "new_max", "score"]
        ),
    }

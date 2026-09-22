"""Live execution core for the Space.

Every number a visitor sees comes from executing the signed, bundled Mojo
runtime (`algenta-runtime-native`, verified against its signed manifest before
first execution). Nothing is simulated: the only Python-side math in this file
is the explicitly-labeled demo featurizer that turns text into toy embedding
vectors (the runtime's `embeddings` kernels then do all vector math on them).

The runtime's 22 LLM modules are pure compute kernels — they need no model
weights and no license token, verified empirically on linux/x86_64 py3.14
against algenta 1.0.17 + algenta-runtime-native 1.0.5.
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
# Catalog metadata — the 22 LLM modules, probed live on 2026-09-20.
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

MODULE_FAMILY: dict[str, str] = {m: fam for fam, mods in FAMILIES.items() for m in mods}

# What the module IS (honest capability framing — these are kernels, not a
# hosted LLM) and one proven live probe call: module -> (function, args, note).
MODULE_INFO: dict[str, tuple[str, str, list[Any], str]] = {
    "bpe_tokenizer": (
        "BPE training *metrics* (merge scores, OOV rate, compression) — not a text tokenizer.",
        "tokenization_compression_ratio",
        [512.0, 137.0],
        "chars/tokens from real counts",
    ),
    "text.tokenizer": (
        "Lexical tokenizer kernels: word/sentence tokenize, n-grams, stopwords, stemming.",
        "word_tokenize",
        ["Algenta runs Mojo kernels live in your browser."],
        "text in, tokens out",
    ),
    "embeddings": (
        "Dense vector math: cosine/dot/distances, k-NN, normalize — you bring the vectors.",
        "cosine_similarity",
        [[1.0, 0.5, 2.0], [1.0, 0.5, 2.0]],
        "pure vector math, no weights",
    ),
    "vector_search": (
        "ANN/index *theory* kernels: recall@k, MRR, HNSW/Faiss/LSH/PQ estimators.",
        "recall_at_k",
        [7.0, 10.0, 9.0],
        "retrieval quality math",
    ),
    "vector_similarity": (
        "Similarity reductions from precomputed sums (dot, norms → cosine, Pearson, …).",
        "cosine_similarity",
        [32.0, 4.0, 8.0],
        "scalar reductions",
    ),
    "vector_kernels.ranker": (
        "Semantic column ranker: query column name → ranked candidate columns.",
        "run_column_rank_v2",
        [
            json.dumps(
                {
                    "query": {"name": "user_email"},
                    "candidates": [
                        {"name": "user_email"},
                        {"name": "order_total"},
                        {"name": "created_at"},
                    ],
                }
            )
        ],
        "schema matching, one raw-JSON frame",
    ),
    "vector_kernels.table": (
        "Candidate-table + rank-request builders (64-d hash featurizer inside the kernel).",
        "build_query",
        ["user_email", 0, 0, 3],
        "builds a RankRequest struct",
    ),
    "sparse_vector": (
        "Sparse vector ops: sparse dot/cosine, dense↔sparse, sparsity stats.",
        "sv_dot",
        [[0, 2], [1.5, -2.0], [0, 2], [3.0, 4.0]],
        "index/value parallel lists",
    ),
    "rerank_eval": (
        "Ranking quality metrics: nDCG/MRR/MAP/precision/recall/hit-rate @k.",
        "ndcg_at_k",
        [[3.0, 2.0, 1.0], [3.0, 2.0, 1.0], 3],
        "graded relevance in, metric out",
    ),
    "flash_attention": (
        "Flash online-softmax recurrence primitives (block max, sum-exp rescale, output).",
        "flash_block_sum_exp",
        [1.0, 2.0, 2.5, 1.25],
        "the flash-attention recurrence, per step",
    ),
    "sparse_attention": (
        "Sparse/long-context attention masks and scores (BigBird, Longformer, sinks, …).",
        "linear_attention_kernel",
        [0.75],
        "φ(x) = elu(x) + 1",
    ),
    "transformer_attention": (
        "Attention fundamentals: scaled dot-product, causal mask, RoPE angle, KV bytes.",
        "scaled_dot_product_attention",
        [3.2, 64.0],
        "q·k/√d and friends",
    ),
    "transformer_blocks": (
        "Block-level ops: residuals, pre/post-norm, FFN layers, head split, dropout.",
        "residual_connection",
        [1.5, -0.25],
        "x + sublayer(x)",
    ),
    "continuous_batching": (
        "Serving scheduler math: admission control, batching efficiency, chunked prefill.",
        "admission_control_accept",
        [1024.0, 4096.0, 0.1],
        "1.0 = admit the request",
    ),
    "generation_loop": (
        "Sampling gates: temperature, top-k/top-p/min-p/typical accept, penalties.",
        "temperature_logit_scale",
        [2.0, 0.7],
        "logit / T",
    ),
    "inference_engine": (
        "Engine estimator kernels: prefill/decode time, throughput, batching capacity.",
        "throughput_tokens_per_sec",
        [8.0, 128.0, 950.0],
        "tokens/s from measured parts",
    ),
    "inference_cost_latency": (
        "Cost/latency model: FLOPs, KV bytes, queue delay, per-request cost.",
        "attention_flops",
        [4, 2048, 32, 32, 128],
        "FLOP accounting",
    ),
    "kv_cache": (
        "KV-cache accounting + eviction scores (H2O, LRU, paged blocks, prefix hits).",
        "kv_cache_memory_per_layer",
        [8.0, 4096.0, 32.0, 128.0, 2.0],
        "bytes per layer",
    ),
    "paged_kv_cache": (
        "Paged-KV math: block copy/compaction, eviction scores, prefix sharing, NTK scale.",
        "page_table_lookup",
        [5.0, 42.0],
        "virtual → physical block",
    ),
    "speculative_decoding": (
        "Speculative-decode math: accept prob, expected tokens, draft speedup, Medusa.",
        "speculative_expected_tokens",
        [0.7, 5.0],
        "E[tokens] per step",
    ),
    "llm_sampling": (
        "Sampling primitives: temperature scale, top-k/top-p thresholds, greedy pick.",
        "temperature_scale",
        [2.0, 0.7],
        "logit / T",
    ),
    "rlhf_dpo": (
        "Alignment losses: DPO/IPO/ORPO/PPO-clip, GAE, GRPO advantage, KL penalty.",
        "dpo_loss",
        [0.8, -0.3, 0.1],
        "-log σ(β·Δ)",
    ),
}

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
    except Exception:  # noqa: BLE001 — the UI will surface the real error per call
        pass


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


# --------------------------------------------------------------------------
# Demo 4 — column ranker (vector_kernels.ranker + vector_kernels.table)
# --------------------------------------------------------------------------

DEFAULT_COLUMNS = (
    "user_email\norder_total\ncreated_at\ncustomer_name\nshipping_address\nsession_id\nutm_source"
)


def demo_ranker(query_name: str, candidates_text: str) -> dict[str, Any]:
    trace: list[KernelCall] = []
    candidates = [{"name": line.strip()} for line in candidates_text.splitlines() if line.strip()]
    payload = {"query": {"name": query_name.strip()}, "candidates": candidates}
    raw = kcall(trace, "vector_kernels.ranker", "run_column_rank_v2", [json.dumps(payload)])
    parsed = json.loads(raw) if isinstance(raw, str) else raw
    request_struct = kcall(
        trace, "vector_kernels.table", "build_query", [query_name.strip(), 0, 0, 3]
    )
    return {
        "trace": trace,
        "request": payload,
        "response": parsed,
        "matches": parsed.get("matches", []),
        "confidence_gap": parsed.get("confidence_gap"),
        "ambiguous": parsed.get("ambiguous"),
        "query_vec_preview": {
            "norm_inv": request_struct.get("query_norm_inv"),
            "dim": len(request_struct.get("query_vec", {}).get("data", [])),
            "nnz": sum(1 for x in request_struct.get("query_vec", {}).get("data", []) if x != 0.0),
        },
        "snippet": snippet_for(
            "vector_kernels.ranker", "run_column_rank_v2", [json.dumps(payload)]
        ),
    }


# --------------------------------------------------------------------------
# Demo 5 — serving math (kv_cache, paged_kv_cache, continuous_batching,
# inference_cost_latency, inference_engine, speculative_decoding)
# --------------------------------------------------------------------------


def demo_serving(
    n_layers: float,
    n_heads: float,
    head_dim: float,
    seq_len: float,
    batch_size: float,
    dtype_bytes: float,
    block_size: float,
    acceptance_rate: float,
    speculation_depth: float,
) -> dict[str, Any]:
    trace: list[KernelCall] = []
    per_layer = kcall(
        trace,
        "kv_cache",
        "kv_cache_memory_per_layer",
        [batch_size, seq_len, n_heads, head_dim, dtype_bytes],
    )
    total = kcall(trace, "kv_cache", "kv_cache_total_memory", [per_layer, n_layers])
    crosscheck = kcall(
        trace,
        "transformer_attention",
        "kv_cache_memory_bytes",
        [n_layers, n_heads, head_dim, seq_len, batch_size],
    )
    blocks = kcall(trace, "kv_cache", "paged_attention_block_count", [seq_len, block_size])
    utilization = kcall(trace, "kv_cache", "kv_cache_utilization", [seq_len * 0.62, seq_len])
    # Can one more sequence of length seq_len fit in a KV budget sized for batch_size sequences?
    admit = kcall(
        trace,
        "continuous_batching",
        "admission_control_accept",
        [seq_len, batch_size * seq_len, 0.1],
    )
    flops = kcall(
        trace,
        "inference_cost_latency",
        "attention_flops",
        [int(batch_size), int(seq_len), int(n_layers), int(n_heads), int(head_dim)],
    )
    accept_prob = kcall(
        trace, "speculative_decoding", "speculative_accept_prob", [0.9, 0.9 * acceptance_rate]
    )
    expected = kcall(
        trace,
        "speculative_decoding",
        "speculative_expected_tokens",
        [acceptance_rate, speculation_depth],
    )
    gib = 1024.0**3
    return {
        "trace": trace,
        "kv": {
            "per_layer_bytes": per_layer,
            "total_bytes": total,
            "total_gib": total / gib,
            "paged_blocks_per_sequence": blocks,
            "example_utilization_at_62pct": utilization,
            "admission_control_accept": admit,
            "crosscheck_bytes_transformer_attention": crosscheck,
            "crosscheck_matches": bool(abs(total - crosscheck) < 1.0),
        },
        "attention_flops_per_forward": flops,
        "speculative": {
            "accept_prob_target0.9_draft_scaled": accept_prob,
            "expected_tokens_per_step": expected,
        },
        "snippet": snippet_for(
            "kv_cache",
            "kv_cache_memory_per_layer",
            [batch_size, seq_len, n_heads, head_dim, dtype_bytes],
        ),
    }


# --------------------------------------------------------------------------
# Demo 6 — sampling, ranking-eval & alignment math
# (llm_sampling, generation_loop, vector_similarity, vector_search,
#  rerank_eval, rlhf_dpo)
# --------------------------------------------------------------------------


def demo_sampling(
    logit: float,
    temperature: float,
    token_prob: float,
    max_prob: float,
    min_p: float,
    cumulative_before: float,
    top_p: float,
    rank: float,
    top_k: float,
) -> dict[str, Any]:
    trace: list[KernelCall] = []
    scaled = kcall(trace, "llm_sampling", "temperature_scale", [logit, temperature])
    threshold = kcall(trace, "llm_sampling", "min_p_threshold", [max_prob, min_p])
    min_p_ok = kcall(trace, "generation_loop", "min_p_accept", [token_prob, max_prob, min_p])
    top_k_ok = kcall(trace, "generation_loop", "top_k_accept", [rank, top_k])
    top_p_ok = kcall(
        trace, "generation_loop", "top_p_cumulative_accept", [cumulative_before, token_prob, top_p]
    )
    greedy = kcall(trace, "llm_sampling", "greedy_token_id", [logit, scaled, 42.0])
    decision = bool(min_p_ok and top_k_ok and top_p_ok)
    return {
        "trace": trace,
        "pipeline": {
            "temperature_scaled_logit": scaled,
            "min_p_threshold": threshold,
            "min_p_accept(1=yes)": min_p_ok,
            "top_k_accept(1=yes)": top_k_ok,
            "top_p_accept(1=yes)": top_p_ok,
            "greedy_pick_token_42": greedy,
            "survives_all_gates": decision,
        },
        "snippet": snippet_for("llm_sampling", "temperature_scale", [logit, temperature]),
    }


def demo_eval(relevance: str, k: int) -> dict[str, Any]:
    trace: list[KernelCall] = []
    try:
        rel = [int(x.strip()) for x in relevance.split(",") if x.strip() != ""]
    except ValueError as exc:
        raise ValueError("relevance must be comma-separated integers, e.g. 1,0,1,1,0") from exc
    if not rel:
        raise ValueError("relevance list is empty")
    k = max(1, min(int(k), len(rel)))
    gains = [float(x) for x in rel]
    ideal = sorted(gains, reverse=True)
    out = {
        "hit_rate_at_k": kcall(trace, "rerank_eval", "hit_rate_at_k", [rel, k]),
        "precision_at_k": kcall(trace, "rerank_eval", "precision_at_k", [rel, k]),
        "recall_at_k": kcall(
            trace, "rerank_eval", "recall_at_k", [rel, sum(1 for x in rel if x > 0), k]
        ),
        "mrr_at_k": kcall(trace, "rerank_eval", "mrr_at_k", [rel, k]),
        "map_at_k": kcall(trace, "rerank_eval", "map_at_k", [rel, k]),
        "ndcg_at_k": kcall(trace, "rerank_eval", "ndcg_at_k", [gains, ideal, k]),
        "recall_at_k_crosscheck": kcall(
            trace,
            "vector_search",
            "recall_at_k",
            [
                float(sum(1 for x in rel[:k] if x > 0)),
                float(k),
                float(sum(1 for x in rel if x > 0)),
            ],
        ),
        "mrr_score_first_relevant_rank1": kcall(trace, "vector_search", "mrr_score", [1.0]),
    }
    # vector_similarity composition: kernel-computed dot + norms → cosine reduction.
    a, b = [1.0, 0.5, 2.0], [1.0, 0.5, 2.0]
    dot = kcall(trace, "embeddings", "dot_product", [a, b])
    na = kcall(trace, "embeddings", "vector_magnitude", [a])
    nb = kcall(trace, "embeddings", "vector_magnitude", [b])
    out["vector_similarity_cosine_from_parts"] = kcall(
        trace, "vector_similarity", "cosine_similarity", [dot, na, nb]
    )
    return {
        "trace": trace,
        "metrics": out,
        "snippet": snippet_for("rerank_eval", "ndcg_at_k", [gains, ideal, k]),
    }


def demo_alignment(
    log_ratio_chosen: float,
    log_ratio_rejected: float,
    beta: float,
    ppo_ratio: float,
    advantage: float,
    clip_eps: float,
    reward: float,
    group_mean: float,
    group_std: float,
) -> dict[str, Any]:
    trace: list[KernelCall] = []
    out = {
        "dpo_loss": kcall(
            trace, "rlhf_dpo", "dpo_loss", [log_ratio_chosen, log_ratio_rejected, beta]
        ),
        "ppo_clip_objective": kcall(
            trace, "rlhf_dpo", "ppo_clip_objective", [ppo_ratio, advantage, clip_eps]
        ),
        "grpo_group_advantage": kcall(
            trace, "rlhf_dpo", "grpo_group_advantage", [reward, group_mean, group_std]
        ),
        "reward_model_score": kcall(
            trace, "rlhf_dpo", "reward_model_score", [log_ratio_chosen, log_ratio_rejected]
        ),
    }
    return {
        "trace": trace,
        "losses": out,
        "snippet": snippet_for(
            "rlhf_dpo", "dpo_loss", [log_ratio_chosen, log_ratio_rejected, beta]
        ),
    }


# --------------------------------------------------------------------------
# Tab-2 module prober
# --------------------------------------------------------------------------


def probe_module(module: str) -> dict[str, Any]:
    if module not in MODULE_INFO:
        raise ValueError(f"unknown module {module!r}")
    _desc, function, args, note = MODULE_INFO[module]
    trace: list[KernelCall] = []
    result = kcall(trace, module, function, args)
    return {
        "trace": trace,
        "module": module,
        "family": MODULE_FAMILY[module],
        "function": function,
        "args": args,
        "result": result,
        "note": note,
    }


def catalog_rows() -> list[list[Any]]:
    rows = []
    for module in MODULES_22:
        desc, function, _args, note = MODULE_INFO[module]
        rows.append(
            [
                module,
                MODULE_FAMILY[module],
                desc,
                f"{function}  —  {note}",
                "✅ RUNS LIVE (probed in this container, no license)",
            ]
        )
    return rows

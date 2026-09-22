"""Algenta LLM Modules — Live.

A Hugging Face Space (Docker SDK, python:3.14) where every tab executes real
Mojo kernels from the signed `algenta-runtime-native` wheel in the visitor's
browser session. No API key, no weights, no simulations — the runtime's 22 LLM
modules are pure compute kernels, and each demo shows its live request /
response JSON, in-kernel latency, and the exact wrapper call to reproduce it.
"""

from __future__ import annotations

import json
import threading

import gradio as gr
from design import FORCE_DARK_JS, THEME
from shell import SHELL_CSS, render_footer, render_header
from space_core import (
    DEFAULT_COLUMNS,
    MODULES_22,
    catalog_rows,
    demo_alignment,
    demo_attention,
    demo_eval,
    demo_ranker,
    demo_retrieve,
    demo_sampling,
    demo_serving,
    demo_tokenize,
    probe_module,
    trace_summary,
    warm_runtime,
)

# Spawn the bundled worker before the first visitor click (first call pays spawn).
threading.Thread(target=warm_runtime, daemon=True).start()


def _json(data) -> str:
    return json.dumps(data, indent=2, default=str)


def _fail(exc: Exception) -> dict:
    """A failed demo is shown as a visible error — never a canned fallback."""
    return {"error": f"{type(exc).__name__}: {exc}"}


# --------------------------------------------------------------------------
# Handlers (thin UI adapters over space_core demos)
# --------------------------------------------------------------------------


def on_tokenize(text: str):
    try:
        r = demo_tokenize(text)
    except Exception as exc:  # noqa: BLE001
        return _json(_fail(exc)), "failed", "", ""
    stats = r["stats"] | {
        "vocab_size_unique_tokens": r["vocab_size"],
        "sentences": len(r["sentences"]),
        "content_tokens_after_stopwords": len(r["content_tokens"]),
    }
    display = {
        "tokens": r["tokens"],
        "sentences": r["sentences"],
        "token_frequency": r["frequency"],
        "word_bigrams": r["bigrams"],
        "bpe_tokenizer_metrics_from_real_counts": stats,
    }
    return (
        _json(display),
        trace_summary(r["trace"]),
        _json([c.as_dict() for c in r["trace"]]),
        r["snippet"],
    )


def on_retrieve(query: str):
    try:
        r = demo_retrieve(query)
    except Exception as exc:  # noqa: BLE001
        return [], _json(_fail(exc)), "failed", "", ""
    rows = [
        [
            d["rank"],
            d["doc_id"],
            round(d["cosine"], 6),
            d.get("sparse_cosine_crosscheck", ""),
            d["text"],
        ]
        for d in r["ranked"]
    ]
    meta = trace_summary(r["trace"]) + (
        " · demo featurizer: deterministic 64-d hash embedding in Python "
        "(**not a neural model**); every vector op above ran in Mojo"
    )
    return (
        rows,
        _json({"query_tokens": r["query_tokens"], "all_cosine_scores": r["all_scores"]}),
        meta,
        _json([c.as_dict() for c in r["trace"]]),
        r["snippet"],
    )


def on_attention():
    try:
        r = demo_attention()
    except Exception as exc:  # noqa: BLE001
        return _json(_fail(exc)), "failed", "", ""
    verdict = "✅ outputs match" if r["match"] else "❌ MISMATCH"
    summary = {
        "shape": r["shape"],
        "live_kernel_calls_this_run": r["kernel_calls"],
        "mojo_path_wall_ms": r["mojo_ms"],
        "numpy_reference_wall_ms": r["numpy_ms"],
        "parity_max_abs_diff": r["parity_max_abs_diff"],
        "verdict": verdict,
        "mojo_output_last_row": r["out_row_last"],
        "numpy_output_last_row": r["ref_row_last"],
        "sparse_attention_local_window_masks_last_row": r["window_masks_row_last"],
        "sparse_attention_linear_kernel_phi(0.75)": r["linear_attention_phi_0.75"],
    }
    meta = trace_summary(r["trace"]) + (
        " · honesty note: the Mojo path makes one kernel call per recurrence step "
        "(~0.3 ms of Python→worker transport each), so at this toy shape numpy "
        "wins on wall-time — this tab proves **exact live execution and parity**, "
        "not throughput. Head-to-head racing lives in ⚡ Speed Arena."
    )
    return (
        _json(summary),
        meta,
        _json(
            [c.as_dict() for c in r["trace"]][:24]
            + [{"…": f"{r['kernel_calls'] - 24} more calls omitted"}]
        ),
        r["snippet"],
    )


def on_ranker(query_name: str, candidates: str):
    try:
        r = demo_ranker(query_name, candidates)
    except Exception as exc:  # noqa: BLE001
        return [], _json(_fail(exc)), "failed", "", ""
    rows = [
        [
            m["column"],
            round(m["score"], 4),
            round(m["name_sim"], 4),
            round(m["token_sim"], 4),
            round(m["type_boost"], 4),
            round(m["prior_boost"], 4),
        ]
        for m in r["matches"]
    ]
    extra = {
        "confidence_gap": r["confidence_gap"],
        "ambiguous": r["ambiguous"],
        "query_vector_built_by_kernel": r["query_vec_preview"],
        "raw_response": r["response"],
    }
    return (
        rows,
        _json(extra),
        trace_summary(r["trace"]),
        _json([c.as_dict() for c in r["trace"]]),
        r["snippet"],
    )


def on_serving(layers, heads, head_dim, seq_len, batch, dtype_bytes, block_size, acc, depth):
    try:
        r = demo_serving(
            layers, heads, head_dim, seq_len, batch, dtype_bytes, block_size, acc, depth
        )
    except Exception as exc:  # noqa: BLE001
        return _json(_fail(exc)), "failed", "", ""
    display = {
        "kv_cache": r["kv"],
        "attention_flops_per_forward_pass": r["attention_flops_per_forward"],
        "speculative_decoding": r["speculative"],
        "note": "crosscheck uses transformer_attention.kv_cache_memory_bytes (fp16) — matches at dtype_bytes=2",
    }
    return (
        _json(display),
        trace_summary(r["trace"]),
        _json([c.as_dict() for c in r["trace"]]),
        r["snippet"],
    )


def on_sampling(logit, temp, prob, max_prob, min_p, cum, top_p, rank, top_k):
    try:
        r = demo_sampling(logit, temp, prob, max_prob, min_p, cum, top_p, rank, top_k)
    except Exception as exc:  # noqa: BLE001
        return _json(_fail(exc)), "failed", "", ""
    return (
        _json(r["pipeline"]),
        trace_summary(r["trace"]),
        _json([c.as_dict() for c in r["trace"]]),
        r["snippet"],
    )


def on_eval(relevance: str, k: int):
    try:
        r = demo_eval(relevance, k)
    except Exception as exc:  # noqa: BLE001
        return _json(_fail(exc)), "failed", "", ""
    return (
        _json(r["metrics"]),
        trace_summary(r["trace"]),
        _json([c.as_dict() for c in r["trace"]]),
        r["snippet"],
    )


def on_alignment(lrc, lrr, beta, ratio, adv, eps, rew, mean, std):
    try:
        r = demo_alignment(lrc, lrr, beta, ratio, adv, eps, rew, mean, std)
    except Exception as exc:  # noqa: BLE001
        return _json(_fail(exc)), "failed", "", ""
    return (
        _json(r["losses"]),
        trace_summary(r["trace"]),
        _json([c.as_dict() for c in r["trace"]]),
        r["snippet"],
    )


def on_probe(module: str):
    try:
        r = probe_module(module)
    except Exception as exc:  # noqa: BLE001
        return _json(_fail(exc)), "failed"
    out = {
        "module": r["module"],
        "family": r["family"],
        "probe": f"{r['function']}  —  {r['note']}",
        "request_args": r["args"],
        "result": r["result"],
        "envelope": r["trace"][0].as_dict() if r["trace"] else {},
    }
    return _json(out), trace_summary(r["trace"])


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------

# Page chrome is the canonical fleet shell (shell.py): title/tagline are this
# Space's README identity, the badges carry the live/honesty claims the old
# hand-rolled header/footer used to make, and the shell nav/footer replace the
# ad-hoc sister links.
HEADER_HTML = render_header(
    title="Algenta LLM Modules — Live",
    tagline="Real Mojo LLM kernels executing live in your browser",
    badges=[
        (
            "real Mojo kernels from the signed algenta-runtime-native wheel, "
            "executing live — no API key, no simulations",
            "ok",
        ),
        "algenta 1.0.17 · algenta-runtime-native 1.0.5 — signed manifest verified in-process",
        (
            "retrieval demo featurizer: deterministic Python hash-embedder — not a neural model",
            "warn",
        ),
    ],
    active="LLM modules live",
)

INTRO = """
Every tab shows the live request/response JSON, the in-kernel latency measured by the wrapper,
and the exact Python call to reproduce it.

The runtime ships **22 LLM modules** — pure compute kernels for tokenization, retrieval,
attention, serving, generation, and alignment. They need **no model weights and no license**:
what you run here is exactly what `pip install algenta algenta-runtime-native` runs on your
machine (CPython 3.14, linux x86_64 / macOS arm64).
"""

with gr.Blocks(title="Algenta LLM Modules — Live", fill_width=True) as app:
    gr.HTML(HEADER_HTML)
    gr.Markdown(INTRO)

    with gr.Tabs():
        # ------------------------------------------------------------------
        with gr.Tab("Live module runner"):
            with gr.Tabs():
                with gr.Tab("Tokenize"):
                    gr.Markdown(
                        "`text.tokenizer` runs the lexical kernels (word/sentence split, "
                        "frequency, n-grams, stopwords). `bpe_tokenizer` is a BPE **training-metrics** "
                        "module — it contributes the compression/fertility numbers computed from the "
                        "real counts of your text. No vocab file, no learned model."
                    )
                    tok_in = gr.Textbox(
                        label="text",
                        value="Mojo kernels execute live in this Hugging Face Space — no API key, "
                        "no weights, and every millisecond you see is measured.",
                        lines=3,
                    )
                    tok_btn = gr.Button("Tokenize live", variant="primary")
                    tok_out = gr.Code(label="result (live)", language="json")
                    tok_meta = gr.Markdown()
                    with gr.Accordion("live kernel trace", open=False):
                        tok_trace = gr.Code(language="json")
                    with gr.Accordion("this exact call in Python", open=False):
                        tok_snip = gr.Code(language="python")
                    tok_btn.click(
                        on_tokenize,
                        tok_in,
                        [tok_out, tok_meta, tok_trace, tok_snip],
                        api_name="tokenize",
                    )

                with gr.Tab("Mini-KB retrieval"):
                    gr.Markdown(
                        "A seeded 8-doc knowledge base, ranked for your query. Text → vectors uses a "
                        "**deterministic demo hash-embedder in Python (labeled — not a neural model)**; "
                        "every vector op — `embeddings.normalize_vector`, `cosine_similarity`, "
                        "`k_nearest_neighbors`, and the `sparse_vector` top-1 cross-check — is a live "
                        "Mojo kernel call."
                    )
                    ret_in = gr.Textbox(
                        label="query",
                        value="how does flash attention reduce memory during training?",
                    )
                    ret_btn = gr.Button("Retrieve live", variant="primary")
                    ret_rows = gr.Dataframe(
                        label="ranked docs (live)",
                        headers=["rank", "doc", "cosine", "sparse cosine (top-1)", "text"],
                        column_widths=["8%", "18%", "10%", "14%", "50%"],
                        wrap=True,
                    )
                    ret_json = gr.Code(label="query tokens + all scores", language="json")
                    ret_meta = gr.Markdown()
                    with gr.Accordion("live kernel trace", open=False):
                        ret_trace = gr.Code(language="json")
                    with gr.Accordion("this exact call in Python", open=False):
                        ret_snip = gr.Code(language="python")
                    ret_btn.click(
                        on_retrieve,
                        ret_in,
                        [ret_rows, ret_json, ret_meta, ret_trace, ret_snip],
                        api_name="retrieve",
                    )

                with gr.Tab("Attention lab"):
                    gr.Markdown(
                        "Exact causal attention at a toy shape (8×8, fixed seed), computed **twice, both "
                        "live**: naive numpy softmax attention vs the runtime's flash-attention "
                        "recurrence — `embeddings.dot_product` → `scaled_dot_product_attention` → "
                        "`causal_mask_value` → `flash_block_max`/`flash_block_sum_exp` → "
                        "`attention_softmax_stable` → `vector_scale`/`vector_add`, one kernel call per "
                        "step (~520 calls). Parity is checked to 1e-9."
                    )
                    att_btn = gr.Button("Run both paths live", variant="primary")
                    att_out = gr.Code(label="parity report (live)", language="json")
                    att_meta = gr.Markdown()
                    with gr.Accordion("live kernel trace (first 24 calls)", open=False):
                        att_trace = gr.Code(language="json")
                    with gr.Accordion("this exact call in Python", open=False):
                        att_snip = gr.Code(language="python")
                    att_btn.click(
                        on_attention,
                        None,
                        [att_out, att_meta, att_trace, att_snip],
                        api_name="attention",
                    )

                with gr.Tab("Column ranker"):
                    gr.Markdown(
                        "`vector_kernels.ranker.run_column_rank_v2` — the semantic schema-matching "
                        "kernel. Give it a query column name and a candidate list (one per line); it "
                        "returns ranked matches with the full score decomposition, a confidence gap, "
                        "and an ambiguity flag. `vector_kernels.table.build_query` builds the hashed "
                        "RankRequest struct."
                    )
                    with gr.Row():
                        rk_q = gr.Textbox(label="query column name", value="user_email")
                        rk_c = gr.Textbox(
                            label="candidate columns (one per line)", value=DEFAULT_COLUMNS, lines=7
                        )
                    rk_btn = gr.Button("Rank live", variant="primary")
                    rk_rows = gr.Dataframe(
                        label="matches (live)",
                        headers=[
                            "column",
                            "score",
                            "name_sim",
                            "token_sim",
                            "type_boost",
                            "prior_boost",
                        ],
                        wrap=True,
                    )
                    rk_json = gr.Code(label="gap / ambiguity / raw response", language="json")
                    rk_meta = gr.Markdown()
                    with gr.Accordion("live kernel trace", open=False):
                        rk_trace = gr.Code(language="json")
                    with gr.Accordion("this exact call in Python", open=False):
                        rk_snip = gr.Code(language="python")
                    rk_btn.click(
                        on_ranker,
                        [rk_q, rk_c],
                        [rk_rows, rk_json, rk_meta, rk_trace, rk_snip],
                        api_name="ranker",
                    )

                with gr.Tab("Serving math"):
                    gr.Markdown(
                        "The engine's own accounting kernels, live on your shape: `kv_cache` "
                        "(per-layer/total bytes, paged blocks, utilization), `transformer_attention."
                        "kv_cache_memory_bytes` as an fp16 cross-check, `continuous_batching."
                        "admission_control_accept`, `inference_cost_latency.attention_flops`, and the "
                        "`speculative_decoding` accept-prob / expected-tokens pair."
                    )
                    with gr.Row():
                        sv_layers = gr.Slider(1, 80, value=32, step=1, label="layers")
                        sv_heads = gr.Slider(1, 64, value=8, step=1, label="KV heads")
                        sv_dim = gr.Slider(32, 256, value=128, step=32, label="head dim")
                    with gr.Row():
                        sv_seq = gr.Slider(512, 32768, value=4096, step=512, label="seq len")
                        sv_batch = gr.Slider(1, 128, value=8, step=1, label="batch")
                        sv_dtype = gr.Dropdown([1.0, 2.0, 4.0, 8.0], value=2.0, label="dtype bytes")
                    with gr.Row():
                        sv_block = gr.Slider(
                            8, 64, value=16, step=8, label="KV page block size (tokens)"
                        )
                        sv_acc = gr.Slider(
                            0.0, 1.0, value=0.7, step=0.05, label="spec acceptance rate"
                        )
                        sv_depth = gr.Slider(1, 12, value=5, step=1, label="speculation depth")
                    sv_btn = gr.Button("Compute live", variant="primary")
                    sv_out = gr.Code(label="serving math (live)", language="json")
                    sv_meta = gr.Markdown()
                    with gr.Accordion("live kernel trace", open=False):
                        sv_trace = gr.Code(language="json")
                    with gr.Accordion("this exact call in Python", open=False):
                        sv_snip = gr.Code(language="python")
                    sv_btn.click(
                        on_serving,
                        [
                            sv_layers,
                            sv_heads,
                            sv_dim,
                            sv_seq,
                            sv_batch,
                            sv_dtype,
                            sv_block,
                            sv_acc,
                            sv_depth,
                        ],
                        [sv_out, sv_meta, sv_trace, sv_snip],
                        api_name="serving",
                    )

                with gr.Tab("Sampling · eval · alignment"):
                    gr.Markdown(
                        "Three live panels in one: the generation loop's sampling gates "
                        "(`llm_sampling` + `generation_loop`), ranking metrics (`rerank_eval` + "
                        "`vector_search` + a `vector_similarity` composition from kernel-computed "
                        "dot/norms), and alignment losses (`rlhf_dpo`)."
                    )
                    gr.Markdown("**sampling gates** — does the candidate token survive?")
                    with gr.Row():
                        sa_logit = gr.Number(value=2.0, label="raw logit")
                        sa_temp = gr.Slider(0.1, 3.0, value=0.7, label="temperature")
                        sa_prob = gr.Slider(0.0, 1.0, value=0.15, label="token prob")
                        sa_maxp = gr.Slider(0.0, 1.0, value=0.42, label="max prob")
                        sa_minp = gr.Slider(0.0, 0.5, value=0.05, label="min_p")
                    with gr.Row():
                        sa_cum = gr.Slider(
                            0.0, 1.0, value=0.80, label="cumulative prob before token"
                        )
                        sa_topp = gr.Slider(0.0, 1.0, value=0.90, label="top_p")
                        sa_rank = gr.Slider(1, 100, value=3, step=1, label="token rank")
                        sa_topk = gr.Slider(1, 100, value=5, step=1, label="top_k")
                    sa_btn = gr.Button("Apply gates live", variant="primary")
                    sa_out = gr.Code(label="sampling pipeline (live)", language="json")
                    sa_meta = gr.Markdown()
                    with gr.Accordion("live kernel trace", open=False):
                        sa_trace = gr.Code(language="json")
                    with gr.Accordion("this exact call in Python", open=False):
                        sa_snip = gr.Code(language="python")
                    sa_btn.click(
                        on_sampling,
                        [
                            sa_logit,
                            sa_temp,
                            sa_prob,
                            sa_maxp,
                            sa_minp,
                            sa_cum,
                            sa_topp,
                            sa_rank,
                            sa_topk,
                        ],
                        [sa_out, sa_meta, sa_trace, sa_snip],
                        api_name="sampling",
                    )

                    gr.Markdown(
                        "**ranking metrics** — comma-separated relevance (0/1), graded as gains"
                    )
                    with gr.Row():
                        ev_rel = gr.Textbox(value="1,0,1,1,0", label="relevance list")
                        ev_k = gr.Slider(1, 10, value=3, step=1, label="k")
                    ev_btn = gr.Button("Score live", variant="primary")
                    ev_out = gr.Code(label="metrics (live)", language="json")
                    ev_meta = gr.Markdown()
                    with gr.Accordion("live kernel trace", open=False):
                        ev_trace = gr.Code(language="json")
                    with gr.Accordion("this exact call in Python", open=False):
                        ev_snip = gr.Code(language="python")
                    ev_btn.click(
                        on_eval,
                        [ev_rel, ev_k],
                        [ev_out, ev_meta, ev_trace, ev_snip],
                        api_name="eval",
                    )

                    gr.Markdown("**alignment losses** — DPO / PPO-clip / GRPO")
                    with gr.Row():
                        al_lrc = gr.Number(value=0.8, label="log ratio chosen")
                        al_lrr = gr.Number(value=-0.3, label="log ratio rejected")
                        al_beta = gr.Slider(0.01, 1.0, value=0.1, label="β (DPO)")
                    with gr.Row():
                        al_ratio = gr.Number(value=1.2, label="PPO ratio")
                        al_adv = gr.Number(value=1.5, label="advantage")
                        al_eps = gr.Slider(0.05, 0.5, value=0.2, label="clip ε")
                    with gr.Row():
                        al_rew = gr.Number(value=1.2, label="reward")
                        al_mean = gr.Number(value=0.9, label="group mean")
                        al_std = gr.Number(value=0.4, label="group std")
                    al_btn = gr.Button("Compute losses live", variant="primary")
                    al_out = gr.Code(label="losses (live)", language="json")
                    al_meta = gr.Markdown()
                    with gr.Accordion("live kernel trace", open=False):
                        al_trace = gr.Code(language="json")
                    with gr.Accordion("this exact call in Python", open=False):
                        al_snip = gr.Code(language="python")
                    al_btn.click(
                        on_alignment,
                        [
                            al_lrc,
                            al_lrr,
                            al_beta,
                            al_ratio,
                            al_adv,
                            al_eps,
                            al_rew,
                            al_mean,
                            al_std,
                        ],
                        [al_out, al_meta, al_trace, al_snip],
                        api_name="alignment",
                    )

        # ------------------------------------------------------------------
        with gr.Tab("The 22 modules"):
            gr.Markdown(
                "The full LLM surface of the bundled runtime. **Honest status:** every one of the 22 "
                "runs live in this Space's container with no license and no weights — they are pure "
                "compute kernels (math over your inputs), *not* a hosted LLM. Generating text with a "
                "real model is the engine's job (weights + `ALGENTA_LICENSE`); the self-host path is "
                "in the next tab."
            )
            gr.Dataframe(
                value=catalog_rows(),
                headers=["module", "family", "what it is", "proven live probe", "status"],
                column_widths=["18%", "12%", "34%", "22%", "14%"],
                wrap=True,
                interactive=False,
            )
            gr.Markdown("**probe any module live** — runs the exact probe call from the table:")
            with gr.Row():
                cat_dd = gr.Dropdown(MODULES_22, value="text.tokenizer", label="module")
                cat_btn = gr.Button("Execute probe live", variant="primary")
            cat_out = gr.Code(label="probe result (live)", language="json")
            cat_meta = gr.Markdown()
            cat_btn.click(on_probe, cat_dd, [cat_out, cat_meta], api_name="probe")

        # ------------------------------------------------------------------
        with gr.Tab("Use it yourself"):
            gr.Markdown(
                """
## Install (CPython 3.14 · linux x86_64 · macOS arm64)

```bash
pip install algenta algenta-runtime-native
```

```python
from algenta import MojoRuntime

rt = MojoRuntime(mode="local")
print(rt.list_functions("text.tokenizer"))

result = rt.execute("text.tokenizer", "word_tokenize", ["runs on your machine now"])
print(result["result"])       # ['runs', 'on', 'your', 'machine', 'now']
print(result["latency_ms"])   # in-kernel time
print(result["engine_used"])  # 'mojo'
```

The runtime resolves its signed manifest, verifies the artifact hash and platform tag, and
executes in-process (bundled worker over a local socket) — no daemon, no TCP listener, no key.

## From Mojo directly

The [mojo-quickstart](https://github.com/thyn-ai/algenta-sdk/tree/main/examples/mojo-quickstart)
talks to the same signed runtime over its public C ABI / wire protocol using nothing but the
Mojo stdlib — the exact pattern this Space uses from Python.

## Self-host the engine — free under the Community license

The 22 modules here are the compute surface. Serving a real LLM (weights, KV-paged decode,
continuous batching as a service) is the Algenta engine — self-host it free under the Community
license via `pip install algenta-sdk`, or drive it from agents with
[`algenta-mcp`](https://pypi.org/project/algenta-mcp/).

## Sister Spaces

- [Algenta Speed Arena](https://huggingface.co/spaces/thyn-ai/algenta-speed-arena) — Mojo kernels vs incumbents, raced live
- [Algenta for LLM Agents](https://huggingface.co/spaces/thyn-ai/algenta-for-llm-agents) — RAG + governed agents demos
- [governed tool calls](https://huggingface.co/spaces/thyn-ai/algenta-governed-tool-calls)

## Packages

- [`algenta`](https://pypi.org/project/algenta/) — wrapper facade + CLI
- [`algenta-runtime-native`](https://pypi.org/project/algenta-runtime-native/) — the signed Mojo runtime wheel
- [`algenta-sdk`](https://pypi.org/project/algenta-sdk/) — typed client · [github.com/thyn-ai/algenta-sdk](https://github.com/thyn-ai/algenta-sdk)
"""
            )

    gr.HTML(render_footer())

if __name__ == "__main__":
    app.launch(theme=THEME, css=SHELL_CSS, js=FORCE_DARK_JS)
